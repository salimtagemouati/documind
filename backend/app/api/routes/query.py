"""
Query (RAG) API Routes
POST /api/v1/query/          — ask a question about a document
GET  /api/v1/query/history   — get user's query history
"""
import uuid
from uuid import UUID

import litellm
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.limiter import exempt_non_demo_request, limiter
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.database import get_db
from app.models.models import Document, DocumentStatus, QueryHistory, User
from app.schemas.schemas import (
    MultiQueryRequest,
    MultiQueryResponse,
    PaginatedResponse,
    QueryHistoryItem,
    QueryRequest,
    QueryResponse,
)
from app.services.ai_service import answer_question, synthesize_multi_document_query
from app.services.cache_service import get_cached_answer, set_cached_answer
from app.services.stripe_service import check_query_limit, increment_daily_queries

router = APIRouter(prefix="/query", tags=["Q&A"])
logger = get_logger(__name__)


@router.post("/", response_model=QueryResponse)
@limiter.limit("10/hour", exempt_when=exempt_non_demo_request)
async def query_document(
    request: Request,
    payload: QueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    RAG-powered question answering over a specific document.

    Flow:
    1. Verify document ownership and readiness
    2. Check cache for identical question
    3. If cache miss: run RAG pipeline with pgvector + re-ranking
    4. Persist to query history
    5. Return answer with source citations
    """
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["sub"])

    # Verify document exists and is owned by user
    result = await db.execute(
        select(Document).where(
            Document.id == payload.document_id,
            Document.user_id == user_id,
        )
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if doc.status != DocumentStatus.ready:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Document is {doc.status.value}. Please wait for processing to complete.",
        )

    # Check cache first (same question + document → return cached answer)
    query_id = uuid.uuid4()
    cached = await get_cached_answer(str(payload.document_id), payload.question)
    if cached:
        logger.info("query_cache_hit", document_id=str(payload.document_id))
        cached["from_cache"] = True
        cached["query_id"] = str(query_id)
        return QueryResponse(**cached)

    # ── Tier enforcement: check daily query limit (only for non-cached) ───
    is_demo = bool(current_user.get("is_demo"))
    if not is_demo:
        try:
            await check_query_limit(str(user_id), db)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    # Run RAG pipeline with pgvector and two-stage re-ranking
    try:
        response = await answer_question(
            document_id=payload.document_id,
            user_id=user_id,
            question=payload.question,
            query_id=query_id,
            filename=doc.original_filename,
            db=db,
            max_tokens=payload.max_tokens,
        )
    except litellm.RateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI service rate limit reached. Please try again later.",
        )
    except litellm.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI service timed out. Please try again later.",
        )
    except litellm.ServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable. Please try again later.",
        )

    if is_demo:
        return response

    # Persist to history
    history_entry = QueryHistory(
        id=query_id,
        user_id=user_id,
        document_id=payload.document_id,
        question=payload.question,
        answer=response.answer,
        sources=[s.model_dump(mode="json") for s in response.sources],
        model_used=response.model_used,
        tokens_used=response.tokens_used,
        latency_ms=response.latency_ms,
        from_cache=False,
    )
    db.add(history_entry)

    # Update user token usage
    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.queries_made = (user.queries_made or 0) + 1
        user.ai_tokens_used = (user.ai_tokens_used or 0) + response.tokens_used

    await db.commit()

    # Track daily query count for tier enforcement
    await increment_daily_queries(str(user_id), db)
    await db.commit()

    # Cache the response (serialize for storage)
    cache_payload = {
        "question": response.question,
        "answer": response.answer,
        "sources": [s.model_dump() for s in response.sources],
        "model_used": response.model_used,
        "tokens_used": response.tokens_used,
        "latency_ms": response.latency_ms,
        "from_cache": True,
        "query_id": str(query_id),
    }
    await set_cached_answer(str(payload.document_id), payload.question, cache_payload)

    return response


@router.post("/multi", response_model=MultiQueryResponse)
@limiter.limit("10/hour", exempt_when=exempt_non_demo_request)
async def query_multiple_documents(
    request: Request,
    payload: MultiQueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Multi-Document Cross-Query & Synthesis Engine.
    Retrieves evidence across multiple documents and generates a comparative,
    provenance-attributed synthesis.
    """
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["sub"])

    # Verify all documents exist, are owned by user, and are ready
    result = await db.execute(
        select(Document).where(
            Document.id.in_(payload.document_ids),
            Document.user_id == user_id,
        )
    )
    docs = result.scalars().all()
    if len(docs) != len(payload.document_ids):
        found_ids = {d.id for d in docs}
        missing = [str(did) for did in payload.document_ids if did not in found_ids]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"One or more documents not found or unauthorized: {', '.join(missing)}",
        )

    for d in docs:
        if d.status != DocumentStatus.ready:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f'Document "{d.original_filename}" is {d.status.value}. Please wait for processing to complete.',
            )

    # Tier enforcement
    is_demo = bool(current_user.get("is_demo"))
    if not is_demo:
        try:
            await check_query_limit(str(user_id), db)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    query_id = uuid.uuid4()
    docs_meta = [{"id": d.id, "name": d.original_filename or d.filename} for d in docs]

    # Synthesize across documents with balanced retrieval + cross-encoder reranking
    try:
        response = await synthesize_multi_document_query(
            document_ids=payload.document_ids,
            user_id=user_id,
            question=payload.question,
            query_id=query_id,
            documents_meta=docs_meta,
            db=db,
            max_tokens=payload.max_tokens,
            enable_rerank=payload.enable_rerank,
        )
    except litellm.RateLimitError:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="AI service rate limit reached. Please try again later.",
        )
    except litellm.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="AI service timed out. Please try again later.",
        )
    except litellm.ServiceUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service is temporarily unavailable. Please try again later.",
        )

    if is_demo:
        return response

    # Persist multi-document query in history
    history_entry = QueryHistory(
        id=query_id,
        user_id=user_id,
        document_id=payload.document_ids[0],
        document_ids=[str(did) for did in payload.document_ids],
        question=payload.question,
        answer=response.answer,
        sources=[s.model_dump(mode="json") for s in response.sources],
        model_used=response.model_used,
        tokens_used=response.tokens_used,
        latency_ms=response.latency_ms,
        from_cache=False,
    )
    db.add(history_entry)

    user_result = await db.execute(select(User).where(User.id == user_id))
    user = user_result.scalar_one_or_none()
    if user:
        user.queries_made = (user.queries_made or 0) + 1
        user.ai_tokens_used = (user.ai_tokens_used or 0) + response.tokens_used

    await db.commit()
    await increment_daily_queries(str(user_id), db)
    await db.commit()

    return response


@router.get("/history", response_model=PaginatedResponse)
async def get_query_history(
    document_id: UUID = None,
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the user's Q&A history, optionally filtered by document."""
    from uuid import UUID as UUIDType

    from sqlalchemy import func

    user_id = UUIDType(current_user["sub"])
    base_filter = [QueryHistory.user_id == user_id]
    if document_id:
        base_filter.append(QueryHistory.document_id == document_id)

    total_result = await db.execute(
        select(func.count(QueryHistory.id)).where(*base_filter)
    )
    total = total_result.scalar()

    items_result = await db.execute(
        select(QueryHistory)
        .where(*base_filter)
        .order_by(QueryHistory.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = items_result.scalars().all()

    return PaginatedResponse(
        items=[QueryHistoryItem.model_validate(q) for q in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )

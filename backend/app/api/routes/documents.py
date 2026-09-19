"""
Documents API Routes

POST /api/v1/documents/upload     — upload + trigger async processing
GET  /api/v1/documents/           — list user's documents
GET  /api/v1/documents/{id}       — get document metadata
GET  /api/v1/documents/{id}/analysis — get full AI analysis
DELETE /api/v1/documents/{id}     — delete document + cleanup
"""
import asyncio
import uuid
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db import database
from app.db.database import get_db
from app.models.models import Document, DocumentStatus, User
from app.schemas.schemas import (
    DocumentAnalysis,
    DocumentMeta,
    DocumentUploadResponse,
    EntityExtractionResult,
    MessageResponse,
    PaginatedResponse,
    SentimentResult,
)
from app.services.ai_service import (
    analyze_sentiment,
    extract_entities,
    extract_keywords,
    summarize_document,
)
from app.services.cache_service import (
    invalidate_document_cache,
)
from app.services.document_processor import chunk_text, extract_text, validate_file
from app.services.progress_service import publish_progress
from app.services.rag_service import build_document_index, delete_document_index
from app.services.stripe_service import check_document_limit

router = APIRouter(prefix="/documents", tags=["Documents"])
settings = get_settings()
logger = get_logger(__name__)


# ─── Background processing pipeline ──────────────────────────────────────────
async def process_document_pipeline(document_id: UUID, file_bytes: bytes, db_session_factory) -> None:
    """
    Full async processing pipeline — runs in background after upload response is sent.
    Now publishes real-time progress events via Redis pub/sub.

    Steps:
    1. Extract text from file
    2. Chunk text into RAG-ready segments
    3. Store chunks in DB
    4. Build FAISS vector index
    5. Run AI analysis (summary, entities, sentiment, keywords)
    6. Update document status → ready
    """
    doc_id_str = str(document_id)

    async with db_session_factory() as db:
        result = await db.execute(select(Document).where(Document.id == document_id))
        doc = result.scalar_one_or_none()
        if not doc:
            logger.error("pipeline_doc_not_found", document_id=doc_id_str)
            return

        try:
            # Mark as processing
            doc.status = DocumentStatus.processing
            await db.commit()

            # ── Stage 1: Extract text ─────────────────────────────────────
            await publish_progress(doc_id_str, "extracting", 10, "Extracting text from document...")
            logger.info("pipeline_extracting_text", document_id=doc_id_str)
            raw_text, page_count = extract_text(file_bytes, doc.file_type)
            doc.raw_text = raw_text
            doc.page_count = page_count

            await publish_progress(doc_id_str, "extracting", 20, f"Extracted {len(raw_text):,} characters")

            # ── Stage 2: Chunk ────────────────────────────────────────────
            await publish_progress(doc_id_str, "chunking", 30, "Splitting into semantic chunks...")
            logger.info("pipeline_chunking", document_id=doc_id_str)
            chunks_data = chunk_text(raw_text)
            doc.chunk_count = len(chunks_data)
            doc.token_count = sum(c["token_count"] for c in chunks_data)

            await publish_progress(
                doc_id_str, "chunking", 40,
                f"Created {len(chunks_data)} chunks ({doc.token_count:,} tokens)"
            )

            # ── Stage 3: Generate embeddings & persist to pgvector ─────────
            await publish_progress(doc_id_str, "embedding", 50, "Generating vector embeddings...")
            logger.info("pipeline_building_pgvector_index", document_id=doc_id_str)
            await build_document_index(db, document_id, chunks_data)

            await publish_progress(doc_id_str, "embedding", 65, "pgvector embeddings stored successfully")

            # ── Stage 5: AI analysis (run concurrently for speed) ─────────
            await publish_progress(doc_id_str, "analyzing", 70, "Running AI analysis...")
            logger.info("pipeline_running_ai", document_id=doc_id_str)

            summary_task = summarize_document(chunks_data, doc.original_filename)
            entities_task = extract_entities(chunks_data)
            sentiment_task = analyze_sentiment(chunks_data, doc.original_filename)
            keywords_task = extract_keywords(raw_text[:4000])

            await publish_progress(doc_id_str, "analyzing", 75, "Generating summary & extracting entities...")

            summary, entities, sentiment, keywords = await asyncio.gather(
                summary_task, entities_task, sentiment_task, keywords_task,
                return_exceptions=True,
            )

            await publish_progress(doc_id_str, "analyzing", 90, "Finalizing analysis results...")

            # Store results (skip individual failures gracefully)
            if isinstance(summary, str):
                doc.summary = summary
            if isinstance(entities, EntityExtractionResult):
                doc.entities = entities.model_dump()
            if isinstance(sentiment, SentimentResult):
                doc.sentiment = sentiment.model_dump()
            if isinstance(keywords, list):
                doc.keywords = keywords

            # ── Stage 6: Mark ready ───────────────────────────────────────
            from datetime import datetime, timezone
            doc.status = DocumentStatus.ready
            doc.processed_at = datetime.now(timezone.utc)

            # Update user stats
            user_result = await db.execute(select(User).where(User.id == doc.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                user.documents_processed = (user.documents_processed or 0) + 1

            await db.commit()

            await publish_progress(doc_id_str, "complete", 100, "Ready!")
            logger.info("pipeline_complete", document_id=doc_id_str)

        except Exception as e:
            logger.error("pipeline_failed", document_id=doc_id_str, error=str(e))
            doc.status = DocumentStatus.failed
            doc.error_message = str(e)[:500]
            await db.commit()

            await publish_progress(
                doc_id_str, "error", 0,
                f"Failed: {str(e)[:200]}"
            )


# ─── Routes ───────────────────────────────────────────────────────────────────
@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload a document. Returns immediately with status=pending.
    Processing happens asynchronously in the background.
    Connect via WebSocket at /api/v1/ws/documents/{id} for real-time progress.
    """
    if current_user.get("is_demo") or current_user.get("role") == "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo accounts are read-only. Create a free account to upload your own documents.",
        )

    file_bytes = await file.read()
    file_type = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    # Validate before storing
    try:
        validate_file(file.filename, len(file_bytes), file_type)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["sub"])

    # ── Tier enforcement: check document limit ────────────────────────
    try:
        await check_document_limit(str(user_id), db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(e))

    # Upload to Supabase Storage
    storage_path = f"{user_id}/{uuid.uuid4()}/{file.filename}"
    try:
        supabase = database.get_supabase_admin()
        supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
            path=storage_path,
            file=file_bytes,
            file_options={"content-type": file.content_type or "application/octet-stream"},
        )
    except Exception as e:
        logger.error("storage_upload_failed", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File upload failed")

    # Create DB record
    doc = Document(
        user_id=user_id,
        filename=storage_path.rsplit("/", 1)[-1],
        original_filename=file.filename,
        file_type=file_type,
        file_size_bytes=len(file_bytes),
        storage_path=storage_path,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    await db.flush()

    # Queue background processing (non-blocking)
    from app.db.database import AsyncSessionLocal
    background_tasks.add_task(process_document_pipeline, doc.id, file_bytes, AsyncSessionLocal)

    logger.info("document_uploaded", document_id=str(doc.id), filename=file.filename)
    return DocumentUploadResponse(
        id=doc.id,
        filename=doc.original_filename,
        file_type=doc.file_type,
        file_size_bytes=doc.file_size_bytes,
        status=doc.status.value,
        created_at=doc.created_at,
    )


@router.get("/", response_model=PaginatedResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the authenticated user's documents with pagination."""
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["sub"])
    offset = (page - 1) * page_size

    total_result = await db.execute(
        select(func.count(Document.id)).where(Document.user_id == user_id)
    )
    total = total_result.scalar()

    docs_result = await db.execute(
        select(Document)
        .where(Document.user_id == user_id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    docs = docs_result.scalars().all()

    return PaginatedResponse(
        items=[DocumentMeta.model_validate(d) for d in docs],
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.get("/{document_id}", response_model=DocumentMeta)
async def get_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get document metadata and processing status."""
    from uuid import UUID as UUIDType
    doc = await _get_user_document(document_id, UUIDType(current_user["sub"]), db)
    return DocumentMeta.model_validate(doc)


@router.get("/{document_id}/analysis", response_model=DocumentAnalysis)
async def get_document_analysis(
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get full AI analysis for a processed document."""
    from uuid import UUID as UUIDType
    doc = await _get_user_document(document_id, UUIDType(current_user["sub"]), db)

    if doc.status != DocumentStatus.ready:
        raise HTTPException(
            status_code=status.HTTP_202_ACCEPTED,
            detail=f"Document is still {doc.status.value}. Try again shortly.",
        )

    entities = EntityExtractionResult(**doc.entities) if doc.entities else None
    sentiment = SentimentResult(**doc.sentiment) if doc.sentiment else None

    return DocumentAnalysis(
        id=doc.id,
        filename=doc.original_filename,
        status=doc.status.value,
        summary=doc.summary,
        entities=entities,
        keywords=doc.keywords,
        sentiment=sentiment,
        chunk_count=doc.chunk_count,
        token_count=doc.token_count,
        page_count=doc.page_count,
        language=doc.language,
        processed_at=doc.processed_at,
    )


@router.delete("/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document, its chunks, FAISS index, and cached data."""
    if current_user.get("is_demo") or current_user.get("role") == "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo accounts are read-only. Cannot delete sample documents.",
        )

    from uuid import UUID as UUIDType
    doc = await _get_user_document(document_id, UUIDType(current_user["sub"]), db)

    # Delete from Supabase Storage
    try:
        database.get_supabase_admin().storage.from_(settings.SUPABASE_BUCKET).remove([doc.storage_path])
    except Exception as e:
        logger.warning("storage_delete_failed", error=str(e))

    # Delete FAISS index
    delete_document_index(document_id)

    # Invalidate cache
    await invalidate_document_cache(str(document_id))

    # Delete DB record (cascades to chunks + query history)
    await db.delete(doc)
    await db.commit()

    logger.info("document_deleted", document_id=str(document_id))
    return MessageResponse(message="Document deleted successfully")


# ─── Helpers ──────────────────────────────────────────────────────────────────
async def _get_user_document(document_id: UUID, user_id: UUID, db: AsyncSession) -> Document:
    """Fetch a document and verify ownership. Raises 404 if not found/owned."""
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc

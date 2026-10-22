"""
Documents API Routes

POST /api/v1/documents/upload     — upload + trigger async processing
GET  /api/v1/documents/           — list user's documents
GET  /api/v1/documents/{id}       — get document metadata
GET  /api/v1/documents/{id}/analysis — get full AI analysis
DELETE /api/v1/documents/{id}     — delete document + cleanup
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import litellm
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db import database
from app.db.database import get_db
from app.models.models import Document, DocumentStatus, QueryHistory, User
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
    analyze_document,
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
    4. Persist pgvector embeddings
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

        pipeline_stage = "extracting"
        try:
            async with asyncio.timeout(settings.DOCUMENT_PROCESSING_TIMEOUT_SECONDS):
                # Mark as processing
                doc.status = DocumentStatus.processing
                await db.commit()

                # ── Stage 1: Extract text ─────────────────────────────────────
                await publish_progress(doc_id_str, "extracting", 10, "Extracting text from document...")
                logger.info("pipeline_extracting_text", document_id=doc_id_str)
                raw_text, page_count = await asyncio.to_thread(extract_text, file_bytes, doc.file_type)
                doc.raw_text = raw_text
                doc.page_count = page_count

                await publish_progress(doc_id_str, "extracting", 20, f"Extracted {len(raw_text):,} characters")

                pipeline_stage = "chunking"
                # ── Stage 2: Chunk ────────────────────────────────────────────
                await publish_progress(doc_id_str, "chunking", 30, "Splitting into semantic chunks...")
                logger.info("pipeline_chunking", document_id=doc_id_str)
                chunks_data = await asyncio.to_thread(chunk_text, raw_text)
                if doc.file_type == "pdf":
                    for chunk in chunks_data:
                        chunk["page_number"] = chunk["page_number"] or 1
                doc.chunk_count = len(chunks_data)
                doc.token_count = sum(c["token_count"] for c in chunks_data)

                await publish_progress(
                    doc_id_str, "chunking", 40,
                    f"Created {len(chunks_data)} chunks ({doc.token_count:,} tokens)"
                )

                pipeline_stage = "embedding"
                # ── Stage 3: Generate embeddings & persist to pgvector ─────────
                await publish_progress(doc_id_str, "embedding", 50, "Indexing document passages...")
                logger.info("pipeline_building_pgvector_index", document_id=doc_id_str)
                await build_document_index(db, document_id, chunks_data)

                await publish_progress(doc_id_str, "embedding", 65, "Document passages indexed")

                pipeline_stage = "analysis"
                # ── Stage 5: AI analysis (run concurrently for speed) ─────────
                await publish_progress(doc_id_str, "analyzing", 70, "Running AI analysis...")
                logger.info("pipeline_running_ai", document_id=doc_id_str)

                if settings.ANALYSIS_MODE == "combined":
                    insights = await analyze_document(chunks_data, doc.original_filename)
                    summary, entities, sentiment, keywords = (
                        insights.summary, insights.entities, insights.sentiment, insights.keywords
                    )
                else:
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

                if all(isinstance(value, Exception) for value in (summary, entities, sentiment)):
                    raise next(value for value in (summary, entities, sentiment) if isinstance(value, Exception))

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
            logger.error("pipeline_failed", document_id=doc_id_str, stage=pipeline_stage, error_type=type(e).__name__, provider_status_code=getattr(e, "status_code", None))
            await db.rollback()
            doc = await db.get(Document, document_id)
            if doc is None:
                return
            doc.status = DocumentStatus.failed
            if isinstance(e, litellm.RateLimitError):
                doc.error_message = "AI provider request quota reached. Retry processing after your provider allowance resets."
            elif isinstance(e, (TimeoutError, litellm.Timeout)):
                doc.error_message = "Document processing timed out. Please retry later or upload a smaller file."
            elif pipeline_stage == "extracting":
                doc.error_message = "Could not extract readable text. Check the file; scanned PDFs require OCR before upload."
            else:
                doc.error_message = "Document processing failed. Check the file and server AI configuration, then retry processing."

            await db.commit()

            await publish_progress(
                doc_id_str, "error", 0,
                doc.error_message
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

    file_bytes = await file.read(settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
    filename = Path((file.filename or "").replace("\\", "/")).name
    file_type = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    # Validate before storing
    try:
        validate_file(filename, len(file_bytes), file_type)
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
    storage_path = f"{user_id}/{uuid.uuid4()}/{filename}"
    try:
        if _uses_local_storage():
            local_path = _local_storage_path(storage_path)
            await asyncio.to_thread(_write_local_original, local_path, file_bytes)
        else:
            supabase = database.get_supabase_admin()
            await asyncio.to_thread(
                supabase.storage.from_(settings.SUPABASE_BUCKET).upload,
                path=storage_path,
                file=file_bytes,
                file_options={"content-type": file.content_type or "application/octet-stream"},
            )
    except Exception as e:
        logger.error("storage_upload_failed", error_type=type(e).__name__)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File upload failed")

    # Create DB record
    doc = Document(
        user_id=user_id,
        filename=storage_path.rsplit("/", 1)[-1],
        original_filename=filename,
        file_type=file_type,
        file_size_bytes=len(file_bytes),
        storage_path=storage_path,
        status=DocumentStatus.pending,
    )
    db.add(doc)
    await db.flush()

    # Background tasks use a separate session; make the record visible first.
    await db.commit()

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


@router.post("/{document_id}/retry", response_model=DocumentMeta, status_code=202)
async def retry_document(
    document_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Reprocess a failed original without creating another document or upload."""
    if current_user.get("is_demo"):
        raise HTTPException(status_code=403, detail="Demo accounts are read-only.")
    result = await db.execute(select(Document).where(
        Document.id == document_id, Document.user_id == UUID(current_user["sub"])
    ).with_for_update())
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if doc.status != DocumentStatus.failed:
        raise HTTPException(status_code=409, detail="Only failed documents can be retried.")
    try:
        if _uses_local_storage():
            def read_original():
                with _local_storage_path(doc.storage_path).open("rb") as source:
                    return source.read(settings.MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
            file_bytes = await asyncio.to_thread(read_original)
        else:
            file_bytes = await asyncio.to_thread(
                database.get_supabase_admin().storage.from_(settings.SUPABASE_BUCKET).download,
                doc.storage_path,
            )
        validate_file(doc.original_filename, len(file_bytes), doc.file_type)
    except Exception as exc:
        logger.warning("retry_original_unavailable", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Could not read the stored original. Please retry later or upload it again.") from None
    doc.status = DocumentStatus.pending
    doc.error_message = None
    await db.commit()
    from app.db.database import AsyncSessionLocal
    background_tasks.add_task(process_document_pipeline, doc.id, file_bytes, AsyncSessionLocal)
    return DocumentMeta.model_validate(doc)


@router.get("/", response_model=PaginatedResponse)
async def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the authenticated user's documents with pagination."""
    from uuid import UUID as UUIDType
    user_id = UUIDType(current_user["sub"])
    await _recover_stalled_documents(db, user_id)
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
    """Delete a document, its cascaded chunks, and cached data."""
    if current_user.get("is_demo") or current_user.get("role") == "demo":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo accounts are read-only. Cannot delete sample documents.",
        )

    from uuid import UUID as UUIDType
    doc = await _get_user_document(document_id, UUIDType(current_user["sub"]), db)

    # Delete from Supabase Storage
    try:
        if _uses_local_storage():
            await asyncio.to_thread(_local_storage_path(doc.storage_path).unlink, missing_ok=True)
        else:
            await asyncio.to_thread(
                database.get_supabase_admin().storage.from_(settings.SUPABASE_BUCKET).remove,
                [doc.storage_path],
            )
    except Exception as e:
        logger.warning("storage_delete_failed", error_type=type(e).__name__)
        raise HTTPException(status_code=503, detail="Could not delete the stored original. Please retry.") from None

    # pgvector chunks are removed by the database cascade.
    delete_document_index(document_id)

    # Invalidate cache
    await invalidate_document_cache(str(document_id))

    # Remove saved excerpts, including cross-document answers, with the source.
    histories = (await db.execute(select(QueryHistory).where(QueryHistory.user_id == doc.user_id))).scalars().all()
    for history in histories:
        if history.document_id == document_id or str(document_id) in (history.document_ids or []):
            await db.delete(history)
    await db.flush()

    # Delete DB record and cascaded chunks
    await db.delete(doc)
    await db.commit()

    logger.info("document_deleted", document_id=str(document_id))
    return MessageResponse(message="Document deleted successfully")


# ─── Helpers ──────────────────────────────────────────────────────────────────
async def _get_user_document(document_id: UUID, user_id: UUID, db: AsyncSession) -> Document:
    """Fetch a document and verify ownership. Raises 404 if not found/owned."""
    await _recover_stalled_documents(db, user_id)
    result = await db.execute(
        select(Document).where(Document.id == document_id, Document.user_id == user_id)
    )
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc


def _local_storage_path(storage_path: str) -> Path:
    """Keep local originals beneath the configured private upload directory."""
    root = Path(settings.LOCAL_UPLOAD_DIR).resolve()
    target = (root / storage_path).resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError("Invalid storage path")
    return target


def _uses_local_storage() -> bool:
    return settings.STORAGE_BACKEND == "local" or (
        settings.STORAGE_BACKEND == "auto" and settings.DATABASE_URL.startswith("sqlite")
    )


async def _recover_stalled_documents(db: AsyncSession, user_id: UUID) -> None:
    """Expose interrupted jobs as retryable failures after the processing deadline.

    The grace interval avoids racing a worker finalizing its timeout. Ownership
    filters prevent a workspace read from changing another tenant's job state.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.DOCUMENT_PROCESSING_TIMEOUT_SECONDS + 30)
    await db.execute(update(Document).where(
        Document.user_id == user_id,
        Document.status.in_([DocumentStatus.pending, DocumentStatus.processing]),
        Document.updated_at < cutoff,
    ).values(status=DocumentStatus.failed, error_message="Processing was interrupted. Retry processing to use the stored original."))


def _write_local_original(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as target:
        target.write(content)

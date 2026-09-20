"""
RAG (Retrieval-Augmented Generation) Service with pgvector & Hybrid Retrieval

Architecture:
  1. Embed document chunks using LiteLLM / Gemini embeddings (768d)
  2. Store embeddings durably in PostgreSQL using pgvector (HNSW index)
  3. Hybrid Retrieval:
     - Dense Semantic Search: Cosine distance via pgvector `<=>`
     - Sparse Lexical Search: PostgreSQL full-text search (tsvector/GIN)
     - Reciprocal Rank Fusion (RRF) combines sparse + dense candidate ranks
  4. Chunks are permanently persisted in PostgreSQL — zero ephemeral index files,
     no startup wipes, fully multi-tenant via RLS and document foreign keys.
"""
import os
import re
from typing import List, Sequence, Union
from uuid import UUID

import litellm
import numpy as np
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.models import Document, DocumentChunk
from app.services.llm_limiter import call_with_limits

settings = get_settings()
logger = get_logger(__name__)

EMBEDDING_DIM = settings.EMBEDDING_DIM
RRF_K = 60


def reciprocal_rank_fusion_score(
    *, vector_rank: int | None, text_rank: int | None, k: int = RRF_K
) -> float:
    """Combine independent result-list ranks using standard RRF."""
    return sum(
        1.0 / (k + rank)
        for rank in (vector_rank, text_rank)
        if rank is not None
    )


# ─── Embedding Helpers ────────────────────────────────────────────────────────
async def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a batch of texts using LiteLLM / configured embedding provider.
    Returns an ndarray of shape (len(texts), EMBEDDING_DIM).
    """
    if not texts:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    # Ensure environment variables for LiteLLM provider
    if settings.GOOGLE_API_KEY:
        os.environ.setdefault("GEMINI_API_KEY", settings.GOOGLE_API_KEY)
        os.environ.setdefault("GOOGLE_API_KEY", settings.GOOGLE_API_KEY)

    all_embeddings = []
    batch_size = 100  # Max batch size per call for free-tier efficiency

    google_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        kwargs = {
            "model": settings.EMBEDDING_MODEL,
            "input": batch,
            "dimensions": settings.EMBEDDING_DIM,
        }
        if google_key and "gemini" in settings.EMBEDDING_MODEL:
            kwargs["api_key"] = google_key
        elif openai_key:
            kwargs["api_key"] = openai_key

        try:
            response = await call_with_limits(lambda: litellm.aembedding(**kwargs))
            batch_embeddings = [item["embedding"] for item in response.data]
            all_embeddings.extend(batch_embeddings)
        except Exception as e:
            logger.error("embedding_failed", error_type=type(e).__name__, model=settings.EMBEDDING_MODEL, batch_size=len(batch))
            raise

    arr = np.array(all_embeddings, dtype=np.float32)
    # Re-normalize vectors to unit norm (Matryoshka truncation breaks unit length)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    arr = arr / norms
    return arr


async def embed_query(query: str) -> np.ndarray:
    """Embed a single query string for retrieval via LiteLLM."""
    google_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
    if google_key:
        os.environ.setdefault("GEMINI_API_KEY", google_key)
        os.environ.setdefault("GOOGLE_API_KEY", google_key)

    kwargs = {
        "model": settings.EMBEDDING_MODEL,
        "input": [query],
        "dimensions": settings.EMBEDDING_DIM,
    }
    if google_key and "gemini" in settings.EMBEDDING_MODEL:
        kwargs["api_key"] = google_key
    elif openai_key:
        kwargs["api_key"] = openai_key

    try:
        response = await call_with_limits(lambda: litellm.aembedding(**kwargs))
        vec = np.array(response.data[0]["embedding"], dtype=np.float32)
    except Exception as e:
        logger.error("query_embedding_failed", error_type=type(e).__name__, model=settings.EMBEDDING_MODEL)
        raise

    # Strictly re-normalize to unit vector
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec


# ─── pgvector Index Building ──────────────────────────────────────────────────
async def build_document_index(db: AsyncSession, document_id: UUID, chunks: List[dict]) -> None:
    """
    Embed all chunks and store them durably in PostgreSQL with pgvector.
    Runs asynchronously during document processing.
    """
    if not chunks:
        logger.warning("no_chunks_to_index", document_id=str(document_id))
        return

    is_sqlite = db.get_bind().dialect.name == "sqlite"
    embeddings = None
    if not is_sqlite:
        texts = [c["content"] for c in chunks]
        logger.info("generating_embeddings", document_id=str(document_id), chunk_count=len(chunks))
        embeddings = await embed_texts(texts)

    # Fetch existing chunks or insert new ones
    result = await db.execute(
        select(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
        .order_by(DocumentChunk.chunk_index)
    )
    existing_chunks = result.scalars().all()
    chunk_map = {c.chunk_index: c for c in existing_chunks}

    for idx, c_data in enumerate(chunks):
        vec_list = None if embeddings is None else embeddings[idx].tolist()
        chunk_obj = chunk_map.get(c_data["chunk_index"])
        if chunk_obj:
            chunk_obj.embedding = vec_list
        else:
            new_chunk = DocumentChunk(
                document_id=document_id,
                chunk_index=c_data["chunk_index"],
                content=c_data["content"],
                token_count=c_data["token_count"],
                page_number=c_data.get("page_number"),
                embedding=vec_list,
            )
            db.add(new_chunk)

    await db.commit()
    logger.info(
        "document_index_built",
        document_id=str(document_id),
        chunks=len(chunks),
        mode="sqlite-lexical" if is_sqlite else "pgvector",
    )


async def _retrieve_sqlite_chunks(
    db: AsyncSession,
    *,
    doc_ids: list[UUID],
    user_id: UUID,
    query: str,
    top_k: int,
) -> list[dict]:
    """Portable lexical fallback for local SQLite development."""
    statement = (
        select(DocumentChunk, Document.original_filename, Document.filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.document_id.in_(doc_ids), Document.user_id == user_id)
    )
    rows = (await db.execute(statement)).all()
    terms = {term for term in re.findall(r"\w+", query.lower()) if len(term) > 2}
    ranked = []
    for chunk, original_name, filename in rows:
        content_terms = set(re.findall(r"\w+", chunk.content.lower()))
        matches = len(terms & content_terms)
        if terms and matches == 0:
            continue
        score = matches / len(terms) if terms else 0.0
        ranked.append((score, chunk, original_name or filename or "Document"))

    ranked.sort(key=lambda item: (item[0], -item[1].chunk_index), reverse=True)
    return [
        {
            "chunk_id": str(chunk.id),
            "document_id": chunk.document_id,
            "document_name": document_name,
            "content": chunk.content,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "similarity_score": round(score, 4),
            "vector_rank": None,
            "text_rank": rank,
            "rrf_score": round(1 / (RRF_K + rank), 5),
        }
        for rank, (score, chunk, document_name) in enumerate(ranked[:top_k], start=1)
    ]


# ─── Retrieval (Dense Vector + Sparse Keyword RRF) ───────────────────────────
async def retrieve_similar_chunks(
    db: AsyncSession,
    document_id: Union[UUID, Sequence[UUID]],
    user_id: UUID,
    query: str,
    top_k: int | None = None,
    threshold: float | None = None,
    enable_hybrid: bool | None = None,
) -> List[dict]:
    """
    Retrieves the most relevant chunks using pgvector cosine distance and optional
    PostgreSQL Full-Text Search with Reciprocal Rank Fusion (RRF).

    Supports:
      - Single document queries (document_id is UUID)
      - Multi-document queries (document_id is Sequence[UUID])
    """
    top_k = settings.RAG_TOP_K if top_k is None else top_k
    threshold = settings.RAG_SIMILARITY_THRESHOLD if threshold is None else threshold
    enable_hybrid = settings.ENABLE_HYBRID_SEARCH if enable_hybrid is None else enable_hybrid

    doc_ids = [document_id] if isinstance(document_id, UUID) else list(document_id)
    if not doc_ids:
        return []

    if db.get_bind().dialect.name == "sqlite":
        return await _retrieve_sqlite_chunks(
            db,
            doc_ids=doc_ids,
            user_id=user_id,
            query=query,
            top_k=top_k,
        )

    query_vec = (await embed_query(query)).tolist()

    # ── 1. Dense Semantic Vector Search ──────────────────────────────────────
    # In pgvector: cosine_distance in [0, 2]. Cosine similarity = 1 - cosine_distance
    sim_col = (1 - DocumentChunk.embedding.cosine_distance(query_vec)).label("sim_score")

    stmt = (
        select(
            DocumentChunk,
            sim_col,
            Document.original_filename,
            Document.filename,
        )
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.document_id.in_(doc_ids))
        .where(Document.user_id == user_id)
        .where(DocumentChunk.embedding.is_not(None))
        .order_by(DocumentChunk.embedding.cosine_distance(query_vec))
        .limit(top_k * 2 if enable_hybrid else top_k)
    )

    result = await db.execute(stmt)
    vector_rows = result.all()

    # Map candidate by chunk.id
    candidates = {}
    for rank, (chunk, sim_score, orig_name, fname) in enumerate(vector_rows, start=1):
        doc_name = orig_name or fname or "Document"
        score = float(sim_score)
        candidates[str(chunk.id)] = {
            "chunk_id": str(chunk.id),
            "document_id": chunk.document_id,
            "document_name": doc_name,
            "content": chunk.content,
            "chunk_index": chunk.chunk_index,
            "page_number": chunk.page_number,
            "similarity_score": round(max(0.0, score), 4),
            "vector_rank": rank,
            "text_rank": None,
        }

    # ── 2. Sparse Lexical Search (Hybrid FTS) ──────────────────────────────────
    if enable_hybrid:
        try:
            # Clean query terms for plain tsquery
            clean_q = " ".join([w for w in query.split() if len(w) > 2])
            if clean_q:
                fts_stmt = (
                    select(
                        DocumentChunk,
                        Document.original_filename,
                        Document.filename,
                        func.ts_rank_cd(
                            func.to_tsvector("english", DocumentChunk.content),
                            func.plainto_tsquery("english", clean_q),
                        ).label("text_rank_score")
                    )
                    .join(Document, DocumentChunk.document_id == Document.id)
                    .where(DocumentChunk.document_id.in_(doc_ids))
                    .where(Document.user_id == user_id)
                    .where(
                        func.to_tsvector("english", DocumentChunk.content).op("@@")(
                            func.plainto_tsquery("english", clean_q)
                        )
                    )
                    .order_by(func.ts_rank_cd(
                        func.to_tsvector("english", DocumentChunk.content),
                        func.plainto_tsquery("english", clean_q)
                    ).desc())
                    .limit(top_k * 2)
                )
                fts_res = await db.execute(fts_stmt)
                fts_rows = fts_res.all()
                for rank, (chunk, orig_name, fname, _) in enumerate(fts_rows, start=1):
                    cid_str = str(chunk.id)
                    if cid_str not in candidates:
                        candidates[cid_str] = {
                            "chunk_id": cid_str,
                            "document_id": chunk.document_id,
                            "document_name": orig_name or fname or "Document",
                            "content": chunk.content,
                            "chunk_index": chunk.chunk_index,
                            "page_number": chunk.page_number,
                            "similarity_score": 0.0,
                            "vector_rank": None,
                            "text_rank": rank,
                        }
                    else:
                        candidates[cid_str]["text_rank"] = rank
        except Exception as fts_err:
            logger.debug("fts_hybrid_skipped", error_type=type(fts_err).__name__)

    # ── 3. Reciprocal Rank Fusion (RRF) Scoring ──────────────────────────────
    results = []
    for c in candidates.values():
        vec_r = c["vector_rank"]
        txt_r = c["text_rank"]

        rrf = reciprocal_rank_fusion_score(vector_rank=vec_r, text_rank=txt_r)

        c["rrf_score"] = round(rrf, 5)
        # Keep chunk if vector similarity is reasonable or exact keyword match was found
        if c["similarity_score"] >= threshold or txt_r is not None:
            results.append(c)

    # Sort by RRF score (or similarity score if hybrid disabled)
    results.sort(key=lambda x: (x.get("rrf_score", 0), x["similarity_score"]), reverse=True)
    final_chunks = results[:top_k]

    logger.info(
        "chunks_retrieved_pgvector",
        doc_count=len(doc_ids),
        query_preview=query[:60],
        retrieved=len(final_chunks),
    )
    return final_chunks


def delete_document_index(document_id: UUID) -> None:
    """
    Retained for backward compatibility. In pgvector, chunks and embeddings
    are deleted automatically via ON DELETE CASCADE in PostgreSQL.
    """
    logger.info("pgvector_document_cascade_deleted", document_id=str(document_id))

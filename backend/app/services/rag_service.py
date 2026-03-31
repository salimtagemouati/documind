"""
RAG (Retrieval-Augmented Generation) Service

Architecture:
  1. Embed each document chunk using Google text-embedding-004 (768d)
  2. Store embeddings in a per-document FAISS index (persisted to disk)
  3. At query time: embed the question, retrieve top-K similar chunks
  4. Pass retrieved chunks as context to the LLM for grounded answers

Why FAISS over a managed vector DB?
- Zero cost, runs in-process, sub-millisecond retrieval for <100K chunks
- For scale (millions of chunks), swap in Pinecone, pgvector, or Qdrant
  with a one-function change to `_search_similar`
"""
import asyncio
import json
import os
import pickle
from pathlib import Path
from typing import List, Tuple
from uuid import UUID

import faiss
import numpy as np
import google.generativeai as genai

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)

# Configure Gemini SDK
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Local directory to persist FAISS indexes
FAISS_INDEX_DIR = Path("./data/faiss_indexes")
FAISS_INDEX_DIR.mkdir(parents=True, exist_ok=True)

EMBEDDING_DIM = 768  # text-embedding-004 output dimension


# ─── Embedding ────────────────────────────────────────────────────────────────
async def embed_texts(texts: List[str]) -> np.ndarray:
    """
    Embed a batch of texts using Google's embedding API.
    Returns an ndarray of shape (len(texts), EMBEDDING_DIM).

    Google's embed_content supports batching natively. We batch in groups
    of 100 to stay safely under API limits.
    """
    all_embeddings = []
    batch_size = 100

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]

        # embed_content is synchronous — run in executor to avoid blocking
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda b=batch: genai.embed_content(
                model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
                content=b,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        batch_embeddings = result["embedding"]
        # Single text returns a flat list, multiple returns list of lists
        if batch_embeddings and not isinstance(batch_embeddings[0], list):
            batch_embeddings = [batch_embeddings]
        all_embeddings.extend(batch_embeddings)
        logger.debug("embeddings_created", batch=i // batch_size, count=len(batch))

    return np.array(all_embeddings, dtype=np.float32)


async def embed_query(query: str) -> np.ndarray:
    """Embed a single query string (uses RETRIEVAL_QUERY task type for better retrieval)."""
    result = await asyncio.get_event_loop().run_in_executor(
        None,
        lambda: genai.embed_content(
            model=f"models/{settings.GEMINI_EMBEDDING_MODEL}",
            content=query,
            task_type="RETRIEVAL_QUERY",
        ),
    )
    embedding = result["embedding"]
    return np.array(embedding, dtype=np.float32)


# ─── FAISS index management ──────────────────────────────────────────────────
def _index_path(document_id: UUID) -> Path:
    return FAISS_INDEX_DIR / f"{document_id}.faiss"


def _meta_path(document_id: UUID) -> Path:
    return FAISS_INDEX_DIR / f"{document_id}.meta"


def _load_index(document_id: UUID) -> Tuple[faiss.Index, List[dict]] | Tuple[None, None]:
    """Load FAISS index and chunk metadata from disk. Returns (None, None) if not found."""
    idx_path = _index_path(document_id)
    meta_path = _meta_path(document_id)

    if not idx_path.exists() or not meta_path.exists():
        return None, None

    index = faiss.read_index(str(idx_path))
    with open(meta_path, "rb") as f:
        metadata = pickle.load(f)

    return index, metadata


def _save_index(document_id: UUID, index: faiss.Index, metadata: List[dict]) -> None:
    faiss.write_index(index, str(_index_path(document_id)))
    with open(_meta_path(document_id), "wb") as f:
        pickle.dump(metadata, f)
    logger.info("faiss_index_saved", document_id=str(document_id), vectors=index.ntotal)


# ─── Index building ───────────────────────────────────────────────────────────
async def build_document_index(document_id: UUID, chunks: List[dict]) -> None:
    """
    Embed all chunks and build a FAISS index for a document.
    Called once during document processing, runs in background.

    chunks: list of {content, chunk_index, token_count, page_number}
    """
    if not chunks:
        logger.warning("no_chunks_to_index", document_id=str(document_id))
        return

    texts = [c["content"] for c in chunks]

    logger.info("building_index", document_id=str(document_id), chunks=len(chunks))
    embeddings = await embed_texts(texts)

    # FAISS IndexFlatIP: inner product (equivalent to cosine sim on normalized vectors)
    faiss.normalize_L2(embeddings)
    index = faiss.IndexFlatIP(EMBEDDING_DIM)
    index.add(embeddings)

    # Metadata maps FAISS vector position → chunk data
    metadata = [
        {
            "chunk_index": c["chunk_index"],
            "content": c["content"],
            "token_count": c["token_count"],
            "page_number": c.get("page_number"),
        }
        for c in chunks
    ]

    _save_index(document_id, index, metadata)
    logger.info("index_built", document_id=str(document_id), total_vectors=len(chunks))


# ─── Retrieval ────────────────────────────────────────────────────────────────
async def retrieve_similar_chunks(
    document_id: UUID,
    query: str,
    top_k: int = None,
    threshold: float = None,
) -> List[dict]:
    """
    Embed the query and return the top-K most similar chunks from the index.

    Returns list of:
    {
        "content": str,
        "chunk_index": int,
        "page_number": int | None,
        "similarity_score": float,    # 0.0 – 1.0
    }
    """
    top_k = top_k or settings.RAG_TOP_K
    threshold = threshold or settings.RAG_SIMILARITY_THRESHOLD

    index, metadata = _load_index(document_id)
    if index is None:
        raise ValueError(f"No FAISS index found for document {document_id}. "
                         "Document may still be processing.")

    query_embedding = await embed_query(query)
    query_embedding = np.array([query_embedding], dtype=np.float32)
    faiss.normalize_L2(query_embedding)

    scores, indices = index.search(query_embedding, min(top_k, index.ntotal))

    results = []
    for score, idx in zip(scores[0], indices[0]):
        if idx == -1:  # FAISS sentinel for "not enough results"
            continue
        if float(score) < threshold:
            continue
        chunk = metadata[idx]
        results.append({
            "content": chunk["content"],
            "chunk_index": chunk["chunk_index"],
            "page_number": chunk.get("page_number"),
            "similarity_score": round(float(score), 4),
        })

    logger.info(
        "chunks_retrieved",
        document_id=str(document_id),
        query_preview=query[:80],
        results=len(results),
    )
    return results


def delete_document_index(document_id: UUID) -> None:
    """Clean up FAISS files when a document is deleted."""
    for path in [_index_path(document_id), _meta_path(document_id)]:
        if path.exists():
            path.unlink()
    logger.info("faiss_index_deleted", document_id=str(document_id))


def purge_all_indexes() -> int:
    """
    Delete ALL FAISS indexes. Called on startup when the embedding model changes
    (e.g., migrating from OpenAI 1536d to Gemini 768d embeddings).
    Returns the number of files deleted.
    """
    deleted = 0
    if FAISS_INDEX_DIR.exists():
        for f in FAISS_INDEX_DIR.iterdir():
            if f.suffix in (".faiss", ".meta"):
                f.unlink()
                deleted += 1
    if deleted:
        logger.warning("faiss_indexes_purged", files_deleted=deleted,
                        reason="Embedding model changed — old indexes incompatible")
    return deleted

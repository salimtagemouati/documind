"""
AI Service — Multi-Provider LLM Document Intelligence (LiteLLM Abstraction)

Supports Google Gemini (default: gemini-2.0-flash), OpenAI (gpt-4o-mini),
Anthropic (claude-3-5-sonnet), Groq, and local Ollama via unified config.
Robust JSON parsing handles cross-provider formatting discrepancies.
"""
import json
import os
import re
import time
from typing import List
from uuid import UUID

import litellm
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.schemas import (
    EntityExtractionResult,
    MultiQueryResponse,
    MultiSourceChunk,
    QueryResponse,
    SentimentResult,
    SourceChunk,
)
from app.services.llm_limiter import call_with_limits
from app.services.rag_service import retrieve_similar_chunks
from app.services.rerank_service import rerank_chunks

settings = get_settings()
logger = get_logger(__name__)

# LiteLLM global settings
litellm.drop_params = True


# ─── Retry Decorator ─────────────────────────────────────────────────────────
def _ai_retry():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=25),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )


# ─── Multi-Provider Execution Helpers ─────────────────────────────────────────
def _get_provider_kwargs() -> dict:
    kwargs = {"model": settings.LLM_MODEL}
    google_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
    anthropic_key = settings.ANTHROPIC_API_KEY or os.environ.get("ANTHROPIC_API_KEY")
    groq_key = settings.GROQ_API_KEY or os.environ.get("GROQ_API_KEY")

    if google_key and "gemini" in settings.LLM_MODEL:
        kwargs["api_key"] = google_key
    elif openai_key and "gpt" in settings.LLM_MODEL:
        kwargs["api_key"] = openai_key
    elif anthropic_key and "claude" in settings.LLM_MODEL:
        kwargs["api_key"] = anthropic_key
    elif groq_key and "groq" in settings.LLM_MODEL:
        kwargs["api_key"] = groq_key
    elif "ollama" in settings.LLM_MODEL:
        kwargs["api_base"] = settings.OLLAMA_API_BASE
    return kwargs


async def _generate_text(prompt: str, max_tokens: int = 800, temperature: float = 0.2) -> str:
    """Generate freeform text using the configured LLM provider via LiteLLM."""
    kwargs = _get_provider_kwargs()
    kwargs.update({
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
    })
    response = await call_with_limits(lambda: litellm.acompletion(**kwargs))
    text = response.choices[0].message.content or ""
    return text.strip()


async def _generate_json(prompt: str, max_tokens: int = 800, temperature: float = 0.1) -> dict:
    """Generate structured JSON with markdown strip and parsing fallback."""
    kwargs = _get_provider_kwargs()
    kwargs.update({
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    })
    try:
        response = await call_with_limits(lambda: litellm.acompletion(**kwargs))
        raw_text = response.choices[0].message.content or "{}"
    except Exception as e:
        logger.warning("json_response_format_failed_retrying_plain", error=str(e))
        # Some older/free endpoints fail on explicit response_format
        kwargs.pop("response_format", None)
        response = await call_with_limits(lambda: litellm.acompletion(**kwargs))
        raw_text = response.choices[0].message.content or "{}"

    # Clean code fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip())
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    # Find JSON block if extra text surrounds it
    json_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
    if json_match:
        cleaned = json_match.group(1)

    return json.loads(cleaned)


# ─── Summarization ────────────────────────────────────────────────────────────
@_ai_retry()
async def summarize_document(
    chunks: List[dict],
    filename: str,
    max_tokens: int = 600,
) -> str:
    """
    Summarize a document using map-reduce or single pass depending on length.
    """
    if len(chunks) <= 15:
        full_text = "\n\n---\n\n".join(c["content"] for c in chunks)
        prompt = f"""You are analyzing a document titled "{filename}".
Write a clear, professional executive summary in 3-5 sentences covering the core themes, major points, and key conclusions.

Document content:
{full_text[:14000]}"""
        return await _generate_text(prompt, max_tokens=max_tokens)

    # Multi-pass for large documents
    group_summaries = []
    for i in range(0, min(len(chunks), 40), 10):
        group = chunks[i : i + 10]
        group_text = "\n\n".join(c["content"] for c in group)
        summary = await _generate_text(
            f"Summarize this document section in 2-3 sentences:\n\n{group_text[:6000]}",
            max_tokens=200,
        )
        group_summaries.append(summary)

    combined = "\n\n".join(group_summaries)
    prompt = f"""You are given section summaries of a document titled "{filename}".
Synthesize them into a coherent executive summary in 4-6 sentences capturing the main themes and conclusions.

Section summaries:
{combined}"""
    return await _generate_text(prompt, max_tokens=max_tokens)


# ─── Entity Extraction ────────────────────────────────────────────────────────
@_ai_retry()
async def extract_entities(chunks: List[dict]) -> EntityExtractionResult:
    """Extract named entities from document content."""
    n = len(chunks)
    if n <= 10:
        sample = chunks
    else:
        indices = list(range(0, 5)) + list(range(n // 2 - 2, n // 2 + 3)) + list(range(n - 3, n))
        sample = [chunks[i] for i in sorted(set(indices)) if i < n]

    text = "\n\n".join(c["content"] for c in sample)[:9000]

    prompt = f"""Extract named entities from this text. Return valid JSON with these exact keys:
{{
  "persons": ["list of person names"],
  "organizations": ["list of organizations/companies"],
  "locations": ["list of countries, cities, regions"],
  "dates": ["list of specific dates or periods"],
  "technologies": ["list of software, models, tools, frameworks"],
  "monetary_values": ["list of financial amounts, prices, budgets"],
  "other": ["other significant entities"]
}}

Rules:
- Include only specific, named entities
- De-duplicate entries
- Max 15 items per category
- Use empty array if category is absent

Text:
{text}"""

    raw = await _generate_json(prompt, max_tokens=600)
    return EntityExtractionResult(**{k: v for k, v in raw.items() if isinstance(v, list)})


# ─── Sentiment Analysis ───────────────────────────────────────────────────────
@_ai_retry()
async def analyze_sentiment(chunks: List[dict], filename: str) -> SentimentResult:
    """Analyze the tone and sentiment distribution of document content."""
    sample_chunks = chunks[:3] + chunks[-2:] if len(chunks) > 5 else chunks
    text = "\n\n".join(c["content"] for c in sample_chunks)[:6000]

    prompt = f"""Analyze the sentiment and tone of this document titled "{filename}".
Return valid JSON with these exact keys:
{{
  "label": "Positive" or "Negative" or "Neutral" or "Mixed",
  "score": <float 0.0 to 1.0 where 1.0 is most positive>,
  "confidence": <float 0.0 to 1.0>,
  "tone": "formal" or "informal" or "technical" or "persuasive" or "critical" or "neutral" or "alarming" or "optimistic",
  "explanation": "<one sentence explaining the assessment>"
}}

Text:
{text}"""

    raw = await _generate_json(prompt, max_tokens=250)
    return SentimentResult(**raw)


# ─── Single Document Question Answering ───────────────────────────────────────
async def answer_question(
    document_id: UUID,
    question: str,
    query_id: UUID,
    filename: str,
    db: AsyncSession,
    max_tokens: int = 800,
    enable_rerank: bool = True,
) -> QueryResponse:
    """
    Two-stage RAG Pipeline:
    1. Hybrid dense+sparse retrieval from pgvector (initial top-15 candidates)
    2. Cross-encoder / LLM re-ranking to top-6 high-information chunks
    3. Grounded answer generation with strict citation adherence
    """
    start_ms = int(time.time() * 1000)

    # Step 1: Initial candidate retrieval
    initial_top_k = settings.RAG_INITIAL_TOP_K if enable_rerank else settings.RAG_TOP_K
    candidates = await retrieve_similar_chunks(
        db=db,
        document_id=document_id,
        query=question,
        top_k=initial_top_k,
    )

    if not candidates:
        return QueryResponse(
            question=question,
            answer="I couldn't find relevant information in this document to answer your question. "
                   "Please try rephrasing or asking about a topic covered in the document.",
            sources=[],
            model_used=settings.LLM_MODEL,
            tokens_used=0,
            latency_ms=int(time.time() * 1000) - start_ms,
            from_cache=False,
            query_id=query_id,
            reranked=False,
        )

    # Step 2: Re-ranking
    if enable_rerank and len(candidates) > settings.RAG_TOP_K:
        similar_chunks = await rerank_chunks(
            query=question,
            chunks=candidates,
            top_k=settings.RAG_TOP_K,
        )
        is_reranked = True
    else:
        similar_chunks = candidates[:settings.RAG_TOP_K]
        is_reranked = False

    # Step 3: Context block with citations
    context_blocks = []
    for i, chunk in enumerate(similar_chunks, 1):
        page_info = f" (Page {chunk['page_number']})" if chunk.get("page_number") else ""
        context_blocks.append(f"[Source {i}{page_info}]\n{chunk['content']}")

    context = "\n\n".join(context_blocks)

    # Step 4: Grounded generation
    prompt = f"""You are DocuMind, an expert document analyst.
Answer questions based ONLY on the provided document context. Do not use external knowledge or fabricate claims.

Rules:
- Answer clearly and cite which source(s) support your answer (e.g. "According to Source 1...", "As noted in Source 2 (Page 4)...")
- If the answer is NOT in the context, say explicitly: "This information is not found in the document."
- Be concise, direct, and factual.

Document: {filename}

Context from document:
{context}

Question: {question}

Answer:"""

    answer = await _generate_text(prompt, max_tokens=max_tokens, temperature=0.1)
    tokens_used = len(prompt.split()) + len(answer.split())
    latency_ms = int(time.time() * 1000) - start_ms

    logger.info(
        "single_doc_rag_complete",
        document_id=str(document_id),
        question_preview=question[:80],
        retrieved=len(candidates),
        reranked=is_reranked,
        latency_ms=latency_ms,
    )

    return QueryResponse(
        question=question,
        answer=answer,
        sources=[
            SourceChunk(
                content=c["content"][:320] + "..." if len(c["content"]) > 320 else c["content"],
                chunk_index=c["chunk_index"],
                page_number=c.get("page_number"),
                similarity_score=c.get("rerank_score", c["similarity_score"]),
            )
            for c in similar_chunks
        ],
        model_used=settings.LLM_MODEL,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        from_cache=False,
        query_id=query_id,
        reranked=is_reranked,
    )


# ─── Multi-Document Synthesis & Comparative Q&A ──────────────────────────────
async def synthesize_multi_document_query(
    document_ids: List[UUID],
    question: str,
    query_id: UUID,
    documents_meta: List[dict],
    db: AsyncSession,
    max_tokens: int = 1000,
    enable_rerank: bool = True,
) -> MultiQueryResponse:
    """
    Multi-Document Cross-Query & Synthesis Engine:
    1. Balanced retrieval: queries pgvector across all requested document IDs
    2. Reranks candidate evidence pool to select the best cross-document sources
    3. Synthesizes a comparative answer highlighting points of agreement,
       divergence, and cross-document relationships with precise provenance tags.
    """
    start_ms = int(time.time() * 1000)
    doc_name_map = {d["id"]: d["name"] for d in documents_meta}

    # Retrieve candidates across all documents
    # Requesting more candidates to ensure representation across multiple files
    candidates_per_doc = max(4, 16 // len(document_ids))
    all_candidates = []

    for doc_id in document_ids:
        doc_chunks = await retrieve_similar_chunks(
            db=db,
            document_id=doc_id,
            query=question,
            top_k=candidates_per_doc,
        )
        all_candidates.extend(doc_chunks)

    if not all_candidates:
        return MultiQueryResponse(
            question=question,
            answer="None of the selected documents contain information relevant to your question.",
            sources=[],
            documents_queried=documents_meta,
            model_used=settings.LLM_MODEL,
            tokens_used=0,
            latency_ms=int(time.time() * 1000) - start_ms,
            reranked=False,
            from_cache=False,
            query_id=query_id,
        )

    # Re-rank pooled candidates
    if enable_rerank and len(all_candidates) > settings.RAG_TOP_K:
        final_chunks = await rerank_chunks(
            query=question,
            chunks=all_candidates,
            top_k=settings.RAG_TOP_K + 2,
        )
        is_reranked = True
    else:
        final_chunks = all_candidates[: settings.RAG_TOP_K + 2]
        is_reranked = False

    # Build comparative context with full provenance
    context_blocks = []
    for i, chunk in enumerate(final_chunks, 1):
        doc_name = doc_name_map.get(chunk["document_id"], "Document")
        page_info = f", Page {chunk['page_number']}" if chunk.get("page_number") else ""
        context_blocks.append(
            f"[Source {i} | Document: \"{doc_name}\"{page_info}]\n{chunk['content']}"
        )

    context = "\n\n".join(context_blocks)
    doc_list_str = ", ".join(f'"{d["name"]}"' for d in documents_meta)

    prompt = f"""You are DocuMind's Cross-Document Intelligence Engine.
Synthesize and answer questions across multiple documents.

Documents Analyzed: {doc_list_str}

Instructions:
- Compare, contrast, and synthesize findings across the provided documents.
- Explicitly cite the document name and source number for each assertion (e.g. 'In "Contract A.pdf" [Source 1], ... whereas "Contract B.pdf" [Source 2] specifies...').
- If documents agree on a topic, explicitly highlight the consensus.
- If documents disagree or specify different terms, figures, or policies, contrast the differences clearly.
- If a document is silent or lacks information on the question, state that clearly.
- Strictly adhere to the provided context without drifting into general assumptions.

Context:
{context}

Question: {question}

Comparative Synthesis:"""

    answer = await _generate_text(prompt, max_tokens=max_tokens, temperature=0.1)
    tokens_used = len(prompt.split()) + len(answer.split())
    latency_ms = int(time.time() * 1000) - start_ms

    logger.info(
        "multi_doc_synthesis_complete",
        doc_count=len(document_ids),
        question_preview=question[:80],
        sources_used=len(final_chunks),
        latency_ms=latency_ms,
    )

    return MultiQueryResponse(
        question=question,
        answer=answer,
        sources=[
            MultiSourceChunk(
                content=c["content"][:320] + "..." if len(c["content"]) > 320 else c["content"],
                chunk_index=c["chunk_index"],
                document_id=c["document_id"],
                document_name=doc_name_map.get(c["document_id"], "Document"),
                page_number=c.get("page_number"),
                similarity_score=c["similarity_score"],
                rerank_score=c.get("rerank_score"),
            )
            for c in final_chunks
        ],
        documents_queried=documents_meta,
        model_used=settings.LLM_MODEL,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        reranked=is_reranked,
        from_cache=False,
        query_id=query_id,
    )


# ─── Keyword Extraction ───────────────────────────────────────────────────────
async def extract_keywords(text_sample: str, n: int = 10) -> List[str]:
    """Extract top N keywords/keyphrases from text."""
    prompt = f"""Extract the {n} most important keywords or keyphrases from this text.
Return ONLY a JSON array of strings:
["keyword1", "keyword2", ...]

Text:
{text_sample[:4000]}"""
    try:
        raw = await _generate_json(prompt, max_tokens=150)
        if isinstance(raw, list):
            return raw[:n]
        for v in raw.values():
            if isinstance(v, list):
                return v[:n]
    except Exception:
        pass
    return []

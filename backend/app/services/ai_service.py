"""
AI Service — LLM-powered document intelligence using Google Gemini.

All structured outputs use response_mime_type="application/json" for reliability.
Uses tenacity for retry logic on transient API errors.
Cost: $0 on Gemini 1.5 Flash free tier.
"""
import json
import time
from typing import List
from uuid import UUID

import google.generativeai as genai
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
    QueryResponse,
    SentimentResult,
    SourceChunk,
)
from app.services.rag_service import retrieve_similar_chunks

settings = get_settings()
logger = get_logger(__name__)

# Configure Gemini SDK
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Reusable model instances
_chat_model = genai.GenerativeModel(settings.GEMINI_CHAT_MODEL)
_json_model = genai.GenerativeModel(
    settings.GEMINI_CHAT_MODEL,
    generation_config=genai.GenerationConfig(
        response_mime_type="application/json",
    ),
)


# ─── Retry decorator ─────────────────────────────────────────────────────────
def _ai_retry():
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )


# ─── Helpers ──────────────────────────────────────────────────────────────────
async def _generate_text(prompt: str, max_tokens: int = 600, temperature: float = 0.3) -> str:
    """Generate text using Gemini (non-JSON mode)."""
    response = await _chat_model.generate_content_async(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )
    return response.text.strip()


async def _generate_json(prompt: str, max_tokens: int = 600, temperature: float = 0.1) -> dict:
    """Generate structured JSON using Gemini with response_mime_type enforcement."""
    response = await _json_model.generate_content_async(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text)


# ─── Summarization ────────────────────────────────────────────────────────────
@_ai_retry()
async def summarize_document(
    chunks: List[dict],
    filename: str,
    max_tokens: int = 600,
) -> str:
    """
    Summarize a document using Gemini's large context window.

    Gemini 1.5 Flash supports ~1M tokens, so we can process much larger
    chunks directly compared to OpenAI — simplifying the map-reduce pattern.
    For very large documents (>30 chunks) we still use a lightweight
    two-pass approach to stay within free-tier rate limits.
    """
    if len(chunks) <= 15:
        # Direct summarization — Gemini handles this easily
        full_text = "\n\n---\n\n".join(c["content"] for c in chunks)
        prompt = f"""You are analyzing a document titled "{filename}".
Write a clear, professional summary in 3-5 sentences covering the main topics, key arguments, and conclusions.

Document content:
{full_text[:12000]}"""

        return await _generate_text(prompt, max_tokens=max_tokens)

    else:
        # Two-pass for very large documents (cost control on free tier)
        group_summaries = []
        for i in range(0, min(len(chunks), 40), 10):
            group = chunks[i : i + 10]
            group_text = "\n\n".join(c["content"] for c in group)
            summary = await _generate_text(
                f"Summarize this section of a document in 2-3 sentences:\n\n{group_text[:6000]}",
                max_tokens=200,
            )
            group_summaries.append(summary)

        combined = "\n\n".join(group_summaries)
        prompt = f"""You are given section summaries of a document titled "{filename}".
Write a coherent final summary in 4-6 sentences that captures the main themes and conclusions.

Section summaries:
{combined}"""

        return await _generate_text(prompt, max_tokens=max_tokens)


# ─── Entity extraction ────────────────────────────────────────────────────────
@_ai_retry()
async def extract_entities(chunks: List[dict]) -> EntityExtractionResult:
    """
    Extract named entities from the document.
    Uses Gemini's JSON mode for guaranteed valid output.
    """
    # Sample strategically: beginning, middle, end
    n = len(chunks)
    if n <= 10:
        sample = chunks
    else:
        indices = list(range(0, 5)) + list(range(n // 2 - 2, n // 2 + 3)) + list(range(n - 3, n))
        sample = [chunks[i] for i in sorted(set(indices)) if i < n]

    text = "\n\n".join(c["content"] for c in sample)[:8000]

    prompt = f"""Extract named entities from this text. Return valid JSON with these exact keys:

{{
  "persons": ["list of full person names"],
  "organizations": ["list of organization/company names"],
  "locations": ["list of countries, cities, regions"],
  "dates": ["list of specific dates or time periods"],
  "technologies": ["list of software, tools, frameworks, APIs, models"],
  "monetary_values": ["list of prices, budgets, financial figures"],
  "other": ["list of other significant named entities"]
}}

Rules:
- Include only clearly named entities (not pronouns or generic nouns)
- De-duplicate entries
- Normalize names to their canonical form
- Maximum 15 items per category
- If a category has no entities, use an empty array

Text:
{text}"""

    raw = await _generate_json(prompt, max_tokens=600)
    return EntityExtractionResult(**{k: v for k, v in raw.items() if isinstance(v, list)})


# ─── Sentiment analysis ───────────────────────────────────────────────────────
@_ai_retry()
async def analyze_sentiment(chunks: List[dict], filename: str) -> SentimentResult:
    """
    Analyze the overall sentiment and tone of a document.
    Uses Gemini's JSON mode for reliable structured output.
    """
    sample_chunks = chunks[:3] + chunks[-2:] if len(chunks) > 5 else chunks
    text = "\n\n".join(c["content"] for c in sample_chunks)[:6000]

    prompt = f"""Analyze the sentiment and tone of this document titled "{filename}".
Return valid JSON with these exact keys:

{{
  "label": "Positive" or "Negative" or "Neutral" or "Mixed",
  "score": <float 0.0 to 1.0 where 1.0 is most positive>,
  "confidence": <float 0.0 to 1.0>,
  "tone": "formal" or "informal" or "technical" or "persuasive" or "critical" or "neutral" or "alarming" or "optimistic",
  "explanation": "<one sentence explaining the sentiment assessment>"
}}

Text:
{text}"""

    raw = await _generate_json(prompt, max_tokens=200)
    return SentimentResult(**raw)


# ─── RAG Question Answering ───────────────────────────────────────────────────
async def answer_question(
    document_id: UUID,
    question: str,
    query_id: UUID,
    filename: str,
    max_tokens: int = 800,
) -> QueryResponse:
    """
    Full RAG pipeline:
    1. Embed the question
    2. Retrieve relevant chunks from FAISS
    3. Build a grounded prompt with retrieved context
    4. Call Gemini with context + question
    5. Return structured answer with source citations
    """
    start_ms = int(time.time() * 1000)

    # Step 1 & 2: Retrieve relevant chunks
    similar_chunks = await retrieve_similar_chunks(
        document_id=document_id,
        query=question,
        top_k=settings.RAG_TOP_K,
    )

    if not similar_chunks:
        return QueryResponse(
            question=question,
            answer="I couldn't find relevant information in this document to answer your question. "
                   "Please try rephrasing or asking about a topic that's covered in the document.",
            sources=[],
            model_used=settings.GEMINI_CHAT_MODEL,
            tokens_used=0,
            latency_ms=int(time.time() * 1000) - start_ms,
            from_cache=False,
            query_id=query_id,
        )

    # Step 3: Build context string with citations
    context_blocks = []
    for i, chunk in enumerate(similar_chunks, 1):
        page_info = f" (Page {chunk['page_number']})" if chunk.get("page_number") else ""
        context_blocks.append(f"[Source {i}{page_info}]\n{chunk['content']}")

    context = "\n\n".join(context_blocks)

    # Step 4: Call Gemini
    prompt = f"""You are DocuMind, an expert document analyst.
Answer questions based ONLY on the provided document context. Do not use external knowledge.

Rules:
- If the answer is in the context, answer clearly and cite which source(s) support your answer
- If the answer is NOT in the context, say "This information is not found in the document"
- Be concise but complete
- Reference sources like: "According to Source 2..." or "As mentioned in Source 1..."

Document: {filename}

Context from document:
{context}

Question: {question}

Answer:"""

    response = await _chat_model.generate_content_async(
        prompt,
        generation_config=genai.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=0.2,
        ),
    )

    answer = response.text.strip()
    # Gemini doesn't provide exact token counts like OpenAI; estimate from text length
    tokens_used = len(prompt.split()) + len(answer.split())
    latency_ms = int(time.time() * 1000) - start_ms

    logger.info(
        "rag_query_complete",
        document_id=str(document_id),
        question_preview=question[:80],
        chunks_used=len(similar_chunks),
        tokens=tokens_used,
        latency_ms=latency_ms,
    )

    return QueryResponse(
        question=question,
        answer=answer,
        sources=[
            SourceChunk(
                content=c["content"][:300] + "..." if len(c["content"]) > 300 else c["content"],
                chunk_index=c["chunk_index"],
                page_number=c.get("page_number"),
                similarity_score=c["similarity_score"],
            )
            for c in similar_chunks
        ],
        model_used=settings.GEMINI_CHAT_MODEL,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
        from_cache=False,
        query_id=query_id,
    )


# ─── Keyword extraction ───────────────────────────────────────────────────────
async def extract_keywords(text_sample: str, n: int = 10) -> List[str]:
    """Extract top N keywords/keyphrases from a text sample."""
    prompt = f"""Extract the {n} most important keywords or keyphrases from this text.
Return ONLY a JSON array of strings:
["keyword1", "keyword2", ...]

Text: {text_sample[:4000]}"""

    try:
        raw = await _generate_json(prompt, max_tokens=150)
        if isinstance(raw, list):
            return raw[:n]
        # Sometimes model returns {"keywords": [...]}
        for v in raw.values():
            if isinstance(v, list):
                return v[:n]
    except Exception:
        pass
    return []

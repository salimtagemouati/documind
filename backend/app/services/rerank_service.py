"""
Re-ranking Service — Two-Stage Retrieval Optimization

Stage 1: High-recall hybrid search retrieves top N candidates (e.g. 15 chunks).
Stage 2: Cross-encoder / LLM relevance scoring ranks candidate passages by semantic alignment.

Reduces retrieval bleed and hallucination by presenting only high-density,
strictly pertinent chunks to the answer generation stage.
"""
import json
import os
import re
from typing import List

import litellm

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.llm_limiter import call_with_limits

settings = get_settings()
logger = get_logger(__name__)


def _term_overlap_score(query: str, content: str) -> float:
    """Heuristic fallback: token overlap with basic length and exact phrase penalty."""
    q_tokens = set(re.findall(r"\w+", query.lower()))
    c_tokens = set(re.findall(r"\w+", content.lower()))
    if not q_tokens:
        return 0.5
    overlap = len(q_tokens & c_tokens) / len(q_tokens)
    return round(overlap * 10.0, 2)


async def rerank_chunks(
    query: str,
    chunks: List[dict],
    top_k: int = 6,
) -> List[dict]:
    """
    Reranks a list of retrieved chunks using LLM relevance scoring or fast fallback.

    Each input chunk is a dict with:
      content: str
      chunk_index: int
      similarity_score: float
      document_id: UUID / str
      page_number: int | None
    """
    if not chunks:
        return []

    if not settings.ENABLE_RERANKING or len(chunks) == 1:
        for c in chunks:
            c.setdefault("rerank_score", c.get("similarity_score", 0.0))
        return chunks[:top_k]

    # Format passages for scoring
    passages_payload = []
    for idx, c in enumerate(chunks):
        snippet = c["content"].strip().replace("\n", " ")
        if len(snippet) > 400:
            snippet = snippet[:400] + "..."
        passages_payload.append(f"[{idx}] {snippet}")

    passages_text = "\n\n".join(passages_payload)

    prompt = f"""You are an expert retrieval relevance ranker.
Score each passage on how directly and completely it provides information to answer the question.

Question: "{query}"

Passages:
{passages_text}

Instructions:
Rate each passage from 0.0 to 10.0 (where 10.0 is exact direct answer, 0.0 is completely irrelevant).
Return ONLY a valid JSON array of objects with "id" (integer) and "score" (float):
[
  {{"id": 0, "score": 9.5}},
  {{"id": 1, "score": 2.0}}
]"""

    try:
        kwargs = {
            "model": settings.LLM_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
            "max_tokens": 400,
        }
        google_key = settings.GOOGLE_API_KEY or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        openai_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
        if google_key and "gemini" in settings.LLM_MODEL:
            kwargs["api_key"] = google_key
        elif openai_key and "gpt" in settings.LLM_MODEL:
            kwargs["api_key"] = openai_key

        response = await call_with_limits(lambda: litellm.acompletion(**kwargs))
        raw_text = response.choices[0].message.content or ""

        # Extract JSON array from output even if surrounded by commentary
        json_match = re.search(r"(\[.*\])", raw_text, re.DOTALL)
        cleaned_text = json_match.group(1) if json_match else raw_text.strip()
        cleaned_text = re.sub(r"^```(?:json)?\s*", "", cleaned_text)
        cleaned_text = re.sub(r"\s*```$", "", cleaned_text)

        scores_list = json.loads(cleaned_text)
        score_map = {item["id"]: float(item["score"]) for item in scores_list if "id" in item and "score" in item}

        ranked = []
        for idx, chunk in enumerate(chunks):
            # Combine LLM relevance score (normalized to 0-1) with initial similarity score
            llm_score = score_map.get(idx, _term_overlap_score(query, chunk["content"]))
            combined_score = round(0.75 * (llm_score / 10.0) + 0.25 * float(chunk.get("similarity_score", 0.5)), 4)
            ranked.append({
                **chunk,
                "rerank_score": combined_score,
            })

        ranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        logger.info("chunks_reranked_llm", candidate_count=len(chunks), final_count=top_k)
        return ranked[:top_k]

    except Exception as e:
        logger.warning("rerank_fallback_triggered", error=str(e))
        # Fallback to composite lexical + semantic scoring
        ranked = []
        for chunk in chunks:
            lex_score = _term_overlap_score(query, chunk["content"])
            vec_score = float(chunk.get("similarity_score", 0.5))
            composite = round(0.6 * vec_score + 0.4 * (lex_score / 10.0), 4)
            ranked.append({
                **chunk,
                "rerank_score": composite,
            })

        ranked.sort(key=lambda x: x["rerank_score"], reverse=True)
        return ranked[:top_k]

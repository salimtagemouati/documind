"""
Evaluation Metrics — Precision@K, Recall@K, MRR, Answer Groundedness, and Refusal Accuracy

Quantifies:
1. Retrieval Precision@K: % of retrieved chunks with relevant evidence
2. Retrieval Recall@K: % of ground truth required facts covered
3. MRR (Mean Reciprocal Rank): Rank position of the first relevant chunk
4. Answer Groundedness: Faithfulness of generated answer to retrieved context
5. Refusal Accuracy: Correct refusal on out-of-domain / unanswerable questions
"""
import re
from typing import Sequence


def precision_at_k(retrieved_contents: Sequence[str], required_keywords: Sequence[str]) -> float:
    """
    Computes Precision@K: Proportion of retrieved chunks that contain relevant ground truth facts.
    """
    if not retrieved_contents:
        return 0.0
    if not required_keywords:
        return 1.0

    relevant_count = 0
    req_lower = [k.lower() for k in required_keywords]

    for chunk in retrieved_contents:
        chunk_lower = chunk.lower()
        if any(k in chunk_lower for k in req_lower):
            relevant_count += 1

    return round(relevant_count / len(retrieved_contents), 4)


def recall_at_k(retrieved_contents: Sequence[str], required_keywords: Sequence[str]) -> float:
    """
    Computes Recall@K: Proportion of required ground truth facts present across all retrieved chunks.
    """
    if not required_keywords:
        return 1.0
    if not retrieved_contents:
        return 0.0

    combined_text = " ".join(retrieved_contents).lower()
    covered = sum(1 for k in required_keywords if k.lower() in combined_text)
    return round(covered / len(required_keywords), 4)


def mean_reciprocal_rank(retrieved_contents: Sequence[str], required_keywords: Sequence[str]) -> float:
    """
    Computes Reciprocal Rank (RR): 1 / position of the first chunk containing relevant information.
    """
    if not required_keywords:
        return 1.0
    if not retrieved_contents:
        return 0.0

    req_lower = [k.lower() for k in required_keywords]
    for rank, chunk in enumerate(retrieved_contents, start=1):
        chunk_lower = chunk.lower()
        if any(k in chunk_lower for k in req_lower):
            return round(1.0 / rank, 4)

    return 0.0


def check_refusal(answer: str) -> bool:
    """Detects whether the model properly refused to hallucinate on out-of-domain questions."""
    refusal_phrases = [
        "not found in the document",
        "not found",
        "not mentioned",
        "does not contain",
        "no information",
        "couldn't find",
        "cannot find",
        "is not provided",
    ]
    ans_lower = answer.lower()
    return any(p in ans_lower for p in refusal_phrases)


def evaluate_groundedness(question: str, context: str, answer: str, is_negative: bool = False) -> float:
    """
    Evaluates whether the answer stays faithful to the context without hallucination drift.
    Returns score between 0.0 and 1.0.
    """
    if is_negative:
        return 1.0 if check_refusal(answer) else 0.0

    if check_refusal(answer):
        # If model refused a positive question, groundedness is 0 (it missed the facts)
        return 0.2

    # Break answer into sentences/assertions
    sentences = [s.strip() for s in re.split(r"[.!?]\s+", answer) if len(s.strip()) > 10]
    if not sentences:
        return 0.5

    context_lower = context.lower()
    supported_sentences = 0

    for sent in sentences:
        words = [w.lower() for w in re.findall(r"\w+", sent) if len(w) > 3]
        if not words:
            supported_sentences += 1
            continue
        # Check overlap density
        matches = sum(1 for w in words if w in context_lower)
        if matches / len(words) >= 0.55:
            supported_sentences += 1

    return round(supported_sentences / len(sentences), 4)

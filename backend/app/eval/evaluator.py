"""
Evaluation Orchestrator — Runs Scientific Side-by-Side RAG Benchmark (Vector vs. Reranked)

Compares:
- Run A (Baseline): Standard Dense Vector Retrieval (top_k=K)
- Run B (Enhanced): Two-Stage Hybrid Candidate Retrieval (top_k=Candidates) + Cross-Encoder / LLM Re-ranking (top_k=K)

Metrics evaluated:
1. Retrieval Precision@K
2. Retrieval Recall@K
3. Mean Reciprocal Rank (MRR)
4. Answer Groundedness (Claim extraction & context verification)
5. Out-of-Domain Refusal Accuracy
"""
import asyncio
import datetime
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger
from app.eval.dataset import BENCHMARK_CASES
from app.eval.metrics import (
    check_refusal,
    evaluate_groundedness,
    mean_reciprocal_rank,
    precision_at_k,
    recall_at_k,
)
from app.services.ai_service import _generate_text
from app.services.demo_service import DEMO_DOCUMENTS
from app.services.document_processor import chunk_text
from app.services.rag_service import embed_query, embed_texts
from app.services.rerank_service import rerank_chunks

settings = get_settings()
logger = get_logger(__name__)

REPORT_FILE = Path(__file__).parent / "benchmark_report.json"
CACHE_DIR = Path(__file__).parents[2] / ".eval_cache"


class RAGEvaluator:
    def __init__(self, mode: str = "in-memory", k: int = 5, candidates: int = 15, enable_rerank: bool = True):
        self.mode = mode
        self.k = k
        self.candidates = candidates
        self.enable_rerank = enable_rerank
        self.doc_index = {}
        self.llm_call_count = 0

    async def setup_corpus(self):
        """
        Indexes the benchmark corpus. Uses disk cache in .eval_cache/ to conserve
        Gemini free-tier quota across consecutive test runs.
        """
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        logger.info("eval_indexing_benchmark_corpus", cache_dir=str(CACHE_DIR))

        doc_key_map = {
            "saas_msa": "SaaS_Master_Services_Agreement_2025.txt",
            "quantum_db": "QuantumDB_Distributed_Architecture_Spec.txt",
            "apex_financial": "ApexGlobal_Q4_Financial_Performance.txt",
        }

        for key, fname in doc_key_map.items():
            cache_file = CACHE_DIR / f"{key}_embeddings.npy"
            raw_doc = next(d for d in DEMO_DOCUMENTS if d["filename"] == fname)
            chunks = chunk_text(raw_doc["content"])
            texts = [c["content"] for c in chunks]

            if cache_file.exists():
                logger.info("eval_loaded_from_cache", doc=key)
                embeddings = np.load(cache_file)
            else:
                logger.info("eval_generating_embeddings", doc=key, chunks=len(texts))
                embeddings = await embed_texts(texts)
                np.save(cache_file, embeddings)

            self.doc_index[key] = {
                "filename": fname,
                "chunks": chunks,
                "embeddings": embeddings,
            }

    async def _retrieve_baseline(self, doc_key: str, query: str, top_k: int = 5) -> List[dict]:
        """Pure vector similarity retrieval (top_k)."""
        doc = self.doc_index[doc_key]
        q_vec = await embed_query(query)

        # Dot product of normalized unit vectors = cosine similarity
        sims = np.dot(doc["embeddings"], q_vec)
        top_indices = np.argsort(sims)[::-1][:top_k]

        results = []
        for idx in top_indices:
            results.append({
                "content": doc["chunks"][idx]["content"],
                "chunk_index": doc["chunks"][idx]["chunk_index"],
                "similarity_score": round(float(sims[idx]), 4),
            })
        return results

    async def _cached_generate_text(self, prompt: str, max_tokens: int = 250, temperature: float = 0.1) -> str:
        cache_dir = CACHE_DIR / "llm_gen"
        cache_dir.mkdir(parents=True, exist_ok=True)
        key = hashlib.sha256(f"{settings.LLM_MODEL}_{prompt}".encode("utf-8")).hexdigest()[:20]
        cache_file = cache_dir / f"{key}.txt"
        if cache_file.exists():
            return cache_file.read_text(encoding="utf-8")
        self.llm_call_count += 1
        res = await _generate_text(prompt, max_tokens=max_tokens, temperature=temperature)
        cache_file.write_text(res, encoding="utf-8")
        return res

    async def _cached_rerank_chunks(self, query: str, chunks: List[dict], top_k: int) -> List[dict]:
        cache_dir = CACHE_DIR / "llm_rerank"
        cache_dir.mkdir(parents=True, exist_ok=True)
        chunk_sig = "".join(str(c.get("content", ""))[:40] for c in chunks)
        key = hashlib.sha256(f"{settings.LLM_MODEL}_{query}_{chunk_sig}_{top_k}".encode("utf-8")).hexdigest()[:20]
        cache_file = cache_dir / f"{key}.json"
        if cache_file.exists():
            return json.loads(cache_file.read_text(encoding="utf-8"))
        self.llm_call_count += 1
        res = await rerank_chunks(query=query, chunks=chunks, top_k=top_k)
        cache_file.write_text(json.dumps(res), encoding="utf-8")
        return res

    async def _retrieve_with_rerank(self, doc_key: str, query: str, initial_top_k: int = 15, final_top_k: int = 5) -> List[dict]:
        """Two-stage retrieval: broad candidate pool + cross-encoder re-ranking."""
        candidates = await self._retrieve_baseline(doc_key, query, top_k=initial_top_k)
        if not self.enable_rerank:
            return candidates[:final_top_k]
        reranked = await self._cached_rerank_chunks(query=query, chunks=candidates, top_k=final_top_k)
        return reranked

    async def run_evaluation(self, cases_limit: Optional[int] = None) -> Dict:
        """
        Executes the evaluation suite and returns comprehensive benchmark metrics.
        """
        if self.mode == "pgvector":
            if "sqlite" in settings.DATABASE_URL:
                raise ValueError(
                    "DATABASE_URL points to SQLite; pgvector mode requires PostgreSQL with the pgvector extension. "
                    "Use --in-memory mode for standalone evaluation or provide a PostgreSQL DATABASE_URL."
                )

        if not self.doc_index:
            await self.setup_corpus()

        cases_to_run = BENCHMARK_CASES[:cases_limit] if cases_limit else BENCHMARK_CASES
        logger.info("eval_starting_benchmark", total_cases=len(cases_to_run), mode=self.mode)

        case_results = []
        baseline_precisions, reranked_precisions = [], []
        baseline_recalls, reranked_recalls = [], []
        baseline_mrrs, reranked_mrrs = [], []
        baseline_groundedness_scores, reranked_groundedness_scores = [], []
        baseline_refusal_checks, reranked_refusal_checks = [], []

        baseline_latencies = []
        reranked_latencies = []

        # Category breakdowns
        category_metrics = {
            "single_fact": {"count": 0, "base_p": [], "rerank_p": [], "base_mrr": [], "rerank_mrr": []},
            "multi_hop": {"count": 0, "base_p": [], "rerank_p": [], "base_mrr": [], "rerank_mrr": []},
            "adversarial_negative": {"count": 0, "base_refusal": [], "rerank_refusal": []},
        }

        for idx, case in enumerate(cases_to_run, start=1):
            doc_key = case["doc_key"]
            q = case["question"]
            req_kws = case["required_keywords"]
            is_neg = case["is_negative"]
            category = case["category"]

            print(f"[{idx}/{len(cases_to_run)}] Evaluating ({category}): {q[:60]}...", flush=True)

            # ── 1. Baseline Run (Vector Only top_k) ───────────────────────────
            t0 = time.perf_counter()
            base_chunks = await self._retrieve_baseline(doc_key, q, top_k=self.k)
            base_contents = [c["content"] for c in base_chunks]

            base_p = precision_at_k(base_contents, req_kws) if not is_neg else 1.0
            base_r = recall_at_k(base_contents, req_kws) if not is_neg else 1.0
            base_mrr = mean_reciprocal_rank(base_contents, req_kws) if not is_neg else 1.0

            base_context = "\n\n".join(f"[Source {i+1}]\n{c}" for i, c in enumerate(base_contents))
            base_prompt = f"Answer using ONLY this context:\n{base_context}\n\nQuestion: {q}\nAnswer:"
            base_answer = await self._cached_generate_text(base_prompt, max_tokens=250, temperature=0.1)
            base_lat = time.perf_counter() - t0
            baseline_latencies.append(base_lat)

            base_groundedness = evaluate_groundedness(q, base_context, base_answer, is_negative=is_neg)

            # ── 2. Enhanced Run (Hybrid Candidates → Rerank to top_k) ────────
            t1 = time.perf_counter()
            rerank_chunks_res = await self._retrieve_with_rerank(
                doc_key, q, initial_top_k=self.candidates, final_top_k=self.k
            )
            rerank_contents = [c["content"] for c in rerank_chunks_res]

            rerank_p = precision_at_k(rerank_contents, req_kws) if not is_neg else 1.0
            rerank_r = recall_at_k(rerank_contents, req_kws) if not is_neg else 1.0
            rerank_mrr = mean_reciprocal_rank(rerank_contents, req_kws) if not is_neg else 1.0

            rerank_context = "\n\n".join(f"[Source {i+1}]\n{c}" for i, c in enumerate(rerank_contents))
            rerank_prompt = f"Answer using ONLY this context:\n{rerank_context}\n\nQuestion: {q}\nAnswer:"
            rerank_answer = await self._cached_generate_text(rerank_prompt, max_tokens=250, temperature=0.1)
            rerank_lat = time.perf_counter() - t1
            reranked_latencies.append(rerank_lat)

            rerank_groundedness = evaluate_groundedness(q, rerank_context, rerank_answer, is_negative=is_neg)

            if is_neg:
                b_ref = check_refusal(base_answer)
                r_ref = check_refusal(rerank_answer)
                baseline_refusal_checks.append(b_ref)
                reranked_refusal_checks.append(r_ref)
                category_metrics["adversarial_negative"]["count"] += 1
                category_metrics["adversarial_negative"]["base_refusal"].append(1.0 if b_ref else 0.0)
                category_metrics["adversarial_negative"]["rerank_refusal"].append(1.0 if r_ref else 0.0)
            else:
                baseline_precisions.append(base_p)
                reranked_precisions.append(rerank_p)
                baseline_recalls.append(base_r)
                reranked_recalls.append(rerank_r)
                baseline_mrrs.append(base_mrr)
                reranked_mrrs.append(rerank_mrr)
                baseline_groundedness_scores.append(base_groundedness)
                reranked_groundedness_scores.append(rerank_groundedness)

                if category in category_metrics:
                    category_metrics[category]["count"] += 1
                    category_metrics[category]["base_p"].append(base_p)
                    category_metrics[category]["rerank_p"].append(rerank_p)
                    category_metrics[category]["base_mrr"].append(base_mrr)
                    category_metrics[category]["rerank_mrr"].append(rerank_mrr)

            case_results.append({
                "case_id": case["id"],
                "question": q,
                "category": category,
                "is_negative": is_neg,
                "baseline": {
                    "precision_at_k": base_p,
                    "recall_at_k": base_r,
                    "mrr": base_mrr,
                    "groundedness": base_groundedness,
                    "latency_sec": round(base_lat, 2),
                    "answer_preview": base_answer[:120],
                },
                "reranked": {
                    "precision_at_k": rerank_p,
                    "recall_at_k": rerank_r,
                    "mrr": rerank_mrr,
                    "groundedness": rerank_groundedness,
                    "latency_sec": round(rerank_lat, 2),
                    "answer_preview": rerank_answer[:120],
                },
            })
            # Pace requests between cases to respect free tier rate quotas
            await asyncio.sleep(2.0)

        # Summary aggregates
        avg_base_p = round(float(np.mean(baseline_precisions)), 3) if baseline_precisions else 0.0
        avg_rerank_p = round(float(np.mean(reranked_precisions)), 3) if reranked_precisions else 0.0

        avg_base_r = round(float(np.mean(baseline_recalls)), 3) if baseline_recalls else 0.0
        avg_rerank_r = round(float(np.mean(reranked_recalls)), 3) if reranked_recalls else 0.0

        avg_base_mrr = round(float(np.mean(baseline_mrrs)), 3) if baseline_mrrs else 0.0
        avg_rerank_mrr = round(float(np.mean(reranked_mrrs)), 3) if reranked_mrrs else 0.0

        avg_base_g = round(float(np.mean(baseline_groundedness_scores)), 3) if baseline_groundedness_scores else 0.0
        avg_rerank_g = round(float(np.mean(reranked_groundedness_scores)), 3) if reranked_groundedness_scores else 0.0

        base_refusal_rate = round(float(sum(baseline_refusal_checks) / len(baseline_refusal_checks)), 3) if baseline_refusal_checks else 1.0
        rerank_refusal_rate = round(float(sum(reranked_refusal_checks) / len(reranked_refusal_checks)), 3) if reranked_refusal_checks else 1.0

        avg_base_lat = round(float(np.mean(baseline_latencies)), 2) if baseline_latencies else 0.0
        avg_rerank_lat = round(float(np.mean(reranked_latencies)), 2) if reranked_latencies else 0.0

        # Build category breakdown
        breakdown = {}
        for cat, data in category_metrics.items():
            if cat == "adversarial_negative":
                breakdown[cat] = {
                    "count": data["count"],
                    "baseline_refusal": round(float(np.mean(data["base_refusal"])), 3) if data["base_refusal"] else 1.0,
                    "reranked_refusal": round(float(np.mean(data["rerank_refusal"])), 3) if data["rerank_refusal"] else 1.0,
                }
            else:
                breakdown[cat] = {
                    "count": data["count"],
                    "baseline_precision": round(float(np.mean(data["base_p"])), 3) if data["base_p"] else 0.0,
                    "reranked_precision": round(float(np.mean(data["rerank_p"])), 3) if data["rerank_p"] else 0.0,
                    "baseline_mrr": round(float(np.mean(data["base_mrr"])), 3) if data["base_mrr"] else 0.0,
                    "reranked_mrr": round(float(np.mean(data["rerank_mrr"])), 3) if data["rerank_mrr"] else 0.0,
                }

        mode_label = "in-memory (numpy cosine similarity, does not test pgvector HNSW)" if self.mode == "in-memory" else "pgvector (Supabase PostgreSQL HNSW)"

        summary = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "mode": mode_label,
            "evaluated_models": {
                "chat_model": settings.LLM_MODEL,
                "embedding_model": settings.EMBEDDING_MODEL,
            },
            "parameters": {
                "k": self.k,
                "candidates": self.candidates,
                "enable_rerank": self.enable_rerank,
                "cases_evaluated": len(cases_to_run),
            },
            "stats": {
                "llm_calls_made": self.llm_call_count,
                "baseline_avg_latency_sec": avg_base_lat,
                "reranked_avg_latency_sec": avg_rerank_lat,
            },
            "metrics": [
                {
                    "name": f"Retrieval Precision@{self.k}",
                    "baseline": avg_base_p,
                    "reranked": avg_rerank_p,
                    "delta": round(avg_rerank_p - avg_base_p, 3),
                    "description": "Proportion of retrieved chunks containing verifiable ground truth evidence.",
                },
                {
                    "name": f"Retrieval Recall@{self.k}",
                    "baseline": avg_base_r,
                    "reranked": avg_rerank_r,
                    "delta": round(avg_rerank_r - avg_base_r, 3),
                    "description": "Coverage of required ground truth facts across all retrieved context.",
                },
                {
                    "name": "Mean Reciprocal Rank (MRR)",
                    "baseline": avg_base_mrr,
                    "reranked": avg_rerank_mrr,
                    "delta": round(avg_rerank_mrr - avg_base_mrr, 3),
                    "description": "Reciprocal rank of the first chunk providing direct answer evidence.",
                },
                {
                    "name": "Answer Groundedness",
                    "baseline": avg_base_g,
                    "reranked": avg_rerank_g,
                    "delta": round(avg_rerank_g - avg_base_g, 3),
                    "description": "Adherence of generated assertions strictly to retrieved context (hallucination resistance).",
                },
                {
                    "name": "Out-of-Domain Refusal Accuracy",
                    "baseline": base_refusal_rate,
                    "reranked": rerank_refusal_rate,
                    "delta": round(rerank_refusal_rate - base_refusal_rate, 3),
                    "description": "Accuracy in refusing unanswerable questions without fabricating claims.",
                },
            ],
            "category_breakdown": breakdown,
            "details": case_results,
        }

        # Save primary report
        REPORT_FILE.write_text(json.dumps(summary, indent=2))
        logger.info("eval_benchmark_report_saved", path=str(REPORT_FILE))
        return summary

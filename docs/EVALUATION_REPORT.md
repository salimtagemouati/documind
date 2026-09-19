# DocuMind RAG evaluation report

## Current status

The checked-in JSON artifact was generated on `2026-09-19T13:43:38.014556+00:00` from 15 curated cases in **in-memory mode**. It is retained as historical evidence, but its aggregate scores are **not validated under the current methodology**.

The audit found that the legacy Precision@K implementation divided relevant results by the number of returned chunks rather than by K. Because the demo corpus often produces fewer than five chunks, this inflated the stored Precision@5 value. The formula is now corrected, but the artifact cannot be regenerated in this checkout without valid provider credentials and quota.

Do not cite the historical percentages as current benchmark results. Rerun the harness first:

```bash
cd backend
python -m app.eval.runner --cases 3
python -m app.eval.runner
```

## Historical artifact (legacy-v1, invalidated)

These values are transcribed from `docs/benchmark_report.json` so the repository history remains auditable; they are not endorsements of correctness.

| Metric | Dense baseline | Dense candidates + LLM rerank |
|---|---:|---:|
| Precision@5 | 100.0% | 100.0% |
| Recall@5 | 94.4% | 94.4% |
| MRR | 100.0% | 100.0% |
| Lexical groundedness proxy | 95.8% | 95.8% |
| Out-of-domain refusal accuracy | 33.3% | 33.3% |

The 33.3% refusal result means two of three adversarial questions were not recognized as refusals by the evaluator. The system must not be described as reliably refusing unsupported questions on the basis of this run.

## What the harness actually measures

- Baseline: normalized embeddings and NumPy cosine similarity in memory.
- Enhanced run: a larger dense candidate pool followed by one batched LLM reranking call.
- Precision@K: relevant returned chunks divided by K.
- Recall@K: fraction of required keywords found across retrieved chunks.
- MRR: reciprocal rank of the first chunk containing any required keyword.
- Groundedness: lexical token overlap between generated answer and retrieved context.
- Refusal accuracy: phrase-based detection on adversarial negative cases.

The gold answer is not passed into generation or reranking prompts. Required keywords are used only after generation for metric computation.

## Limitations

- Only 15 hand-authored cases and three small seeded documents are included.
- The corpus currently yields very few chunks per document, limiting the discriminative value of Precision@5 and MRR.
- The run does not exercise PostgreSQL, pgvector, HNSW, full-text search, RRF, database ownership filters, or multi-document balancing.
- Groundedness is a lexical heuristic, not an LLM judge and not human adjudication.
- MRR and recall rely on keyword matches, which can reward incidental mentions and miss paraphrases.
- LLM outputs and provider behavior can vary; caches must be invalidated when prompts, models, dimensions, or methodology change.
- The stored latencies include provider and cache effects and are not a controlled performance benchmark.

## Reproducibility requirements

A publishable rerun should record the Git commit, methodology version, provider model identifiers, embedding dimension, cache state, K, candidate count, case count, UTC timestamp, and whether each call was cached. A database-backed evaluation should be added separately before making claims about pgvector or hybrid retrieval quality.

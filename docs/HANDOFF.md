# DocuMind flagship RAG — reviewed handoff

Date: 19 September 2026
Branch: `feat/flagship-rag`

This document supersedes the original agent handoff. The previous “100% validated” status was not supported by the repository: the evaluation artifact used a flawed Precision@K denominator, the analytics schema did not accept the stored JSON, demo sessions could bypass cost controls and reach billing writes, and retrieval ownership was enforced only at the route layer.

## Verified after independent review

- Dense and full-text retrieval both join `documents` and filter by authenticated `user_id`.
- Client-provided document IDs are ownership-checked; duplicate IDs are rejected.
- Cosine similarity is `1 - cosine_distance`; embeddings are unit-normalized; configured/model/migration dimension is 768.
- RRF uses `k=60`, accepts dense-only or lexical-only candidates, and deduplicates by chunk ID.
- Reranking uses one batch call, respects `ENABLE_RERANKING`, parses JSON defensively, and preserves original order on failure.
- Multi-document results reserve evidence from each available document before filling remaining slots by rank.
- Retrieved text is explicitly delimited as untrusted data in generation and rerank prompts.
- Demo access and refresh tokens expire after two hours and preserve the `is_demo` claim.
- Demo upload, delete, checkout, and billing portal writes are rejected; queries are per-IP limited and do not persist history or usage.
- Provider failures map to clean HTTP 429/503/504 responses. Exception messages are not written to application logs.
- Frontend TypeScript build passes without explicit `any` or debug `console.log` calls in `src`.
- CI lints application and tests, enforces 60% aggregate coverage, builds the frontend, and no longer masks Docker verification failures.

## Evaluation status

The checked-in 15-case JSON files are identical historical artifacts. They report 100% Precision@5, 94.4% Recall@5, 100% MRR, 95.8% lexical groundedness, and 33.3% refusal accuracy. These numbers must not be presented as current results because the legacy Precision@K implementation was wrong and the run could not be reproduced without provider credentials.

The harness is in-memory only. It does not validate pgvector, HNSW, PostgreSQL FTS, RRF, tenant filtering, or multi-document retrieval. Groundedness is lexical overlap, not an LLM judge. See `docs/EVALUATION_REPORT.md`.

## Remaining risks and manual checks

- Rotate any provider credential that may have existed in Git history, then decide whether to rewrite history. The current tracked tree contains no `.env` file.
- Run the corrected three-case smoke benchmark, then all 15 cases, with a valid provider credential and quota. Review the generated diff before committing it.
- Run database integration tests against an isolated PostgreSQL + pgvector instance. SQLite tests compile vector distance to a constant and cannot validate real similarity ordering, FTS, HNSW, or RLS.
- Confirm the HNSW index and 768-dimensional vector column in the target Supabase project.
- Exercise the public demo through the deployed UI and confirm that the provider-side project quota/budget is capped.
- Configure and validate Stripe only if billing is intended for this deployment.
- Decide whether to add database Row Level Security. The application currently uses server-side owner filters; the repository does not define RLS policies tied to the custom JWT model.

## Verification commands

```bash
cd backend
.venv/bin/ruff check app tests --select E,F,I --ignore E501
.venv/bin/pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under=60

cd ../frontend
npm run build
```

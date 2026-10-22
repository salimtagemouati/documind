# Project showcase — evidence-based interview brief

## Thirty-second pitch

DocuMind lets users upload documents and ask questions with inspectable source passages. I built a full-stack pipeline around FastAPI, React, Gemini and PostgreSQL/pgvector, with hybrid retrieval and explicit account isolation. The engineering emphasis is traceability: retaining PDF page provenance, testing real provider-backed requests, and measuring retrieval behavior instead of treating a plausible answer as proof of correctness.

## Two-minute walkthrough

Start with a synthetic two-page contract. Upload it, explain the pending/processing/ready states, and open its summary. Ingestion extracts text, preserves page boundaries, chunks within a fixed budget, requests Gemini embeddings and stores them in pgvector. Ask how long the warranty lasts. The API checks ownership, retrieves evidence using cosine search and full-text search combined with reciprocal-rank fusion, and asks Gemini to answer from that evidence. Expand the returned passages and point to page 2. Ask a follow-up and then an unsupported question to demonstrate the conversational boundary and refusal behavior.

Show the architecture diagram and explain why SQLite development is a lexical fallback rather than a semantic-search benchmark. Run the test suite and the disposable PostgreSQL check. Show the six-case provenance comparison: retrieval hits were unchanged while source-page correctness improved. Close with the deployment limitations: in-process jobs, no complete factuality guarantee, no verified production rollout and no measured scale claim.

## Five defensible achievements

1. Verified an actual upload-to-answer path through Gemini embeddings, pgvector and Gemini generation, including correct page-2 evidence and document deletion. See `live_gemini_primary_run.json` for the successful primary run; later expanded attempts are recorded separately.
2. Preserved PDF page provenance through chunking, improving supporting-page accuracy from 0/6 to 6/6 in a reproducible SQLite fixture evaluation, without claiming a retrieval-hit improvement.
3. Added regression coverage for exact source spans, token limits, blank PDF pages, DOCX tables, failed analysis, invalid embeddings, cache expiry and bounded follow-ups.
4. Verified cosine search, full-text search, RRF and cross-account exclusion against disposable PostgreSQL rather than a SQLite simulation of vector operations.
5. Hardened the user workflow with complete evidence passages, document-specific chat state, query input recovery, accessible document selection and a mobile drawer that closes after selection.

## Three difficult challenges

**Page provenance:** Flattening a PDF lost the page containing each fact. Retaining page separators through extraction and chunking allows the same page ID to survive indexing, retrieval and rendering. Blank pages must count even when they contain no text.

**False success after provider failure:** Keyword extraction returned an empty list on failure, preventing an all-exceptions check from detecting that every primary analysis had failed. Readiness now depends on the primary analysis outcomes. A regression test reproduces the misleading-success path.

**Testing production retrieval locally:** SQLite cannot prove pgvector/FTS behavior. A disposable Docker script initializes PostgreSQL and the real vector migration, then verifies ranks, fusion and ownership with deterministic vectors. The live smoke script extends this to actual Gemini embeddings and answers.

## Decisions and trade-offs

- Use SQLAlchemy and focused services rather than another RAG orchestration framework.
- Keep semantic and lexical signals separate until rank fusion; avoid treating incompatible raw scores as interchangeable.
- Disable optional reranking by default until a representative quality/cost comparison supports it.
- Bound conversation context and bypass stateless caching for follow-ups.
- Preserve full retrieved evidence; do not equate visible citations with verified factuality.
- Keep in-process ingestion for the current demo scale; recognize durable jobs as a release prerequisite for reliable multi-worker production.

## GitHub / portfolio description

“Document intelligence workspace with FastAPI, React, Gemini and PostgreSQL/pgvector. Includes hybrid retrieval, page-aware evidence, bounded follow-up Q&A, isolated account access and reproducible local/live verification.”

## CV-ready bullets

- Implemented and verified Gemini-backed document ingestion and cited question answering using FastAPI, React and PostgreSQL/pgvector.
- Built a reproducible source-provenance evaluation; improved supporting-page accuracy from 0/6 to 6/6 synthetic cases while retaining 6/6 retrieval hits.
- Added regression and disposable-database checks for document parsing, tenant-filtered hybrid retrieval, cache expiration and provider-failure handling.

Avoid “production-proven,” “hallucination-free,” “secure at scale,” or percentage-quality gains beyond the explicitly measured fixtures.

The latest continuation has 118 passing backend tests and seven frontend tests. The complete extended Gemini Flash Lite run passed PDF, Markdown, adversarial TXT, DOCX tables and multi-document answers; raw evidence is in `live_gemini_results.json`. A temporary public preview serves the real application from the Mac, with separate persistent pgvector storage. It requires the Mac to stay awake and is not permanent hosting.

## Interview questions

**Why hybrid search?** Dense similarity can find paraphrases; lexical search can preserve exact terms. RRF combines ranks without assuming comparable score scales. Its advantage on a specific corpus still needs measurement.

**How do you prevent cross-account retrieval?** Verify document ownership at the route and apply a user predicate in retrieval. Test an outsider against the same document ID in PostgreSQL. Hosted RLS is a separate defense to verify.

**How are citations trustworthy?** Source passages and PDF pages are traceable to extraction. The model receives numbered passages. That proves provenance, not that every assertion is entailed; factuality and citation correctness need labeled evaluation.

**What happens if the provider is down?** Calls have deadlines and bounded transient retries. The API maps known provider failures to actionable statuses. All primary analysis failures mark ingestion failed instead of ready.

**How would you scale ingestion?** Move the orchestrator into a durable worker, persist job state and retry ownership, isolate parsers, reconcile storage/database changes and enforce quotas atomically.

**What did the benchmark prove?** On six synthetic fixtures, page attribution improved and retrieval hits did not regress. It did not establish general semantic accuracy, throughput or reranker value.

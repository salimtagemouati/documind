# DocuMind engineering audit — 20 October 2026

## Executive assessment

The complete extended Gemini Flash Lite → pgvector → cited answer workflow now passes PDF, Markdown, adversarial TXT, DOCX tables and multi-document synthesis. A temporary public preview runs the actual application on the Mac. Earlier quota and timeout failures remain recorded below. This is a working engineering demonstration, not a certification of production readiness; hosted Supabase Storage/RLS, permanent cloud deployment, billing and durable ingestion remain unverified or incomplete.

Work was performed in the actual DocuMind checkout, not the portfolio repository in which the request arrived. Existing uncommitted changes were preserved. No hosted production data, credential rotation, paid infrastructure or Git publishing was changed. A temporary public preview was subsequently launched from the DocuMind checkout. A supplied Gemini credential was saved only to ignored `backend/.env` with mode 0600.

## Initial state

The repository already contained React 18, TypeScript, Vite, React Query, Zustand, FastAPI, SQLAlchemy, pypdf, python-docx, LiteLLM, PostgreSQL/pgvector, optional Redis, Supabase Storage and Stripe integration. Existing audit work had repaired demo-account privilege bypass, account checks, SQLite storage, pagination and frontend cache isolation. Those repairs were present on arrival and are not attributed to this pass.

The baseline backend suite passed **85 tests**. The app had real service boundaries and retrieval implementations, but several claims were stronger than the available evidence. The historical evaluation artifact was already documented as invalid under its corrected methodology.

### Prioritized findings

| Priority | Finding | Outcome |
| --- | --- | --- |
| P1 | PDF page identities disappeared before indexing | Preserve physical page boundaries, including blank pages |
| P1 | Chunker could silently truncate or exceed intended bounds; offsets often zero | Bounded exact extracted-text slices; explicit chunk-limit failure |
| P1 | DOCX tables were omitted | Extract paragraphs and tables in document order |
| P1 | Empty keyword fallback could mark total primary-analysis failure ready | Readiness now checks primary analysis outcomes; regression covered |
| P1 | WebSocket accepted refresh tokens and did not check active account | Require access token and active account |
| P1 | Deleted documents left saved query excerpts/history | Remove source-bearing single/multi-document history on deletion |
| P1 | Missing environment templates broke fresh-clone setup | Restore templates; read template before creating destination |
| P2 | Chat retained state across document selection and ignored prior turns | Key viewers by selection; send at most three bounded turns |
| P2 | Follow-ups could reuse unrelated stateless cache answers | Bypass cache for contextual requests; include output budget in key |
| P2 | In-memory cache lacked expiry/bounds and aliased responses | TTL, deep copies and 256-entry cap |
| P2 | Provider retries could exceed frontend timeout by minutes | Three transient attempts, per-attempt timeout, 90-second query deadline |
| P2 | Sources were truncated to 320 characters and UI hid sources after three | Return/show all complete retrieved passages with page labels |
| P2 | Invalid vectors could reach persistence | Validate shape, finiteness and nonzero norm |
| P2 | Failed optional FTS could poison PostgreSQL transaction | Execute FTS in a savepoint |
| P2 | Mobile drawer obscured document and header overflowed | Close drawer on selection; wrap header; scroll stats/tabs |
| P2 | New long passwords silently collided after bcrypt truncation | Reject registration passwords over 72 UTF-8 bytes |
| P2 | Authentication endpoints lacked explicit tight limits | Add login and registration per-IP limits |
| P2 | Reranker enabled without representative measured benefit | Default off; retain explicit opt-in and tests |

## Changes implemented

### Ingestion and persistence

`document_processor.py` retains PDF separators, handles DOCX tables, rejects empty extracted text and oversized expanded content, and uses exact token-counted slices. Parser work runs in a worker thread. The pipeline carries page numbers into stored chunks. It reports index progress without claiming that SQLite generated vectors.

`documents.py` exposes safe failure metadata and original filenames through the schema. Storage selection can be configured independently of the database, enabling real local pgvector verification without Supabase access. Deletion fails visibly if the original cannot be removed, and saved source-bearing history is deleted with its document.

### AI and retrieval

`ai_service.py` adds a system-level untrusted-document boundary, bounded single-document conversation context, complete evidence responses and token estimates using the configured tokenizer instead of word counts. It stops retrying authentication failures as JSON-format incompatibilities. Multi-document reranking retains the full candidate pool before balancing, so selected documents are not lost prematurely.

`rag_service.py` validates vectors and isolates optional FTS errors. Query logs record lengths rather than raw question previews. `llm_limiter.py` bounds transient retries and honors provider retry delays up to a finite cap. Query routes map timeouts to HTTP 504.

### Product workflow

The UI preserves failed questions for retry, restricts question length, exposes all evidence, labels token counts as estimates, resets chat on document changes, and supports keyboard document selection. A narrow-screen browser check confirmed that the selected document becomes visible after the sidebar closes. The existing visual design was preserved. Five frontend component tests now cover all-source rendering, question recovery, input length constraints, failed-document retry and file acceptance/rejection. Original-file previews and full accessibility certification are not claimed.

### Reproducibility

New scripts:

- `scripts/evaluate_local.py`: six-case before/after source-provenance evaluation through actual SQLite persistence/retrieval.
- `scripts/check_pgvector.py`: disposable Docker PostgreSQL, actual vector migration, cosine search, FTS, RRF and ownership checks.
- `scripts/live_gemini_smoke.py`: real Gemini-backed upload/query/citation/deletion scenario with synthetic files and disposable PostgreSQL.

CI now includes the credential-free provenance evaluation and PostgreSQL integration script. Live provider tests remain explicit opt-in to avoid unpredictable cost and quota consumption. Environment files are ignored, and local Compose ports bind to loopback.

## Final architecture

React → authenticated FastAPI routes → SQLAlchemy metadata/chunks/history → owner-scoped pgvector + FTS + RRF → optional reranker → Gemini via LiteLLM → answer and complete evidence. Ingestion runs as an in-process background task; storage is private disk or Supabase; Redis provides optional shared caching/progress. See [ARCHITECTURE.md](ARCHITECTURE.md) for component and sequence diagrams.

## Verification and evidence

The initial 85-test baseline passed. New tests cover span fidelity, chunk bounds, PDF blank pages, DOCX tables, empty input, failed analyses, invalid vectors, bounded history, cache expiry, password-byte limits and JSON-provider authentication failures. The final command results are recorded in the concluding verification section below.

Commands used from the repository root unless noted:

```sh
backend/.venv/bin/pytest backend/tests -q --cov=app --cov-report=term-missing --cov-fail-under=60
backend/.venv/bin/ruff check backend/app backend/tests
# Run from backend:
.venv/bin/mypy app/services/rag_service.py app/services/rerank_service.py app/services/ai_service.py --follow-imports=skip --ignore-missing-imports
# Run from repository root:
backend/.venv/bin/python scripts/smoke_test.py
backend/.venv/bin/python scripts/evaluate_local.py
backend/.venv/bin/python scripts/check_pgvector.py
backend/.venv/bin/python scripts/live_gemini_smoke.py
# Additional provider quota required:
backend/.venv/bin/python scripts/live_gemini_smoke.py --extended
# Run from frontend:
npm run lint
npm run build
npm audit --omit=dev
```

### Real requests

The credential-free smoke starts a real Uvicorn process, verifies readiness, demo analyses, read-only access and cross-account isolation. It additionally exercises empty uploads and malformed PDF failure/deletion.

The [first live Gemini run](live_gemini_primary_run.json), recorded from its observed stdout, completed PDF upload, real embeddings, pgvector persistence/retrieval, analysis, question answering, a follow-up, refusal and deletion. The answer was “According to Source 1 (Page 2), the warranty lasts 24 months.” The supporting passage included both warranty and support facts on physical page 2. Ingestion took 51,645 ms and the measured answer path took 14,787 ms in that run; these are single observations, not performance benchmarks.

An expanded run passed the PDF, follow-up, refusal and answer-cache checks, then failed with HTTP 429 on a Markdown question. It is retained in [live_gemini_first_extended_attempt.json](live_gemini_first_extended_attempt.json). The latest expanded-run result is in [live_gemini_results.json](live_gemini_results.json); its `status` and checks are authoritative. Partial runs must not be described as complete format coverage.

### Evaluation comparison

[Raw results](local_retrieval_results.json), six synthetic cases, K=3:

| Metric | Frozen baseline | Current |
| --- | ---: | ---: |
| Retrieval hit rate | 6/6 | 6/6 |
| Correct supporting physical page retrieved | 0/6 | 6/6 |
| LLM answer quality / factual groundedness | Not measured in this comparison | Not measured in this comparison |

The frozen baseline was taken from the repository's prior document processor. The comparison simulates extracted PDF page text, persists chunks in actual SQLite, then calls the application's lexical retrieval function. A separate real PDF live test validates extraction and page attribution through Gemini/pgvector. Timing values are recorded but are too small and sample-dependent to establish a speed improvement. No claim is made that semantic retrieval accuracy improved.

The historical dense/reranker benchmark remains unvalidated. No historical scores were replaced with invented results. The new local measurement is separate and does not validate the historical benchmark UI.

### Checks and limitations

Frontend ESLint and production build passed. Backend Ruff and the existing three-service mypy scope passed. `pip check` reported no broken requirements; this is a dependency consistency check, not a vulnerability scan. `npm audit --omit=dev` reported zero known production-package vulnerabilities at audit time. The design detector returned no findings for the changed UI targets; this is not a WCAG certification.

## Launch continuation — 21 October 2026

- Backend: **112 passed**, **60.96% coverage**, exceeding the configured 60% threshold. Frontend: **5 passed**, lint and production build pass.
- Replaced `python-jose` with pinned PyJWT 2.15.1 after a dependency advisory was identified; restricted application JWT algorithms to HS256. Existing HS256 JWT format remains compatible.
- `npm audit` now reports zero known findings across the complete resolved frontend dependency tree. Removed unused Tailwind tooling rather than migrating the working CSS. Both the pinned-requirements audit and the full resolved Python dependency audit report zero known findings; the resolved audit includes transitive dependencies.
- Retry processing is connected from the UI to an authenticated API endpoint, preserving original identity and storage. It rejects demo sessions and other owners. Reindexing refreshes content/page metadata and removes stale passages.
- Reads mark overdue pending/processing jobs as interrupted failures, scoped to the requesting owner. This provides manual recovery after crashes, not automatic durable execution.
- Local originals are created exclusively with mode 0600 and are not silently overwritten.
- The default analysis mode combines four panels into one validated provider call. A unit test verifies one generation call, and an API integration test verifies all analysis panels. This reduces request count by construction; no measured model-quality or billed-cost improvement is claimed.
- The PostgreSQL check now applies the actual bootstrap and migrations and verifies browser-role privilege revocations plus RLS, in addition to retrieval. Production readiness checks schema and shared Redis. No hosted SQL was applied.
- Deployment defaults now match tested Gemini settings, retain explicit configured models, force private Supabase storage/production debug settings and reject local/insecure production endpoints. The deployment helper accepts a separate private production environment file.
- A fresh generation connectivity probe and embedding probe passed. That morning’s extended live run failed during **analysis** with provider HTTP 429. Dated failure artifacts are retained; the later Flash Lite continuation below supersedes that status.
- The connected Supabase account's only project, `personal`, was inactive. It was inspected without reactivation or mutation.

[GO_LIVE.md](GO_LIVE.md) contains the concrete owner inputs and review/apply sequence. The private production file is created and ignored; its remaining missing settings are listed in [launch-check.json](verification/launch-check.json).

## Autonomous preview continuation — 22 October 2026

- **118 backend tests pass, 61.55% coverage; seven frontend tests pass.** Backend Ruff and three-service mypy scope, frontend lint/build and diff whitespace checks pass.
- Switched the local configuration to available `gemini/gemini-3.5-flash-lite`. Model listing alone was insufficient: a listed 2.5 Flash model returned 404 for this account, and 3.8 Flash returned temporary 503. Flash Lite passed actual generation.
- Removed custom low-temperature values for Gemini 3+ following [Google’s model guidance](https://ai.google.dev/gemini-api/docs/gemini-3). Local asynchronous attempt deadlines now receive at most three attempts; the pipeline/query deadlines and daily quota fail-fast rules remain in place.
- A complete extended run passed all four formats, adversarial document text, follow-up, refusal, page provenance, caching, balanced multi-document synthesis and deletion. The [raw passing run](live_gemini_20261021T200407Z.json) records a 4,125 ms primary ingestion and 2,582 ms primary answer. These are single observations, not benchmarks.
- The extended test exposed a product bug: lifetime `documents_processed` was used for the three-document storage allowance. The quota now counts retained documents (including pending/failed), locks the owner row for PostgreSQL uploads, and frees a slot on deletion without changing historical usage statistics.
- Added an optional built SPA mount to FastAPI, with API/asset/dotfile 404 boundaries. HTTP and WebSocket URLs now share the configured origin, including HTTPS/WSS. Added regression tests.
- `scripts/preview.py` runs an isolated persistent Docker database, local private originals, built frontend/API and optional account-free HTTPS tunnel. It leaves hosted Supabase and portfolio files untouched. It supports start/status/stop and preserves data across restart.
- The public API passed real PDF upload/analysis/answer/citation, another-account isolation and deletion. Final link and browser checks are recorded in the public preview artifact. This Mac must remain awake, online and running Docker; the tunnel is temporary.

## Remaining release blockers and roadmap

1. **Durable ingestion:** process restarts can strand jobs. Add a persistent queue/worker, restart recovery and parser process resource limits before production reliability claims.
2. **Provider quotas:** the extended live run encountered HTTP 429. The direct provider diagnostic confirmed daily quota exhaustion, not a credential failure; see `provider_diagnostic.json`. A subsequent run exceeded its 180-second test deadline while retrying, recorded in `live_gemini_retry_attempt.json`. This led to the new 120-second processing deadline and daily-quota fail-fast handling, both regression-tested locally. The later Flash Lite run passed, but adequate allowance and monitoring are still needed for reliable multi-user production usage; no canned answer fallback was added.
3. **Hosted boundaries:** validate Supabase private bucket permissions, SQL migrations/RLS, deployed CORS and anonymous demo access. Local PostgreSQL proves SQL behavior, not hosted security.
4. **Evaluation depth:** add representative labeled documents, paraphrases, conflicting sources, multilingual/OCR cases and claim-level citation/groundedness judgments. Measure reranking before enabling it by default.
5. **Security/reliability:** implement refresh-token revocation, shared rate limits, atomic quota reservations and storage/database reconciliation. Add recurring dependency scanning and complete billing webhook/idempotency tests.
6. **Product completion:** original-file preview/download, multi-document conversational follow-ups, history with source inspection, frontend automated browser end-to-end tests and broader desktop/mobile accessibility checks.
7. **Observability:** provider-reported token/cost usage, stage latency distributions, queue health and schema/provider readiness. Current token estimates are not billing data.

No scalability, cost reduction, comprehensive security, hallucination elimination or production deployment claim is supported by this audit.

## Preview service recovery — 22 October 2026

Installed a per-user macOS launch agent (`com.documind.preview`) to restart the
preview process after exit and at login. The helper supports install/remove/status
and checks checkout ownership before replacing a service. Runtime secrets stay in
the ignored private data directory. Status now suppresses stale public links when
the launcher is no longer running. Docker and an awake, connected Mac remain
requirements; the tunnel URL changes after restart.

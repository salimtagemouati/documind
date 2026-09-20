# Local Run and Honest Landing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DocuMind start reliably with SQLite or a temporarily unavailable PostgreSQL database, provide a usable local demo flow, and remove unverifiable landing-page claims.

**Architecture:** Keep the FastAPI process alive independently from database readiness. Centralize database URL validation, availability state, health checks, and retry behavior in `app/db/database.py`; HTTP dependencies translate database outages into clean 503 responses. Use a documented SQLite development mode with Python-side lexical retrieval, while keeping pgvector/PostgreSQL behavior unchanged in production. Frontend API status/error handling remains centralized and the demo route waits for a cold backend before authenticating.

**Tech Stack:** FastAPI, SQLAlchemy async, asyncpg, aiosqlite, pgvector, pytest, React 18, TypeScript, Axios, Zustand, react-hot-toast, Vite.

**Spec:** `/Users/salimtagemouati/.codex/attachments/d411e89c-e5ad-4ec2-b189-4534e34f5734/Pasted text.txt`

## Global Constraints

- Never read, print, copy, or commit `backend/.env` or any secret value.
- Never place credentials in commands, tracked files, tests, or logs.
- Do not run the full evaluation benchmark, push, or deploy.
- Preserve the existing pgvector production path and all existing tests.
- Run backend pytest and frontend build before each commit.
- Keep each change in its requested category with minimal unrelated churn.

---

### Task 1: Resilient Database Startup and SQLite Development Mode

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/db/database.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models/models.py`
- Modify: `backend/app/services/rag_service.py`
- Modify: `backend/app/services/demo_service.py`
- Create: `backend/tests/test_database_resilience.py`
- Modify: `backend/tests/test_rag_service.py`

**Interfaces:**
- Produces: `validate_database_url(url: str)`, `is_database_available()`, `check_database_health()`, `retry_database_connection()`, and SQLite lexical retrieval.
- Consumes: existing `Base`, `engine`, `AsyncSessionLocal`, and FastAPI lifespan.

- [x] Write failing tests for placeholder URL validation, unavailable startup with 503 health, clean 503 database dependency errors, SQLite table creation, and SQLite retrieval.
- [x] Run the focused tests and confirm they fail for missing behavior.
- [x] Add safe URL validation and database availability state without logging credentials.
- [x] Change lifespan startup to continue when the database is unavailable and start a cancellable retry task with exponential attempts followed by 30-second intervals.
- [x] Add `/health` and `/ready` responses that return 200 when connected and 503 with `{"status":"degraded","db":"unreachable"}` otherwise.
- [x] Compile PostgreSQL-only UUID, ARRAY, and Vector types for SQLite and create metadata only in SQLite mode.
- [x] Add a documented SQLite lexical retrieval path and seed demo chunks without provider embeddings.
- [x] Run focused tests, full pytest, Ruff, and frontend build. Focused mypy exposed three pre-existing untyped SQLAlchemy columns.
- [x] Commit as `fix(backend): make local database startup resilient`.

### Task 2: Local Development Documentation and Safe Examples

**Files:**
- Create: `docs/LOCAL_DEV.md`
- Modify: `docs/superpowers/plans/2026-09-20-local-run-and-landing.md`
- Modify: `backend/.env.example`
- Modify: `frontend/.env.example`
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Produces: a secret-free SQLite quickstart and Supabase pooler guidance.
- Consumes: backend port 8000, frontend dev port 5173, preview port 4173, migrations `001` then `003`.

- [x] Set the backend example database to `sqlite+aiosqlite:///./dev.db` and use only `REPLACE_ME` placeholders for secrets.
- [x] Make the frontend example local-first and remove the obsolete Render URL.
- [x] Ignore `backend/dev.db` and retain `.env` and `.eval_cache/` exclusions.
- [x] Document SQLite startup, Supabase Session/Transaction poolers, URL encoding, CORS, migrations, Vite dev/preview behavior, and verification commands.
- [x] Link the guide from README.
- [x] Run secret-marker scans, pytest, Ruff, frontend lint, and frontend build.
- [x] Commit as `docs: add safe local development setup`.

### Task 3: Frontend Cold-Start and Error Experience

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/services/api.ts`
- Create: `frontend/src/services/toasts.ts`
- Modify: `frontend/src/store/authStore.ts`
- Modify: `frontend/src/pages/DemoPage.tsx`
- Modify: `frontend/src/pages/AuthPage.tsx`
- Modify: `frontend/src/pages/LandingPage.tsx`
- Modify: `frontend/src/components/dashboard/DocumentViewer.tsx`
- Modify: `frontend/src/components/dashboard/MultiDocViewer.tsx`
- Modify: `frontend/src/components/dashboard/UpgradePrompt.tsx`
- Modify: `frontend/src/pages/BillingPage.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Modify: `frontend/vite.config.ts`
- Modify: `docs/LOCAL_DEV.md`

**Interfaces:**
- Produces: `getApiErrorMessage(error, fallback)`, `waitForApi(timeoutMs)`, and `showApiError(error, fallback, id)`.
- Consumes: `/health`, Axios errors, `Retry-After`, and existing Zustand authentication.

- [x] Add a deterministic error classifier for unreachable API, 429 retry timing, demo 403, and generic failures.
- [x] Add toast de-duplication by stable ID and a maximum of three visible error toasts.
- [x] Add health prewarming on landing load without visible failure.
- [x] Make the demo route poll health for at most 60 seconds, show the cold-start message after 3 seconds, prevent duplicate attempts, and provide an explicit retry action.
- [x] Route component errors through the centralized toast helper and keep buttons disabled during requests.
- [x] Proxy `/health` in Vite development and document manual toast/cold-start checks because the repository has no Vitest/RTL harness.
- [x] Run Impeccable detection, frontend lint/build, backend pytest, and Ruff.
- [x] Commit as `fix(frontend): handle API cold starts and dedupe errors`.

### Task 4: Honest Landing Content and Payment State

**Files:**
- Modify: `backend/app/api/routes/billing.py`
- Modify: `frontend/src/services/api.ts`
- Modify: `frontend/src/pages/LandingPage.tsx`
- Modify: `frontend/src/pages/LandingPage.css`
- Modify: `backend/app/eval/evaluator.py`
- Modify: `backend/app/api/routes/query.py`
- Modify: `README.md`
- Modify: `docs/EVALUATION_REPORT.md`
- Modify: `docs/HANDOFF.md`
- Modify: `backend/tests/test_auth.py`

**Interfaces:**
- Produces: public `GET /api/v1/billing/config` returning only `payments_enabled: bool`.
- Consumes: actual free limits 3 documents and 20 daily queries from backend settings.

- [x] Write a failing backend test for the non-secret payment configuration endpoint.
- [x] Implement the endpoint and frontend query with a safe disabled default.
- [x] Replace fabricated usage statistics with qualitative capabilities.
- [x] Rename all cross-encoder claims to LLM re-ranking.
- [x] Remove unsupported trial, priority, API-access, email-support, and latency promises.
- [x] Keep only features confirmed by `ai_service.py`, document processing, and billing enforcement.
- [x] Run repository claim searches, Impeccable detection, pytest, Ruff, lint, build, and npm audit.
- [x] Commit as `fix(landing): align product claims with implementation`.

### Task 5: Local SQLite Smoke Verification

**Files:**
- No tracked file changes expected.

**Interfaces:**
- Consumes: local `backend/.env` without reading it, process-scoped SQLite URL, `/health`, `/api/v1/auth/demo`, `/api/v1/documents/`, and demo upload guard.
- Produces: sanitized command evidence only.

- [ ] Start Uvicorn with only a process-scoped SQLite database override.
- [ ] Confirm `/health` and `/ready` return 200.
- [ ] Create a demo session without printing the full token and confirm seeded documents list successfully.
- [ ] Confirm demo upload returns 403.
- [ ] Run final pytest with coverage, Ruff, focused mypy, frontend lint/build, npm audit, `git diff --check`, and a clean status check.
- [ ] Record any remaining environment-dependent work without creating a verification-only commit.

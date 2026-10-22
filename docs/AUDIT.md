# End-to-end audit — October 1, 2026

## Fixed

- PostgreSQL enum names now match the checked-in SQL migrations (`user_role` and `doc_status`), preventing insert casts to nonexistent types.

- The public demo's source-visible password could be used through normal login to obtain unrestricted tokens. Normal login and registration now reject that identity, new seed passwords are random, and current database identity enforces demo restrictions even for previously issued tokens.
- Access tokens now reject missing/deactivated accounts and malformed subjects; current roles come from the database.
- SQLite uploads no longer require Supabase Storage. Originals are stored privately on local disk, with bounded reads and path containment, and removed on document deletion.
- Uploads commit before the background worker opens its own session, avoiding a visibility race.
- Invalid pagination values now produce HTTP 422 instead of division errors or unbounded page sizes.
- Provider authentication/model errors return a useful HTTP 503. A document whose entire AI analysis fails is marked failed, and provider exception text is not exposed through document metadata.
- Account switches clear the React Query cache. Authentication failures remove only application-owned storage keys; failed login requests no longer trigger token refresh.
- Setup generates a signing secret without overwriting existing environment files. Docker persists local data, and frontend tooling consistently targets Node 22.
- CI includes frontend lint and a real-process API smoke test. The README distinguishes sample fixtures, local lexical retrieval and production vector retrieval; its broken public-demo claim is removed.
- Added the missing MIT license file already referenced by the repository, and corrected the landing page's GitHub link.

## External limitations

- The configured Google provider credential was rejected with `AuthenticationError` (HTTP 401). A valid credential is required to verify live AI generation. Unit/integration tests use mocked AI responses; they do not prove that a provider accepts the current key.
- The README's previous Vercel deployment redirected anonymous requests to Vercel sign-in. A publicly accessible deployment and a working backend/provider must be verified before restoring a public-demo badge.
- Docker was installed but its daemon was not running during this audit. Container build/runtime verification remains a CI check.
- No live PostgreSQL/Supabase database was modified. SQLite tests do not validate production HNSW indexes, RLS, or Supabase Storage.
- The historical evaluation artifact remains invalid under the revised methodology. It has not been regenerated using a working provider.

## Verification completed

- Backend suite: **85 passed**, including 14 new regression cases, with **60.32% coverage** (required: 60%). Python 3.13.7 locally; CI retains Python 3.11. One upstream Starlette/httpx deprecation warning remains.

- Fresh `npm ci`, frontend ESLint and production build passed on Node 22.20.0.
- Backend Ruff checks, the existing service-level mypy checks, and `pip check` passed.
- The real-process, credential-free API smoke test passed.
- Setup was checked in a disposable directory: generated secrets, private file permissions and preservation of existing files passed.
- `docker compose config --quiet` passed; the Docker daemon was unavailable for a build/run.
- Browser checks covered the landing page, demo sign-in, seeded document analysis, benchmark panel, sign-out, a separate account's empty workspace and disabled billing.
- Live AI verification failed at provider authentication (HTTP 401), before a successful answer could be established.

## Reproduce

Use the verification commands in the README. `scripts/smoke_test.py` creates and removes its own temporary database, starts a real Uvicorn process, and checks demo seeding, analyses, read-only enforcement and tenant isolation without loading local credentials.

Changes are local only: no commit, push or deployment was performed.

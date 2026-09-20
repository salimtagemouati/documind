# Local development

DocuMind supports two database modes:

- SQLite for a zero-infrastructure local start. Tables and demo chunks are created locally; retrieval uses a deterministic lexical fallback and does not call the embedding provider.
- Supabase PostgreSQL for the production pgvector path. Apply the SQL migrations before using document retrieval.

Never commit `backend/.env` or `frontend/.env`. The repository ignores both files and the local SQLite database.

## Quickstart with SQLite

From the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Replace `SECRET_KEY=REPLACE_ME` with a local random value. The Supabase placeholders may remain unchanged while testing local health, authentication, the seeded demo, and document listing. A provider credential is required only for AI generation.

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

The default `DATABASE_URL=sqlite+aiosqlite:///./dev.db` creates `backend/dev.db`. Healthy probes return HTTP 200:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:8000/ready
```

If PostgreSQL is configured but unreachable, FastAPI still starts. `/health` and `/ready` return HTTP 503 with a degraded database status, and database-backed routes return a short 503 response instead of a traceback. The process retries database initialization in the background.

## Frontend

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`. An empty `VITE_API_URL` uses the Vite development proxies for `/api` and `/health`.

`npm run preview` normally listens on `http://127.0.0.1:4173` and does not use the development proxy. For preview, set:

```text
VITE_API_URL=http://127.0.0.1:8000/api/v1
```

The backend allows both default local origins. If the frontend uses another port, add its exact origin to `ALLOWED_ORIGINS`; do not use `*` with authenticated requests.

## Supabase PostgreSQL and pgvector

Use an async SQLAlchemy URL:

```text
DATABASE_URL=postgresql+asyncpg://USER:URL_ENCODED_PASSWORD@POOLER_HOST:5432/postgres
```

Percent-encode reserved characters in the password before placing it in the URL. Supabase provides two pooler modes:

- Session mode, commonly on port 5432, is appropriate for a persistent application connection pool.
- Transaction mode, commonly on port 6543, is useful when direct or session connections are unavailable. DocuMind disables asyncpg statement caches for this mode because transaction poolers do not preserve session-level prepared statements.

Use the connection parameters shown by the target Supabase project rather than copying a host from documentation. Keep the database region close to the Cloud Run region to reduce round-trip latency.

Apply migrations in order with a PostgreSQL client. `psql` expects a `postgresql://` connection URI rather than SQLAlchemy's `postgresql+asyncpg://` URL; keep that URI in an untracked local environment variable:

```bash
psql "$PSQL_DATABASE_URL" -f scripts/001_init_schema.sql
psql "$PSQL_DATABASE_URL" -f backend/migrations/002_add_billing.sql
psql "$PSQL_DATABASE_URL" -f backend/migrations/003_pgvector.sql
```

The pgvector migration must match `EMBEDDING_DIM=768`. SQLite is a local compatibility mode and does not validate PostgreSQL extensions, RLS policies, HNSW indexes, or Supabase Storage.

## Verification

```bash
cd backend
pytest tests/ -q --cov=app --cov-report=term-missing
ruff check app tests

cd ../frontend
npm run lint
npm run build
```

Manual checks:

1. Open `/demo` while the backend is stopped and confirm the page offers a retry without duplicating error notifications.
2. Start the backend and retry; the demo should open with seeded documents.
3. Stop and restart the backend to exercise the frontend cold-start message.
4. In demo mode, confirm upload and delete operations remain forbidden.

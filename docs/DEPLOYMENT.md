# DocuMind — Deployment Guide

> Production deployment on **Render** (backend + Redis) + **Vercel** (frontend).
> AI powered by **Google Gemini 1.5 Flash** (free tier — $0 operating cost).

---

## Prerequisites

- [x] GitHub repository with DocuMind code pushed
- [x] Supabase project created (PostgreSQL + Storage)
- [x] Google AI Studio API key (free) → [aistudio.google.com](https://aistudio.google.com/app/apikey)
- [ ] Render account → [render.com](https://render.com)
- [ ] Vercel account → [vercel.com](https://vercel.com)

---

## 1. Database Setup (Supabase)

Run the schema migration in your Supabase SQL editor:

```sql
-- Initial schema
-- Copy contents of scripts/001_init_schema.sql
```

Create a storage bucket:
1. Go to **Storage** → **New Bucket**
2. Name: `documents`
3. Public: **No** (files are accessed via signed URLs)

---

## 2. Google Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Click **Create API Key**
3. Copy the key (starts with `AIzaSy...`)
4. Set as `GOOGLE_API_KEY` environment variable

> **Cost: $0** — Gemini 1.5 Flash free tier includes:
> - 15 RPM, 1M TPM, 1,500 RPD for chat
> - Embedding API has generous free limits
> - No credit card required

---

## 3. Backend — Render

### Option A: Blueprint (Recommended)

1. Go to [Render Dashboard](https://dashboard.render.com) → **New** → **Blueprint**
2. Connect your GitHub repo
3. Point to `infra/render.yaml`
4. Render will create:
   - `documind-api` (Web Service, Docker)
   - `documind-redis` (Redis instance)
5. Fill in the environment variables marked `sync: false` (see the full env matrix below).

### Option B: Manual

1. **New Web Service** → Docker → Root: `backend`
2. **New Redis** → Connect to web service via internal URL
3. Set the env vars from the matrix below.

### 3a. Backend Environment Variables (full matrix)

| Variable | Required | Default | Where to get it / what it does |
|----------|---------|---------|--------------------------------|
| `SECRET_KEY` | ✅ | — | 32-byte hex string for JWT signing. Generate with `python -c "import secrets; print(secrets.token_hex(32))"` (Render can auto-generate via `generateValue: true`). |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ⚠️ | `60` | Access-token lifetime in minutes. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ⚠️ | `30` | Refresh-token lifetime in days. |
| `ALLOWED_ORIGINS` | ✅ | `["http://localhost:5173", …]` | JSON array of CORS-allowed origins. Include your Vercel frontend URL. |
| `SUPABASE_URL` | ✅ | — | Supabase → Settings → API → URL. |
| `SUPABASE_ANON_KEY` | ✅ | — | Supabase → Settings → API → `anon` key. |
| `SUPABASE_SERVICE_KEY` | ✅ | — | Supabase → Settings → API → `service_role` key. **Never expose to the frontend.** |
| `DATABASE_URL` | ✅ | — | Supabase → Settings → Database → Connection string (URI). Must use the `postgresql+asyncpg://` driver prefix. |
| `SUPABASE_BUCKET` | ⚠️ | `documents` | Storage bucket name. |
| `MAX_FILE_SIZE_MB` | ⚠️ | `20` | Reject uploads larger than this. |
| `ALLOWED_EXTENSIONS` | ⚠️ | `["pdf","txt","docx","md"]` | JSON array of permitted file extensions. |
| `GOOGLE_API_KEY` | ✅ | — | [aistudio.google.com](https://aistudio.google.com/app/apikey). |
| `GEMINI_CHAT_MODEL` | ⚠️ | `gemini-1.5-flash` | Override to use a different Gemini model. |
| `GEMINI_EMBEDDING_MODEL` | ⚠️ | `text-embedding-004` | Override only if you know what you're doing — must match the dimensionality FAISS expects. |
| `CHUNK_SIZE` | ⚠️ | `800` | Token target per RAG chunk. |
| `CHUNK_OVERLAP` | ⚠️ | `100` | Token overlap between consecutive chunks. |
| `MAX_CHUNKS_PER_DOC` | ⚠️ | `200` | Hard cap on chunks per document (cost / latency control). |
| `RAG_TOP_K` | ⚠️ | `6` | Chunks retrieved per query. |
| `RAG_SIMILARITY_THRESHOLD` | ⚠️ | `0.70` | Minimum cosine similarity for a chunk to be considered relevant. |
| `RATE_LIMIT_REQUESTS` / `RATE_LIMIT_WINDOW` | ⚠️ | `60` / `60` | Default per-IP rate limit (requests per window in seconds). |
| `AI_RATE_LIMIT_REQUESTS` / `AI_RATE_LIMIT_WINDOW` | ⚠️ | `10` / `60` | Tighter limit for AI-touching endpoints. |
| `REDIS_URL` | ✅ | `redis://localhost:6379` | Auto-wired from the Render Redis instance. Empty string disables Redis (in-memory fallback). |
| `CACHE_TTL_SECONDS` | ⚠️ | `3600` | TTL for cached Q&A answers. |
| `FREE_DOC_LIMIT` | ⚠️ | `10` | Max documents per account. Set to `0` to disable the cap. |
| `SENTRY_DSN` | ❌ | `""` | Optional — enables Sentry error tracking. |
| `ENVIRONMENT` | ⚠️ | `development` | One of `development` / `staging` / `production`. Affects Swagger exposure. |
| `DEBUG` | ⚠️ | `false` | Enables SQL echo + verbose logging. **Must be `false` in production.** |

✅ required · ⚠️ recommended · ❌ optional

### 3b. Verify Backend

```bash
# Health check
curl https://documind-api.onrender.com/health

# Expected:
# {"status":"healthy","app":"DocuMind","version":"1.0.0","environment":"production"}
```

---

## 4. Redis on Render

1. Go to Render Dashboard → **New** → **Redis**
2. Name: `documind-redis`
3. Plan: Free tier or Starter
4. After creation, copy the **Internal Connection String**
5. Set as `REDIS_URL` on your backend service

> The internal URL format is: `redis://red-xxxxx:6379`

---

## 5. Frontend — Vercel

### Deploy

1. Go to [Vercel Dashboard](https://vercel.com/dashboard) → **Add New** → **Project**
2. Import your GitHub repo
3. Configure:
   - **Framework Preset**: Vite
   - **Root Directory**: `frontend`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

4. **Environment Variables**:

| Variable | Value |
|----------|-------|
| `VITE_API_URL` | `https://documind-api.onrender.com/api/v1` |

5. Click **Deploy**

### Custom Domain (Optional)

1. Vercel → Project Settings → Domains
2. Add your domain (e.g., `app.documind.com`)
3. Update `ALLOWED_ORIGINS` on Render to include the new domain

---

## 6. GitHub Actions CI

CI runs automatically on push to `main`/`develop` and on PRs.

The workflow runs **3 parallel jobs**:

| Job | What it does |
|-----|-------------|
| `backend` | ruff lint → AST syntax check → pytest (with Redis service) |
| `frontend` | TypeScript check → Vite production build → bundle size report |
| `docker` | Full Docker image build (after backend passes) |

> Tests are run with `pytest tests/ -v --tb=short` — failures will fail the build (no silent skipping).

### CI Secrets

Tests use mocks for all external APIs, so no GitHub Actions secrets are required for the default workflow. If you enable real-API integration tests, you'll need:

| Secret | Value |
|--------|-------|
| `GOOGLE_API_KEY` | Your Gemini API key |

---

## 7. Post-Deploy Smoke Test Checklist

Run through this after every deployment:

- [ ] Backend `/health` returns 200
- [ ] Frontend loads at Vercel URL
- [ ] **Register** a new user → verify JWT tokens returned and email present in token payload
- [ ] **Upload** a PDF document → returns 202
- [ ] **Watch processing** → WebSocket shows progress stages
- [ ] **Wait for "Ready!"** status
- [ ] **Ask a question** about the document → expect answer with source citations
- [ ] **Verify sources** — answer references `[Source N]` labels
- [ ] **Hit document limit** — upload more than `FREE_DOC_LIMIT` documents → expect 429 with the limit message

---

## Architecture Overview

```
┌──────────────────┐     HTTPS      ┌──────────────────┐
│   Vercel CDN     │◄──────────────►│     Browser      │
│   (React SPA)    │                │                  │
└────────┬─────────┘                └──────────────────┘
         │ VITE_API_URL                      │
         ▼                                   │ WebSocket
┌──────────────────┐                         │
│  Render          │◄────────────────────────┘
│  (FastAPI)       │
│  ├── Auth        │     ┌──────────────┐
│  ├── Documents   │────►│  Supabase    │
│  ├── RAG/Query   │     │  (Postgres + │
│  └── WebSocket   │     │   Storage)   │
│                  │     └──────────────┘
│  ├── FAISS       │     ┌──────────────┐
│  └── Redis ──────│────►│ Render Redis │
│      (cache +    │     │ (pub/sub)    │
│       pub/sub)   │     └──────────────┘
└──────────────────┘
         │                ┌──────────────┐
         └───────────────►│  Google AI   │
           Gemini API     │  (free tier) │
                          └──────────────┘
```

---

## Troubleshooting

### Backend won't start
- Check the **Logs** tab on Render
- Most common: missing env var → check all required vars are set
- Database URL format must be `postgresql+asyncpg://...`
- `GOOGLE_API_KEY` must be set (even for basic startup)

### "No FAISS index found" errors after migration
- On first startup after the OpenAI → Gemini migration, old indexes are automatically purged
- Documents need to be re-uploaded and re-processed with the new Gemini embeddings
- This is expected — old 1536d OpenAI embeddings are incompatible with 768d Gemini embeddings

### WebSocket not connecting
- Ensure Render plan supports long-lived connections (Starter+ does)
- Check CORS origins include your frontend domain
- Browser console: look for WebSocket errors

### Gemini API rate limits
- Free tier: 15 requests per minute, 1,500 per day
- If you hit limits, wait 60 seconds or upgrade to pay-as-you-go
- Embeddings have separate (generous) limits

### Frontend shows blank page
- Check `VITE_API_URL` is set correctly in Vercel env vars
- Check browser console for CORS errors
- Ensure the Render backend `ALLOWED_ORIGINS` includes your Vercel URL

### Common env var issues
| Symptom | Fix |
|---------|-----|
| `ValidationError: GOOGLE_API_KEY` | Set `GOOGLE_API_KEY` in Render env vars |
| `asyncpg.InvalidCatalogNameError` | Check `DATABASE_URL` format — must use `postgresql+asyncpg://` |
| `CORS error` | Add frontend domain to `ALLOWED_ORIGINS` |
| 429 on every upload | `FREE_DOC_LIMIT` reached for the account — increase the env var or set to `0` to disable |

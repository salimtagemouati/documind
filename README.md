# DocuMind — AI Document Intelligence Platform

> A production-grade, full-stack SaaS application that transforms any document into structured knowledge using RAG, semantic search, and LLM pipelines.

[![CI](https://github.com/SalimTag/documind/actions/workflows/ci.yml/badge.svg)](https://github.com/SalimTag/documind/actions)
[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB)](https://react.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Overview

DocuMind is a full-stack AI SaaS application that allows users to upload documents (PDF, DOCX, TXT) and instantly extract intelligence from them: structured summaries, named entity graphs, sentiment analysis, keyword extraction — and most importantly, a **RAG-powered Q&A engine** that answers questions grounded strictly in the document content.

Built to demonstrate production-level software engineering: async Python backend, JWT authentication, PostgreSQL with Row Level Security, FAISS vector indexing, Redis caching, and a React dashboard — all deployable in one command.

---

## Architecture

```
┌────────────────────────────────────────────────────┐
│              React Frontend (Vite)                  │
│   Auth · Upload · Dashboard · Analysis · Q&A       │
└──────────────────────┬─────────────────────────────┘
                       │ HTTPS + JWT Bearer
┌──────────────────────▼─────────────────────────────┐
│           FastAPI Backend (Python 3.11)             │
│  JWT auth · Rate limiting · CORS · Health checks   │
│                                                     │
│  ┌─────────────┐  ┌──────────────┐  ┌───────────┐ │
│  │Auth Service │  │Doc Processor │  │AI Service │ │
│  │JWT · bcrypt │  │Extract·Chunk │  │LLM prompts│ │
│  └─────────────┘  └──────────────┘  └───────────┘ │
│                                                     │
│  ┌──────────────────────────────────────────────┐  │
│  │            RAG Service (Core)                │  │
│  │  Embed chunks → FAISS index → Retrieve top-K │  │
│  │  → Build context → LLM → Grounded answer     │  │
│  └──────────────────────────────────────────────┘  │
└────────┬────────────┬─────────────┬────────────────┘
         │            │             │
    ┌────▼───┐  ┌─────▼────┐  ┌────▼────┐
    │Postgres│  │Supabase  │  │  Redis  │
    │+Supa.  │  │Storage   │  │ Cache   │
    │RLS     │  │(files)   │  │(Q&A TTL)│
    └────────┘  └──────────┘  └─────────┘
                                    │
                            ┌───────▼──────┐
                            │  Google AI   │
                            │ Gemini Flash │
                            │+ Embeddings  │
                            └──────────────┘
```

### Component breakdown

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React 18, Vite, Zustand, TanStack Query | Dashboard, auth, file upload, analysis display, Q&A |
| API layer | FastAPI, Pydantic v2, Uvicorn | REST API, request validation, JWT middleware |
| Auth | python-jose, passlib/bcrypt | Token issuance, refresh, password hashing |
| Doc processor | pypdf, python-docx, tiktoken | Text extraction, smart sentence-aware chunking |
| RAG service | FAISS, Gemini text-embedding-004 | Vector index build, semantic similarity retrieval |
| AI service | Google Gemini 1.5 Flash | Summarization, entity extraction, sentiment, Q&A |
| Database | PostgreSQL (Supabase), SQLAlchemy async | Users, documents, chunks, query history, analytics |
| Storage | Supabase Storage | Binary file storage with per-user path isolation |
| Cache | Redis | Q&A response caching (TTL 1h), cost control |
| CI | GitHub Actions | Test + build on every push |

---

## Key Engineering Decisions

### RAG over naïve text dumping
Most demos send the full document text to the LLM. This fails for large documents (exceeds context window), wastes tokens (expensive), and produces unfocused answers. DocuMind implements proper RAG:

1. **Chunking** — documents split into ~800-token segments with 100-token overlap at sentence boundaries (not arbitrary character positions)
2. **Embedding** — each chunk embedded via `text-embedding-004` into 768-dimensional vectors
3. **FAISS indexing** — inner product index built per document, persisted to disk
4. **Retrieval** — query embedded, top-6 most similar chunks fetched (cosine similarity ≥ 0.70)
5. **Generation** — only retrieved context passed to Gemini, with strict "answer from document only" system prompt

### Map-reduce summarization
Gemini 1.5 Flash's large context window allows processing up to 15 chunks directly. For larger documents (15+ chunks), DocuMind uses a lightweight two-pass approach: groups of 10 chunks summarized independently, then summaries combined.

### Async pipeline + background tasks
File upload returns `202 Accepted` immediately. The full processing pipeline (extract → chunk → embed → analyze) runs as a FastAPI `BackgroundTask`, with status polling available via `GET /documents/{id}`.

### Redis caching for cost control
Identical Q&A pairs (same document + normalized question) are cached for 1 hour. Cache hit rate is tracked per-user in analytics. This prevents re-charging users for repeated queries.

---

## Features

### Document intelligence
- **Summarization** — 3–6 sentence AI summary using map-reduce for large docs
- **Named entity extraction** — persons, organizations, locations, dates, technologies, monetary values — structured JSON
- **Sentiment analysis** — positive/negative/neutral/mixed label, 0–1 score, confidence, tone classification
- **Keyword extraction** — top 10 keyphrases

### RAG Q&A
- Semantic retrieval of relevant chunks
- Grounded answers — LLM instructed to cite sources and refuse out-of-scope questions
- Source citations with similarity scores and page numbers
- Query history with token usage and latency tracking

### Platform
- JWT authentication with access + refresh token rotation
- File upload: PDF, DOCX, TXT, MD — up to 20 MB
- Supabase Storage with per-user path isolation
- PostgreSQL Row Level Security — users can never access each other's data
- Redis Q&A cache (1h TTL, per-document invalidation on delete)
- Rate limiting: 60 req/min general, 10 AI req/min per IP
- Per-user analytics: documents uploaded, queries made, tokens used, avg latency, cache hit rate
- Admin analytics: system-wide stats
- Sentry integration for production error tracking

---

## Tech Stack

**Backend**
- Python 3.11
- FastAPI 0.111 — async REST API framework
- SQLAlchemy 2.0 (async) — ORM with connection pooling
- Supabase — PostgreSQL + Storage + RLS
- Google Generative AI SDK — Gemini 1.5 Flash + text-embedding-004 (free tier, $0 cost)
- FAISS-CPU — vector similarity search
- Redis — async caching via aioredis
- python-jose — JWT handling
- passlib/bcrypt — password hashing
- structlog — structured JSON logging
- slowapi — rate limiting
- tenacity — retry logic for API calls
- pypdf, python-docx — document parsing
- tiktoken — accurate token counting

**Frontend**
- React 18
- TypeScript
- Vite — fast dev server + optimized builds
- Zustand — lightweight auth state
- TanStack Query — server state, caching, auto-refetch
- Axios — HTTP client with auto-refresh interceptor
- react-dropzone — drag-and-drop upload
- react-hot-toast — notifications
- date-fns — date formatting

**Infrastructure**
- Docker + Docker Compose — local full-stack dev
- Render — backend + Redis hosting
- Vercel — frontend hosting
- GitHub Actions — CI (tests + build)

---

## Project Structure

```
documind/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, middleware, lifespan
│   │   ├── api/routes/
│   │   │   ├── auth.py          # Register, login, refresh, /me
│   │   │   ├── documents.py     # Upload, list, get, analyze, delete
│   │   │   ├── query.py         # RAG Q&A + query history
│   │   │   └── analytics.py     # User stats + admin stats
│   │   ├── core/
│   │   │   ├── config.py        # Pydantic settings (env vars)
│   │   │   ├── security.py      # JWT + password utilities
│   │   │   └── logging.py       # structlog setup
│   │   ├── services/
│   │   │   ├── document_processor.py  # Text extraction + chunking
│   │   │   ├── rag_service.py         # FAISS build + retrieval
│   │   │   ├── ai_service.py          # LLM calls (summarize, NER, Q&A)
│   │   │   └── cache_service.py       # Redis caching
│   │   ├── models/models.py     # SQLAlchemy ORM models
│   │   ├── schemas/schemas.py   # Pydantic request/response schemas
│   │   └── db/database.py       # Async engine + Supabase client
│   ├── tests/
│   │   └── test_document_processor.py
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Router + providers
│   │   ├── pages/
│   │   │   ├── AuthPage.tsx     # Login + register
│   │   │   └── Dashboard.tsx    # Main workspace
│   │   ├── components/dashboard/
│   │   │   ├── DocumentViewer.tsx  # Analysis tabs + Q&A
│   │   │   ├── DocumentList.tsx    # Sidebar document list
│   │   │   ├── UploadZone.tsx      # Drag-drop uploader
│   │   │   └── StatsBar.tsx        # Usage metrics
│   │   ├── services/api.ts      # Axios instance + all API calls
│   │   └── store/authStore.ts   # Zustand auth state
│   ├── vercel.json
│   └── .env.example
├── scripts/
│   └── 001_init_schema.sql      # Full Postgres schema + RLS
├── infra/
│   └── render.yaml              # Render one-click deploy config
├── .github/workflows/ci.yml     # GitHub Actions CI
└── docker-compose.yml           # Full local stack
```

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node 20+
- Docker (optional, for Redis locally)
- Supabase account (free tier works)
- Google AI Studio API key (free) — [aistudio.google.com](https://aistudio.google.com/app/apikey)

### 1. Clone

```bash
git clone https://github.com/SalimTag/documind.git
cd documind
```

### 2. Supabase setup

1. Create a new project at [supabase.com](https://supabase.com)
2. Open the SQL Editor and run `scripts/001_init_schema.sql`
3. Create a Storage bucket named `documents` (set to private)
4. Copy your Project URL, anon key, service key, and DB connection string

### 3. Backend setup

```bash
cd backend
cp .env.example .env
# Edit .env — fill in SUPABASE_*, GOOGLE_API_KEY, DATABASE_URL, SECRET_KEY

python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt

uvicorn app.main:app --reload
# API running at http://localhost:8000
# Docs at http://localhost:8000/api/docs
```

### 4. Redis (optional but recommended)

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

Without Redis, DocuMind falls back to in-memory caching (not shared across workers, not persistent).

### 5. Frontend setup

```bash
cd frontend
cp .env.example .env
# VITE_API_URL can stay empty for local dev (Vite proxy handles it)

npm install
npm run dev
# App running at http://localhost:5173
```

### 6. Full stack with Docker Compose

```bash
cp backend/.env.example backend/.env
# Edit backend/.env

docker compose up --build
```

Access: `http://localhost:5173` (frontend) · `http://localhost:8000/api/docs` (API)

### 7. Run tests

```bash
cd backend
pytest tests/ -v
```

---

## Deployment

### Backend → Render

1. Push repo to GitHub
2. Go to [render.com](https://render.com) → New → Blueprint
3. Connect your repo — Render reads `infra/render.yaml` automatically
4. Set environment variables in the Render dashboard:
   - `GOOGLE_API_KEY`
   - `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`
   - `DATABASE_URL`
5. Deploy — Redis service is created automatically

### Frontend → Vercel

```bash
cd frontend
npx vercel --prod
```

Or connect the GitHub repo in the Vercel dashboard. Set `VITE_API_URL` to your Render backend URL.

### Environment variables summary

| Variable | Where | Required |
|---|---|---|
| `SECRET_KEY` | Backend | Yes — generate with `openssl rand -hex 32` |
| `GOOGLE_API_KEY` | Backend | Yes — free from [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `SUPABASE_URL` | Backend | Yes |
| `SUPABASE_ANON_KEY` | Backend | Yes |
| `SUPABASE_SERVICE_KEY` | Backend | Yes |
| `DATABASE_URL` | Backend | Yes — `postgresql+asyncpg://...` |
| `REDIS_URL` | Backend | Recommended |
| `SENTRY_DSN` | Backend | Optional |
| `VITE_API_URL` | Frontend | Production only |

---

## API Reference

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/register` | — | Create account |
| POST | `/api/v1/auth/login` | — | Get tokens |
| POST | `/api/v1/auth/refresh` | — | Rotate access token |
| GET | `/api/v1/auth/me` | JWT | Current user profile |
| POST | `/api/v1/documents/upload` | JWT | Upload document (async processing) |
| GET | `/api/v1/documents/` | JWT | List documents (paginated) |
| GET | `/api/v1/documents/{id}` | JWT | Document metadata + status |
| GET | `/api/v1/documents/{id}/analysis` | JWT | Full AI analysis |
| DELETE | `/api/v1/documents/{id}` | JWT | Delete document + cleanup |
| POST | `/api/v1/query/` | JWT | RAG Q&A |
| GET | `/api/v1/query/history` | JWT | Query history |
| GET | `/api/v1/analytics/me` | JWT | Personal usage stats |
| GET | `/api/v1/analytics/admin` | Admin JWT | System-wide analytics |

Full interactive docs: `http://localhost:8000/api/docs`

---

## What This Demonstrates

This project was built to show real engineering skill — not tutorial-level demos.

**Backend engineering**
- Async FastAPI with proper service separation (no "god files")
- JWT auth with access + refresh token rotation
- PostgreSQL RLS — security at the data layer, not just the API layer
- Background task pipeline with status tracking
- Connection pooling, structured logging, global error handling

**AI system design**
- RAG pipeline: chunking → embeddings → FAISS → retrieval → grounded generation
- Hierarchical (map-reduce) summarization for large documents
- Structured JSON prompting with response validation
- Cost controls: Gemini free tier ($0), token limits, Redis caching, rate limiting

**Product thinking**
- Upload UX: immediate 202 response, background processing, polling
- Cache hit rate tracked in analytics (shows cost awareness)
- Per-user data isolation at DB + storage layer
- Graceful degradation (Redis optional, cache falls back to memory)

---

## Author

**Salim** — CS Graduate, Al Akhawayn University  
Backend Engineering · AI Integration · FinTech

- GitHub: [@SalimTag](https://github.com/SalimTag)
- LinkedIn: [linkedin.com/in/salim](https://linkedin.com)

---

## License

MIT — see [LICENSE](LICENSE)

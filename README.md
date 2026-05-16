# DocuMind — AI Document Intelligence Platform

> **Transform documents into structured intelligence.** A full-stack RAG application that analyzes PDFs, DOCXs, and TXTs using Google Gemini 1.5 Flash and FAISS vector indexing.

[![Production Frontend](https://img.shields.io/badge/Production-Live-61DAFB?style=for-the-badge&logo=vercel)](https://documind-frontend-bsaovr054-storsterx89s-projects.vercel.app)
[![Production API](https://img.shields.io/badge/API-Live-009688?style=for-the-badge&logo=fastapi)](https://documind-api-fq31.onrender.com/health)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![Supabase](https://img.shields.io/badge/Supabase-PostgreSQL-3ECF8E?style=for-the-badge&logo=supabase)](https://supabase.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

---

## 🔗 Live Demo

| Service | URL |
|---------|-----|
| 🌐 Frontend (Vercel) | [documind-frontend.vercel.app](https://documind-frontend-bsaovr054-storsterx89s-projects.vercel.app) |
| ⚙️ API Docs (Swagger) | [documind-api.onrender.com/api/docs](https://documind-api-fq31.onrender.com/api/docs) |

---

## 🧠 What is DocuMind?

DocuMind is an AI-powered application built for **deep document interrogation**. Instead of simple text extraction, it implements a **Retrieval-Augmented Generation (RAG)** pipeline that lets users have grounded, cited conversations with their documents.

Whether you're analyzing contracts, research papers, or internal reports — DocuMind extracts meaning, answers questions, and surfaces intelligence in seconds.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🔍 **RAG Q&A Engine** | Ask natural language questions and receive accurate, cited answers grounded in your documents |
| 📝 **Smart Summarization** | Hierarchical map-reduce summarization for large files (15+ chunks) |
| 🏷️ **Named Entity Recognition** | Auto-extract people, organizations, dates, locations, and monetary values |
| 📊 **Sentiment Analysis** | Multi-dimensional emotional tone and sentiment distribution across document content |
| 🔑 **Keyword Extraction** | Surface the most relevant keywords and themes automatically |
| 🕐 **Query History** | Full history of every question asked, with cached responses for instant retrieval |

---

## 🏗️ System Architecture

```mermaid
graph TD
    User((User)) -->|HTTPS/JWT| FE[React Frontend\nVercel]
    FE -->|REST API + WebSocket| BE[FastAPI Backend\nRender]

    subgraph "Backend Services"
        BE -->|Async Processing| DP[Document Processor]
        BE -->|Semantic Retrieval| RS[RAG Service]
        RS -->|Vector Index| FAISS[FAISS-CPU]
    end

    subgraph "Data Layer"
        BE -->|SQLAlchemy ORM| PG[(Supabase PostgreSQL)]
        DP -->|Object Storage| S3[(Supabase Storage)]
        BE -->|Cache + Pub/Sub| RD[(Redis - 1h TTL)]
    end

    subgraph "AI Intelligence"
        BE -->|LLM + Embeddings| GM[Google Gemini 1.5 Flash\ntext-embedding-004]
    end
```

### Engineering Highlights

- **🔐 Authorization** — Authorization is enforced **in the application layer** (every route fetches documents via a `_get_user_document` ownership check). The Supabase database has Row Level Security policies enabled, but they are **not currently the primary boundary**: the backend uses the Supabase service-role key + a SQLAlchemy connection that both bypass RLS. RLS policies act as a defense-in-depth layer, not the sole control.
- **⚡ Performance** — Redis caching with 1h TTL for Q&A responses reduces LLM latency and API costs significantly. FAISS indexes are LRU-cached in memory across queries.
- **🔄 Reliability** — FastAPI `BackgroundTasks` provides non-blocking document upload, with real-time progress streamed to the frontend over WebSockets backed by Redis pub/sub.
- **🎯 Accuracy** — Sentence-aware chunking (800 tokens + 100 overlap) preserves semantic context across chunk boundaries.

---

## 💻 Tech Stack

### Frontend
![React](https://img.shields.io/badge/React_18-20232A?logo=react&logoColor=61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-007ACC?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite&logoColor=white)
![Zustand](https://img.shields.io/badge/Zustand-orange)
![TanStack Query](https://img.shields.io/badge/TanStack_Query-FF4154?logo=reactquery&logoColor=white)

> The UI is styled with plain CSS-in-JS (inline styles) and a small `LandingPage.css` file. There is no Tailwind, no design-system library, and no CSS framework runtime in production.

### Backend
![Python](https://img.shields.io/badge/Python_3.11-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2.0-red)
![Pydantic](https://img.shields.io/badge/Pydantic_v2-E92063?logo=pydantic&logoColor=white)

### Infrastructure & Data
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)
![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?logo=supabase&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Render](https://img.shields.io/badge/Render-46E3B7?logo=render&logoColor=white)
![Vercel](https://img.shields.io/badge/Vercel-000000?logo=vercel&logoColor=white)

### AI / ML
![Google Gemini](https://img.shields.io/badge/Gemini_1.5_Flash-4285F4?logo=google&logoColor=white)
![FAISS](https://img.shields.io/badge/FAISS_CPU-Vector_Search-blueviolet)

---

## 🚀 Getting Started

### Prerequisites

- Python 3.11+ and Node 20+
- [Google AI Studio API Key](https://aistudio.google.com/) (free tier available)
- [Supabase Project](https://supabase.com/) (Postgres + Storage)

### Local Development (Docker)

```bash
# 1. Clone the repository
git clone https://github.com/SalimTag/documind.git
cd documind

# 2. Set up environment variables
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
# Fill in your API keys in both .env files

# 3. Launch the full stack
docker compose up --build
```

The app will be available at `http://localhost:5173` with the API at `http://localhost:8000`.

### Environment Variables

#### Backend (`backend/.env`)
```env
# Security
SECRET_KEY=your-32-byte-hex-secret
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
ALLOWED_ORIGINS=["http://localhost:5173"]

# Database (Supabase)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJhbGciOi...                    # public key for client SDKs
SUPABASE_SERVICE_KEY=eyJhbGciOi...                 # server-only, full DB access
DATABASE_URL=postgresql+asyncpg://user:password@host/db

# Storage
SUPABASE_BUCKET=documents
MAX_FILE_SIZE_MB=20
ALLOWED_EXTENSIONS=["pdf","txt","docx","md"]

# AI
GOOGLE_API_KEY=your_google_ai_studio_key
GEMINI_CHAT_MODEL=gemini-1.5-flash
GEMINI_EMBEDDING_MODEL=text-embedding-004

# RAG
CHUNK_SIZE=800
CHUNK_OVERLAP=100
MAX_CHUNKS_PER_DOC=200
RAG_TOP_K=6
RAG_SIMILARITY_THRESHOLD=0.70

# Redis (caching + WebSocket pub/sub)
REDIS_URL=redis://localhost:6379
CACHE_TTL_SECONDS=3600

# Quotas (no billing)
FREE_DOC_LIMIT=10                                  # Set to 0 to disable
```

> **Note:** `SUPABASE_ANON_KEY` and `SUPABASE_SERVICE_KEY` are two different keys from the same Supabase project (Settings → API). Don't confuse them — the service key bypasses RLS and must never reach the browser.

#### Frontend (`frontend/.env`)
```env
VITE_API_URL=http://localhost:8000/api/v1
```

---

## ☁️ Production Deployment

See [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) for the full Render + Vercel walkthrough, including the env var matrix and post-deploy smoke tests.

---

## 📁 Project Structure

```
documind/
├── backend/
│   ├── app/
│   │   ├── api/           # FastAPI route handlers
│   │   ├── core/          # Config, security, dependencies
│   │   ├── models/        # SQLAlchemy ORM models
│   │   ├── schemas/       # Pydantic v2 schemas
│   │   ├── services/      # RAG engine, document processor, cache, quotas
│   │   └── main.py
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/    # Reusable UI components
│   │   ├── pages/         # Route-level views
│   │   ├── store/         # Zustand state management
│   │   ├── hooks/         # WebSocket + TanStack Query hooks
│   │   └── services/      # API client
│   └── package.json
└── docker-compose.yml
```

---

## 💰 Pricing

DocuMind is currently free to self-host. There is **no payment integration** in this codebase. A single environment variable, `FREE_DOC_LIMIT` (default `10`), caps the number of documents per account; setting it to `0` disables the cap entirely.

---

## 🛣️ Roadmap

- [ ] Multi-document cross-querying
- [ ] Team workspaces & collaboration
- [ ] Webhook support for document events
- [ ] OpenAI / Anthropic model switcher
- [ ] Browser extension for web page analysis
- [ ] Self-hosted / open-source edition

---

## 🤝 Contributing

Contributions are welcome! Please open an issue first to discuss what you'd like to change.

1. Fork the repo
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit your changes: `git commit -m 'Add amazing feature'`
4. Push and open a Pull Request

---

## ⚖️ License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

## 👤 Author

**Salim Taghzouti** — Full-Stack AI Engineer

[![GitHub](https://img.shields.io/badge/GitHub-@SalimTag-181717?logo=github)](https://github.com/SalimTag)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin)](https://linkedin.com/in/salim)

---

<p align="center">Built with FastAPI, React, and Google Gemini</p>

# DocuMind — Production-Grade AI Document Intelligence & RAG SaaS

> **Transform documents into structured intelligence.** A full-stack RAG application with PostgreSQL + pgvector (HNSW), batched LLM re-ranking, multi-provider routing, and an evaluation harness with explicit methodology limits.

[![Production Frontend](https://img.shields.io/badge/Production-Live-61DAFB?style=for-the-badge&logo=vercel)](https://documind-frontend-bsaovr054-storsterx89s-projects.vercel.app)
[![Backend](https://img.shields.io/badge/Backend-Cloud_Run-4285F4?style=for-the-badge&logo=googlecloud&logoColor=white)](docs/DEPLOYMENT.md)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![pgvector](https://img.shields.io/badge/pgvector-HNSW_Cosine-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-Multi--Provider-purple?style=for-the-badge)](https://litellm.ai)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=for-the-badge&logo=react)](https://react.dev)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-007ACC?style=for-the-badge&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)

---

## 🔗 Live Deployments & Instant Demo

| Service | Access Link | Notes |
|:---|:---|:---|
| 🌐 **Web App (Vercel)** | [documind-frontend.vercel.app](https://documind-frontend-bsaovr054-storsterx89s-projects.vercel.app) | Production SPA with Interactive Benchmark Modal |
| 🚀 **Instant Demo Mode** | [Live Demo Access](https://documind-frontend-bsaovr054-storsterx89s-projects.vercel.app/demo) | 1-click recruiter demo with preloaded enterprise contracts |
| ⚙️ **Backend deployment** | [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md) | Cloud Run deployment and cutover guide |
| 📊 **Evaluation Methodology** | [`docs/EVALUATION_REPORT.md`](docs/EVALUATION_REPORT.md) | Audit status, formulas, legacy artifact, and limitations |

---

## 🧠 What is DocuMind?

DocuMind is an enterprise-grade AI SaaS application built for **rigorous document interrogation**. Unlike standard naive RAG wrappers, DocuMind addresses the real engineering bottlenecks of retrieval systems:

1. **Durable Vector Persistence**: Vector embeddings live in PostgreSQL with `pgvector` HNSW indexes. Application queries join documents and filter by authenticated owner.
2. **Two-Stage Retrieval Pipeline**: Combines dense vector and PostgreSQL full-text candidates using RRF, then optionally applies one batched LLM relevance-scoring call.
3. **Multi-Provider LLM Layer**: Standardized across LiteLLM to seamlessly route between Google Gemini, OpenAI, Anthropic, Groq, and local Ollama instances with zero vendor lock-in.
4. **Adaptive Rate Limiting & Backoff**: Concurrency semaphores with regex-driven `SmartWait` backoff that respects provider quotas (e.g. Google AI Studio 429 retry-after windows).
5. **Multi-Document Cross-Querying**: Unified retrieval across multiple workspace documents simultaneously with per-source citation badges and chunk-level provenance.
6. **Evaluation Harness**: Automated in-memory comparisons for Precision@K, Recall@K, keyword-based MRR, lexical groundedness, and phrase-based refusal detection.

---

## 📊 RAG evaluation status

The repository contains a 15-case historical artifact, but the audit invalidated its aggregate values after correcting the Precision@K denominator. The stored 33.3% refusal accuracy also contradicts any claim of reliable abstention. See [`docs/EVALUATION_REPORT.md`](docs/EVALUATION_REPORT.md) for the formulas, limitations, and legacy values.

The harness is in-memory only: it compares dense retrieval with a larger dense candidate pool plus LLM reranking. It does not exercise pgvector, HNSW, PostgreSQL FTS, RRF, tenant filters, or multi-document balancing.

```bash
cd backend
python -m app.eval.runner --cases 3
python -m app.eval.runner
```

---

## 🏗️ System Architecture

```mermaid
graph TD
    subgraph Client["Frontend (React 18 + TS + Vite)"]
        UI[Document Viewer & Chat UI]
        MDV[MultiDocViewer / Cross-Query]
        MODAL[EvalModal / Live Benchmark Viewer]
        DEMO[Demo Mode Controller]
    end

    subgraph API["FastAPI Backend Gateway (Cloud Run)"]
        ROUTER[API Router / SlowAPI Rate Limiting]
        AUTH[JWT Auth + Demo Guardrails]
        LIMITER[LLM Limiter & SmartWait Backoff]
    end

    subgraph Retrieval["RAG Engine (app/services)"]
        PROC[Document Processor & Chunking]
        EMB[Matryoshka Embedding 768d]
        SEARCH[Vector Search Engine]
        RERANK[Two-Stage LLM Reranker]
    end

    subgraph Storage["Persistent Data Tier (Supabase)"]
        PG[(PostgreSQL + pgvector HNSW)]
        CHUNKS[(document_chunks table)]
        STORE[(Supabase Storage Bucket)]
        REDIS[(Redis Query Cache)]
    end

    subgraph Providers["Multi-Provider AI Gateway (LiteLLM)"]
        GEMINI[Google Gemini 3.5 Flash Lite]
        OPENAI[OpenAI / GPT-4o Optional]
        OLLAMA[Local Ollama Optional]
    end

    UI -->|HTTPS / JWT| ROUTER
    DEMO -->|Guest Token| ROUTER
    ROUTER --> AUTH
    AUTH --> PROC
    AUTH --> SEARCH

    PROC -->|Upload PDF/DOCX/TXT| STORE
    PROC -->|800t Chunking + Overlap| EMB
    EMB -->|Matryoshka 768d + L2 Norm| CHUNKS

    SEARCH -->|Cosine Similarity <=>| PG
    SEARCH --> RERANK
    RERANK -->|Score Candidates 1..10| LIMITER
    LIMITER --> GEMINI
    LIMITER --> OPENAI
    LIMITER --> OLLAMA
    SEARCH -->|Cache Hit| REDIS
```

---

## 🔬 Two-Stage Retrieval & Re-ranking Pipeline

```mermaid
flowchart LR
    A["User Query"] --> B["gemini-embedding-001\n(Matryoshka 768d + L2 Norm)"]
    B --> C["pgvector HNSW Index\n(Cosine Distance <=>)"]
    C -->|Top 10-15 Candidates| D["Two-Stage Reranker\n(LLM Cross-Relevance Scoring)"]
    D -->|Filtered & Re-ordered Top 5| E["Grounded Context Assembler\n(Provenance & Source Citations)"]
    E --> F["gemini-3.5-flash-lite\n(Answer Generation)"]
    F --> G["Cited Response with Metadata"]
```

### Engineering Decisions:
- **HNSW over IVFFlat**: HNSW delivers significantly higher recall and queries-per-second (QPS) without requiring periodic index retraining after inserts.
- **Matryoshka Dimensionality Reduction (768d)**: Google's `gemini-embedding-001` natively supports output dimensionality truncation down to 768 dimensions while preserving >99% semantic fidelity, halving database vector footprint and accelerating index scans.
- **Strict Unit Normalization**: Embeddings are \(L_2\) normalized on creation, enabling Euclidean distance, cosine distance, and inner product to be mathematically monotonic.

---

## ✨ Core Features

| Feature | Description |
|:---|:---|
| 🔍 **Two-Stage RAG Q&A** | Hybrid RRF candidate retrieval + batched LLM relevance scoring with inline citations |
| 📚 **Multi-Document Querying** | Query multiple documents simultaneously across a workspace (`document_ids: [...]`) with per-source attribution |
| 🛡️ **Tenant-filtered retrieval** | Every dense and lexical retrieval query joins the document owner and filters by authenticated user ID |
| 🎭 **Instant Public Demo Mode** | Short-lived demo tokens, read-only UI/API writes, per-IP query limits, and seeded documents |
| 📈 **In-App Benchmark Viewer** | Displays stored results and warns when an artifact predates the current methodology |
| 📝 **Document Summarization** | Hierarchical map-reduce summarization handles large multi-page files effortlessly |
| 🏷️ **Entity & Theme Extraction** | Automatic extraction of people, organizations, dates, and domain entities |
| ⚡ **Redis Cache Layer** | Exact-query cache with 1h TTL saves LLM costs and provides instant responses |
| 💳 **Stripe Subscription Billing** | Tiered usage limits with Stripe Webhook integration for automated plan upgrades |

---

## 💻 Tech Stack

### Frontend
- **Framework**: React 18 with TypeScript 5
- **Build Tool**: Vite 5
- **Styling**: component-scoped inline styles and shared CSS, with Lucide Icons available
- **State & Data**: Zustand + TanStack React Query v5
- **Notifications**: React Hot Toast

### Backend
- **Framework**: FastAPI (Python 3.11+)
- **ORM & Database**: SQLAlchemy 2.0 (AsyncIO) with `asyncpg`
- **Vector Database**: PostgreSQL with `pgvector` (HNSW indexing)
- **AI Gateway**: LiteLLM (Multi-provider abstraction for Gemini, OpenAI, Anthropic, Ollama)
- **Primary LLM**: Google Gemini 3.5 Flash Lite (`gemini/gemini-3.5-flash-lite`)
- **Primary Embeddings**: Google Gemini Embedding 001 (`gemini/gemini-embedding-001`, 768d)
- **Resilience**: Tenacity with regex-based `SmartWait` backoff + SlowAPI rate limiting
- **Cache**: Redis 7

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11+ and Node.js 20+
- [Google AI Studio API Key](https://aistudio.google.com/) (Free tier)
- [Supabase Project](https://supabase.com/) with pgvector enabled

### Local Setup (Without Docker)

#### 1. Backend
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env with GOOGLE_API_KEY and Supabase / database credentials

# Run database migrations / initialization
python -m app.db.database

# Start backend server
uvicorn app.main:app --reload --port 8000
```

#### 2. Frontend
```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

App runs at `http://localhost:5173`, API docs at `http://localhost:8000/api/docs`.

### Full-Stack Docker Setup
```bash
docker compose up --build
```

---

## 🧪 Running the Test & Benchmark Suite

### Backend unit and integration tests
```bash
cd backend
pytest tests/ -q --cov=app --cov-report=term-missing
```

### Full 15-Case Empirical Evaluation Harness
```bash
cd backend

# In-memory evaluation; provider credentials are required
python -m app.eval.runner
```

Outputs formatted ASCII comparison table, writes `docs/EVALUATION_REPORT.md`, and updates `backend/benchmark_report.json`.

---

## 📁 Repository Layout

```
documind/
├── .github/workflows/
│   └── ci.yml                 # Automated backend test, lint & frontend build
├── backend/
│   ├── app/
│   │   ├── api/routes/        # Auth, documents, query, analytics, demo, billing
│   │   ├── core/              # Config, security, rate limiter, logging
│   │   ├── db/                # Database connection, init, pgvector setup
│   │   ├── eval/              # Scientific benchmark harness, dataset, evaluator, runner
│   │   ├── models/            # SQLAlchemy models (User, Document, DocumentChunk)
│   │   ├── schemas/           # Pydantic v2 schemas
│   │   ├── services/          # RAG engine, LiteLLM client, document processor, demo service
│   │   └── main.py            # FastAPI entrypoint
│   ├── tests/                 # Pytest unit and integration tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/        # EvalModal, MultiDocViewer, DocumentChat, etc.
│   │   ├── pages/             # LandingPage, DashboardPage, DemoPage, etc.
│   │   └── lib/               # Axios API client, auth utilities
│   ├── package.json
│   └── vite.config.ts
├── docs/
│   ├── EVALUATION_REPORT.md   # Ground-truth benchmark report with real numbers
│   └── benchmark_report.json  # Raw evaluation dataset & metrics
└── docker-compose.yml
```

---

## ⚖️ License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

---

## 👤 Author

**Salim Taghzouti** — Full-Stack AI Engineer  
[![GitHub](https://img.shields.io/badge/GitHub-@SalimTag-181717?logo=github)](https://github.com/SalimTag)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin)](https://linkedin.com/in/salim)

# DocuMind — Deployment Guide

> Production deployment on **Render** (backend + Redis) + **Vercel** (frontend).
> AI powered by **Google Gemini 1.5 Flash** (free tier — $0 operating cost).

---

## Prerequisites

- [x] GitHub repository with DocuMind code pushed
- [x] Supabase project created (PostgreSQL + Storage)
- [x] Google AI Studio API key (free) → [aistudio.google.com](https://aistudio.google.com/app/apikey)
- [x] Stripe account (for billing)
- [ ] Render account → [render.com](https://render.com)
- [ ] Vercel account → [vercel.com](https://vercel.com)

---

## 1. Database Setup (Supabase)

Run the migration scripts in your Supabase SQL editor:

```sql
-- Step 1: Initial schema
-- Copy contents of scripts/001_init_schema.sql

-- Step 2: Billing columns (Phase 3)
-- Copy contents of backend/migrations/002_add_billing.sql
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
5. Fill in the environment variables marked `sync: false`:

| Variable | Where to get it |
|----------|----------------|
| `SUPABASE_URL` | Supabase → Settings → API → URL |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API → `anon` key |
| `SUPABASE_SERVICE_KEY` | Supabase → Settings → API → `service_role` key |
| `DATABASE_URL` | Supabase → Settings → Database → Connection string (URI) |
| `GOOGLE_API_KEY` | [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `STRIPE_SECRET_KEY` | Stripe → Developers → API keys → Secret key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe → Developers → API keys → Publishable key |
| `STRIPE_WEBHOOK_SECRET` | See step 3c below |
| `STRIPE_PRICE_ID_PRO` | See step 3b below |
| `SENTRY_DSN` | Optional — [sentry.io](https://sentry.io) |

### Option B: Manual

1. **New Web Service** → Docker → Root: `backend`
2. **New Redis** → Connect to web service via internal URL
3. Set all env vars from the table above

### 3b. Stripe Product Setup

1. Go to [Stripe Dashboard](https://dashboard.stripe.com) → **Products** → **Add Product**
2. Name: `DocuMind Pro`
3. Price: `$12.00/month` (recurring)
4. Copy the **Price ID** (starts with `price_...`) → set as `STRIPE_PRICE_ID_PRO`

### 3c. Stripe Webhook Setup

1. Go to Stripe → **Developers** → **Webhooks** → **Add endpoint**
2. URL: `https://documind-api.onrender.com/api/v1/billing/webhook`
3. Events to listen for:
   - `checkout.session.completed`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_failed`
4. Copy the **Signing secret** (starts with `whsec_...`) → set as `STRIPE_WEBHOOK_SECRET`

### 3d. Test Stripe Locally

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local backend
stripe listen --forward-to localhost:8000/api/v1/billing/webhook

# In another terminal, trigger test events
stripe trigger checkout.session.completed
```

### 3e. Verify Backend

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
4. Update `FRONTEND_URL` on Render to the new domain

---

## 6. GitHub Actions CI

CI runs automatically on push to `main`/`develop` and on PRs.

The workflow runs **3 parallel jobs**:

| Job | What it does |
|-----|-------------|
| `backend` | ruff lint → AST syntax check → pytest (with Redis service) |
| `frontend` | TypeScript check → Vite production build → bundle size report |
| `docker` | Full Docker image build (after backend passes) |

### Required CI Secrets

Go to GitHub → Repo Settings → Secrets and Variables → Actions:

| Secret | Value |
|--------|-------|
| `GOOGLE_API_KEY` | Your Gemini API key (for integration tests, if enabled) |
| `STRIPE_SECRET_KEY` | Stripe test-mode secret key |

> No secrets are required for unit tests — all external APIs are mocked.

---

## 7. Post-Deploy Smoke Test Checklist

Run through this after every deployment:

- [ ] Backend `/health` returns 200
- [ ] Frontend loads at Vercel URL
- [ ] **Register** a new user → verify JWT tokens returned
- [ ] **Upload** a PDF document → returns 202
- [ ] **Watch processing** → WebSocket shows progress stages
- [ ] **Wait for "Ready!"** status
- [ ] **Ask a question** about the document → expect answer with source citations
- [ ] **Verify sources** — answer references `[Source N]` labels
- [ ] **Check billing** — Free tier badge shows in navbar
- [ ] **Hit free tier limit** — upload 4th document → expect 429 with upgrade prompt
- [ ] **Stripe checkout** — click Upgrade, verify redirect to Stripe
- [ ] **Webhook** — complete test payment, verify user becomes Pro
- [ ] **Pro user** — upload unlimited documents, unlimited queries

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
│  ├── Billing     │     │   Storage)   │
│  └── WebSocket   │     └──────────────┘
│                  │
│  ├── FAISS       │     ┌──────────────┐
│  └── Redis ──────│────►│ Render Redis │
│      (cache +    │     │ (pub/sub)    │
│       pub/sub)   │     └──────────────┘
└──────────────────┘
         │                ┌──────────────┐
         ├───────────────►│  Google AI   │
         │  Gemini API    │  (free tier) │
         │                └──────────────┘
         │                ┌──────────────┐
         └───────────────►│   Stripe     │
           webhooks       │  (billing)   │
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

### Stripe webhook failing
- Check the webhook signing secret matches
- Verify the webhook URL includes `/api/v1/billing/webhook`
- Test locally with `stripe listen --forward-to localhost:8000/api/v1/billing/webhook`

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
| `Stripe webhook 400` | Ensure `STRIPE_WEBHOOK_SECRET` starts with `whsec_` |
| `CORS error` | Add frontend domain to `ALLOWED_ORIGINS` |

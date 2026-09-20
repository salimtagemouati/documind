# Deploy DocuMind on Google Cloud Run

Target architecture: Vercel frontend, Cloud Run FastAPI backend, Supabase PostgreSQL/storage, and an external Redis service. Cloud Run replaces the previous Render backend.

Official references:

- [Deploy a FastAPI service](https://cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service)
- [Configure Secret Manager secrets](https://cloud.google.com/run/docs/configuring/services/secrets)
- [Cloud Run WebSockets](https://cloud.google.com/run/docs/triggering/websockets)
- [Minimum instances](https://cloud.google.com/run/docs/configuring/min-instances)

## 1. Prerequisites

- Google Cloud CLI installed and authenticated.
- A Google Cloud project with billing enabled.
- Supabase migrations applied, including the 768-dimensional pgvector migration and HNSW index.
- `backend/.env` present locally and ignored by Git.
- A production Redis URL. Cloud Run can start without Redis, but cache and cross-instance WebSocket pub/sub degrade.
- A dedicated Cloud Run service account.

Create the service account and grant only the permissions it needs:

```bash
gcloud iam service-accounts create documind-runner \
  --display-name="DocuMind Cloud Run runtime"

gcloud projects add-iam-policy-binding "$GOOGLE_CLOUD_PROJECT" \
  --member="serviceAccount:documind-runner@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

The deployer also needs Cloud Run Admin, Service Account User, Cloud Build permissions, and permission to create Secret Manager versions.

## 2. Prepare local configuration

Copy `backend/.env.example` to `backend/.env` and fill it locally. Required entries include:

- application signing secret;
- Supabase URL, database URL, anonymous key, and service-role key;
- Google provider key;
- frontend origin and URL;
- production Redis URL;
- optional billing and monitoring settings.

Do not paste secret values into `gcloud` arguments, CI variables, shell history, or tracked YAML. The deployment script reads `backend/.env` and streams each secret value to Secret Manager over stdin. Secret references, not values, are attached to Cloud Run.

## 3. Validate, then deploy

Choose the Cloud Run region closest to the Supabase database, because database round trips usually dominate API latency. `europe-west1` is only the script default and should be changed when the database is elsewhere.

```bash
cd backend

.venv/bin/python ../scripts/deploy_cloud_run.py \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region europe-west1 \
  --service-account "documind-runner@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com"
```

The first invocation validates configuration and prints a secret-free plan. Add `--apply` only after reviewing it:

Validation rejects template values, SQLite database URLs, local-only frontend origins, and a localhost Redis URL before any secret version or Cloud Run revision is created.

```bash
.venv/bin/python ../scripts/deploy_cloud_run.py \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region europe-west1 \
  --service-account "documind-runner@$GOOGLE_CLOUD_PROJECT.iam.gserviceaccount.com" \
  --apply
```

The deployment uses:

- one vCPU and 1 GiB memory;
- one minimum instance to reduce cold-start latency;
- startup CPU boost;
- instance-based CPU allocation for processing and WebSocket activity;
- concurrency 40, maximum 10 instances;
- 60-minute request timeout and best-effort session affinity for WebSockets;
- one asynchronous Uvicorn worker per container.

These settings favor responsiveness and reliable background document processing over the lowest possible cost. Tune them using Cloud Run latency, instance, CPU, memory, and billable-time metrics.

## 4. Cut over the frontend

After the Cloud Run health check succeeds, set the Vercel production variable:

```text
VITE_API_URL=https://YOUR_CLOUD_RUN_HOST/api/v1
```

Redeploy the frontend, then update the backend `ALLOWED_ORIGINS` and `FRONTEND_URL` values if the frontend domain changed. Do not remove the Render service until all checks below pass.

## 5. Verify before removing Render

```bash
gcloud run services describe documind-api \
  --project "$GOOGLE_CLOUD_PROJECT" \
  --region europe-west1
```

Then verify manually:

1. `/health` responds successfully on the Cloud Run URL.
2. Registration, login, token refresh, and the public demo work.
3. Uploading a document reaches `ready` and progress reconnects after a forced WebSocket disconnect.
4. Single- and multi-document questions return grounded citations.
5. Demo upload, delete, and billing writes remain forbidden; the 11th demo query from one IP is rate-limited.
6. Stripe webhooks target the new Cloud Run endpoint and pass signature verification.
7. Vercel uses the Cloud Run API URL and browser CORS succeeds.
8. Cloud Run logs contain no secret values or raw provider exceptions.

Keep Render available for rollback until production traffic and error rates are stable. The deleted `infra/render.yaml` remains recoverable from Git history.

## Cloud Run caveats

- WebSockets are supported, but each connection is still an HTTP request subject to the configured timeout. The frontend reconnect logic is therefore required.
- A minimum instance reduces cold starts but adds idle cost.
- Best-effort session affinity is not a substitute for Redis-backed shared state.
- The container filesystem is ephemeral; benchmark caches and uploaded documents must not rely on local persistence.

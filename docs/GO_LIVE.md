# DocuMind live preview — 22 October 2026

DocuMind can now run through a temporary public HTTPS URL using the existing
Gemini credential and this Mac. No new account, hosted database or paid resource
was required. Permanent, unattended cloud hosting is not configured.

## Open and operate

The macOS login service is installed and running. For its current URL, run
`backend/.venv/bin/python scripts/preview_service.py status`. The commands below
also support a manual preview after removing the login service.

From the repository root, with Docker/OrbStack running:

```sh
backend/.venv/bin/python scripts/preview.py start --share
backend/.venv/bin/python scripts/preview.py status
backend/.venv/bin/python scripts/preview.py stop
```

`status` reports the current public URL and local `http://127.0.0.1:8765` address.
Open the public URL, then choose **Explore Live Demo** for seeded read-only
samples, or **Create Account** to upload your own files. The preview has no payment
checkout. The free workspace holds three documents; deleting one frees a slot.

The launcher uses the installed backend virtualenv, Node/npm, Docker and
`cloudflared`. It builds React, starts the same-origin FastAPI server, and runs a
Cloudflare Quick Tunnel. Gemini Flash Lite is configured server-side in the
ignored backend environment file. Credentials are never included in the frontend.

The Mac must remain awake and connected, with Docker and the launcher running.
The installed per-user macOS login service restarts the launcher after exit and at login. Docker/OrbStack must also be running. Manage the service with `backend/.venv/bin/python scripts/preview_service.py status` or `remove`; reinstall with `install`. Use `remove` to stop it permanently, since the service restarts a manually stopped process.
The HTTPS URL changes when the tunnel restarts. Quick Tunnels are for previews,
not production uptime: [Cloudflare documentation](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/).
The launcher does not prevent system sleep or change the Mac's power settings.

## Persistence and boundaries

The dedicated `documind-preview-db` Docker container uses PostgreSQL/pgvector and
stores its database under ignored `backend/data/preview/postgres`. Originals,
private runtime secrets, state and logs are also under `backend/data/preview`.
Stopping the launcher preserves this directory and leaves the database container
available. Do not remove it unless the preview's data is intentionally being erased.
The inactive hosted Supabase project and portfolio website were not modified.

The API binds only to loopback; the tunnel exposes the app via HTTPS. Account
ownership checks apply to uploads, queries and deletion. API documentation is
hidden in this runtime, and missing API routes/assets/dotfiles return 404. A single
API process uses memory cache, progress and rate-limit fallbacks. These reset on
restart; shared Redis and durable ingestion are still needed for multi-instance
hosting. Provider quota and availability can still cause a visible failure with
retry; a successful run does not establish unlimited provider allowance.

## Verification

- 118 backend tests pass, with 61.55% coverage; seven frontend tests pass.
- Backend lint/type checks and frontend lint/production build pass.
- The complete real Gemini/pgvector test passed PDF, Markdown, adversarial TXT,
  DOCX tables, follow-up, refusal, page citations, cross-document synthesis,
  answer caching and deletion: [raw run](live_gemini_results.json).
- The actual public API was tested with synthetic documents, real generation,
  account isolation and deletion: [public preview evidence](verification/public-preview.json).

Earlier failed runs are preserved. Fixes include same-origin WebSockets, retained
file quotas rather than lifetime processing quotas, Gemini default sampling and
bounded retry of local asynchronous provider deadlines. No canned answer fallback
was added.

## Permanent cloud hosting later

The existing Cloud Run + Vercel + Supabase/Redis deployment path remains available
in [DEPLOYMENT.md](DEPLOYMENT.md). It requires authenticated hosting access,
approved spending, actual production database/storage/Redis configuration and a
reviewed migration plan. The private `backend/.env.production` still contains
placeholders for those services. Do not apply bootstrap SQL to a populated hosted
project. This preview does not depend on completing that cloud configuration.

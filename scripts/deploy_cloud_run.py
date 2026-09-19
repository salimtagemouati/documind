#!/usr/bin/env python3
"""Deploy DocuMind to Cloud Run without putting secret values in argv or Git."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
ENV_FILE = BACKEND_DIR / ".env"

REQUIRED_SECRETS = {
    "SECRET_KEY": "documind-secret-key",
    "SUPABASE_ANON_KEY": "documind-supabase-anon-key",
    "SUPABASE_SERVICE_KEY": "documind-supabase-service-key",
    "DATABASE_URL": "documind-database-url",
    "GOOGLE_API_KEY": "documind-google-api-key",
}

OPTIONAL_SECRETS = {
    "OPENAI_API_KEY": "documind-openai-api-key",
    "ANTHROPIC_API_KEY": "documind-anthropic-api-key",
    "GROQ_API_KEY": "documind-groq-api-key",
    "REDIS_URL": "documind-redis-url",
    "STRIPE_SECRET_KEY": "documind-stripe-secret-key",
    "STRIPE_WEBHOOK_SECRET": "documind-stripe-webhook-secret",
    "SENTRY_DSN": "documind-sentry-dsn",
}

NON_SECRET_DEFAULTS = {
    "ENVIRONMENT": "production",
    "DEBUG": "false",
    "SUPABASE_BUCKET": "documents",
    "LLM_PROVIDER": "gemini",
    "LLM_MODEL": "gemini/gemini-3.5-flash-lite",
    "EMBEDDING_MODEL": "gemini/gemini-embedding-001",
    "EMBEDDING_DIM": "768",
    "LLM_MAX_CONCURRENCY": "3",
    "RAG_TOP_K": "6",
    "RAG_INITIAL_TOP_K": "15",
    "RAG_SIMILARITY_THRESHOLD": "0.50",
    "ENABLE_RERANKING": "true",
    "ENABLE_HYBRID_SEARCH": "true",
}

PASSTHROUGH_NON_SECRETS = {
    "APP_NAME",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REFRESH_TOKEN_EXPIRE_DAYS",
    "ALLOWED_ORIGINS",
    "SUPABASE_URL",
    "MAX_FILE_SIZE_MB",
    "ALLOWED_EXTENSIONS",
    "OLLAMA_API_BASE",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "MAX_CHUNKS_PER_DOC",
    "RATE_LIMIT_REQUESTS",
    "RATE_LIMIT_WINDOW",
    "AI_RATE_LIMIT_REQUESTS",
    "AI_RATE_LIMIT_WINDOW",
    "CACHE_TTL_SECONDS",
    "STRIPE_PUBLISHABLE_KEY",
    "STRIPE_PRICE_ID_PRO",
    "STRIPE_FREE_DOC_LIMIT",
    "STRIPE_FREE_QUERY_LIMIT",
    "FRONTEND_URL",
}


def run(command: list[str], *, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=ROOT,
        input=stdin,
        text=True,
        check=True,
    )


def configured_project() -> str:
    result = subprocess.run(
        ["gcloud", "config", "get-value", "project"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    project = result.stdout.strip()
    if not project or project == "(unset)":
        raise RuntimeError("No Google Cloud project is configured")
    return project


def ensure_secret(project: str, secret_name: str, secret_value: str) -> str:
    describe = subprocess.run(
        ["gcloud", "secrets", "describe", secret_name, "--project", project],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if describe.returncode != 0:
        run(
            [
                "gcloud",
                "secrets",
                "create",
                secret_name,
                "--replication-policy=automatic",
                "--project",
                project,
            ]
        )
    version_result = subprocess.run(
        [
            "gcloud",
            "secrets",
            "versions",
            "add",
            secret_name,
            "--data-file=-",
            "--format=value(name)",
            "--project",
            project,
        ],
        cwd=ROOT,
        input=secret_value,
        capture_output=True,
        text=True,
        check=True,
    )
    return version_result.stdout.strip().rsplit("/", 1)[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=None)
    parser.add_argument("--region", default=os.environ.get("CLOUD_RUN_REGION", "europe-west1"))
    parser.add_argument("--service", default="documind-api")
    parser.add_argument("--service-account", required=True)
    parser.add_argument("--apply", action="store_true", help="Create secrets and deploy")
    args = parser.parse_args()

    if not ENV_FILE.exists():
        print("backend/.env is required and must remain untracked", file=sys.stderr)
        return 2

    values = {key: value for key, value in dotenv_values(ENV_FILE).items() if value}
    missing = sorted(key for key in REQUIRED_SECRETS if not values.get(key))
    missing.extend(key for key in ("SUPABASE_URL", "ALLOWED_ORIGINS", "FRONTEND_URL") if not values.get(key))
    if missing:
        print("Missing required backend/.env variables: " + ", ".join(missing), file=sys.stderr)
        return 2

    project = args.project or configured_project()
    secret_values = {
        env_name: (secret_name, values[env_name])
        for env_name, secret_name in {**REQUIRED_SECRETS, **OPTIONAL_SECRETS}.items()
        if values.get(env_name)
    }
    environment = {
        **NON_SECRET_DEFAULTS,
        **{key: values[key] for key in PASSTHROUGH_NON_SECRETS if values.get(key)},
    }

    print(
        f"Cloud Run plan: project={project}, region={args.region}, service={args.service}, "
        f"secrets={len(secret_values)}, min_instances=1"
    )
    if not args.apply:
        print("Validation complete. Re-run with --apply to create a revision.")
        return 0

    run(
        [
            "gcloud",
            "services",
            "enable",
            "run.googleapis.com",
            "cloudbuild.googleapis.com",
            "artifactregistry.googleapis.com",
            "secretmanager.googleapis.com",
            "--project",
            project,
        ]
    )

    secret_versions = {
        env_name: (secret_name, ensure_secret(project, secret_name, secret_value))
        for env_name, (secret_name, secret_value) in secret_values.items()
    }

    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as env_file:
        env_path = Path(env_file.name)
        for key, value in sorted(environment.items()):
            escaped = value.replace("'", "''")
            env_file.write(f"{key}: '{escaped}'\n")

    secret_bindings = ",".join(
        f"{env_name}={secret_name}:{version}"
        for env_name, (secret_name, version) in sorted(secret_versions.items())
    )
    try:
        run(
            [
                "gcloud",
                "run",
                "deploy",
                args.service,
                "--source",
                str(BACKEND_DIR),
                "--project",
                project,
                "--region",
                args.region,
                "--service-account",
                args.service_account,
                "--allow-unauthenticated",
                "--execution-environment=gen2",
                "--port=8080",
                "--cpu=1",
                "--memory=1Gi",
                "--concurrency=40",
                "--min-instances=1",
                "--max-instances=10",
                "--timeout=3600",
                "--cpu-boost",
                "--no-cpu-throttling",
                "--session-affinity",
                "--env-vars-file",
                str(env_path),
                "--update-secrets",
                secret_bindings,
                "--quiet",
            ]
        )
    finally:
        env_path.unlink(missing_ok=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

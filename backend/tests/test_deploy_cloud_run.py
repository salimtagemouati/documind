import importlib.util
from pathlib import Path


def _load_deploy_module():
    script_path = Path(__file__).parents[2] / "scripts" / "deploy_cloud_run.py"
    spec = importlib.util.spec_from_file_location("deploy_cloud_run", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cloud_run_validation_rejects_template_and_local_values():
    deploy = _load_deploy_module()
    values = {
        "SECRET_KEY": "REPLACE_ME",
        "SUPABASE_URL": "https://your-project.example.invalid",
        "SUPABASE_ANON_KEY": "REPLACE_ME",
        "SUPABASE_SERVICE_KEY": "REPLACE_ME",
        "DATABASE_URL": "sqlite+aiosqlite:///./dev.db",
        "GOOGLE_API_KEY": "REPLACE_ME",
        "ALLOWED_ORIGINS": "http://localhost:5173",
        "FRONTEND_URL": "http://127.0.0.1:4173",
        "REDIS_URL": "redis://localhost:6379",
    }

    invalid = deploy.invalid_configuration_keys(values)

    assert invalid == sorted(values)


def test_cloud_run_validation_accepts_production_shaped_values():
    deploy = _load_deploy_module()
    values = {
        "SECRET_KEY": "a-production-signing-secret-value",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_ANON_KEY": "anon-value",
        "SUPABASE_SERVICE_KEY": "service-value",
        "DATABASE_URL": "postgresql+asyncpg://user:password@db.pooler.supabase.com:5432/postgres",
        "GOOGLE_API_KEY": "provider-value",
        "ALLOWED_ORIGINS": "https://app.documind.dev,http://localhost:5173",
        "FRONTEND_URL": "https://app.documind.dev",
        "REDIS_URL": "rediss://cache.internal.net:6379/0",
    }

    assert deploy.invalid_configuration_keys(values) == []


def test_cloud_run_validation_rejects_database_template_host():
    deploy = _load_deploy_module()
    values = {
        "SECRET_KEY": "a-production-signing-secret-value",
        "SUPABASE_URL": "https://project.supabase.co",
        "SUPABASE_ANON_KEY": "anon-value",
        "SUPABASE_SERVICE_KEY": "service-value",
        "DATABASE_URL": "postgresql+asyncpg://user:password@host:5432/postgres",
        "GOOGLE_API_KEY": "provider-value",
        "ALLOWED_ORIGINS": "https://app.documind.dev",
        "FRONTEND_URL": "https://app.documind.dev",
    }

    assert deploy.invalid_configuration_keys(values) == ["DATABASE_URL"]

import os
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Set test environment variables before any app configuration is loaded
os.environ.setdefault("SECRET_KEY", "ci-test-secret-key-do-not-use-in-production-long-enough")
os.environ.setdefault("GOOGLE_API_KEY", "test-placeholder-key")
os.environ.setdefault("GEMINI_API_KEY", "test-placeholder-key")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "test-anon-key")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-service-key")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ENVIRONMENT", "test")

# ruff: noqa: E402
import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import BinaryExpression

# Register sqlite3 adapters for list and dict so SQLite can serialize JSON/ARRAY columns in tests
sqlite3.register_adapter(list, lambda val: json.dumps(val, default=str))
sqlite3.register_adapter(dict, lambda val: json.dumps(val, default=str))

# Must override postgres types for SQLite in-memory DB before importing models
@compiles(UUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "VARCHAR(36)"

@compiles(ARRAY, "sqlite")
def compile_array(element, compiler, **kw):
    return "JSON"

@compiles(Vector, "sqlite")
def compile_vector(element, compiler, **kw):
    return "TEXT"

@compiles(BinaryExpression, "sqlite")
def compile_binary(element, compiler, **kw):
    if getattr(element.operator, "opstring", None) == "<=>":
        return "0.0"
    return compiler.visit_binary(element, **kw)

from app.core.config import get_settings
from app.core.limiter import limiter
from app.db.database import get_db
from app.main import app
from app.models.models import Base

settings = get_settings()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Keep per-IP limiter state isolated between tests."""
    limiter._limiter.storage.reset()
    yield
    limiter._limiter.storage.reset()

from sqlalchemy.pool import StaticPool

# Setup SQLite in memory connection with StaticPool so all sessions share the in-memory database
engine = create_async_engine(
    "sqlite+aiosqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False
)
TestingSessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)


@pytest_asyncio.fixture(scope="function")
async def db_session():
    """Yield a database session and rollback/drop afterward."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with TestingSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="function")
def test_app(db_session):
    """Override FastAPI dependencies and provide the app."""
    async def override_get_db():
        yield db_session

    import app.db.database as db_mod
    orig_db_asl = db_mod.AsyncSessionLocal
    db_mod.AsyncSessionLocal = TestingSessionLocal

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()
    db_mod.AsyncSessionLocal = orig_db_asl


@pytest.fixture(scope="function")
def client(test_app):
    """Sync TestClient."""
    with TestClient(test_app) as c:
        yield c


@pytest_asyncio.fixture(scope="function")
async def async_client(test_app):
    """Async TestClient using httpx."""
    from httpx import ASGITransport, AsyncClient
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_ai_and_gemini():
    """Mock all LiteLLM and Google Gemini API calls across the app."""
    with patch("litellm.acompletion") as mock_litellm_comp, \
         patch("litellm.aembedding") as mock_litellm_embed:

        # Mock LiteLLM embedding
        def _fake_embed(*args, **kwargs):
            inputs = kwargs.get("input", ["test"])
            dims = kwargs.get("dimensions", 768)
            mock_obj = MagicMock()
            mock_obj.data = [{"embedding": [0.05] * dims} for _ in inputs]
            return mock_obj

        mock_litellm_embed.side_effect = _fake_embed

        # Mock LiteLLM completion
        mock_choice = MagicMock()
        mock_choice.message.content = (
            '{"summary": "Test Summary", '
            '"persons": ["John Doe"], "organizations": ["Acme"], "locations": ["Paris"], '
            '"dates": ["2025"], "technologies": ["Python"], "monetary_values": ["$100"], "other": [], '
            '"label": "Positive", "score": 0.9, "confidence": 0.9, "tone": "formal", "explanation": "Good test", '
            '"answer": "Mock Answer", "id": 0}'
        )
        mock_resp = MagicMock()
        mock_resp.choices = [mock_choice]
        mock_litellm_comp.return_value = mock_resp

        yield {
            "acompletion": mock_litellm_comp,
            "aembedding": mock_litellm_embed,
        }


@pytest.fixture(autouse=True)
def mock_supabase():
    """Mock Supabase storage calls cleanly across all import paths."""
    mock_client = MagicMock()
    mock_admin = MagicMock()

    mock_bucket = MagicMock()
    mock_bucket.upload.return_value = {"Key": "test_path"}
    mock_bucket.remove.return_value = [{"Key": "test_path"}]
    mock_bucket.get_public_url.return_value = "http://test.supabase.co/storage/v1/public/test_path"

    mock_client.storage.from_.return_value = mock_bucket
    mock_admin.storage.from_.return_value = mock_bucket

    with patch("app.db.database.get_supabase", return_value=mock_client), \
         patch("app.db.database.get_supabase_admin", return_value=mock_admin), \
         patch("app.db.database._supabase_client", mock_client), \
         patch("app.db.database._supabase_admin", mock_admin):

        yield {
            "client": mock_client,
            "admin": mock_admin,
            "bucket": mock_bucket,
        }

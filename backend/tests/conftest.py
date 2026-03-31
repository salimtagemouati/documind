import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from fastapi.testclient import TestClient

# Must override postgres types for SQLite in-memory DB before importing models
@compiles(UUID, "sqlite")
def compile_uuid(element, compiler, **kw):
    return "VARCHAR(36)"

@compiles(ARRAY, "sqlite")
def compile_array(element, compiler, **kw):
    return "JSON"

from app.db.database import get_db, Base
from app.main import app
from app.core.config import get_settings

settings = get_settings()

# Setup SQLite in memory connection
engine = create_async_engine(
    "sqlite+aiosqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=None,
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

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def client(test_app):
    """Sync TestClient."""
    with TestClient(test_app) as c:
        yield c

@pytest_asyncio.fixture(scope="function")
async def async_client(test_app):
    """Async TestClient using httpx."""
    from httpx import AsyncClient, ASGITransport
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as ac:
        yield ac


from unittest.mock import AsyncMock, patch, MagicMock

@pytest.fixture(autouse=True)
def mock_gemini():
    """Mock all Google Gemini API calls across the app."""
    with patch("app.services.ai_service.genai") as mock_genai, \
         patch("app.services.ai_service._chat_model") as mock_chat, \
         patch("app.services.ai_service._json_model") as mock_json, \
         patch("app.services.rag_service.genai") as mock_rag_genai:

        # Mock embeddings (768 dimensions for Gemini text-embedding-004)
        mock_embed_result = {"embedding": [[0.1] * 768]}
        mock_rag_genai.embed_content.return_value = mock_embed_result
        mock_genai.embed_content.return_value = mock_embed_result

        # Mock chat completions (text generation)
        mock_response = MagicMock()
        mock_response.text = '{"summary": "Test", "entities": {}, "sentiment": {"label": "positive", "score": 0.9}, "keywords": ["test"]}'
        
        mock_chat.generate_content_async = AsyncMock(return_value=mock_response)
        mock_json.generate_content_async = AsyncMock(return_value=mock_response)

        yield {
            "genai": mock_genai,
            "chat_model": mock_chat,
            "json_model": mock_json,
            "rag_genai": mock_rag_genai,
        }

@pytest.fixture(autouse=True)
def mock_supabase():
    """Mock Supabase storage calls."""
    with patch("app.db.database.get_supabase") as mock_get_supabase, \
         patch("app.db.database.get_supabase_admin") as mock_get_admin:
        
        mock_client = MagicMock()
        mock_admin = MagicMock()
        
        # Mock storage operations
        mock_client.storage = MagicMock()
        mock_client.storage.from_ = MagicMock()
        
        mock_get_supabase.return_value = mock_client
        mock_get_admin.return_value = mock_admin
        
        yield {
            "client": mock_client,
            "admin": mock_admin
        }

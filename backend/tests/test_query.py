from uuid import uuid4
from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.models.models import Document, DocumentStatus, User
from app.schemas.schemas import MultiQueryResponse, MultiSourceChunk, QueryResponse, SourceChunk


@pytest_asyncio.fixture
async def auth_client(async_client: AsyncClient):
    await async_client.post("/api/v1/auth/register", json={"email": "query@example.com", "password": "SecurePwd123!", "full_name": "Query User"})
    resp = await async_client.post("/api/v1/auth/login", json={"email": "query@example.com", "password": "SecurePwd123!"})
    token = resp.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client


@pytest.mark.asyncio
async def test_query_unauthorized(async_client: AsyncClient):
    payload = {"document_id": str(uuid4()), "question": "What is life?"}
    response = await async_client.post("/api/v1/query/", json=payload)
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_query_cache_miss_and_hit(auth_client: AsyncClient, db_session, monkeypatch):
    import app.api.routes.query as query_route
    import app.services.cache_service as cache

    # Mock Redis cache
    class MockRedis:
        def __init__(self): self.d = {}
        async def get(self, k): return self.d.get(k)
        async def setex(self, k, ttl, v): self.d[k] = v
        async def delete(self, *k): pass
    monkeypatch.setattr(cache, "_redis", MockRedis())

    # Setup document
    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    user = user_result.scalar_one()

    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        filename="test.pdf",
        original_filename="test.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path",
        status=DocumentStatus.ready,
    )
    db_session.add(doc)
    await db_session.commit()

    # Mock Answer Question RAG
    async def mock_rag(*args, **kwargs):
        return QueryResponse(
            question=kwargs["question"],
            answer="Mock Answer",
            sources=[
                SourceChunk(content="Context", chunk_index=0, similarity_score=0.99, page_number=None)
            ],
            model_used="gemini/gemini-2.0-flash",
            tokens_used=100,
            latency_ms=10,
            from_cache=False,
            query_id=uuid4(),
            reranked=True,
        )
    monkeypatch.setattr(query_route, "answer_question", mock_rag)

    # Query - Cache Miss
    payload = {"document_id": str(doc_id), "question": "What is the capital of Paris?", "max_tokens": 100}
    response = await auth_client.post("/api/v1/query/", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Mock Answer"
    assert data["from_cache"] is False

    # Query - Cache Hit
    response2 = await auth_client.post("/api/v1/query/", json=payload)
    data2 = response2.json()
    assert data2["answer"] == "Mock Answer"
    assert data2["from_cache"] is True


@pytest.mark.asyncio
async def test_query_document_not_ready(auth_client: AsyncClient, db_session):
    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    user = user_result.scalar_one()

    doc_id = uuid4()
    doc = Document(
        id=doc_id,
        user_id=user.id,
        filename="pending.pdf",
        original_filename="pending.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path",
        status=DocumentStatus.processing,
    )
    db_session.add(doc)
    await db_session.commit()

    payload = {"document_id": str(doc_id), "question": "Wait for me"}
    response = await auth_client.post("/api/v1/query/", json=payload)
    assert response.status_code == 409
    assert "Please wait for processing" in response.json()["detail"]


@pytest.mark.asyncio
async def test_multi_document_query(auth_client: AsyncClient, db_session, monkeypatch):
    import app.api.routes.query as query_route

    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    user = user_result.scalar_one()

    doc1_id = uuid4()
    doc2_id = uuid4()

    doc1 = Document(
        id=doc1_id,
        user_id=user.id,
        filename="contract1.pdf",
        original_filename="Contract A.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path1",
        status=DocumentStatus.ready,
    )
    doc2 = Document(
        id=doc2_id,
        user_id=user.id,
        filename="contract2.pdf",
        original_filename="Contract B.pdf",
        file_type="pdf",
        file_size_bytes=100,
        storage_path="path2",
        status=DocumentStatus.ready,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    async def mock_multi_rag(*args, **kwargs):
        return MultiQueryResponse(
            question=kwargs["question"],
            answer="Both contracts specify liability terms.",
            sources=[
                MultiSourceChunk(content="Doc 1 clause", chunk_index=0, document_id=doc1_id, document_name="Contract A.pdf", similarity_score=0.9),
                MultiSourceChunk(content="Doc 2 clause", chunk_index=0, document_id=doc2_id, document_name="Contract B.pdf", similarity_score=0.88),
            ],
            documents_queried=[{"id": str(doc1_id), "name": "Contract A.pdf"}, {"id": str(doc2_id), "name": "Contract B.pdf"}],
            model_used="gemini/gemini-2.0-flash",
            tokens_used=150,
            latency_ms=25,
            reranked=True,
            from_cache=False,
            query_id=uuid4(),
        )
    monkeypatch.setattr(query_route, "synthesize_multi_document_query", mock_multi_rag)

    payload = {
        "document_ids": [str(doc1_id), str(doc2_id)],
        "question": "Compare the liability terms across both contracts",
    }
    response = await auth_client.post("/api/v1/query/multi", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "Both contracts" in data["answer"]
    assert len(data["sources"]) == 2
    assert len(data["documents_queried"]) == 2

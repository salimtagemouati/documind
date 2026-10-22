from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import select

from app.models.models import Document, DocumentStatus, User
from app.schemas.schemas import (
    MultiQueryResponse,
    MultiSourceChunk,
    QueryResponse,
    SourceChunk,
)


@pytest.mark.asyncio
async def test_multi_query_rejects_duplicate_document_ids(auth_client: AsyncClient):
    document_id = str(uuid4())
    response = await auth_client.post(
        "/api/v1/query/multi",
        json={
            "document_ids": [document_id, document_id],
            "question": "Compare these documents",
        },
    )

    assert response.status_code == 422


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
async def test_query_rate_limit_error_returns_clean_response(
    auth_client: AsyncClient, db_session, monkeypatch
):
    import litellm

    import app.api.routes.query as query_route

    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    user = user_result.scalar_one()
    doc = Document(
        id=uuid4(), user_id=user.id, filename="ready.pdf", original_filename="ready.pdf",
        file_type="pdf", file_size_bytes=100, storage_path="ready", status=DocumentStatus.ready,
    )
    db_session.add(doc)
    await db_session.commit()

    async def fail_with_rate_limit(**kwargs):
        raise litellm.RateLimitError(
            message="provider rejected request with api_key=do-not-leak",
            model="test-model",
            llm_provider="test-provider",
        )

    monkeypatch.setattr(query_route, "answer_question", fail_with_rate_limit)
    response = await auth_client.post(
        "/api/v1/query/",
        json={"document_id": str(doc.id), "question": "What is the answer?"},
    )

    assert response.status_code == 429
    assert response.json() == {"detail": "AI service rate limit reached. Please try again later."}
    assert "do-not-leak" not in response.text


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


@pytest.mark.asyncio
async def test_multi_query_unauthorized_document(auth_client: AsyncClient, db_session):
    """Verify 404 when one document belongs to another user (no existence leakage)."""
    user2 = User(email="other_owner@example.com", hashed_password="h", full_name="Other Owner")
    db_session.add(user2)
    await db_session.flush()

    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    current_user = user_result.scalar_one()

    doc1 = Document(
        id=uuid4(), user_id=current_user.id, filename="mine.pdf", original_filename="mine.pdf",
        file_type="pdf", file_size_bytes=100, storage_path="p1", status=DocumentStatus.ready,
    )
    doc2 = Document(
        id=uuid4(), user_id=user2.id, filename="theirs.pdf", original_filename="theirs.pdf",
        file_type="pdf", file_size_bytes=100, storage_path="p2", status=DocumentStatus.ready,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    payload = {
        "document_ids": [str(doc1.id), str(doc2.id)],
        "question": "Cross query",
    }
    response = await auth_client.post("/api/v1/query/multi", json=payload)
    assert response.status_code == 404
    assert "not found or unauthorized" in response.json()["detail"]


@pytest.mark.asyncio
async def test_multi_query_max_documents_validation(auth_client: AsyncClient):
    """Verify 422 Unprocessable Entity when more than 5 documents are passed."""
    payload = {
        "document_ids": [str(uuid4()) for _ in range(6)],
        "question": "Too many documents query",
    }
    response = await auth_client.post("/api/v1/query/multi", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_multi_query_rerank_disabled(auth_client: AsyncClient, db_session, monkeypatch):
    """Verify querying multiple documents with enable_rerank=False."""
    import app.api.routes.query as query_route

    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    user = user_result.scalar_one()

    doc1 = Document(
        id=uuid4(), user_id=user.id, filename="d1.pdf", original_filename="d1.pdf",
        file_type="pdf", file_size_bytes=100, storage_path="p1", status=DocumentStatus.ready,
    )
    doc2 = Document(
        id=uuid4(), user_id=user.id, filename="d2.pdf", original_filename="d2.pdf",
        file_type="pdf", file_size_bytes=100, storage_path="p2", status=DocumentStatus.ready,
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()

    rerank_flag_received = None

    async def mock_multi_rag(*args, **kwargs):
        nonlocal rerank_flag_received
        rerank_flag_received = kwargs.get("enable_rerank")
        return MultiQueryResponse(
            question=kwargs["question"],
            answer="Answer without rerank.",
            sources=[],
            documents_queried=[{"id": str(doc1.id), "name": "d1.pdf"}, {"id": str(doc2.id), "name": "d2.pdf"}],
            model_used="gemini/gemini-3.6-flash",
            tokens_used=80,
            latency_ms=15,
            reranked=False,
            from_cache=False,
            query_id=uuid4(),
        )

    monkeypatch.setattr(query_route, "synthesize_multi_document_query", mock_multi_rag)

    payload = {
        "document_ids": [str(doc1.id), str(doc2.id)],
        "question": "Compare without reranking",
        "enable_rerank": False,
    }
    response = await auth_client.post("/api/v1/query/multi", json=payload)
    assert response.status_code == 200
    assert rerank_flag_received is False

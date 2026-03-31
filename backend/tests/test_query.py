import pytest
from httpx import AsyncClient
from uuid import uuid4
from sqlalchemy import select
from app.models.models import Document, DocumentStatus, User

@pytest.fixture
async def auth_client(async_client: AsyncClient):
    await async_client.post("/api/v1/auth/register", json={"email": "query@example.com", "password": "pass", "full_name": "Query User"})
    resp = await async_client.post("/api/v1/auth/login", json={"email": "query@example.com", "password": "pass"})
    token = resp.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client

@pytest.mark.asyncio
async def test_query_unauthorized(async_client: AsyncClient):
    payload = {"document_id": str(uuid4()), "question": "What is life?"}
    response = await async_client.post("/api/v1/query/", json=payload)
    assert response.status_code == 401

@pytest.mark.asyncio
async def test_query_cache_miss_and_hit(auth_client: AsyncClient, db_session, monkeypatch):
    import app.services.cache_service as cache
    import app.api.routes.query as query_route
    
    # Mock Redis cache
    class MockRedis:
        def __init__(self): self.d = {}
        async def get(self, k): return self.d.get(k)
        async def setex(self, k, ttl, v): self.d[k] = v
        async def delete(self, *k): pass
    monkeypatch.setattr(cache, "redis_client", MockRedis())
    
    # Setup document
    user_result = await db_session.execute(select(User).where(User.email == "query@example.com"))
    user = user_result.scalar_one()
    
    doc_id = uuid4()
    doc = Document(id=doc_id, user_id=user.id, filename="test.pdf", original_filename="test.pdf", file_type="pdf", file_size_bytes=100, storage_path="path", status=DocumentStatus.ready)
    db_session.add(doc)
    await db_session.commit()
    
    # Mock Answer Question RAG
    async def mock_rag(*args, **kwargs):
        from app.schemas.schemas import QueryResponse, SourceChunk
        return QueryResponse(
            question=kwargs["question"], answer="Mock Answer", sources=[
                SourceChunk(content="Context", chunk_index=0, similarity_score=0.99)
            ], model_used="gpt-4o", tokens_used=100, latency_ms=10, from_cache=False, query_id=uuid4()
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
    doc = Document(id=doc_id, user_id=user.id, filename="pending.pdf", original_filename="pending.pdf", file_type="pdf", file_size_bytes=100, storage_path="path", status=DocumentStatus.processing)
    db_session.add(doc)
    await db_session.commit()
    
    payload = {"document_id": str(doc_id), "question": "Wait for me"}
    response = await auth_client.post("/api/v1/query/", json=payload)
    assert response.status_code == 409
    assert "Please wait for processing" in response.json()["detail"]

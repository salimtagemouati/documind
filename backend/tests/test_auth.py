import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_public_billing_config_reports_payments_disabled(
    async_client: AsyncClient, monkeypatch
):
    import app.api.routes.billing as billing_route

    monkeypatch.setattr(billing_route.settings, "STRIPE_SECRET_KEY", "")
    monkeypatch.setattr(billing_route.settings, "STRIPE_PRICE_ID_PRO", "")

    response = await async_client.get("/api/v1/billing/config")

    assert response.status_code == 200
    assert response.json() == {"payments_enabled": False}


@pytest.mark.asyncio
async def test_register_success(async_client: AsyncClient):
    payload = {"email": "test@example.com", "password": "SecurePwd123!", "full_name": "Test User"}
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    assert "access_token" in response.json()
    assert "refresh_token" in response.json()

@pytest.mark.asyncio
async def test_register_duplicate_email(async_client: AsyncClient):
    payload = {"email": "dup@example.com", "password": "SecurePwd123!", "full_name": "Dup User"}
    await async_client.post("/api/v1/auth/register", json=payload)
    response = await async_client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]

@pytest.mark.asyncio
async def test_login_success(async_client: AsyncClient):
    await async_client.post("/api/v1/auth/register", json={"email": "login@example.com", "password": "SecurePwd123!", "full_name": "Login User"})
    
    response = await async_client.post("/api/v1/auth/login", json={"email": "login@example.com", "password": "SecurePwd123!"})
    assert response.status_code == 200
    assert "access_token" in response.json()

@pytest.mark.asyncio
async def test_login_wrong_password(async_client: AsyncClient):
    await async_client.post("/api/v1/auth/register", json={"email": "wrong@example.com", "password": "SecurePwd123!", "full_name": "Wrong User"})
    
    response = await async_client.post("/api/v1/auth/login", json={"email": "wrong@example.com", "password": "wrongpwd"})
    assert response.status_code == 401
    assert "Invalid email or password" in response.json()["detail"]

@pytest.mark.asyncio
async def test_refresh_success(async_client: AsyncClient):
    await async_client.post("/api/v1/auth/register", json={"email": "ref@example.com", "password": "SecurePwd123!", "full_name": "Refresh User"})
    login_resp = await async_client.post("/api/v1/auth/login", json={"email": "ref@example.com", "password": "SecurePwd123!"})
    refresh_token = login_resp.json()["refresh_token"]
    
    refresh_resp = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert refresh_resp.status_code == 200
    assert "access_token" in refresh_resp.json()
    assert "refresh_token" in refresh_resp.json()


@pytest.mark.asyncio
async def test_demo_login_success(async_client: AsyncClient):
    from app.core.security import decode_token

    response = await async_client.post("/api/v1/auth/demo")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["expires_in"] == 7200  # 2 hours

    payload = decode_token(data["access_token"])
    assert payload.get("is_demo") is True
    assert payload.get("exp") - payload.get("iat") == 7200

    refresh_payload = decode_token(data["refresh_token"])
    assert refresh_payload.get("is_demo") is True
    assert refresh_payload.get("exp") - refresh_payload.get("iat") == 7200

    profile = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {data['access_token']}"},
    )
    assert profile.status_code == 200
    assert profile.json()["is_demo"] is True


@pytest.mark.asyncio
async def test_demo_refresh_remains_short_lived_and_demo_scoped(async_client: AsyncClient):
    from app.core.security import decode_token

    demo_response = await async_client.post("/api/v1/auth/demo")
    refresh_response = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": demo_response.json()["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    access_payload = decode_token(refreshed["access_token"])
    refresh_payload = decode_token(refreshed["refresh_token"])
    assert access_payload.get("is_demo") is True
    assert refresh_payload.get("is_demo") is True
    assert access_payload["exp"] - access_payload["iat"] == 7200
    assert refresh_payload["exp"] - refresh_payload["iat"] == 7200


@pytest.mark.asyncio
async def test_demo_user_seed_idempotent(async_client: AsyncClient):
    resp1 = await async_client.post("/api/v1/auth/demo")
    assert resp1.status_code == 200
    resp2 = await async_client.post("/api/v1/auth/demo")
    assert resp2.status_code == 200


@pytest.mark.asyncio
async def test_demo_user_upload_rejected(async_client: AsyncClient):
    demo_resp = await async_client.post("/api/v1/auth/demo")
    token = demo_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    files = {"file": ("test.txt", b"Hello DocuMind", "text/plain")}
    upload_resp = await async_client.post("/api/v1/documents/upload", headers=headers, files=files)
    assert upload_resp.status_code == 403
    assert "Demo accounts are read-only" in upload_resp.json()["detail"]


@pytest.mark.asyncio
async def test_demo_user_delete_rejected(async_client: AsyncClient):
    from uuid import uuid4
    demo_resp = await async_client.post("/api/v1/auth/demo")
    token = demo_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    del_resp = await async_client.delete(f"/api/v1/documents/{uuid4()}", headers=headers)
    assert del_resp.status_code == 403
    assert "Demo accounts are read-only" in del_resp.json()["detail"]


@pytest.mark.asyncio
async def test_demo_user_billing_write_rejected(async_client: AsyncClient):
    demo_resp = await async_client.post("/api/v1/auth/demo")
    headers = {"Authorization": f"Bearer {demo_resp.json()['access_token']}"}

    checkout_resp = await async_client.post("/api/v1/billing/checkout", headers=headers)
    portal_resp = await async_client.post("/api/v1/billing/portal", headers=headers)

    assert checkout_resp.status_code == 403
    assert portal_resp.status_code == 403


@pytest.mark.asyncio
async def test_demo_query_does_not_persist_history_or_usage(
    async_client: AsyncClient, db_session, monkeypatch
):
    from uuid import UUID

    from sqlalchemy import func, select

    import app.api.routes.query as query_route
    from app.models.models import Document, QueryHistory, User
    from app.schemas.schemas import QueryResponse, SourceChunk

    demo_resp = await async_client.post("/api/v1/auth/demo")
    headers = {"Authorization": f"Bearer {demo_resp.json()['access_token']}"}
    docs_resp = await async_client.get("/api/v1/documents/", headers=headers)
    doc_id = docs_resp.json()["items"][0]["id"]

    async def fake_answer(**kwargs):
        return QueryResponse(
            question=kwargs["question"],
            answer="Grounded demo answer",
            sources=[SourceChunk(content="Evidence", chunk_index=0, page_number=1, similarity_score=0.9)],
            model_used="test-model",
            tokens_used=20,
            latency_ms=5,
            from_cache=False,
            query_id=kwargs["query_id"],
        )

    monkeypatch.setattr(query_route, "answer_question", fake_answer)

    response = await async_client.post(
        "/api/v1/query/",
        headers=headers,
        json={"document_id": doc_id, "question": "What does the sample say?"},
    )
    assert response.status_code == 200

    history_count = (
        await db_session.execute(select(func.count(QueryHistory.id)))
    ).scalar_one()
    demo_user = (
        await db_session.execute(
            select(User).join(Document, Document.user_id == User.id).where(Document.id == UUID(doc_id))
        )
    ).scalar_one()
    assert history_count == 0
    assert demo_user.queries_made == 0
    assert demo_user.ai_tokens_used == 0


@pytest.mark.asyncio
async def test_demo_queries_are_rate_limited_per_ip(
    async_client: AsyncClient, monkeypatch
):
    import app.api.routes.query as query_route
    from app.schemas.schemas import QueryResponse

    demo_resp = await async_client.post("/api/v1/auth/demo")
    headers = {"Authorization": f"Bearer {demo_resp.json()['access_token']}"}
    docs_resp = await async_client.get("/api/v1/documents/", headers=headers)
    doc_id = docs_resp.json()["items"][0]["id"]

    async def no_cache(*args, **kwargs):
        return None

    async def fake_answer(**kwargs):
        return QueryResponse(
            question=kwargs["question"],
            answer="Grounded demo answer",
            sources=[],
            model_used="test-model",
            tokens_used=20,
            latency_ms=5,
            from_cache=False,
            query_id=kwargs["query_id"],
        )

    monkeypatch.setattr(query_route, "get_cached_answer", no_cache)
    monkeypatch.setattr(query_route, "answer_question", fake_answer)

    responses = []
    for index in range(11):
        responses.append(
            await async_client.post(
                "/api/v1/query/",
                headers=headers,
                json={"document_id": doc_id, "question": f"Demo question number {index}"},
            )
        )

    assert all(response.status_code == 200 for response in responses[:10])
    assert responses[10].status_code == 429

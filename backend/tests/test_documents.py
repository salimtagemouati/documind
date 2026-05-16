import pytest
import pytest_asyncio
from httpx import AsyncClient
from io import BytesIO

@pytest_asyncio.fixture
async def auth_client(async_client: AsyncClient):
    await async_client.post("/api/v1/auth/register", json={"email": "doc@example.com", "password": "SecurePwd123!", "full_name": "Doc User"})
    resp = await async_client.post("/api/v1/auth/login", json={"email": "doc@example.com", "password": "SecurePwd123!"})
    token = resp.json()["access_token"]
    async_client.headers["Authorization"] = f"Bearer {token}"
    return async_client

@pytest.mark.asyncio
async def test_upload_document(auth_client: AsyncClient):
    file_content = b"This is a test document."
    files = {"file": ("test.txt", BytesIO(file_content), "text/plain")}
    response = await auth_client.post("/api/v1/documents/upload", files=files)
    assert response.status_code == 202
    assert "id" in response.json()
    assert response.json()["filename"] == "test.txt"

@pytest.mark.asyncio
async def test_list_documents(auth_client: AsyncClient):
    response = await auth_client.get("/api/v1/documents/")
    assert response.status_code == 200
    assert "items" in response.json()
    assert isinstance(response.json()["items"], list)

@pytest.mark.asyncio
async def test_get_document(auth_client: AsyncClient):
    file_content = b"Hello, world!"
    files = {"file": ("test2.txt", BytesIO(file_content), "text/plain")}
    upload = await auth_client.post("/api/v1/documents/upload", files=files)
    doc_id = upload.json()["id"]
    
    response = await auth_client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    assert response.json()["id"] == doc_id

@pytest.mark.asyncio
async def test_delete_document(auth_client: AsyncClient):
    files = {"file": ("test3.txt", BytesIO(b"Hello Delete"), "text/plain")}
    upload = await auth_client.post("/api/v1/documents/upload", files=files)
    doc_id = upload.json()["id"]
    
    response = await auth_client.delete(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    
    get_resp = await auth_client.get(f"/api/v1/documents/{doc_id}")
    assert get_resp.status_code == 404

@pytest.mark.asyncio
async def test_unauthorized_access(async_client: AsyncClient):
    response = await async_client.get("/api/v1/documents/")
    assert response.status_code in [401, 403]

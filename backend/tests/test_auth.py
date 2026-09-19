import pytest
from httpx import AsyncClient

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
    response = await async_client.post("/api/v1/auth/demo")
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data

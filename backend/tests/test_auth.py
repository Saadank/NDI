import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_login_missing_fields():
    """Login with empty body returns 422 validation error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/platform/auth/login", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_endpoint_exists():
    """Login endpoint exists (not 404)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/platform/auth/login",
            json={"username": "test@test.com", "password": "wrong"},
        )
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_refresh_missing_token():
    """Refresh with empty body returns 422."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/api/v1/platform/auth/refresh", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_protected_endpoint_requires_auth():
    """Accessing a protected endpoint without token returns 403."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/platform/users/me")
    assert response.status_code in (401, 403)

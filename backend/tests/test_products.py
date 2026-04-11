import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_platform_auth_endpoints_exist():
    """Auth endpoints are registered and don't return 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for method, path in [
            ("POST", "/api/v1/platform/auth/login"),
            ("POST", "/api/v1/platform/auth/refresh"),
            ("POST", "/api/v1/platform/auth/logout"),
        ]:
            response = await client.request(method, path, json={})
            assert response.status_code != 404, f"{method} {path} returned 404"


@pytest.mark.asyncio
async def test_protected_endpoints_require_auth():
    """Protected platform endpoints return 401 without a token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in [
            "/api/v1/platform/users/me",
            "/api/v1/platform/invitations/",
            "/api/v1/platform/tenants/",
            "/api/v1/platform/products/me",
            "/api/v1/platform/audit/",
        ]:
            response = await client.get(path)
            assert response.status_code in (401, 403), f"{path} returned {response.status_code}"

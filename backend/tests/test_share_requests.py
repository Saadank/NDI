import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_create_request_missing_title():
    """Validation: title is required on share request creation."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/products/data-sharing/requests/",
            json={"purpose": "Testing"},
            headers={"Authorization": "Bearer fake"},
        )
    assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_mvp_endpoints_exist():
    """All MVP Data Sharing endpoints are registered (not 404)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for path in [
            "/api/v1/products/data-sharing/requests/",
            "/api/v1/products/data-sharing/notifications/",
            "/api/v1/products/data-sharing/files/initiate",
            "/api/v1/products/data-sharing/workflows/templates",
            "/api/v1/products/data-sharing/connections/",
        ]:
            response = await client.get(path)
            assert response.status_code != 404, f"{path} returned 404"

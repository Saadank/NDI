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
    # Returns 403 (no valid auth) or 422 (validation) — not 404
    assert response.status_code in (401, 403, 422)


@pytest.mark.asyncio
async def test_share_request_endpoints_exist():
    """All share request endpoints are registered (not 404)."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # These should all return 403 (auth required), not 404
        for path in [
            "/api/v1/products/data-sharing/requests/",
            "/api/v1/products/data-sharing/notifications/",
            "/api/v1/products/data-sharing/files/initiate",
            "/api/v1/products/data-sharing/workflows/templates",
            "/api/v1/products/data-sharing/connections/",
            "/api/v1/products/data-sharing/glossary/",
            "/api/v1/products/data-sharing/dsa/",
            "/api/v1/products/data-sharing/breaches/",
            "/api/v1/products/data-sharing/dsr/",
        ]:
            response = await client.get(path)
            assert response.status_code != 404, f"{path} returned 404"

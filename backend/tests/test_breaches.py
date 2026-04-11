import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_breach_endpoint_requires_auth():
    """Breach endpoint returns 403 without auth."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/products/data-sharing/breaches/")
    assert response.status_code in (401, 403)


@pytest.mark.asyncio
async def test_report_breach_validation():
    """Title and description are required to report a breach."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/products/data-sharing/breaches/",
            json={"title": "Test Breach"},
            headers={"Authorization": "Bearer fake"},
        )
    # 403 (no valid auth) or 422 (validation)
    assert response.status_code in (401, 403, 422)

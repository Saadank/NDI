import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_notification_endpoint_requires_auth():
    """Notifications endpoint returns 403 without auth, not 404."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/products/data-sharing/notifications/")
    assert response.status_code in (401, 403)

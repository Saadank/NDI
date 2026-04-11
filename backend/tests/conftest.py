import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import get_current_user
from app.main import app
from app.structures.auth_user import AuthUser
from app.platform.enums.platform_role import PlatformRole


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def make_auth_user(
    user_id: int = 1,
    tenant_id: int = 1,
    platform_role: PlatformRole = PlatformRole.ORG_ADMIN,
    keycloak_id: str = "kc-test-user",
) -> AuthUser:
    return AuthUser(
        user_id=user_id,
        keycloak_id=keycloak_id,
        tenant_id=tenant_id,
        platform_role=platform_role,
        product_role=None,
        current_product=None,
    )


@pytest.fixture
def auth_user():
    return make_auth_user()


@pytest.fixture
def admin_user():
    return make_auth_user(platform_role=PlatformRole.PLATFORM_ADMIN)


@pytest.fixture
async def client(auth_user):
    """Test client with mocked auth — no DB required for route-level tests."""
    app.dependency_overrides[get_current_user] = lambda: auth_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest.fixture
async def admin_client(admin_user):
    app.dependency_overrides[get_current_user] = lambda: admin_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

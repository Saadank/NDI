import logging
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.core.config import get_settings
from app.structures.auth_user import AuthUser
from app.utils.exceptions import UnauthorizedException

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer()
_public_key_cache: str | None = None


async def _get_public_key() -> str:
    global _public_key_cache
    if _public_key_cache is not None:
        return _public_key_cache

    from app.gateways.keycloak_gateway import KeycloakGateway

    gateway = KeycloakGateway()
    _public_key_cache = gateway.get_public_key()
    return _public_key_cache


def decode_token(token: str, public_key: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience="account",
            issuer=f"{settings.KEYCLOAK_SERVER_URL}/realms/{settings.KEYCLOAK_REALM}",
        )
        return payload
    except JWTError as e:
        logger.warning(f"Token decode failed: {e}")
        raise UnauthorizedException("Invalid or expired token")


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
) -> AuthUser:
    public_key = await _get_public_key()
    payload = decode_token(credentials.credentials, public_key)

    keycloak_id = payload.get("sub")
    if not keycloak_id:
        raise UnauthorizedException("Token missing subject")

    realm_roles = payload.get("realm_access", {}).get("roles", [])

    from app.platform.enums.platform_role import PlatformRole

    # Try to get user_id and tenant_id from JWT claims first
    user_id = payload.get("user_id")
    tenant_id = payload.get("tenant_id")

    # Look up from database to get accurate platform_role
    from app.platform.repositories.user_repository import UserRepository
    user_repo = UserRepository()
    db_user = await user_repo.find_by_keycloak_id(keycloak_id)
    if db_user:
        user_id = user_id or db_user["id"]
        tenant_id = tenant_id or db_user["tenant_id"]
    elif not user_id or not tenant_id:
        raise UnauthorizedException("User not found in platform database")

    # Resolve platform_role: check DB first (source of truth), fallback to JWT
    if db_user and db_user.get("platform_role"):
        try:
            platform_role = PlatformRole(db_user["platform_role"])
        except ValueError:
            platform_role = PlatformRole.USER
    elif PlatformRole.PLATFORM_ADMIN.value in realm_roles:
        platform_role = PlatformRole.PLATFORM_ADMIN
    elif PlatformRole.ORG_ADMIN.value in realm_roles:
        platform_role = PlatformRole.ORG_ADMIN
    else:
        platform_role = PlatformRole.USER

    # Resolve product role from database
    product_role = None
    if user_id and tenant_id:
        from app.platform.repositories.product_repository import ProductRepository
        product_repo = ProductRepository()
        product = await product_repo.find_product_by_slug("data_sharing")
        if product:
            role_record = await product_repo.find_user_product_role(user_id, product["id"])
            if role_record:
                product_role = role_record["role"]

    group_id = db_user.get("group_id") if db_user else None

    return AuthUser(
        user_id=user_id,
        keycloak_id=keycloak_id,
        tenant_id=tenant_id,
        platform_role=platform_role,
        product_role=product_role,
        current_product=None,
        group_id=group_id,
    )

from pydantic import BaseModel

from app.platform.enums.platform_role import PlatformRole


class AuthUser(BaseModel):
    user_id: int
    keycloak_id: str
    tenant_id: int | None
    platform_role: PlatformRole | None = None
    product_role: str | None = None
    current_product: str | None = None

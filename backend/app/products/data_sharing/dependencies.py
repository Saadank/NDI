from fastapi import Depends

from app.core.security import get_current_user
from app.platform.services.product_service import ProductService, get_product_service
from app.structures.auth_user import AuthUser


def require_product(product_slug: str):
    async def _check(
        auth_user: AuthUser = Depends(get_current_user),
        service: ProductService = Depends(get_product_service),
    ) -> AuthUser:
        await service.assert_tenant_has_product(auth_user.tenant_id, product_slug)
        return auth_user

    return _check


require_data_sharing = require_product("data_sharing")

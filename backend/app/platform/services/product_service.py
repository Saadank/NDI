import logging

from app.platform.repositories.product_repository import ProductRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ResourceNotFoundException

logger = logging.getLogger(__name__)


class ProductService:

    def __init__(self) -> None:
        self.repo = ProductRepository()

    async def list_all_products(self) -> list[dict]:
        return await self.repo.find_all_products()

    async def list_products_for_tenant(self, tenant_id: int) -> list[dict]:
        return await self.repo.find_tenant_products(tenant_id)

    async def enable_product(self, tenant_id: int, product_slug: str, admin_id: int) -> dict:
        product = await self.repo.find_product_by_slug(product_slug)
        if not product:
            raise ResourceNotFoundException(f"Product '{product_slug}' not found")
        return await self.repo.enable_product(tenant_id, product["id"], admin_id)

    async def disable_product(self, tenant_id: int, product_slug: str, admin_id: int) -> None:
        product = await self.repo.find_product_by_slug(product_slug)
        if not product:
            raise ResourceNotFoundException(f"Product '{product_slug}' not found")
        await self.repo.disable_product(tenant_id, product["id"], admin_id)

    async def get_user_product_role(self, user_id: int, product_slug: str) -> str | None:
        product = await self.repo.find_product_by_slug(product_slug)
        if not product:
            return None
        role_record = await self.repo.find_user_product_role(user_id, product["id"])
        return role_record["role"] if role_record else None

    async def assign_user_product_role(self, user_id: int, product_slug: str, role: str, auth_user: AuthUser) -> dict:
        product = await self.repo.find_product_by_slug(product_slug)
        if not product:
            raise ResourceNotFoundException(f"Product '{product_slug}' not found")
        return await self.repo.assign_user_product_role(user_id, product["id"], role, auth_user.user_id)

    async def assert_tenant_has_product(self, tenant_id: int, product_slug: str) -> None:
        enabled = await self.repo.is_product_enabled_for_tenant(tenant_id, product_slug)
        if not enabled:
            raise ForbiddenException(f"Product '{product_slug}' is not enabled for this organisation")


def get_product_service() -> ProductService:
    return ProductService()

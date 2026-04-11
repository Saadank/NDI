from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.platform.services.product_service import ProductService, get_product_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/products", tags=["products"])


class EnableProductRequest(BaseModel):
    product_slug: str


class AssignProductRoleRequest(BaseModel):
    product_slug: str
    role: str


@router.get("/")
async def list_catalogue(service: ProductService = Depends(get_product_service)):
    return await service.list_all_products()


@router.get("/me")
async def my_products(
    auth_user: AuthUser = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    products = await service.list_products_for_tenant(auth_user.tenant_id)
    result = []
    for p in products:
        role = await service.get_user_product_role(auth_user.user_id, p["slug"])
        result.append({**p, "user_role": role})
    return result


@router.get("/tenants/{tenant_id}")
async def tenant_products(
    tenant_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    return await service.list_products_for_tenant(tenant_id)


@router.post("/tenants/{tenant_id}")
async def enable_product(
    tenant_id: int,
    body: EnableProductRequest,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    return await service.enable_product(tenant_id, body.product_slug, auth_user.user_id)


@router.delete("/tenants/{tenant_id}/{slug}")
async def disable_product(
    tenant_id: int, slug: str,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    await service.disable_product(tenant_id, slug, auth_user.user_id)
    return {"detail": "Product disabled"}


@router.post("/users/{user_id}/product-roles")
async def assign_product_role(
    user_id: int,
    body: AssignProductRoleRequest,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProductService = Depends(get_product_service),
):
    return await service.assign_user_product_role(user_id, body.product_slug, body.role, auth_user)

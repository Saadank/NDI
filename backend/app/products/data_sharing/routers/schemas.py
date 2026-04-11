from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.security import get_current_user
from app.products.data_sharing.services.schema_service import SchemaService, get_schema_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/schemas", tags=["schemas"])


@router.get("/{connection_id}")
async def get_schema(
    connection_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: SchemaService = Depends(get_schema_service),
):
    return await service.get_schema(connection_id, auth_user)

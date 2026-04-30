from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.services.table_type_service import (
    TableTypeService, get_table_type_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/tables", tags=["dq-tables"])


class AssignTypeBody(BaseModel):
    schema_name: str = Field(min_length=1, max_length=255)
    table_name: str = Field(min_length=1, max_length=255)
    semantic_type: str
    note: str | None = None


class ClearTypeBody(BaseModel):
    schema_name: str
    table_name: str


@router.get("/connections/{connection_id}")
async def list_tables_for_connection(
    connection_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: TableTypeService = Depends(get_table_type_service),
):
    """List source-DB tables for a connection, joined with the team's stored
    semantic-type assignments. Tables without an assignment carry the
    "low context confidence" flag (BRD FR-TYPE-02)."""
    return await service.list_tables_with_types(connection_id, auth_user)


@router.put("/connections/{connection_id}/assign")
async def assign_table_type(
    connection_id: UUID,
    body: AssignTypeBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: TableTypeService = Depends(get_table_type_service),
):
    """Assign or update the semantic type for one (schema, table) on the connection."""
    row = await service.assign(
        connection_id=connection_id,
        schema_name=body.schema_name,
        table_name=body.table_name,
        semantic_type=body.semantic_type,
        note=body.note,
        auth_user=auth_user,
    )
    return {"detail": "Type assigned", "row": row}


@router.get("/connections/{connection_id}/preview")
async def preview_table(
    connection_id: UUID,
    schema_name: str = Query(..., min_length=1, max_length=255),
    table_name: str = Query(..., min_length=1, max_length=255),
    limit: int = Query(default=10, ge=1, le=100),
    auth_user: AuthUser = Depends(get_current_user),
    service: TableTypeService = Depends(get_table_type_service),
):
    """Live peek — column metadata + N sample rows. Nothing is persisted."""
    return await service.preview_table(
        connection_id=connection_id, schema_name=schema_name,
        table_name=table_name, limit=limit, auth_user=auth_user,
    )


@router.delete("/connections/{connection_id}/assign")
async def clear_table_type(
    connection_id: UUID,
    body: ClearTypeBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: TableTypeService = Depends(get_table_type_service),
):
    await service.clear(
        connection_id=connection_id,
        schema_name=body.schema_name,
        table_name=body.table_name,
        auth_user=auth_user,
    )
    return {"detail": "Type cleared"}

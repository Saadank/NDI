from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.services.structured_data_service import (
    StructuredDataService, get_structured_data_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/structured", tags=["structured-data"])


class PreviewBody(BaseModel):
    connection_id: UUID
    selection_mode: str  # "tables" | "query"
    selected_items: list[dict] | None = None
    custom_sql: str | None = None
    limit: int = 100


class AttachBody(BaseModel):
    request_id: UUID
    connection_id: UUID
    selection_mode: str
    selected_items: list[dict] | None = None
    custom_sql: str | None = None
    filename: str | None = None


@router.post("/preview")
async def preview_structured(
    body: PreviewBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: StructuredDataService = Depends(get_structured_data_service),
):
    return await service.preview(
        connection_id=body.connection_id,
        selection_mode=body.selection_mode,
        selected_items=body.selected_items,
        custom_sql=body.custom_sql,
        auth_user=auth_user,
        limit=body.limit,
    )


@router.post("/attach")
async def attach_structured(
    body: AttachBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: StructuredDataService = Depends(get_structured_data_service),
):
    return await service.attach_to_request(
        request_id=body.request_id,
        connection_id=body.connection_id,
        selection_mode=body.selection_mode,
        selected_items=body.selected_items,
        custom_sql=body.custom_sql,
        filename=body.filename,
        auth_user=auth_user,
    )

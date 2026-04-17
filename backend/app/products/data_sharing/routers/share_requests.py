from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.core.security import get_current_user
from app.products.data_sharing.enums.data_classification import DataClassification
from app.products.data_sharing.services.share_request_service import ShareRequestService, get_share_request_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/requests", tags=["share-requests"])


class ExternalRecipientInline(BaseModel):
    org_name: str = Field(..., min_length=1)
    contact_email: EmailStr
    contact_name: str | None = None
    phone: str | None = None


class CreateShareRequestBody(BaseModel):
    title: str = Field(..., min_length=1)
    purpose: str = Field(..., min_length=1)
    legal_basis: str = ""
    sharing_type: Literal["internal", "external"] = "internal"
    data_classification: DataClassification = DataClassification.INTERNAL
    personal_data_involved: bool = False
    estimated_data_subjects: int | None = None
    data_subject_categories: list[str] | None = None
    source_description: str | None = None
    receiving_tenant_id: int | None = None
    receiver_group_id: int | None = None
    dpia_confirmed: bool = False
    # Structured-data fields — only set when data_type == "structured"
    data_type: Literal["file", "structured"] = "file"
    connection_id: UUID | None = None
    selection_mode: Literal["tables", "query"] | None = None
    selected_items: list[dict] | None = None
    custom_sql: str | None = None
    # External recipient (non-tenant) — set when sharing_type='external' and the
    # receiver is not another customer tenant.
    external_recipient: ExternalRecipientInline | None = None
    delivery_channel: Literal["portal", "email", "api"] = "portal"


@router.get("/")
async def list_requests(
    page: int = 1, limit: int = 20, status: str | None = None,
    auth_user: AuthUser = Depends(get_current_user),
    service: ShareRequestService = Depends(get_share_request_service),
):
    return await service.list_requests(auth_user, status, page, limit)


@router.post("/")
async def create_request(
    body: CreateShareRequestBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ShareRequestService = Depends(get_share_request_service),
):
    return await service.create_draft(body.model_dump(), auth_user)


@router.get("/{request_id}")
async def get_request(
    request_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: ShareRequestService = Depends(get_share_request_service),
):
    return await service.get_request(request_id, auth_user)


@router.post("/{request_id}/submit")
async def submit_request(
    request_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: ShareRequestService = Depends(get_share_request_service),
):
    return await service.submit_request(request_id, auth_user)


@router.post("/{request_id}/cancel")
async def cancel_request(
    request_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: ShareRequestService = Depends(get_share_request_service),
):
    return await service.cancel_request(request_id, auth_user)

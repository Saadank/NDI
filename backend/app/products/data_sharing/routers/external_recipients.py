from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_sharing.permissions import can_manage_recipients, require
from app.products.data_sharing.services.external_recipient_service import (
    ExternalRecipientService, get_external_recipient_service,
)
from app.products.data_sharing.services.pickup_service import (
    PickupService, get_pickup_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(tags=["external-recipients"])


class UpdateRecipientBody(BaseModel):
    org_name: str | None = None
    notes: str | None = None
    dpa_required: bool | None = None
    is_active: bool | None = None


class AddContactBody(BaseModel):
    email: str
    name: str | None = None
    phone: str | None = None


class UpdateContactBody(BaseModel):
    name: str | None = None
    phone: str | None = None
    is_active: bool | None = None


class RevokeTokenBody(BaseModel):
    reason: str | None = None


@router.get("/external-recipients")
async def list_recipients(
    search: str | None = None, page: int = 1, limit: int = 20,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExternalRecipientService = Depends(get_external_recipient_service),
):
    require(can_manage_recipients(auth_user), "You cannot manage external recipients")
    return await service.list(auth_user.tenant_id, search, page, limit)


@router.get("/external-recipients/{recipient_id}")
async def get_recipient(
    recipient_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExternalRecipientService = Depends(get_external_recipient_service),
):
    require(can_manage_recipients(auth_user), "You cannot manage external recipients")
    return await service.get_detail(recipient_id, auth_user.tenant_id)


@router.patch("/external-recipients/{recipient_id}")
async def update_recipient(
    recipient_id: int, body: UpdateRecipientBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExternalRecipientService = Depends(get_external_recipient_service),
):
    require(can_manage_recipients(auth_user), "You cannot manage external recipients")
    return await service.update(recipient_id, auth_user.tenant_id, body.model_dump(), auth_user)


@router.post("/external-recipients/{recipient_id}/contacts")
async def add_contact(
    recipient_id: int, body: AddContactBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExternalRecipientService = Depends(get_external_recipient_service),
):
    require(can_manage_recipients(auth_user), "You cannot manage external recipients")
    return await service.add_contact(
        recipient_id, auth_user.tenant_id,
        body.email, body.name, body.phone, auth_user,
    )


@router.patch("/recipient-contacts/{contact_id}")
async def update_contact(
    contact_id: int, body: UpdateContactBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExternalRecipientService = Depends(get_external_recipient_service),
):
    require(can_manage_recipients(auth_user), "You cannot manage external recipients")
    return await service.update_contact(contact_id, auth_user.tenant_id, body.model_dump(), auth_user)


@router.post("/pickup-tokens/{token_id}/revoke")
async def revoke_pickup_token(
    token_id: UUID, body: RevokeTokenBody,
    auth_user: AuthUser = Depends(get_current_user),
    pickup: PickupService = Depends(get_pickup_service),
):
    require(can_manage_recipients(auth_user), "You cannot revoke pickup tokens")
    return await pickup.revoke(token_id, auth_user, body.reason)

from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr, Field

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.platform.services.invitation_service import InvitationService, get_invitation_service
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

router = APIRouter(prefix="/invitations", tags=["invitations"])


class CreateInvitationRequest(BaseModel):
    email: EmailStr
    role: str = Field(..., min_length=1)
    product_slug: str | None = None
    product_role: str | None = None
    tenant_id: int | None = None


class AcceptInvitationRequest(BaseModel):
    token: str = Field(..., min_length=1)
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    password: str = Field(..., min_length=8)


@router.get("/")
async def list_invitations(
    auth_user: AuthUser = Depends(get_current_user),
    service: InvitationService = Depends(get_invitation_service),
):
    return await service.list_invitations(auth_user.tenant_id, auth_user)


@router.post("/")
async def create_invitation(
    body: CreateInvitationRequest,
    auth_user: AuthUser = Depends(get_current_user),
    service: InvitationService = Depends(get_invitation_service),
):
    target_tenant_id = auth_user.tenant_id
    if body.tenant_id is not None and body.tenant_id != auth_user.tenant_id:
        if auth_user.platform_role != PlatformRole.PLATFORM_ADMIN:
            raise ForbiddenException("Only platform admins can invite users into another tenant")
        target_tenant_id = body.tenant_id
    return await service.create_invitation(
        tenant_id=target_tenant_id, email=body.email, role=body.role,
        product_slug=body.product_slug, product_role=body.product_role,
        auth_user=auth_user,
    )


@router.post("/accept")
async def accept_invitation(
    body: AcceptInvitationRequest,
    service: InvitationService = Depends(get_invitation_service),
):
    return await service.accept_invitation(body.token, body.first_name, body.last_name, body.password)

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user
from app.platform.services.invitation_service import InvitationService, get_invitation_service
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/invitations", tags=["invitations"])


class CreateInvitationRequest(BaseModel):
    email: str
    role: str
    product_slug: str | None = None
    product_role: str | None = None


class AcceptInvitationRequest(BaseModel):
    token: str
    first_name: str
    last_name: str
    password: str


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
    return await service.create_invitation(
        tenant_id=auth_user.tenant_id, email=body.email, role=body.role,
        product_slug=body.product_slug, product_role=body.product_role,
        auth_user=auth_user,
    )


@router.post("/accept")
async def accept_invitation(
    body: AcceptInvitationRequest,
    service: InvitationService = Depends(get_invitation_service),
):
    return await service.accept_invitation(body.token, body.first_name, body.last_name, body.password)

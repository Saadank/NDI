import logging
import secrets
from datetime import timedelta

from app.core.config import get_settings
from app.gateways.email_gateway import EmailGateway
from app.gateways.keycloak_gateway import KeycloakGateway
from app.platform.repositories.invitation_repository import InvitationRepository
from app.platform.repositories.tenant_repository import TenantRepository
from app.platform.repositories.user_repository import UserRepository
from app.products.data_sharing.permissions import can_manage_users
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException, ValidationException, ResourceNotFoundException
from app.utils.timezone import now

logger = logging.getLogger(__name__)

INVITATION_EXPIRY_HOURS = 72


class InvitationService:

    def __init__(self) -> None:
        self.repo = InvitationRepository()
        self.user_repo = UserRepository()
        self.tenant_repo = TenantRepository()
        self.keycloak = KeycloakGateway()
        self.email_gateway = EmailGateway()

    async def create_invitation(
        self,
        tenant_id: int,
        email: str,
        role: str,
        product_slug: str | None,
        product_role: str | None,
        auth_user: AuthUser,
    ) -> dict:
        if not can_manage_users(auth_user):
            raise ForbiddenException("Only admins and DPOs can send invitations")

        existing = await self.user_repo.find_by_email(email, tenant_id)
        if existing:
            raise ValidationException("User already exists in this organisation")

        # BRD §1.3: enforce the tenant's contracted seat cap. Pending invitations
        # count toward the cap to prevent over-provisioning between invite and accept.
        tenant = await self.tenant_repo.find_by_id(tenant_id)
        seat_limit = (tenant or {}).get("seat_limit")
        if seat_limit is not None:
            active_users = await self.user_repo.count_active(tenant_id)
            pending = await self.repo.count_pending(tenant_id)
            if active_users + pending >= seat_limit:
                raise ValidationException(
                    f"Cannot invite: seat limit of {seat_limit} reached for this organisation"
                )

        token = secrets.token_urlsafe(48)
        expires_at = now() + timedelta(hours=INVITATION_EXPIRY_HOURS)

        invitation = await self.repo.create(
            tenant_id=tenant_id,
            email=email,
            role=role,
            product_slug=product_slug,
            product_role=product_role,
            token=token,
            invited_by=auth_user.user_id,
            expires_at=expires_at,
        )

        settings = get_settings()
        invite_link = f"{settings.FRONTEND_URL}/accept-invitation?token={token}"
        await self.email_gateway.send_html_email(
            from_email=settings.INVITATION_FROM_EMAIL,
            to_email=email,
            subject="You have been invited to the Data Management Platform",
            body=f"<p>You have been invited to join the platform. Click <a href='{invite_link}'>here</a> to accept.</p><p>This invitation expires in {INVITATION_EXPIRY_HOURS} hours.</p>",
        )

        return invitation

    async def accept_invitation(self, token: str, first_name: str, last_name: str, password: str) -> dict:
        invitation = await self.repo.find_by_token(token)
        if not invitation:
            raise ResourceNotFoundException("Invitation not found")

        if invitation["status"] != "pending":
            raise ValidationException("Invitation already processed")

        if invitation["expires_at"] < now():
            raise ValidationException("Invitation has expired")

        keycloak_id = await self.keycloak.create_user(
            username=invitation["email"],
            email=invitation["email"],
            first_name=first_name,
            last_name=last_name,
            password=password,
            roles=[invitation["role"]],
        )

        user = await self.user_repo.create(
            tenant_id=invitation["tenant_id"],
            keycloak_id=keycloak_id,
            email=invitation["email"],
            first_name=first_name,
            last_name=last_name,
            platform_role=invitation["role"],
        )

        await self.repo.update_status(invitation["id"], "accepted")

        return user

    async def list_invitations(self, tenant_id: int, auth_user: AuthUser) -> list[dict]:
        if not can_manage_users(auth_user):
            raise ForbiddenException("Only admins and DPOs can list invitations")
        return await self.repo.find_by_tenant(tenant_id)


def get_invitation_service() -> InvitationService:
    return InvitationService()

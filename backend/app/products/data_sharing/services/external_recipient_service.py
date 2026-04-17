import logging

from app.platform.services.audit_service import AuditService
from app.products.data_sharing.repositories.external_recipient_repository import ExternalRecipientRepository
from app.products.data_sharing.repositories.pickup_token_repository import PickupTokenRepository
from app.products.data_sharing.repositories.recipient_contact_repository import RecipientContactRepository
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException
from app.utils.pagination import get_pagination_data

logger = logging.getLogger(__name__)


class ExternalRecipientService:

    def __init__(self) -> None:
        self.recipients = ExternalRecipientRepository()
        self.contacts = RecipientContactRepository()
        self.tokens = PickupTokenRepository()
        self.audit = AuditService()

    async def upsert_by_email(
        self,
        tenant_id: int,
        org_name: str,
        contact_email: str,
        contact_name: str | None,
        phone: str | None,
        auth_user: AuthUser,
    ) -> tuple[dict, dict]:
        """Find-or-create the recipient org by (tenant, lower(org_name)), then the contact by (recipient, lower(email))."""
        if not org_name or not org_name.strip():
            raise ValidationException("Recipient organisation name is required")
        if not contact_email or "@" not in contact_email:
            raise ValidationException("A valid contact email is required")

        org_name = org_name.strip()
        contact_email = contact_email.strip().lower()

        recipient = await self.recipients.find_by_org_name_in_tenant(tenant_id, org_name)
        if not recipient:
            recipient = await self.recipients.create(
                tenant_id=tenant_id, org_name=org_name, notes=None,
                dpa_required=True, created_by=auth_user.user_id,
            )
            await self.audit.log(
                tenant_id=tenant_id, action_type="recipient.created",
                resource_type="external_recipient", resource_id=str(recipient["id"]),
                actor_id=auth_user.user_id, after_state=recipient,
            )

        contact = await self.contacts.find_by_recipient_and_email(recipient["id"], contact_email)
        if not contact:
            contact = await self.contacts.create(
                recipient_id=recipient["id"], email=contact_email,
                name=contact_name, phone=phone, created_by=auth_user.user_id,
            )
            await self.audit.log(
                tenant_id=tenant_id, action_type="recipient.contact_added",
                resource_type="recipient_contact", resource_id=str(contact["id"]),
                actor_id=auth_user.user_id,
                metadata={"recipient_id": recipient["id"]},
                after_state=contact,
            )
        return recipient, contact

    async def list(self, tenant_id: int, search: str | None,
                   page: int, limit: int) -> dict:
        rows = await self.recipients.list_by_tenant(tenant_id, search, page, limit)
        total = await self.recipients.count_by_tenant(tenant_id, search)
        # Enrich each row with a contact count.
        for row in rows:
            contacts = await self.contacts.list_for_recipient(row["id"])
            row["contacts_count"] = len(contacts)
        pagination = get_pagination_data(limit, page, total)
        return {"data": rows, **pagination}

    async def get_detail(self, recipient_id: int, tenant_id: int) -> dict:
        recipient = await self.recipients.find_by_id(recipient_id, tenant_id)
        if not recipient:
            raise ResourceNotFoundException("External recipient not found")
        recipient["contacts"] = await self.contacts.list_for_recipient(recipient_id)
        active_tokens = await self.tokens.list_by_recipient(recipient_id, active_only=True)
        # Strip the hash from the response — never expose it.
        for t in active_tokens:
            t.pop("token_hash", None)
        recipient["active_tokens"] = active_tokens
        return recipient

    async def add_contact(self, recipient_id: int, tenant_id: int, email: str,
                          name: str | None, phone: str | None, auth_user: AuthUser) -> dict:
        recipient = await self.recipients.find_by_id(recipient_id, tenant_id)
        if not recipient:
            raise ResourceNotFoundException("External recipient not found")
        if not email or "@" not in email:
            raise ValidationException("A valid contact email is required")
        email = email.strip().lower()
        existing = await self.contacts.find_by_recipient_and_email(recipient_id, email)
        if existing:
            raise ValidationException("A contact with this email already exists for this recipient")
        contact = await self.contacts.create(
            recipient_id=recipient_id, email=email, name=name,
            phone=phone, created_by=auth_user.user_id,
        )
        await self.audit.log(
            tenant_id=tenant_id, action_type="recipient.contact_added",
            resource_type="recipient_contact", resource_id=str(contact["id"]),
            actor_id=auth_user.user_id, metadata={"recipient_id": recipient_id},
            after_state=contact,
        )
        return contact

    async def update(self, recipient_id: int, tenant_id: int, fields: dict, auth_user: AuthUser) -> dict:
        existing = await self.recipients.find_by_id(recipient_id, tenant_id)
        if not existing:
            raise ResourceNotFoundException("External recipient not found")
        # Whitelist updatable columns.
        allowed = {k: v for k, v in fields.items() if k in ("org_name", "notes", "dpa_required", "is_active") and v is not None}
        if not allowed:
            return existing
        allowed["updated_by"] = auth_user.user_id
        updated = await self.recipients.update(recipient_id, tenant_id, **allowed)
        action = "recipient.deactivated" if allowed.get("is_active") is False else "recipient.updated"
        await self.audit.log(
            tenant_id=tenant_id, action_type=action,
            resource_type="external_recipient", resource_id=str(recipient_id),
            actor_id=auth_user.user_id,
            before_state=existing, after_state=updated,
        )
        return updated

    async def update_contact(self, contact_id: int, tenant_id: int, fields: dict, auth_user: AuthUser) -> dict:
        existing = await self.contacts.find_by_id(contact_id)
        if not existing:
            raise ResourceNotFoundException("Contact not found")
        recipient = await self.recipients.find_by_id(existing["recipient_id"], tenant_id)
        if not recipient:
            raise ResourceNotFoundException("Contact not found")
        allowed = {k: v for k, v in fields.items() if k in ("name", "phone", "is_active") and v is not None}
        if not allowed:
            return existing
        updated = await self.contacts.update(contact_id, **allowed)
        await self.audit.log(
            tenant_id=tenant_id, action_type="recipient.contact_updated",
            resource_type="recipient_contact", resource_id=str(contact_id),
            actor_id=auth_user.user_id,
            before_state=existing, after_state=updated,
        )
        return updated


def get_external_recipient_service() -> ExternalRecipientService:
    return ExternalRecipientService()

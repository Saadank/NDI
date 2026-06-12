"""Glossary domain service — hierarchy CRUD + steward assignment.

Authorization is domain-scoped (see glossary_permissions): Org Admin manages
top-level domains; Data Owners manage their own subtree.
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.products.ndmo_compliance import glossary_permissions as perm
from app.products.ndmo_compliance.entities.glossary_domain import GlossaryDomain
from app.products.ndmo_compliance.glossary_permissions import GlossaryActor
from app.products.ndmo_compliance.repositories.glossary_domain_repository import (
    GlossaryDomainRepository,
)
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)

_ADMIN_PLATFORM_ROLES = {"org_admin", "platform_admin"}


class GlossaryDomainService:
    def __init__(self) -> None:
        self._domains = GlossaryDomainRepository()

    # ---- actor resolution (shared by all glossary routers) --------------

    async def resolve_actor(self, auth_user: AuthUser) -> GlossaryActor:
        tenant_id = auth_user.tenant_id
        platform_role = (
            auth_user.platform_role.value
            if auth_user.platform_role is not None
            else None
        )
        is_admin = platform_role in _ADMIN_PLATFORM_ROLES
        owned = await self._domains.owned_domain_ids(
            tenant_id=tenant_id, user_id=auth_user.user_id
        )
        steward = await self._domains.steward_domain_ids(
            tenant_id=tenant_id, user_id=auth_user.user_id
        )
        return GlossaryActor(
            user_id=auth_user.user_id,
            tenant_id=tenant_id,
            is_org_admin=is_admin,
            owned_domain_ids=set(owned),
            steward_domain_ids=set(steward),
        )

    # ---- reads ----------------------------------------------------------

    async def list_domains(
        self, *, auth_user: AuthUser, include_archived: bool = False
    ) -> list[GlossaryDomain]:
        return await self._domains.list_all(
            tenant_id=auth_user.tenant_id, include_archived=include_archived
        )

    async def get_domain(
        self, *, domain_id: UUID, auth_user: AuthUser
    ) -> GlossaryDomain:
        return await self._domains.find_by_id(
            domain_id=domain_id, tenant_id=auth_user.tenant_id
        )

    async def list_users(
        self, *, auth_user: AuthUser, search: str | None = None
    ) -> list[dict]:
        rows = await self._domains.list_users(
            tenant_id=auth_user.tenant_id, search=search
        )
        out = []
        for r in rows:
            name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            out.append({
                "id": r["id"],
                "name": name or r["email"],
                "email": r["email"],
            })
        return out

    # ---- writes ---------------------------------------------------------

    async def create_top_level(
        self, *, auth_user: AuthUser, name_en: str, name_ar: str | None,
        description_en: str | None, description_ar: str | None,
        owner_user_id: int | None,
    ) -> GlossaryDomain:
        actor = await self.resolve_actor(auth_user)
        perm.require(
            perm.can_create_top_level_domain(actor),
            "Only an Org Admin can create top-level domains.",
        )
        return await self._domains.create(
            tenant_id=auth_user.tenant_id, name_en=name_en, name_ar=name_ar,
            description_en=description_en, description_ar=description_ar,
            owner_user_id=owner_user_id, parent_id=None,
            created_by=auth_user.user_id,
        )

    async def create_subdomain(
        self, *, auth_user: AuthUser, parent_id: UUID, name_en: str,
        name_ar: str | None, description_en: str | None,
        description_ar: str | None, owner_user_id: int | None,
        steward_user_ids: list[int] | None = None,
    ) -> GlossaryDomain:
        actor = await self.resolve_actor(auth_user)
        perm.require(
            perm.can_create_subdomain(actor, parent_id),
            "You can only add sub-domains under a domain you own.",
        )
        parent = await self._domains.find_by_id(
            domain_id=parent_id, tenant_id=auth_user.tenant_id
        )
        # Owner inherits from parent unless overridden (BRD WF-04 step 4).
        # A Steward (not the owner/admin) cannot reassign ownership — the
        # sub-domain always inherits the parent's owner for them.
        may_set_owner = actor.is_org_admin or actor.owns(parent_id)
        resolved_owner = (owner_user_id if may_set_owner else None) or parent.owner_user_id
        domain = await self._domains.create(
            tenant_id=auth_user.tenant_id, name_en=name_en, name_ar=name_ar,
            description_en=description_en, description_ar=description_ar,
            owner_user_id=resolved_owner, parent_id=parent_id,
            created_by=auth_user.user_id,
        )
        for uid in steward_user_ids or []:
            await self._domains.add_steward(
                tenant_id=auth_user.tenant_id, domain_id=domain.id,
                user_id=uid, assigned_by=auth_user.user_id,
            )
        domain.steward_ids = list(steward_user_ids or [])
        return domain

    async def update_domain(
        self, *, auth_user: AuthUser, domain_id: UUID, **fields
    ) -> GlossaryDomain:
        actor = await self.resolve_actor(auth_user)
        # Reassigning the owner is Admin-only (BRD FR-004); other metadata
        # edits are allowed for the domain owner too.
        if fields.get("owner_user_id") is not None:
            perm.require(actor.is_org_admin, "Only an Org Admin can reassign a domain owner.")
        else:
            perm.require(
                perm.can_manage_domain(actor, domain_id),
                "You do not manage this domain.",
            )
        return await self._domains.update(
            domain_id=domain_id, tenant_id=auth_user.tenant_id, **fields
        )

    async def archive_domain(self, *, auth_user: AuthUser, domain_id: UUID) -> None:
        actor = await self.resolve_actor(auth_user)
        perm.require(
            perm.can_manage_domain(actor, domain_id),
            "You do not manage this domain.",
        )
        await self._domains.archive(
            domain_id=domain_id, tenant_id=auth_user.tenant_id
        )

    async def assign_steward(
        self, *, auth_user: AuthUser, domain_id: UUID, user_id: int
    ) -> None:
        actor = await self.resolve_actor(auth_user)
        perm.require(
            perm.can_assign_steward(actor, domain_id),
            "Only the domain owner or an Org Admin can assign stewards.",
        )
        await self._domains.add_steward(
            tenant_id=auth_user.tenant_id, domain_id=domain_id,
            user_id=user_id, assigned_by=auth_user.user_id,
        )

    async def remove_steward(
        self, *, auth_user: AuthUser, domain_id: UUID, user_id: int
    ) -> None:
        actor = await self.resolve_actor(auth_user)
        perm.require(
            perm.can_manage_domain(actor, domain_id),
            "Only the domain owner or an Org Admin can remove stewards.",
        )
        await self._domains.remove_steward(
            tenant_id=auth_user.tenant_id, domain_id=domain_id, user_id=user_id
        )


def get_glossary_domain_service() -> GlossaryDomainService:
    return GlossaryDomainService()

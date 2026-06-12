"""Domain-scoped RBAC for the Business Glossary (BRD §3).

Three roles, but unlike the platform's flat product-role model these are
*derived from data*: a user is a Data Owner of the domains whose
``owner_user_id`` is theirs, and a Data Steward of the domains they appear in
under ``t_glossary_domain_stewards``.  Org Admin is the platform org_admin /
platform_admin.

A ``GlossaryActor`` snapshots those sets for one request; the capability
helpers below answer authorization questions against it.  Routers resolve the
actor once (via GlossaryTermService.resolve_actor) and pass it down.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from fastapi import HTTPException

from app.products.ndmo_compliance.entities.glossary_term import GlossaryTerm
from app.products.ndmo_compliance.enums.glossary_term_type import GlossaryTermType


@dataclass(slots=True)
class GlossaryActor:
    user_id: int
    tenant_id: int
    is_org_admin: bool
    owned_domain_ids: set[UUID] = field(default_factory=set)
    steward_domain_ids: set[UUID] = field(default_factory=set)

    # ---- role label (for the frontend / sidebar gating) -----------------
    @property
    def effective_role(self) -> str:
        if self.is_org_admin:
            return "org_admin"
        if self.owned_domain_ids:
            return "glossary_data_owner"
        if self.steward_domain_ids:
            return "glossary_data_steward"
        return "glossary_viewer"

    def owns(self, domain_id: UUID | None) -> bool:
        return domain_id is not None and domain_id in self.owned_domain_ids

    def stewards(self, domain_id: UUID | None) -> bool:
        return domain_id is not None and domain_id in self.steward_domain_ids

    def assigned_domain_ids(self) -> set[UUID]:
        return self.owned_domain_ids | self.steward_domain_ids


# ---- capability checks (return bool) ------------------------------------

def can_create_top_level_domain(actor: GlossaryActor) -> bool:
    return actor.is_org_admin


def can_create_subdomain(actor: GlossaryActor, parent_id: UUID) -> bool:
    # Org Admin, the parent's Data Owner, OR a Data Steward of the parent
    # domain may add sub-domains (BRD: stewards can create sub-domains).
    return (
        actor.is_org_admin
        or actor.owns(parent_id)
        or actor.stewards(parent_id)
    )


def can_manage_domain(actor: GlossaryActor, domain_id: UUID) -> bool:
    """Edit metadata / reassign owner / archive — Org Admin or the owner."""
    return actor.is_org_admin or actor.owns(domain_id)


def can_assign_steward(actor: GlossaryActor, domain_id: UUID) -> bool:
    """Assigning stewards is the Data Owner's (or Org Admin's) right."""
    return actor.is_org_admin or actor.owns(domain_id)


def can_create_term(
    actor: GlossaryActor, domain_id: UUID | None, term_type: str
) -> bool:
    if term_type == GlossaryTermType.ENTERPRISE:
        return actor.is_org_admin          # enterprise terms: Admin only
    if domain_id is None:
        return False
    return (
        actor.is_org_admin
        or actor.owns(domain_id)
        or actor.stewards(domain_id)
    )


def can_edit_term(actor: GlossaryActor, term: GlossaryTerm) -> bool:
    if term.term_type == GlossaryTermType.ENTERPRISE:
        return actor.is_org_admin
    return (
        actor.is_org_admin
        or actor.owns(term.domain_id)
        or actor.stewards(term.domain_id)
    )


def can_approve_term(actor: GlossaryActor, term: GlossaryTerm) -> bool:
    if term.term_type == GlossaryTermType.ENTERPRISE:
        return actor.is_org_admin          # enterprise: Org Admin approves
    return actor.is_org_admin or actor.owns(term.domain_id)


def can_deprecate_term(actor: GlossaryActor, term: GlossaryTerm) -> bool:
    return can_approve_term(actor, term)   # same authority as approval


# ---- enforcement (raise 403) --------------------------------------------

def require(condition: bool, detail: str) -> None:
    if not condition:
        raise HTTPException(status_code=403, detail=detail)

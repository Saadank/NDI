"""Glossary term service — authoring + the governed lifecycle state machine.

Lifecycle (BRD §5.3):
    draft --submit--> under_review --approve--> approved
    under_review --request_changes|reject--> draft   (new term)
    approved --edit--> under_review (published stays live via version snapshot)
    approved --deprecate--> deprecated --reinstate--> draft

Edit-of-published (WF-03): editing an approved term snapshots the live content
as the *published version* and applies the edit to the working row in
under_review.  On approval the edit becomes the new published version; on
reject the published snapshot is restored.  (Slice-1 simplification:
request_changes on an *edit* also restores the published snapshot rather than
keeping a separate pending-content draft — the published term must stay live
and the single content row can't hold both.  New-term request_changes keeps
the draft as expected.)

Authorization is domain-scoped — see glossary_permissions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.products.ndmo_compliance import glossary_permissions as perm
from app.products.ndmo_compliance.entities.glossary_term import GlossaryTerm
from app.products.ndmo_compliance.enums.glossary_review_decision import (
    GlossaryReviewDecision,
)
from app.products.ndmo_compliance.enums.glossary_status import GlossaryTermStatus
from app.products.ndmo_compliance.enums.glossary_term_type import GlossaryTermType
from app.products.ndmo_compliance.glossary_permissions import GlossaryActor
from app.products.ndmo_compliance.repositories.glossary_review_repository import (
    GlossaryReviewRepository,
)
from app.products.ndmo_compliance.repositories.glossary_term_repository import (
    GlossaryTermRepository,
)
from app.products.ndmo_compliance.services.glossary_domain_service import (
    GlossaryDomainService,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ConflictException, ValidationException

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TermDetail:
    term: GlossaryTerm
    relations: list[dict]
    versions: list[dict]
    reviews: list[dict]
    published_snapshot: dict | None


@dataclass(slots=True)
class DuplicateWarning:
    existing_term_id: str
    existing_name_en: str


class GlossaryTermService:
    def __init__(self) -> None:
        self._terms = GlossaryTermRepository()
        self._reviews = GlossaryReviewRepository()
        self._domains = GlossaryDomainService()

    async def resolve_actor(self, auth_user: AuthUser) -> GlossaryActor:
        return await self._domains.resolve_actor(auth_user)

    # ---- create ---------------------------------------------------------

    async def create_term(
        self, *, auth_user: AuthUser, name_en: str, domain_id: UUID | None,
        term_type: str, name_ar: str | None = None,
        definition_en: str | None = None, definition_ar: str | None = None,
        acronym: str | None = None, examples: str | None = None,
        business_rule: str | None = None, source: str = "manual",
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        perm.require(
            perm.can_create_term(actor, domain_id, term_type),
            "You cannot create a term in this domain. "
            "Stewards/owners may only author terms in their assigned domains; "
            "enterprise terms are Org-Admin-only.",
        )
        if term_type == GlossaryTermType.DOMAIN and domain_id is None:
            raise ValidationException("A domain is required for a domain-scoped term.")
        if term_type == GlossaryTermType.ENTERPRISE:
            domain_id = None
        return await self._terms.create(
            tenant_id=auth_user.tenant_id, name_en=name_en,
            created_by=auth_user.user_id, domain_id=domain_id,
            term_type=term_type, source=source, name_ar=name_ar,
            definition_en=definition_en, definition_ar=definition_ar,
            acronym=acronym, examples=examples, business_rule=business_rule,
            steward_user_id=auth_user.user_id,
        )

    async def check_duplicate(
        self, *, auth_user: AuthUser, name_en: str, domain_id: UUID | None
    ) -> DuplicateWarning | None:
        dup = await self._terms.find_duplicate(
            tenant_id=auth_user.tenant_id, domain_id=domain_id, name_en=name_en
        )
        if dup is None:
            return None
        return DuplicateWarning(existing_term_id=str(dup.id), existing_name_en=dup.name_en)

    # ---- read -----------------------------------------------------------

    async def get_term_detail(
        self, *, auth_user: AuthUser, term_id: UUID
    ) -> TermDetail:
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        relations = await self._terms.list_relations(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        versions = await self._terms.list_versions(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        reviews = await self._reviews.list_for_term(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        published_snapshot = None
        if term.published_version_id is not None:
            published_snapshot = next(
                (v["snapshot"] for v in versions
                 if v["id"] == term.published_version_id),
                None,
            )
        return TermDetail(
            term=term, relations=relations, versions=versions,
            reviews=reviews, published_snapshot=published_snapshot,
        )

    async def list_terms(
        self, *, auth_user: AuthUser, domain_id: UUID | None = None,
        status: str | None = None, term_type: str | None = None,
        search: str | None = None, scope: str = "all",
        include_deprecated: bool = False,
    ) -> list[GlossaryTerm]:
        """scope='my' restricts to the actor's owned + steward domains."""
        domain_ids = None
        if scope == "my":
            actor = await self.resolve_actor(auth_user)
            if not actor.is_org_admin:
                domain_ids = list(actor.assigned_domain_ids()) or [_NIL_UUID]
        return await self._terms.list_terms(
            tenant_id=auth_user.tenant_id, domain_id=domain_id,
            domain_ids=domain_ids, status=status, term_type=term_type,
            search=search, include_deprecated=include_deprecated,
        )

    # ---- edit (draft) ---------------------------------------------------

    async def update_term(
        self, *, auth_user: AuthUser, term_id: UUID, **fields
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_edit_term(actor, term), "You cannot edit this term.")

        if term.status == GlossaryTermStatus.APPROVED:
            # Editing a published term forks an under_review edit while the
            # published version stays live (WF-03).
            return await self._fork_edit(auth_user, term, fields)
        if term.status == GlossaryTermStatus.UNDER_REVIEW:
            raise ConflictException("Term is under review; cancel the review before editing.")
        return await self._terms.update_fields(
            term_id=term_id, tenant_id=auth_user.tenant_id, **fields
        )

    async def _fork_edit(
        self, auth_user: AuthUser, term: GlossaryTerm, fields: dict
    ) -> GlossaryTerm:
        # Snapshot the live content as the published version if not already.
        published_id = term.published_version_id
        if published_id is None:
            published_id = await self._terms.add_version(
                tenant_id=auth_user.tenant_id, term_id=term.id,
                version=term.version, snapshot=_snapshot(term),
                changed_by=auth_user.user_id,
            )
        updated = await self._terms.update_fields(
            term_id=term.id, tenant_id=auth_user.tenant_id, **fields
        )
        # Keep published pointer, move to under_review.
        await self._terms.set_status(
            term_id=term.id, tenant_id=auth_user.tenant_id, status="under_review"
        )
        await self._terms._execute(  # noqa: SLF001 — set published pointer
            "UPDATE ndmo.t_glossary_terms SET published_version_id = $3 "
            "WHERE id = $1 AND tenant_id = $2",
            (term.id, auth_user.tenant_id, published_id),
        )
        updated.status = GlossaryTermStatus.UNDER_REVIEW
        updated.published_version_id = published_id
        return updated

    # ---- lifecycle transitions ------------------------------------------

    async def submit_for_review(
        self, *, auth_user: AuthUser, term_id: UUID
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_edit_term(actor, term), "You cannot submit this term.")
        if term.status not in (
            GlossaryTermStatus.DRAFT,
            GlossaryTermStatus.CHANGES_REQUESTED,
        ):
            raise ConflictException("Only a draft term can be submitted for review.")
        if not term.name_en or not term.definition_en:
            raise ValidationException("Name (EN) and Definition (EN) are required to submit.")
        return await self._terms.set_status(
            term_id=term_id, tenant_id=auth_user.tenant_id, status="under_review"
        )

    async def cancel_review(
        self, *, auth_user: AuthUser, term_id: UUID
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_edit_term(actor, term), "You cannot cancel this review.")
        if term.status != GlossaryTermStatus.UNDER_REVIEW:
            raise ConflictException("Term is not under review.")
        # An edit-in-review reverts to approved; a new term reverts to draft.
        target = "approved" if term.published_version_id else "draft"
        return await self._terms.set_status(
            term_id=term_id, tenant_id=auth_user.tenant_id, status=target
        )

    async def review(
        self, *, auth_user: AuthUser, term_id: UUID, decision: str,
        note: str | None,
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(
            perm.can_approve_term(actor, term),
            "You are not the Data Owner for this term's domain."
            if term.term_type == GlossaryTermType.DOMAIN
            else "Only an Org Admin can review enterprise terms.",
        )
        if term.status != GlossaryTermStatus.UNDER_REVIEW:
            raise ConflictException("Only a term under review can be reviewed.")
        if decision in (GlossaryReviewDecision.REQUEST_CHANGES,
                        GlossaryReviewDecision.REJECT) and not (note and note.strip()):
            raise ValidationException("A note is required to request changes or reject.")

        await self._reviews.add(
            tenant_id=auth_user.tenant_id, term_id=term_id,
            reviewer_id=auth_user.user_id, decision=decision,
            version=term.version, note=note,
        )

        if decision == GlossaryReviewDecision.APPROVE:
            return await self._approve(auth_user, term)
        return await self._return_to_author(auth_user, term, decision)

    async def _approve(self, auth_user: AuthUser, term: GlossaryTerm) -> GlossaryTerm:
        is_edit = term.published_version_id is not None
        new_version = term.version + 1 if is_edit else term.version
        snapshot_id = await self._terms.add_version(
            tenant_id=auth_user.tenant_id, term_id=term.id,
            version=new_version, snapshot=_snapshot(term),
            changed_by=auth_user.user_id,
        )
        return await self._terms.bump_version_and_approve(
            term_id=term.id, tenant_id=auth_user.tenant_id,
            new_version=new_version, published_version_id=snapshot_id,
        )

    async def _return_to_author(
        self, auth_user: AuthUser, term: GlossaryTerm, decision: str
    ) -> GlossaryTerm:
        if term.published_version_id is None:
            # New term — request_changes keeps it visibly "Changes Requested"
            # (steward edits & resubmits); reject sends it back to plain draft.
            target = (
                "changes_requested"
                if decision == GlossaryReviewDecision.REQUEST_CHANGES
                else "draft"
            )
            return await self._terms.set_status(
                term_id=term.id, tenant_id=auth_user.tenant_id, status=target
            )
        # Edit of a published term — discard the edit, restore the live
        # published snapshot, term stays approved.
        versions = await self._terms.list_versions(
            term_id=term.id, tenant_id=auth_user.tenant_id
        )
        snap = next(
            (v["snapshot"] for v in versions if v["id"] == term.published_version_id),
            None,
        )
        if snap:
            await self._terms.update_fields(
                term_id=term.id, tenant_id=auth_user.tenant_id,
                name_en=snap.get("name_en"), name_ar=snap.get("name_ar"),
                definition_en=snap.get("definition_en"),
                definition_ar=snap.get("definition_ar"),
                acronym=snap.get("acronym"), examples=snap.get("examples"),
                business_rule=snap.get("business_rule"),
            )
        return await self._terms.set_status(
            term_id=term.id, tenant_id=auth_user.tenant_id, status="approved"
        )

    async def deprecate(
        self, *, auth_user: AuthUser, term_id: UUID, reason: str,
        replacement_term_id: UUID | None,
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_deprecate_term(actor, term), "You cannot deprecate this term.")
        if term.status != GlossaryTermStatus.APPROVED:
            raise ConflictException("Only an approved term can be deprecated.")
        if not (reason and reason.strip()):
            raise ValidationException("A reason is required to deprecate a term.")
        return await self._terms.deprecate(
            term_id=term_id, tenant_id=auth_user.tenant_id, reason=reason,
            replaced_by_term_id=replacement_term_id,
        )

    async def reinstate(
        self, *, auth_user: AuthUser, term_id: UUID
    ) -> GlossaryTerm:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_deprecate_term(actor, term), "You cannot reinstate this term.")
        if term.status != GlossaryTermStatus.DEPRECATED:
            raise ConflictException("Only a deprecated term can be reinstated.")
        return await self._terms.set_status(
            term_id=term_id, tenant_id=auth_user.tenant_id, status="draft"
        )

    async def delete_term(self, *, auth_user: AuthUser, term_id: UUID) -> None:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_edit_term(actor, term), "You cannot delete this term.")
        ok = await self._terms.delete(term_id=term_id, tenant_id=auth_user.tenant_id)
        if not ok:
            raise ConflictException("Only a draft term can be deleted.")

    # ---- relations ------------------------------------------------------

    async def add_relation(
        self, *, auth_user: AuthUser, term_id: UUID, target_term_id: UUID,
        relation_type: str,
    ) -> None:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_edit_term(actor, term), "You cannot edit this term.")
        await self._terms.add_relation(
            tenant_id=auth_user.tenant_id, source_term_id=term_id,
            target_term_id=target_term_id, relation_type=relation_type,
        )

    async def remove_relation(
        self, *, auth_user: AuthUser, term_id: UUID, relation_id: UUID
    ) -> None:
        actor = await self.resolve_actor(auth_user)
        term = await self._terms.find_by_id(
            term_id=term_id, tenant_id=auth_user.tenant_id
        )
        perm.require(perm.can_edit_term(actor, term), "You cannot edit this term.")
        await self._terms.remove_relation(
            tenant_id=auth_user.tenant_id, relation_id=relation_id
        )

    # ---- review queue ---------------------------------------------------

    async def review_queue(self, *, auth_user: AuthUser) -> list[GlossaryTerm]:
        actor = await self.resolve_actor(auth_user)
        domain_ids = list(actor.owned_domain_ids)
        terms = await self._terms.list_terms(
            tenant_id=auth_user.tenant_id, status="under_review",
            domain_ids=domain_ids or ([_NIL_UUID] if not actor.is_org_admin else None),
        )
        if actor.is_org_admin:
            # Admin also sees enterprise terms under review (already included
            # by the unfiltered query above when domain_ids is None).
            return terms
        # Owners also review enterprise? No — enterprise is Admin-only.
        return terms

    async def review_queue_count(self, *, auth_user: AuthUser) -> int:
        actor = await self.resolve_actor(auth_user)
        return await self._terms.count_under_review_for_domains(
            tenant_id=auth_user.tenant_id,
            domain_ids=list(actor.owned_domain_ids),
            include_enterprise=actor.is_org_admin,
        )


# Sentinel so a "my domains" / owner query with no domains returns nothing
# rather than everything.
_NIL_UUID = UUID("00000000-0000-0000-0000-000000000000")


def _snapshot(term: GlossaryTerm) -> dict:
    return {
        "name_en": term.name_en,
        "name_ar": term.name_ar,
        "definition_en": term.definition_en,
        "definition_ar": term.definition_ar,
        "acronym": term.acronym,
        "examples": term.examples,
        "business_rule": term.business_rule,
        "term_type": str(term.term_type),
        "domain_id": str(term.domain_id) if term.domain_id else None,
    }


def get_glossary_term_service() -> GlossaryTermService:
    return GlossaryTermService()

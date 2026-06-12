"""Term-management endpoints for the Business Glossary.

Mounted under ``/api/v1/products/ndmo-compliance/glossary``.  Covers the term
lifecycle (create → submit → review → approve/deprecate), versions, relations,
and the Data Owner's review queue.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.ndmo_compliance.entities.glossary_term import GlossaryTerm
from app.products.ndmo_compliance.services.glossary_term_service import (
    GlossaryTermService,
    get_glossary_term_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/glossary/terms", tags=["ndmo-glossary-terms"])


# ---------- shapes -------------------------------------------------------


class TermCreateBody(BaseModel):
    name_en: str = Field(..., min_length=1, max_length=255)
    domain_id: UUID | None = None
    term_type: str = Field(default="domain", pattern="^(domain|enterprise)$")
    name_ar: str | None = Field(default=None, max_length=255)
    definition_en: str | None = None
    definition_ar: str | None = None
    acronym: str | None = Field(default=None, max_length=50)
    examples: str | None = None
    business_rule: str | None = None
    source: str = Field(default="manual", pattern="^(manual|llm_assisted|db_extracted)$")


class TermUpdateBody(BaseModel):
    name_en: str | None = Field(default=None, max_length=255)
    name_ar: str | None = Field(default=None, max_length=255)
    definition_en: str | None = None
    definition_ar: str | None = None
    acronym: str | None = Field(default=None, max_length=50)
    examples: str | None = None
    business_rule: str | None = None


class ReviewBody(BaseModel):
    decision: str = Field(..., pattern="^(approve|request_changes|reject)$")
    note: str | None = None


class DeprecateBody(BaseModel):
    reason: str = Field(..., min_length=1)
    replacement_term_id: UUID | None = None


class RelationBody(BaseModel):
    target_term_id: UUID
    relation_type: str = Field(..., pattern="^(synonym|related|parent_of|calculated_from)$")


class TermResponse(BaseModel):
    id: str
    domain_id: str | None
    name_en: str
    name_ar: str | None
    definition_en: str | None
    definition_ar: str | None
    acronym: str | None
    examples: str | None
    business_rule: str | None
    status: str
    term_type: str
    source: str
    owner_user_id: int | None
    steward_user_id: int | None
    created_by: int
    version: int
    published_version_id: str | None
    pending_version_id: str | None
    deprecation_reason: str | None
    replaced_by_term_id: str | None
    created_at: str
    updated_at: str
    approved_at: str | None
    deprecated_at: str | None


class TermDetailResponse(TermResponse):
    relations: list[dict]
    versions: list[dict]
    reviews: list[dict]
    published_snapshot: dict | None


class DuplicateResponse(BaseModel):
    duplicate: bool
    existing_term_id: str | None = None
    existing_name_en: str | None = None


def _term_to_response(t: GlossaryTerm) -> dict:
    return {
        "id": str(t.id),
        "domain_id": str(t.domain_id) if t.domain_id else None,
        "name_en": t.name_en,
        "name_ar": t.name_ar,
        "definition_en": t.definition_en,
        "definition_ar": t.definition_ar,
        "acronym": t.acronym,
        "examples": t.examples,
        "business_rule": t.business_rule,
        "status": str(t.status),
        "term_type": str(t.term_type),
        "source": str(t.source),
        "owner_user_id": t.owner_user_id,
        "steward_user_id": t.steward_user_id,
        "created_by": t.created_by,
        "version": t.version,
        "published_version_id": str(t.published_version_id) if t.published_version_id else None,
        "pending_version_id": str(t.pending_version_id) if t.pending_version_id else None,
        "deprecation_reason": t.deprecation_reason,
        "replaced_by_term_id": str(t.replaced_by_term_id) if t.replaced_by_term_id else None,
        "created_at": t.created_at.isoformat(),
        "updated_at": t.updated_at.isoformat(),
        "approved_at": t.approved_at.isoformat() if t.approved_at else None,
        "deprecated_at": t.deprecated_at.isoformat() if t.deprecated_at else None,
    }


# ---------- list / queue (static paths before /{term_id}) ----------------


@router.get("", response_model=list[TermResponse])
async def list_terms(
    domain_id: UUID | None = Query(default=None),
    status: str | None = Query(default=None),
    term_type: str | None = Query(default=None),
    search: str | None = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|my)$"),
    include_deprecated: bool = Query(default=False),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    terms = await service.list_terms(
        auth_user=auth_user, domain_id=domain_id, status=status,
        term_type=term_type, search=search, scope=scope,
        include_deprecated=include_deprecated,
    )
    return [_term_to_response(t) for t in terms]


@router.get("/review-queue", response_model=list[TermResponse])
async def review_queue(
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    terms = await service.review_queue(auth_user=auth_user)
    return [_term_to_response(t) for t in terms]


@router.post("/check-duplicate", response_model=DuplicateResponse)
async def check_duplicate(
    name_en: str = Query(..., min_length=1),
    domain_id: UUID | None = Query(default=None),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    dup = await service.check_duplicate(
        auth_user=auth_user, name_en=name_en, domain_id=domain_id
    )
    if dup is None:
        return DuplicateResponse(duplicate=False)
    return DuplicateResponse(
        duplicate=True, existing_term_id=dup.existing_term_id,
        existing_name_en=dup.existing_name_en,
    )


@router.post("", response_model=TermResponse, status_code=201)
async def create_term(
    body: TermCreateBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    term = await service.create_term(
        auth_user=auth_user, name_en=body.name_en, domain_id=body.domain_id,
        term_type=body.term_type, name_ar=body.name_ar,
        definition_en=body.definition_en, definition_ar=body.definition_ar,
        acronym=body.acronym, examples=body.examples,
        business_rule=body.business_rule, source=body.source,
    )
    return _term_to_response(term)


# ---------- single term --------------------------------------------------


@router.get("/{term_id}", response_model=TermDetailResponse)
async def get_term(
    term_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    detail = await service.get_term_detail(auth_user=auth_user, term_id=term_id)
    return {
        **_term_to_response(detail.term),
        "relations": detail.relations,
        "versions": detail.versions,
        "reviews": detail.reviews,
        "published_snapshot": detail.published_snapshot,
    }


@router.put("/{term_id}", response_model=TermResponse)
async def update_term(
    term_id: UUID,
    body: TermUpdateBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    term = await service.update_term(
        auth_user=auth_user, term_id=term_id,
        **body.model_dump(exclude_none=True),
    )
    return _term_to_response(term)


@router.delete("/{term_id}", status_code=204)
async def delete_term(
    term_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    await service.delete_term(auth_user=auth_user, term_id=term_id)


@router.post("/{term_id}/submit", response_model=TermResponse)
async def submit_term(
    term_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    return _term_to_response(
        await service.submit_for_review(auth_user=auth_user, term_id=term_id)
    )


@router.post("/{term_id}/cancel-review", response_model=TermResponse)
async def cancel_review(
    term_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    return _term_to_response(
        await service.cancel_review(auth_user=auth_user, term_id=term_id)
    )


@router.post("/{term_id}/review", response_model=TermResponse)
async def review_term(
    term_id: UUID,
    body: ReviewBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    return _term_to_response(
        await service.review(
            auth_user=auth_user, term_id=term_id,
            decision=body.decision, note=body.note,
        )
    )


@router.post("/{term_id}/deprecate", response_model=TermResponse)
async def deprecate_term(
    term_id: UUID,
    body: DeprecateBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    return _term_to_response(
        await service.deprecate(
            auth_user=auth_user, term_id=term_id, reason=body.reason,
            replacement_term_id=body.replacement_term_id,
        )
    )


@router.post("/{term_id}/reinstate", response_model=TermResponse)
async def reinstate_term(
    term_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    return _term_to_response(
        await service.reinstate(auth_user=auth_user, term_id=term_id)
    )


@router.get("/{term_id}/versions")
async def list_versions(
    term_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    detail = await service.get_term_detail(auth_user=auth_user, term_id=term_id)
    return detail.versions


@router.post("/{term_id}/relations", status_code=204)
async def add_relation(
    term_id: UUID,
    body: RelationBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    await service.add_relation(
        auth_user=auth_user, term_id=term_id,
        target_term_id=body.target_term_id, relation_type=body.relation_type,
    )


@router.delete("/{term_id}/relations/{relation_id}", status_code=204)
async def remove_relation(
    term_id: UUID,
    relation_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryTermService = Depends(get_glossary_term_service),
):
    await service.remove_relation(
        auth_user=auth_user, term_id=term_id, relation_id=relation_id
    )

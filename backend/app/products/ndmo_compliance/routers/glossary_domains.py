"""Domain-hierarchy endpoints for the Business Glossary.

Mounted under ``/api/v1/products/ndmo-compliance/glossary`` (see main.py),
gated by ``require_ndmo_compliance``.  Authorization beyond product
entitlement is domain-scoped inside the service layer.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.ndmo_compliance.entities.glossary_domain import GlossaryDomain
from app.products.ndmo_compliance.services.glossary_domain_service import (
    GlossaryDomainService,
    get_glossary_domain_service,
)
from app.products.ndmo_compliance.services.glossary_term_service import (
    GlossaryTermService,
    get_glossary_term_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/glossary", tags=["ndmo-glossary-domains"])


# ---------- shapes -------------------------------------------------------


class DomainBody(BaseModel):
    name_en: str = Field(..., min_length=1, max_length=255)
    name_ar: str | None = Field(default=None, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    owner_user_id: int | None = None


class SubdomainBody(DomainBody):
    steward_user_ids: list[int] = Field(default_factory=list)


class DomainUpdateBody(BaseModel):
    name_en: str | None = Field(default=None, max_length=255)
    name_ar: str | None = Field(default=None, max_length=255)
    description_en: str | None = None
    description_ar: str | None = None
    owner_user_id: int | None = None


class StewardBody(BaseModel):
    user_id: int


class DomainResponse(BaseModel):
    id: str
    parent_id: str | None
    name_en: str
    name_ar: str | None
    description_en: str | None
    description_ar: str | None
    owner_user_id: int | None
    steward_ids: list[int]
    status: str
    term_count: int


class GlossaryUser(BaseModel):
    id: int
    name: str
    email: str


class GlossaryRoleResponse(BaseModel):
    """The caller's derived glossary role + scope (drives sidebar gating)."""
    effective_role: str
    is_org_admin: bool
    owned_domain_ids: list[str]
    steward_domain_ids: list[str]
    review_queue_count: int


def _to_response(d: GlossaryDomain) -> DomainResponse:
    return DomainResponse(
        id=str(d.id),
        parent_id=str(d.parent_id) if d.parent_id else None,
        name_en=d.name_en,
        name_ar=d.name_ar,
        description_en=d.description_en,
        description_ar=d.description_ar,
        owner_user_id=d.owner_user_id,
        steward_ids=d.steward_ids,
        status=d.status,
        term_count=d.term_count,
    )


# ---------- routes -------------------------------------------------------


@router.get("/me", response_model=GlossaryRoleResponse)
async def my_glossary_role(
    auth_user: AuthUser = Depends(get_current_user),
    domain_service: GlossaryDomainService = Depends(get_glossary_domain_service),
    term_service: GlossaryTermService = Depends(get_glossary_term_service),
):
    actor = await domain_service.resolve_actor(auth_user)
    count = await term_service.review_queue_count(auth_user=auth_user)
    return GlossaryRoleResponse(
        effective_role=actor.effective_role,
        is_org_admin=actor.is_org_admin,
        owned_domain_ids=[str(i) for i in actor.owned_domain_ids],
        steward_domain_ids=[str(i) for i in actor.steward_domain_ids],
        review_queue_count=count,
    )


@router.get("/users", response_model=list[GlossaryUser])
async def list_assignable_users(
    search: str | None = Query(default=None),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    """Active users in the tenant, for owner/steward pickers (id + name)."""
    return await service.list_users(auth_user=auth_user, search=search)


@router.get("/domains", response_model=list[DomainResponse])
async def list_domains(
    include_archived: bool = Query(default=False),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    domains = await service.list_domains(
        auth_user=auth_user, include_archived=include_archived
    )
    return [_to_response(d) for d in domains]


@router.get("/domains/{domain_id}", response_model=DomainResponse)
async def get_domain(
    domain_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    return _to_response(await service.get_domain(domain_id=domain_id, auth_user=auth_user))


@router.post("/domains", response_model=DomainResponse, status_code=201)
async def create_domain(
    body: DomainBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    domain = await service.create_top_level(
        auth_user=auth_user, name_en=body.name_en, name_ar=body.name_ar,
        description_en=body.description_en, description_ar=body.description_ar,
        owner_user_id=body.owner_user_id,
    )
    return _to_response(domain)


@router.post("/domains/{parent_id}/subdomains", response_model=DomainResponse, status_code=201)
async def create_subdomain(
    parent_id: UUID,
    body: SubdomainBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    domain = await service.create_subdomain(
        auth_user=auth_user, parent_id=parent_id, name_en=body.name_en,
        name_ar=body.name_ar, description_en=body.description_en,
        description_ar=body.description_ar, owner_user_id=body.owner_user_id,
        steward_user_ids=body.steward_user_ids,
    )
    return _to_response(domain)


@router.put("/domains/{domain_id}", response_model=DomainResponse)
async def update_domain(
    domain_id: UUID,
    body: DomainUpdateBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    domain = await service.update_domain(
        auth_user=auth_user, domain_id=domain_id,
        **body.model_dump(exclude_none=True),
    )
    return _to_response(domain)


@router.delete("/domains/{domain_id}", status_code=204)
async def archive_domain(
    domain_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    await service.archive_domain(auth_user=auth_user, domain_id=domain_id)


@router.post("/domains/{domain_id}/stewards", status_code=204)
async def add_steward(
    domain_id: UUID,
    body: StewardBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    await service.assign_steward(
        auth_user=auth_user, domain_id=domain_id, user_id=body.user_id
    )


@router.delete("/domains/{domain_id}/stewards/{user_id}", status_code=204)
async def remove_steward(
    domain_id: UUID,
    user_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryDomainService = Depends(get_glossary_domain_service),
):
    await service.remove_steward(
        auth_user=auth_user, domain_id=domain_id, user_id=user_id
    )

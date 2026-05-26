"""Dictionary CRUD endpoints (BRD §4.4 / FR-LIB)."""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.services.concept_service import (
    ConceptService, get_concept_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/concepts", tags=["dq-concepts"])


class CreateConceptBody(BaseModel):
    dimension: str
    concept: str = Field(min_length=1, max_length=100)
    synonyms: list[str] = Field(default_factory=list)
    rule_type: str
    parameter: dict = Field(default_factory=dict)
    severity: str = "medium"
    notes: str | None = None
    enabled: bool = True


class UpdateConceptBody(BaseModel):
    synonyms: list[str] | None = None
    rule_type: str | None = None
    parameter: dict | None = None
    severity: str | None = None
    notes: str | None = None
    enabled: bool | None = None


@router.get("")
async def list_concepts(
    dimension: str | None = Query(default=None),
    enabled_only: bool = Query(default=False),
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    rows = await service.list_concepts(
        auth_user, dimension=dimension, enabled_only=enabled_only,
    )
    return {"items": rows}


@router.post("")
async def create_concept(
    body: CreateConceptBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    row = await service.create_concept(
        dimension=body.dimension, concept=body.concept,
        synonyms=body.synonyms, rule_type=body.rule_type,
        parameter=body.parameter, severity=body.severity,
        notes=body.notes,
        enabled=body.enabled, auth_user=auth_user,
    )
    return {"detail": "Concept created", "concept": row}


@router.get("/{concept_id}")
async def get_concept(
    concept_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    return await service.get_concept(concept_id, auth_user)


@router.put("/{concept_id}")
async def update_concept(
    concept_id: int,
    body: UpdateConceptBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    row = await service.update_concept(
        concept_id,
        synonyms=body.synonyms, rule_type=body.rule_type,
        parameter=body.parameter, severity=body.severity,
        notes=body.notes,
        enabled=body.enabled, auth_user=auth_user,
    )
    return {"detail": "Concept updated", "concept": row}


@router.delete("/{concept_id}")
async def delete_concept(
    concept_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    await service.delete_concept(concept_id, auth_user)
    return {"detail": "Concept deleted"}


@router.post("/seed-defaults")
async def seed_defaults(
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    """Idempotently install the default dictionary for the caller's tenant.
    Concepts that already exist (by dimension + name) are left untouched —
    user edits are preserved."""
    return await service.seed_defaults(auth_user)


@router.post("/refresh-seeded")
async def refresh_seeded(
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptService = Depends(get_concept_service),
):
    """Re-apply the current seed file to all is_seed=TRUE concepts: inserts
    missing concepts and overwrites stale fields (e.g. regex patterns added
    after the original install). Customized concepts (is_seed=FALSE) are
    skipped."""
    return await service.refresh_seeded(auth_user)

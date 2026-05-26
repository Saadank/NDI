"""Reference CRUD endpoints — reusable value lists that dictionary_match
concepts point at."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.ai.services.concept_draft_service import (
    ConceptDraftService, get_concept_draft_service,
)
from app.products.data_quality.services.reference_service import (
    ReferenceService, get_reference_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/references", tags=["dq-references"])


class CreateReferenceBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    case_sensitive: bool = False
    values: list[str] = Field(default_factory=list)


class UpdateReferenceBody(BaseModel):
    name: str | None = None
    description: str | None = None
    case_sensitive: bool | None = None
    # Bulk-replace the values list when present; omit to leave values untouched.
    values: list[str] | None = None


@router.get("")
async def list_references(
    auth_user: AuthUser = Depends(get_current_user),
    service: ReferenceService = Depends(get_reference_service),
):
    rows = await service.list_references(auth_user)
    return {"items": rows}


@router.post("")
async def create_reference(
    body: CreateReferenceBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ReferenceService = Depends(get_reference_service),
):
    row = await service.create_reference(
        name=body.name, description=body.description,
        case_sensitive=body.case_sensitive, values=body.values,
        auth_user=auth_user,
    )
    return {"detail": "Reference created", "reference": row}


@router.get("/{reference_id}")
async def get_reference(
    reference_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ReferenceService = Depends(get_reference_service),
):
    return await service.get_reference(reference_id, auth_user)


@router.put("/{reference_id}")
async def update_reference(
    reference_id: int,
    body: UpdateReferenceBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ReferenceService = Depends(get_reference_service),
):
    row = await service.update_reference(
        reference_id,
        name=body.name, description=body.description,
        case_sensitive=body.case_sensitive, values=body.values,
        auth_user=auth_user,
    )
    return {"detail": "Reference updated", "reference": row}


@router.delete("/{reference_id}")
async def delete_reference(
    reference_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ReferenceService = Depends(get_reference_service),
):
    await service.delete_reference(reference_id, auth_user)
    return {"detail": "Reference deleted"}


# ---------------------------------------------------------------------------
# AI value drafting — "Ask AI to draft values" in the Reference editor.
# Calls the same underlying LLM purpose as the concept-level draft helper.
# ---------------------------------------------------------------------------

class DraftValuesBody(BaseModel):
    nl_text: str = Field(min_length=1, max_length=2000)
    reference_name: str | None = None
    current_values: list[str] | None = None


@router.post("/draft-values")
async def draft_values_from_nl(
    body: DraftValuesBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptDraftService = Depends(get_concept_draft_service),
):
    """Generate a list of allowed values for a reference from a natural-
    language description. Used by the Reference editor's 'Ask AI to draft
    values' button. Returns ``{status, draft: {values, case_sensitive,
    explanation, confidence}, latency_ms, ...}``."""
    return await service.draft_dictionary(
        nl_text=body.nl_text,
        concept_name=body.reference_name,
        current_values=body.current_values,
        auth_user=auth_user,
    )

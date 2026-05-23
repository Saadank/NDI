"""LLM-assisted concept endpoints — Approach 2 (interactive).

Mounted under ``/api/v1/products/data-quality/concepts`` so it sits next
to the deterministic concepts router; the path suffix (``/draft-from-nl``)
keeps the two clearly separated.
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.ai.services.concept_draft_service import (
    ConceptDraftService, get_concept_draft_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/concepts", tags=["dq-concepts-ai"])


class DraftFromNlBody(BaseModel):
    nl_text: str = Field(min_length=1, max_length=2000)
    dimension_hint: str | None = None  # completeness | validity | uniqueness


class DraftRegexBody(BaseModel):
    nl_text: str = Field(min_length=1, max_length=2000)
    concept_name: str | None = None
    current_pattern: str | None = None


@router.post("/draft-from-nl")
async def draft_concept_from_nl(
    body: DraftFromNlBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptDraftService = Depends(get_concept_draft_service),
):
    """Draft a single concept from a natural-language description.

    Returns ``{status, draft?, error?, latency_ms, input_tokens?, output_tokens?}``.
    The frontend's "Draft with AI" modal pre-fills the new-concept form
    with ``draft`` so the user can edit before saving — they ARE the
    reviewer for this path."""
    return await service.draft(
        nl_text=body.nl_text,
        dimension_hint=body.dimension_hint,
        auth_user=auth_user,
    )


@router.post("/draft-regex")
async def draft_regex_from_nl(
    body: DraftRegexBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ConceptDraftService = Depends(get_concept_draft_service),
):
    """Generate just a regex pattern from a natural-language description.

    Used by the Edit-concept modal's 'Ask AI' button. Returns
    ``{status, draft: {pattern, explanation, examples_pass, examples_fail,
    confidence}, latency_ms, ...}``. The frontend fills the Regex pattern
    field with ``draft.pattern`` and seeds the live tester with the examples."""
    return await service.draft_regex(
        nl_text=body.nl_text,
        concept_name=body.concept_name,
        current_pattern=body.current_pattern,
        auth_user=auth_user,
    )

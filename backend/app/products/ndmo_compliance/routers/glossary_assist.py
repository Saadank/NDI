"""AI-Assist endpoints for the Business Glossary (BRD §6.3 / WF-06).

Mounted under ``/api/v1/products/ndmo-compliance/glossary``.  Three modes —
Draft / Rephrase / Advise.  Suggestions only: these endpoints never create or
mutate a term.  Each returns ``available`` so the frontend can show a graceful
fallback when the LLM is unavailable.

Prefix is ``/glossary/assist`` (not ``/glossary/terms/assist``) so the static
paths never collide with the terms router's ``/{term_id}`` routes.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.ndmo_compliance.services.glossary_assist_service import (
    AssistResult,
    GlossaryAssistService,
    get_glossary_assist_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/glossary/assist", tags=["ndmo-glossary-assist"])


class DraftBody(BaseModel):
    term_name: str = Field(..., min_length=1, max_length=255)
    context: str | None = None
    term_id: UUID | None = None


class RephraseBody(BaseModel):
    current_definition: str = Field(..., min_length=1)
    instruction: str | None = None
    term_id: UUID | None = None


class AdviseBody(BaseModel):
    term_name: str = Field(..., min_length=1, max_length=255)
    definition_draft: str | None = None
    related_terms: str | None = None
    term_id: UUID | None = None


class AssistResponse(BaseModel):
    available: bool
    output: str | None = None
    message: str | None = None


def _to_response(r: AssistResult) -> AssistResponse:
    return AssistResponse(available=r.available, output=r.output, message=r.message)


@router.post("/draft", response_model=AssistResponse)
async def assist_draft(
    body: DraftBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryAssistService = Depends(get_glossary_assist_service),
):
    return _to_response(
        await service.draft(
            auth_user=auth_user, term_name=body.term_name,
            context=body.context, term_id=body.term_id,
        )
    )


@router.post("/rephrase", response_model=AssistResponse)
async def assist_rephrase(
    body: RephraseBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryAssistService = Depends(get_glossary_assist_service),
):
    return _to_response(
        await service.rephrase(
            auth_user=auth_user, current_definition=body.current_definition,
            instruction=body.instruction, term_id=body.term_id,
        )
    )


@router.post("/advise", response_model=AssistResponse)
async def assist_advise(
    body: AdviseBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryAssistService = Depends(get_glossary_assist_service),
):
    return _to_response(
        await service.advise(
            auth_user=auth_user, term_name=body.term_name,
            definition_draft=body.definition_draft,
            related_terms=body.related_terms, term_id=body.term_id,
        )
    )

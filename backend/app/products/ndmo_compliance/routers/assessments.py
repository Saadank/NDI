"""Assessment HTTP endpoints.

Mounted under ``/api/v1/products/ndmo-compliance/assessments`` (see main.py).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.ndmo_compliance.enums.review_decision import ReviewDecision
from app.products.ndmo_compliance.services.assessment_service import (
    AssessmentService,
    get_assessment_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/assessments", tags=["ndmo-assessments"])


class RunAssessmentBody(BaseModel):
    cycle_id: int | None = Field(default=None, ge=1,
                                 description="Defaults to the tenant's active cycle.")
    dry_run: bool = Field(default=False,
                          description="If true, no DB writes; useful for cost/latency canary.")
    spec_limit: int | None = Field(default=None, ge=1, le=200,
                                   description="Cap number of specs (canary mode).")


class RunAssessmentResponse(BaseModel):
    cycle_id: int
    total_specs: int
    dry_run: bool


class SubmitReviewBody(BaseModel):
    decision: ReviewDecision
    note: str | None = Field(default=None, max_length=2000)
    override_maturity_level: int | None = Field(default=None, ge=0, le=5)


@router.post("/run", response_model=RunAssessmentResponse)
async def run_assessment(
    body: RunAssessmentBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
):
    started = await service.trigger_run(
        auth_user=auth_user,
        cycle_id=body.cycle_id,
        dry_run=body.dry_run,
        spec_limit=body.spec_limit,
    )
    return RunAssessmentResponse(**started.__dict__)


@router.get("")
async def list_assessments(
    status: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    auth_user: AuthUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
):
    return await service.list_for_active_cycle(
        auth_user=auth_user, status=status, limit=limit, offset=offset,
    )


@router.get("/{assessment_id}")
async def get_assessment(
    assessment_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
):
    result = await service.get_with_citations(
        assessment_id=assessment_id, auth_user=auth_user
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return result


@router.post("/{assessment_id}/review", status_code=204)
async def submit_review(
    assessment_id: UUID,
    body: SubmitReviewBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: AssessmentService = Depends(get_assessment_service),
):
    await service.submit_review(
        assessment_id=assessment_id, auth_user=auth_user,
        decision=body.decision, note=body.note,
        override_maturity_level=body.override_maturity_level,
    )

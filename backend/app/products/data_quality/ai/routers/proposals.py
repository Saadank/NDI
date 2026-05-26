"""Proposal-review endpoints — Step 6.7.

These are the only ai/ endpoints that mutate the deterministic rule
engine (via ProposalService applying approved proposals to
t_dq_concepts + t_dq_active_rules).
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.ai.services.proposal_service import (
    ProposalService, get_proposal_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/proposals", tags=["dq-proposals"])


class ApproveBody(BaseModel):
    """Optional reviewer overrides. Unset fields keep the LLM/import value."""
    final_value: dict | None = None


class RejectBody(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class BulkApproveBody(BaseModel):
    import_id: int
    # Hard-coded to HIGH for safety today. Future versions may relax.
    confidence: str = "HIGH"


@router.get("")
async def list_proposals(
    import_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=2000),
    auth_user: AuthUser = Depends(get_current_user),
    service: ProposalService = Depends(get_proposal_service),
):
    """List proposals. Filter by import_id, status, confidence."""
    if import_id is not None:
        items = await service.list_for_import(
            import_id, auth_user, status=status, confidence=confidence,
        )
    else:
        items = await service.list_for_tenant(
            auth_user, status=status, limit=limit,
        )
    return {"items": items}


@router.get("/{proposal_id}")
async def get_proposal(
    proposal_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProposalService = Depends(get_proposal_service),
):
    return await service.get(proposal_id, auth_user)


@router.post("/{proposal_id}/approve")
async def approve_proposal(
    proposal_id: int, body: ApproveBody | None = None,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProposalService = Depends(get_proposal_service),
):
    """Apply the proposal: create/update the deterministic concept and,
    when a target table/column is set and a profile exists for that
    table, write an active_rule binding."""
    return await service.approve(
        proposal_id, auth_user,
        final_value_override=(body.final_value if body else None),
    )


@router.post("/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int, body: RejectBody | None = None,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProposalService = Depends(get_proposal_service),
):
    return await service.reject(
        proposal_id, auth_user,
        reason=(body.reason if body else None),
    )


@router.post("/bulk-approve")
async def bulk_approve(
    body: BulkApproveBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProposalService = Depends(get_proposal_service),
):
    """Approve every pending HIGH-confidence proposal under an import.
    Returns ``{approved, skipped, errors[], matched_count}``."""
    if body.confidence != "HIGH":
        # Future: relax once we have more telemetry on MEDIUM/LOW approval
        # patterns. Today bulk-approve is HIGH-only for safety.
        return {"approved": 0, "skipped": 0, "errors": [],
                "matched_count": 0,
                "detail": "Bulk-approve currently restricted to confidence=HIGH"}
    return await service.bulk_approve_high(body.import_id, auth_user)

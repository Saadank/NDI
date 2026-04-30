"""Concept matcher + active-rule lifecycle endpoints.

Phase 1.5: requests are scoped by profile_id. The matcher reads the source
binding from the profile (connection + schema + table); rules persist with
profile_id so the validator can read its workload via that one key.
"""
from fastapi import APIRouter, Depends

from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.data_quality.services.active_rule_service import (
    ActiveRuleService, get_active_rule_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/active-rules", tags=["dq-active-rules"])


class ProfileTargetBody(BaseModel):
    profile_id: int


class BlockBody(BaseModel):
    reason: str | None = None


class BindManualBody(BaseModel):
    profile_id: int
    column_name: str
    concept_id: int


@router.post("/preview")
async def preview(
    body: ProfileTargetBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    """Run the matcher on the profile's table and return what it would
    activate — without persisting. Used by the UI to preview proposals."""
    return await service.preview_profile(
        profile_id=body.profile_id, auth_user=auth_user,
    )


@router.post("/apply")
async def apply(
    body: ProfileTargetBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    """Same as /preview but persists results to t_dq_active_rules.
    HIGH-confidence matches activate immediately; others land as proposed."""
    return await service.apply_profile(
        profile_id=body.profile_id, auth_user=auth_user,
    )


@router.get("")
async def list_rules(
    profile_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    rows = await service.list_for_profile(
        profile_id=profile_id, auth_user=auth_user,
    )
    return {"items": rows}


@router.post("/manual")
async def bind_manual(
    body: BindManualBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    """Manually bind a concept to a column. Lands as auto_applied — the
    validator picks it up on the next scan. The matcher leaves manual rows
    alone on subsequent runs."""
    row = await service.bind_manual(
        profile_id=body.profile_id, column_name=body.column_name,
        concept_id=body.concept_id, auth_user=auth_user,
    )
    return {"detail": "Rule bound manually", "rule": row}


@router.post("/{rule_id}/approve")
async def approve(
    rule_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    return {"detail": "Rule approved",
            "rule": await service.approve(rule_id, auth_user)}


@router.post("/{rule_id}/block")
async def block(
    rule_id: int, body: BlockBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    return {"detail": "Rule blocked",
            "rule": await service.block(rule_id, body.reason, auth_user)}


@router.post("/{rule_id}/unblock")
async def unblock(
    rule_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ActiveRuleService = Depends(get_active_rule_service),
):
    return {"detail": "Rule unblocked",
            "rule": await service.unblock(rule_id, auth_user)}

"""Governed exception endpoints — Phase 1, Step 5 (BRD §4.8 / FR-EXC).

Manages the lifecycle of dq.t_dq_exceptions rows. Reads are open to any DQ
team member; mutations are gated to org/platform admins because tier bands
and exception coverage shape governance metrics for the whole tenant.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.services.exception_service import (
    ExceptionService, get_exception_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/exceptions", tags=["dq-exceptions"])


class CreateExceptionBody(BaseModel):
    profile_id: int
    active_rule_id: int
    reason_category: str
    explanation: str = Field(min_length=1, max_length=4000)
    violation_count_ceiling: int | None = Field(default=None, ge=0)
    # Either expires_at (ISO timestamp) or expires_in_days (default 90 from now).
    expires_at: datetime | None = None
    expires_in_days: int | None = Field(default=None, ge=1, le=365)


class ExtendBody(BaseModel):
    days: int | None = Field(default=None, ge=1, le=365)
    until: datetime | None = None


class RevokeBody(BaseModel):
    reason: str | None = None


@router.get("/profile/{profile_id}")
async def list_for_profile(
    profile_id: int,
    include_revoked: bool = Query(default=False),
    auth_user: AuthUser = Depends(get_current_user),
    service: ExceptionService = Depends(get_exception_service),
):
    items = await service.list_for_profile(
        profile_id=profile_id, include_revoked=include_revoked, auth_user=auth_user,
    )
    return {"items": items}


@router.get("/{exception_id}")
async def get_exception(
    exception_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExceptionService = Depends(get_exception_service),
):
    return await service.get_exception(exception_id, auth_user)


@router.post("")
async def create_exception(
    body: CreateExceptionBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExceptionService = Depends(get_exception_service),
):
    """Create or replace the active exception for a rule. Default expiry is
    90 days from now; pass `expires_at` or `expires_in_days` to override."""
    if body.expires_at is not None:
        expires_at = body.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
    else:
        days = body.expires_in_days if body.expires_in_days is not None else 90
        expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    row = await service.create_exception(
        profile_id=body.profile_id, active_rule_id=body.active_rule_id,
        reason_category=body.reason_category, explanation=body.explanation,
        violation_count_ceiling=body.violation_count_ceiling,
        expires_at=expires_at, auth_user=auth_user,
    )
    return {"detail": "Exception created", "row": row}


@router.post("/{exception_id}/revoke")
async def revoke_exception(
    exception_id: int, body: RevokeBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExceptionService = Depends(get_exception_service),
):
    row = await service.revoke(exception_id, reason=body.reason, auth_user=auth_user)
    return {"detail": "Exception revoked", "row": row}


@router.put("/{exception_id}/extend")
async def extend_exception(
    exception_id: int, body: ExtendBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ExceptionService = Depends(get_exception_service),
):
    until = body.until
    if until is not None and until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    row = await service.extend(
        exception_id, days=body.days, until=until, auth_user=auth_user,
    )
    return {"detail": "Exception extended", "row": row}

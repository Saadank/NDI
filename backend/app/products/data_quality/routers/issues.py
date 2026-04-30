"""Issue read endpoints — validator findings (BRD §4.6 / FR-VAL).

Phase 1.5: issues are listed per profile (the unit of work). Per-scan
queries still work — they're keyed by scan_id which has the profile_id.
"""
from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.issue_repository import IssueRepository
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/issues", tags=["dq-issues"])


def _repo() -> IssueRepository:
    return IssueRepository()


@router.get("/scan/{scan_id}")
async def by_scan(
    scan_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    repo: IssueRepository = Depends(_repo),
):
    """All issues produced by a single scan."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    rows = await repo.find_by_scan(scan_id, auth_user.tenant_id)
    summary = await repo.summary_for_scan(scan_id, auth_user.tenant_id)
    return {"scan_id": scan_id, "summary": summary, "items": rows}


@router.get("/profile/{profile_id}")
async def by_profile(
    profile_id: int,
    latest_scan_only: bool = Query(default=True),
    limit: int = Query(default=500, ge=1, le=2000),
    auth_user: AuthUser = Depends(get_current_user),
    repo: IssueRepository = Depends(_repo),
):
    """Issues for a profile. Defaults to the most recent successful scan;
    set latest_scan_only=false to walk history."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    items = await repo.list_for_profile(
        tenant_id=auth_user.tenant_id, profile_id=profile_id,
        latest_scan_only=latest_scan_only, limit=limit,
    )
    return {"items": items}

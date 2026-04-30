"""Score / metrics endpoints — Phase 1, Step 4 (BRD §4.7 / FR-SCORE).

Reads the per-scan score history persisted by ScoringService and exposes
the Metrics-tab payload (dimension donuts + trend deltas + rule occurrences)
plus a per-tenant thresholds CRUD path for admins.

Score recomputation is idempotent — useful when the validator added new
issues after the original scoring pass (e.g. concept enabled mid-flight).
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.services.scoring_service import (
    ScoringService, get_scoring_service,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ForbiddenException

router = APIRouter(prefix="/scores", tags=["dq-scores"])

_VALID_DIMENSIONS = {"*", "completeness", "validity", "uniqueness", "overall"}


class UpsertThresholdsBody(BaseModel):
    dimension: str = Field(default="*")
    good_min: float = Field(ge=0.0, le=1.0)
    acceptable_min: float = Field(ge=0.0, le=1.0)
    severity_weighting_enabled: bool | None = None


@router.get("/profile/{profile_id}/metrics")
async def metrics_for_profile(
    profile_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ScoringService = Depends(get_scoring_service),
):
    """Latest dimension scores + delta vs previous scan + rule occurrences."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    return await service.get_metrics_for_profile(
        tenant_id=auth_user.tenant_id, profile_id=profile_id,
    )


@router.get("/profile/{profile_id}/trend")
async def trend_for_profile(
    profile_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    auth_user: AuthUser = Depends(get_current_user),
    service: ScoringService = Depends(get_scoring_service),
):
    """Per-(scan, dimension) score history for trend charts. Newest first."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    items = await service.get_trend_for_profile(
        tenant_id=auth_user.tenant_id, profile_id=profile_id, limit=limit,
    )
    return {"items": items}


@router.post("/scan/{scan_id}/recompute")
async def recompute_scan(
    scan_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ScoringService = Depends(get_scoring_service),
):
    """Recompute scores for a scan from current issues. Idempotent — useful
    after threshold changes or if scoring failed during the original scan."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    # Look up the profile_id from the scan to keep the body shape narrow.
    from app.products.data_quality.repositories.scan_repository import ScanRepository
    scan = await ScanRepository().find_by_id(scan_id, auth_user.tenant_id)
    if not scan:
        from app.utils.exceptions import ResourceNotFoundException
        raise ResourceNotFoundException("Scan not found")
    rows = await service.score_scan(
        tenant_id=auth_user.tenant_id, profile_id=scan["profile_id"],
        scan_id=scan_id,
    )
    return {"detail": f"Scored {len(rows)} dimension(s)", "items": rows}


@router.get("/thresholds")
async def get_thresholds(
    auth_user: AuthUser = Depends(get_current_user),
    service: ScoringService = Depends(get_scoring_service),
):
    """Tier thresholds for the caller's tenant (one row per dimension or '*')."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    rows = await service.score_repo.get_thresholds_for_tenant(auth_user.tenant_id)
    return {"items": rows}


@router.put("/thresholds")
async def upsert_thresholds(
    body: UpsertThresholdsBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ScoringService = Depends(get_scoring_service),
):
    """Upsert a thresholds row. Org/platform admins only — tier bands shape
    everyone's scores so they're a tenant-wide governance setting."""
    require(can_use_dq(auth_user), "Data Quality is not available for this account")
    if auth_user.platform_role not in (PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN):
        raise ForbiddenException("Only org or platform admins can edit DQ thresholds")
    if body.dimension not in _VALID_DIMENSIONS:
        from app.utils.exceptions import ValidationException
        raise ValidationException(
            f"dimension must be one of {sorted(_VALID_DIMENSIONS)}"
        )
    if body.good_min < body.acceptable_min:
        from app.utils.exceptions import ValidationException
        raise ValidationException("good_min must be >= acceptable_min")

    # Re-load existing severity_weighting flag if the body didn't override it.
    existing_rows = await service.score_repo.get_thresholds_for_tenant(auth_user.tenant_id)
    existing = next((r for r in existing_rows if r["dimension"] == body.dimension), None)
    weighting = (
        body.severity_weighting_enabled
        if body.severity_weighting_enabled is not None
        else (bool(existing["severity_weighting_enabled"]) if existing else False)
    )

    row = await service.score_repo.upsert_thresholds(
        tenant_id=auth_user.tenant_id, dimension=body.dimension,
        good_min=body.good_min, acceptable_min=body.acceptable_min,
        severity_weighting_enabled=weighting,
        updated_by=auth_user.user_id,
    )
    return {"detail": "Thresholds updated", "row": row}

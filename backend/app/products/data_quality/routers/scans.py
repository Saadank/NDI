"""Profile / validation scan endpoints (BRD §4.5, FR-PROF).

Phase 1.5: requests are scoped by profile_id, not (conn, schema, table).
The Profile Asset owns the source binding, sampling config, and history.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.services.profiler_service import (
    ProfilerService, get_profiler_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/scans", tags=["dq-scans"])


class StartScanBody(BaseModel):
    profile_id: int


class StartBatchScanBody(BaseModel):
    profile_ids: list[int] = Field(min_length=1, max_length=500)


class StartValidateOnlyBody(BaseModel):
    profile_id: int
    dimension: str | None = None  # 'completeness' | 'validity' | 'uniqueness'
    active_rule_ids: list[int] | None = None


@router.post("")
async def start_scan(
    body: StartScanBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    """Trigger a profile scan against the given profile. Returns immediately
    with a `pending` scan record; the work runs as a background task."""
    scan = await service.start_profile_scan(
        profile_id=body.profile_id, auth_user=auth_user,
    )
    return {"detail": "Scan queued", "scan": scan}


@router.post("/validate-only")
async def start_validate_only(
    body: StartValidateOnlyBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    """Re-validate a profile without re-profiling. Skips the slow per-column
    aggregates and runs only the active rules — optionally filtered to a
    single dimension or a list of rule IDs. Seconds vs minutes for iteration."""
    if body.dimension and body.dimension not in ("completeness", "validity", "uniqueness"):
        from app.utils.exceptions import ValidationException
        raise ValidationException(
            "dimension must be one of completeness/validity/uniqueness"
        )
    scan = await service.start_validate_only_scan(
        profile_id=body.profile_id, auth_user=auth_user,
        dimension=body.dimension, active_rule_ids=body.active_rule_ids,
    )
    return {"detail": "Validate-only scan queued", "scan": scan}


@router.post("/batch")
async def start_batch_scan(
    body: StartBatchScanBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    """Queue scans for many profiles at once. Per-connection concurrency
    cap throttles parallel execution against any single source DB."""
    result = await service.start_batch_scan(
        profile_ids=body.profile_ids, auth_user=auth_user,
    )
    return {"detail": f"{result['queued']} scan(s) queued", **result}


@router.get("")
async def list_scans(
    profile_id: int | None = None,
    connection_id: UUID | None = None,
    schema_name: str | None = None,
    table_name: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    """List scans. Filter by profile_id (preferred) or by source tuple
    (back-compat — same source can have multiple profile variants)."""
    rows = await service.list_scans(
        auth_user, profile_id=profile_id, connection_id=connection_id,
        schema_name=schema_name, table_name=table_name, limit=limit,
    )
    return {"items": rows}


@router.get("/{scan_id}")
async def get_scan(
    scan_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    return await service.get_scan(scan_id, auth_user)


@router.get("/{scan_id}/profiles")
async def get_scan_profiles(
    scan_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    """Per-column profile rows for the given scan."""
    return await service.get_profiles(scan_id, auth_user)


@router.delete("/{scan_id}")
async def delete_scan(
    scan_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfilerService = Depends(get_profiler_service),
):
    """Hard-delete a scan. CASCADES to column profiles, issues, and
    score history for the scan. Refuses on pending / running scans to
    avoid orphaning rows written by the background task. UI must
    surface the cascade scope before sending."""
    return await service.delete_scan(scan_id, auth_user)

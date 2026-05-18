"""Profile Asset endpoints (Phase 1.5)."""
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.products.data_quality.services.profile_service import (
    ProfileService, get_profile_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/profiles", tags=["dq-profiles"])


class CreateProfileBody(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    location_path: str | None = Field(default=None, max_length=500)
    connection_id: UUID
    schema_name: str = Field(min_length=1, max_length=255)
    table_name: str = Field(min_length=1, max_length=255)
    sampling_mode: str = "all"
    sample_size: int | None = None
    drill_down: bool = True
    ai_enabled: bool = True
    # Per-profile column subset. Omit (or pass null) to profile every column.
    selected_columns: list[str] | None = None


class UpdateProfileBody(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = None
    location_path: str | None = Field(default=None, max_length=500)
    sampling_mode: str | None = None
    sample_size: int | None = None
    drill_down: bool | None = None
    ai_enabled: bool | None = None
    # NOTE: PATCH semantics need a sentinel to distinguish "leave alone"
    # (omit) from "set to NULL i.e. all columns" (None) from "set to a
    # specific list" (a list). Pydantic can't model that cleanly without
    # either Optional[Optional[...]] or a custom type, so we treat:
    #   - field absent / explicit null → no change
    #   - empty list                   → set to empty list (zero columns; profiler errors out)
    #   - non-empty list               → set to that list
    # If a tenant ever needs "go back to all-columns mode", they can
    # currently re-create the profile or we add a `clear_selected_columns`
    # flag later.
    selected_columns: list[str] | None = None


class CloneProfileBody(BaseModel):
    new_name: str = Field(min_length=1, max_length=255)


@router.get("")
async def list_profiles(
    location_path: str | None = Query(default=None),
    connection_id: UUID | None = Query(default=None),
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    rows = await service.list_profiles(
        auth_user, location_path=location_path, connection_id=connection_id,
    )
    return {"items": rows}


@router.post("")
async def create_profile(
    body: CreateProfileBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    row = await service.create_profile(
        name=body.name, description=body.description,
        location_path=body.location_path,
        connection_id=body.connection_id, schema_name=body.schema_name,
        table_name=body.table_name, sampling_mode=body.sampling_mode,
        sample_size=body.sample_size, drill_down=body.drill_down,
        ai_enabled=body.ai_enabled,
        selected_columns=body.selected_columns,
        auth_user=auth_user,
    )
    return {"detail": "Profile created", "profile": row}


@router.get("/{profile_id}")
async def get_profile(
    profile_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    return await service.get_profile(profile_id, auth_user)


@router.put("/{profile_id}")
async def update_profile(
    profile_id: int, body: UpdateProfileBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    row = await service.update_profile(
        profile_id, name=body.name, description=body.description,
        location_path=body.location_path, sampling_mode=body.sampling_mode,
        sample_size=body.sample_size, drill_down=body.drill_down,
        ai_enabled=body.ai_enabled,
        selected_columns=body.selected_columns,
        auth_user=auth_user,
    )
    return {"detail": "Profile updated", "profile": row}


@router.delete("/{profile_id}")
async def delete_profile(
    profile_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    await service.delete_profile(profile_id, auth_user)
    return {"detail": "Profile deleted (cascading scans, rules, and issues)"}


@router.post("/{profile_id}/clone")
async def clone_profile(
    profile_id: int, body: CloneProfileBody,
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    row = await service.clone_profile(profile_id, body.new_name, auth_user)
    return {"detail": "Profile cloned", "profile": row}


@router.get("/{profile_id}/columns/{column_name}/sample-stats")
async def column_sample_stats(
    profile_id: int,
    column_name: str,
    top_limit: int = Query(default=10, ge=1, le=50),
    auth_user: AuthUser = Depends(get_current_user),
    service: ProfileService = Depends(get_profile_service),
):
    """Live-peek the most-frequent values for one column on the profile's
    bound source table. **Nothing is persisted.** Backs the
    "Most-frequent values" tile in the redesigned Scans → Tiles view."""
    return await service.column_sample_stats(
        profile_id, column_name, top_limit=top_limit, auth_user=auth_user,
    )

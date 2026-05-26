"""Profile Asset CRUD orchestration (Phase 1.5).

A Profile is the unit of work — it owns scans, active rules, and (later)
score history. Connection/schema/table form the immutable source binding;
everything else (name, description, location, sampling, drill-down, AI on/off)
can be edited.
"""
from __future__ import annotations

import re
from uuid import UUID

from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.profile_repository import ProfileRepository
from app.products.data_sharing.repositories.connection_repository import (
    ConnectionRepository,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

_VALID_SAMPLING = {"all", "first_n", "random"}
# Names allow parens, brackets, and slashes too — users tend to qualify
# variants (e.g. "Customers (master)" or "Sales [Q3]"). Excludes control
# chars, semicolons, and quote characters that would muddy SQL/HTML output.
_NAME_RE = re.compile(r"^[A-Za-z0-9._,/\(\)\[\]\- ]{1,255}$")
_LOCATION_RE = re.compile(r"^[A-Za-z0-9._,/\(\)\[\]\- ]{0,500}$")


class ProfileService:

    def __init__(self) -> None:
        self.repo = ProfileRepository()
        self.connection_repo = ConnectionRepository()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_profiles(
        self, auth_user: AuthUser, *, location_path: str | None = None,
        connection_id: UUID | None = None,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self.repo.list_for_tenant(
            auth_user.tenant_id, location_path=location_path,
            connection_id=connection_id,
        )

    async def get_profile(self, profile_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        row = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not row:
            raise ResourceNotFoundException("Profile not found")
        return row

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def create_profile(
        self, *, name: str, description: str | None, location_path: str | None,
        connection_id: UUID, schema_name: str, table_name: str,
        sampling_mode: str, sample_size: int | None,
        drill_down: bool, ai_enabled: bool, auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._validate_name(name)
        self._validate_location(location_path)
        self._validate_sampling(sampling_mode, sample_size)
        if not schema_name or not table_name:
            raise ValidationException("schema_name and table_name are required")

        # Connection must belong to the caller's tenant.
        conn = await self.connection_repo.find_by_id(connection_id, auth_user.tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        # Friendlier error than the raw UNIQUE-constraint violation.
        if await self.repo.find_by_name(auth_user.tenant_id, name):
            raise ValidationException(
                f"A profile named '{name}' already exists in this tenant"
            )

        return await self.repo.insert(
            tenant_id=auth_user.tenant_id, name=name.strip(),
            description=description, location_path=(location_path or None),
            connection_id=connection_id, schema_name=schema_name,
            table_name=table_name, sampling_mode=sampling_mode,
            sample_size=sample_size, drill_down=drill_down,
            ai_enabled=ai_enabled, created_by=auth_user.user_id,
        )

    async def update_profile(
        self, profile_id: int, *,
        name: str | None = None, description: str | None = None,
        location_path: str | None = None,
        sampling_mode: str | None = None, sample_size: int | None = None,
        drill_down: bool | None = None, ai_enabled: bool | None = None,
        auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Profile not found")

        if name is not None:
            self._validate_name(name)
            if name != existing["name"] and await self.repo.find_by_name(
                auth_user.tenant_id, name
            ):
                raise ValidationException(
                    f"A profile named '{name}' already exists in this tenant"
                )
        if location_path is not None:
            self._validate_location(location_path)
        if sampling_mode is not None or sample_size is not None:
            # Validate the *combined* state — patch updates may fill in only
            # one half of the (mode, size) pair.
            effective_mode = sampling_mode if sampling_mode is not None else existing["sampling_mode"]
            effective_size = sample_size  if sample_size  is not None else existing["sample_size"]
            self._validate_sampling(effective_mode, effective_size)

        return await self.repo.update(
            profile_id, auth_user.tenant_id,
            name=name, description=description, location_path=location_path,
            sampling_mode=sampling_mode, sample_size=sample_size,
            drill_down=drill_down, ai_enabled=ai_enabled,
        )

    async def delete_profile(self, profile_id: int, auth_user: AuthUser) -> None:
        """Cascading delete — scans, active rules, and issues belonging to
        this profile go with it (via FK ON DELETE CASCADE)."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Profile not found")
        await self.repo.delete(profile_id, auth_user.tenant_id)

    async def clone_profile(
        self, profile_id: int, new_name: str, auth_user: AuthUser,
    ) -> dict:
        """Make a fresh profile with the same source binding + config but a
        new name. History (scans/rules/issues) is NOT copied — the clone
        starts empty so users can experiment with different sampling or AI
        settings without polluting the original's history."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._validate_name(new_name)

        src = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not src:
            raise ResourceNotFoundException("Profile not found")
        if await self.repo.find_by_name(auth_user.tenant_id, new_name):
            raise ValidationException(
                f"A profile named '{new_name}' already exists in this tenant"
            )

        return await self.repo.insert(
            tenant_id=auth_user.tenant_id, name=new_name.strip(),
            description=src.get("description"),
            location_path=src.get("location_path"),
            connection_id=src["connection_id"],
            schema_name=src["schema_name"], table_name=src["table_name"],
            sampling_mode=src["sampling_mode"], sample_size=src.get("sample_size"),
            drill_down=src["drill_down"], ai_enabled=src["ai_enabled"],
            created_by=auth_user.user_id,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_name(self, name: str) -> None:
        if not name or not name.strip():
            raise ValidationException("Profile name is required")
        if not _NAME_RE.match(name.strip()):
            raise ValidationException(
                "Profile name must be 1–255 chars, letters/digits/space/dot/dash/underscore only"
            )

    def _validate_location(self, location_path: str | None) -> None:
        if location_path is None:
            return
        if not _LOCATION_RE.match(location_path):
            raise ValidationException(
                "Location path may contain only letters/digits/space/dot/dash/underscore/slash, max 500 chars"
            )

    def _validate_sampling(self, mode: str, size: int | None) -> None:
        if mode not in _VALID_SAMPLING:
            raise ValidationException(
                f"sampling_mode must be one of {sorted(_VALID_SAMPLING)}"
            )
        if mode == "all":
            return
        if size is None or size <= 0:
            raise ValidationException(
                f"sampling_mode={mode} requires sample_size > 0"
            )
        if size > 10_000_000:
            raise ValidationException("sample_size capped at 10,000,000 rows")


def get_profile_service() -> ProfileService:
    return ProfileService()

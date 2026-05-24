"""Profile Asset CRUD orchestration (Phase 1.5).

A Profile is the unit of work — it owns scans, active rules, and (later)
score history. Connection/schema/table form the immutable source binding;
everything else (name, description, location, sampling, drill-down, AI on/off)
can be edited.
"""
from __future__ import annotations

import logging
import re
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.profile_repository import ProfileRepository
from app.products.data_sharing.repositories.connection_repository import (
    ConnectionRepository,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

def _stringify_value(v) -> str:
    """Coerce a sampled scalar to a JSON-safe string for the live-peek
    response. Bytes are dropped (BLOB-ish columns are noisy) and Decimals
    are rendered without scientific notation."""
    from datetime import date, datetime
    from decimal import Decimal
    if v is None:
        return ""
    if isinstance(v, (bytes, bytearray, memoryview)):
        return ""
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return format(v, "f")
    s = str(v)
    # Cap per-value length so a stray TEXT column doesn't bloat the payload.
    return s[:200]


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
        drill_down: bool, ai_enabled: bool,
        selected_columns: list[str] | None,
        auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._validate_name(name)
        self._validate_location(location_path)
        self._validate_sampling(sampling_mode, sample_size)
        self._validate_selected_columns(selected_columns)
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
            ai_enabled=ai_enabled, selected_columns=selected_columns,
            created_by=auth_user.user_id,
        )

    async def update_profile(
        self, profile_id: int, *,
        name: str | None = None, description: str | None = None,
        location_path: str | None = None,
        sampling_mode: str | None = None, sample_size: int | None = None,
        drill_down: bool | None = None, ai_enabled: bool | None = None,
        selected_columns: list[str] | None = None,
        entity_key_columns: list[str] | None = None,
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
        if selected_columns is not None:
            self._validate_selected_columns(selected_columns)
        if entity_key_columns is not None:
            self._validate_entity_key_columns(entity_key_columns)

        return await self.repo.update(
            profile_id, auth_user.tenant_id,
            name=name, description=description, location_path=location_path,
            sampling_mode=sampling_mode, sample_size=sample_size,
            drill_down=drill_down, ai_enabled=ai_enabled,
            selected_columns=selected_columns,
            entity_key_columns=entity_key_columns,
        )

    async def set_entity_key(
        self, profile_id: int, entity_key_columns: list[str],
        *, auth_user: AuthUser,
    ) -> dict:
        """Dedicated entrypoint for the entity-key override UI. Validates
        the list (empty allowed = clear) and LOCKS the value so future
        scans don't overwrite the user's choice. The unlock path is
        clear_entity_key()."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Profile not found")
        self._validate_entity_key_columns(entity_key_columns)
        return await self.repo.update(
            profile_id, auth_user.tenant_id,
            entity_key_columns=entity_key_columns,
            entity_key_locked=True,
        )

    async def clear_entity_key(
        self, profile_id: int, *, auth_user: AuthUser,
    ) -> dict:
        """Reset the entity key to auto-detect mode: clear the columns
        AND release the lock so the next scan can re-populate from
        declared PK / heuristics."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Profile not found")
        return await self.repo.update(
            profile_id, auth_user.tenant_id,
            entity_key_columns=[],
            entity_key_locked=False,
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
            selected_columns=src.get("selected_columns"),
            created_by=auth_user.user_id,
        )

    # ------------------------------------------------------------------
    # Live column inspection (NOT persisted)
    # ------------------------------------------------------------------

    async def column_sample_stats(
        self, profile_id: int, column_name: str, *,
        top_limit: int = 10, auth_user: AuthUser,
    ) -> dict:
        """Live-fetch the most-frequent values for one column on the
        profile's bound source table. **Nothing is persisted** — the
        result is computed on-demand and returned to the caller.

        This is the live-peek lane for the redesigned scan-results Tiles
        view (the "القيم الأكثر تكرارا" / Most-frequent-values tile).
        Migration 013 forbids storing raw row values, and migration 023's
        header preserves that boundary for top values specifically.

        Returns: ``{"column_name", "top_values": [{value, count}], "limit"}``.
        On column-not-found or connector failure, returns the partial dict
        with ``error`` populated rather than raising — the UI tile shows a
        muted "—" instead of failing the whole card."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        if not column_name or not column_name.strip():
            raise ValidationException("column_name is required")
        if top_limit < 1 or top_limit > 50:
            raise ValidationException("top_limit must be between 1 and 50")

        profile = await self.repo.find_by_id(profile_id, auth_user.tenant_id)
        if not profile:
            raise ResourceNotFoundException("Profile not found")

        conn = await self.connection_repo.find_by_id(
            profile["connection_id"], auth_user.tenant_id,
        )
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        # Lazy-import to avoid the circular dep between profile_service and
        # profiler_service (profiler imports profile_service indirectly).
        from app.products.data_quality.services.profiler_service import (
            _qualified_table, _quote_ident,
        )

        db_type = conn["db_type"]
        qcol = _quote_ident(db_type, column_name)
        qtable = _qualified_table(db_type, profile["schema_name"], profile["table_name"])

        gateway = DbConnectorGateway(
            db_type=db_type, username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database") or "",
        )
        try:
            # SELECT col, COUNT(*) GROUP BY col ORDER BY count DESC LIMIT N
            # All target dialects accept this form. MSSQL needs TOP, Oracle
            # needs FETCH FIRST.
            base = (
                f"SELECT {qcol} AS v, COUNT(*) AS c FROM {qtable} "
                f"WHERE {qcol} IS NOT NULL GROUP BY {qcol} ORDER BY c DESC"
            )
            if db_type == "mssql":
                sql = (
                    f"SELECT TOP {top_limit} {qcol} AS v, COUNT(*) AS c FROM {qtable} "
                    f"WHERE {qcol} IS NOT NULL GROUP BY {qcol} ORDER BY c DESC"
                )
            elif db_type == "oracle":
                sql = base + f" FETCH FIRST {top_limit} ROWS ONLY"
            else:
                sql = base + f" LIMIT {top_limit}"

            result = await gateway.execute_query(sql)
            if not result.success:
                logger.warning(
                    "column_sample_stats failed for profile=%s col=%s: %s",
                    profile_id, column_name, result.error,
                )
                return {
                    "column_name": column_name,
                    "top_values": [],
                    "limit": top_limit,
                    "error": result.error,
                }

            top_values = [
                {"value": _stringify_value(row[0]), "count": int(row[1])}
                for row in (result.data or {}).get("rows", [])
            ]
            return {
                "column_name": column_name,
                "top_values": top_values,
                "limit": top_limit,
            }
        finally:
            await gateway.close()

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

    def _validate_selected_columns(self, cols: list[str] | None) -> None:
        """``selected_columns`` is a TEXT[] of source column names. We allow
        an empty list (deliberate "scan nothing" — degenerate but legal at
        the schema level; the profiler raises a clearer error at run time)
        but enforce shape and a sane upper bound so a tenant can't paste a
        million-element array."""
        if cols is None:
            return
        if not isinstance(cols, list):
            raise ValidationException("selected_columns must be a list of strings")
        if len(cols) > 2000:
            raise ValidationException("selected_columns capped at 2000 entries")
        for c in cols:
            if not isinstance(c, str) or not c.strip():
                raise ValidationException(
                    "selected_columns entries must be non-empty strings"
                )
            if len(c) > 255:
                raise ValidationException(
                    "selected_columns entries capped at 255 chars"
                )

    def _validate_entity_key_columns(self, cols: list[str]) -> None:
        """Empty list is legal (clears the override; uniqueness rules
        revert to globally-unique behaviour). Non-empty must be plain
        column-name strings — same shape rules as selected_columns,
        capped tighter because a composite key with more than a handful
        of columns is almost certainly a mistake."""
        if not isinstance(cols, list):
            raise ValidationException("entity_key_columns must be a list of strings")
        if len(cols) > 10:
            raise ValidationException(
                "entity_key_columns capped at 10 entries — a business "
                "entity key spanning more than 10 columns is almost "
                "certainly a modelling error."
            )
        seen: set[str] = set()
        for c in cols:
            if not isinstance(c, str) or not c.strip():
                raise ValidationException(
                    "entity_key_columns entries must be non-empty strings"
                )
            if len(c) > 255:
                raise ValidationException(
                    "entity_key_columns entries capped at 255 chars"
                )
            if c in seen:
                raise ValidationException(
                    f"entity_key_columns contains duplicate '{c}'"
                )
            seen.add(c)

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

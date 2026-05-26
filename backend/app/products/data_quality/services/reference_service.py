"""Reference CRUD + value management.

A reference is a reusable named list of allowed values (e.g. "Saudi Banks").
``dictionary_match`` concepts point at one via ``parameter.reference_id``;
the validator pulls the value list from t_dq_reference_values at scan time.
"""
from __future__ import annotations

from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.reference_repository import (
    ReferenceRepository,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import (
    ConflictException, ResourceNotFoundException, ValidationException,
)

# Same caps as the old inline-values shape — keep the IN-clause size
# bounded and reject pathological pastes early.
_MAX_VALUES = 5000
_MAX_VALUE_LEN = 200
_MAX_NAME_LEN = 120


def _normalize_values(raw: list, *, case_sensitive: bool) -> list[str]:
    """Strip blanks, dedupe (case-aware), enforce per-value length limit.
    Returns the cleaned list ready to persist."""
    if not isinstance(raw, list):
        raise ValidationException("values must be an array")
    if len(raw) > _MAX_VALUES:
        raise ValidationException(
            f"reference accepts up to {_MAX_VALUES} values (got {len(raw)})"
        )
    out: list[str] = []
    seen: set[str] = set()
    for v in raw:
        if v is None:
            continue
        if not isinstance(v, (str, int, float)):
            raise ValidationException(
                f"reference values must be strings (got {type(v).__name__})"
            )
        s = str(v).strip()
        if not s:
            continue
        if len(s) > _MAX_VALUE_LEN:
            raise ValidationException(
                f"reference value exceeds {_MAX_VALUE_LEN} chars: {s[:40]}…"
            )
        key = s if case_sensitive else s.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


class ReferenceService:

    def __init__(self) -> None:
        self.repo = ReferenceRepository()

    async def list_references(self, auth_user: AuthUser) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self.repo.find_by_tenant(auth_user.tenant_id)

    async def get_reference(
        self, reference_id: int, auth_user: AuthUser, *, with_values: bool = True,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        row = await self.repo.find_by_id(reference_id, auth_user.tenant_id)
        if not row:
            raise ResourceNotFoundException("Reference not found")
        out = dict(row)
        if with_values:
            out["values"] = await self.repo.list_values(reference_id)
        return out

    async def create_reference(
        self, *, name: str, description: str | None, case_sensitive: bool,
        values: list[str], auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        name = (name or "").strip()
        if not name:
            raise ValidationException("name is required")
        if len(name) > _MAX_NAME_LEN:
            raise ValidationException(f"name exceeds {_MAX_NAME_LEN} chars")
        # Pre-check the unique constraint so we can return a friendly error
        # instead of the raw PG violation.
        if await self.repo.find_by_name(auth_user.tenant_id, name):
            raise ConflictException(f"Reference '{name}' already exists")

        cleaned = _normalize_values(values or [], case_sensitive=case_sensitive)
        row = await self.repo.insert(
            tenant_id=auth_user.tenant_id, name=name,
            description=(description or None),
            case_sensitive=case_sensitive,
            is_seed=False, created_by=auth_user.user_id,
        )
        if cleaned:
            await self.repo.replace_values(row["id"], cleaned)
        out = dict(row)
        out["values"] = await self.repo.list_values(row["id"])
        return out

    async def update_reference(
        self, reference_id: int, *,
        name: str | None, description: str | None,
        case_sensitive: bool | None, values: list[str] | None,
        auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(reference_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Reference not found")
        if name is not None:
            name = name.strip()
            if not name:
                raise ValidationException("name cannot be empty")
            if len(name) > _MAX_NAME_LEN:
                raise ValidationException(f"name exceeds {_MAX_NAME_LEN} chars")
            if name != existing["name"]:
                collision = await self.repo.find_by_name(auth_user.tenant_id, name)
                if collision and collision["id"] != reference_id:
                    raise ConflictException(f"Reference '{name}' already exists")

        row = await self.repo.update(
            reference_id, auth_user.tenant_id,
            name=name, description=description, case_sensitive=case_sensitive,
        )

        if values is not None:
            effective_cs = (case_sensitive if case_sensitive is not None
                            else existing["case_sensitive"])
            cleaned = _normalize_values(values, case_sensitive=effective_cs)
            await self.repo.replace_values(reference_id, cleaned)

        out = dict(row)
        out["values"] = await self.repo.list_values(reference_id)
        return out

    async def delete_reference(
        self, reference_id: int, auth_user: AuthUser,
    ) -> None:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(reference_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Reference not found")
        blockers = await self.repo.find_delete_blockers(
            reference_id, auth_user.tenant_id,
        )
        if blockers["concept_count"] > 0:
            preview = ", ".join(
                f"{c['dimension']}/{c['concept']}"
                for c in blockers["concepts"][:5]
            )
            if blockers["concept_count"] > 5:
                preview += f", +{blockers['concept_count'] - 5} more"
            raise ConflictException(
                f"Cannot delete reference '{existing['name']}' — it is still "
                f"used by {blockers['concept_count']} concept(s): {preview}. "
                f"Re-point those concepts at a different reference first."
            )
        await self.repo.delete(reference_id, auth_user.tenant_id)


def get_reference_service() -> ReferenceService:
    return ReferenceService()

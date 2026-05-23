"""Dictionary CRUD + default-seed orchestration."""
from __future__ import annotations

import json
import re

from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.concept_repository import ConceptRepository
from app.products.data_quality.services.concept_seed import all_seed_concepts
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ConflictException, ResourceNotFoundException, ValidationException


def _coerce_concept(row: dict | None) -> dict | None:
    """asyncpg returns jsonb columns as strings when no codec is registered.
    FastAPI then serializes the string verbatim, so the frontend receives
    `parameter` as `'{"pattern":"..."}'` instead of `{"pattern":"..."}` —
    making `c.parameter.pattern` undefined client-side. Parse it here so
    every concept response is consistent. Mirrors _coerce_jsonb in
    active_rule_service."""
    if row is None:
        return None
    raw = row.get("parameter")
    if isinstance(raw, str):
        try:
            row["parameter"] = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            row["parameter"] = {}
    elif raw is None:
        row["parameter"] = {}
    return row

_VALID_DIMENSIONS = {"completeness", "validity", "uniqueness"}
_VALID_RULE_TYPES = {"not_null", "max_null_rate", "no_pseudo_nulls", "unique", "format_regex"}
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_VALID_SEMANTIC_TYPES = {"master_data", "transaction", "event_log",
                        "reference", "staging", "snapshot"}


def _normalize_synonyms(syns: list[str] | None) -> list[str]:
    """Lowercase + dedupe + drop empties. Synonym matching is case-insensitive
    so storing pre-normalized values keeps the matcher (Step 3b) trivial."""
    if not syns:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for s in syns:
        if not isinstance(s, str):
            continue
        n = s.strip().lower()
        if n and n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _validate_parameter(rule_type: str, parameter: dict) -> dict:
    """Per-rule parameter sanity. Reject early with a clear error so the UI
    can surface it before the user wastes time tuning a broken concept."""
    parameter = parameter or {}
    if rule_type == "format_regex":
        pattern = parameter.get("pattern")
        if not pattern or not isinstance(pattern, str):
            raise ValidationException("format_regex requires parameter.pattern (string)")
        try:
            re.compile(pattern)
        except re.error as e:
            raise ValidationException(f"Invalid regex pattern: {e}") from e
    elif rule_type == "max_null_rate":
        thr = parameter.get("threshold")
        if thr is None or not isinstance(thr, (int, float)) or not (0 <= thr <= 1):
            raise ValidationException(
                "max_null_rate requires parameter.threshold in [0, 1]"
            )
    # not_null / unique / no_pseudo_nulls take no parameters; ignore extras.
    return parameter


class ConceptService:

    def __init__(self) -> None:
        self.repo = ConceptRepository()

    async def list_concepts(
        self, auth_user: AuthUser, *, dimension: str | None = None,
        enabled_only: bool = False,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        if dimension is not None and dimension not in _VALID_DIMENSIONS:
            raise ValidationException(f"Unknown dimension: {dimension}")
        rows = await self.repo.find_by_tenant(
            auth_user.tenant_id, dimension=dimension, enabled_only=enabled_only,
        )
        return [_coerce_concept(r) for r in rows]

    async def get_concept(self, concept_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        row = await self.repo.find_by_id(concept_id, auth_user.tenant_id)
        if not row:
            raise ResourceNotFoundException("Concept not found")
        return _coerce_concept(row)

    async def create_concept(self, *, dimension: str, concept: str,
                             synonyms: list[str], rule_type: str,
                             parameter: dict, severity: str,
                             applies_to_types: list[str] | None,
                             notes: str | None, enabled: bool,
                             auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        self._validate_inputs(dimension, concept, rule_type, severity, applies_to_types)
        parameter = _validate_parameter(rule_type, parameter)
        row = await self.repo.insert(
            tenant_id=auth_user.tenant_id, dimension=dimension,
            concept=concept.strip(), synonyms=_normalize_synonyms(synonyms),
            rule_type=rule_type, parameter=parameter, severity=severity,
            applies_to_types=applies_to_types or None, notes=notes,
            enabled=enabled, is_seed=False, created_by=auth_user.user_id,
        )
        return _coerce_concept(row)

    async def update_concept(self, concept_id: int, *, synonyms: list[str] | None,
                             rule_type: str | None, parameter: dict | None,
                             severity: str | None, applies_to_types: list[str] | None,
                             notes: str | None, enabled: bool | None,
                             auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        # Make sure the row belongs to the caller's tenant before touching it.
        existing = await self.repo.find_by_id(concept_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Concept not found")

        # Validate only the fields the caller actually set.
        if rule_type is not None and rule_type not in _VALID_RULE_TYPES:
            raise ValidationException(f"Invalid rule_type: {rule_type}")
        if severity is not None and severity not in _VALID_SEVERITIES:
            raise ValidationException(f"Invalid severity: {severity}")
        if applies_to_types is not None:
            self._validate_semantic_types(applies_to_types)

        # Parameter validation needs both new and existing rule_type.
        effective_rule_type = rule_type or existing["rule_type"]
        if parameter is not None:
            parameter = _validate_parameter(effective_rule_type, parameter)

        row = await self.repo.update(
            concept_id, auth_user.tenant_id,
            synonyms=_normalize_synonyms(synonyms) if synonyms is not None else None,
            rule_type=rule_type, parameter=parameter, severity=severity,
            applies_to_types=applies_to_types, notes=notes, enabled=enabled,
        )
        return _coerce_concept(row)

    async def delete_concept(self, concept_id: int, auth_user: AuthUser) -> None:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.repo.find_by_id(concept_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Concept not found")
        # Pre-check the t_dq_issues.concept_id FK (RESTRICT). Without this,
        # the DB raises a raw FK violation that leaks as a 500.
        blockers = await self.repo.find_delete_blockers(concept_id, auth_user.tenant_id)
        if blockers["issue_count"] > 0:
            profiles = sorted(blockers["profile_ids"] or [])
            preview = ", ".join(str(p) for p in profiles[:5])
            if len(profiles) > 5:
                preview += f", +{len(profiles) - 5} more"
            raise ConflictException(
                f"Cannot delete concept '{existing['concept']}' — it is still "
                f"referenced by {blockers['issue_count']} scan issue(s) across "
                f"{blockers['profile_count']} profile(s) "
                f"(profile id: {preview}). "
                f"Delete those profiles (or just their scans) first, then retry."
            )
        await self.repo.delete(concept_id, auth_user.tenant_id)

    async def seed_defaults(self, auth_user: AuthUser) -> dict:
        """Idempotent: inserts seed concepts that don't already exist for the
        caller's tenant. Existing concepts (including user-edited ones) are
        untouched."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing_before = await self.repo.find_by_tenant(auth_user.tenant_id)
        existing_keys = {(c["dimension"], c["concept"]) for c in existing_before}

        inserted = 0
        for dimension, c in all_seed_concepts():
            if (dimension, c["concept"]) in existing_keys:
                continue
            await self.repo.upsert_seed(
                tenant_id=auth_user.tenant_id,
                dimension=dimension,
                concept=c["concept"],
                synonyms=_normalize_synonyms(c["synonyms"]),
                rule_type=c["rule_type"],
                parameter=c.get("parameter", {}),
                severity=c.get("severity", "medium"),
                applies_to_types=c.get("applies_to_types"),
                notes=c.get("notes"),
            )
            inserted += 1

        return {"inserted": inserted, "total_after": len(existing_before) + inserted}

    async def refresh_seeded(self, auth_user: AuthUser) -> dict:
        """Re-apply the current seed file to every is_seed=TRUE concept for
        the caller's tenant. Missing concepts are inserted; existing seeded
        rows have their synonyms/rule/parameter/severity/notes overwritten
        from the seed file. User-customized rows (is_seed=FALSE) are left
        untouched. Use this to backfill fields that were added to the seed
        after the original install (e.g. regex patterns)."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing_before = await self.repo.find_by_tenant(auth_user.tenant_id)
        by_key = {(c["dimension"], c["concept"]): c for c in existing_before}

        inserted = updated = skipped_custom = 0
        for dimension, c in all_seed_concepts():
            existing = by_key.get((dimension, c["concept"]))
            if existing is None:
                inserted += 1
            elif existing["is_seed"]:
                updated += 1
            else:
                skipped_custom += 1
                continue  # don't call refresh_seed — DO UPDATE would no-op anyway
            await self.repo.refresh_seed(
                tenant_id=auth_user.tenant_id,
                dimension=dimension,
                concept=c["concept"],
                synonyms=_normalize_synonyms(c["synonyms"]),
                rule_type=c["rule_type"],
                parameter=c.get("parameter", {}),
                severity=c.get("severity", "medium"),
                applies_to_types=c.get("applies_to_types"),
                notes=c.get("notes"),
            )

        return {
            "inserted": inserted,
            "updated": updated,
            "skipped_custom": skipped_custom,
            "total_after": len(existing_before) + inserted,
        }

    # -- internals ----------------------------------------------------------

    def _validate_inputs(
        self, dimension: str, concept: str, rule_type: str, severity: str,
        applies_to_types: list[str] | None,
    ) -> None:
        if dimension not in _VALID_DIMENSIONS:
            raise ValidationException(f"Invalid dimension: {dimension}")
        if not concept or not concept.strip():
            raise ValidationException("concept is required")
        if rule_type not in _VALID_RULE_TYPES:
            raise ValidationException(f"Invalid rule_type: {rule_type}")
        if severity not in _VALID_SEVERITIES:
            raise ValidationException(f"Invalid severity: {severity}")
        if applies_to_types:
            self._validate_semantic_types(applies_to_types)

    def _validate_semantic_types(self, types: list[str]) -> None:
        bad = [t for t in types if t not in _VALID_SEMANTIC_TYPES]
        if bad:
            raise ValidationException(
                f"Unknown semantic types: {bad}. Allowed: {sorted(_VALID_SEMANTIC_TYPES)}"
            )


def get_concept_service() -> ConceptService:
    return ConceptService()

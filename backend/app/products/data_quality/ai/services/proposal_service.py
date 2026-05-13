"""Proposal review + applier — Step 6.7.

The single boundary-crossing service in the ``ai/`` subsystem: this is
the only module allowed to import from the deterministic ``services/``,
``repositories/``, ``routers/`` layers, and it does so only at
human-approval time. Everything else in ``ai/`` stays one-way.

What "approve a proposal" means today (kind=new_concept only — other
kinds land in Steps 6.4/6.6 and aren't yet generated):

  1. Read payload {name, dimension, rule_type, parameter, severity,
     synonyms, applies_to_types, _target_table, _target_column}.
  2. Look up or insert the concept at (tenant_id, dimension, name).
     Parameter is shaped per rule_type (format_regex -> {"pattern": ...},
     max_null_rate -> {"threshold": ...}, others -> {}).
  3. If _target_table is set AND a profile exists for that table in
     the tenant, upsert an active_rule binding with matched_by=manual,
     confidence=high, approval_status=auto_applied. Picks the first
     matching profile by id when multiple exist (one-table-many-profiles
     is rare and the reviewer can fix up afterwards).
  4. Mark the proposal as approved, set applied_target_id = concept.id,
     applied_target_kind = "concept" (or "active_rule" if a binding
     also landed).

Idempotency: a re-approve walks the same path and returns the same
concept_id without duplicating. The active_rule_repository.upsert()
already preserves human approval_status overrides.

Rollback (Step 6.8) walks applied_target_id back in reverse insertion
order, refusing if t_dq_issues references the binding.
"""
from __future__ import annotations

import json
import logging

from app.products.data_quality.ai.repositories.import_repository import (
    ImportRepository,
)
from app.products.data_quality.ai.repositories.proposal_repository import (
    ProposalRepository,
)
from app.products.data_quality.permissions import can_use_dq, require
# ↓ Cross-boundary imports — the documented exception. Everything else
#   in ai/ stays one-way (services/repositories/routers don't import ai/).
from app.products.data_quality.repositories.active_rule_repository import (
    ActiveRuleRepository,
)
from app.products.data_quality.repositories.concept_repository import (
    ConceptRepository,
)
from app.products.data_quality.repositories.profile_repository import (
    ProfileRepository,
)
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)


def _jsonb_to_dict(value) -> dict:
    """asyncpg returns JSONB columns as raw strings by default. Normalise
    to a dict (or empty dict) so callers can ``.get()`` / ``.update()``
    without surprises."""
    if value is None or value == "":
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _shape_parameter(rule_type: str, raw: str | None) -> dict:
    """Convert the proposal's flat-string parameter into the JSONB shape
    that t_dq_concepts.parameter expects per rule_type."""
    if raw is None or raw == "":
        return {}
    if rule_type == "format_regex":
        return {"pattern": raw}
    if rule_type == "max_null_rate":
        try:
            return {"threshold": float(raw)}
        except (TypeError, ValueError):
            return {"threshold": 0.05}
    # not_null / no_pseudo_nulls / unique take no parameter.
    return {}


class _ProfileByTableLookup(PostgresqlAsyncRepository):
    """Inline helper — same shape as the candidate-column query in 6.6
    but returns the profile itself so we can write an active_rule."""

    async def first_for_table(self, tenant_id: int, table_name: str) -> dict | None:
        return await self._fetch_row_optional(
            """SELECT id, tenant_id, connection_id, schema_name, table_name
                 FROM dq.t_dq_profiles
                WHERE tenant_id = $1 AND table_name = $2
             ORDER BY id
                LIMIT 1""",
            (tenant_id, table_name),
        )


class ProposalService:

    def __init__(self) -> None:
        self.proposals = ProposalRepository()
        self.imports = ImportRepository()
        self.concepts = ConceptRepository()
        self.active_rules = ActiveRuleRepository()
        self.profiles = ProfileRepository()
        self.profile_lookup = _ProfileByTableLookup()

    # ------------------------------------------------------------------
    # Reads
    # ------------------------------------------------------------------

    async def list_for_tenant(
        self, auth_user: AuthUser, *,
        status: str | None = None, limit: int = 200,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self.proposals.list_for_tenant(
            auth_user.tenant_id, status=status, limit=limit,
        )

    async def list_for_import(
        self, import_id: int, auth_user: AuthUser, *,
        status: str | None = None, confidence: str | None = None,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        # Tenant-scope check via the import.
        imp = await self.imports.find_by_id(import_id, auth_user.tenant_id)
        if not imp:
            raise ResourceNotFoundException("Import not found")
        return await self.proposals.list_for_import(
            import_id, auth_user.tenant_id,
            status=status, confidence=confidence,
        )

    async def get(self, proposal_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        row = await self.proposals.find_by_id(proposal_id, auth_user.tenant_id)
        if not row:
            raise ResourceNotFoundException("Proposal not found")
        return row

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    async def reject(
        self, proposal_id: int, auth_user: AuthUser, *,
        reason: str | None,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        prop = await self.proposals.find_by_id(proposal_id, auth_user.tenant_id)
        if not prop:
            raise ResourceNotFoundException("Proposal not found")
        if prop["status"] in ("approved", "rolled_back"):
            raise ValidationException(
                f"Proposal is {prop['status']}; reject would orphan applied rules"
            )
        final_value = {"rejected_reason": reason} if reason else None
        return await self.proposals.mark_reviewed(
            proposal_id, auth_user.tenant_id,
            status="rejected", final_value=final_value,
            reviewer_id=auth_user.user_id,
        )

    async def approve(
        self, proposal_id: int, auth_user: AuthUser, *,
        final_value_override: dict | None = None,
    ) -> dict:
        """Apply a proposal. ``final_value_override`` lets the reviewer
        tweak fields (column, parameter, severity, etc.) before save."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        prop = await self.proposals.find_by_id(proposal_id, auth_user.tenant_id)
        if not prop:
            raise ResourceNotFoundException("Proposal not found")
        if prop["status"] == "approved":
            # Idempotent: return the existing row unchanged.
            return prop
        if prop["status"] in ("rejected", "rolled_back", "rejected_by_validator"):
            raise ValidationException(
                f"Cannot approve a proposal in status {prop['status']!r}"
            )
        if prop["kind"] != "new_concept":
            raise ValidationException(
                f"Proposal kind {prop['kind']!r} not yet supported by the applier"
            )

        # Merge override onto payload — overrides win. JSONB columns come
        # back from asyncpg as strings, so normalise first.
        payload = _jsonb_to_dict(prop["payload"])
        if final_value_override:
            payload.update(final_value_override)

        name = (payload.get("name") or "").strip()
        dimension = payload.get("dimension")
        rule_type = payload.get("rule_type")
        parameter_raw = payload.get("parameter")
        severity = payload.get("severity") or "medium"
        synonyms = payload.get("synonyms") or []
        applies_to = payload.get("applies_to_types") or []
        target_table = payload.get("_target_table")
        target_column = payload.get("_target_column")

        if not name or not dimension or not rule_type:
            raise ValidationException(
                "Proposal payload missing required fields (name/dimension/rule_type)"
            )

        # ---- Concept upsert ------------------------------------------
        # Find existing concept by (tenant, dimension, name).
        existing = [
            c for c in await self.concepts.find_by_tenant(
                auth_user.tenant_id, dimension=dimension,
            )
            if c["concept"] == name
        ]
        if existing:
            concept = existing[0]
            # Patch parameter / severity / synonyms if the override changed them.
            concept = await self.concepts.update(
                concept["id"], auth_user.tenant_id,
                synonyms=synonyms,
                rule_type=rule_type,
                parameter=_shape_parameter(rule_type, parameter_raw),
                severity=severity,
                applies_to_types=applies_to,
                enabled=True,
            )
        else:
            concept = await self.concepts.insert(
                tenant_id=auth_user.tenant_id,
                dimension=dimension, concept=name,
                synonyms=synonyms, rule_type=rule_type,
                parameter=_shape_parameter(rule_type, parameter_raw),
                severity=severity,
                applies_to_types=(applies_to or None),
                notes=None, enabled=True, is_seed=False,
                created_by=auth_user.user_id,
            )

        # ---- Optional active_rule binding ----------------------------
        applied_kind = "concept"
        applied_id = concept["id"]
        if target_table and target_column:
            profile = await self.profile_lookup.first_for_table(
                auth_user.tenant_id, target_table,
            )
            if profile:
                rule = await self.active_rules.upsert(
                    tenant_id=auth_user.tenant_id,
                    profile_id=profile["id"],
                    connection_id=profile["connection_id"],
                    schema_name=profile["schema_name"],
                    table_name=profile["table_name"],
                    column_name=target_column,
                    concept_id=concept["id"],
                    matched_by="manual",
                    confidence="high",
                    matcher_score=1.0,
                    matcher_reasoning=(
                        f"Created from proposal #{proposal_id} "
                        f"({prop['source_row'] and 'Excel row ' + str(prop['source_row'])})"
                    ),
                    approval_status="auto_applied",
                )
                applied_kind = "active_rule"
                applied_id = rule["id"]
            else:
                logger.info(
                    "Proposal #%s approved but no profile exists for table %r — "
                    "binding skipped (concept created)",
                    proposal_id, target_table,
                )

        # ---- Mark proposal approved ----------------------------------
        return await self.proposals.mark_reviewed(
            proposal_id, auth_user.tenant_id, status="approved",
            final_value=payload, reviewer_id=auth_user.user_id,
            applied_target_id=applied_id, applied_target_kind=applied_kind,
        )

    async def bulk_approve_high(
        self, import_id: int, auth_user: AuthUser,
    ) -> dict:
        """Approve every HIGH-confidence pending proposal under an import.
        Returns a summary {approved: int, skipped: int, errors: [...]}.
        Best-effort: per-row errors don't fail the bulk operation."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        imp = await self.imports.find_by_id(import_id, auth_user.tenant_id)
        if not imp:
            raise ResourceNotFoundException("Import not found")

        rows = await self.proposals.list_for_import(
            import_id, auth_user.tenant_id,
            status="pending", confidence="HIGH",
        )

        approved = 0
        skipped = 0
        errors: list[dict] = []
        for r in rows:
            try:
                await self.approve(r["id"], auth_user)
                approved += 1
            except Exception as e:  # noqa: BLE001
                errors.append({"proposal_id": r["id"], "error": str(e)})
                skipped += 1
                logger.warning(
                    "bulk-approve: proposal #%s failed: %s", r["id"], e,
                )
        return {
            "import_id": import_id,
            "approved": approved,
            "skipped": skipped,
            "errors": errors,
            "matched_count": len(rows),
        }


def get_proposal_service() -> ProposalService:
    return ProposalService()

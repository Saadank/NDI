"""Concept matcher orchestrator + active-rule lifecycle.

Public surface (used by the router):
- preview_table(...)  -> compute matches, do NOT persist
- apply_table(...)    -> compute matches, upsert into t_dq_active_rules
- list_for_table(...) -> read materialized rules (with concept join)
- approve(...) / block(...) / unblock(...) — human moderation

Internally:
- get_columns_with_profile() pulls live column metadata from the source DB and
  joins with the latest column-profile rows from the most recent successful
  scan (so the LLM has stats to work with).
- _match_one_column() runs fuzzy first; if no fuzzy hit, escalates to LLM.
- HIGH-confidence matches → approval_status='auto_applied'
  MEDIUM/LOW matches → approval_status='proposed'
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.active_rule_repository import (
    ActiveRuleRepository,
)
from app.products.data_quality.repositories.column_profile_repository import (
    ColumnProfileRepository,
)
from app.products.data_quality.repositories.concept_repository import ConceptRepository
from app.products.data_quality.repositories.profile_repository import ProfileRepository
from app.products.data_quality.repositories.table_type_repository import (
    TableTypeRepository,
)
from app.products.data_quality.ai.matchers import concept_matcher as llm_matcher
from app.products.data_quality.services import fuzzy_matcher
from app.products.data_sharing.repositories.connection_repository import (
    ConnectionRepository,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)


def _approval_status_for(confidence: str) -> str:
    return "auto_applied" if confidence == "high" else "proposed"


class ActiveRuleService:

    def __init__(self) -> None:
        self.active_repo = ActiveRuleRepository()
        self.concept_repo = ConceptRepository()
        self.column_profile_repo = ColumnProfileRepository()
        self.type_repo = TableTypeRepository()
        self.connection_repo = ConnectionRepository()
        self.profile_asset_repo = ProfileRepository()

    # ------------------------------------------------------------------
    # Preview / apply
    # ------------------------------------------------------------------

    async def preview_profile(
        self, *, profile_id: int, auth_user: AuthUser,
    ) -> dict:
        """Run the matcher over every column of the profile's table and
        return proposals — without persisting."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self._compute_matches(
            profile_id=profile_id, tenant_id=auth_user.tenant_id, persist=False,
        )

    async def apply_profile(
        self, *, profile_id: int, auth_user: AuthUser,
    ) -> dict:
        """Run the matcher and persist results. HIGH → auto_applied,
        MEDIUM/LOW → proposed. Approved/blocked rows survive re-applies."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self._compute_matches(
            profile_id=profile_id, tenant_id=auth_user.tenant_id, persist=True,
        )

    async def list_for_profile(
        self, *, profile_id: int, auth_user: AuthUser,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self.active_repo.list_for_profile(
            tenant_id=auth_user.tenant_id, profile_id=profile_id,
        )

    # ------------------------------------------------------------------
    # Approval lifecycle
    # ------------------------------------------------------------------

    async def approve(self, rule_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.active_repo.find_by_id(rule_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Active rule not found")
        return await self.active_repo.update_approval(
            rule_id, auth_user.tenant_id,
            approval_status="approved", approved_by=auth_user.user_id,
            blocked_reason=None,
        )

    async def block(self, rule_id: int, reason: str | None,
                    auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.active_repo.find_by_id(rule_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Active rule not found")
        return await self.active_repo.update_approval(
            rule_id, auth_user.tenant_id,
            approval_status="blocked", approved_by=auth_user.user_id,
            blocked_reason=(reason or "").strip() or None,
        )

    async def bind_manual(
        self, *, profile_id: int, column_name: str, concept_id: int,
        auth_user: AuthUser,
    ) -> dict:
        """Hand-bind a concept to a specific column on a profile, bypassing
        the matcher. Lands as `auto_applied` so the validator picks it up on
        the next scan. Subsequent matcher applies will leave manual rows
        untouched (the upsert preserves human decisions)."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        profile = await self.profile_asset_repo.find_by_id(
            profile_id, auth_user.tenant_id,
        )
        if not profile:
            raise ResourceNotFoundException("Profile not found")
        if not column_name or not column_name.strip():
            raise ValidationException("column_name is required")

        concept = await self.concept_repo.find_by_id(
            concept_id, auth_user.tenant_id,
        )
        if not concept:
            raise ResourceNotFoundException("Concept not found")

        return await self.active_repo.upsert(
            tenant_id=auth_user.tenant_id, profile_id=profile_id,
            connection_id=profile["connection_id"],
            schema_name=profile["schema_name"],
            table_name=profile["table_name"],
            column_name=column_name.strip(), concept_id=concept_id,
            matched_by="manual", confidence="high",
            matcher_score=None,
            matcher_reasoning=f"Manually bound by user #{auth_user.user_id}",
            approval_status="auto_applied",
        )

    async def unblock(self, rule_id: int, auth_user: AuthUser) -> dict:
        """Move blocked → proposed. The user can then approve or let the
        next matcher pass refresh it."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        existing = await self.active_repo.find_by_id(rule_id, auth_user.tenant_id)
        if not existing:
            raise ResourceNotFoundException("Active rule not found")
        return await self.active_repo.update_approval(
            rule_id, auth_user.tenant_id,
            approval_status="proposed", approved_by=None,
            blocked_reason=None,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _compute_matches(
        self, *, profile_id: int, tenant_id: int, persist: bool,
    ) -> dict:
        # 1. Resolve the profile (provides connection + schema + table).
        profile = await self.profile_asset_repo.find_by_id(profile_id, tenant_id)
        if not profile:
            raise ResourceNotFoundException("Profile not found")
        connection_id = profile["connection_id"]
        schema_name = profile["schema_name"]
        table_name = profile["table_name"]

        conn = await self.connection_repo.find_by_id(connection_id, tenant_id)
        if not conn:
            raise ResourceNotFoundException("Connection not found")

        # Table must be tagged with a semantic type — matcher needs it.
        type_row = await self.type_repo.find_one(
            connection_id, schema_name, table_name, tenant_id,
        )
        if not type_row:
            raise ValidationException(
                "Table is untagged. Assign a semantic type before running the matcher."
            )
        semantic_type = type_row["semantic_type"]

        # 2. Get the column list. Prefer the latest profile (gives the LLM
        # statistics + patterns). Fall back to information_schema if no scan
        # has run yet — the LLM still works, just with less context.
        columns = await self._get_columns_for_matching(
            tenant_id=tenant_id, connection_id=connection_id,
            schema_name=schema_name, table_name=table_name, conn=conn,
        )
        if not columns:
            return {
                "table": {"schema_name": schema_name, "table_name": table_name,
                          "semantic_type": semantic_type},
                "columns": [], "llm_used": False,
                "warning": "No columns found.",
            }

        # 3. Get the dictionary (enabled only — disabled concepts are skipped).
        concepts = await self.concept_repo.find_by_tenant(
            tenant_id, enabled_only=True,
        )
        if not concepts:
            return {
                "table": {"schema_name": schema_name, "table_name": table_name,
                          "semantic_type": semantic_type},
                "columns": [{"column_name": c["column_name"], "matches": []} for c in columns],
                "llm_used": False,
                "warning": "Dictionary is empty. Seed defaults from the Dictionary tab.",
            }

        # 4. Match each column.
        per_column: list[dict] = []
        llm_called = False
        all_concept_ids: list[int] = []
        for col in columns:
            col_name = col["column_name"]
            fuzzy_hits = fuzzy_matcher.match_column_against_concepts(
                col_name, concepts, semantic_type=semantic_type,
            )

            if fuzzy_hits:
                matches = fuzzy_hits
            else:
                # No fuzzy hit — try the LLM if available.
                if llm_matcher.is_available():
                    llm_called = True
                    matches = await llm_matcher.match_column(
                        col, concepts, semantic_type=semantic_type,
                    )
                else:
                    matches = []

            for m in matches:
                all_concept_ids.append(m["concept_id"])

            per_column.append({
                "column_name": col_name,
                "type_category": col.get("type_category"),
                "inferred_column_type": col.get("inferred_column_type"),
                "dominant_pattern": col.get("dominant_pattern"),
                "matches": matches,
            })

        # 5. Persist if requested.
        if persist:
            for col_entry in per_column:
                col_name = col_entry["column_name"]
                for m in col_entry["matches"]:
                    await self.active_repo.upsert(
                        tenant_id=tenant_id, profile_id=profile_id,
                        connection_id=connection_id,
                        schema_name=schema_name, table_name=table_name,
                        column_name=col_name, concept_id=m["concept_id"],
                        matched_by=m["matched_by"], confidence=m["confidence"],
                        matcher_score=m.get("matcher_score"),
                        matcher_reasoning=m.get("matcher_reasoning"),
                        approval_status=_approval_status_for(m["confidence"]),
                    )
            # Drop stale auto/proposed rows whose concept no longer matches.
            # Approved/blocked rows survive — those are human commitments.
            await self.active_repo.delete_stale_proposals_by_profile(
                tenant_id=tenant_id, profile_id=profile_id,
                keep_concept_ids=list(set(all_concept_ids)),
            )

        return {
            "profile_id": profile_id,
            "table": {"schema_name": schema_name, "table_name": table_name,
                      "semantic_type": semantic_type},
            "columns": per_column,
            "llm_used": llm_called,
            "llm_available": llm_matcher.is_available(),
            "persisted": persist,
        }

    async def _get_columns_for_matching(
        self, *, tenant_id: int, connection_id: UUID,
        schema_name: str, table_name: str, conn: dict,
    ) -> list[dict]:
        """Try the latest profile snapshot first; fall back to a live
        information_schema lookup if the table has never been scanned."""
        profiled = await self.column_profile_repo.find_latest_for_table(
            connection_id, schema_name, table_name, tenant_id,
        )
        if profiled:
            return profiled

        # Fall back: ask the source DB directly. This is rarer; we still
        # produce useful matches, just without the pattern signature.
        gateway = DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database") or "",
        )
        try:
            sql = (
                "SELECT column_name, data_type FROM information_schema.columns "
                f"WHERE table_schema = '{schema_name}' "
                f"AND table_name = '{table_name}' ORDER BY ordinal_position"
            )
            r = await gateway.execute_query(sql)
            if not r.success or not r.data:
                return []
            return [
                {"column_name": row[0], "declared_data_type": row[1],
                 "type_category": None, "inferred_column_type": None,
                 "dominant_pattern": None, "pattern_conformance_rate": None,
                 "top_patterns": [], "distinct_count": None,
                 "distinct_rate": None, "null_rate": None}
                for row in r.data["rows"]
            ]
        finally:
            await gateway.close()


def get_active_rule_service() -> ActiveRuleService:
    return ActiveRuleService()

"""Live violator examples for a uniqueness issue.

Returns up to N (target_value, entity_key_values…) pairs that show *why*
a uniqueness rule failed. Computed on-demand against the source DB —
**never persisted**. This honours the platform's privacy boundary
(migration 013 / validator_service.py header: raw row values stay in
the source; only counts and pattern signatures live in DQ storage).

Gated on the profile's `drill_down` flag. Privacy-conservative tenants
disable drill-down and see only summary counts on issues; they get a
clear 'disabled' message from this endpoint rather than partial data.
"""
from __future__ import annotations

import logging
from typing import Any

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.issue_repository import IssueRepository
from app.products.data_quality.repositories.profile_repository import ProfileRepository
from app.products.data_quality.services.profiler_service import (
    _PSEUDO_NULL_TOKENS, _qualified_table, _quote_ident,
)
from app.products.data_sharing.repositories.connection_repository import (
    ConnectionRepository,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

# Hard cap on returned examples and on the inner row scan. Both are tight
# on purpose: a uniqueness diagnostic is meant to be illustrative, not
# exhaustive. Anyone needing the full violator set should query the
# source DB directly.
_MAX_TARGETS = 3
_MAX_KEYS_PER_TARGET = 5
_INNER_ROW_LIMIT = 200


class ViolatorExamplesService:

    def __init__(self) -> None:
        self.issue_repo = IssueRepository()
        self.profile_repo = ProfileRepository()
        self.connection_repo = ConnectionRepository()

    async def for_issue(self, issue_id: int, *, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user),
                "Data Quality is not available for this account")

        issue = await self.issue_repo.find_by_id(issue_id, auth_user.tenant_id)
        if not issue:
            raise ResourceNotFoundException("Issue not found")
        if issue.get("rule_type") != "unique":
            raise ValidationException(
                "Violator examples are only available for uniqueness rules; "
                f"this issue is rule_type={issue.get('rule_type')!r}."
            )
        if issue.get("status") != "fail":
            # Nothing to show — the rule didn't fail. Return a clean empty
            # rather than raising; the UI can render "no violators" calmly.
            return _empty_response(issue, reason="rule passed; no violators")

        profile = await self.profile_repo.find_by_id(
            issue["profile_id"], auth_user.tenant_id,
        )
        if not profile:
            raise ResourceNotFoundException("Profile not found")

        if not profile.get("drill_down"):
            raise ValidationException(
                "Drill-down is disabled on this profile, so live violator "
                "examples are blocked. Enable 'Drill-down' on the Definition "
                "tab to allow this lookup. Counts remain visible on the issue."
            )

        entity_keys = list(profile.get("entity_key_columns") or [])
        # Exclude the target column from the entity-key list (same defensive
        # filter the validator applies — self-references collapse the check).
        target = issue["column_name"]
        entity_keys = [c for c in entity_keys if c and c != target]

        conn = await self.connection_repo.find_by_id(
            issue["connection_id"], auth_user.tenant_id,
        )
        if not conn:
            raise ResourceNotFoundException("Source connection not found")

        gateway = DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database") or "",
        )
        try:
            sql = _build_examples_sql(
                db_type=conn["db_type"],
                schema_name=issue["schema_name"], table_name=issue["table_name"],
                target_column=target, entity_key_columns=entity_keys,
            )
            if sql is None:
                # No entity key OR the dialect isn't supported by the
                # example-builder. Return empty with a hint rather than
                # erroring — the UI can show a graceful "not available".
                return _empty_response(
                    issue,
                    reason=("no entity key configured — set one on the "
                            "Definition tab to enable per-entity examples")
                    if not entity_keys
                    else f"live examples not implemented for {conn['db_type']}",
                )

            result = await gateway.execute_query(sql)
            if not result.success or not result.data:
                logger.warning(
                    "violator-examples query failed (issue=%s): %s",
                    issue_id, result.error,
                )
                return _empty_response(
                    issue, reason=f"query failed: {result.error}",
                )

            rows = (result.data or {}).get("rows", []) or []
            examples = _group_examples(rows)
            return {
                "issue_id": issue_id,
                "target_column": target,
                "entity_key_columns": entity_keys,
                "examples": examples,
                "row_limit_hit": len(rows) >= _INNER_ROW_LIMIT,
                "note": (
                    f"Up to {_MAX_TARGETS} target values, each with up to "
                    f"{_MAX_KEYS_PER_TARGET} entity-key examples. "
                    "Values are fetched live from the source — nothing is "
                    "persisted by this endpoint."
                ),
            }
        finally:
            await gateway.close()


# ---------------------------------------------------------------------------
# SQL builder
# ---------------------------------------------------------------------------

def _build_examples_sql(
    *, db_type: str, schema_name: str, table_name: str,
    target_column: str, entity_key_columns: list[str],
) -> str | None:
    """Construct a single SQL statement that returns flat
    (target_value, entity_key_value) rows for the top conflicting target
    values. Returns None when:
      - entity_key_columns is empty (no per-entity check; nothing to show)
      - the dialect isn't supported by this builder
    """
    if not entity_key_columns:
        return None
    db = (db_type or "").lower()
    if db not in {"postgresql", "mysql", "mariadb", "mssql", "oracle"}:
        return None

    qtable = _qualified_table(db, schema_name, table_name)
    qtarget = _quote_ident(db, target_column)
    no_pseudo = _pseudo_null_predicate(db, qtarget)

    # Build the entity-key expression. For composites we concat into a
    # single string so the CTE remains a flat two-column thing.
    if len(entity_key_columns) == 1:
        qkey_expr = _quote_ident(db, entity_key_columns[0])
        qkey_cast = _cast_to_text(db, qkey_expr)
    else:
        cast_parts = [
            _cast_to_text(db, _quote_ident(db, c))
            for c in entity_key_columns
        ]
        qkey_cast = _concat_ws(db, " | ", cast_parts)

    # Dialect-specific LIMIT for the outer top-K target picker.
    if db == "mssql":
        top_targets = (
            f"SELECT TOP {_MAX_TARGETS} v FROM ("
            f"  SELECT {qtarget} AS v, COUNT(DISTINCT {qkey_cast}) AS kc "
            f"  FROM {qtable} "
            f"  WHERE {qtarget} IS NOT NULL AND {no_pseudo} "
            f"  GROUP BY {qtarget} "
            f"  HAVING COUNT(DISTINCT {qkey_cast}) > 1"
            f") tt ORDER BY kc DESC, v"
        )
    elif db == "oracle":
        top_targets = (
            f"SELECT v FROM ("
            f"  SELECT {qtarget} AS v, COUNT(DISTINCT {qkey_cast}) AS kc "
            f"  FROM {qtable} "
            f"  WHERE {qtarget} IS NOT NULL AND {no_pseudo} "
            f"  GROUP BY {qtarget} "
            f"  HAVING COUNT(DISTINCT {qkey_cast}) > 1 "
            f"  ORDER BY kc DESC, v"
            f") FETCH FIRST {_MAX_TARGETS} ROWS ONLY"
        )
    else:
        # postgres / mysql / mariadb — standard LIMIT
        top_targets = (
            f"SELECT v FROM ("
            f"  SELECT {qtarget} AS v, COUNT(DISTINCT {qkey_cast}) AS kc "
            f"  FROM {qtable} "
            f"  WHERE {qtarget} IS NOT NULL AND {no_pseudo} "
            f"  GROUP BY {qtarget} "
            f"  HAVING COUNT(DISTINCT {qkey_cast}) > 1 "
            f"  ORDER BY kc DESC, v "
            f"  LIMIT {_MAX_TARGETS}"
            f") tt"
        )

    # Outer: flat rows for those top targets. SELECT DISTINCT so we don't
    # over-fetch when one (target, key) pair appears many times.
    if db == "mssql":
        outer = (
            f"SELECT TOP {_INNER_ROW_LIMIT} DISTINCT {qtarget} AS v, {qkey_cast} AS k "
            f"FROM {qtable} "
            f"WHERE {qtarget} IS NOT NULL AND {no_pseudo} "
            f"AND {qtarget} IN ({top_targets}) "
            f"ORDER BY v, k"
        )
    elif db == "oracle":
        outer = (
            f"SELECT DISTINCT {qtarget} AS v, {qkey_cast} AS k "
            f"FROM {qtable} "
            f"WHERE {qtarget} IS NOT NULL AND {no_pseudo} "
            f"AND {qtarget} IN ({top_targets}) "
            f"ORDER BY v, k "
            f"FETCH FIRST {_INNER_ROW_LIMIT} ROWS ONLY"
        )
    else:
        outer = (
            f"SELECT DISTINCT {qtarget} AS v, {qkey_cast} AS k "
            f"FROM {qtable} "
            f"WHERE {qtarget} IS NOT NULL AND {no_pseudo} "
            f"AND {qtarget} IN ({top_targets}) "
            f"ORDER BY v, k "
            f"LIMIT {_INNER_ROW_LIMIT}"
        )
    return outer


def _pseudo_null_predicate(db_type: str, qcol: str) -> str:
    """Mirror of validator_service._pseudo_null_exclusion (kept inline to
    avoid importing a private helper through a third file)."""
    cast_target = "TEXT" if db_type == "postgresql" else (
        "NVARCHAR(MAX)" if db_type == "mssql" else "CHAR")
    tokens = ", ".join(f"'{t}'" for t in _PSEUDO_NULL_TOKENS)
    return f"LOWER(TRIM(CAST({qcol} AS {cast_target}))) NOT IN ({tokens})"


def _cast_to_text(db_type: str, expr: str) -> str:
    """Force a column expression to a text representation so the outer
    GROUP BY / CONCAT_WS sees a comparable value regardless of the
    column's declared type."""
    if db_type == "postgresql":
        return f"({expr})::TEXT"
    if db_type == "mssql":
        return f"CAST({expr} AS NVARCHAR(MAX))"
    if db_type == "oracle":
        return f"TO_CHAR({expr})"
    return f"CAST({expr} AS CHAR)"  # mysql / mariadb


def _concat_ws(db_type: str, sep: str, parts: list[str]) -> str:
    """CONCAT_WS-equivalent across dialects. Treats NULLs as empty (the
    Postgres/MySQL behaviour) so a partially-null composite key still
    groups together rather than splattering into spurious distinct buckets."""
    sep_lit = sep.replace("'", "''")
    if db_type == "oracle":
        joined = f" || '{sep_lit}' || ".join(f"NVL({p}, '')" for p in parts)
        return f"({joined})"
    # postgres / mysql / mariadb / mssql 2017+
    inner = ", ".join(parts)
    return f"CONCAT_WS('{sep_lit}', {inner})"


# ---------------------------------------------------------------------------
# Result shaping
# ---------------------------------------------------------------------------

def _group_examples(rows: list[Any]) -> list[dict]:
    """Group flat (target_value, entity_key_value) rows into a per-target
    list of distinct entity-key values, capped at _MAX_KEYS_PER_TARGET each."""
    bucket: dict[str, list[str]] = {}
    for row in rows:
        if not row:
            continue
        try:
            target, key = row[0], row[1]
        except (IndexError, TypeError):
            continue
        target = _stringify(target)
        key = _stringify(key)
        if target == "" or key == "":
            continue
        keys = bucket.setdefault(target, [])
        if key not in keys and len(keys) < _MAX_KEYS_PER_TARGET:
            keys.append(key)
    return [
        {"target_value": t, "entity_key_values": ks, "key_count": len(ks)}
        for t, ks in bucket.items()
    ]


def _stringify(v: Any) -> str:
    """Coerce a DB value to a short string for the JSON response. Same
    rules as column_sample_stats — drop bytes, format Decimals plain,
    cap length to keep the payload tight."""
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
    return str(v)[:200]


def _empty_response(issue: dict, *, reason: str) -> dict:
    """Standard 'nothing to show' shape so the UI can render gracefully
    even when the probe was skipped."""
    return {
        "issue_id": issue["id"],
        "target_column": issue.get("column_name"),
        "entity_key_columns": [],
        "examples": [],
        "row_limit_hit": False,
        "note": reason,
    }


def get_violator_examples_service() -> ViolatorExamplesService:
    return ViolatorExamplesService()

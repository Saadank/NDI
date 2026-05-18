"""Validator engine — Phase 1, Step 3c (BRD §4.6 / FR-VAL).

Reads dq.t_dq_active_rules for a (table) target, generates a SQL assertion per
rule based on the concept's rule_type + parameter, executes pushdown via the
existing DbConnectorGateway, and persists per-rule findings to dq.t_dq_issues.

Failure isolation: one rule blowing up (bad regex on the source dialect,
network blip, etc.) is recorded as `status='error'` on that issue row and
does NOT abort the rest of the scan.

Privacy: violation counts only. Where pattern context is useful (format_regex)
we sample a handful of violators in-app, derive their pattern signatures, and
persist *only* the signatures + counts. Raw values never reach DQ storage.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.repositories.active_rule_repository import (
    ActiveRuleRepository,
)
from app.products.data_quality.repositories.issue_repository import IssueRepository
from app.products.data_quality.services.profiler_service import (
    _PSEUDO_NULL_TOKENS, _qualified_table, _quote_ident, _extract_pattern,
)

logger = logging.getLogger(__name__)

_VIOLATION_PATTERN_SAMPLE = 200
_TOP_VIOLATION_PATTERNS_LIMIT = 5


# ---------------------------------------------------------------------------
# Dialect-specific regex operator. PG/Oracle use `~`, MySQL uses `REGEXP`,
# MSSQL has no native regex (we'll skip format_regex on MSSQL).
# ---------------------------------------------------------------------------

def _regex_predicate(db_type: str, qcol: str, pattern: str) -> str | None:
    # Single quotes inside the pattern need doubling for SQL string literals.
    safe = pattern.replace("'", "''")
    # Cast the column to text so regex works regardless of declared type
    # (e.g. integer 'id' columns approved against the uuid concept).
    if db_type == "postgresql":
        return f"({qcol})::text ~ '{safe}'"
    if db_type == "oracle":
        return f"REGEXP_LIKE(TO_CHAR({qcol}), '{safe}')"
    if db_type in ("mysql", "mariadb"):
        return f"CAST({qcol} AS CHAR) REGEXP '{safe}'"
    if db_type == "clickhouse":
        return f"match(toString({qcol}), '{safe}') = 1"
    # MSSQL has no built-in regex; format_regex is unsupported.
    return None


# ---------------------------------------------------------------------------
# Rule executors. Each returns a dict ready to feed IssueRepository.insert().
#
# Contract:
#   row_count: total rows in the table
#   violation_count: how many rows broke the rule
#   violation_rate:  count / row_count
#   status: 'pass' | 'fail' | 'error'
#   diagnostic_text: short human-readable explanation
# ---------------------------------------------------------------------------


async def _row_count(gateway: DbConnectorGateway, db_type: str,
                     schema_name: str, table_name: str) -> int | None:
    qtable = _qualified_table(db_type, schema_name, table_name)
    r = await gateway.execute_query(f"SELECT COUNT(*) FROM {qtable}")
    if not r.success or not r.data or not r.data["rows"]:
        return None
    try:
        return int(r.data["rows"][0][0])
    except (TypeError, ValueError):
        return None


async def _scalar_count(gateway: DbConnectorGateway, sql: str) -> tuple[int | None, str | None]:
    r = await gateway.execute_query(sql)
    if not r.success or not r.data or not r.data["rows"]:
        return None, r.error or "no rows returned"
    try:
        return int(r.data["rows"][0][0]), None
    except (TypeError, ValueError) as e:
        return None, str(e)


async def _eval_not_null(gateway, db_type, schema_name, table_name, column_name,
                         row_count, parameter):
    qcol = _quote_ident(db_type, column_name)
    qtable = _qualified_table(db_type, schema_name, table_name)
    sql = f"SELECT COUNT(*) FROM {qtable} WHERE {qcol} IS NULL"
    vc, err = await _scalar_count(gateway, sql)
    if vc is None:
        return _error_result(err, sql)
    rate = (vc / row_count) if row_count else None
    status = "fail" if vc > 0 else "pass"
    diag = (f"{vc} of {row_count} rows have NULL"
            if status == "fail" else "no NULL rows")
    return {"row_count": row_count, "violation_count": vc,
            "violation_rate": _round5(rate), "status": status,
            "diagnostic_text": diag, "violation_patterns": []}


async def _eval_max_null_rate(gateway, db_type, schema_name, table_name, column_name,
                              row_count, parameter):
    threshold = float((parameter or {}).get("threshold", 0.0))
    qcol = _quote_ident(db_type, column_name)
    qtable = _qualified_table(db_type, schema_name, table_name)
    sql = f"SELECT COUNT(*) FROM {qtable} WHERE {qcol} IS NULL"
    nulls, err = await _scalar_count(gateway, sql)
    if nulls is None:
        return _error_result(err, sql)
    rate = (nulls / row_count) if row_count else 0.0
    status = "fail" if rate > threshold else "pass"
    diag = (f"null_rate={rate:.4f} exceeds threshold {threshold:.4f}"
            if status == "fail"
            else f"null_rate={rate:.4f} within threshold {threshold:.4f}")
    return {"row_count": row_count, "violation_count": nulls,
            "violation_rate": _round5(rate), "status": status,
            "diagnostic_text": diag, "violation_patterns": []}


async def _eval_no_pseudo_nulls(gateway, db_type, schema_name, table_name, column_name,
                                row_count, parameter):
    qcol = _quote_ident(db_type, column_name)
    qtable = _qualified_table(db_type, schema_name, table_name)
    cast_target = "TEXT" if db_type == "postgresql" else (
        "NVARCHAR(MAX)" if db_type == "mssql" else "CHAR")
    tokens = ", ".join(f"'{t}'" for t in _PSEUDO_NULL_TOKENS)
    sql = (f"SELECT COUNT(*) FROM {qtable} "
           f"WHERE LOWER(TRIM(CAST({qcol} AS {cast_target}))) IN ({tokens})")
    vc, err = await _scalar_count(gateway, sql)
    if vc is None:
        return _error_result(err, sql)
    rate = (vc / row_count) if row_count else None
    status = "fail" if vc > 0 else "pass"
    diag = (f"{vc} rows match pseudo-null tokens (e.g. 'null', 'N/A', '-')"
            if status == "fail" else "no pseudo-null values")
    return {"row_count": row_count, "violation_count": vc,
            "violation_rate": _round5(rate), "status": status,
            "diagnostic_text": diag, "violation_patterns": []}


async def _eval_unique(gateway, db_type, schema_name, table_name, column_name,
                       row_count, parameter):
    qcol = _quote_ident(db_type, column_name)
    qtable = _qualified_table(db_type, schema_name, table_name)
    # Count rows whose value isn't unique. Excludes both NULL (NULL groups
    # vary by dialect; "uniqueness on a NULL column" is conventionally
    # "non-null values must be unique") AND pseudo-null tokens like
    # "N/A"/"null" — those repeating across rows are a completeness issue,
    # not a real key-collision. Reporting them here would double-count.
    no_pseudo = _pseudo_null_exclusion(db_type, qcol)
    sql = (
        f"SELECT COALESCE(SUM(c), 0) FROM ("
        f"  SELECT {qcol} AS v, COUNT(*) AS c FROM {qtable} "
        f"  WHERE {qcol} IS NOT NULL AND {no_pseudo} "
        f"  GROUP BY {qcol} "
        f"  HAVING COUNT(*) > 1"
        f") dups"
    )
    vc, err = await _scalar_count(gateway, sql)
    if vc is None:
        return _error_result(err, sql)
    rate = (vc / row_count) if row_count else None
    status = "fail" if vc > 0 else "pass"
    diag = (f"{vc} rows share a value with another row (column not unique)"
            if status == "fail" else "all non-null values are unique")
    return {"row_count": row_count, "violation_count": vc,
            "violation_rate": _round5(rate), "status": status,
            "diagnostic_text": diag, "violation_patterns": []}


def _pseudo_null_exclusion(db_type: str, qcol: str) -> str:
    """SQL predicate that's TRUE when {qcol} is NOT a pseudo-null token
    ('null', 'n/a', '-', etc. — see profiler._PSEUDO_NULL_TOKENS).

    Validity / uniqueness checks compose this with `IS NOT NULL` so a row
    whose value is the literal string ``"N/A"`` is reported only by the
    completeness `no_pseudo_nulls` rule, not double-counted as a validity
    failure. Mirrors the cast-and-tokenize logic used by the profiler."""
    cast_target = "TEXT" if db_type == "postgresql" else (
        "NVARCHAR(MAX)" if db_type == "mssql" else "CHAR")
    tokens = ", ".join(f"'{t}'" for t in _PSEUDO_NULL_TOKENS)
    return f"LOWER(TRIM(CAST({qcol} AS {cast_target}))) NOT IN ({tokens})"


async def _eval_format_regex(gateway, db_type, schema_name, table_name, column_name,
                             row_count, parameter):
    pattern = (parameter or {}).get("pattern")
    if not pattern:
        return _error_result("rule parameter missing 'pattern'", "")
    qcol = _quote_ident(db_type, column_name)
    qtable = _qualified_table(db_type, schema_name, table_name)
    pred = _regex_predicate(db_type, qcol, pattern)
    if pred is None:
        return _error_result(f"format_regex unsupported on {db_type}", "")

    # Count violators (NOT match), excluding both real NULL and pseudo-null
    # tokens. Both are completeness's job: NULL via not_null/max_null_rate,
    # "N/A"/"null"/"-" via no_pseudo_nulls. Reporting them here would
    # double-count the same root cause.
    no_pseudo = _pseudo_null_exclusion(db_type, qcol)
    sql = (f"SELECT COUNT(*) FROM {qtable} "
           f"WHERE {qcol} IS NOT NULL AND {no_pseudo} AND NOT ({pred})")
    vc, err = await _scalar_count(gateway, sql)
    if vc is None:
        return _error_result(err, sql)

    # Sample a few violators in-app to derive pattern signatures (counts only).
    patterns: list[dict] = []
    if vc > 0:
        sample_sql = (
            f"SELECT {qcol} FROM {qtable} "
            f"WHERE {qcol} IS NOT NULL AND {no_pseudo} AND NOT ({pred}) "
            f"LIMIT {_VIOLATION_PATTERN_SAMPLE}"
        )
        sr = await gateway.execute_query(sample_sql)
        if sr.success and sr.data:
            counts: dict[str, int] = {}
            for row in sr.data["rows"]:
                sig = _extract_pattern(row[0])
                if sig:
                    counts[sig] = counts.get(sig, 0) + 1
            ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:_TOP_VIOLATION_PATTERNS_LIMIT]
            patterns = [{"pattern": p[:120], "count": c} for p, c in ranked]

    rate = (vc / row_count) if row_count else None
    status = "fail" if vc > 0 else "pass"
    diag = (f"{vc} rows do not match pattern (sample shapes: "
            f"{', '.join(p['pattern'] for p in patterns[:3])})"
            if status == "fail" else "all rows match pattern")
    return {"row_count": row_count, "violation_count": vc,
            "violation_rate": _round5(rate), "status": status,
            "diagnostic_text": diag, "violation_patterns": patterns}


_EVALUATORS = {
    "not_null": _eval_not_null,
    "max_null_rate": _eval_max_null_rate,
    "no_pseudo_nulls": _eval_no_pseudo_nulls,
    "unique": _eval_unique,
    "format_regex": _eval_format_regex,
}


def _round5(v: float | None) -> float | None:
    return round(v, 5) if v is not None else None


def _error_result(msg: str | None, sql: str) -> dict:
    return {
        "row_count": None, "violation_count": None, "violation_rate": None,
        "status": "error",
        "diagnostic_text": (sql[:500] + " — " if sql else "") + (msg or "unknown error"),
        "violation_patterns": [],
    }


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ValidatorService:

    def __init__(self) -> None:
        self.active_repo = ActiveRuleRepository()
        self.issue_repo = IssueRepository()

    async def validate_scan(
        self, *, scan_id: int, tenant_id: int, profile_id: int,
        connection_id: UUID, db_type: str, schema_name: str, table_name: str,
        gateway: DbConnectorGateway,
        dimension_filter: str | None = None,
        active_rule_ids: list[int] | None = None,
    ) -> dict:
        """Evaluate every active rule for the (schema, table) target and
        persist findings to dq.t_dq_issues. Returns a summary count.

        Optional filters narrow the rule set without changing the per-rule
        contract — used by the validate-only scan path so users can re-run
        a single dimension or a hand-picked subset of rules in seconds."""
        rules = await self.active_repo.list_active_for_validator_by_profile(
            tenant_id=tenant_id, profile_id=profile_id,
        )
        if dimension_filter:
            rules = [r for r in rules if r["dimension"] == dimension_filter]
        if active_rule_ids:
            allow = set(active_rule_ids)
            rules = [r for r in rules if r["active_rule_id"] in allow]
        if not rules:
            return {"evaluated": 0, "fail": 0, "pass": 0, "error": 0}

        # Compute row count once and reuse — every evaluator needs it.
        row_count = await _row_count(gateway, db_type, schema_name, table_name)

        summary = {"evaluated": 0, "fail": 0, "pass": 0, "error": 0}
        for rule in rules:
            evaluator = _EVALUATORS.get(rule["rule_type"])
            if evaluator is None:
                logger.warning("Unknown rule_type %s on rule %s",
                               rule["rule_type"], rule["active_rule_id"])
                result = _error_result(f"unsupported rule_type {rule['rule_type']}", "")
            else:
                try:
                    parameter = _coerce_jsonb(rule["parameter"])
                    result = await evaluator(
                        gateway, db_type, schema_name, table_name,
                        rule["column_name"], row_count, parameter,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.exception("rule %s failed", rule["active_rule_id"])
                    result = _error_result(str(e), "")

            await self.issue_repo.insert(
                tenant_id=tenant_id, scan_id=scan_id, profile_id=profile_id,
                connection_id=connection_id,
                schema_name=schema_name, table_name=table_name,
                column_name=rule["column_name"],
                active_rule_id=rule["active_rule_id"],
                concept_id=rule["concept_id"],
                dimension=rule["dimension"], rule_type=rule["rule_type"],
                severity=rule["severity"],
                row_count=result["row_count"],
                violation_count=result["violation_count"],
                violation_rate=result["violation_rate"],
                status=result["status"],
                error_message=(result["diagnostic_text"] if result["status"] == "error" else None),
                rule_parameter=_coerce_jsonb(rule["parameter"]),
                violation_patterns=result["violation_patterns"],
                diagnostic_text=result["diagnostic_text"],
            )
            summary["evaluated"] += 1
            summary[result["status"]] = summary.get(result["status"], 0) + 1

        return summary


def _coerce_jsonb(raw: Any) -> Any:
    """asyncpg returns jsonb columns as already-decoded JSON (dict/list)
    when a codec is registered, but as a string when not. Normalize."""
    if isinstance(raw, (dict, list)):
        return raw
    if isinstance(raw, str):
        import json as _json
        try:
            return _json.loads(raw)
        except _json.JSONDecodeError:
            return {}
    return {} if raw is None else raw


def get_validator_service() -> ValidatorService:
    return ValidatorService()

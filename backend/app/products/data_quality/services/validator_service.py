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
from app.products.data_quality.repositories.profile_repository import (
    ProfileRepository,
)
from app.products.data_quality.repositories.reference_repository import (
    ReferenceRepository,
)
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
    # Exclude NULL (NULL groups vary by dialect; "uniqueness on a NULL
    # column" is conventionally "non-null values must be unique") AND
    # pseudo-null tokens like "N/A"/"null" — those repeating across rows
    # are a completeness issue, not a real key-collision, and reporting
    # them here would double-count.
    no_pseudo = _pseudo_null_exclusion(db_type, qcol)

    # `__entity_key_columns` is injected by validate_scan when the profile
    # has a configured entity key. Its presence flips the rule from
    # "column must be globally unique" to "column must be unique across
    # distinct business entities" — i.e. the same mobile across many
    # claims of the same client is fine, but two clients sharing a mobile
    # is a violation. Empty / missing → legacy behaviour.
    entity_keys = (parameter or {}).get("__entity_key_columns") or []
    # A column can't legitimately be checked against itself as the entity
    # key; that collapses to the legacy check, so drop self-references.
    entity_keys = [c for c in entity_keys if c and c != column_name]

    if entity_keys:
        qkeys = [_quote_ident(db_type, c) for c in entity_keys]
        distinct_expr = _count_distinct_tuple(db_type, qkeys)
        sql = (
            f"SELECT COALESCE(SUM(c), 0) FROM ("
            f"  SELECT {qcol} AS v, {distinct_expr} AS c FROM {qtable} "
            f"  WHERE {qcol} IS NOT NULL AND {no_pseudo} "
            f"  GROUP BY {qcol} "
            f"  HAVING {distinct_expr} > 1"
            f") dups"
        )
        vc, err = await _scalar_count(gateway, sql)
        if vc is None:
            return _error_result(err, sql)
        rate = (vc / row_count) if row_count else None
        status = "fail" if vc > 0 else "pass"
        key_label = ", ".join(entity_keys)
        diag = (
            f"{vc} value(s) of '{column_name}' appear under more than one "
            f"distinct ({key_label}); per-entity uniqueness violated."
            if status == "fail"
            else f"every non-null '{column_name}' belongs to at most one "
                 f"distinct ({key_label})."
        )
        return {"row_count": row_count, "violation_count": vc,
                "violation_rate": _round5(rate), "status": status,
                "diagnostic_text": diag, "violation_patterns": []}

    # Legacy fallback — no entity key configured for the table. The
    # column itself must be globally unique (e.g. customers.email on a
    # master-data table).
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


def _count_distinct_tuple(db_type: str, qcols: list[str]) -> str:
    """Build a COUNT(DISTINCT …) expression that works across dialects.

    PostgreSQL, Oracle, ClickHouse: `COUNT(DISTINCT col1, col2)` is legal.
    MySQL / MariaDB: same syntax accepted.
    MSSQL: only single-argument COUNT(DISTINCT) — collapse the tuple via
    a delimiter-safe CONCAT so distinctness over the composite still
    works. NULL would poison the concat, but entity-key columns rarely
    carry NULL; when they do, COALESCE keeps them grouping together
    rather than splattering into spurious distinct buckets."""
    if not qcols:
        # Shouldn't happen — _eval_unique already guards on empty —
        # but degrade safely to COUNT(*).
        return "COUNT(*)"
    if len(qcols) == 1:
        return f"COUNT(DISTINCT {qcols[0]})"
    if db_type == "mssql":
        # CONCAT_WS handles NULLs cleanly on MSSQL 2017+. The delimiter
        # is unlikely to appear inside any business identifier.
        parts = ", ".join(f"COALESCE(CAST({c} AS NVARCHAR(MAX)), '')" for c in qcols)
        return f"COUNT(DISTINCT CONCAT_WS('\\x1f', {parts}))"
    return f"COUNT(DISTINCT {', '.join(qcols)})"


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
    # tokens. Both are completeness's job: NULL via not_null, "N/A"/"null"/"-"
    # via no_pseudo_nulls. Reporting them here would double-count the same
    # root cause.
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


async def _eval_dictionary_match(gateway, db_type, schema_name, table_name, column_name,
                                 row_count, parameter):
    """Values in the column must appear in a named reference list (e.g.
    "Saudi Banks", "GCC Countries"). The concept's parameter points at the
    reference by id: ``{"reference_id": 42}``; the validator fetches the
    actual values from t_dq_reference_values at scan time.

    Like ``format_regex``, this excludes NULL and pseudo-null tokens — those
    are reported by completeness rules, not as validity violations.

    The reference (and its values + case_sensitive flag) come from a
    per-scan cache that ``validate_scan`` populates in ``parameter`` under
    the ``__reference`` key — avoids re-querying the same reference once
    per rule when many columns point at the same list."""
    cached = (parameter or {}).get("__reference")
    if not cached or not isinstance(cached, dict):
        return _error_result(
            "dictionary_match rule has no resolvable reference "
            "(reference_id missing or reference deleted)", "",
        )
    raw_values = cached.get("values") or []
    case_sensitive = bool(cached.get("case_sensitive", False))
    ref_name = cached.get("name") or f"reference#{cached.get('id')}"
    if not raw_values:
        return _error_result(
            f"reference '{ref_name}' is empty — add values or disable the concept",
            "",
        )

    # Normalize values up-front. Drop blanks; for case-insensitive, lower +
    # trim so the SQL comparison can do the same on the column side.
    values: list[str] = []
    for v in raw_values:
        if v is None:
            continue
        s = str(v)
        s = s if case_sensitive else s.strip().lower()
        if s == "":
            continue
        if len(s) > 200:
            return _error_result(
                f"reference value exceeds 200 chars (got {len(s)})", "",
            )
        values.append(s)
    if not values:
        return _error_result(
            f"reference '{ref_name}' has no usable values after normalization",
            "",
        )
    values = list(dict.fromkeys(values))

    qcol = _quote_ident(db_type, column_name)
    qtable = _qualified_table(db_type, schema_name, table_name)
    no_pseudo = _pseudo_null_exclusion(db_type, qcol)

    # Cast column to text for comparison so integer-typed columns
    # (e.g. a currency_code stored as smallint) still work. The exact
    # cast spelling differs by dialect.
    cast_target = "TEXT" if db_type == "postgresql" else (
        "NVARCHAR(MAX)" if db_type == "mssql" else "CHAR")
    col_expr = f"CAST({qcol} AS {cast_target})"
    if not case_sensitive:
        col_expr = f"LOWER(TRIM({col_expr}))"

    # Single-quote each value, escaping embedded apostrophes for SQL literal
    # safety. Values themselves are not user-typed at scan-time — they were
    # vetted by sql_safety.check_parameter at save time — but we still
    # double-quote defensively.
    in_list = ", ".join("'" + v.replace("'", "''") + "'" for v in values)

    sql = (
        f"SELECT COUNT(*) FROM {qtable} "
        f"WHERE {qcol} IS NOT NULL AND {no_pseudo} "
        f"AND {col_expr} NOT IN ({in_list})"
    )
    vc, err = await _scalar_count(gateway, sql)
    if vc is None:
        return _error_result(err, sql)

    # Sample violators and bucket them by raw value (truncated). Counts
    # only — like format_regex pattern signatures, never the raw rows.
    patterns: list[dict] = []
    if vc > 0:
        sample_sql = (
            f"SELECT {qcol} FROM {qtable} "
            f"WHERE {qcol} IS NOT NULL AND {no_pseudo} "
            f"AND {col_expr} NOT IN ({in_list}) "
            f"LIMIT {_VIOLATION_PATTERN_SAMPLE}"
        )
        sr = await gateway.execute_query(sample_sql)
        if sr.success and sr.data:
            counts: dict[str, int] = {}
            for row in sr.data["rows"]:
                v = row[0]
                if v is None:
                    continue
                key = str(v)[:80]
                counts[key] = counts.get(key, 0) + 1
            ranked = sorted(counts.items(), key=lambda kv: -kv[1])[:_TOP_VIOLATION_PATTERNS_LIMIT]
            patterns = [{"pattern": p, "count": c} for p, c in ranked]

    rate = (vc / row_count) if row_count else None
    status = "fail" if vc > 0 else "pass"
    if status == "fail":
        sample_str = ", ".join(p["pattern"] for p in patterns[:3])
        diag = (f"{vc} rows have a value not in reference '{ref_name}' "
                f"({len(values)} entries; sample: {sample_str})")
    else:
        diag = (f"every non-null row matches reference '{ref_name}' "
                f"({len(values)} entries)")
    return {"row_count": row_count, "violation_count": vc,
            "violation_rate": _round5(rate), "status": status,
            "diagnostic_text": diag, "violation_patterns": patterns}


_EVALUATORS = {
    "not_null": _eval_not_null,
    "no_pseudo_nulls": _eval_no_pseudo_nulls,
    "unique": _eval_unique,
    "format_regex": _eval_format_regex,
    "dictionary_match": _eval_dictionary_match,
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
        self.profile_repo = ProfileRepository()
        self.reference_repo = ReferenceRepository()

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

        # Load the entity key once per scan — uniqueness rules need it to
        # switch between "globally unique" and "unique per business entity".
        # Other rule types ignore the field.
        profile_row = await self.profile_repo.find_by_id(profile_id, tenant_id)
        entity_key_columns: list[str] = list(
            (profile_row or {}).get("entity_key_columns") or []
        )

        # Resolve every dictionary_match rule's referenced list up-front.
        # Many columns can point at the same reference (one Saudi-banks list
        # powers rules on bank_name, issuing_bank, payee_bank, …), so we
        # cache by reference_id and reuse across rules in this scan.
        reference_cache: dict[int, dict] = {}
        for r in rules:
            if r["rule_type"] != "dictionary_match":
                continue
            param = _coerce_jsonb(r["parameter"])
            ref_id = (param or {}).get("reference_id") if isinstance(param, dict) else None
            if not isinstance(ref_id, int) or ref_id in reference_cache:
                continue
            ref_row = await self.reference_repo.find_by_id(ref_id, tenant_id)
            if not ref_row:
                # Mark as resolved-but-missing so the per-rule evaluator can
                # emit a clean error instead of crashing.
                reference_cache[ref_id] = {"id": ref_id, "name": None,
                                            "case_sensitive": False, "values": []}
                continue
            values = await self.reference_repo.list_values_for_validator(ref_id)
            reference_cache[ref_id] = {
                "id": ref_id, "name": ref_row["name"],
                "case_sensitive": ref_row["case_sensitive"], "values": values,
            }

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
                    # Thread the table-level entity key into the unique
                    # evaluator without changing every evaluator's signature.
                    # The `__` prefix marks this as runtime-injected, not a
                    # user-facing parameter — it never round-trips through
                    # the rule's persisted JSON.
                    if rule["rule_type"] == "unique" and entity_key_columns:
                        parameter = {
                            **(parameter if isinstance(parameter, dict) else {}),
                            "__entity_key_columns": entity_key_columns,
                        }
                    if rule["rule_type"] == "dictionary_match":
                        # Thread the resolved reference (values + case flag)
                        # into the evaluator without re-querying. Missing or
                        # non-int reference_id → cache lookup returns None
                        # and the evaluator emits a clean error.
                        ref_id = (parameter or {}).get("reference_id") \
                            if isinstance(parameter, dict) else None
                        cached = reference_cache.get(ref_id) if isinstance(ref_id, int) else None
                        parameter = {
                            **(parameter if isinstance(parameter, dict) else {}),
                            "__reference": cached,
                        }
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

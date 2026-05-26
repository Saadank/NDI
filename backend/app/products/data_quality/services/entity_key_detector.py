"""Detect a table's entity key for uniqueness checks.

The "entity key" is the column (or composite) that identifies the business
entity a row is about. The uniqueness validator uses it to distinguish
legitimate repetition (one client, many claims, same mobile — fine) from
real bugs (two different clients sharing a mobile — wrong).

Two detection paths:
  1. `detect_entity_key_columns` — reads the declared PRIMARY KEY from
     the source DB's metadata. Ground truth when available.
  2. `propose_candidate_columns` — heuristic fallback for tables WITHOUT
     a declared PK (e.g. master-data dumps onboarded without constraints):
     uses already-profiled column stats + name shape to nominate one
     column. Master-data oriented — transactional tables typically need
     a manual override regardless of any heuristic.
"""
from __future__ import annotations

import logging

from app.gateways.db_connector_gateway import DbConnectorGateway

logger = logging.getLogger(__name__)


async def detect_entity_key_columns(
    *, gateway: DbConnectorGateway, db_type: str,
    schema_name: str, table_name: str,
) -> list[str]:
    """Return the ordered list of column names that form the table's
    declared primary key, or [] if no PK is declared (or detection fails).

    Composite PKs are returned in their constraint-defined order. Order
    matters for diagnostics ("entity key = (claim_id, national_id)") even
    though the uniqueness SQL treats them as a set.

    Never raises — a probe that fails (permissions, dialect quirk) is
    logged and yields an empty list so the scan keeps moving."""
    db = (db_type or "").lower()
    try:
        if db == "postgresql":
            return await _pk_postgresql(gateway, schema_name, table_name)
        if db == "mssql":
            return await _pk_mssql(gateway, schema_name, table_name)
        if db in ("mysql", "mariadb"):
            return await _pk_mysql(gateway, schema_name, table_name)
        if db == "oracle":
            return await _pk_oracle(gateway, schema_name, table_name)
        # Fall back to portable information_schema for everything else
        # (e.g. ClickHouse) — most dialects expose the same view.
        return await _pk_information_schema(gateway, schema_name, table_name)
    except Exception:  # noqa: BLE001
        logger.exception(
            "Entity-key detection failed for %s.%s (db_type=%s); leaving empty.",
            schema_name, table_name, db_type,
        )
        return []


# ---------------------------------------------------------------------------
# Per-dialect PK probes. Each returns columns in constraint-defined order.
# ---------------------------------------------------------------------------

async def _pk_postgresql(
    gateway: DbConnectorGateway, schema_name: str, table_name: str,
) -> list[str]:
    # pg_constraint + pg_attribute is the canonical way; it preserves the
    # ordinal position of columns inside the constraint (conkey is an int[]
    # of pg_attribute.attnum values in declaration order).
    sql = (
        "SELECT a.attname "
        "FROM pg_constraint c "
        "JOIN pg_class t ON t.oid = c.conrelid "
        "JOIN pg_namespace n ON n.oid = t.relnamespace "
        "JOIN unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE "
        "JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = k.attnum "
        f"WHERE c.contype = 'p' AND n.nspname = '{_escape(schema_name)}' "
        f"AND t.relname = '{_escape(table_name)}' "
        "ORDER BY k.ord"
    )
    return await _run_and_collect(gateway, sql)


async def _pk_mssql(
    gateway: DbConnectorGateway, schema_name: str, table_name: str,
) -> list[str]:
    # sys.key_constraints links to sys.index_columns, which carries the
    # in-key ordinal in key_ordinal.
    sql = (
        "SELECT c.name AS column_name "
        "FROM sys.key_constraints kc "
        "JOIN sys.tables t ON t.object_id = kc.parent_object_id "
        "JOIN sys.schemas s ON s.schema_id = t.schema_id "
        "JOIN sys.index_columns ic ON ic.object_id = kc.parent_object_id "
        "AND ic.index_id = kc.unique_index_id "
        "JOIN sys.columns c ON c.object_id = ic.object_id "
        "AND c.column_id = ic.column_id "
        f"WHERE kc.type = 'PK' AND s.name = '{_escape(schema_name)}' "
        f"AND t.name = '{_escape(table_name)}' "
        "ORDER BY ic.key_ordinal"
    )
    return await _run_and_collect(gateway, sql)


async def _pk_mysql(
    gateway: DbConnectorGateway, schema_name: str, table_name: str,
) -> list[str]:
    # MySQL exposes the PK as an INDEX named PRIMARY; information_schema
    # gives SEQ_IN_INDEX as the column order within the key.
    sql = (
        "SELECT COLUMN_NAME FROM information_schema.STATISTICS "
        f"WHERE TABLE_SCHEMA = '{_escape(schema_name)}' "
        f"AND TABLE_NAME = '{_escape(table_name)}' "
        "AND INDEX_NAME = 'PRIMARY' "
        "ORDER BY SEQ_IN_INDEX"
    )
    return await _run_and_collect(gateway, sql)


async def _pk_oracle(
    gateway: DbConnectorGateway, schema_name: str, table_name: str,
) -> list[str]:
    sql = (
        "SELECT cols.column_name FROM all_constraints cons "
        "JOIN all_cons_columns cols ON cols.constraint_name = cons.constraint_name "
        "AND cols.owner = cons.owner "
        f"WHERE cons.constraint_type = 'P' AND cons.owner = '{_escape(schema_name).upper()}' "
        f"AND cons.table_name = '{_escape(table_name).upper()}' "
        "ORDER BY cols.position"
    )
    return await _run_and_collect(gateway, sql)


async def _pk_information_schema(
    gateway: DbConnectorGateway, schema_name: str, table_name: str,
) -> list[str]:
    # Standard fallback — works on most ANSI-compliant dialects.
    sql = (
        "SELECT kcu.column_name "
        "FROM information_schema.table_constraints tc "
        "JOIN information_schema.key_column_usage kcu "
        "  ON kcu.constraint_name = tc.constraint_name "
        " AND kcu.table_schema    = tc.table_schema "
        " AND kcu.table_name      = tc.table_name "
        f"WHERE tc.constraint_type = 'PRIMARY KEY' "
        f"AND tc.table_schema = '{_escape(schema_name)}' "
        f"AND tc.table_name   = '{_escape(table_name)}' "
        "ORDER BY kcu.ordinal_position"
    )
    return await _run_and_collect(gateway, sql)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _escape(value: str) -> str:
    """Single-quote escape for inline string literals. The schema/table
    names come from already-validated profile rows, not user input, but
    defensive-double anyway."""
    return (value or "").replace("'", "''")


# ---------------------------------------------------------------------------
# Heuristic candidate detection (Phase 2)
# ---------------------------------------------------------------------------

# Distinct rate at or above this counts as "near-unique". Tuned for
# master-data tables where one row = one entity. Transactional tables
# (many rows per entity) will rarely surface a candidate here — that's
# intentional; we'd rather propose nothing than the wrong column.
_DISTINCT_RATE_MIN = 0.9

# Identifier columns are essentially never null on a healthy table.
# A few stray nulls are tolerated (data-onboarding noise).
_NULL_RATE_MAX = 0.02

# Exact column names that strongly suggest a business entity identifier.
# Score 2 — wins over generic suffix matches.
#
# Deliberately conservative: only columns that are immutable, assigned
# once at entity creation, and never reused. Attribute-shaped columns
# (email, username, login, handle) are NOT here — they're mutable and
# describe an entity rather than identify it. Domain "natural keys" like
# sku / isbn / ssn are also excluded; a user can set them manually when
# they really are the entity key for a table.
_EXACT_STRONG = {
    "national_id", "national_no", "customer_id", "client_id",
    "customer_code", "account_number", "account_no", "external_id",
    "person_id", "subscriber_id", "uuid", "guid",
}

# Generic suffixes that hint "this column is some kind of identifier".
# Score 1 — fallback when nothing more specific matches.
_GENERIC_SUFFIXES = ("_id", "_no", "_code", "_key", "_number", "_uuid", "_guid")


def propose_candidate_columns(
    column_profiles: list[dict],
    *,
    declared_pk: list[str] | None = None,
) -> list[str]:
    """Return [best_candidate] or [] for the table's entity key, based on
    already-profiled column statistics + name shape.

    Single-column candidates only — composite candidates need additional
    probe queries to verify joint uniqueness and aren't worth the latency
    for the master-data common case.

    The declared PK list is used as an exclusion set: a column that's
    already the row PK shouldn't be re-proposed (the uniqueness rule on
    it would be a tautology). Pass [] (or omit) when no declared PK
    exists — the heuristic is meant for exactly that case."""
    declared = {c for c in (declared_pk or []) if c}

    scored: list[tuple[int, float, str]] = []
    for prof in column_profiles or []:
        name = prof.get("column_name") or ""
        if not name or name in declared:
            continue

        distinct_rate = prof.get("distinct_rate")
        if distinct_rate is None or distinct_rate < _DISTINCT_RATE_MIN:
            continue
        null_rate = prof.get("null_rate")
        if null_rate is not None and null_rate > _NULL_RATE_MAX:
            continue

        name_score = _name_score(name)
        if name_score == 0:
            continue

        scored.append((name_score, float(distinct_rate), name))

    if not scored:
        return []

    # Highest name_score wins; break ties by higher distinct_rate, then
    # by column name (stable across scans so the chosen candidate doesn't
    # flap when two columns are tied on every signal).
    scored.sort(key=lambda t: (-t[0], -t[1], t[2]))
    return [scored[0][2]]


def _name_score(name: str) -> int:
    """0, 1, or 2 — higher = more strongly identifier-shaped.

    Conservative on purpose: anything that doesn't match a known
    identifier pattern scores 0, so columns like "amount", "status",
    "email", or "username" never get nominated even if they happen
    to have a high distinct rate on a small table. Attribute-shaped
    columns (email, username, etc.) are excluded deliberately — they
    describe an entity rather than identify it, and a user always
    needs to confirm the choice for those cases."""
    n = (name or "").lower().strip()
    if not n:
        return 0
    if n in _EXACT_STRONG:
        return 2
    if any(n.endswith(suf) for suf in _GENERIC_SUFFIXES):
        return 1
    # Bare "id" / "uuid" / "guid" — common surrogate row keys. When a
    # table has no declared PK, these are the most likely de-facto PK,
    # but they're typically the row identifier rather than the business
    # entity. Still worth nominating since the user can override.
    if n in {"id", "uuid", "guid", "pk", "key"}:
        return 1
    return 0


async def _run_and_collect(
    gateway: DbConnectorGateway, sql: str,
) -> list[str]:
    result = await gateway.execute_query(sql)
    if not result.success or not result.data:
        if not result.success:
            logger.info("PK probe returned no PK (or query failed): %s", result.error)
        return []
    rows = (result.data or {}).get("rows", []) or []
    out: list[str] = []
    for row in rows:
        if not row:
            continue
        col = row[0]
        if isinstance(col, (bytes, bytearray)):
            col = col.decode("utf-8", errors="replace")
        col = str(col).strip() if col is not None else ""
        if col:
            out.append(col)
    return out

"""Statistical profiler — Phase 1, Step 2 of IDQP (BRD §4.5, FR-PROF).

Pushes SQL aggregates down to the source DB through the existing
DbConnectorGateway and persists one row per column in dq.t_dq_column_profiles.
Phase 1 is descriptive only — anomaly logic / baseline tracking arrives in
Phase 2 once we have ≥3 historical scans per table (BRD FR-BASE-01).

Design notes:
- Each metric group (universal counts, numeric extras, string extras,
  pseudo-null check, top values, sample) runs as its own SQL roundtrip.
  This is more queries than a single mega-aggregate, but it lets the profiler
  degrade gracefully: a metric that fails on one column doesn't kill the scan.
- Identifier quoting follows the source DB's dialect; identifiers come from
  information_schema (not from the user) so this is correctness, not safety.
- The scan runs as a fire-and-forget asyncio task. Step 8 will replace this
  with the scheduled-scan worker; the in-process path stays as the manual
  "Run scan now" affordance.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from datetime import datetime, date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_quality.permissions import can_use_dq, require
from app.products.data_quality.repositories.column_profile_repository import (
    ColumnProfileRepository,
)
from app.products.data_quality.repositories.profile_repository import ProfileRepository
from app.products.data_quality.repositories.scan_repository import ScanRepository
from app.products.data_sharing.repositories.connection_repository import (
    ConnectionRepository,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

# Sentinel values commonly used to encode "missing" without using SQL NULL.
# Matches BRD FR-PROF "pseudo-null detection".
_PSEUDO_NULL_TOKENS = (
    "", "null", "n/a", "na", "-", "?", "nan", "none", "unknown", "(null)", "tbd",
)

# Inference thresholds — mirrors BRD §4.5 column type heuristics.
_IDENTIFIER_DISTINCT_RATE = 0.95
_FREE_TEXT_AVG_LENGTH = 50
_CATEGORICAL_MAX_DISTINCT = 50

# How many sampled values to inspect when computing the pattern signature.
# Sampled values flow through the app process but are NEVER persisted —
# only the derived signatures (e.g. "Aaa-999", "EMAIL") leave the function.
_PATTERN_SAMPLE_SIZE = 500
_TOP_PATTERNS_LIMIT = 10
_PATTERN_TOKEN_CAP = 64  # tokenized values longer than this are truncated

# Per-connection concurrency cap. Limits how many scans against the *same*
# source DB can run in parallel — protects the source from being smashed when
# a user runs a schema-wide batch. Sized for a small/dev cluster; promote to
# settings.DQ_SCAN_CONCURRENCY when the env var is added.
_PER_CONNECTION_CONCURRENCY = 4
_connection_semaphores: dict[str, asyncio.Semaphore] = {}


def _semaphore_for(connection_id: UUID) -> asyncio.Semaphore:
    """Lazy-create one asyncio.Semaphore per connection. Safe under cooperative
    concurrency — `dict.setdefault` is atomic between awaits."""
    key = str(connection_id)
    sem = _connection_semaphores.get(key)
    if sem is None:
        sem = asyncio.Semaphore(_PER_CONNECTION_CONCURRENCY)
        _connection_semaphores[key] = sem
    return sem

# Known formats short-circuit the per-character tokenizer with a label,
# giving us cleaner, BRD-aligned signatures (FR-LIB Table 16 mentions email,
# phone, IBAN, national_id, URL detection).
_KNOWN_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"), "EMAIL"),
    (re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"), "UUID"),
    (re.compile(r"^https?://[\w.\-/:%?=&#]+$"), "URL"),
    (re.compile(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+\-]\d{2}:?\d{2})?)?$"), "ISO_DATE"),
    (re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$"), "IPV4"),
    (re.compile(r"^\+?[\d][\d\s().\-]{6,19}$"), "PHONE"),
    (re.compile(r"^[A-Z]{2}\d{2}[A-Z0-9]{1,30}$"), "IBAN"),
]


# ---------------------------------------------------------------------------
# Dialect helpers — identifier quoting + DB-specific aggregate names.
# ---------------------------------------------------------------------------

def _quote_ident(db_type: str, ident: str) -> str:
    """Quote an identifier for the given dialect. The double-up rule prevents
    a stray quote in the identifier (which would not normally happen for a
    valid table/column) from escaping the quote."""
    if db_type in ("postgresql", "oracle"):
        return '"' + ident.replace('"', '""') + '"'
    if db_type == "mssql":
        return "[" + ident.replace("]", "]]") + "]"
    # mysql / mariadb / clickhouse
    return "`" + ident.replace("`", "``") + "`"


def _qualified_table(db_type: str, schema: str | None, table: str) -> str:
    if schema:
        return f"{_quote_ident(db_type, schema)}.{_quote_ident(db_type, table)}"
    return _quote_ident(db_type, table)


def _scan_target(
    db_type: str, schema: str | None, table: str,
    sampling_mode: str, sample_size: int | None,
) -> str:
    """Build the FROM-clause expression the profiler should query against.

    When sampling is configured, returns a LIMIT-bounded subquery so every
    aggregate operates on the same logical population. The validator does
    NOT use this — violation counts must always reflect the full table —
    so this helper lives in the profiler module.
    """
    base = _qualified_table(db_type, schema, table)
    if sampling_mode == "all" or not sample_size or sample_size <= 0:
        return base
    n = int(sample_size)
    if sampling_mode == "first_n":
        # PG / MySQL / MariaDB / ClickHouse / SQLite all accept LIMIT.
        # MSSQL needs TOP n; Oracle needs FETCH FIRST n ROWS ONLY.
        if db_type == "mssql":
            return f"(SELECT TOP {n} * FROM {base}) _sample"
        if db_type == "oracle":
            return f"(SELECT * FROM {base} FETCH FIRST {n} ROWS ONLY) _sample"
        return f"(SELECT * FROM {base} LIMIT {n}) _sample"
    if sampling_mode == "random":
        if db_type == "mssql":
            return f"(SELECT TOP {n} * FROM {base} ORDER BY NEWID()) _sample"
        if db_type in ("mysql", "mariadb"):
            return f"(SELECT * FROM {base} ORDER BY RAND() LIMIT {n}) _sample"
        if db_type == "clickhouse":
            return f"(SELECT * FROM {base} ORDER BY rand() LIMIT {n}) _sample"
        if db_type == "oracle":
            # Oracle has no built-in random sampler that's both cheap and stable
            # across the per-column queries; fall back to first_n semantics.
            return f"(SELECT * FROM {base} FETCH FIRST {n} ROWS ONLY) _sample"
        # PG default
        return f"(SELECT * FROM {base} ORDER BY RANDOM() LIMIT {n}) _sample"
    return base


def _stddev_func(db_type: str) -> str:
    if db_type == "clickhouse":
        return "stddevPop"
    return "STDDEV"


def _percentile_expr(db_type: str, qcol: str, p: float) -> str | None:
    """Per-dialect SQL fragment that yields the p-th percentile of qcol
    (p in [0,1]). Returns None when the dialect lacks a clean built-in;
    caller should skip percentile collection in that case rather than
    fall back to client-side sort (which would re-introduce the
    raw-row-leak risk migration 013 was about).

    - PostgreSQL/Oracle/MSSQL → percentile_cont(p) WITHIN GROUP (ORDER BY col)
    - ClickHouse              → quantile(p)(col)
    - MySQL/MariaDB           → no native function; return None
    """
    if db_type in ("postgresql", "postgres", "oracle", "mssql"):
        return f"percentile_cont({p}) WITHIN GROUP (ORDER BY {qcol})"
    if db_type == "clickhouse":
        return f"quantile({p})({qcol})"
    return None


def _length_func(db_type: str) -> str:
    # All target dialects accept LENGTH; MSSQL prefers LEN but accepts LENGTH
    # only via wrappers. Use LEN for MSSQL.
    if db_type == "mssql":
        return "LEN"
    return "LENGTH"


# ---------------------------------------------------------------------------
# Type categorization
# ---------------------------------------------------------------------------

def _categorize(declared: str | None) -> str:
    """Classify a SQLAlchemy-stringified type into one of:
    numeric / string / datetime / boolean / other."""
    if not declared:
        return "other"
    t = declared.lower()
    if any(k in t for k in ("bool", "bit ")):
        return "boolean"
    if any(k in t for k in ("int", "numeric", "decimal", "float", "double", "real", "money")):
        return "numeric"
    if any(k in t for k in ("char", "text", "varchar", "string", "clob")):
        return "string"
    if any(k in t for k in ("date", "time", "timestamp")):
        return "datetime"
    return "other"


def _stringify_for_pattern(value: Any) -> str:
    """Coerce a sampled value to a string for pattern extraction. The result
    leaves this function only as the derived signature — never persisted."""
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (bytes, bytearray, memoryview)):
        return ""
    return str(value)


def _stringify_min_max(value: Any) -> str | None:
    """ISO-stringify a MIN/MAX result for persistence into min_text/max_text.
    Returns None for null inputs so the column distinguishes "no data" from
    "empty string". Capped at 200 chars to avoid pathologically long rows."""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray, memoryview)):
        return None
    return str(value)[:200]


def _tokenize_pattern(s: str) -> str:
    """Replace upper letters with 'A', lower with 'a', digits with '9'; keep
    punctuation/spaces as separators. Empty string for empty input."""
    if not s:
        return ""
    s = s[:_PATTERN_TOKEN_CAP]
    out: list[str] = []
    for ch in s:
        if ch.isalpha():
            out.append("A" if ch.isupper() else "a")
        elif ch.isdigit():
            out.append("9")
        else:
            out.append(ch)
    return "".join(out)


def _extract_pattern(value: Any) -> str:
    """Return a signature for a single sampled value. Never returns the value
    itself — only a class label (EMAIL/UUID/...) or a tokenized shape."""
    s = _stringify_for_pattern(value)
    if not s:
        return ""
    for rx, label in _KNOWN_PATTERNS:
        if rx.match(s):
            return label
    return _tokenize_pattern(s)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class ProfilerService:

    def __init__(self) -> None:
        self.scan_repo = ScanRepository()
        self.profile_repo = ColumnProfileRepository()
        self.profile_asset_repo = ProfileRepository()
        self.connection_repo = ConnectionRepository()

    # -- public API ---------------------------------------------------------

    async def start_profile_scan(
        self, profile_id: int, auth_user: AuthUser,
    ) -> dict:
        """Create a scan row in 'pending' for the given profile and dispatch
        the profiling work as a fire-and-forget asyncio task. Returns the
        scan record so the UI can poll status."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        profile = await self.profile_asset_repo.find_by_id(profile_id, auth_user.tenant_id)
        if not profile:
            raise ResourceNotFoundException("Profile not found")

        scan = await self.scan_repo.create(
            tenant_id=auth_user.tenant_id,
            profile_id=profile_id,
            connection_id=profile["connection_id"],
            schema_name=profile["schema_name"],
            table_name=profile["table_name"],
            triggered_by=auth_user.user_id,
            trigger_source="manual",
        )
        self._dispatch(scan["id"], auth_user.tenant_id, profile["connection_id"])
        return scan

    async def start_validate_only_scan(
        self, *, profile_id: int, auth_user: AuthUser,
        dimension: str | None = None,
        active_rule_ids: list[int] | None = None,
    ) -> dict:
        """Re-run the validator only — skip the slow per-column profiler step.
        Useful for fast iteration after editing a rule. Optional `dimension`
        and `active_rule_ids` narrow the rule set further. Scan row carries
        scan_type='validation' so reports can distinguish full vs rule-only."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        profile = await self.profile_asset_repo.find_by_id(profile_id, auth_user.tenant_id)
        if not profile:
            raise ResourceNotFoundException("Profile not found")

        scan = await self.scan_repo.create(
            tenant_id=auth_user.tenant_id,
            profile_id=profile_id,
            connection_id=profile["connection_id"],
            schema_name=profile["schema_name"],
            table_name=profile["table_name"],
            scan_type="validation",
            triggered_by=auth_user.user_id,
            trigger_source="manual",
        )
        self._dispatch_validate_only(
            scan["id"], auth_user.tenant_id, profile["connection_id"],
            dimension=dimension, active_rule_ids=active_rule_ids,
        )
        return scan

    def _dispatch_validate_only(
        self, scan_id: int, tenant_id: int, connection_id: UUID,
        *, dimension: str | None, active_rule_ids: list[int] | None,
    ) -> None:
        sem = _semaphore_for(connection_id)

        async def runner():
            async with sem:
                await self._run_validate_only(
                    scan_id, tenant_id,
                    dimension=dimension, active_rule_ids=active_rule_ids,
                )

        asyncio.create_task(runner())

    async def _run_validate_only(
        self, scan_id: int, tenant_id: int, *,
        dimension: str | None, active_rule_ids: list[int] | None,
    ) -> None:
        """Validation-only scan path — opens a connection, runs validator + scoring,
        no per-column profiler. Always finalizes the scan row."""
        started = time.monotonic()
        gateway: DbConnectorGateway | None = None
        try:
            await self.scan_repo.mark_running(scan_id)
            scan = await self.scan_repo.find_by_id(scan_id, tenant_id)
            if not scan:
                logger.error("Scan %s vanished mid-run", scan_id)
                return
            conn = await self.connection_repo.find_by_id(scan["connection_id"], tenant_id)
            if not conn:
                raise ResourceNotFoundException("Connection no longer exists")

            gateway = DbConnectorGateway(
                db_type=conn["db_type"], username=conn["username"],
                password=conn["password_encrypted"], host=conn["host"],
                port=str(conn["port"]), database=conn.get("database") or "",
            )

            from app.products.data_quality.services.validator_service import (
                get_validator_service,
            )
            validator = get_validator_service()
            vsum = await validator.validate_scan(
                scan_id=scan_id, tenant_id=tenant_id,
                profile_id=scan["profile_id"],
                connection_id=scan["connection_id"], db_type=conn["db_type"],
                schema_name=scan["schema_name"], table_name=scan["table_name"],
                gateway=gateway,
                dimension_filter=dimension,
                active_rule_ids=active_rule_ids,
            )
            logger.info("Validate-only scan %s: %s", scan_id, vsum)

            try:
                from app.products.data_quality.services.scoring_service import (
                    get_scoring_service,
                )
                await get_scoring_service().score_scan(
                    tenant_id=tenant_id, profile_id=scan["profile_id"],
                    scan_id=scan_id,
                )
            except Exception:  # noqa: BLE001
                logger.exception("scoring failed for validate-only scan %s", scan_id)

            duration_ms = int((time.monotonic() - started) * 1000)
            await self.scan_repo.mark_success(
                scan_id, row_count=None, column_count=None, duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.exception("Validate-only scan %s failed", scan_id)
            try:
                await self.scan_repo.mark_failed(scan_id, str(exc), duration_ms)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to record scan %s failure", scan_id)
        finally:
            if gateway is not None:
                try:
                    await gateway.close()
                except Exception:  # noqa: BLE001
                    pass

    async def start_batch_scan(
        self, profile_ids: list[int], auth_user: AuthUser,
    ) -> dict:
        """Run scans for many profiles at once. Queues each under the
        per-connection concurrency semaphore so the source isn't smashed."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")

        if not profile_ids:
            return {"scans": [], "queued": 0}

        # De-dup while preserving order — guards against accidental double-clicks.
        seen: set[int] = set()
        ordered: list[int] = []
        for pid in profile_ids:
            if pid and pid not in seen:
                ordered.append(pid)
                seen.add(pid)

        created: list[dict] = []
        for pid in ordered:
            profile = await self.profile_asset_repo.find_by_id(pid, auth_user.tenant_id)
            if not profile:
                # Skip unknown profile ids silently rather than aborting the
                # whole batch — the UI can flag missing items by counting.
                continue
            scan = await self.scan_repo.create(
                tenant_id=auth_user.tenant_id,
                profile_id=pid,
                connection_id=profile["connection_id"],
                schema_name=profile["schema_name"],
                table_name=profile["table_name"],
                triggered_by=auth_user.user_id,
                trigger_source="manual",
            )
            created.append(scan)
            self._dispatch(scan["id"], auth_user.tenant_id, profile["connection_id"])

        return {"scans": created, "queued": len(created)}

    def _dispatch(self, scan_id: int, tenant_id: int, connection_id: UUID) -> None:
        """Schedule a scan to run when the per-connection semaphore lets it."""
        sem = _semaphore_for(connection_id)

        async def runner():
            async with sem:
                await self._run_scan(scan_id, tenant_id)

        asyncio.create_task(runner())

    async def get_scan(self, scan_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        scan = await self.scan_repo.find_by_id(scan_id, auth_user.tenant_id)
        if not scan:
            raise ResourceNotFoundException("Scan not found")
        return scan

    async def delete_scan(self, scan_id: int, auth_user: AuthUser) -> dict:
        """Hard-delete a scan and all of its derived data. CASCADES via
        FK ON DELETE CASCADE to ``t_dq_column_profiles`` (per-column
        descriptive stats), ``t_dq_issues`` (validator output), and
        ``t_dq_score_history`` (per-dimension scoring rows).

        Refuses with a clear error when the scan is still running so a
        background-task race can't leave half-written child rows
        orphaned. Otherwise no preflight — the user explicitly asked
        for the scan's history to be gone."""
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        scan = await self.scan_repo.find_by_id(scan_id, auth_user.tenant_id)
        if not scan:
            raise ResourceNotFoundException("Scan not found")
        if scan["status"] in ("pending", "running"):
            raise ValidationException(
                f"Cannot delete a scan in status {scan['status']!r}. "
                f"Wait for it to finish or fail, then retry."
            )
        await self.scan_repo.delete_by_id(scan_id, auth_user.tenant_id)
        return {
            "detail": "Scan deleted (cascade: column_profiles + issues + score_history)",
            "scan_id": scan_id,
        }

    async def list_scans(
        self, auth_user: AuthUser, *, profile_id: int | None = None,
        connection_id: UUID | None = None,
        schema_name: str | None = None, table_name: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self.scan_repo.list_for_tenant(
            auth_user.tenant_id, profile_id=profile_id,
            connection_id=connection_id,
            schema_name=schema_name, table_name=table_name, limit=limit,
        )

    async def get_profiles(self, scan_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        scan = await self.scan_repo.find_by_id(scan_id, auth_user.tenant_id)
        if not scan:
            raise ResourceNotFoundException("Scan not found")
        profiles = await self.profile_repo.find_by_scan(scan_id, auth_user.tenant_id)
        return {"scan": scan, "profiles": profiles}

    # -- internals ----------------------------------------------------------

    async def _run_scan(self, scan_id: int, tenant_id: int) -> None:
        """Execute the profile scan. Always finalizes the scan row (success
        or failed) so a crash mid-flight never leaves a 'running' zombie."""
        started = time.monotonic()
        gateway: DbConnectorGateway | None = None
        try:
            await self.scan_repo.mark_running(scan_id)
            scan = await self.scan_repo.find_by_id(scan_id, tenant_id)
            if not scan:
                logger.error("Scan %s vanished mid-run", scan_id)
                return

            conn = await self.connection_repo.find_by_id(scan["connection_id"], tenant_id)
            if not conn:
                raise ResourceNotFoundException("Connection no longer exists")

            # Pull sampling config from the parent profile. If the profile is
            # missing (shouldn't happen post-3.5.d), default to no sampling.
            asset = await self.profile_asset_repo.find_by_id(scan["profile_id"], tenant_id)
            sampling_mode = (asset or {}).get("sampling_mode", "all")
            sample_size = (asset or {}).get("sample_size")

            gateway = DbConnectorGateway(
                db_type=conn["db_type"], username=conn["username"],
                password=conn["password_encrypted"], host=conn["host"],
                port=str(conn["port"]), database=conn.get("database") or "",
            )

            columns = await self._fetch_columns(
                gateway, conn["db_type"], scan["schema_name"], scan["table_name"],
            )
            if not columns:
                raise RuntimeError(
                    f"No columns found for {scan['schema_name']}.{scan['table_name']}"
                )

            # Per-profile column-subset filter (migration 026). NULL = scan
            # everything (current default for legacy profiles). Empty list =
            # explicit "scan nothing" — error rather than silently no-op.
            # Non-empty list = intersect with the live information_schema
            # list, so a column the user picked but that no longer exists in
            # the source is silently skipped.
            selected = (asset or {}).get("selected_columns")
            if selected is not None:
                if not selected:
                    raise RuntimeError(
                        "Profile has selected_columns=[] (zero columns picked). "
                        "Edit the Columns tab and pick at least one column."
                    )
                wanted = {c for c in selected}
                before = len(columns)
                columns = [c for c in columns if c["name"] in wanted]
                logger.info(
                    "Scan %s column subset: %d/%d columns kept (profile.selected_columns)",
                    scan_id, len(columns), before,
                )
                if not columns:
                    raise RuntimeError(
                        "Profile's selected_columns matches no live source columns. "
                        "The source schema may have changed — review the Columns tab."
                    )

            # Build the FROM-clause expression once. With sampling, every
            # aggregate operates on the same LIMIT-bounded subquery — within
            # a single column's queries the sample is consistent, and across
            # columns the *size* matches even if the exact rows don't.
            qtable = _scan_target(
                conn["db_type"], scan["schema_name"], scan["table_name"],
                sampling_mode, sample_size,
            )
            logger.info(
                "Scan %s target: %s (sampling=%s, size=%s)",
                scan_id, qtable, sampling_mode, sample_size,
            )

            row_count = await self._fetch_row_count(gateway, qtable)

            # Collected as we go so the entity-key heuristic (below) can
            # propose candidates from in-memory stats without a re-fetch.
            scanned_profiles: list[dict] = []
            for ordinal, col in enumerate(columns, start=1):
                profile = await self._profile_column(
                    gateway=gateway, db_type=conn["db_type"], qtable=qtable,
                    column_name=col["name"], declared=col["data_type"],
                    ordinal=ordinal, row_count=row_count,
                )
                # Step 4.5 — stash declared_length into raw_metrics so the
                # dense dashboard can flag over-allocated columns (avoiding
                # a schema migration; raw_metrics is JSONB).
                if col.get("declared_length") is not None:
                    profile.setdefault("raw_metrics", {})["declared_length"] = col["declared_length"]
                await self.profile_repo.insert(
                    scan_id=scan_id, tenant_id=tenant_id,
                    connection_id=scan["connection_id"],
                    schema_name=scan["schema_name"], table_name=scan["table_name"],
                    profile=profile,
                )
                scanned_profiles.append(profile)

            # Detect the table's entity key (declared PK) once per scan and
            # persist it onto the profile. The uniqueness validator reads
            # this to choose between "column must be globally unique" and
            # "column must be unique per business entity" semantics. A scan
            # without a profile row (transient mode) skips persistence; the
            # validator then falls back to the legacy behaviour.
            if scan.get("profile_id"):
                try:
                    # Honour the lock — if the user has explicitly set the
                    # entity key via the /entity-key endpoint, never let a
                    # scan overwrite it. Heuristic candidates (Phase 2)
                    # would otherwise drift the value between scans.
                    profile_row = await self.profile_asset_repo.find_by_id(
                        scan["profile_id"], tenant_id,
                    )
                    locked = bool((profile_row or {}).get("entity_key_locked"))
                    if locked:
                        logger.info(
                            "Scan %s: entity_key_columns locked by user on %s.%s; skipping auto-update.",
                            scan_id, scan["schema_name"], scan["table_name"],
                        )
                    else:
                        from app.products.data_quality.services.entity_key_detector import (
                            detect_entity_key_columns, propose_candidate_columns,
                        )
                        detected = await detect_entity_key_columns(
                            gateway=gateway, db_type=conn["db_type"],
                            schema_name=scan["schema_name"], table_name=scan["table_name"],
                        )
                        source = "declared PK"
                        # Phase 2 fallback: when no declared PK exists,
                        # nominate a single-column candidate from the
                        # column-profile stats we just collected. This
                        # populates entity_key_columns for tables whose
                        # source DB never had constraints declared (the
                        # common case for warehouse / staging dumps).
                        if not detected:
                            detected = propose_candidate_columns(
                                scanned_profiles, declared_pk=[],
                            )
                            if detected:
                                source = "heuristic candidate"
                        # Only overwrite when we found something. Leaving
                        # the existing value alone on an empty detection
                        # avoids clearing the previous-scan's result just
                        # because, say, the gateway briefly lost metadata
                        # access.
                        if detected:
                            await self.profile_asset_repo.update(
                                scan["profile_id"], tenant_id,
                                entity_key_columns=detected,
                            )
                            logger.info(
                                "Scan %s set entity key on %s.%s to %s (source: %s).",
                                scan_id, scan["schema_name"], scan["table_name"],
                                detected, source,
                            )
                        else:
                            logger.info(
                                "Scan %s: no declared PK and no candidate match on %s.%s; entity_key_columns left as-is.",
                                scan_id, scan["schema_name"], scan["table_name"],
                            )
                except Exception:  # noqa: BLE001
                    logger.exception("entity-key detection failed for scan %s", scan_id)

            # Profile is done — now run the validator over any active rules
            # for this table. Issues persist whether or not any fail; an
            # error inside a rule is recorded as a per-issue 'error' row and
            # doesn't block the scan from succeeding.
            try:
                from app.products.data_quality.services.validator_service import (
                    get_validator_service,
                )
                validator = get_validator_service()
                vsum = await validator.validate_scan(
                    scan_id=scan_id, tenant_id=tenant_id,
                    profile_id=scan["profile_id"],
                    connection_id=scan["connection_id"], db_type=conn["db_type"],
                    schema_name=scan["schema_name"], table_name=scan["table_name"],
                    gateway=gateway,
                )
                logger.info("Scan %s validation: %s", scan_id, vsum)

                # Step 4 — score the scan once issues are persisted. Failure
                # here is logged but does not fail the scan; metrics can be
                # re-computed later from the issues table.
                try:
                    from app.products.data_quality.services.scoring_service import (
                        get_scoring_service,
                    )
                    scoring = get_scoring_service()
                    persisted = await scoring.score_scan(
                        tenant_id=tenant_id, profile_id=scan["profile_id"],
                        scan_id=scan_id,
                    )
                    logger.info("Scan %s scored: %s rows", scan_id, len(persisted))
                except Exception:  # noqa: BLE001
                    logger.exception("scoring failed for scan %s", scan_id)
            except Exception:  # noqa: BLE001
                logger.exception("validator orchestration failed for scan %s", scan_id)

            duration_ms = int((time.monotonic() - started) * 1000)
            await self.scan_repo.mark_success(
                scan_id, row_count=row_count, column_count=len(columns),
                duration_ms=duration_ms,
            )
            logger.info("Scan %s succeeded (%s cols, %sms)", scan_id, len(columns), duration_ms)

        except Exception as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            logger.exception("Scan %s failed", scan_id)
            try:
                await self.scan_repo.mark_failed(scan_id, str(exc), duration_ms)
            except Exception:  # noqa: BLE001
                logger.exception("Failed to record scan %s failure", scan_id)
        finally:
            if gateway is not None:
                try:
                    await gateway.close()
                except Exception:  # noqa: BLE001
                    pass

    async def _fetch_columns(
        self, gateway: DbConnectorGateway, db_type: str, schema: str, table: str,
    ) -> list[dict]:
        """Pull ordered column metadata from the source DB.

        Uses information_schema where possible. We do this directly rather than
        going through DbConnectorGateway.list_schemas() because we want only
        the target table's columns, not the entire schema.

        Step 4.5 — also capture `character_maximum_length` (and Oracle's
        DATA_LENGTH) so the dense dashboard can flag over-allocated columns
        (declared length much greater than observed max length)."""
        if db_type in ("postgresql", "mysql", "mariadb", "mssql"):
            sql = (
                "SELECT column_name, data_type, character_maximum_length "
                "FROM information_schema.columns "
                f"WHERE table_schema = '{schema}' AND table_name = '{table}' "
                "ORDER BY ordinal_position"
            )
        elif db_type == "oracle":
            sql = (
                "SELECT column_name, data_type, data_length "
                "FROM all_tab_columns "
                f"WHERE owner = '{schema.upper()}' AND table_name = '{table.upper()}' "
                "ORDER BY column_id"
            )
        elif db_type == "clickhouse":
            sql = (
                f"SELECT name AS column_name, type AS data_type, NULL AS data_length "
                f"FROM system.columns "
                f"WHERE database = '{schema}' AND table = '{table}' "
                "ORDER BY position"
            )
        else:
            raise RuntimeError(f"Unsupported db_type for profiling: {db_type}")

        result = await gateway.execute_query(sql)
        if not result.success or not result.data:
            return []
        out: list[dict] = []
        for row in result.data["rows"]:
            declared_length: int | None = None
            try:
                if len(row) >= 3 and row[2] is not None:
                    declared_length = int(row[2])
            except (TypeError, ValueError):
                declared_length = None
            out.append({"name": row[0], "data_type": row[1],
                        "declared_length": declared_length})
        return out

    async def _fetch_row_count(
        self, gateway: DbConnectorGateway, qtable: str,
    ) -> int | None:
        """COUNT(*) over the (possibly sampled) target. When the target is a
        LIMIT-bounded subquery, the result is min(actual_rows, sample_size)."""
        sql = f"SELECT COUNT(*) FROM {qtable}"
        result = await gateway.execute_query(sql)
        if not result.success or not result.data or not result.data["rows"]:
            return None
        try:
            return int(result.data["rows"][0][0])
        except (TypeError, ValueError):
            return None

    async def _profile_column(
        self, *, gateway: DbConnectorGateway, db_type: str, qtable: str,
        column_name: str, declared: str | None,
        ordinal: int, row_count: int | None,
    ) -> dict:
        """Build one column-profile dict. Each metric group is best-effort —
        a failure logs a warning but doesn't abort the column.

        qtable is the pre-built FROM-clause expression: either the bare
        `"schema"."table"` reference or a LIMIT-bounded subquery when the
        profile asks for sampling."""
        category = _categorize(declared)
        qcol = _quote_ident(db_type, column_name)

        profile: dict[str, Any] = {
            "column_name": column_name,
            "ordinal_position": ordinal,
            "declared_data_type": declared,
            "type_category": category,
            "row_count": row_count,
            "raw_metrics": {},
        }

        await self._compute_universal(gateway, profile, qcol, qtable, db_type)
        if category == "numeric":
            await self._compute_numeric_extras(gateway, profile, qcol, qtable, db_type)
        elif category == "string":
            await self._compute_string_extras(gateway, profile, qcol, qtable, db_type)
            await self._compute_pseudo_null(gateway, profile, qcol, qtable, db_type)
            # Pattern signature: pulls a sample of raw values into app memory,
            # tokenizes each, persists ONLY the resulting signatures + counts.
            # Raw values are discarded when this function returns.
            await self._compute_pattern_signature(gateway, profile, qcol, qtable)
        elif category == "datetime":
            await self._compute_text_min_max(gateway, profile, qcol, qtable)

        profile["inferred_column_type"] = _infer_column_type(profile)
        return profile

    async def _compute_universal(
        self, gateway: DbConnectorGateway, profile: dict, qcol: str, qtable: str, db_type: str,
    ) -> None:
        # Counts only — no MIN/MAX. Raw bound values would leak a single row.
        sql = (
            f"SELECT COUNT(*) AS rc, COUNT({qcol}) AS nn, "
            f"COUNT(DISTINCT {qcol}) AS dc "
            f"FROM {qtable}"
        )
        result = await gateway.execute_query(sql)
        if not result.success or not result.data or not result.data["rows"]:
            logger.warning("universal stats failed for %s: %s", qcol, result.error)
            return
        row = result.data["rows"][0]
        rc, nn, dc = (row + [None] * 3)[:3]
        rc = int(rc) if rc is not None else None
        nn = int(nn) if nn is not None else None
        dc = int(dc) if dc is not None else None
        profile["row_count"] = profile.get("row_count") or rc
        profile["non_null_count"] = nn
        profile["null_count"] = (rc - nn) if (rc is not None and nn is not None) else None
        profile["null_rate"] = round(((rc - nn) / rc), 5) if rc else None
        profile["distinct_count"] = dc
        profile["distinct_rate"] = round((dc / rc), 5) if rc and dc is not None else None

    async def _compute_numeric_extras(
        self, gateway: DbConnectorGateway, profile: dict, qcol: str, qtable: str, db_type: str,
    ) -> None:
        """Numeric distribution stats. Two SQL roundtrips:

        1. Mean / stddev / min / max — one aggregate query, all dialects.
        2. Median + p25/p75/p95 — only if the dialect supports a percentile
           function. Skipped silently otherwise; UI shows "—" for those tiles.

        min_value / max_value are persisted (see migration 023 header for the
        privacy trade-off this represents)."""
        # ---- mean, stddev, min, max ------------------------------------
        sql = (
            f"SELECT AVG({qcol}) AS av, {_stddev_func(db_type)}({qcol}) AS sd, "
            f"MIN({qcol}) AS mn, MAX({qcol}) AS mx "
            f"FROM {qtable}"
        )
        result = await gateway.execute_query(sql)
        if not result.success or not result.data or not result.data["rows"]:
            logger.debug("numeric extras failed for %s: %s", qcol, result.error)
            return
        av, sd, mn, mx = (result.data["rows"][0] + [None, None, None, None])[:4]
        for key, val in (("mean_value", av), ("stddev_value", sd),
                         ("min_value", mn), ("max_value", mx)):
            try:
                profile[key] = float(val) if val is not None else None
            except (TypeError, ValueError):
                profile[key] = None

        # ---- percentiles (median, p25, p75, p95) -----------------------
        # Built per-dialect; MySQL/MariaDB get None across the board.
        parts = []
        keys: list[str] = []
        for label, p in (("median_value", 0.5), ("p25_value", 0.25),
                         ("p75_value", 0.75), ("p95_value", 0.95)):
            expr = _percentile_expr(db_type, qcol, p)
            if expr is None:
                continue
            parts.append(f"{expr} AS {label}")
            keys.append(label)
        if not parts:
            return
        sql_p = f"SELECT {', '.join(parts)} FROM {qtable}"
        result_p = await gateway.execute_query(sql_p)
        if not result_p.success or not result_p.data or not result_p.data["rows"]:
            logger.debug("percentiles failed for %s: %s", qcol, result_p.error)
            return
        row = (result_p.data["rows"][0] + [None] * len(keys))[:len(keys)]
        for key, val in zip(keys, row):
            try:
                profile[key] = float(val) if val is not None else None
            except (TypeError, ValueError):
                profile[key] = None

    async def _compute_string_extras(
        self, gateway: DbConnectorGateway, profile: dict, qcol: str, qtable: str, db_type: str,
    ) -> None:
        lf = _length_func(db_type)
        sql = (
            f"SELECT MIN({lf}({qcol})) AS lmin, MAX({lf}({qcol})) AS lmax, "
            f"AVG({lf}({qcol})) AS lavg "
            f"FROM {qtable}"
        )
        result = await gateway.execute_query(sql)
        if not result.success or not result.data or not result.data["rows"]:
            logger.debug("string extras failed for %s: %s", qcol, result.error)
            return
        lmin, lmax, lavg = (result.data["rows"][0] + [None, None, None])[:3]
        try:
            profile["min_length"] = int(lmin) if lmin is not None else None
        except (TypeError, ValueError):
            profile["min_length"] = None
        try:
            profile["max_length"] = int(lmax) if lmax is not None else None
        except (TypeError, ValueError):
            profile["max_length"] = None
        try:
            profile["avg_length"] = float(lavg) if lavg is not None else None
        except (TypeError, ValueError):
            profile["avg_length"] = None

        # Alphabetical min/max — same single-row leak class as numeric min/max
        # (see migration 025 header). Stored in min_text / max_text.
        await self._compute_text_min_max(gateway, profile, qcol, qtable)

    async def _compute_text_min_max(
        self, gateway: DbConnectorGateway, profile: dict, qcol: str, qtable: str,
    ) -> None:
        """MIN/MAX for non-numeric columns. For dates the DB returns a
        datetime/date object; ISO-stringify so a single TEXT column fits all
        types. Persisted into min_text / max_text (migration 025)."""
        sql = f"SELECT MIN({qcol}) AS mn, MAX({qcol}) AS mx FROM {qtable}"
        result = await gateway.execute_query(sql)
        if not result.success or not result.data or not result.data["rows"]:
            logger.debug("text min/max failed for %s: %s", qcol, result.error)
            return
        mn, mx = (result.data["rows"][0] + [None, None])[:2]
        profile["min_text"] = _stringify_min_max(mn)
        profile["max_text"] = _stringify_min_max(mx)

    async def _compute_pseudo_null(
        self, gateway: DbConnectorGateway, profile: dict, qcol: str, qtable: str, db_type: str,
    ) -> None:
        # CAST → string then LOWER+TRIM → match against the sentinel set.
        cast_target = "TEXT" if db_type == "postgresql" else "CHAR"
        if db_type == "mssql":
            cast_target = "NVARCHAR(MAX)"
        token_list = ", ".join(f"'{t}'" for t in _PSEUDO_NULL_TOKENS)
        sql = (
            f"SELECT COUNT(*) FROM {qtable} "
            f"WHERE LOWER(TRIM(CAST({qcol} AS {cast_target}))) IN ({token_list})"
        )
        result = await gateway.execute_query(sql)
        if not result.success or not result.data or not result.data["rows"]:
            logger.debug("pseudo-null check failed for %s: %s", qcol, result.error)
            return
        try:
            cnt = int(result.data["rows"][0][0])
        except (TypeError, ValueError):
            return
        profile["pseudo_null_count"] = cnt
        rc = profile.get("row_count")
        profile["pseudo_null_rate"] = round((cnt / rc), 5) if rc else None

    async def _compute_pattern_signature(
        self, gateway: DbConnectorGateway, profile: dict, qcol: str, qtable: str,
    ) -> None:
        """Tokenize a sample of non-null values into shape signatures and
        persist only the distribution. Raw values exist in app memory for the
        duration of this method and are discarded on return.

        Two signatures are produced:
          - dominant_pattern + pattern_conformance_rate (single dominant shape)
          - top_patterns: [{pattern, count}, ...] — top-K with counts only
        """
        sql = (
            f"SELECT {qcol} FROM {qtable} "
            f"WHERE {qcol} IS NOT NULL "
            f"LIMIT {_PATTERN_SAMPLE_SIZE}"
        )
        result = await gateway.execute_query(sql)
        if not result.success or not result.data:
            return

        counts: dict[str, int] = {}
        for row in result.data["rows"]:
            sig = _extract_pattern(row[0])
            if not sig:
                continue
            counts[sig] = counts.get(sig, 0) + 1

        total = sum(counts.values())
        if not total:
            return

        ranked = sorted(counts.items(), key=lambda kv: -kv[1])
        top = ranked[:_TOP_PATTERNS_LIMIT]
        # Cap the persisted dominant pattern to 120 chars to match the column.
        dominant_pattern = top[0][0][:120]
        profile["dominant_pattern"] = dominant_pattern
        profile["pattern_conformance_rate"] = round(top[0][1] / total, 5)
        profile["top_patterns"] = [
            {"pattern": p[:120], "count": c} for p, c in top
        ]


def _infer_column_type(profile: dict) -> str:
    """Phase 1 heuristic — refined in Phase 2 with sample-based regex matching."""
    category = profile.get("type_category")
    rc = profile.get("row_count") or 0
    dc = profile.get("distinct_count")
    drate = profile.get("distinct_rate")
    avg_len = profile.get("avg_length")

    if rc == 0:
        return "general"
    if dc is not None and dc <= 1:
        return "constant"
    if dc is not None and dc == 2:
        return "boolean"
    if drate is not None and drate >= _IDENTIFIER_DISTINCT_RATE:
        return "identifier"
    if category == "datetime":
        return "datetime"
    if category == "boolean":
        return "boolean"
    if category == "numeric":
        if dc is not None and dc <= _CATEGORICAL_MAX_DISTINCT:
            return "numeric_discrete"
        return "numeric_continuous"
    if category == "string":
        if avg_len is not None and avg_len > _FREE_TEXT_AVG_LENGTH and (
            drate is None or drate > 0.5
        ):
            return "free_text"
        if dc is not None and dc <= _CATEGORICAL_MAX_DISTINCT:
            return "categorical"
    return "general"


def get_profiler_service() -> ProfilerService:
    return ProfilerService()

"""Business-rule ingest — BRD Table 12.

Schema:
    rule_name* | description | logic_nl* | severity* | dimension* | table | column

Lifecycle:
    uploaded -> parsing -> enriching -> awaiting_review
                                     -> error  (parse-only failure)

Three paths per row:

- **Easy path** — both ``table`` and ``column`` filled. Skip
  ``column_match``; only call ``sql_generation`` to convert the NL
  rule + chosen column into a (rule_type, parameter) pair.

- **Hard path** — ``column`` blank but ``table`` filled. Call
  ``column_match`` against the table's columns (from the latest
  successful scan), pick the top candidate, then call
  ``sql_generation`` against that candidate. The remaining ranked
  candidates go on the proposal's ``candidates`` field so the
  reviewer can swap at approval.

- **Unsupported** — both ``table`` and ``column`` blank, or the
  table has never been scanned so we have no column list. Lands as
  ``unsupported_logic`` proposal — visible to the reviewer with the
  error_reason explaining what's missing.

Each successful hard path consumes **two LLM calls** per row
(column_match + sql_generation). For Excel uploads of 50+ rules this
gets slow on a local model; batching across rows is deferred until we
hit a real cost ceiling.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from app.products.data_quality.ai.client import get_llm_client
from app.products.data_quality.ai.prompts import (
    column_match as col_prompt,
    sql_generation as sql_prompt,
)
from app.products.data_quality.ai.repositories.glossary_repository import (
    GlossaryRepository,
)
from app.products.data_quality.ai.repositories.import_repository import (
    ImportRepository,
)
from app.products.data_quality.ai.repositories.llm_call_repository import (
    LlmCallRepository,
)
from app.products.data_quality.ai.repositories.proposal_repository import (
    ProposalRepository,
)
from app.products.data_quality.ai.services import pii_anonymizer
from app.products.data_quality.ai.services.excel_parser import (
    ColumnSpec, ParsedRow, parse_excel,
)
from app.products.data_quality.ai.validators.response_schema import (
    validate_response,
)
from app.products.data_quality.ai.validators.rule_type_whitelist import (
    RULE_TYPE_WHITELIST,
)
from app.products.data_quality.ai.validators.sql_safety import (
    check_parameter,
)
from app.products.data_quality.permissions import can_use_dq, require
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

_VALID_DIMENSIONS = {"completeness", "validity", "uniqueness"}
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}

_COLUMNS = [
    ColumnSpec("rule_name",   required=True,  aliases=("name",)),
    ColumnSpec("description", required=False),
    ColumnSpec("logic_nl",    required=True,  aliases=("logic", "natural_language")),
    ColumnSpec("severity",    required=True),
    ColumnSpec("dimension",   required=True,  aliases=("dim",)),
    ColumnSpec("table",       required=False, aliases=("table_name",)),
    ColumnSpec("column",      required=False, aliases=("column_name",)),
]


def _validate_row(row: ParsedRow) -> None:
    sev = row.values.get("severity")
    if sev is not None:
        s = str(sev).lower().strip()
        if s not in _VALID_SEVERITIES:
            row.errors.append(
                f"severity {sev!r} must be one of {sorted(_VALID_SEVERITIES)}"
            )
        row.values["severity"] = s

    dim = row.values.get("dimension")
    if dim is not None:
        d = str(dim).lower().strip()
        if d not in _VALID_DIMENSIONS:
            row.errors.append(
                f"dimension {dim!r} must be one of {sorted(_VALID_DIMENSIONS)}"
            )
        row.values["dimension"] = d


def _normalize_name(s: str) -> str:
    """snake_case-ish concept name from a free-form rule_name."""
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:120] or "unnamed_rule"


class _ColumnCandidateRepo(PostgresqlAsyncRepository):
    """Lightweight inline repo for the candidate-column query.

    Bypasses ColumnProfileRepository because we want a tenant-scoped
    cross-profile lookup that takes only a table name."""

    async def candidates_for_table(
        self, tenant_id: int, table_name: str, *, limit: int = 60,
    ) -> list[dict]:
        return await self._fetch_all(
            """WITH latest_scans AS (
                  SELECT DISTINCT ON (s.profile_id) s.id, s.profile_id
                    FROM dq.t_dq_scans s
                    JOIN dq.t_dq_profiles p ON p.id = s.profile_id
                   WHERE p.tenant_id = $1 AND p.table_name = $2
                     AND s.status = 'success'
                ORDER BY s.profile_id, s.finished_at DESC NULLS LAST
               )
               SELECT cp.column_name, cp.declared_data_type, cp.type_category,
                      cp.inferred_column_type, cp.dominant_pattern,
                      p.id AS profile_id, p.connection_id, p.schema_name
                 FROM dq.t_dq_column_profiles cp
                 JOIN latest_scans ls ON ls.id = cp.scan_id
                 JOIN dq.t_dq_profiles p ON p.id = ls.profile_id
                ORDER BY cp.ordinal_position NULLS LAST, cp.column_name
                LIMIT $3""",
            (tenant_id, table_name, limit),
        )


class BusinessRuleIngestService:

    def __init__(self) -> None:
        self.imports = ImportRepository()
        self.proposals = ProposalRepository()
        self.audit = LlmCallRepository()
        self.glossary = GlossaryRepository()
        self.candidates = _ColumnCandidateRepo()

    async def ingest(
        self, *, file_bytes: bytes, filename: str,
        version_label: str | None, auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        if not file_bytes:
            raise ValidationException("Empty file")
        if len(file_bytes) > 10 * 1024 * 1024:
            raise ValidationException("File too large (max 10 MB)")

        file_hash = hashlib.sha256(file_bytes).hexdigest()
        existing = await self.imports.find_by_hash(auth_user.tenant_id, file_hash)
        if existing:
            return {
                "detail": "Duplicate upload — same bytes already imported",
                "import": existing,
            }

        imp = await self.imports.insert(
            tenant_id=auth_user.tenant_id, uploader_id=auth_user.user_id,
            kind="business_rules", filename=filename[:500], file_hash=file_hash,
            version_label=version_label,
        )
        import_id = imp["id"]

        await self.imports.update_status(
            import_id, auth_user.tenant_id, status="parsing",
        )
        parse = parse_excel(
            file_bytes, _COLUMNS, row_validators=[_validate_row],
        )

        if parse.file_errors and not parse.rows:
            imp_final = await self.imports.update_status(
                import_id, auth_user.tenant_id, status="error",
                row_count=0, error_count=parse.error_count,
                errors=parse.to_error_jsonb(),
            )
            return {"detail": "Parse failed", "import": imp_final}

        await self.imports.update_status(
            import_id, auth_user.tenant_id, status="enriching",
        )

        # Glossary context cached once per upload; same hint goes to every
        # column_match call so the LLM benefits from tenant-specific terms.
        glossary_hint = await self.glossary.list_for_tenant(auth_user.tenant_id)

        tally = {"easy": 0, "hard": 0, "unsupported": 0, "rejected": 0}

        for row in parse.ok_rows:
            outcome = await self._ingest_one(
                row=row, import_id=import_id, auth_user=auth_user,
                glossary_hint=glossary_hint,
            )
            tally[outcome] = tally.get(outcome, 0) + 1

        imp_final = await self.imports.update_status(
            import_id, auth_user.tenant_id, status="awaiting_review",
            row_count=len(parse.ok_rows),
            error_count=parse.error_count,
            errors=parse.to_error_jsonb() if parse.error_count else None,
            applied_at=datetime.now(timezone.utc),
        )
        return {
            "detail": (
                f"Business-rules import: {tally['easy']} easy-path, "
                f"{tally['hard']} hard-path (column matched + SQL generated), "
                f"{tally['unsupported']} unsupported, "
                f"{tally['rejected']} rejected by validator. "
                f"Review under /imports/{import_id}."
            ),
            "import": imp_final,
            "summary": {**tally, "row_errors": parse.error_count},
        }

    async def _ingest_one(
        self, *, row: ParsedRow, import_id: int, auth_user: AuthUser,
        glossary_hint: list[dict],
    ) -> str:
        """Per-row dispatcher. Returns the tally bucket: easy / hard /
        unsupported / rejected."""
        rule_name = row.values["rule_name"]
        description = row.values.get("description") or ""
        logic_nl = row.values["logic_nl"]
        severity = row.values["severity"]
        dimension = row.values["dimension"]
        table = (row.values.get("table") or "").strip() or None
        column = (row.values.get("column") or "").strip() or None

        if not table and not column:
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason=(
                    "Row has neither table nor column specified. Cross-table "
                    "rules aren't supported in this pipeline — split into "
                    "per-table rows or author manually."
                ),
                table=None, column=None,
            )
            return "unsupported"

        # Easy path — both table + column known. One LLM call (sql_generation).
        if table and column:
            return await self._easy_path(
                row=row, import_id=import_id, auth_user=auth_user,
                rule_name=rule_name, description=description, logic_nl=logic_nl,
                severity=severity, dimension=dimension,
                table=table, column=column,
            )

        # Hard path — table known, column blank. column_match -> sql_generation.
        # We can also accept "column known, table blank" by promoting it to
        # the easy path with no table context, but that's rare in practice.
        if table and not column:
            return await self._hard_path(
                row=row, import_id=import_id, auth_user=auth_user,
                rule_name=rule_name, description=description, logic_nl=logic_nl,
                severity=severity, dimension=dimension,
                table=table, glossary_hint=glossary_hint,
            )

        # column-only is treated as easy: the LLM gets the column name and
        # picks a rule_type/parameter. Table context is omitted.
        return await self._easy_path(
            row=row, import_id=import_id, auth_user=auth_user,
            rule_name=rule_name, description=description, logic_nl=logic_nl,
            severity=severity, dimension=dimension,
            table=None, column=column,
        )

    # ------------------------------------------------------------------
    # Easy path — single sql_generation call
    # ------------------------------------------------------------------

    async def _easy_path(
        self, *, row: ParsedRow, import_id: int, auth_user: AuthUser,
        rule_name: str, description: str, logic_nl: str,
        severity: str, dimension: str,
        table: str | None, column: str,
    ) -> str:
        client = get_llm_client()
        if client is None:
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason="LLM unavailable — set DQ_LLM_PROVIDER and retry.",
                table=table, column=column,
            )
            return "unsupported"

        sql_resp, sql_audit = await self._call_sql_generation(
            column=column, table=table, dimension=dimension,
            user_hint=f"{rule_name}. {logic_nl}",
            auth_user=auth_user,
        )

        return await self._persist_from_sql(
            row=row, import_id=import_id, auth_user=auth_user,
            rule_name=rule_name, dimension=dimension, severity=severity,
            table=table, column=column,
            sql_resp=sql_resp, sql_audit=sql_audit,
            candidates=None,
        )

    # ------------------------------------------------------------------
    # Hard path — column_match then sql_generation
    # ------------------------------------------------------------------

    async def _hard_path(
        self, *, row: ParsedRow, import_id: int, auth_user: AuthUser,
        rule_name: str, description: str, logic_nl: str,
        severity: str, dimension: str,
        table: str, glossary_hint: list[dict],
    ) -> str:
        client = get_llm_client()
        if client is None:
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason="LLM unavailable — set DQ_LLM_PROVIDER and retry.",
                table=table, column=None,
            )
            return "unsupported"

        candidates = await self.candidates.candidates_for_table(
            auth_user.tenant_id, table,
        )
        if not candidates:
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason=(
                    f"No profiled columns found for table {table!r}. "
                    f"Run a scan on a profile pointing at this table first, "
                    f"then re-upload."
                ),
                table=table, column=None,
            )
            return "unsupported"

        # column_match LLM call
        term = pii_anonymizer.anonymize_text(rule_name)
        sys_p = col_prompt.system_prompt()
        user_p = col_prompt.user_prompt(
            term=term, term_definition=f"{rule_name}. {logic_nl}",
            table_name=table, columns=candidates,
            glossary_hint=glossary_hint,
        )
        cm_result = await client.call(
            system=sys_p, user=user_p, json_mode=True,
            max_tokens=512, temperature=0.1,
        )
        prompt_hash = hashlib.sha256((sys_p + "\n---\n" + user_p).encode("utf-8")).hexdigest()
        response_hash = (
            hashlib.sha256(cm_result.text.encode("utf-8")).hexdigest()
            if cm_result.text else None
        )

        if not cm_result.success:
            cm_audit = await self._audit(
                "column_match", "api_error", cm_result, prompt_hash, response_hash, auth_user,
                prompt_version=col_prompt.PROMPT_VERSION,
            )
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason=f"column_match call failed: {cm_result.error}",
                table=table, column=None,
                llm_call_id=cm_audit["id"] if cm_audit else None,
            )
            return "rejected"

        cm_model, cm_err = validate_response("column_match", cm_result.parsed_json)
        if cm_err or cm_model is None or not cm_model.matches:
            cm_audit = await self._audit(
                "column_match", "validator_failed" if cm_err else "ok",
                cm_result, prompt_hash, response_hash, auth_user,
                prompt_version=col_prompt.PROMPT_VERSION, error=cm_err,
            )
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason=(cm_err or
                        f"LLM found no candidate columns for {rule_name!r} in {table}."),
                table=table, column=None,
                llm_call_id=cm_audit["id"] if cm_audit else None,
            )
            return "rejected"

        cm_audit = await self._audit(
            "column_match", "ok", cm_result, prompt_hash, response_hash, auth_user,
            prompt_version=col_prompt.PROMPT_VERSION,
        )

        # Verify the LLM didn't hallucinate column names — keep only ones
        # actually in our candidate list. Then pick the top by confidence.
        cand_names = {c["column_name"]: c for c in candidates}
        ranked = [
            {
                "column_name": m.column_name,
                "confidence": m.confidence,
                "reasoning": m.reasoning,
            }
            for m in cm_model.matches if m.column_name in cand_names
        ]
        if not ranked:
            await self._persist_unsupported(
                row, import_id, auth_user, rule_name, dimension, severity,
                reason=(
                    f"LLM proposed columns that don't exist on {table}: "
                    f"{[m.column_name for m in cm_model.matches]}"
                ),
                table=table, column=None,
                llm_call_id=cm_audit["id"] if cm_audit else None,
            )
            return "rejected"

        top = ranked[0]
        chosen_column = top["column_name"]

        # sql_generation against the chosen column.
        sql_resp, sql_audit = await self._call_sql_generation(
            column=chosen_column, table=table, dimension=dimension,
            user_hint=f"{rule_name}. {logic_nl}",
            auth_user=auth_user,
        )

        return await self._persist_from_sql(
            row=row, import_id=import_id, auth_user=auth_user,
            rule_name=rule_name, dimension=dimension, severity=severity,
            table=table, column=chosen_column,
            sql_resp=sql_resp, sql_audit=sql_audit,
            candidates=ranked,  # reviewer sees ranked alternatives
        )

    # ------------------------------------------------------------------
    # Shared LLM call + persistence helpers
    # ------------------------------------------------------------------

    async def _call_sql_generation(
        self, *, column: str, table: str | None,
        dimension: str | None, user_hint: str,
        auth_user: AuthUser,
    ) -> tuple[Any, dict | None]:
        """Run sql_generation and return (validated_model_or_None, audit_row).
        Validation failures still produce an audit row + return None."""
        client = get_llm_client()
        sys_p = sql_prompt.system_prompt()
        user_p = sql_prompt.user_prompt(
            column_name=pii_anonymizer.anonymize_column_name(column),
            table_name=table, rule_type=None, dimension=dimension,
            user_hint=user_hint,
        )
        result = await client.call(
            system=sys_p, user=user_p, json_mode=True,
            max_tokens=256, temperature=0.1,
        )
        prompt_hash = hashlib.sha256((sys_p + "\n---\n" + user_p).encode("utf-8")).hexdigest()
        response_hash = (
            hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            if result.text else None
        )

        if not result.success:
            audit = await self._audit(
                "sql_generation", "api_error", result, prompt_hash, response_hash, auth_user,
                prompt_version=sql_prompt.PROMPT_VERSION,
            )
            return None, audit

        model, err = validate_response("sql_generation", result.parsed_json)
        if err is not None or model is None:
            audit = await self._audit(
                "sql_generation", "validator_failed", result, prompt_hash,
                response_hash, auth_user,
                prompt_version=sql_prompt.PROMPT_VERSION, error=err,
            )
            return ({"error": err, "raw": result.text[:400]}, audit)

        audit = await self._audit(
            "sql_generation", "ok", result, prompt_hash, response_hash, auth_user,
            prompt_version=sql_prompt.PROMPT_VERSION,
        )
        return model, audit

    async def _persist_from_sql(
        self, *, row: ParsedRow, import_id: int, auth_user: AuthUser,
        rule_name: str, dimension: str, severity: str,
        table: str | None, column: str,
        sql_resp, sql_audit: dict | None,
        candidates: list[dict] | None,
    ) -> str:
        """Map the sql_generation outcome into a proposal row."""
        if sql_resp is None:
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload=self._payload(rule_name, dimension, None, None,
                                      severity, column, table),
                candidates=candidates, proposed_value=None,
                reasoning=None,
                error_reason="sql_generation LLM call failed",
                target_concept_id=None,
                llm_call_id=sql_audit["id"] if sql_audit else None,
            )
            return "rejected"

        # Validator-failed path returns a dict with {error, raw}
        if isinstance(sql_resp, dict):
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload=self._payload(rule_name, dimension, None, None,
                                      severity, column, table),
                candidates=candidates,
                proposed_value=sql_resp,
                reasoning=None,
                error_reason=sql_resp.get("error") or "schema validation failed",
                target_concept_id=None,
                llm_call_id=sql_audit["id"] if sql_audit else None,
            )
            return "rejected"

        # sql_resp is a SqlGenerationResponse pydantic model
        if sql_resp.rule_type is None:
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="unsupported_logic", confidence=sql_resp.confidence,
                payload=self._payload(rule_name, dimension, None, None,
                                      severity, column, table),
                candidates=candidates,
                proposed_value=sql_resp.model_dump(),
                reasoning=sql_resp.reasoning,
                error_reason=sql_resp.error_reason or "LLM declined to generate a rule",
                target_concept_id=None,
                llm_call_id=sql_audit["id"] if sql_audit else None,
            )
            return "unsupported"

        if sql_resp.rule_type not in RULE_TYPE_WHITELIST:
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload=self._payload(rule_name, dimension,
                                      sql_resp.rule_type, sql_resp.parameter,
                                      severity, column, table),
                candidates=candidates,
                proposed_value=sql_resp.model_dump(),
                reasoning=sql_resp.reasoning,
                error_reason=f"rule_type {sql_resp.rule_type!r} not in whitelist",
                target_concept_id=None,
                llm_call_id=sql_audit["id"] if sql_audit else None,
            )
            return "rejected"

        # Parameter safety check
        p_err = check_parameter(sql_resp.rule_type, sql_resp.parameter)
        if p_err:
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload=self._payload(rule_name, dimension,
                                      sql_resp.rule_type, None,
                                      severity, column, table),
                candidates=candidates,
                proposed_value=sql_resp.model_dump(),
                reasoning=sql_resp.reasoning,
                error_reason=p_err,
                target_concept_id=None,
                llm_call_id=sql_audit["id"] if sql_audit else None,
            )
            return "rejected"

        # Success.
        await self.proposals.insert(
            tenant_id=auth_user.tenant_id, import_id=import_id,
            source_row=row.row_number, kind="new_concept",
            status="pending",
            confidence=sql_resp.confidence or "MEDIUM",
            payload=self._payload(rule_name, dimension,
                                  sql_resp.rule_type, sql_resp.parameter,
                                  severity, column, table),
            candidates=candidates,
            proposed_value=sql_resp.model_dump(),
            reasoning=sql_resp.reasoning,
            error_reason=None,
            target_concept_id=None,
            llm_call_id=sql_audit["id"] if sql_audit else None,
        )
        return "easy" if not candidates else "hard"

    async def _persist_unsupported(
        self, row: ParsedRow, import_id: int, auth_user: AuthUser,
        rule_name: str, dimension: str, severity: str, *,
        reason: str, table: str | None, column: str | None,
        llm_call_id: int | None = None,
    ) -> None:
        await self.proposals.insert(
            tenant_id=auth_user.tenant_id, import_id=import_id,
            source_row=row.row_number, kind="new_concept",
            status="unsupported_logic", confidence=None,
            payload=self._payload(rule_name, dimension, None, None,
                                  severity, column, table),
            candidates=None, proposed_value=None,
            reasoning=None,
            error_reason=reason,
            target_concept_id=None,
            llm_call_id=llm_call_id,
        )

    def _payload(
        self, rule_name: str, dimension: str,
        rule_type: str | None, parameter: str | None,
        severity: str, column: str | None, table: str | None,
    ) -> dict:
        synonyms = []
        if column:
            synonyms.append(column.lower())
        return {
            "name": _normalize_name(rule_name),
            "dimension": dimension,
            "rule_type": rule_type,
            "parameter": parameter,
            "severity": severity,
            "synonyms": synonyms,
            "applies_to_types": [],
            "_source_rule_name": rule_name,
            "_target_table": table,
            "_target_column": column,
        }

    async def _audit(
        self, purpose: str, status: str, result, prompt_hash, response_hash,
        auth_user: AuthUser, *, prompt_version: int,
        error: str | None = None,
    ) -> dict | None:
        try:
            return await self.audit.insert(
                tenant_id=auth_user.tenant_id, purpose=purpose,
                model=result.model or "unknown",
                prompt_version=prompt_version,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_creation_tokens=result.cache_creation_tokens,
                latency_ms=result.latency_ms,
                status=status, error=(error or result.error),
                prompt_hash=prompt_hash, response_hash=response_hash,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("%s audit write failed: %s", purpose, e)
            return None


def get_business_rule_ingest_service() -> BusinessRuleIngestService:
    return BusinessRuleIngestService()

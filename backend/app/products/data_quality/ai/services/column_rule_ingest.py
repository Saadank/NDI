"""Column-rule ingest — BRD Table 13.

Schema:
    table* | column* | rule_type* | parameter | severity* | dimension*

Lifecycle:
    uploaded -> parsing -> enriching -> awaiting_review
                                     -> error  (parse or LLM-only-failure)

Two paths per row:

- **Easy path** — all six fields supplied. Confidence = HIGH. No LLM call.
  Lands as a ``new_concept`` proposal in ``pending`` status.

- **Hard path** — ``parameter`` blank AND ``rule_type=format_regex``.
  Calls the ``sql_generation`` LLM purpose to draft the regex. The
  generated parameter goes through the same validators as Approach 2
  (response_schema + rule_type_whitelist + sql_safety.check_parameter).
  Confidence inherited from the LLM response (HIGH / MEDIUM / LOW).
  Validator failures land as ``rejected_by_validator`` with error_reason.

Why ``new_concept`` (not ``active_rule_binding``) per row:
    Table 13 rows describe a per-column rule, not a binding to an
    already-existing dictionary concept. We synthesise the concept on
    approval (Step 6.7); the column name is captured as a synonym so
    the matcher will bind it automatically on the next apply.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone

from app.products.data_quality.ai.client import get_llm_client
from app.products.data_quality.ai.prompts import sql_generation as sql_prompt
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
    check as check_rule_type, RULE_TYPE_WHITELIST,
)
from app.products.data_quality.ai.validators.sql_safety import (
    check_parameter,
)
from app.products.data_quality.permissions import can_use_dq, require
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

_VALID_DIMENSIONS = {"completeness", "validity", "uniqueness"}
_VALID_SEVERITIES = {"critical", "high", "medium", "low"}
_NAME_RE = re.compile(r"[^a-z0-9]+")

_COLUMNS = [
    ColumnSpec("table",      required=True,  aliases=("table_name",)),
    ColumnSpec("column",     required=True,  aliases=("column_name",)),
    ColumnSpec("rule_type",  required=True,  aliases=("rule",)),
    ColumnSpec("parameter",  required=False, aliases=("param", "value")),
    ColumnSpec("severity",   required=True),
    ColumnSpec("dimension",  required=True,  aliases=("dim",)),
]


def _validate_row(row: ParsedRow) -> None:
    """Per-row business validation. Normalizes whitespace/case in place."""
    rt = row.values.get("rule_type")
    if rt is not None:
        rt_norm = str(rt).lower().strip()
        if rt_norm not in RULE_TYPE_WHITELIST:
            row.errors.append(
                f"rule_type {rt!r} must be one of {sorted(RULE_TYPE_WHITELIST)}"
            )
        row.values["rule_type"] = rt_norm

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

    # If the user supplied a parameter, validate it through the same gates the
    # LLM-generated ones go through. Fails-fast: invalid easy-path parameters
    # become row errors and never reach the proposal queue.
    param = row.values.get("parameter")
    if param is not None and str(param).strip():
        p_err = check_parameter(row.values.get("rule_type") or "", str(param).strip())
        if p_err:
            row.errors.append(f"parameter: {p_err}")
        else:
            row.values["parameter"] = str(param).strip()
    else:
        row.values["parameter"] = None


def _synthesize_name(table: str, column: str, rule_type: str) -> str:
    """Generate a stable, snake_case concept name from the row's
    (table, column, rule_type) triple. Used as the default ``name`` on
    the new_concept proposal payload — reviewer can override at approval."""
    base = f"{rule_type}_{column}_{table}"
    base = _NAME_RE.sub("_", base.lower()).strip("_")
    return base[:120] or "unnamed_concept"


class ColumnRuleIngestService:

    def __init__(self) -> None:
        self.imports = ImportRepository()
        self.proposals = ProposalRepository()
        self.audit = LlmCallRepository()

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
            kind="column_rules", filename=filename[:500], file_hash=file_hash,
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

        # Move into enriching state — LLM calls happen for any row whose
        # parameter is blank under a rule_type that needs one.
        await self.imports.update_status(
            import_id, auth_user.tenant_id, status="enriching",
        )

        easy_count = 0
        llm_count = 0
        rejected_count = 0

        for row in parse.ok_rows:
            await self._ingest_one(
                row=row, import_id=import_id, auth_user=auth_user,
            )
        # Re-tally for the import summary.
        for row in parse.ok_rows:
            tag = getattr(row, "_outcome", None)
            if tag == "easy":
                easy_count += 1
            elif tag == "llm":
                llm_count += 1
            elif tag == "rejected":
                rejected_count += 1

        imp_final = await self.imports.update_status(
            import_id, auth_user.tenant_id, status="awaiting_review",
            row_count=len(parse.ok_rows),
            error_count=parse.error_count,
            errors=parse.to_error_jsonb() if parse.error_count else None,
            applied_at=datetime.now(timezone.utc),
        )
        return {
            "detail": (
                f"Column-rules import: {easy_count} HIGH (easy path), "
                f"{llm_count} LLM-drafted, {rejected_count} rejected by validator. "
                f"Review under /imports/{import_id}."
            ),
            "import": imp_final,
            "summary": {
                "easy": easy_count, "llm": llm_count,
                "rejected": rejected_count,
                "row_errors": parse.error_count,
            },
        }

    async def _ingest_one(
        self, *, row: ParsedRow, import_id: int, auth_user: AuthUser,
    ) -> None:
        """Persist one Table-13 row as a t_dq_proposals entry. Annotates
        the row with ``_outcome`` for the caller's summary tally."""
        table = row.values["table"]
        column = row.values["column"]
        rule_type = row.values["rule_type"]
        parameter = row.values.get("parameter")
        severity = row.values["severity"]
        dimension = row.values["dimension"]

        # Easy path — user supplied the parameter (or rule_type takes none).
        needs_llm = (
            parameter is None
            and rule_type == "format_regex"
        )

        if not needs_llm:
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id,
                import_id=import_id, source_row=row.row_number,
                kind="new_concept", status="pending",
                confidence="HIGH",
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension,
                    "rule_type": rule_type,
                    "parameter": parameter,
                    "severity": severity,
                    "synonyms": [column.lower()],
                    # Captured for 6.7's applier to find the right profile.
                    "_target_table": table,
                    "_target_column": column,
                },
                candidates=None,
                proposed_value=None,
                reasoning="User-supplied column rule (no LLM needed).",
                error_reason=None,
                target_concept_id=None,
                llm_call_id=None,
            )
            row._outcome = "easy"
            return

        # Hard path — LLM generates the missing parameter.
        client = get_llm_client()
        if client is None:
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="needs_llm", confidence=None,
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension, "rule_type": rule_type,
                    "parameter": None, "severity": severity,
                    "synonyms": [column.lower()],
                    "_target_table": table, "_target_column": column,
                },
                candidates=None, proposed_value=None,
                reasoning=None,
                error_reason="LLM unavailable — set DQ_LLM_PROVIDER and retry.",
                target_concept_id=None, llm_call_id=None,
            )
            row._outcome = "rejected"
            return

        # PII gate (pass-through stub today).
        col_safe = pii_anonymizer.anonymize_column_name(column)

        system = sql_prompt.system_prompt()
        user = sql_prompt.user_prompt(
            column_name=col_safe, table_name=table,
            rule_type=rule_type, dimension=dimension,
        )

        result = await client.call(
            system=system, user=user, json_mode=True,
            max_tokens=256, temperature=0.1,
        )

        prompt_hash = hashlib.sha256(
            (system + "\n---\n" + user).encode("utf-8")
        ).hexdigest()
        response_hash = (
            hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            if result.text else None
        )

        if not result.success:
            llm_row = await self._audit("api_error", result, prompt_hash, response_hash, auth_user)
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension, "rule_type": rule_type,
                    "parameter": None, "severity": severity,
                    "synonyms": [column.lower()],
                    "_target_table": table, "_target_column": column,
                },
                candidates=None, proposed_value=None, reasoning=None,
                error_reason=f"LLM call failed: {result.error}",
                target_concept_id=None,
                llm_call_id=llm_row["id"] if llm_row else None,
            )
            row._outcome = "rejected"
            return

        model, err = validate_response("sql_generation", result.parsed_json)
        if err is not None or model is None:
            llm_row = await self._audit("validator_failed", result, prompt_hash, response_hash, auth_user, error=err)
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension, "rule_type": rule_type,
                    "parameter": None, "severity": severity,
                    "synonyms": [column.lower()],
                    "_target_table": table, "_target_column": column,
                },
                candidates=None,
                proposed_value=({"raw": result.text[:400]}
                                if result.text else None),
                reasoning=None,
                error_reason=err or "response schema validation failed",
                target_concept_id=None,
                llm_call_id=llm_row["id"] if llm_row else None,
            )
            row._outcome = "rejected"
            return

        # LLM explicitly returned rule_type=null (couldn't generate).
        if model.rule_type is None:
            llm_row = await self._audit("ok", result, prompt_hash, response_hash, auth_user)
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="unsupported_logic", confidence=None,
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension, "rule_type": rule_type,
                    "parameter": None, "severity": severity,
                    "synonyms": [column.lower()],
                    "_target_table": table, "_target_column": column,
                },
                candidates=None, proposed_value=model.model_dump(),
                reasoning=model.reasoning,
                error_reason=model.error_reason or "LLM declined to generate a parameter",
                target_concept_id=None,
                llm_call_id=llm_row["id"] if llm_row else None,
            )
            row._outcome = "rejected"
            return

        # Rule_type the LLM picked must match what the user asked for.
        if model.rule_type != rule_type:
            llm_row = await self._audit("validator_failed", result, prompt_hash, response_hash, auth_user,
                                        error=f"LLM rule_type drift: asked {rule_type}, got {model.rule_type}")
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension, "rule_type": rule_type,
                    "parameter": None, "severity": severity,
                    "synonyms": [column.lower()],
                    "_target_table": table, "_target_column": column,
                },
                candidates=None, proposed_value=model.model_dump(),
                reasoning=model.reasoning,
                error_reason=f"LLM drifted on rule_type (asked {rule_type}, got {model.rule_type})",
                target_concept_id=None,
                llm_call_id=llm_row["id"] if llm_row else None,
            )
            row._outcome = "rejected"
            return

        # Parameter safety check (regex compile, deny-list, range).
        p_err = check_parameter(model.rule_type, model.parameter)
        if p_err:
            llm_row = await self._audit("validator_failed", result, prompt_hash, response_hash, auth_user, error=p_err)
            await self.proposals.insert(
                tenant_id=auth_user.tenant_id, import_id=import_id,
                source_row=row.row_number, kind="new_concept",
                status="rejected_by_validator", confidence=None,
                payload={
                    "name": _synthesize_name(table, column, rule_type),
                    "dimension": dimension, "rule_type": rule_type,
                    "parameter": None, "severity": severity,
                    "synonyms": [column.lower()],
                    "_target_table": table, "_target_column": column,
                },
                candidates=None, proposed_value=model.model_dump(),
                reasoning=model.reasoning,
                error_reason=p_err,
                target_concept_id=None,
                llm_call_id=llm_row["id"] if llm_row else None,
            )
            row._outcome = "rejected"
            return

        # Success — pending proposal with LLM-drafted parameter.
        llm_row = await self._audit("ok", result, prompt_hash, response_hash, auth_user)
        await self.proposals.insert(
            tenant_id=auth_user.tenant_id, import_id=import_id,
            source_row=row.row_number, kind="new_concept",
            status="pending",
            confidence=model.confidence or "MEDIUM",
            payload={
                "name": _synthesize_name(table, column, rule_type),
                "dimension": dimension, "rule_type": rule_type,
                "parameter": model.parameter, "severity": severity,
                "synonyms": [column.lower()],
                "_target_table": table, "_target_column": column,
            },
            candidates=None,
            proposed_value=model.model_dump(),
            reasoning=model.reasoning,
            error_reason=None,
            target_concept_id=None,
            llm_call_id=llm_row["id"] if llm_row else None,
        )
        row._outcome = "llm"

    async def _audit(
        self, status: str, result, prompt_hash, response_hash,
        auth_user: AuthUser, *, error: str | None = None,
    ) -> dict | None:
        try:
            return await self.audit.insert(
                tenant_id=auth_user.tenant_id, purpose="sql_generation",
                model=result.model or "unknown",
                prompt_version=sql_prompt.PROMPT_VERSION,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_creation_tokens=result.cache_creation_tokens,
                latency_ms=result.latency_ms,
                status=status, error=(error or result.error),
                prompt_hash=prompt_hash, response_hash=response_hash,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("sql_generation audit write failed: %s", e)
            return None


def get_column_rule_ingest_service() -> ColumnRuleIngestService:
    return ColumnRuleIngestService()

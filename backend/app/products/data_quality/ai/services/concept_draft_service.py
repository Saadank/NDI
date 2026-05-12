"""Approach 2 — interactive NL → concept drafting.

Called by ``POST /concepts/draft-from-nl``. The user is the reviewer in
real-time (modal in the Dictionary tab), so this path bypasses
``t_dq_proposals`` and returns the draft directly. We still write a row
to ``t_dq_llm_calls`` for cost/audit.

Failure modes returned to the caller:
- ``llm_unavailable``  — provider not configured / Ollama unreachable
- ``llm_error``        — LLM call failed (timeout / api error)
- ``invalid_response`` — LLM returned but the schema rejected it
- ``ok``               — returns the drafted concept payload
"""
from __future__ import annotations

import hashlib
import logging

from app.products.data_quality.ai.client import get_llm_client
from app.products.data_quality.ai.prompts import concept_draft as prompt
from app.products.data_quality.ai.repositories.llm_call_repository import (
    LlmCallRepository,
)
from app.products.data_quality.ai.services import pii_anonymizer
from app.products.data_quality.ai.validators.response_schema import (
    validate_response,
)
from app.products.data_quality.ai.validators.rule_type_whitelist import (
    check as check_rule_type,
)
from app.products.data_quality.ai.validators.sql_safety import (
    check_parameter,
)
from app.products.data_quality.permissions import can_use_dq, require
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

_PURPOSE = "concept_draft"
_VALID_DIMENSIONS = {"completeness", "validity", "uniqueness"}


class ConceptDraftService:

    def __init__(self) -> None:
        self.audit = LlmCallRepository()

    async def draft(
        self, *, nl_text: str, dimension_hint: str | None,
        auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        if not nl_text or not nl_text.strip():
            raise ValidationException("nl_text is required")
        if len(nl_text) > 2000:
            raise ValidationException("nl_text too long (max 2000 chars)")
        if dimension_hint and dimension_hint not in _VALID_DIMENSIONS:
            raise ValidationException(
                f"dimension_hint must be one of {sorted(_VALID_DIMENSIONS)}"
            )

        client = get_llm_client()
        if client is None:
            return {
                "status": "llm_unavailable",
                "error": "DQ_LLM_PROVIDER not configured or LLM unreachable",
            }

        # PII gate — pass-through today (Step 6.2 stub).
        safe_text = pii_anonymizer.anonymize_text(nl_text)

        system = prompt.system_prompt()
        user = prompt.user_prompt(safe_text, dimension_hint)

        # Slightly higher token cap than the default — concept drafts include
        # a regex + reasoning + synonyms which can run long.
        result = await client.call(
            system=system, user=user,
            json_mode=True, max_tokens=512, temperature=0.2,
        )

        # Audit every call regardless of outcome — that's the point of the
        # audit table. prompt_hash fingerprints the input without storing it.
        prompt_hash = hashlib.sha256(
            (system + "\n---\n" + user).encode("utf-8")
        ).hexdigest()
        response_hash = (
            hashlib.sha256(result.text.encode("utf-8")).hexdigest()
            if result.text else None
        )

        # --- LLM-call failure ----------------------------------------------
        if not result.success:
            await self._audit(auth_user, result, status="api_error",
                              prompt_hash=prompt_hash, response_hash=response_hash)
            return {
                "status": "llm_error",
                "error": result.error,
                "latency_ms": result.latency_ms,
            }

        # --- schema validation ---------------------------------------------
        model, err = validate_response(_PURPOSE, result.parsed_json)
        if err is not None or model is None:
            await self._audit(auth_user, result, status="validator_failed",
                              error=err, prompt_hash=prompt_hash,
                              response_hash=response_hash)
            return {
                "status": "invalid_response",
                "error": err,
                "raw": result.text[:400],
                "latency_ms": result.latency_ms,
            }

        # --- rule_type whitelist (belt and suspenders) ---------------------
        rt_err = check_rule_type(model.rule_type)
        if rt_err is not None:
            await self._audit(auth_user, result, status="validator_failed",
                              error=rt_err, prompt_hash=prompt_hash,
                              response_hash=response_hash)
            return {
                "status": "invalid_response", "error": rt_err,
                "latency_ms": result.latency_ms,
            }

        # --- parameter safety (regex compile, range, deny-list) ------------
        p_err = check_parameter(model.rule_type, model.parameter)
        if p_err is not None:
            await self._audit(auth_user, result, status="validator_failed",
                              error=p_err, prompt_hash=prompt_hash,
                              response_hash=response_hash)
            return {
                "status": "invalid_response", "error": p_err,
                "latency_ms": result.latency_ms,
            }

        # Success.
        await self._audit(auth_user, result, status="ok",
                          prompt_hash=prompt_hash, response_hash=response_hash)
        return {
            "status": "ok",
            "draft": model.model_dump(),
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        }

    async def _audit(
        self, auth_user: AuthUser, result, *,
        status: str, error: str | None = None,
        prompt_hash: str | None, response_hash: str | None,
    ) -> None:
        """Best-effort audit log — never fails the user-facing call."""
        try:
            await self.audit.insert(
                tenant_id=auth_user.tenant_id,
                purpose=_PURPOSE,
                model=result.model or "unknown",
                prompt_version=prompt.PROMPT_VERSION,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=result.cache_read_tokens,
                cache_creation_tokens=result.cache_creation_tokens,
                latency_ms=result.latency_ms,
                status=status,
                error=(error or result.error),
                prompt_hash=prompt_hash,
                response_hash=response_hash,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("LLM audit write failed: %s", e)


def get_concept_draft_service() -> ConceptDraftService:
    return ConceptDraftService()

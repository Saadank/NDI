"""Glossary AI-Assist service — Draft / Rephrase / Advise (BRD §6.3, WF-06).

Suggestions only — this service NEVER writes a term or changes its status; the
router returns text and the frontend's "Apply" copies it into a field locally.

Design constraints honoured here:
  * Privacy (FR-025 / NFR-4): the prompt carries only the term name, the
    user-provided context, and existing definition text — never raw data
    values from any source database.
  * Audit (FR-023): every call is logged to t_glossary_llm_calls with content
    *hashes* only (sha256), token count, latency, and a success flag.
  * Graceful fallback (FR-024): if no LLM is configured or the call fails, the
    service returns ``available=False`` with a message and the rest of the
    authoring workflow keeps working.

LLM access goes through the NDMO product's **provider-agnostic** client
(``ai/client.py``) — Ollama / Anthropic / … behind one interface — rather than
binding directly to any single SDK.  The provider is chosen by environment
config shared with the platform's DQ LLM settings.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from uuid import UUID

from app.products.ndmo_compliance.ai.client import get_ndmo_llm_client
from app.products.ndmo_compliance.repositories.glossary_llm_repository import (
    GlossaryLlmRepository,
)
from app.structures.auth_user import AuthUser

logger = logging.getLogger(__name__)

_UNAVAILABLE_MSG = (
    "AI Assist is temporarily unavailable. You can continue authoring manually."
)

_SYSTEM = (
    "You are a data-governance assistant helping a steward author a business "
    "glossary term for an organisation operating under the Saudi NDMO "
    "framework. Write clear, formal, vendor-neutral definitions. Never invent "
    "specific data values, figures, or proprietary details — define the "
    "business *meaning* only. Keep output concise and ready to paste into a "
    "glossary field. Do not add headers, markdown, or commentary unless asked."
)


@dataclass(slots=True)
class AssistResult:
    available: bool
    output: str | None
    message: str | None = None


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class GlossaryAssistService:
    def __init__(self) -> None:
        self._llm = GlossaryLlmRepository()

    # ---- public modes ---------------------------------------------------

    async def draft(
        self, *, auth_user: AuthUser, term_name: str, context: str | None,
        term_id: UUID | None = None,
    ) -> AssistResult:
        user = (
            f"Term name: {term_name}\n"
            f"Business context: {context or '(none provided)'}\n\n"
            "Write a single concise business definition (2–4 sentences) for "
            "this term. Define its business meaning, not a technical/column "
            "description."
        )
        return await self._run(auth_user, "draft", user, term_id)

    async def rephrase(
        self, *, auth_user: AuthUser, current_definition: str,
        instruction: str | None, term_id: UUID | None = None,
    ) -> AssistResult:
        user = (
            f"Current definition:\n{current_definition}\n\n"
            f"Instruction: {instruction or 'Improve clarity, precision and tone.'}\n\n"
            "Rewrite the definition accordingly. Return only the rewritten "
            "definition text."
        )
        return await self._run(auth_user, "rephrase", user, term_id)

    async def advise(
        self, *, auth_user: AuthUser, term_name: str,
        definition_draft: str | None, related_terms: str | None,
        term_id: UUID | None = None,
    ) -> AssistResult:
        user = (
            f"Term name: {term_name}\n"
            f"Draft definition: {definition_draft or '(none yet)'}\n"
            f"Related terms: {related_terms or '(none)'}\n\n"
            "Act as a glossary reviewer. Give brief, actionable advice: missing "
            "fields, ambiguities, inconsistencies with the related terms, and "
            "suggested synonyms. Use short bullet points. Do NOT write the "
            "definition itself."
        )
        return await self._run(auth_user, "advise", user, term_id)

    # ---- core -----------------------------------------------------------

    async def _run(
        self, auth_user: AuthUser, purpose: str, user_prompt: str,
        term_id: UUID | None,
    ) -> AssistResult:
        input_hash = _sha(_SYSTEM + "\n" + user_prompt)
        client = get_ndmo_llm_client()

        if client is None:
            await self._audit(auth_user, purpose, input_hash, None, None, None, False, term_id)
            return AssistResult(
                available=False, output=None,
                message="AI Assist isn't configured in this environment. "
                        "You can continue authoring manually.",
            )

        result = await client.call(system=_SYSTEM, user=user_prompt, json_mode=False)
        output = result.text.strip() if (result.success and result.text) else None
        await self._audit(
            auth_user, purpose, input_hash,
            result.response_hash or (_sha(output) if output else None),
            result.total_tokens, result.latency_ms, bool(output), term_id,
        )
        if output:
            return AssistResult(available=True, output=output, message=None)
        logger.warning("glossary assist (%s) failed: %s", purpose, result.error)
        return AssistResult(available=False, output=None, message=_UNAVAILABLE_MSG)

    async def _audit(
        self, auth_user: AuthUser, purpose: str, input_hash: str | None,
        output_hash: str | None, tokens: int | None, latency_ms: int | None,
        success: bool, term_id: UUID | None,
    ) -> None:
        try:
            await self._llm.record(
                tenant_id=auth_user.tenant_id, purpose=purpose,
                input_hash=input_hash, output_hash=output_hash,
                tokens_used=tokens, latency_ms=latency_ms,
                success=success, term_id=term_id,
            )
        except Exception as e:  # noqa: BLE001 — audit must never break the response
            logger.error("failed to record glossary LLM audit row: %s", e)


def get_glossary_assist_service() -> GlossaryAssistService:
    return GlossaryAssistService()

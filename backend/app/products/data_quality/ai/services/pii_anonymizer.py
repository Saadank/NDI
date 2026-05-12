"""PII gatekeeper for LLM prompts.

**STUB** — currently a pass-through. Logged as IDQP_STATUS open-item #2:
real PII rules will land before this codebase is exposed to tenants
whose column names are themselves sensitive (e.g. ``patient_dob``,
``cardholder_ssn``, employee compensation columns).

When the real implementation lands it will:

  - Strip raw row values that somehow made it into a prompt builder.
    The profiler already enforces this on its own data path, but the
    Excel ingestion paths in 6.4–6.6 don't have that guarantee.
  - Hash sensitive column names against a tenant-configurable blocklist
    so the LLM sees ``col_4a2f`` instead of ``patient_ssn``. The mapping
    stays in app memory for the call duration, never persisted.
  - Be unit-tested with fixture data: CI will fail if any raw value or
    blocklisted column name reaches the test harness's prompt-builder
    output.

Until then this module exists so the call sites can wire through the
interface without refactoring later. The pass-through behavior is
**safe by default for the current dev tenant** (portfolio / holdings /
test users — no real PII), but unsafe to ship to production without
the real implementation.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Has the "stub in use" warning fired once already?
_warned = False


def anonymize_text(text: str) -> str:
    """Strip / redact PII-ish content from a free-form text passed to the
    LLM. **Pass-through stub.**"""
    _warn_once()
    return text


def anonymize_column_name(column_name: str) -> str:
    """Hash a sensitive column name to a stable opaque label.
    **Pass-through stub.**"""
    _warn_once()
    return column_name


def anonymize_glossary_term(term: str) -> str:
    """Same gating, applied to a business-glossary term before it lands
    in a prompt. **Pass-through stub.**"""
    _warn_once()
    return term


def _warn_once() -> None:
    global _warned
    if not _warned:
        logger.warning(
            "PII anonymizer is a pass-through stub — raw inputs are forwarded "
            "to the LLM. Real rules pending (IDQP_STATUS open-item #2)."
        )
        _warned = True

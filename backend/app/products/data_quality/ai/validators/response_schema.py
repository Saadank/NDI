"""Pydantic schemas — one per LLM purpose — used to validate the JSON
the model returns. A failure here turns into a ``rejected_by_validator``
proposal so the human reviewer can see what went wrong without being
able to approve broken output.

These schemas are intentionally **permissive on the edges** (extra fields
ignored) and **strict on the core** (required keys, bounded enums) — small
local models often add commentary fields we don't care about, but always
need to nail the required shape.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Confidence labels — match the active-rule applier's HIGH/MEDIUM/LOW.
Confidence = Literal["HIGH", "MEDIUM", "LOW"]

# Rule-type whitelist — mirrors the deterministic validator's set.
RuleType = Literal[
    "not_null", "max_null_rate", "no_pseudo_nulls", "unique", "format_regex",
]

# DQ dimensions — mirrors enums/dq_dimension.py.
Dimension = Literal["completeness", "validity", "uniqueness"]

Severity = Literal["critical", "high", "medium", "low"]


class _Base(BaseModel):
    """All response models accept unknown fields silently."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


# ----- concept_match (existing matcher uses bespoke parsing; kept here for parity) -----

class ConceptMatchEntry(_Base):
    concept_id: int
    confidence: Confidence
    reasoning: str = ""


class ConceptMatchResponse(_Base):
    matches: list[ConceptMatchEntry] = Field(default_factory=list)


# ----- column_match (business term -> column name candidates) -----

class ColumnMatchEntry(_Base):
    column_name: str
    confidence: Confidence
    reasoning: str = ""


class ColumnMatchResponse(_Base):
    matches: list[ColumnMatchEntry] = Field(default_factory=list)


# ----- sql_generation (NL rule -> rule_type + parameter) -----

class SqlGenerationResponse(_Base):
    """LLM may decline to produce a rule (returns rule_type=None) — that's
    a valid response and becomes a ``unsupported_logic`` proposal."""
    rule_type: RuleType | None = None
    parameter: str | None = None  # regex string, threshold string, etc.
    confidence: Confidence | None = None
    reasoning: str = ""
    error_reason: str | None = None  # when rule_type is null

    @field_validator("parameter", mode="before")
    @classmethod
    def _coerce_parameter(cls, v):
        # Numeric thresholds come back as floats sometimes; we always
        # persist them as strings to keep the parameter column type-stable.
        return None if v is None else str(v)


# ----- concept_draft (NL → full concept) -----

class ConceptDraftResponse(_Base):
    name: str = Field(min_length=1, max_length=120)
    dimension: Dimension
    rule_type: RuleType
    parameter: str | None = None
    severity: Severity = "medium"
    synonyms: list[str] = Field(default_factory=list)
    applies_to_types: list[str] = Field(default_factory=list)
    confidence: Confidence = "MEDIUM"
    reasoning: str = ""

    @field_validator("parameter", mode="before")
    @classmethod
    def _coerce_parameter(cls, v):
        return None if v is None else str(v)

    @field_validator("synonyms", "applies_to_types", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        """Small models sometimes return ``"a,b,c"`` for list fields.
        Accept that and split."""
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


# ----- regex_draft (NL → regex pattern + examples for a single concept) -----

class RegexDraftResponse(_Base):
    pattern: str = Field(min_length=1, max_length=500)
    explanation: str = ""
    examples_pass: list[str] = Field(default_factory=list, max_length=5)
    examples_fail: list[str] = Field(default_factory=list, max_length=5)
    confidence: Confidence = "MEDIUM"

    @field_validator("examples_pass", "examples_fail", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


# ----- synonym_expansion -----

class SynonymExpansionResponse(_Base):
    synonyms: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("synonyms", mode="before")
    @classmethod
    def _coerce_list(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_SCHEMA_BY_PURPOSE: dict[str, type[_Base]] = {
    "concept_match":      ConceptMatchResponse,
    "column_match":       ColumnMatchResponse,
    "sql_generation":     SqlGenerationResponse,
    "concept_draft":      ConceptDraftResponse,
    "regex_draft":        RegexDraftResponse,
    "synonym_expansion":  SynonymExpansionResponse,
}


def validate_response(purpose: str, parsed_json) -> tuple[_Base | None, str | None]:
    """Validate a parsed-JSON response against the schema for ``purpose``.

    Returns ``(model, None)`` on success, ``(None, error_msg)`` on failure.
    """
    schema = _SCHEMA_BY_PURPOSE.get(purpose)
    if schema is None:
        return None, f"unknown purpose: {purpose}"
    if parsed_json is None:
        return None, "response was not JSON"
    try:
        return schema.model_validate(parsed_json), None
    except Exception as e:  # pydantic.ValidationError but also broader
        return None, f"schema validation failed: {e}"

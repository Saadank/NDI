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

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _coerce_parameter_to_str(v: Any) -> str | None:
    """Normalize an LLM-returned ``parameter`` field to a single JSON-safe
    string.

    The parameter field is shared across rule types: a regex string for
    format_regex, ``null`` for not_null/unique/no_pseudo_nulls, a JSON list
    or object for dictionary_match. Storing it as ``str | None`` keeps the
    schema simple, but ``str([...])`` would emit Python-repr (single quotes)
    which downstream consumers can't parse as JSON — hence ``json.dumps``
    for non-scalar values."""
    if v is None:
        return None
    if isinstance(v, str):
        return v
    if isinstance(v, (list, dict)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)

# Confidence labels — match the active-rule applier's HIGH/MEDIUM/LOW.
Confidence = Literal["HIGH", "MEDIUM", "LOW"]

# Rule-type whitelist — mirrors the deterministic validator's set.
RuleType = Literal[
    "not_null", "no_pseudo_nulls", "unique", "format_regex", "dictionary_match",
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
    parameter: str | None = None  # regex string, JSON-list string, etc.
    confidence: Confidence | None = None
    reasoning: str = ""
    error_reason: str | None = None  # when rule_type is null

    @field_validator("parameter", mode="before")
    @classmethod
    def _coerce_parameter(cls, v):
        return _coerce_parameter_to_str(v)


# ----- concept_draft (NL → full concept) -----

class ConceptDraftResponse(_Base):
    name: str = Field(min_length=1, max_length=120)
    dimension: Dimension
    rule_type: RuleType
    parameter: str | None = None
    severity: Severity = "medium"
    synonyms: list[str] = Field(default_factory=list)
    confidence: Confidence = "MEDIUM"
    reasoning: str = ""

    @field_validator("parameter", mode="before")
    @classmethod
    def _coerce_parameter(cls, v):
        return _coerce_parameter_to_str(v)

    @field_validator("synonyms", mode="before")
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


# ----- dictionary_draft (NL → list of allowed values for a dictionary_match concept) -----

class DictionaryDraftResponse(_Base):
    values: list[str] = Field(default_factory=list, max_length=200)
    case_sensitive: bool = False
    explanation: str = ""
    confidence: Confidence = "MEDIUM"

    @field_validator("values", mode="before")
    @classmethod
    def _coerce_values(cls, v):
        # Small models sometimes return ``"USD,EUR,SAR"`` for list fields,
        # or a list with int/float entries. Normalize to a clean str list
        # while preserving order; per-value sanitisation happens in
        # sql_safety + concept_service.
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        out: list[str] = []
        for entry in v:
            if entry is None:
                continue
            s = str(entry).strip()
            if s:
                out.append(s)
        return out


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
    "dictionary_draft":   DictionaryDraftResponse,
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

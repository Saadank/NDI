"""Structured output the assessment LLM is forced to produce.

Implemented as an OpenAI Structured Outputs ``response_format`` (strict
JSON Schema, model-guaranteed since gpt-4o-2024-08-06).  The model
cannot emit free-form text — every response is a JSON object matching
the schema, no extraction parsing fragility.

OpenAI strict-mode constraints we honor here:
  * every property MUST appear in ``required``
  * every object MUST set ``additionalProperties: false``
  * value constraints (minimum/maximum/minLength/maxLength/minItems/
    maxItems/pattern) are NOT supported — we move them into descriptions
    so the model still sees the rule, just not as a hard schema check.
    The engine then validates ranges in Python.

The Python dataclasses below mirror the schema 1:1 so the engine
type-checks the parsed output without a Pydantic dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# JSON Schema delivered to OpenAI's Chat Completions API as
# ``response_format={"type": "json_schema", "json_schema": ASSESSMENT_JSON_SCHEMA}``.
ASSESSMENT_JSON_SCHEMA: dict[str, Any] = {
    "name": "submit_assessment",
    "description": (
        "NDMO compliance assessment for the current specification. "
        "All Arabic free-text fields must be in Modern Standard Arabic. "
        "Citations must reference chunks from the provided evidence list only — "
        "do not fabricate chunk_ids."
    ),
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "maturity_level": {
                "type": "integer",
                "description": (
                    "Integer 0..5.  0=Absence of capabilities, 1=Building, "
                    "2=Defined, 3=Activated, 4=Enabled, 5=Leading.  "
                    "Any value outside 0..5 will be rejected by the engine."
                ),
            },
            "confidence": {
                "type": "number",
                "description": (
                    "Number between 0.0 and 1.0.  Subjective confidence in "
                    "the maturity verdict given evidence quality and coverage. "
                    "Below 0.6 means the assessment must be reviewed by an analyst."
                ),
            },
            "rationale_ar": {
                "type": "string",
                "description": (
                    "Arabic explanation (2–5 sentences, minimum 30 characters) "
                    "of why this maturity level was chosen.  Reference specific evidence."
                ),
            },
            "citations": {
                "type": "array",
                "description": (
                    "Zero to five citations from the provided evidence list.  "
                    "Do NOT fabricate chunk_ids — use the values shown verbatim "
                    "in the 'الأدلة المرفقة' section."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "chunk_id": {
                            "type": "string",
                            "description": (
                                "Must match one of the chunk_id values listed in the "
                                "evidence section verbatim."
                            ),
                        },
                        "page_number": {
                            "type": "integer",
                            "description": "1-indexed page number from the source file.",
                        },
                        "source_file": {
                            "type": "string",
                            "description": "Source filename, exactly as shown in the evidence.",
                        },
                        "quoted_text_ar": {
                            "type": "string",
                            "description": (
                                "Short Arabic quote (≤ 200 characters, hard cap 400) "
                                "from the chunk that supports the maturity verdict."
                            ),
                        },
                        "supports_level": {
                            "type": "integer",
                            "description": (
                                "Maturity level (0..5) that this citation supports. "
                                "May differ from the final maturity_level if the "
                                "evidence is partial."
                            ),
                        },
                    },
                    "required": ["chunk_id", "page_number", "source_file",
                                 "quoted_text_ar", "supports_level"],
                    "additionalProperties": False,
                },
            },
            "gaps_ar": {
                "type": "string",
                "description": (
                    "Arabic description of what evidence is missing to reach the "
                    "next maturity level.  Empty string if maturity_level is 5."
                ),
            },
            "needs_review": {
                "type": "boolean",
                "description": (
                    "True if the analyst should manually review this verdict "
                    "(e.g. confidence < 0.6, contradictory evidence, missing "
                    "required document, fewer than 3 citations)."
                ),
            },
        },
        "required": ["maturity_level", "confidence", "rationale_ar",
                     "citations", "gaps_ar", "needs_review"],
        "additionalProperties": False,
    },
}


@dataclass(slots=True)
class Citation:
    """One row destined for ndmo.t_ndmo_citations."""

    chunk_id: str
    page_number: int
    source_file: str
    quoted_text_ar: str
    supports_level: int | None = None


@dataclass(slots=True)
class AssessmentOutput:
    """Parsed result of one LLM assessment call."""

    maturity_level: int                     # 0..5
    confidence: float                       # 0..1
    rationale_ar: str
    citations: list[Citation] = field(default_factory=list)
    gaps_ar: str = ""
    needs_review: bool = False

    @classmethod
    def from_json_object(cls, obj: dict) -> "AssessmentOutput":
        # Range checks Python-side since strict-mode JSON Schema can't carry
        # min/max constraints.
        ml = int(obj["maturity_level"])
        if not 0 <= ml <= 5:
            raise ValueError(f"maturity_level out of range: {ml}")
        conf = float(obj["confidence"])
        if not 0.0 <= conf <= 1.0:
            raise ValueError(f"confidence out of range: {conf}")
        return cls(
            maturity_level=ml,
            confidence=conf,
            rationale_ar=str(obj["rationale_ar"]),
            citations=[
                Citation(
                    chunk_id=str(c["chunk_id"]),
                    page_number=int(c["page_number"]),
                    source_file=str(c["source_file"]),
                    quoted_text_ar=str(c["quoted_text_ar"]),
                    supports_level=int(c["supports_level"]) if c.get("supports_level") is not None else None,
                )
                for c in obj.get("citations", [])
            ],
            gaps_ar=str(obj.get("gaps_ar") or ""),
            needs_review=bool(obj.get("needs_review", False)),
        )

"""Dataclasses representing a row in each of the ndmo.* catalog tables.

The parsers produce these; the runner inserts them.  The dataclass layout
matches the columns in 023_ndmo_core.sql so the INSERT statements are
straightforward.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(slots=True)
class DomainRow:
    code: str
    name_ar: str
    name_en: str | None = None
    description_ar: str | None = None
    sort_order: int = 0


@dataclass(slots=True)
class ControlRow:
    domain_code: str
    code: str
    name_ar: str
    description_ar: str | None = None
    sort_order: int = 0


@dataclass(slots=True)
class SpecRow:
    control_code: str
    code: str
    name_ar: str
    description_ar: str | None = None
    priority: int = 0  # 1 / 2 / 3
    nca_conditional: bool = False
    maturity_levels: dict[str, Any] = field(default_factory=dict)
    required_elements: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: str | None = None
    search_query: str | None = None
    related_specs: list[str] = field(default_factory=list)
    issue_date: date | None = None
    raw_source: dict[str, Any] = field(default_factory=dict)
    sort_order: int = 0


@dataclass(slots=True)
class ParseReport:
    """Summary of one parser stage, surfaced in the seed-run audit row."""

    stage: str
    counts: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SeedBundle:
    """Everything one seed pass extracted, ready to be persisted."""

    domains: list[DomainRow] = field(default_factory=list)
    controls: list[ControlRow] = field(default_factory=list)
    specs: list[SpecRow] = field(default_factory=list)
    reports: list[ParseReport] = field(default_factory=list)

"""Explicit relationship types between two terms (BRD §6.2 / FR-017).

Matches ndmo.t_glossary_term_relations.relation_type.
"""

from __future__ import annotations

from enum import StrEnum


class GlossaryRelationType(StrEnum):
    SYNONYM = "synonym"
    RELATED = "related"
    PARENT_OF = "parent_of"
    CALCULATED_FROM = "calculated_from"

"""Whether a term is scoped to a single domain or shared across the org.

Matches ndmo.t_glossary_terms.term_type.  Enterprise terms (BRD §4.3) have
domain_id NULL and are approved by the Org Admin.
"""

from __future__ import annotations

from enum import StrEnum


class GlossaryTermType(StrEnum):
    DOMAIN = "domain"
    ENTERPRISE = "enterprise"

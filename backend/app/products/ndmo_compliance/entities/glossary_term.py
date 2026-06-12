"""GlossaryTerm entity — mirrors ndmo.t_glossary_terms.

Core business-term record (BRD §5.1).  domain_id is None for an Enterprise
term.  The dual-version pointers (published/pending) drive the edit-under-
review flow (WF-03): a published term stays live while an edit is pending.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.products.ndmo_compliance.enums.glossary_source import GlossaryTermSource
from app.products.ndmo_compliance.enums.glossary_status import GlossaryTermStatus
from app.products.ndmo_compliance.enums.glossary_term_type import GlossaryTermType


@dataclass(slots=True)
class GlossaryTerm:
    id: UUID
    tenant_id: int
    name_en: str
    status: GlossaryTermStatus
    term_type: GlossaryTermType
    source: GlossaryTermSource
    created_by: int
    version: int
    created_at: datetime
    updated_at: datetime
    domain_id: UUID | None = None
    name_ar: str | None = None
    definition_en: str | None = None
    definition_ar: str | None = None
    acronym: str | None = None
    examples: str | None = None
    business_rule: str | None = None
    owner_user_id: int | None = None
    steward_user_id: int | None = None
    published_version_id: UUID | None = None
    pending_version_id: UUID | None = None
    deprecation_reason: str | None = None
    replaced_by_term_id: UUID | None = None
    approved_at: datetime | None = None
    deprecated_at: datetime | None = None

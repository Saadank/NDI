"""GlossaryDomain entity — mirrors ndmo.t_glossary_domains.

A node in the org-specific, n-level domain tree (BRD §4).  parent_id is None
for a top-level domain.  ``steward_ids`` and ``term_count`` are not columns —
they are hydrated by the repository for tree/detail responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(slots=True)
class GlossaryDomain:
    id: UUID
    tenant_id: int
    name_en: str
    status: str
    created_by: int
    created_at: datetime
    updated_at: datetime
    parent_id: UUID | None = None
    name_ar: str | None = None
    description_en: str | None = None
    description_ar: str | None = None
    owner_user_id: int | None = None
    # Hydrated (not stored on this row):
    steward_ids: list[int] = field(default_factory=list)
    term_count: int = 0

"""Document entity — mirrors ndmo.t_ndmo_documents.

Cortex equivalent: ``entities/file.py``.  Three meaningful changes vs. the
cortex original:

  1. Primary key is a UUID (cortex used a SERIAL integer; UUID is the
     Datarix convention for tenant-scoped artefacts and avoids leaking
     row-count information across tenants via sequential IDs).
  2. ``tenant_id`` is a required field (cortex relied on a per-tenant DB
     schema; Datarix uses one schema with tenant_id columns).
  3. No ``user_id`` foreign key on the access path — we track who
     uploaded via ``uploaded_by``, then defer authorization to the
     product-role layer rather than per-file ACLs.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.products.ndmo_compliance.enums.document_status import DocumentStatus


@dataclass(slots=True)
class Document:
    id: UUID
    tenant_id: int
    file_name: str
    minio_key: str
    status: DocumentStatus
    uploaded_by: int
    uploaded_at: datetime
    cycle_id: int | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    page_count: int | None = None
    sha256: str | None = None
    processed_at: datetime | None = None

    @property
    def extension(self) -> str:
        """File extension (without dot), lowercase — used by the validator."""
        if "." not in self.file_name:
            return ""
        return self.file_name.rsplit(".", 1)[1].lower()

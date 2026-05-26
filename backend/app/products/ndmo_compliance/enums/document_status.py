"""Lifecycle status of an NDMO document.

Matches the CHECK constraint on ndmo.t_ndmo_documents.status in
023_ndmo_core.sql.  Direct port of cortex `enums/file_status.py` with the
NDMO-specific values.
"""

from __future__ import annotations

from enum import StrEnum


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"        # presigned PUT completed, awaiting scan
    SCANNING = "scanning"        # ClamAV in flight
    INFECTED = "infected"        # ClamAV positive — quarantined
    CLEAN = "clean"              # ClamAV negative — safe to process
    EXTRACTING = "extracting"    # Arabic OCR / PyMuPDF text extraction
    EMBEDDING = "embedding"      # chunked + vectors written to Qdrant
    READY = "ready"              # available to the assessment engine
    FAILED = "failed"            # unrecoverable error — see audit row

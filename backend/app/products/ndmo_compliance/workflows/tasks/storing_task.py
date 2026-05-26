"""Stage 2: storage — move scanned file to a canonical key + convert to PDF.

PORTED FROM:
  cortex-backend-main/tasks/storing_task.py

PORTING DIFF:
  cortex → NDMO
  - "clean" / "uploads" bucket names  -> BUCKET_CLEAN (single canonical bucket)
  - new_object_name = f"{file.id}.{file.extension}"
    becomes the canonical key      -> f"{tenant_id}/{document_id}/final.pdf"
  - cortex converts doc/docx/ppt/pptx/png/jpg/jpeg to PDF; NDMO scope is
    PDF/Word/Excel/PowerPoint — no image conversion (images aren't an
    accepted NDMO upload format per the requirement).  Excel is left as
    .xlsx (extraction pipeline handles xlsx natively via openpyxl).
  - LibreOffice search retains the cortex Linux/Mac/Windows fallbacks.
"""

from __future__ import annotations

import io
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from restate import RunOptions, WorkflowSharedContext
from restate.serde import BytesSerde

from app.products.ndmo_compliance.dependencies import current_tenant_id
from app.products.ndmo_compliance.enums.document_status import DocumentStatus
from app.products.ndmo_compliance.gateways.object_store_gateway import (
    BUCKET_CLEAN,
    NdmoObjectStoreGateway,
)
from app.products.ndmo_compliance.repositories.document_repository import DocumentRepository
from app.products.ndmo_compliance.workflows.restate_workflows import (
    ndmo_document_ingestion_workflow,
)

logger = logging.getLogger(__name__)

# Office formats LibreOffice converts to PDF.  Excel is excluded — we extract
# it via openpyxl downstream rather than converting.
_LIBREOFFICE_INPUTS: frozenset[str] = frozenset({"doc", "docx", "ppt", "pptx"})


@ndmo_document_ingestion_workflow.handler("Store")
async def store_task(ctx: WorkflowSharedContext, data: dict) -> str:
    """Move from the post-scan key to a canonical key, converting to PDF
    if the source is an Office format.  Returns the canonical key.
    """
    source_key: str = data["object_name"]
    document_id = data["document_id"]
    tenant_id: int = data["tenant_id"]
    current_tenant_id.set(tenant_id)

    documents = DocumentRepository()
    document = await ctx.run_typed(
        "fetch document row",
        documents.find_by_id,
        document_id=document_id, tenant_id=tenant_id,
    )

    storage = NdmoObjectStoreGateway()
    extension = document.extension
    canonical_key = f"{tenant_id}/{document_id}/final.{'pdf' if extension in _LIBREOFFICE_INPUTS or extension == 'pdf' else extension}"

    if extension in _LIBREOFFICE_INPUTS:
        # Pull, convert, push as PDF, drop the source.
        source_bytes = await ctx.run_typed(
            "download office doc",
            lambda: storage.get_object_bytes(bucket=BUCKET_CLEAN, key=source_key),
            RunOptions(serde=BytesSerde()),
        )
        pdf_bytes = await ctx.run_typed(
            "convert office -> pdf",
            _office_to_pdf,
            RunOptions(serde=BytesSerde()),
            content=source_bytes,
            extension=extension,
        )

        def _put_pdf_no_return() -> None:
            from io import BytesIO
            storage._platform.put_object(  # noqa: SLF001 — re-use platform put_object
                key=canonical_key,
                data=BytesIO(pdf_bytes),
                size=len(pdf_bytes),
                content_type="application/pdf",
                bucket=BUCKET_CLEAN,
            )

        await ctx.run_typed("store converted pdf", _put_pdf_no_return)
    else:
        # Just copy to the canonical key; same bucket.
        await ctx.run_typed(
            "copy to canonical key",
            storage.copy_object,
            source_bucket=BUCKET_CLEAN, source_key=source_key,
            destination_bucket=BUCKET_CLEAN, destination_key=canonical_key,
        )

    # Drop the random-name source so listings stay clean.
    if source_key != canonical_key:
        await ctx.run_typed(
            "remove staging key",
            storage.remove_object,
            bucket=BUCKET_CLEAN, key=source_key,
        )

    # Persist the canonical key so subsequent stages don't depend on the input arg.
    await ctx.run_typed(
        "persist canonical key",
        documents._execute,  # noqa: SLF001 — short, internal SQL
        """
        UPDATE ndmo.t_ndmo_documents
           SET minio_key = $1, status = $2
         WHERE id = $3 AND tenant_id = $4
        """,
        (canonical_key, DocumentStatus.CLEAN.value, document_id, tenant_id),
    )

    logger.info("Document %s stored at %s", document_id, canonical_key)
    return canonical_key


# ---------------------------------------------------------------------------
# LibreOffice conversion (sync helper; runs inside ctx.run_typed)
# ---------------------------------------------------------------------------


def _office_to_pdf(content: bytes, extension: str) -> bytes:
    """Single LibreOffice headless call that handles doc/docx/ppt/pptx."""
    with tempfile.TemporaryDirectory() as temp_dir:
        in_path = os.path.join(temp_dir, f"input.{extension}")
        with open(in_path, "wb") as f:
            f.write(content)

        soffice = _find_libreoffice()
        if not soffice:
            raise EnvironmentError(
                "LibreOffice not found.  Install it on the api container "
                "(apt-get install -y libreoffice) or set the soffice path."
            )

        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf",
             "--outdir", temp_dir, in_path],
            check=True,
            capture_output=True,
        )

        pdf_path = os.path.join(temp_dir, "input.pdf")
        with open(pdf_path, "rb") as f:
            return f.read()


def _find_libreoffice() -> str | None:
    """Return path to ``soffice``; ports the cortex platform discovery logic."""
    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\LibreOffice\program\soffice.exe",
            r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/Applications/LibreOffice.app/Contents/MacOS/soffice",
            os.path.expanduser("~/Applications/LibreOffice.app/Contents/MacOS/soffice"),
        ]
    else:  # Linux container
        candidates = [
            "/usr/bin/soffice",
            "/usr/bin/libreoffice",
            "/usr/local/bin/soffice",
            "/usr/local/bin/libreoffice",
            "/opt/libreoffice/program/soffice",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return shutil.which("soffice") or shutil.which("libreoffice")

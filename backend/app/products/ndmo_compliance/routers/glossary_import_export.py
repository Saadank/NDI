"""Bulk Import / Export endpoints for the Business Glossary (BRD §6.6, design H).

Mounted under ``/api/v1/products/ndmo-compliance/glossary``.
"""

from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.core.security import get_current_user
from app.products.ndmo_compliance.services.glossary_import_export_service import (
    GlossaryImportExportService,
    get_glossary_import_export_service,
)
from app.structures.auth_user import AuthUser

router = APIRouter(prefix="/glossary", tags=["ndmo-glossary-import-export"])

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class ExportCount(BaseModel):
    count: int


class RowResultModel(BaseModel):
    row: int
    term: str
    status: str
    message: str


class ImportSummaryModel(BaseModel):
    file_name: str
    batch_id: str
    imported: int
    warnings: int
    errors: int
    rows: list[RowResultModel]


class RollbackResult(BaseModel):
    deleted: int


def _xlsx_response(data: bytes, filename: str) -> StreamingResponse:
    return StreamingResponse(
        BytesIO(data),
        media_type=_XLSX,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/count", response_model=ExportCount)
async def export_count(
    scope: str = Query(default="all", pattern="^(all|my)$"),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryImportExportService = Depends(get_glossary_import_export_service),
):
    return ExportCount(count=await service.export_count(auth_user=auth_user, scope=scope))


@router.get("/export")
async def export_glossary(
    scope: str = Query(default="all", pattern="^(all|my)$"),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryImportExportService = Depends(get_glossary_import_export_service),
):
    data = await service.export_xlsx(auth_user=auth_user, scope=scope)
    return _xlsx_response(data, "business-glossary.xlsx")


@router.get("/import/template")
async def import_template(
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryImportExportService = Depends(get_glossary_import_export_service),
):
    return _xlsx_response(service.template_xlsx(), "glossary-import-template.xlsx")


@router.post("/import", response_model=ImportSummaryModel)
async def import_glossary(
    file: UploadFile = File(...),
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryImportExportService = Depends(get_glossary_import_export_service),
):
    contents = await file.read()
    summary = await service.import_xlsx(
        auth_user=auth_user, file_bytes=contents, file_name=file.filename or "import.xlsx"
    )
    return ImportSummaryModel(
        file_name=summary.file_name, batch_id=summary.batch_id,
        imported=summary.imported, warnings=summary.warnings, errors=summary.errors,
        rows=[RowResultModel(row=r.row, term=r.term, status=r.status, message=r.message) for r in summary.rows],
    )


@router.post("/import/{batch_id}/rollback", response_model=RollbackResult)
async def rollback_import(
    batch_id: UUID,
    auth_user: AuthUser = Depends(get_current_user),
    service: GlossaryImportExportService = Depends(get_glossary_import_export_service),
):
    return RollbackResult(deleted=await service.rollback(auth_user=auth_user, batch_id=batch_id))

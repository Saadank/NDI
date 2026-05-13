"""Excel import endpoints for the LLM-touching workflows (Step 6.4 →).

Sub-step landings:
- 6.4 — kind=glossary (no LLM, persist to t_dq_glossary_terms)
- 6.5 — kind=column_rules (sql_generation LLM purpose, proposals queue)
- 6.6 — kind=business_rules (column_match + sql_generation, easy/hard paths)
- 6.8 — POST /imports/{id}/rollback
"""
from io import BytesIO

from fastapi import APIRouter, Depends, Query, UploadFile, File, Form
from fastapi.responses import StreamingResponse

from app.core.security import get_current_user
from app.products.data_quality.ai.services.business_rule_ingest import (
    BusinessRuleIngestService, get_business_rule_ingest_service,
)
from app.products.data_quality.ai.services.column_rule_ingest import (
    ColumnRuleIngestService, get_column_rule_ingest_service,
)
from app.products.data_quality.ai.services.excel_parser import (
    write_business_rules_template, write_column_rules_template,
    write_glossary_template,
)
from app.products.data_quality.ai.services.glossary_ingest import (
    GlossaryIngestService, get_glossary_ingest_service,
)
from app.products.data_quality.ai.services.proposal_service import (
    ProposalService, get_proposal_service,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ValidationException

router = APIRouter(prefix="/imports", tags=["dq-imports"])


@router.post("")
async def upload_import(
    kind: str = Form(...),
    file: UploadFile = File(...),
    version_label: str | None = Form(default=None),
    auth_user: AuthUser = Depends(get_current_user),
    glossary_svc: GlossaryIngestService = Depends(get_glossary_ingest_service),
    column_rule_svc: ColumnRuleIngestService = Depends(get_column_rule_ingest_service),
    business_rule_svc: BusinessRuleIngestService = Depends(get_business_rule_ingest_service),
):
    """Upload an Excel file. ``kind`` selects which ingest pipeline runs:

    - ``glossary``       — Table 11. No LLM. Persists straight to
                           t_dq_glossary_terms.
    - ``column_rules``   — Table 13. LLM only for format_regex rows
                           with a blank parameter.
    - ``business_rules`` — Table 12. Easy path (1 LLM call) when
                           table+column supplied; hard path
                           (2 LLM calls — column_match + sql_generation)
                           when column blank.
    """
    if kind not in ("glossary", "column_rules", "business_rules"):
        raise ValidationException(
            "kind must be one of glossary / column_rules / business_rules"
        )
    contents = await file.read()
    filename = file.filename or f"upload.{kind}.xlsx"

    if kind == "glossary":
        return await glossary_svc.ingest(
            file_bytes=contents, filename=filename,
            version_label=version_label, auth_user=auth_user,
        )

    if kind == "column_rules":
        return await column_rule_svc.ingest(
            file_bytes=contents, filename=filename,
            version_label=version_label, auth_user=auth_user,
        )

    return await business_rule_svc.ingest(
        file_bytes=contents, filename=filename,
        version_label=version_label, auth_user=auth_user,
    )


@router.get("")
async def list_imports(
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    auth_user: AuthUser = Depends(get_current_user),
    glossary_svc: GlossaryIngestService = Depends(get_glossary_ingest_service),
):
    """List imports for the caller's tenant, newest first.
    Filters: ``kind`` (glossary / business_rules / column_rules),
    ``status`` (uploaded / parsing / ... / applied / error / rolled_back).
    """
    items = await glossary_svc.list_imports(
        kind=kind, status=status, auth_user=auth_user,
    )
    return {"items": items}


@router.get("/template/glossary")
async def download_glossary_template(
    _auth: AuthUser = Depends(get_current_user),
):
    """Download the Table-11 .xlsx template (headers + 2 example rows)."""
    buf = write_glossary_template(BytesIO())
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="glossary_template.xlsx"',
        },
    )


@router.get("/template/column_rules")
async def download_column_rules_template(
    _auth: AuthUser = Depends(get_current_user),
):
    """Download the Table-13 .xlsx template (headers + 3 example rows
    — one easy-path, one LLM hard-path, one no-parameter rule)."""
    buf = write_column_rules_template(BytesIO())
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="column_rules_template.xlsx"',
        },
    )


@router.get("/template/business_rules")
async def download_business_rules_template(
    _auth: AuthUser = Depends(get_current_user),
):
    """Download the Table-12 .xlsx template (headers + 3 example rows
    — easy path, hard path with blank column, unsupported cross-table)."""
    buf = write_business_rules_template(BytesIO())
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="business_rules_template.xlsx"',
        },
    )


@router.get("/{import_id}")
async def get_import(
    import_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    glossary_svc: GlossaryIngestService = Depends(get_glossary_ingest_service),
):
    """Single import: status, row/error counts, errors list, terms_count."""
    return await glossary_svc.get_import(import_id, auth_user)


@router.post("/{import_id}/rollback")
async def rollback_import(
    import_id: int,
    auth_user: AuthUser = Depends(get_current_user),
    proposal_svc: ProposalService = Depends(get_proposal_service),
):
    """Walk every approved proposal in this import in reverse and undo
    it. **Strict, all-or-nothing** — refuses with HTTP 200 + ok=False
    when any applied active_rule already has validator issues, so the
    caller can show a precise list of blockers to the reviewer.

    On success: returns ``{ok: true, reverted, proposals_marked, import}``
    with the import row flipped to ``status='rolled_back'``."""
    return await proposal_svc.rollback_import(import_id, auth_user)

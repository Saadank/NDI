"""Glossary bulk Import / Export (BRD §6.6 / FR-051-052, design H).

Export: approved terms → an Excel workbook (name EN/AR, definition EN/AR,
domain, owner, status, version, approved date).

Import: an Excel workbook → draft terms in the normal approval workflow.  Each
row is validated independently; valid rows become drafts tagged with a shared
import_batch_id so the whole batch is roll-back-able.  Rows are classified:
  * imported — created as a draft
  * warning  — created, but flagged (e.g. missing definition, duplicate name)
  * error    — not created (missing name, unknown/again unauthorised domain)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from io import BytesIO
from uuid import UUID, uuid4

from openpyxl import Workbook, load_workbook

from app.products.ndmo_compliance import glossary_permissions as perm
from app.products.ndmo_compliance.repositories.glossary_domain_repository import (
    GlossaryDomainRepository,
)
from app.products.ndmo_compliance.repositories.glossary_term_repository import (
    GlossaryTermRepository,
)
from app.products.ndmo_compliance.services.glossary_domain_service import (
    GlossaryDomainService,
)
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

_MAX_ROWS = 5000

# Export column order (FR-051).
_EXPORT_HEADERS = [
    "Term Name (EN)", "Term Name (AR)", "Definition (EN)", "Definition (AR)",
    "Acronym", "Domain", "Owner", "Term Type", "Status", "Version", "Approved At",
]

# Import template headers + header-alias resolution.
_IMPORT_HEADERS = [
    "Term Name (EN)", "Term Name (AR)", "Acronym", "Domain", "Term Type",
    "Definition (EN)", "Definition (AR)", "Examples", "Business Rule",
]
_ALIASES = {
    "name_en": {"term name (en)", "name en", "term name en", "name (en)"},
    "name_ar": {"term name (ar)", "name ar", "term name ar", "name (ar)"},
    "acronym": {"acronym", "abbreviation"},
    "domain": {"domain", "domain name"},
    "term_type": {"term type", "type"},
    "definition_en": {"definition (en)", "definition en", "definition"},
    "definition_ar": {"definition (ar)", "definition ar"},
    "examples": {"examples", "example"},
    "business_rule": {"business rule", "rule"},
}


@dataclass(slots=True)
class RowResult:
    row: int
    term: str
    status: str          # imported | warning | error
    message: str = ""


@dataclass(slots=True)
class ImportSummary:
    file_name: str
    batch_id: str
    imported: int
    warnings: int
    errors: int
    rows: list[RowResult] = field(default_factory=list)


class GlossaryImportExportService:
    def __init__(self) -> None:
        self._terms = GlossaryTermRepository()
        self._domains_repo = GlossaryDomainRepository()
        self._domains = GlossaryDomainService()

    # ---- export ---------------------------------------------------------

    async def _scope_domains(self, auth_user: AuthUser, scope: str) -> list[UUID] | None:
        if scope != "my":
            return None
        actor = await self._domains.resolve_actor(auth_user)
        if actor.is_org_admin:
            return None
        return list(actor.assigned_domain_ids()) or [UUID(int=0)]

    async def export_count(self, *, auth_user: AuthUser, scope: str) -> int:
        rows = await self._terms.list_approved_for_export(
            tenant_id=auth_user.tenant_id,
            domain_ids=await self._scope_domains(auth_user, scope),
        )
        return len(rows)

    async def export_xlsx(self, *, auth_user: AuthUser, scope: str) -> bytes:
        rows = await self._terms.list_approved_for_export(
            tenant_id=auth_user.tenant_id,
            domain_ids=await self._scope_domains(auth_user, scope),
        )
        users = await self._domains_repo.list_users(tenant_id=auth_user.tenant_id)
        name_of = {u["id"]: (f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip() or u["email"]) for u in users}

        wb = Workbook()
        ws = wb.active
        ws.title = "Glossary"
        ws.append(_EXPORT_HEADERS)
        for r in rows:
            ws.append([
                r["name_en"], r.get("name_ar"), r.get("definition_en"),
                r.get("definition_ar"), r.get("acronym"),
                r.get("domain_name") or "Enterprise", name_of.get(r.get("owner_user_id"), ""),
                r["term_type"], "approved", r["version"],
                r["approved_at"].strftime("%Y-%m-%d") if r.get("approved_at") else "",
            ])
        return _wb_bytes(wb)

    def template_xlsx(self) -> bytes:
        wb = Workbook()
        ws = wb.active
        ws.title = "Terms"
        ws.append(_IMPORT_HEADERS)
        ws.append([
            "Premium", "القسط", "PRM", "Underwriting", "domain",
            "The recurring amount paid to keep an insurance policy active.",
            "المبلغ المتكرر المدفوع للحفاظ على سريان وثيقة التأمين.",
            "Monthly premium, annual premium.", "",
        ])
        return _wb_bytes(wb)

    # ---- import ---------------------------------------------------------

    async def import_xlsx(
        self, *, auth_user: AuthUser, file_bytes: bytes, file_name: str
    ) -> ImportSummary:
        actor = await self._domains.resolve_actor(auth_user)
        perm.require(
            actor.is_org_admin or bool(actor.owned_domain_ids) or bool(actor.steward_domain_ids),
            "You need an authoring role to import terms.",
        )

        try:
            wb = load_workbook(BytesIO(file_bytes), read_only=True, data_only=True)
        except Exception as e:  # noqa: BLE001
            raise ValidationException(f"Could not read the Excel file: {e}")
        ws = wb.active

        rows_iter = ws.iter_rows(values_only=True)
        try:
            header = next(rows_iter)
        except StopIteration:
            raise ValidationException("The file is empty.")
        col = _resolve_headers(header)
        if "name_en" not in col:
            raise ValidationException("Missing required column: Term Name (EN).")

        domains = await self._domains_repo.list_all(
            tenant_id=auth_user.tenant_id, include_archived=False
        )
        domain_by_name = {d.name_en.strip().lower(): d for d in domains}

        batch_id = uuid4()
        results: list[RowResult] = []
        imported = warnings = errors = 0
        data_rows = list(rows_iter)
        if len(data_rows) > _MAX_ROWS:
            raise ValidationException(f"Too many rows ({len(data_rows)}). The limit is {_MAX_ROWS}.")

        for idx, raw in enumerate(data_rows, start=2):  # row 1 = header
            get = lambda key: _cell(raw, col.get(key))  # noqa: E731
            name_en = (get("name_en") or "").strip()
            if not name_en:
                continue  # blank line — skip silently
            term_type = (get("term_type") or "domain").strip().lower()
            if term_type not in ("domain", "enterprise"):
                term_type = "domain"

            # Resolve / authorise the target domain.
            domain_id: UUID | None = None
            if term_type == "enterprise":
                if not actor.is_org_admin:
                    errors += 1
                    results.append(RowResult(idx, name_en, "error", "Enterprise terms can only be imported by an Org Admin."))
                    continue
            else:
                dname = (get("domain") or "").strip().lower()
                dom = domain_by_name.get(dname)
                if not dom:
                    errors += 1
                    results.append(RowResult(idx, name_en, "error", f"Unknown domain: '{get('domain') or ''}'."))
                    continue
                if not perm.can_create_term(actor, dom.id, "domain"):
                    errors += 1
                    results.append(RowResult(idx, name_en, "error", f"You can't author in domain '{dom.name_en}'."))
                    continue
                domain_id = dom.id

            note = ""
            if not (get("definition_en") or "").strip():
                note = "Imported without an English definition."
            dup = await self._terms.find_duplicate(
                tenant_id=auth_user.tenant_id, domain_id=domain_id, name_en=name_en
            )
            if dup is not None:
                note = (note + " " if note else "") + "A term with this name already exists."

            await self._terms.create(
                tenant_id=auth_user.tenant_id, name_en=name_en,
                created_by=auth_user.user_id, domain_id=domain_id,
                term_type=term_type, source="manual",
                name_ar=(get("name_ar") or None), definition_en=(get("definition_en") or None),
                definition_ar=(get("definition_ar") or None), acronym=(get("acronym") or None),
                examples=(get("examples") or None), business_rule=(get("business_rule") or None),
                steward_user_id=auth_user.user_id, import_batch_id=batch_id,
            )
            if note:
                warnings += 1
                results.append(RowResult(idx, name_en, "warning", note.strip()))
            else:
                imported += 1
                results.append(RowResult(idx, name_en, "imported", "Created as a draft."))

        return ImportSummary(
            file_name=file_name, batch_id=str(batch_id),
            imported=imported, warnings=warnings, errors=errors, rows=results,
        )

    async def rollback(self, *, auth_user: AuthUser, batch_id: UUID) -> int:
        return await self._terms.delete_import_batch(
            tenant_id=auth_user.tenant_id, batch_id=batch_id
        )


def _wb_bytes(wb: Workbook) -> bytes:
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _resolve_headers(header_row: tuple) -> dict[str, int]:
    out: dict[str, int] = {}
    for i, cell in enumerate(header_row):
        if cell is None:
            continue
        norm = str(cell).strip().lower()
        for field_name, aliases in _ALIASES.items():
            if norm in aliases and field_name not in out:
                out[field_name] = i
    return out


def _cell(row: tuple, idx: int | None):
    if idx is None or idx >= len(row):
        return None
    v = row[idx]
    return str(v).strip() if v is not None else None


def get_glossary_import_export_service() -> GlossaryImportExportService:
    return GlossaryImportExportService()

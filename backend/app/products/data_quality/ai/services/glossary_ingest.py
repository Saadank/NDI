"""Glossary ingest — BRD Table 11.

Schema:
    term* | definition | synonyms (; or , separated) | language (en|ar|mixed|auto)

Lifecycle:
    uploaded -> parsing -> applied   (no LLM calls, no proposals queue)
    uploaded -> parsing -> error     (parse / per-row validation failed)

Why no proposals queue:
    Glossary terms are raw business terminology. They feed downstream
    LLM column-matching (Step 6.6) as additional context, but they
    don't themselves create concepts or rules. Reviewer mapping a term
    to an existing concept lands in a later sub-step.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone

from app.products.data_quality.ai.repositories.glossary_repository import (
    GlossaryRepository,
)
from app.products.data_quality.ai.repositories.import_repository import (
    ImportRepository,
)
from app.products.data_quality.ai.services.excel_parser import (
    ColumnSpec, ParsedRow, parse_excel, split_list_cell,
)
from app.products.data_quality.permissions import can_use_dq, require
from app.structures.auth_user import AuthUser
from app.utils.exceptions import ResourceNotFoundException, ValidationException

logger = logging.getLogger(__name__)

_VALID_LANGUAGES = {"en", "ar", "mixed", "auto", "unknown"}

_COLUMNS = [
    ColumnSpec("term",       required=True,  aliases=("business term", "name")),
    ColumnSpec("definition", required=False, aliases=("description",)),
    ColumnSpec("synonyms",   required=False, aliases=("aliases",)),
    ColumnSpec("language",   required=False, aliases=("lang",)),
]


def _validate_row(row: ParsedRow) -> None:
    """Per-row business validation beyond what ColumnSpec.required handles."""
    term = row.values.get("term")
    if term is not None:
        if len(str(term)) > 255:
            row.errors.append("term too long (max 255 chars)")
    lang = row.values.get("language")
    if lang is not None:
        lang_str = str(lang).lower().strip()
        if lang_str not in _VALID_LANGUAGES:
            row.errors.append(
                f"language must be one of {sorted(_VALID_LANGUAGES)}; got {lang!r}"
            )
        row.values["language"] = lang_str
    # Normalize synonyms list early — keeps the persistence layer dumb.
    row.values["synonyms"] = split_list_cell(row.values.get("synonyms"))


class GlossaryIngestService:
    """Two-phase ingest: open an import row, parse, persist (or mark error).

    Idempotent on (tenant_id, file_hash): a re-upload of the exact same
    bytes returns the existing import without re-running parsing."""

    def __init__(self) -> None:
        self.imports = ImportRepository()
        self.glossary = GlossaryRepository()

    async def ingest(
        self, *, file_bytes: bytes, filename: str,
        version_label: str | None, auth_user: AuthUser,
    ) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        if not file_bytes:
            raise ValidationException("Empty file")
        if len(file_bytes) > 10 * 1024 * 1024:
            raise ValidationException("File too large (max 10 MB)")

        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # Idempotency: same hash → return existing import as-is.
        existing = await self.imports.find_by_hash(auth_user.tenant_id, file_hash)
        if existing:
            return {
                "detail": "Duplicate upload — same bytes already imported",
                "import": existing,
            }

        # Open an `uploaded` row first so we have an id to attach
        # per-row errors and the persisted glossary entries to.
        imp = await self.imports.insert(
            tenant_id=auth_user.tenant_id, uploader_id=auth_user.user_id,
            kind="glossary", filename=filename[:500], file_hash=file_hash,
            version_label=version_label,
        )
        import_id = imp["id"]

        # Move to `parsing` state, parse, validate.
        await self.imports.update_status(
            import_id, auth_user.tenant_id, status="parsing",
        )
        parse = parse_excel(
            file_bytes, _COLUMNS, row_validators=[_validate_row],
        )

        if parse.file_errors and not parse.rows:
            # Whole-file failure — nothing to apply.
            imp_final = await self.imports.update_status(
                import_id, auth_user.tenant_id, status="error",
                row_count=0, error_count=parse.error_count,
                errors=parse.to_error_jsonb(),
            )
            return {"detail": "Parse failed", "import": imp_final}

        # Persist only the rows that passed per-row validation. Rows with
        # errors stay in the error report so the user can fix the file
        # and re-upload (a re-upload with the same bytes is idempotent;
        # they'll get a new file_hash if they edit even one cell).
        ok_rows = [
            {
                "term": r.values["term"],
                "definition": r.values.get("definition"),
                "synonyms": r.values.get("synonyms") or [],
                "language": r.values.get("language"),
            }
            for r in parse.ok_rows
        ]
        inserted = await self.glossary.insert_batch(
            tenant_id=auth_user.tenant_id, import_id=import_id, rows=ok_rows,
        )

        # Glossary has no LLM phase, so `applied` is the terminal state
        # straight out of parsing. If any rows had errors, we still apply
        # the good ones and keep the import in `applied` with errors
        # populated — the user reviews and decides whether to re-upload.
        imp_final = await self.imports.update_status(
            import_id, auth_user.tenant_id, status="applied",
            row_count=inserted, error_count=parse.error_count,
            errors=parse.to_error_jsonb() if parse.error_count else None,
            applied_at=datetime.now(timezone.utc),
        )
        return {
            "detail": (
                f"Glossary imported: {inserted} term(s) persisted"
                + (f", {parse.error_count} row(s) had errors" if parse.error_count else "")
            ),
            "import": imp_final,
        }

    async def list_imports(
        self, *, kind: str | None, status: str | None, auth_user: AuthUser,
    ) -> list[dict]:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        return await self.imports.list_for_tenant(
            auth_user.tenant_id, kind=kind, status=status,
        )

    async def get_import(self, import_id: int, auth_user: AuthUser) -> dict:
        require(can_use_dq(auth_user), "Data Quality is not available for this account")
        row = await self.imports.find_by_id(import_id, auth_user.tenant_id)
        if not row:
            raise ResourceNotFoundException("Import not found")
        # Attach term count for convenience — saves a second roundtrip.
        terms = await self.glossary.list_for_import(import_id, auth_user.tenant_id)
        return {**row, "terms_count": len(terms)}


def get_glossary_ingest_service() -> GlossaryIngestService:
    return GlossaryIngestService()

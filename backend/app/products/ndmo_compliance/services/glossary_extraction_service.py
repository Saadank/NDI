"""Glossary DB-extraction service (BRD §6.4 / WF-05).

Bootstraps the glossary from a connected source database.  Reads schema /
table / column **metadata only** — never data values (FR-031), consistent with
the Data Quality product's privacy posture.

Flow:
  * ``scan``: build a DbConnectorGateway from a stored connection, introspect
    its schema, and create a candidate term per column (name inferred from the
    column name).  Optionally drafts AI definitions in the background.
  * ``list_candidates`` / ``assign`` / ``dismiss``: manage the review queue.
  * ``accept``: promote a candidate to a draft term in the normal workflow,
    with case-insensitive duplicate detection (FR-036).

Permissions: scanning is Org-Admin / Data-Owner only (FR-030).  Accepting into
a domain requires authoring rights there (owner / steward / admin).
"""

from __future__ import annotations

import asyncio
import logging
import re
from uuid import UUID

from app.gateways.db_connector_gateway import DbConnectorGateway
from app.products.data_sharing.repositories.connection_repository import (
    ConnectionRepository,
)
from app.products.ndmo_compliance import glossary_permissions as perm
from app.products.ndmo_compliance.ai.client import get_ndmo_llm_client
from app.products.ndmo_compliance.repositories.glossary_candidate_repository import (
    GlossaryCandidateRepository,
)
from app.products.ndmo_compliance.repositories.glossary_llm_repository import (
    GlossaryLlmRepository,
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

_DRAFT_BATCH = 1000         # safety bound per drafting run
_DRAFT_SYSTEM = (
    "You are a data-governance assistant. Given a database column, write a "
    "concise (1–2 sentence) business definition of what the term means in "
    "business language. Define the business meaning only — do not describe the "
    "data type or invent specific values. Return only the definition text."
)

# Keep references to fire-and-forget background tasks so they aren't GC'd.
_BG_TASKS: set[asyncio.Task] = set()
# Which tenants currently have a drafting run in flight (in-memory).  Resets on
# process restart — which is the point: after a restart the flag clears, the UI
# sees active=False with remaining>0, and the user resumes with one click.
_DRAFTING_ACTIVE: set[int] = set()


def _infer_name(column: str) -> str:
    """snake_case / camelCase / kebab → 'Readable English' (BRD FR-032)."""
    s = re.sub(r"(?<!^)(?=[A-Z])", " ", column)      # camelCase → spaces
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    # Title-case but keep short all-caps tokens (ID, KPI) uppercase.
    return " ".join(
        w.upper() if len(w) <= 3 and w.isupper() else w.capitalize()
        for w in s.split()
    ) or column


class GlossaryExtractionService:
    def __init__(self) -> None:
        self._candidates = GlossaryCandidateRepository()
        self._terms = GlossaryTermRepository()
        self._domains = GlossaryDomainService()
        self._connections = ConnectionRepository()
        self._llm_audit = GlossaryLlmRepository()

    # ---- connections ----------------------------------------------------

    async def list_connections(self, *, auth_user: AuthUser) -> list[dict]:
        # Read the tenant's connections directly (the glossary has its own
        # permission model — admin/owner can scan — rather than DS's connection-
        # admin gate).  Strip the stored password before returning.
        rows = await self._connections.find_by_tenant(auth_user.tenant_id)
        return [{k: v for k, v in r.items() if k != "password_encrypted"} for r in rows]

    # ---- scan -----------------------------------------------------------

    async def scan(
        self, *, auth_user: AuthUser, connection_id: UUID, ai_draft: bool
    ) -> dict:
        actor = await self._domains.resolve_actor(auth_user)
        perm.require(
            actor.is_org_admin or bool(actor.owned_domain_ids),
            "Only an Org Admin or a Data Owner can run a DB extraction.",
        )

        conn = await self._connections.find_by_id(connection_id, auth_user.tenant_id)
        gateway = DbConnectorGateway(
            db_type=conn["db_type"], username=conn["username"],
            password=conn["password_encrypted"], host=conn["host"],
            port=str(conn["port"]), database=conn.get("database") or "",
        )
        result = await gateway.list_schemas()
        if not result.success:
            raise ValidationException(f"Could not read schema: {result.error}")

        schema_label = conn.get("database") or "public"
        existing = {
            (r["schema_name"], r["table_name"], r["column_name"])
            for r in await self._candidates.list_candidates(
                tenant_id=auth_user.tenant_id, status="pending"
            )
        }
        rows: list[dict] = []
        total_columns = 0
        for table, info in (result.data or {}).items():
            for column in (info.get("columns") or {}):
                total_columns += 1
                key = (schema_label, table, column)
                if key in existing:
                    continue
                rows.append({
                    "schema_name": schema_label,
                    "table_name": table,
                    "column_name": column,
                    "inferred_name_en": _infer_name(column),
                })

        created = await self._candidates.bulk_create(
            tenant_id=auth_user.tenant_id, connection_id=connection_id, rows=rows
        )

        if ai_draft and created:
            await self.start_drafting(auth_user=auth_user)

        return {
            "created": len(created),
            "skipped_existing": total_columns - len(rows),
            "ai_drafting": bool(ai_draft and created),
            "tables_scanned": len(result.data or {}),
        }

    # ---- queue management ----------------------------------------------

    async def list_candidates(
        self, *, auth_user: AuthUser, status: str | None = "pending",
        schema: str | None = None, table: str | None = None,
        domain_id: UUID | None = None,
    ) -> list[dict]:
        return await self._candidates.list_candidates(
            tenant_id=auth_user.tenant_id, status=status, schema=schema,
            table=table, domain_id=domain_id,
        )

    async def assign(
        self, *, auth_user: AuthUser, candidate_id: UUID,
        domain_id: UUID | None, user_id: int | None,
    ) -> dict:
        actor = await self._domains.resolve_actor(auth_user)
        if domain_id is not None:
            perm.require(
                perm.can_create_term(actor, domain_id, "domain"),
                "You can only assign candidates to a domain you author in.",
            )
        return await self._candidates.assign(
            candidate_id=candidate_id, tenant_id=auth_user.tenant_id,
            domain_id=domain_id, user_id=user_id,
        )

    async def dismiss(
        self, *, auth_user: AuthUser, candidate_id: UUID, reason: str | None
    ) -> None:
        actor = await self._domains.resolve_actor(auth_user)
        perm.require(
            actor.effective_role != "glossary_viewer",
            "You don't have permission to dismiss candidates.",
        )
        await self._candidates.mark_dismissed(
            candidate_id=candidate_id, tenant_id=auth_user.tenant_id, reason=reason
        )

    async def clear_pending(
        self, *, auth_user: AuthUser, table: str | None = None
    ) -> int:
        actor = await self._domains.resolve_actor(auth_user)
        perm.require(
            actor.effective_role != "glossary_viewer",
            "You don't have permission to clear candidates.",
        )
        return await self._candidates.dismiss_all_pending(
            tenant_id=auth_user.tenant_id, table=table, reason="Cleared from queue",
        )

    async def accept(
        self, *, auth_user: AuthUser, candidate_id: UUID,
        domain_id: UUID | None, force: bool = False,
    ) -> dict:
        actor = await self._domains.resolve_actor(auth_user)
        cand = await self._candidates.find_by_id(
            candidate_id=candidate_id, tenant_id=auth_user.tenant_id
        )
        target_domain = domain_id or cand["assigned_domain_id"]
        if target_domain is None:
            raise ValidationException("Select a domain for this term before accepting.")
        perm.require(
            perm.can_create_term(actor, target_domain, "domain"),
            "You can only accept candidates into a domain you author in.",
        )

        # Duplicate detection (FR-036) — case-insensitive in the same domain.
        dup = await self._terms.find_duplicate(
            tenant_id=auth_user.tenant_id, domain_id=target_domain,
            name_en=cand["inferred_name_en"],
        )
        if dup is not None and not force:
            return {
                "accepted": False, "duplicate": True,
                "existing_term_id": str(dup.id), "existing_name_en": dup.name_en,
            }

        term = await self._terms.create(
            tenant_id=auth_user.tenant_id, name_en=cand["inferred_name_en"],
            created_by=auth_user.user_id, domain_id=target_domain,
            term_type="domain", source="db_extracted",
            definition_en=cand.get("ai_draft_definition"),
            steward_user_id=auth_user.user_id,
        )
        await self._candidates.mark_accepted(
            candidate_id=candidate_id, tenant_id=auth_user.tenant_id,
            promoted_term_id=term.id, domain_id=target_domain,
        )
        return {"accepted": True, "duplicate": False, "term_id": str(term.id)}

    # ---- AI drafting (resumable, on-demand) -----------------------------

    async def drafting_status(self, *, auth_user: AuthUser) -> dict:
        counts = await self._candidates.draft_counts(tenant_id=auth_user.tenant_id)
        remaining = counts["total"] - counts["drafted"]
        return {
            "total": counts["total"],
            "drafted": counts["drafted"],
            "remaining": remaining,
            "active": auth_user.tenant_id in _DRAFTING_ACTIVE,
            "llm_available": get_ndmo_llm_client() is not None,
        }

    async def start_drafting(self, *, auth_user: AuthUser) -> dict:
        """Kick a background run that drafts every still-undrafted pending
        candidate.  Idempotent — does nothing if a run is already active or the
        LLM is unavailable.  Resumable — re-querying each run means it picks up
        where an interrupted run stopped."""
        tenant_id = auth_user.tenant_id
        if get_ndmo_llm_client() is not None and tenant_id not in _DRAFTING_ACTIVE:
            counts = await self._candidates.draft_counts(tenant_id=tenant_id)
            if counts["total"] - counts["drafted"] > 0:
                _DRAFTING_ACTIVE.add(tenant_id)
                self._spawn_bg(self._draft_pending(tenant_id))
        return await self.drafting_status(auth_user=auth_user)

    def _spawn_bg(self, coro) -> None:
        task = asyncio.create_task(coro)
        _BG_TASKS.add(task)
        task.add_done_callback(_BG_TASKS.discard)

    async def _draft_pending(self, tenant_id: int) -> None:
        client = get_ndmo_llm_client()
        try:
            if client is None:
                return
            candidates = await self._candidates.list_pending_undrafted(
                tenant_id=tenant_id, limit=_DRAFT_BATCH
            )
            for cand in candidates:
                user = (
                    f"Column: {cand['column_name']}\n"
                    f"Table: {cand['table_name']}\n"
                    f"Inferred term: {cand['inferred_name_en']}\n\n"
                    "Write the business definition."
                )
                try:
                    res = await client.call(system=_DRAFT_SYSTEM, user=user, json_mode=False)
                    if res.success and res.text.strip():
                        await self._candidates.set_ai_definition(
                            candidate_id=cand["id"], tenant_id=tenant_id,
                            definition=res.text.strip(),
                        )
                    await self._llm_audit.record(
                        tenant_id=tenant_id, purpose="draft",
                        input_hash=res.prompt_hash, output_hash=res.response_hash,
                        tokens_used=res.total_tokens, latency_ms=res.latency_ms,
                        success=bool(res.success and res.text.strip()), term_id=None,
                    )
                except Exception as e:  # noqa: BLE001 — best-effort, keep going
                    logger.warning("candidate AI draft failed for %s: %s", cand["id"], e)
        finally:
            _DRAFTING_ACTIVE.discard(tenant_id)


def get_glossary_extraction_service() -> GlossaryExtractionService:
    return GlossaryExtractionService()

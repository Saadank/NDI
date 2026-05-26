"""FastAPI dependency + tenant ContextVar for NDMO Compliance.

Mirrors `data_quality/dependencies.py` but adds a `current_tenant_id`
ContextVar that the Restate workflow handlers set at the top of each
stage.  This is the cortex pattern (`dependencies.current_tenant_id`)
ported in.  HTTP request handlers still rely on the explicit
``AuthUser.tenant_id`` plumbing from the platform layer; the ContextVar
exists for background work where a request scope isn't available.
"""

from __future__ import annotations

from contextvars import ContextVar

from app.products.data_sharing.dependencies import require_product

# Backend slug stays as 'ndmo' (decision locked in Phase 1 — no DB migration,
# no enum change).  User-facing URL is /ndmo-compliance.
require_ndmo_compliance = require_product("ndmo")


# Background-task tenant scope.  Set by every Restate handler at entry; the
# repositories still take tenant_id explicitly, but having the ContextVar
# means downstream helpers (extraction, embedding, chunker) can read it
# without re-threading it through every call signature.
current_tenant_id: ContextVar[int | None] = ContextVar(
    "ndmo_current_tenant_id", default=None
)

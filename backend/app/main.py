import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.core.config import get_settings
from app.core.database import init_pool, close_pool
from app.utils.exceptions import BaseAppException

# Platform Core routers
from app.platform.routers import auth, users, invitations, tenants, products, audit, groups, holidays, metrics

# Product: Data Sharing
from app.products.data_sharing.dependencies import require_data_sharing
from app.products.data_sharing.routers import (
    share_requests, approvals, files, notifications,
    workflows, connections, schemas, structured,
    external_recipients, pickup,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


settings = get_settings()

app = FastAPI(
    title="Data Management Platform API",
    version="1.0.0",
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
    lifespan=lifespan,
)


# CORS — allow frontend to call API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        settings.FRONTEND_URL,
        settings.FRONTEND_BASE_URL,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# Platform Core — /api/v1/platform/...
for r in [auth, users, invitations, tenants, products, audit, groups, holidays, metrics]:
    app.include_router(r.router, prefix="/api/v1/platform")

# Product: Data Sharing — /api/v1/products/data-sharing/...
# Router-level dependency ensures every call is blocked (403) if the caller's tenant
# does not have the data_sharing product enabled in t_tenant_products.
for r in [share_requests, approvals, files, notifications,
          workflows, connections, schemas, structured, external_recipients]:
    app.include_router(
        r.router,
        prefix="/api/v1/products/data-sharing",
        dependencies=[Depends(require_data_sharing)],
    )

# Public pickup portal — /api/v1/pickup/... (NO auth middleware, NO product gate)
app.include_router(pickup.router, prefix="/api/v1")

# Future products register here — zero changes to Platform Core needed
# from app.products.data_quality.routers import profiling, quality_rules
# app.include_router(profiling.router, prefix="/api/v1/products/data-quality")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}


# Dev-only: serve the standalone pickup portal page for magic-link URLs.
# Production should serve /pickup/{token} via nginx routing to the static file.
_PICKUP_HTML_CANDIDATES = ["/frontend/pickup.html", "frontend/pickup.html", "../frontend/pickup.html"]
_ACCEPT_INVITE_HTML_CANDIDATES = [
    "/frontend/accept-invitation.html",
    "frontend/accept-invitation.html",
    "../frontend/accept-invitation.html",
]


def _resolve_static(candidates: list[str]) -> str | None:
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


@app.get("/pickup/{token}")
async def pickup_page(token: str):
    path = _resolve_static(_PICKUP_HTML_CANDIDATES)
    if not path:
        return JSONResponse(status_code=404, content={"detail": "pickup.html not found"})
    return FileResponse(path, media_type="text/html")


@app.get("/accept-invitation")
async def accept_invitation_page():
    path = _resolve_static(_ACCEPT_INVITE_HTML_CANDIDATES)
    if not path:
        return JSONResponse(status_code=404, content={"detail": "accept-invitation.html not found"})
    return FileResponse(path, media_type="text/html")

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.database import init_pool, close_pool
from app.utils.exceptions import BaseAppException

# Platform Core routers
from app.platform.routers import auth, users, invitations, tenants, products, audit

# Product: Data Sharing
from app.products.data_sharing.routers import (
    share_requests, approvals, files, notifications,
    workflows, connections, schemas, glossary, dsa, breaches, dsr,
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


@app.exception_handler(BaseAppException)
async def app_exception_handler(request: Request, exc: BaseAppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.message})


# Platform Core — /api/v1/platform/...
for r in [auth, users, invitations, tenants, products, audit]:
    app.include_router(r.router, prefix="/api/v1/platform")

# Product: Data Sharing — /api/v1/products/data-sharing/...
for r in [share_requests, approvals, files, notifications,
          workflows, connections, schemas, glossary, dsa, breaches, dsr]:
    app.include_router(r.router, prefix="/api/v1/products/data-sharing")

# Future products register here — zero changes to Platform Core needed
# from app.products.data_quality.routers import profiling, quality_rules
# app.include_router(profiling.router, prefix="/api/v1/products/data-quality")


@app.get("/health")
async def health():
    return {"status": "ok", "env": settings.APP_ENV}

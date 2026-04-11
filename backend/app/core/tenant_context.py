from contextvars import ContextVar

from app.utils.exceptions import ForbiddenException

current_tenant_id: ContextVar[int | None] = ContextVar("current_tenant_id", default=None)


def get_current_tenant_id() -> int:
    tenant_id = current_tenant_id.get()
    if tenant_id is None:
        raise ForbiddenException("Tenant context is not set")
    return tenant_id

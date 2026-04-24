from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.security import get_current_user
from app.platform.enums.platform_role import PlatformRole
from app.structures.auth_user import AuthUser
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.exceptions import ForbiddenException

router = APIRouter(prefix="/holidays", tags=["holidays"])

_ADMIN = {PlatformRole.PLATFORM_ADMIN, PlatformRole.ORG_ADMIN}


class HolidayBody(BaseModel):
    holiday_date: date
    name: str = Field(..., min_length=1)
    name_ar: str | None = None


class _HolidayRepo(PostgresqlAsyncRepository):

    async def list_for_tenant(self, tenant_id: int, year: int | None = None) -> list[dict]:
        if year is None:
            return await self._fetch_all(
                "SELECT * FROM t_business_holidays WHERE tenant_id = $1 ORDER BY holiday_date",
                (tenant_id,),
            )
        return await self._fetch_all(
            "SELECT * FROM t_business_holidays WHERE tenant_id = $1 "
            "AND EXTRACT(YEAR FROM holiday_date) = $2 ORDER BY holiday_date",
            (tenant_id, year),
        )

    async def upsert(self, tenant_id: int, holiday_date: date, name: str,
                    name_ar: str | None, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_business_holidays (tenant_id, holiday_date, name, name_ar, created_by)
               VALUES ($1, $2, $3, $4, $5)
               ON CONFLICT (tenant_id, holiday_date)
               DO UPDATE SET name = EXCLUDED.name, name_ar = EXCLUDED.name_ar
               RETURNING *""",
            (tenant_id, holiday_date, name, name_ar, created_by),
        )

    async def delete(self, tenant_id: int, holiday_id: int) -> str:
        return await self._execute(
            "DELETE FROM t_business_holidays WHERE id = $1 AND tenant_id = $2",
            (holiday_id, tenant_id),
        )


def _require_admin(auth_user: AuthUser) -> None:
    if auth_user.platform_role not in _ADMIN:
        raise ForbiddenException("Only admins can manage holidays")


@router.get("/")
async def list_holidays(
    year: int | None = None,
    auth_user: AuthUser = Depends(get_current_user),
):
    return await _HolidayRepo().list_for_tenant(auth_user.tenant_id, year)


@router.post("/")
async def upsert_holiday(
    body: HolidayBody,
    auth_user: AuthUser = Depends(get_current_user),
):
    _require_admin(auth_user)
    return await _HolidayRepo().upsert(
        auth_user.tenant_id, body.holiday_date, body.name, body.name_ar, auth_user.user_id,
    )


@router.delete("/{holiday_id}")
async def delete_holiday(
    holiday_id: int,
    auth_user: AuthUser = Depends(get_current_user),
):
    _require_admin(auth_user)
    await _HolidayRepo().delete(auth_user.tenant_id, holiday_id)
    return {"deleted": holiday_id}

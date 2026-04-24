"""Saudi business-calendar helpers used for SLA calculations (BRD §4.3).

Working week: Sunday (weekday 6) through Thursday (weekday 3).
Non-working days: Friday (4) and Saturday (5), plus any date in
t_business_holidays for the tenant.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.timezone import RIYADH_TZ, now

# Python's date.weekday(): Monday=0 ... Sunday=6.
_WEEKEND = {4, 5}  # Friday, Saturday


def is_weekend(d: date) -> bool:
    return d.weekday() in _WEEKEND


def _as_riyadh_date(moment: datetime) -> date:
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=RIYADH_TZ)
    return moment.astimezone(RIYADH_TZ).date()


class BusinessCalendar(PostgresqlAsyncRepository):
    """Tenant-scoped business-day calculator.

    Holidays are cached per-instance so a single SLA computation doesn't issue
    one query per step. Re-instantiate for a fresh read of holidays.
    """

    def __init__(self, tenant_id: int) -> None:
        super().__init__()
        self.tenant_id = tenant_id
        self._holidays: set[date] | None = None

    async def _load_holidays(self) -> set[date]:
        if self._holidays is None:
            rows = await self._fetch_all(
                "SELECT holiday_date FROM t_business_holidays WHERE tenant_id = $1",
                (self.tenant_id,),
            )
            self._holidays = {r["holiday_date"] for r in rows}
        return self._holidays

    async def is_working_day(self, d: date) -> bool:
        if is_weekend(d):
            return False
        holidays = await self._load_holidays()
        return d not in holidays

    async def add_business_days(
        self, start: datetime, business_days: int,
    ) -> datetime:
        """Return `start` advanced by `business_days` working days.

        The start moment's time-of-day is preserved. A zero or negative value
        returns `start` unchanged.
        """
        if business_days <= 0:
            return start

        current_date = _as_riyadh_date(start)
        remaining = business_days
        # Consume the rest of today only if today is a working day. This matches
        # BRD §4.3: "Request submitted on a Friday evening — SLA clock starts
        # next business day (Sunday)." Same logic applies mid-week.
        while remaining > 0:
            current_date += timedelta(days=1)
            if await self.is_working_day(current_date):
                remaining -= 1

        # Preserve the start's wall-clock time, in Riyadh tz, on the target date.
        moment_local = (
            start.astimezone(RIYADH_TZ)
            if start.tzinfo else start.replace(tzinfo=RIYADH_TZ)
        )
        return datetime(
            year=current_date.year,
            month=current_date.month,
            day=current_date.day,
            hour=moment_local.hour,
            minute=moment_local.minute,
            second=moment_local.second,
            microsecond=moment_local.microsecond,
            tzinfo=RIYADH_TZ,
        )

    async def working_days_between(self, start: datetime, end: datetime) -> int:
        """Count full working days in `[start, end)` (used by escalation ladder)."""
        if end <= start:
            return 0
        start_d = _as_riyadh_date(start)
        end_d = _as_riyadh_date(end)
        count = 0
        cursor = start_d
        while cursor < end_d:
            if await self.is_working_day(cursor):
                count += 1
            cursor += timedelta(days=1)
        return count


async def business_deadline(
    tenant_id: int, start: datetime | None, business_days: int | None,
) -> datetime | None:
    """Convenience wrapper used by the workflow engine."""
    if not business_days:
        return None
    cal = BusinessCalendar(tenant_id)
    return await cal.add_business_days(start or now(), business_days)

from datetime import datetime
from zoneinfo import ZoneInfo

RIYADH_TZ = ZoneInfo("Asia/Riyadh")


def now() -> datetime:
    return datetime.now(RIYADH_TZ)

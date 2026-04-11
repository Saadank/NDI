import asyncio
import logging

from app.core.config import get_settings
from app.core.database import init_pool, close_pool
from app.products.data_sharing.workers.expiry_worker import run_expiry_check
from app.products.data_sharing.workers.sla_worker import run_sla_check
from app.products.data_sharing.workers.notification_worker import run_notification_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


async def periodic(func, interval_minutes: int) -> None:
    while True:
        try:
            await func()
        except Exception as e:
            logger.error(f"Worker {func.__name__} error: {e}")
        await asyncio.sleep(interval_minutes * 60)


async def main() -> None:
    settings = get_settings()
    await init_pool()
    logger.info("Workers started")

    try:
        await asyncio.gather(
            periodic(run_expiry_check, settings.WORKER_EXPIRY_CHECK_INTERVAL_MINUTES),
            periodic(run_sla_check, settings.WORKER_SLA_CHECK_INTERVAL_MINUTES),
            periodic(run_notification_worker, settings.WORKER_NOTIFICATION_INTERVAL_MINUTES),
        )
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())

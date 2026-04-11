import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import asyncpg
from asyncpg import Connection, Pool

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_pool: Pool | None = None


async def init_pool() -> Pool:
    global _pool
    if _pool is not None:
        return _pool

    settings = get_settings()
    logger.info("Initializing database connection pool")
    _pool = await asyncpg.create_pool(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
        min_size=5,
        max_size=20,
        command_timeout=60,
    )
    logger.info("Database connection pool initialized")
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool:
        logger.info("Closing database connection pool")
        await _pool.close()
        _pool = None


async def get_pool() -> Pool:
    global _pool
    if _pool is None:
        await init_pool()
    return _pool


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[Connection, None]:
    pool = await get_pool()
    connection = await pool.acquire()
    try:
        await connection.execute("SET timezone TO 'Asia/Riyadh'")
        yield connection
    finally:
        await pool.release(connection)

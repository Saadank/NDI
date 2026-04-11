from abc import ABC
from contextlib import asynccontextmanager
import logging

from asyncpg import Connection, PostgresError

from app.core.database import get_db_connection
from app.utils.exceptions import ResourceNotFoundException


logger = logging.getLogger(__name__)


class PostgresqlAsyncRepository(ABC):

    async def _fetch_value(self, query: str, args: tuple = (), connection: Connection = None):
        try:
            async with self._get_connection(connection) as conn:
                return await conn.fetchval(query, *args)
        except PostgresError as e:
            logger.error(f"Database error fetching value: {e}")
            raise Exception(f"Failed to fetch value: {e}") from e

    async def _fetch_row(self, query: str, args: tuple = (), connection: Connection = None):
        try:
            async with self._get_connection(connection) as conn:
                row = await conn.fetchrow(query, *args)
                if row is None:
                    raise ResourceNotFoundException("Resource not found")
                return dict(row)
        except ResourceNotFoundException:
            raise
        except PostgresError as e:
            logger.error(f"Database error fetching one: {e}")
            raise Exception(f"Failed to fetch row: {e}") from e

    async def _fetch_row_optional(self, query: str, args: tuple = (), connection: Connection = None):
        try:
            async with self._get_connection(connection) as conn:
                row = await conn.fetchrow(query, *args)
                return dict(row) if row else None
        except PostgresError as e:
            logger.error(f"Database error fetching one: {e}")
            raise Exception(f"Failed to fetch row: {e}") from e

    async def _fetch_all(self, query: str, args: tuple = (), connection: Connection = None):
        try:
            async with self._get_connection(connection) as conn:
                rows = await conn.fetch(query, *args)
                return [dict(row) for row in rows]
        except PostgresError as e:
            logger.error(f"Database error fetching all: {e}")
            raise Exception(f"Failed to fetch rows: {e}") from e

    async def _execute(self, query: str, args: tuple = (), connection: Connection = None):
        try:
            async with self._get_connection(connection) as conn:
                result = await conn.execute(query, *args)
                logger.debug(f"Executed query. Result: {result}")
                return result
        except PostgresError as e:
            logger.error(f"Database error executing query: {e}")
            raise Exception(f"Failed to execute query: {e}") from e

    async def _execute_many(self, query: str, args_list: list[tuple], connection: Connection = None):
        try:
            async with self._get_connection(connection) as conn:
                await conn.executemany(query, args_list)
                logger.debug(f"Executed query {len(args_list)} times")
        except PostgresError as e:
            logger.error(f"Database error executing many: {e}")
            raise Exception(f"Failed to execute many: {e}") from e

    @asynccontextmanager
    async def _get_connection(self, connection: Connection = None):
        if connection is not None:
            yield connection
        else:
            async with get_db_connection() as conn:
                yield conn

    @asynccontextmanager
    async def _transaction(self, connection: Connection = None):
        async with self._get_connection(connection) as conn:
            async with conn.transaction():
                try:
                    logger.debug("Transaction started")
                    yield conn
                    logger.debug("Transaction committed")
                except Exception as e:
                    logger.error(f"Transaction rolled back due to error: {e}")
                    raise

    def _deleted_successfully(self, result: str) -> bool:
        affected_rows = int(result.split()[-1])
        return affected_rows > 0

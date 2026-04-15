"""
Multi-database connector gateway. Adapted from Revelate's DatabasesOperations.
Supports: PostgreSQL, MySQL, MariaDB, MSSQL, Oracle, ClickHouse.
"""
import logging
import traceback
import urllib.parse
from typing import Any, Generic, Optional, TypeVar

from sqlalchemy import inspect, text, MetaData
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

logger = logging.getLogger(__name__)
T = TypeVar("T")

DEFAULT_PORTS = {
    "postgresql": 5432,
    "mysql": 3306,
    "mariadb": 3306,
    "mssql": 1433,
    "oracle": 1521,
    "clickhouse": 9000,
}


class QueryResult(Generic[T]):
    def __init__(self, success: bool, data: Optional[T] = None, error: Optional[str] = None):
        self.success = success
        self.data = data
        self.error = error


class DbConnectorGateway:

    def __init__(self, db_type: str, username: str, password: str, host: str,
                 port: str = "", database: str = "", pool_size: int = 5) -> None:
        self.db_type = db_type
        self.username = username
        self.password = password
        self.host = host
        self.port = port or str(DEFAULT_PORTS.get(db_type, ""))
        self.database = database
        self.pool_size = pool_size
        self.engine = self._create_engine()
        self.metadata = MetaData()

    def _create_engine(self) -> AsyncEngine | None:
        try:
            encoded_password = urllib.parse.quote_plus(self.password)
            if self.db_type == "postgresql":
                dsn = f"postgresql+asyncpg://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"
            elif self.db_type in ("mysql", "mariadb"):
                dsn = f"mysql+aiomysql://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"
            elif self.db_type == "mssql":
                odbc = f"Driver={{ODBC Driver 17 for SQL Server}};Server={self.host},{self.port};Database={self.database};UID={self.username};PWD={self.password}"
                dsn = f"mssql+aioodbc:///?odbc_connect={urllib.parse.quote_plus(odbc)}"
            elif self.db_type == "oracle":
                dsn = f"oracle+asyncio_oracledb://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"
            elif self.db_type == "clickhouse":
                dsn = f"clickhouse+asynch://{self.username}:{encoded_password}@{self.host}:{self.port}/{self.database}"
            else:
                raise ValueError(f"Unsupported database type: {self.db_type}")

            return create_async_engine(dsn, pool_size=self.pool_size)
        except Exception as e:
            logger.error(f"Engine creation failed for {self.db_type}: {e}")
            return None

    async def test_connection(self) -> QueryResult[bool]:
        if not self.engine:
            return QueryResult(False, False, "No engine available")
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return QueryResult(True, True)
        except Exception as e:
            return QueryResult(False, False, str(e))

    async def list_tables(self) -> QueryResult[list[str]]:
        if not self.engine:
            return QueryResult(False, [], "No engine available")
        try:
            async with self.engine.connect() as conn:
                if self.db_type == "postgresql":
                    query = text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
                elif self.db_type in ("mysql", "mariadb"):
                    query = text("SHOW TABLES")
                elif self.db_type == "mssql":
                    query = text("SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_TYPE = 'BASE TABLE'")
                else:
                    query = text("SELECT table_name FROM information_schema.tables")
                result = await conn.execute(query)
                return QueryResult(True, [row[0] for row in result.fetchall()])
        except Exception as e:
            return QueryResult(False, [], str(e))

    async def list_schemas(self) -> QueryResult[dict[str, Any]]:
        if not self.engine:
            return QueryResult(False, {}, "No engine available")
        try:
            async with self.engine.connect() as conn:
                def get_schema(sync_conn):
                    inspector = inspect(sync_conn)
                    schema_info = {}
                    for table in inspector.get_table_names():
                        columns = {}
                        for col in inspector.get_columns(table):
                            columns[col["name"]] = {"data_type": str(col["type"]), "nullable": col.get("nullable")}
                        pks = inspector.get_pk_constraint(table).get("constrained_columns", [])
                        fks = inspector.get_foreign_keys(table)
                        schema_info[table] = {"columns": columns, "primary_keys": pks, "foreign_keys": fks}
                    return schema_info
                schema_info = await conn.run_sync(get_schema)
            return QueryResult(True, schema_info)
        except Exception as e:
            return QueryResult(False, {}, str(e))

    async def execute_query(self, sql: str, limit: int | None = None) -> QueryResult[dict]:
        """Execute a SELECT query and return {columns, rows}. If limit is set, wraps the query."""
        if not self.engine:
            return QueryResult(False, None, "No engine available")
        try:
            query_sql = sql.strip().rstrip(";")
            if limit is not None:
                query_sql = f"SELECT * FROM ({query_sql}) _preview LIMIT {int(limit)}"
            async with self.engine.connect() as conn:
                result = await conn.execute(text(query_sql))
                columns = list(result.keys())
                rows = [
                    [
                        v.isoformat() if hasattr(v, "isoformat")
                        else (str(v) if isinstance(v, (bytes, bytearray, memoryview)) else v)
                        for v in row
                    ]
                    for row in result.fetchall()
                ]
            return QueryResult(True, {"columns": columns, "rows": rows})
        except Exception as e:
            return QueryResult(False, None, str(e))

    async def close(self) -> None:
        if self.engine:
            await self.engine.dispose()
            self.engine = None

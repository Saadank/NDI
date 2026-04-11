from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class UserRepository(PostgresqlAsyncRepository):

    async def find_by_tenant(self, tenant_id: int, page: int = 1, limit: int = 20) -> list[dict]:
        offset = (page - 1) * limit
        return await self._fetch_all(
            "SELECT * FROM t_users WHERE tenant_id = $1 AND deleted_at IS NULL ORDER BY created_at DESC LIMIT $2 OFFSET $3",
            (tenant_id, limit, offset),
        )

    async def count_by_tenant(self, tenant_id: int) -> int:
        return await self._fetch_value(
            "SELECT COUNT(*) FROM t_users WHERE tenant_id = $1 AND deleted_at IS NULL", (tenant_id,)
        )

    async def find_by_id(self, user_id: int) -> dict:
        return await self._fetch_row("SELECT * FROM t_users WHERE id = $1 AND deleted_at IS NULL", (user_id,))

    async def find_by_keycloak_id(self, keycloak_id: str) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_users WHERE keycloak_id = $1 AND deleted_at IS NULL", (keycloak_id,)
        )

    async def find_by_email(self, email: str, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_users WHERE email = $1 AND tenant_id = $2 AND deleted_at IS NULL", (email, tenant_id)
        )

    async def create(self, tenant_id: int, keycloak_id: str, email: str, first_name: str | None, last_name: str | None, platform_role: str) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_users (tenant_id, keycloak_id, email, first_name, last_name, platform_role)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            (tenant_id, keycloak_id, email, first_name, last_name, platform_role),
        )

    async def update(self, user_id: int, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        args.append(user_id)
        query = f"UPDATE t_users SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *"
        return await self._fetch_row(query, tuple(args))

    async def soft_delete(self, user_id: int) -> str:
        return await self._execute(
            "UPDATE t_users SET deleted_at = CURRENT_TIMESTAMP WHERE id = $1", (user_id,)
        )

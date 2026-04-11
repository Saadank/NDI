from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class TenantRepository(PostgresqlAsyncRepository):

    async def find_all(self, include_deleted: bool = False) -> list[dict]:
        query = "SELECT * FROM t_tenants"
        if not include_deleted:
            query += " WHERE deleted_at IS NULL"
        query += " ORDER BY created_at DESC"
        return await self._fetch_all(query)

    async def find_by_id(self, tenant_id: int) -> dict:
        return await self._fetch_row("SELECT * FROM t_tenants WHERE id = $1 AND deleted_at IS NULL", (tenant_id,))

    async def find_by_slug(self, slug: str) -> dict | None:
        return await self._fetch_row_optional("SELECT * FROM t_tenants WHERE slug = $1 AND deleted_at IS NULL", (slug,))

    async def create(self, name: str, slug: str, tenant_type: str, name_ar: str | None, dpo_name: str | None, dpo_email: str | None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_tenants (name, name_ar, slug, tenant_type, dpo_name, dpo_email)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            (name, name_ar, slug, tenant_type, dpo_name, dpo_email),
        )

    async def update(self, tenant_id: int, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append(f"updated_at = CURRENT_TIMESTAMP")
        set_clauses.append(f"version = version + 1")
        args.append(tenant_id)
        query = f"UPDATE t_tenants SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *"
        return await self._fetch_row(query, tuple(args))

    async def soft_delete(self, tenant_id: int) -> str:
        return await self._execute(
            "UPDATE t_tenants SET deleted_at = CURRENT_TIMESTAMP WHERE id = $1", (tenant_id,)
        )

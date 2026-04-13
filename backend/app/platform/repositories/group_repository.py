from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class GroupRepository(PostgresqlAsyncRepository):

    async def find_by_tenant(self, tenant_id: int, include_inactive: bool = False) -> list[dict]:
        if include_inactive:
            return await self._fetch_all(
                "SELECT * FROM t_groups WHERE tenant_id = $1 ORDER BY name", (tenant_id,)
            )
        return await self._fetch_all(
            "SELECT * FROM t_groups WHERE tenant_id = $1 AND is_active = TRUE ORDER BY name", (tenant_id,)
        )

    async def find_by_id(self, group_id: int) -> dict | None:
        return await self._fetch_row_optional("SELECT * FROM t_groups WHERE id = $1", (group_id,))

    async def find_by_slug(self, tenant_id: int, slug: str) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_groups WHERE tenant_id = $1 AND slug = $2", (tenant_id, slug)
        )

    async def create(self, tenant_id: int, name: str, name_ar: str | None,
                     slug: str, description: str | None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_groups (tenant_id, name, name_ar, slug, description)
               VALUES ($1, $2, $3, $4, $5) RETURNING *""",
            (tenant_id, name, name_ar, slug, description),
        )

    async def update(self, group_id: int, **fields) -> dict:
        set_clauses = []
        args = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        args.append(group_id)
        return await self._fetch_row(
            f"UPDATE t_groups SET {', '.join(set_clauses)} WHERE id = ${idx} RETURNING *",
            tuple(args),
        )

    async def count_members(self, group_id: int) -> int:
        return await self._fetch_value(
            "SELECT COUNT(*) FROM t_users WHERE group_id = $1 AND deleted_at IS NULL", (group_id,)
        )

    async def find_members(self, group_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT id, email, first_name, last_name, platform_role FROM t_users WHERE group_id = $1 AND deleted_at IS NULL ORDER BY first_name",
            (group_id,),
        )

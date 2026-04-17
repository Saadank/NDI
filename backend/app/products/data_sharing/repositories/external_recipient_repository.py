from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ExternalRecipientRepository(PostgresqlAsyncRepository):

    async def create(self, tenant_id: int, org_name: str, notes: str | None,
                     dpa_required: bool, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_external_recipients
               (tenant_id, org_name, notes, dpa_required, created_by)
               VALUES ($1, $2, $3, $4, $5)
               RETURNING *""",
            (tenant_id, org_name, notes, dpa_required, created_by),
        )

    async def find_by_id(self, recipient_id: int, tenant_id: int) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_external_recipients WHERE id = $1 AND tenant_id = $2",
            (recipient_id, tenant_id),
        )

    async def find_by_org_name_in_tenant(self, tenant_id: int, org_name: str) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_external_recipients WHERE tenant_id = $1 AND lower(org_name) = lower($2)",
            (tenant_id, org_name),
        )

    async def list_by_tenant(self, tenant_id: int, search: str | None,
                             page: int, limit: int) -> list[dict]:
        conditions = ["tenant_id = $1"]
        args: list = [tenant_id]
        idx = 2
        if search:
            conditions.append(f"lower(org_name) LIKE ${idx}")
            args.append(f"%{search.lower()}%")
            idx += 1
        where = " AND ".join(conditions)
        offset = (page - 1) * limit
        args.extend([limit, offset])
        return await self._fetch_all(
            f"SELECT * FROM t_external_recipients WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

    async def count_by_tenant(self, tenant_id: int, search: str | None) -> int:
        conditions = ["tenant_id = $1"]
        args: list = [tenant_id]
        idx = 2
        if search:
            conditions.append(f"lower(org_name) LIKE ${idx}")
            args.append(f"%{search.lower()}%")
        where = " AND ".join(conditions)
        return await self._fetch_value(
            f"SELECT COUNT(*) FROM t_external_recipients WHERE {where}", tuple(args)
        )

    async def update(self, recipient_id: int, tenant_id: int, **fields) -> dict:
        set_clauses = []
        args: list = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        args.extend([recipient_id, tenant_id])
        return await self._fetch_row(
            f"UPDATE t_external_recipients SET {', '.join(set_clauses)} "
            f"WHERE id = ${idx} AND tenant_id = ${idx + 1} RETURNING *",
            tuple(args),
        )

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class ProductRepository(PostgresqlAsyncRepository):

    async def find_all_products(self) -> list[dict]:
        return await self._fetch_all("SELECT * FROM t_products WHERE is_active = TRUE ORDER BY sort_order")

    async def find_product_by_slug(self, slug: str) -> dict | None:
        return await self._fetch_row_optional("SELECT * FROM t_products WHERE slug = $1", (slug,))

    async def find_tenant_products(self, tenant_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT p.*, tp.enabled, tp.enabled_at
               FROM t_products p
               JOIN t_tenant_products tp ON tp.product_id = p.id
               WHERE tp.tenant_id = $1 AND tp.enabled = TRUE AND p.is_active = TRUE
               ORDER BY p.sort_order""",
            (tenant_id,),
        )

    async def enable_product(self, tenant_id: int, product_id: int, enabled_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_tenant_products (tenant_id, product_id, enabled_by)
               VALUES ($1, $2, $3)
               ON CONFLICT (tenant_id, product_id)
               DO UPDATE SET enabled = TRUE, enabled_at = CURRENT_TIMESTAMP, enabled_by = $3, disabled_at = NULL, disabled_by = NULL
               RETURNING *""",
            (tenant_id, product_id, enabled_by),
        )

    async def disable_product(self, tenant_id: int, product_id: int, disabled_by: int) -> str:
        return await self._execute(
            """UPDATE t_tenant_products SET enabled = FALSE, disabled_at = CURRENT_TIMESTAMP, disabled_by = $3
               WHERE tenant_id = $1 AND product_id = $2""",
            (tenant_id, product_id, disabled_by),
        )

    async def find_user_product_role(self, user_id: int, product_id: int) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_user_product_roles WHERE user_id = $1 AND product_id = $2",
            (user_id, product_id),
        )

    async def assign_user_product_role(self, user_id: int, product_id: int, role: str, assigned_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_user_product_roles (user_id, product_id, role, assigned_by)
               VALUES ($1, $2, $3, $4)
               ON CONFLICT (user_id, product_id)
               DO UPDATE SET role = $3, assigned_by = $4, assigned_at = CURRENT_TIMESTAMP
               RETURNING *""",
            (user_id, product_id, role, assigned_by),
        )

    async def is_product_enabled_for_tenant(self, tenant_id: int, product_slug: str) -> bool:
        val = await self._fetch_value(
            """SELECT COUNT(*) FROM t_tenant_products tp
               JOIN t_products p ON p.id = tp.product_id
               WHERE tp.tenant_id = $1 AND p.slug = $2 AND tp.enabled = TRUE""",
            (tenant_id, product_slug),
        )
        return val > 0

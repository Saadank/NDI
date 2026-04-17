from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class RecipientContactRepository(PostgresqlAsyncRepository):

    async def create(self, recipient_id: int, email: str, name: str | None,
                     phone: str | None, created_by: int) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_recipient_contacts
               (recipient_id, email, name, phone, created_by)
               VALUES ($1, lower($2), $3, $4, $5)
               RETURNING *""",
            (recipient_id, email, name, phone, created_by),
        )

    async def find_by_id(self, contact_id: int) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_recipient_contacts WHERE id = $1",
            (contact_id,),
        )

    async def find_by_recipient_and_email(self, recipient_id: int, email: str) -> dict | None:
        return await self._fetch_row_optional(
            "SELECT * FROM t_recipient_contacts WHERE recipient_id = $1 AND email = lower($2)",
            (recipient_id, email),
        )

    async def list_for_recipient(self, recipient_id: int) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_recipient_contacts WHERE recipient_id = $1 ORDER BY created_at ASC",
            (recipient_id,),
        )

    async def find_by_email_in_tenant(self, tenant_id: int, email: str) -> list[dict]:
        return await self._fetch_all(
            """SELECT c.* FROM t_recipient_contacts c
               JOIN t_external_recipients r ON r.id = c.recipient_id
               WHERE r.tenant_id = $1 AND c.email = lower($2)""",
            (tenant_id, email),
        )

    async def mark_verified(self, contact_id: int) -> dict:
        return await self._fetch_row(
            """UPDATE t_recipient_contacts
               SET email_verified_at = COALESCE(email_verified_at, CURRENT_TIMESTAMP),
                   updated_at = CURRENT_TIMESTAMP
               WHERE id = $1 RETURNING *""",
            (contact_id,),
        )

    async def update(self, contact_id: int, **fields) -> dict:
        set_clauses = []
        args: list = []
        idx = 1
        for key, val in fields.items():
            set_clauses.append(f"{key} = ${idx}")
            args.append(val)
            idx += 1
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
        args.append(contact_id)
        return await self._fetch_row(
            f"UPDATE t_recipient_contacts SET {', '.join(set_clauses)} "
            f"WHERE id = ${idx} RETURNING *",
            tuple(args),
        )

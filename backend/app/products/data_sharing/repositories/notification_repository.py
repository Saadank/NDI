from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository


class NotificationRepository(PostgresqlAsyncRepository):

    async def create(self, user_id: int, tenant_id: int, type: str, title: str, body: str | None, request_id: UUID | None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_notifications (user_id, tenant_id, type, title, body, request_id)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *""",
            (user_id, tenant_id, type, title, body, request_id),
        )

    async def find_by_user(self, user_id: int, unread_only: bool = False) -> list[dict]:
        query = "SELECT * FROM t_notifications WHERE user_id = $1"
        if unread_only:
            query += " AND is_read = FALSE"
        query += " ORDER BY created_at DESC LIMIT 50"
        return await self._fetch_all(query, (user_id,))

    async def mark_read(self, notification_id: UUID, user_id: int) -> dict:
        return await self._fetch_row(
            "UPDATE t_notifications SET is_read = TRUE, read_at = CURRENT_TIMESTAMP WHERE id = $1 AND user_id = $2 RETURNING *",
            (notification_id, user_id),
        )

    async def queue_email(self, to_email: str, subject: str, html_body: str, request_id: UUID | None = None) -> dict:
        return await self._fetch_row(
            """INSERT INTO t_email_queue (to_email, subject, html_body, request_id)
               VALUES ($1, $2, $3, $4) RETURNING *""",
            (to_email, subject, html_body, request_id),
        )

    async def find_pending_emails(self, limit: int = 20) -> list[dict]:
        return await self._fetch_all(
            "SELECT * FROM t_email_queue WHERE status = 'pending' AND attempts < 3 ORDER BY created_at LIMIT $1",
            (limit,),
        )

    async def update_email_status(self, email_id: UUID, status: str, error: str | None = None) -> str:
        return await self._execute(
            "UPDATE t_email_queue SET status = $1, attempts = attempts + 1, last_error = $2, sent_at = CASE WHEN $1 = 'sent' THEN CURRENT_TIMESTAMP ELSE sent_at END WHERE id = $3",
            (status, error, email_id),
        )

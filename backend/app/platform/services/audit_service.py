import logging
from typing import Any
from uuid import UUID

from app.structures.postgresql_async_repository import PostgresqlAsyncRepository
from app.utils.pagination import get_pagination_data

logger = logging.getLogger(__name__)


class AuditService(PostgresqlAsyncRepository):

    async def log(
        self,
        tenant_id: int,
        action_type: str,
        resource_type: str,
        resource_id: str | None = None,
        actor_id: int | None = None,
        actor_ip: str | None = None,
        before_state: dict | None = None,
        after_state: dict | None = None,
        metadata: dict | None = None,
        request_id: UUID | None = None,
    ) -> None:
        try:
            import json
            from datetime import datetime, date

            def _serialize(obj):
                if isinstance(obj, (UUID, )):
                    return str(obj)
                if isinstance(obj, (datetime, date)):
                    return obj.isoformat()
                raise TypeError(f"Not serializable: {type(obj)}")

            await self._execute(
                """INSERT INTO t_audit_events (tenant_id, action_type, resource_type, resource_id,
                   actor_id, actor_ip, before_state, after_state, metadata, request_id)
                   VALUES ($1, $2, $3, $4, $5, $6::inet, $7::jsonb, $8::jsonb, $9::jsonb, $10)""",
                (
                    tenant_id, action_type, resource_type, resource_id,
                    actor_id, actor_ip,
                    json.dumps(before_state, default=_serialize) if before_state else None,
                    json.dumps(after_state, default=_serialize) if after_state else None,
                    json.dumps(metadata, default=_serialize) if metadata else None,
                    request_id,
                ),
            )
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")

    async def list_events(
        self, tenant_id: int, page: int = 1, limit: int = 20,
        request_id: UUID | None = None, actor_id: int | None = None,
        action_type: str | None = None,
    ) -> dict:
        conditions = ["tenant_id = $1"]
        args: list[Any] = [tenant_id]
        idx = 2

        if request_id:
            conditions.append(f"request_id = ${idx}")
            args.append(request_id)
            idx += 1
        if actor_id:
            conditions.append(f"actor_id = ${idx}")
            args.append(actor_id)
            idx += 1
        if action_type:
            conditions.append(f"action_type = ${idx}")
            args.append(action_type)
            idx += 1

        where = " AND ".join(conditions)
        count = await self._fetch_value(f"SELECT COUNT(*) FROM t_audit_events WHERE {where}", tuple(args))

        offset = (page - 1) * limit
        args.extend([limit, offset])
        rows = await self._fetch_all(
            f"SELECT * FROM t_audit_events WHERE {where} ORDER BY created_at DESC LIMIT ${idx} OFFSET ${idx + 1}",
            tuple(args),
        )

        pagination = get_pagination_data(limit, page, count)
        return {"data": rows, **pagination}


def get_audit_service() -> AuditService:
    return AuditService()

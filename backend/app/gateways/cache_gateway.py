import json
import logging
from typing import Any

import redis

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class CacheGateway:

    def __init__(self) -> None:
        settings = get_settings()
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True,
        )

    def get(self, key: str) -> str | None:
        return self.client.get(name=key)

    def set(self, key: str, value: Any, ex: int | None = None) -> bool:
        return self.client.set(name=key, value=value, ex=ex)

    def delete(self, *keys: str) -> int:
        return self.client.delete(*keys)

    def exists(self, key: str) -> bool:
        return self.client.exists(key) > 0

    def expire(self, key: str, seconds: int) -> bool:
        return self.client.expire(name=key, time=seconds)

    def sadd(self, key: str, *members: Any) -> int:
        return self.client.sadd(key, *members)

    def sismember(self, key: str, member: Any) -> bool:
        return self.client.sismember(key, member)

    def srem(self, key: str, *members: Any) -> int:
        return self.client.srem(key, *members)

    def push(self, key: str, *values: Any) -> int:
        return self.client.rpush(key, *values)

    def pop(self, key: str) -> str | None:
        return self.client.lpop(key)

    def set_json(self, key: str, value: dict, ex: int | None = None) -> bool:
        return self.client.set(name=key, value=json.dumps(value), ex=ex)

    def get_json(self, key: str) -> dict | None:
        value = self.client.get(key)
        return json.loads(value) if value else None

    def ping(self) -> bool:
        return self.client.ping()

    def close(self) -> None:
        self.client.close()

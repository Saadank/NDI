"""Lightweight in-process sliding-window rate limiter.

Suitable for single-process dev / low-traffic deployments of the public pickup
router. In multi-worker production, swap with a Redis-backed implementation.
"""
from collections import defaultdict, deque
from time import monotonic
from threading import Lock

from fastapi import HTTPException


class SlidingWindowLimiter:

    def __init__(self, window_seconds: int = 60) -> None:
        self._window = window_seconds
        self._hits: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit: int) -> None:
        """Raise HTTPException(429) if `key` has more than `limit` hits in the window."""
        now = monotonic()
        cutoff = now - self._window
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] < cutoff:
                hits.popleft()
            if len(hits) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests")
            hits.append(now)


# Module-level singleton used by the pickup router.
pickup_limiter = SlidingWindowLimiter(window_seconds=60)

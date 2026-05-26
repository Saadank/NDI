"""Assessment-cycle lifecycle."""

from __future__ import annotations

from enum import StrEnum


class CycleStatus(StrEnum):
    PLANNING = "planning"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"

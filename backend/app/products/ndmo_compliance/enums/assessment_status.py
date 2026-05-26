"""Lifecycle status of a single (tenant, specification, cycle) assessment row."""

from __future__ import annotations

from enum import StrEnum


class AssessmentStatus(StrEnum):
    PENDING = "pending"               # not yet assessed by the engine
    IN_PROGRESS = "in_progress"       # engine is currently running
    UNDER_REVIEW = "under_review"     # engine done, analyst hasn't acted yet
    APPROVED = "approved"             # analyst approved
    REJECTED = "rejected"             # analyst rejected and edited

"""Three-way review outcome from the Compliance Analyst on an AI assessment."""

from __future__ import annotations

from enum import StrEnum


class ReviewDecision(StrEnum):
    APPROVED = "approved"                       # accept AI verdict as-is
    CHANGES_REQUESTED = "changes_requested"     # ask for more evidence
    REJECTED = "rejected"                       # override the AI verdict

"""Data Owner's decision on a submitted term (BRD §6.2 / WF-02).

Matches ndmo.t_glossary_term_reviews.decision.  `request_changes` and
`reject` both return the term to draft and both REQUIRE a note.
"""

from __future__ import annotations

from enum import StrEnum


class GlossaryReviewDecision(StrEnum):
    APPROVE = "approve"
    REQUEST_CHANGES = "request_changes"
    REJECT = "reject"

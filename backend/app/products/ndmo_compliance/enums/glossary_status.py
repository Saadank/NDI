"""Lifecycle status of a glossary term.

Matches the CHECK constraint on ndmo.t_glossary_terms.status in
034_ndmo_glossary.sql.  State machine (BRD §5.3):

    (new) -> draft
    draft -> under_review               (steward submits)
    changes_requested -> under_review   (steward resubmits)
    under_review -> approved             (owner approves)
    under_review -> changes_requested    (owner requests changes — new term)
    under_review -> draft                (owner rejects — new term)
    approved -> under_review             (edit submitted on a published term)
    approved -> deprecated               (owner deprecates)
    deprecated -> draft                  (reinstated)

`changes_requested` is kept distinct from `draft` so the steward can see the
owner's note and that the term was sent back (NOT a fresh draft).
"""

from __future__ import annotations

from enum import StrEnum


class GlossaryTermStatus(StrEnum):
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    APPROVED = "approved"
    DEPRECATED = "deprecated"
    CHANGES_REQUESTED = "changes_requested"

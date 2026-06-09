from enum import Enum


class RequestStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    # Set when a reviewer (DPO / Data Owner) sends a request back for edits.
    # The requester edits and resubmits; submit_request already accepts this
    # status as a valid resubmission source (spec v4.0 §4.4).
    CHANGES_REQUESTED = "changes_requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"

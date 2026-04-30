from enum import Enum


class TableSemanticType(str, Enum):
    """BRD §4.2 Table Semantic Types — drives rule applicability and scoring weights."""

    MASTER_DATA = "master_data"
    TRANSACTION = "transaction"
    EVENT_LOG = "event_log"
    REFERENCE = "reference"
    STAGING = "staging"
    SNAPSHOT = "snapshot"

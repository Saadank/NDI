from enum import Enum


class Severity(str, Enum):
    """Issue / rule severity (BRD §4.3, FR-XLS rule rows)."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"

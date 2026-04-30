from enum import Enum


class DqDimension(str, Enum):
    """BRD Table 23 — six standard DQ dimensions."""

    COMPLETENESS = "completeness"
    VALIDITY = "validity"
    UNIQUENESS = "uniqueness"
    CONSISTENCY = "consistency"
    TIMELINESS = "timeliness"
    ACCURACY = "accuracy"

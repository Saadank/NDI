"""The official NDMO 6-level maturity model.

These are the values for ndmo.t_ndmo_assessments.maturity_level and the
keys of ndmo.t_ndmo_specifications.maturity_levels JSONB.

NDMO official wording:
  0 - غياب القدرات      (Absence of capabilities)
  1 - البناء             (Building)
  2 - مُعرَّف            (Defined)
  3 - مُفعَّل            (Activated)
  4 - مُمكَّن            (Enabled)
  5 - ريادي              (Leading)
"""

from __future__ import annotations

from enum import IntEnum


class MaturityLevel(IntEnum):
    ABSENCE_OF_CAPABILITIES = 0
    BUILDING = 1
    DEFINED = 2
    ACTIVATED = 3
    ENABLED = 4
    LEADING = 5

    @property
    def name_ar(self) -> str:
        return _NAMES_AR[self]

    @property
    def name_en(self) -> str:
        return _NAMES_EN[self]


_NAMES_AR: dict[MaturityLevel, str] = {
    MaturityLevel.ABSENCE_OF_CAPABILITIES: "غياب القدرات",
    MaturityLevel.BUILDING: "البناء",
    MaturityLevel.DEFINED: "مُعرَّف",
    MaturityLevel.ACTIVATED: "مُفعَّل",
    MaturityLevel.ENABLED: "مُمكَّن",
    MaturityLevel.LEADING: "ريادي",
}

_NAMES_EN: dict[MaturityLevel, str] = {
    MaturityLevel.ABSENCE_OF_CAPABILITIES: "Absence of capabilities",
    MaturityLevel.BUILDING: "Building",
    MaturityLevel.DEFINED: "Defined",
    MaturityLevel.ACTIVATED: "Activated",
    MaturityLevel.ENABLED: "Enabled",
    MaturityLevel.LEADING: "Leading",
}

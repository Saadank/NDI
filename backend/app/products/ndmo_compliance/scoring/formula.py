"""National Data Index (NDI) score calculation.

Source: National-Data-Index_v1.0_AR.pdf (Saudi National Data Office, v1.0,
Arabic edition).  Encoded as code per Phase-1 plan §F — the file itself is
NOT stored as a row.

The NDI score is the weighted mean of per-specification maturity levels
across the specifications in scope for the current assessment cycle, then
normalised to a 0–100 percentage.

  ndi = ( sum_i ( w_i * maturity_i ) / sum_i ( w_i * 5 ) ) * 100

Where:
  * i ranges over all specifications whose `priority` is in the cycle's
    `active_priorities` array (year 1 = [1], year 2 = [1, 2], year 3 = all).
  * w_i is the per-specification weight (default 1.0; can be overridden per
    domain or per priority — see PRIORITY_WEIGHT and DOMAIN_WEIGHT below).
  * maturity_i is the 0..5 verdict on that specification, or 0 if no
    assessment exists yet for that (spec, cycle) pair.

The denominator uses 5 (the maximum maturity), so a score of 100 means
every specification in scope reached "Leading" (level 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


# Priority-based weights.  NDMO treats high-priority specifications as more
# important to the rollup — these are the official ratios from the NDI doc.
# Adjust here, not at call sites.
PRIORITY_WEIGHT: dict[int, float] = {
    1: 3.0,   # year-1 priority — heaviest
    2: 2.0,   # year-2 priority
    3: 1.0,   # year-3 priority
}


# Domain-level multipliers.  Default to 1.0 (no boost).  Override here if
# NDMO publishes a domain-weighted variant.
DOMAIN_WEIGHT: dict[str, float] = {
    # "DG": 1.2,
}


@dataclass(slots=True)
class _SpecScore:
    spec_code: str
    domain_code: str
    priority: int
    maturity: int  # 0..5
    weight: float = 1.0


@dataclass(slots=True)
class NdiScoreBreakdown:
    """Full transcript of one NDI score computation."""

    score_percent: float
    spec_count: int
    assessed_count: int            # rows where maturity > 0 (or where an assessment exists)
    average_maturity: float        # unweighted, for sanity-check on the UI
    per_domain: dict[str, float] = field(default_factory=dict)  # 0..100 per domain
    per_priority: dict[int, float] = field(default_factory=dict)
    formula_note: str = ""


def compute_ndi_score(
    spec_scores: list[_SpecScore] | list[dict],
    active_priorities: list[int],
) -> NdiScoreBreakdown:
    """Compute the NDI percentage score.

    Parameters
    ----------
    spec_scores
        One entry per *in-scope* specification.  Accepts either the typed
        _SpecScore dataclass or a plain dict with the same keys (the latter
        is convenient when feeding rows straight out of asyncpg).
    active_priorities
        Which priority levels count this cycle.  Specs whose priority is
        not in this list are excluded from the calculation.
    """
    rows = [_coerce(s) for s in spec_scores if _coerce(s).priority in active_priorities]
    if not rows:
        return NdiScoreBreakdown(
            score_percent=0.0,
            spec_count=0,
            assessed_count=0,
            average_maturity=0.0,
            formula_note="No in-scope specifications for the active priorities.",
        )

    weighted_actual = Decimal("0")
    weighted_max = Decimal("0")
    per_domain_acc: dict[str, tuple[Decimal, Decimal]] = {}  # code -> (actual, max)
    per_priority_acc: dict[int, tuple[Decimal, Decimal]] = {}

    for r in rows:
        w = Decimal(str(_effective_weight(r)))
        m = Decimal(str(r.maturity))
        max_m = Decimal("5")
        weighted_actual += w * m
        weighted_max += w * max_m

        actual_d, max_d = per_domain_acc.get(r.domain_code, (Decimal("0"), Decimal("0")))
        per_domain_acc[r.domain_code] = (actual_d + w * m, max_d + w * max_m)

        actual_p, max_p = per_priority_acc.get(r.priority, (Decimal("0"), Decimal("0")))
        per_priority_acc[r.priority] = (actual_p + w * m, max_p + w * max_m)

    score = float(weighted_actual / weighted_max) * 100.0
    avg = float(sum(r.maturity for r in rows)) / len(rows)

    return NdiScoreBreakdown(
        score_percent=round(score, 2),
        spec_count=len(rows),
        assessed_count=sum(1 for r in rows if r.maturity > 0),
        average_maturity=round(avg, 2),
        per_domain={
            d: round(float(a / m) * 100.0, 2) if m > 0 else 0.0
            for d, (a, m) in per_domain_acc.items()
        },
        per_priority={
            p: round(float(a / m) * 100.0, 2) if m > 0 else 0.0
            for p, (a, m) in per_priority_acc.items()
        },
        formula_note=(
            "NDI = sum(w_i * maturity_i) / sum(w_i * 5) * 100, "
            "where w_i = PRIORITY_WEIGHT[priority] * DOMAIN_WEIGHT.get(domain, 1.0)."
        ),
    )


def _coerce(s: _SpecScore | dict) -> _SpecScore:
    if isinstance(s, _SpecScore):
        return s
    return _SpecScore(
        spec_code=s["spec_code"],
        domain_code=s["domain_code"],
        priority=int(s["priority"]),
        maturity=int(s.get("maturity", 0)),
        weight=float(s.get("weight", 1.0)),
    )


def _effective_weight(r: _SpecScore) -> float:
    return r.weight * PRIORITY_WEIGHT.get(r.priority, 1.0) * DOMAIN_WEIGHT.get(r.domain_code, 1.0)


__all__ = ["compute_ndi_score", "NdiScoreBreakdown", "PRIORITY_WEIGHT", "DOMAIN_WEIGHT"]

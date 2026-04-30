"""Quality-score computation — Phase 1, Step 4 (BRD §4.7 / FR-SCORE).

The validator emits one issue row per (scan, active_rule). This service
aggregates those into per-dimension and overall scores, classifies each
into a tier (good / acceptable / not_acceptable), and persists the result
to dq.t_dq_score_history for trend deltas across scan history.

The scoring service is invoked by the validator immediately after issue
inserts; it reads the issues for the scan via SQL aggregate so we don't
double-handle the per-rule data in Python.

Severity weighting is opt-in per tenant via t_dq_score_thresholds. When
ON, weighted_score = SUM(pass_rate × w) / SUM(w) with w in {critical:4,
high:3, medium:2, low:1}. raw_score remains unweighted regardless.

Step 5 will introduce governed_score (raw minus exception-suppressed
issues). Today the two values are equal.
"""
from __future__ import annotations

import logging

from app.products.data_quality.repositories.score_repository import ScoreRepository
from app.structures.postgresql_async_repository import PostgresqlAsyncRepository

logger = logging.getLogger(__name__)

_DIMENSIONS = ("completeness", "validity", "uniqueness")
_DEFAULT_GOOD_MIN = 0.95
_DEFAULT_ACCEPTABLE_MIN = 0.70
_SEVERITY_WEIGHTS = {"critical": 4.0, "high": 3.0, "medium": 2.0, "low": 1.0}


class _IssueAggReader(PostgresqlAsyncRepository):
    """Tiny helper repo — keeps the SUM(pass_rate)/COUNT(*) query co-located
    with the scoring service rather than scattering it across IssueRepository.

    Step 5: switched to per-issue rows so we can apply per-rule exception
    forgiveness (governed score) before aggregating. Pure SQL aggregation
    can't see exceptions efficiently, so we move the bucket logic to Python.
    """

    async def issues_for_scan(self, *, tenant_id: int, scan_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT
                  active_rule_id, dimension, severity, status,
                  violation_count, violation_rate
                FROM dq.t_dq_issues
               WHERE tenant_id = $1 AND scan_id = $2""",
            (tenant_id, scan_id),
        )


class ScoringService:

    def __init__(self) -> None:
        self.score_repo = ScoreRepository()
        self._issue_reader = _IssueAggReader()

    async def score_scan(
        self, *, tenant_id: int, profile_id: int, scan_id: int,
    ) -> list[dict]:
        """Compute and persist one score row per dimension + one 'overall'
        for the given scan. Idempotent — safe to re-run if the validator is
        re-invoked on the same scan, or when an exception change requires
        a recompute.

        Step 5 — raw vs governed:
          - raw_pass     = 1 - violation_rate (or 1.0 for status='pass')
          - governed_pass = 1.0 if an active exception covers this rule
                            (no ceiling, OR violation_count <= ceiling),
                            else raw_pass
        """
        issues = await self._issue_reader.issues_for_scan(
            tenant_id=tenant_id, scan_id=scan_id,
        )
        thresholds_map, weighting_on, snapshot = await self._load_thresholds(tenant_id)

        # Pull active exceptions covering any rule in this scan.
        from app.products.data_quality.repositories.exception_repository import (
            ExceptionRepository,
        )
        exc_repo = ExceptionRepository()
        exceptions_by_rule = await exc_repo.find_active_for_scan(
            tenant_id=tenant_id, scan_id=scan_id,
        )

        # Bucket per-dimension. Track raw + governed separately.
        per_dim: dict[str, dict] = {
            d: {"rule_count": 0, "pass": 0, "fail": 0, "error": 0,
                "raw_sum": 0.0, "gov_sum": 0.0, "eligible": 0,
                "raw_w_num": 0.0, "gov_w_num": 0.0, "w_den": 0.0,
                "exception_count": 0}
            for d in _DIMENSIONS
        }
        for issue in issues:
            dim = issue["dimension"]
            if dim not in per_dim:
                continue
            status = issue["status"]
            severity = issue["severity"]
            per_dim[dim]["rule_count"] += 1
            per_dim[dim][status] = per_dim[dim].get(status, 0) + 1
            if status not in ("pass", "fail"):
                # error rows have no meaningful pass_rate
                continue

            vr = float(issue["violation_rate"] or 0.0)
            raw_pass = 1.0 - vr
            gov_pass = raw_pass

            exc = exceptions_by_rule.get(issue["active_rule_id"])
            if exc is not None:
                ceiling = exc.get("violation_count_ceiling")
                vc = int(issue.get("violation_count") or 0)
                if ceiling is None or vc <= int(ceiling):
                    gov_pass = 1.0
                    per_dim[dim]["exception_count"] += 1

            per_dim[dim]["raw_sum"] += raw_pass
            per_dim[dim]["gov_sum"] += gov_pass
            per_dim[dim]["eligible"] += 1
            w = _SEVERITY_WEIGHTS.get(severity, 1.0)
            per_dim[dim]["raw_w_num"] += raw_pass * w
            per_dim[dim]["gov_w_num"] += gov_pass * w
            per_dim[dim]["w_den"] += w

        persisted: list[dict] = []
        overall = {"raw_sum": 0.0, "gov_sum": 0.0, "eligible": 0,
                   "pass": 0, "fail": 0, "error": 0,
                   "raw_w_num": 0.0, "gov_w_num": 0.0, "w_den": 0.0,
                   "exception_count": 0}

        for dim in _DIMENSIONS:
            agg = per_dim[dim]
            eligible = agg["eligible"]
            rule_count = agg["rule_count"]
            raw_rate = (agg["raw_sum"] / eligible) if eligible else None
            gov_rate = (agg["gov_sum"] / eligible) if eligible else None
            # Tier band uses governed score (the team's acknowledged reality).
            tier = self._tier_for(gov_rate, thresholds_map.get(dim, thresholds_map["*"]))
            weighted = (agg["gov_w_num"] / agg["w_den"]) if (weighting_on and agg["w_den"]) else None

            row = await self.score_repo.insert_score(
                tenant_id=tenant_id, profile_id=profile_id, scan_id=scan_id,
                scope_type="profile", scope_key="",
                dimension=dim,
                # `pass_rate` is the user-facing headline; we surface the
                # governed view there since that's what the tier band uses.
                pass_rate=_round5(gov_rate if gov_rate is not None else 0.0),
                rule_count=rule_count,
                pass_count=agg.get("pass", 0),
                fail_count=agg.get("fail", 0),
                error_count=agg.get("error", 0),
                raw_score=_round5(raw_rate if raw_rate is not None else 0.0),
                governed_score=_round5(gov_rate if gov_rate is not None else 0.0),
                tier=tier,
                thresholds_snapshot={**snapshot, "exceptions_applied": agg["exception_count"]},
                weighted_score=_round5(weighted) if weighted is not None else None,
            )
            persisted.append(row)

            overall["raw_sum"] += agg["raw_sum"]
            overall["gov_sum"] += agg["gov_sum"]
            overall["eligible"] += eligible
            overall["pass"] += agg.get("pass", 0)
            overall["fail"] += agg.get("fail", 0)
            overall["error"] += agg.get("error", 0)
            overall["raw_w_num"] += agg["raw_w_num"]
            overall["gov_w_num"] += agg["gov_w_num"]
            overall["w_den"] += agg["w_den"]
            overall["exception_count"] += agg["exception_count"]

        elig = overall["eligible"]
        raw_overall = (overall["raw_sum"] / elig) if elig else None
        gov_overall = (overall["gov_sum"] / elig) if elig else None
        tier_overall = self._tier_for(
            gov_overall, thresholds_map.get("overall", thresholds_map["*"]),
        )
        weighted_overall = (overall["gov_w_num"] / overall["w_den"]) if (
            weighting_on and overall["w_den"]) else None
        total_rules = overall["pass"] + overall["fail"] + overall["error"]
        overall_row = await self.score_repo.insert_score(
            tenant_id=tenant_id, profile_id=profile_id, scan_id=scan_id,
            scope_type="profile", scope_key="",
            dimension="overall",
            pass_rate=_round5(gov_overall if gov_overall is not None else 0.0),
            rule_count=total_rules,
            pass_count=overall["pass"], fail_count=overall["fail"], error_count=overall["error"],
            raw_score=_round5(raw_overall if raw_overall is not None else 0.0),
            governed_score=_round5(gov_overall if gov_overall is not None else 0.0),
            tier=tier_overall,
            thresholds_snapshot={**snapshot, "exceptions_applied": overall["exception_count"]},
            weighted_score=_round5(weighted_overall) if weighted_overall is not None else None,
        )
        persisted.append(overall_row)
        return persisted

    # ------------------------------------------------------------------
    # Read paths used by the metrics router.
    # ------------------------------------------------------------------

    async def get_metrics_for_profile(
        self, *, tenant_id: int, profile_id: int,
    ) -> dict:
        """Build the Metrics-tab payload: latest dimension scores + delta vs
        previous scan + a per-rule occurrences table for the latest scan."""
        latest = await self.score_repo.latest_for_profile(
            tenant_id=tenant_id, profile_id=profile_id,
        )
        if not latest:
            return {
                "scan_id": None,
                "dimensions": [],
                "overall": None,
                "rule_occurrences": [],
                "thresholds": (await self._load_thresholds(tenant_id))[2],
            }

        scan_id = latest[0]["scan_id"]
        dimensions = []
        overall = None
        for r in latest:
            payload = {
                "dimension": r["dimension"],
                "pass_rate": _flt(r["pass_rate"]),
                "rule_count": r["rule_count"],
                "pass_count": r["pass_count"],
                "fail_count": r["fail_count"],
                "error_count": r["error_count"],
                "raw_score": _flt(r["raw_score"]),
                "governed_score": _flt(r["governed_score"]),
                "weighted_score": _flt(r["weighted_score"]),
                "tier": r["tier"],
                "prev_pass_rate": _flt(r.get("prev_pass_rate")),
                "delta": _delta(r["pass_rate"], r.get("prev_pass_rate")),
                "scan_id": r["scan_id"],
                "computed_at": r["computed_at"],
            }
            if r["dimension"] == "overall":
                overall = payload
            else:
                dimensions.append(payload)

        rule_occ = await self.score_repo.rule_occurrences_for_scan(
            tenant_id=tenant_id, scan_id=scan_id,
        )

        # Mark which rule occurrences are covered by an active exception so
        # the UI can render the "Suppressed" badge + de-emphasize them.
        from app.products.data_quality.repositories.exception_repository import (
            ExceptionRepository,
        )
        exc_by_rule = await ExceptionRepository().find_active_for_scan(
            tenant_id=tenant_id, scan_id=scan_id,
        )

        return {
            "scan_id": scan_id,
            "dimensions": dimensions,
            "overall": overall,
            "active_exception_count": len(exc_by_rule),
            "rule_occurrences": [
                {
                    "issue_id": r["issue_id"],
                    "active_rule_id": r["active_rule_id"],
                    "column_name": r["column_name"],
                    "concept": r["concept"],
                    "concept_description": r.get("concept_description"),
                    "dimension": r["dimension"],
                    "rule_type": r["rule_type"],
                    "severity": r["severity"],
                    "row_count": r["row_count"],
                    "violation_count": r["violation_count"],
                    "violation_rate": _flt(r["violation_rate"]),
                    "pass_rate": _flt(r["pass_rate"]),
                    "status": r["status"],
                    "diagnostic_text": r["diagnostic_text"],
                    "created_at": r["created_at"],
                    # Step 5 — UI tags suppressed rows with a badge.
                    "suppressed": r["active_rule_id"] in exc_by_rule,
                    "exception_id": (exc_by_rule.get(r["active_rule_id"]) or {}).get("id"),
                }
                for r in rule_occ
            ],
            "thresholds": (await self._load_thresholds(tenant_id))[2],
        }

    async def get_trend_for_profile(
        self, *, tenant_id: int, profile_id: int, limit: int = 50,
    ) -> list[dict]:
        rows = await self.score_repo.trend_for_profile(
            tenant_id=tenant_id, profile_id=profile_id, limit=limit,
        )
        return [
            {
                "scan_id": r["scan_id"],
                "dimension": r["dimension"],
                "pass_rate": _flt(r["pass_rate"]),
                "tier": r["tier"],
                "rule_count": r["rule_count"],
                "finished_at": r["finished_at"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Thresholds
    # ------------------------------------------------------------------

    async def _load_thresholds(
        self, tenant_id: int,
    ) -> tuple[dict, bool, dict]:
        """Return (per-dimension thresholds map, severity_weighting_on,
        snapshot dict). Falls back to BRD defaults if the tenant has no row."""
        rows = await self.score_repo.get_thresholds_for_tenant(tenant_id)
        thresholds = {
            "*": {"good_min": _DEFAULT_GOOD_MIN, "acceptable_min": _DEFAULT_ACCEPTABLE_MIN},
        }
        weighting = False
        for r in rows:
            thresholds[r["dimension"]] = {
                "good_min": float(r["good_min"]),
                "acceptable_min": float(r["acceptable_min"]),
            }
            # Tenant-level switch lives on the '*' (default) row.
            if r["dimension"] == "*" and r["severity_weighting_enabled"]:
                weighting = True
        snapshot = {
            "thresholds": thresholds,
            "severity_weighting_enabled": weighting,
            "severity_weights": _SEVERITY_WEIGHTS,
        }
        return thresholds, weighting, snapshot

    @staticmethod
    def _tier_for(pass_rate: float | None, bands: dict) -> str:
        if pass_rate is None:
            return "no_rules"
        if pass_rate >= bands["good_min"]:
            return "good"
        if pass_rate >= bands["acceptable_min"]:
            return "acceptable"
        return "not_acceptable"


def _round5(v: float | None) -> float | None:
    return round(v, 5) if v is not None else None


def _flt(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _delta(curr, prev) -> float | None:
    """Signed delta in pass-rate points (e.g. +0.04 = ↑4 pp)."""
    if curr is None or prev is None:
        return None
    try:
        return round(float(curr) - float(prev), 5)
    except (TypeError, ValueError):
        return None


def get_scoring_service() -> ScoringService:
    return ScoringService()

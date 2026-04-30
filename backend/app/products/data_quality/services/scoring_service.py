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
    """

    async def aggregate_for_scan(self, *, tenant_id: int, scan_id: int) -> list[dict]:
        return await self._fetch_all(
            """SELECT
                  dimension,
                  severity,
                  status,
                  COUNT(*) AS n,
                  COALESCE(SUM(1 - COALESCE(violation_rate, 0)), 0) AS sum_pass
                FROM dq.t_dq_issues
               WHERE tenant_id = $1 AND scan_id = $2
            GROUP BY dimension, severity, status""",
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
        re-invoked on the same scan."""
        rows = await self._issue_reader.aggregate_for_scan(
            tenant_id=tenant_id, scan_id=scan_id,
        )
        thresholds_map, weighting_on, snapshot = await self._load_thresholds(tenant_id)

        # Bucket the aggregate rows.
        per_dim: dict[str, dict] = {
            d: {"sum_pass": 0.0, "rule_count": 0, "pass": 0,
                "fail": 0, "error": 0, "weighted_sum": 0.0, "weight_sum": 0.0}
            for d in _DIMENSIONS
        }
        for r in rows:
            dim = r["dimension"]
            if dim not in per_dim:
                continue
            n = int(r["n"])
            sp = float(r["sum_pass"])
            status = r["status"]
            severity = r["severity"]
            per_dim[dim]["rule_count"] += n
            per_dim[dim][status] = per_dim[dim].get(status, 0) + n
            # Errors don't have a meaningful pass_rate — exclude from raw.
            if status in ("pass", "fail"):
                per_dim[dim]["sum_pass"] += sp
                w = _SEVERITY_WEIGHTS.get(severity, 1.0)
                per_dim[dim]["weighted_sum"] += sp * w
                per_dim[dim]["weight_sum"] += n * w

        persisted: list[dict] = []

        # Per-dimension rows.
        overall_sum_pass = 0.0
        overall_eligible = 0
        overall_pass = overall_fail = overall_error = 0
        overall_w_num = overall_w_den = 0.0

        for dim in _DIMENSIONS:
            agg = per_dim[dim]
            eligible = agg["pass"] + agg["fail"]
            rule_count = agg["rule_count"]
            pass_rate = (agg["sum_pass"] / eligible) if eligible else None
            tier = self._tier_for(pass_rate, thresholds_map.get(dim, thresholds_map["*"]))
            weighted = (agg["weighted_sum"] / agg["weight_sum"]) if (weighting_on and agg["weight_sum"]) else None

            row = await self.score_repo.insert_score(
                tenant_id=tenant_id, profile_id=profile_id, scan_id=scan_id,
                scope_type="profile", scope_key="",
                dimension=dim,
                pass_rate=_round5(pass_rate if pass_rate is not None else 0.0),
                rule_count=rule_count,
                pass_count=agg.get("pass", 0),
                fail_count=agg.get("fail", 0),
                error_count=agg.get("error", 0),
                raw_score=_round5(pass_rate if pass_rate is not None else 0.0),
                governed_score=_round5(pass_rate if pass_rate is not None else 0.0),
                tier=tier,
                thresholds_snapshot=snapshot,
                weighted_score=_round5(weighted) if weighted is not None else None,
            )
            persisted.append(row)

            overall_sum_pass += agg["sum_pass"]
            overall_eligible += eligible
            overall_pass += agg.get("pass", 0)
            overall_fail += agg.get("fail", 0)
            overall_error += agg.get("error", 0)
            overall_w_num += agg["weighted_sum"]
            overall_w_den += agg["weight_sum"]

        # Overall row — one score across every dimension's eligible rules.
        overall_rate = (overall_sum_pass / overall_eligible) if overall_eligible else None
        overall_tier = self._tier_for(
            overall_rate, thresholds_map.get("overall", thresholds_map["*"]),
        )
        overall_weighted = (overall_w_num / overall_w_den) if (weighting_on and overall_w_den) else None
        total_rules = overall_pass + overall_fail + overall_error
        overall_row = await self.score_repo.insert_score(
            tenant_id=tenant_id, profile_id=profile_id, scan_id=scan_id,
            scope_type="profile", scope_key="",
            dimension="overall",
            pass_rate=_round5(overall_rate if overall_rate is not None else 0.0),
            rule_count=total_rules,
            pass_count=overall_pass, fail_count=overall_fail, error_count=overall_error,
            raw_score=_round5(overall_rate if overall_rate is not None else 0.0),
            governed_score=_round5(overall_rate if overall_rate is not None else 0.0),
            tier=overall_tier,
            thresholds_snapshot=snapshot,
            weighted_score=_round5(overall_weighted) if overall_weighted is not None else None,
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

        return {
            "scan_id": scan_id,
            "dimensions": dimensions,
            "overall": overall,
            "rule_occurrences": [
                {
                    "issue_id": r["issue_id"],
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

"""Stage E — verify the NDI scoring formula encoded in scoring/formula.py.

National-Data-Index_v1.0_AR.pdf is the source for the score formula.  The
formula itself lives in code (scoring/formula.py) — this stage exists only
to (a) record the file hash in the seed-run audit row, and (b) cheaply
smoke-test the compute_ndi_score function on a synthetic input so we can
detect regressions in future seeder runs.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from app.products.ndmo_compliance.scoring.formula import compute_ndi_score

from .models import ParseReport

logger = logging.getLogger(__name__)


def verify_ndi_formula(ndi_pdf_path: Path) -> tuple[dict[str, str], ParseReport]:
    """Hash the NDI PDF + run a smoke calculation.  Returns the hash payload."""
    report = ParseReport(stage="E.parse_ndi_formula")
    payload: dict[str, str] = {}

    ndi_pdf_path = Path(ndi_pdf_path)
    if not ndi_pdf_path.exists():
        report.errors.append(f"National-Data-Index PDF not found: {ndi_pdf_path}")
        return payload, report

    digest = hashlib.sha256(ndi_pdf_path.read_bytes()).hexdigest()
    payload[ndi_pdf_path.name] = digest

    # Smoke test: 3 specs, two at "Activated" and one at "Building".
    smoke_input = [
        {"spec_code": "DG.1.1", "domain_code": "DG", "priority": 1, "maturity": 3},
        {"spec_code": "DG.1.2", "domain_code": "DG", "priority": 1, "maturity": 1},
        {"spec_code": "MCM.3.1", "domain_code": "MCM", "priority": 2, "maturity": 3},
    ]
    breakdown = compute_ndi_score(smoke_input, active_priorities=[1, 2])

    if not 0.0 <= breakdown.score_percent <= 100.0:
        report.errors.append(
            f"compute_ndi_score produced out-of-range value: {breakdown.score_percent}"
        )
    report.counts = {
        "ndi_pdf_hashed": 1,
        "smoke_test_score_percent_x100": int(breakdown.score_percent * 100),
    }
    logger.info("NDI formula smoke test: score=%.2f%% (input=%d specs)",
                breakdown.score_percent, len(smoke_input))
    return payload, report


__all__ = ["verify_ndi_formula"]

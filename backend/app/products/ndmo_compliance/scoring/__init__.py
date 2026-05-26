"""NDI score calculation for NDMO Compliance.

The formula is encoded as Python, not data — it's derived once from the
National-Data-Index_v1.0_AR.pdf reference document and lives in formula.py.
"""

from .formula import compute_ndi_score, NdiScoreBreakdown

__all__ = ["compute_ndi_score", "NdiScoreBreakdown"]

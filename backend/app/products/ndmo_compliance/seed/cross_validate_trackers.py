"""Stage D — extract evidence codes from the 13 Tracker xlsx files AND
cross-validate per domain.

Phase-1 reconciliation learning: Tracker files use the "evidence code"
scheme (XX.M.N for mandatory evidence, XX.C.N(.N){1,3} for compliance/
acceptance checks).  They do NOT carry the DMS hierarchical spec codes,
so cross-validation cannot work at the spec-code level.

Reframed scope:
  1. Extract every evidence row from each Tracker's "قائمة المتطلبات" sheet.
     Each row has: standard name (e.g. "الأول – الخطة"), maturity level
     (e.g. "البناء (1)"), evidence code (e.g. "BIA.M.1"), evidence name,
     evidence description.
  2. Group by (domain, control_ordinal_from_standard_name, maturity_level).
  3. Return the data as a mapping ready to be merged into each spec's
     `maturity_levels[level].evidence_codes` JSONB on the runner side.
  4. Emit a per-domain count comparison: standards_in_tracker vs
     standards_in_dms (= controls), as the reconciliation metric.

PDP_Tracker_HaniAlharthi.xlsx is excluded per the project guardrail
("any Tracker file named after a person").
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .models import ParseReport
from .parse_dms_pdf import ASSESSABLE_DOMAINS
from .parse_xlsx_template import ARABIC_ORDINALS

logger = logging.getLogger(__name__)

_TRACKER_FILENAMES: dict[str, str] = {
    "BIA":  "BIA_Tracker.xlsx",
    "DAM":  "DAM_Tracker.xlsx",
    "DC":   "DC_Tracker.xlsx",
    "DCM":  "DCM_Tracker.xlsx",
    "DG":   "DG Tracker.xlsx",      # filename uses space, not underscore
    "DO":   "DO_Tracker.xlsx",
    "DQ":   "DQ_Tracker.xlsx",
    "DSI":  "DSI_Tracker.xlsx",
    "DVR":  "DVR_Tracker.xlsx",
    "FOI":  "FOI_Tracker.xlsx",
    "MCM":  "MCM_Tracker.xlsx",
    "OD":   "OD_Tracker.xlsx",
    "RMD":  "RMD_Tracker.xlsx",
}

_EVIDENCE_RE = re.compile(r"\b([A-Z]{2,4})\.(M|C)(?:\.\d+){1,3}\b")
_LEVEL_NUM_RE = re.compile(r"\(([0-5])\)")          # "البناء (1)" → 1   (BIA-tracker style)
_LEVEL_ARABIC_DIGIT = re.compile(r"\(([٠-٥])\)")
# "1 – البناء" → 1   (DG-tracker style: digit at start, possibly followed by separator)
_LEVEL_LEADING = re.compile(r"^\s*([٠-٥0-5])\s*[–\-—:]")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Sheet names where the per-evidence rows live.  Observed variants across
# the 13 Tracker files: "قائمة المتطلبات" (BIA-style), "متطلبات <domain>"
# (DG-style, e.g. "متطلبات DG"), and the bare Arabic word "متطلبات".
def _is_requirements_sheet(name: str) -> bool:
    if not isinstance(name, str):
        return False
    norm = unicodedata.normalize("NFKC", name).strip()
    return "متطلبات" in norm or "المتطلبات" in norm

# Column-header synonyms observed across the Trackers.
_COL_STANDARD = ("المعيار",)
_COL_LEVEL = ("مستوى النضج", "المستوى", "مستوى")
_COL_CODE = ("رمز الوثيقة", "رمز الدليل", "رمز المتطلب")
_COL_NAME = ("اسم الوثيقة", "اسم الدليل", "اسم المتطلب")
_COL_DESC = ("وصف الوثيقة", "وصف الدليل", "وصف المتطلب")


def _resolve_col(headers: list[Any], synonyms: tuple[str, ...]) -> int | None:
    for i, h in enumerate(headers):
        if not isinstance(h, str):
            continue
        norm = unicodedata.normalize("NFKC", h).strip()
        for syn in synonyms:
            if syn in norm:
                return i
    return None


def extract_tracker_evidence(
    input_dir: Path,
    dms_control_codes: set[str],
) -> tuple[dict[str, dict[int, list[dict[str, Any]]]], dict[str, Any], ParseReport]:
    """Return:
      * by_control[dms_code][level_int] = [ {code, name_ar, description_ar}, ... ]
      * per_domain_summary = { dom: { standards_in_tracker, evidence_total,
                                       standards_in_dms } }
      * report
    """
    input_dir = Path(input_dir)
    report = ParseReport(stage="D.extract_tracker_evidence")

    by_control: dict[str, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    per_domain_summary: dict[str, Any] = {}
    trackers_parsed: list[str] = []
    trackers_missing: list[str] = []
    standards_unmapped: list[str] = []

    for domain_code, fname in _TRACKER_FILENAMES.items():
        path = input_dir / fname
        if not path.exists():
            trackers_missing.append(fname)
            continue
        try:
            domain_evidence, ordinals_seen = _extract_one(path, domain_code, standards_unmapped)
        except Exception as exc:  # noqa: BLE001
            report.errors.append(f"{fname}: {exc}")
            continue
        trackers_parsed.append(fname)

        for control_ordinal, by_level in domain_evidence.items():
            dms_code = f"{domain_code}.{control_ordinal}"
            for level, evidence_list in by_level.items():
                by_control[dms_code][level].extend(evidence_list)

        # Per-domain summary
        dms_controls_for_domain = sorted(
            c for c in dms_control_codes if c.startswith(domain_code + ".")
        )
        per_domain_summary[domain_code] = {
            "tracker_file": fname,
            "standards_in_tracker": sorted(ordinals_seen),
            "standards_in_dms": [int(c.split(".")[1]) for c in dms_controls_for_domain],
            "evidence_total": sum(len(v) for d in domain_evidence.values() for v in d.values()),
        }

    report.counts = {
        "trackers_parsed": len(trackers_parsed),
        "trackers_missing": len(trackers_missing),
        "controls_with_evidence_codes": len(by_control),
        "evidence_codes_total": sum(len(v) for d in by_control.values() for v in d.values()),
        "standards_with_no_ordinal_match": len(standards_unmapped),
    }
    if standards_unmapped:
        report.warnings.append(
            f"{len(standards_unmapped)} standard label(s) in Trackers did not "
            f"contain a known Arabic ordinal; first few: {standards_unmapped[:3]}"
        )
    if "PDP" not in (d for d in _TRACKER_FILENAMES if (input_dir / _TRACKER_FILENAMES[d]).exists()):
        report.warnings.append(
            "PDP Tracker intentionally excluded (PDP_Tracker_HaniAlharthi.xlsx "
            "carries a person's name per the project guardrail)."
        )

    return dict(by_control), per_domain_summary, report


def _extract_one(
    path: Path,
    domain_code: str,
    standards_unmapped: list[str],
) -> tuple[dict[int, dict[int, list[dict[str, Any]]]], set[int]]:
    """Pull evidence rows from one Tracker file.

    Returns (per_control_per_level_evidence, ordinals_seen).
    """
    wb = load_workbook(path, data_only=True)
    # Pick the first sheet whose name contains "متطلبات".
    req_sheet_name = next(
        (s for s in wb.sheetnames if _is_requirements_sheet(s)), None
    )
    if req_sheet_name is None:
        return {}, set()
    ws = wb[req_sheet_name]

    # Find the header row — the one containing "المعيار" plus a code-column synonym.
    rows: list[list[Any]] = [[_norm(c) for c in r] for r in ws.iter_rows(values_only=True)]
    header_idx: int | None = None
    for i, row in enumerate(rows):
        joined = " ".join(str(c) for c in row if isinstance(c, str))
        if "المعيار" in joined and any(syn in joined for syn in _COL_CODE):
            header_idx = i
            break
    if header_idx is None:
        return {}, set()

    headers = rows[header_idx]
    idx_standard = _resolve_col(headers, _COL_STANDARD)
    idx_level = _resolve_col(headers, _COL_LEVEL)
    idx_code = _resolve_col(headers, _COL_CODE)
    idx_name = _resolve_col(headers, _COL_NAME)
    idx_desc = _resolve_col(headers, _COL_DESC)

    by_control: dict[int, dict[int, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    ordinals_seen: set[int] = set()

    for r_idx in range(header_idx + 1, len(rows)):
        row = rows[r_idx]
        if all(c in (None, "") for c in row):
            continue
        standard = row[idx_standard] if idx_standard is not None and idx_standard < len(row) else None
        level_cell = row[idx_level] if idx_level is not None and idx_level < len(row) else None
        code_cell = row[idx_code] if idx_code is not None and idx_code < len(row) else None
        name_cell = row[idx_name] if idx_name is not None and idx_name < len(row) else None
        desc_cell = row[idx_desc] if idx_desc is not None and idx_desc < len(row) else None

        ordinal = _ordinal_from_standard_label(standard)
        if ordinal is None:
            if isinstance(standard, str) and standard.strip():
                standards_unmapped.append(f"{domain_code}::{standard[:40]}")
            continue
        ordinals_seen.add(ordinal)

        level_int = _level_from_label(level_cell)
        if level_int is None:
            continue

        # Some rows have multiple codes squished into one cell (rare); split.
        codes: list[str] = []
        if isinstance(code_cell, str):
            for m in _EVIDENCE_RE.finditer(code_cell):
                if m.group(1) == domain_code:
                    codes.append(m.group(0))
            if not codes and code_cell.strip():
                # capture even if regex misses (will surface in audit)
                codes.append(code_cell.strip())

        for c in codes:
            by_control[ordinal][level_int].append({
                "code": c,
                "name_ar": name_cell if isinstance(name_cell, str) else None,
                "description_ar": desc_cell if isinstance(desc_cell, str) else None,
                "source": "tracker_xlsx",
            })

    return dict(by_control), ordinals_seen


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return unicodedata.normalize("NFKC", v).strip()
    return v


def _ordinal_from_standard_label(label: Any) -> int | None:
    """'الأول – الخطة' → 1."""
    if not isinstance(label, str):
        return None
    for word, n in ARABIC_ORDINALS.items():
        if word in label:
            return n
    return None


def _level_from_label(label: Any) -> int | None:
    """Recover the integer level from any of the observed label shapes.

    Handles:
      * 'البناء (1)'       → 1  (BIA, DAM, RMD-style)
      * 'البناء (١)'       → 1  (Arabic-Indic digit variant)
      * '1 – البناء'       → 1  (DG, DCM, OD-style leading digit)
      * 'مستوى 2'          → 2
    """
    if not isinstance(label, str):
        return None
    m = _LEVEL_NUM_RE.search(label)
    if m:
        return int(m.group(1))
    m = _LEVEL_ARABIC_DIGIT.search(label)
    if m:
        return int(m.group(1).translate(_AR_DIGITS))
    m = _LEVEL_LEADING.search(label)
    if m:
        return int(m.group(1).translate(_AR_DIGITS))
    # last resort: any digit 0–5 anywhere in the label
    m = re.search(r"[٠-٥0-5]", label)
    if m:
        d = m.group(0).translate(_AR_DIGITS)
        try:
            v = int(d)
            if 0 <= v <= 5:
                return v
        except ValueError:
            return None
    return None


__all__ = ["extract_tracker_evidence"]

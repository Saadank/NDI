"""Stage B — parse the نضيء (nudaa) structured template xlsx.

__مؤشر نضيء_-d9a5d936.xlsx (newest version) is the NDMO-published per-control
structured template.  Key insight learned during Phase 1 reconciliation:

  * The xlsx uses code format "XX.MO.N" (or "XX.MQ.N" — a Y-to-Q typo for some
    rows in the original).
  * Each "standard" in the xlsx maps to a CONTROL (not a specification) in
    the DMS hierarchy.  Ordinal 1 → XX.1, ordinal 2 → XX.2, …
  * Each control row block contains 5–10 sub-rows, one per maturity level,
    with description text and evidence-code references in column H.

Layout (observed in the DG sheet):

    R5  : "المعيار الأول"
    R6  : code DG.MO.1 | name | question | "مستوى 0: …" | desc | evidence | …
    R7  :                                  "مستوى 1: …" | desc | …
    …
    R16 : "المعيار الثاني"
    R17 : code DG.MQ.2 | …

Output: dict keyed by *control code* in DMS form (e.g. "DG.1"), containing
the rich per-control data ready to be merged onto every child SpecRow's
`required_elements` JSONB.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from .models import ParseReport

logger = logging.getLogger(__name__)

# Tolerant code regex: accepts both "MO" (correct) and "MQ" (source typo).
_STD_CODE_RE = re.compile(r"\b([A-Z]{2,4})\.M[OQ]\.(\d+)\b")

# Acceptance-evidence and mandatory-evidence codes in column H.
_EVIDENCE_RE = re.compile(r"\b([A-Z]{2,4})\.(M|C)(?:\.\d+){1,3}\b")

# Arabic ordinals → integer.  Includes the observed typo "الثاالث" (extra alef).
ARABIC_ORDINALS: dict[str, int] = {
    "الأول": 1, "الأوّل": 1, "الاول": 1,
    "الثاني": 2, "الثانى": 2,
    "الثالث": 3, "الثاالث": 3, "الثلاث": 3,
    "الرابع": 4,
    "الخامس": 5,
    "السادس": 6,
    "السابع": 7,
    "الثامن": 8,
}

# Maturity-level header in column D ("مستوى 0: …" / "مستوى ١: …").
_LEVEL_HEADER_RE = re.compile(r"مستوى\s*([٠-٥0-5])")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_xlsx_template(xlsx_path: Path) -> tuple[dict[str, dict[str, Any]], ParseReport]:
    """Return ``{ control_code -> required_elements_payload }`` + report."""
    xlsx_path = Path(xlsx_path)
    report = ParseReport(stage="B.parse_xlsx_template")
    by_control: dict[str, dict[str, Any]] = {}

    if not xlsx_path.exists():
        report.errors.append(f"File not found: {xlsx_path}")
        return by_control, report

    wb = load_workbook(xlsx_path, data_only=True)

    for sheet_name in wb.sheetnames:
        # Sheet names ARE the domain codes (DG, BIA, ...).
        domain_code = sheet_name.strip().upper()
        ws = wb[sheet_name]

        # First pass: scan column A for ordinal markers + their adjacent code row.
        standards: list[dict[str, Any]] = []
        rows: list[list[Any]] = [list(r) for r in ws.iter_rows(values_only=True)]
        for i, row in enumerate(rows):
            a = _norm(row[0]) if row else None
            if not isinstance(a, str):
                continue
            ordinal = _arabic_ordinal_in(a)
            if ordinal is None:
                continue
            # Look at the very next row for the code; tolerate gap of up to 2 rows.
            code_str = None
            code_row_idx = None
            for j in range(i + 1, min(len(rows), i + 4)):
                next_a = _norm(rows[j][0]) if rows[j] else None
                if isinstance(next_a, str) and _STD_CODE_RE.search(next_a):
                    code_str = _STD_CODE_RE.search(next_a).group(0)
                    code_row_idx = j
                    break
            if code_str is None:
                continue
            standards.append({
                "ordinal": ordinal,
                "nudaa_code": code_str,
                "code_row_idx": code_row_idx,
                "header_row_idx": i,
                "_typo": ".MQ." in code_str,
            })

        # Determine the row range that "belongs to" each standard.
        for k, std in enumerate(standards):
            start = std["code_row_idx"]
            end = standards[k + 1]["header_row_idx"] if k + 1 < len(standards) else len(rows)

            # Pull the standard name (col B), question (col C), and walk level
            # descriptions + evidence codes across the block.
            name_ar = _norm(rows[start][1]) if len(rows[start]) > 1 else None
            question_ar = _norm(rows[start][2]) if len(rows[start]) > 2 else None
            level_data: dict[str, dict[str, Any]] = {}
            evidence_codes_seen: list[str] = []

            current_level: str | None = None
            for r_idx in range(start, end):
                row = rows[r_idx]
                # Level header in column D
                col_d = _norm(row[3]) if len(row) > 3 else None
                if isinstance(col_d, str):
                    m = _LEVEL_HEADER_RE.search(col_d)
                    if m:
                        lvl = int(m.group(1).translate(_AR_DIGITS))
                        if 0 <= lvl <= 5:
                            current_level = str(lvl)
                            level_data.setdefault(current_level, {
                                "name_ar": col_d.split(":")[-1].strip() if ":" in col_d else col_d,
                                "description_ar": "",
                                "evidence_codes": [],
                            })
                # Level description in column E
                col_e = _norm(row[4]) if len(row) > 4 else None
                if isinstance(col_e, str) and current_level is not None:
                    if not level_data[current_level]["description_ar"]:
                        level_data[current_level]["description_ar"] = col_e
                # Evidence code in column H
                col_h = _norm(row[7]) if len(row) > 7 else None
                if isinstance(col_h, str):
                    for em in _EVIDENCE_RE.finditer(col_h):
                        ev_code = em.group(0)
                        evidence_codes_seen.append(ev_code)
                        if current_level is not None:
                            level_data[current_level]["evidence_codes"].append({
                                "code": ev_code,
                                "source": "xlsx_template",
                            })

            # DMS control = "<DOMAIN>.<ordinal>"
            dms_control = f"{domain_code}.{std['ordinal']}"
            by_control[dms_control] = {
                "nudaa_codes": [std["nudaa_code"]],
                "nudaa_typo": std["_typo"],
                "standard_name_ar": name_ar,
                "standard_question_ar": question_ar,
                "standard_ordinal": std["ordinal"],
                "source_sheet": sheet_name,
                "level_descriptions": level_data,
                "evidence_codes_from_xlsx": evidence_codes_seen,
            }

    report.counts = {
        "controls_extracted_from_xlsx": len(by_control),
        "typos_seen": sum(1 for v in by_control.values() if v.get("nudaa_typo")),
        "evidence_codes_total": sum(len(v.get("evidence_codes_from_xlsx", []))
                                    for v in by_control.values()),
    }
    if len(by_control) < 30:
        report.warnings.append(
            f"Only {len(by_control)} controls extracted from xlsx; "
            f"expected ~50–77.  The xlsx may be a partial template."
        )
    return by_control, report


# ---------- helpers -------------------------------------------------------- #


def _norm(v: Any) -> Any:
    if isinstance(v, str):
        return unicodedata.normalize("NFKC", v).strip()
    return v


def _arabic_ordinal_in(text: str) -> int | None:
    """Return the ordinal integer if ``text`` contains an Arabic ordinal word."""
    for word, n in ARABIC_ORDINALS.items():
        if word in text:
            return n
    return None


__all__ = ["parse_xlsx_template", "ARABIC_ORDINALS"]

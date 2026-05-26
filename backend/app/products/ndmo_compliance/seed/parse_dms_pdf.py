"""Stage A — parse the master DMS standards PDF.

DataManagementPersonalDataProtectionStandardsAr.pdf publishes the NDMO data
management & PDP standards.  We extract:

  * 14 assessable domains (BIA, DAM, DC, DCM, DG, DO, DQ, DSI, DVR, FOI,
    MCM, OD, PDP, RMD).  The 15th NDMO domain — Data Security & Protection —
    is in scope of the PDF but explicitly NOT assessable per the project
    spec; we skip it.
  * 77 controls (e.g. DG.1, MCM.3).
  * ~190 specifications.  Two numbering conventions appear in the source:
      - dotted:    DG.1.1, BIA.3.2
      - non-dotted: DC1.1, DC2.3   (DC domain only)
    We normalise both to the dotted form when storing.
  * Priority per spec (1 / 2 / 3) from the Arabic `أولوية ١/٢/٣` label.
  * NCA-conditional flag from the `حسب لوائح وسياسات الهيئة الوطنية للأمن
    السيبراني` annotation.

Strategy: render each page as plain layout-preserving text (which we found
gives reliable column alignment for the DMS PDF specifically), apply the
NFKC + bidi-strip normalisation from our extraction layer, then walk the
text with two regexes — one for control headers, one for spec rows.
"""

from __future__ import annotations

import logging
import re
import subprocess
import unicodedata
from collections import defaultdict
from pathlib import Path

from .models import ControlRow, DomainRow, ParseReport, SpecRow

logger = logging.getLogger(__name__)

# The 14 assessable domain codes (from the project spec).  Anything outside
# this set is rejected as noise (e.g. "SP" from NIST.SP references, "DCL"
# from a malformed "DC.3" tail in the source).
ASSESSABLE_DOMAINS: tuple[str, ...] = (
    "BIA", "DAM", "DC", "DCM", "DG", "DO", "DQ", "DSI",
    "DVR", "FOI", "MCM", "OD", "PDP", "RMD",
)

# Arabic-Indic to ASCII digits map (for priority parsing).
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")

# Bidi & invisible Arabic control chars (same as our extraction module).
_BIDI_CONTROL_RE = re.compile(
    r"[‎‏؜۝۞ۥۦ۩‪‫‬‭‮⁦⁧⁨⁩]"
)


def parse_dms_pdf(pdf_path: Path) -> tuple[list[DomainRow], list[ControlRow], list[SpecRow], ParseReport]:
    """Top-level: returns the assembled hierarchy + a stage report."""
    pdf_path = Path(pdf_path)
    report = ParseReport(stage="A.parse_dms_pdf")

    text = _extract_layout_text(pdf_path)
    text = _clean(text)

    spec_codes, spec_priorities, spec_nca = _scan_spec_codes_and_priorities(text)
    controls = _scan_controls(text, spec_codes)
    domains = _build_domain_rows(spec_codes)
    controls_rows = _build_control_rows(controls)
    spec_rows = _build_spec_rows(spec_codes, spec_priorities, spec_nca)

    # Sanity checks
    report.counts = {
        "domains": len(domains),
        "controls": len(controls_rows),
        "specs": len(spec_rows),
        "priority_1": sum(1 for s in spec_rows if s.priority == 1),
        "priority_2": sum(1 for s in spec_rows if s.priority == 2),
        "priority_3": sum(1 for s in spec_rows if s.priority == 3),
        "nca_conditional": sum(1 for s in spec_rows if s.nca_conditional),
    }
    if len(domains) != 14:
        report.warnings.append(
            f"Expected 14 assessable domains, found {len(domains)}: {sorted(d.code for d in domains)}"
        )
    if len(controls_rows) != 77:
        report.warnings.append(
            f"Expected 77 controls, found {len(controls_rows)}"
        )
    if len(spec_rows) < 190:
        report.warnings.append(
            f"Found {len(spec_rows)} specifications; expected ~190–191. "
            f"Will surface in Tracker cross-validation (stage D)."
        )

    return domains, controls_rows, spec_rows, report


# ---------- low-level helpers --------------------------------------------- #


def _extract_layout_text(pdf_path: Path) -> str:
    """Use pdftotext -layout to preserve column structure.

    PyMuPDF's text extraction reflows blocks in ways that break the DMS
    tabular layout; pdftotext -layout keeps the spec-table columns intact,
    which is what our regexes lean on.
    """
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", str(pdf_path), "-"],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        return proc.stdout
    except FileNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "pdftotext binary not found.  Install poppler-utils (`apt-get "
            "install -y poppler-utils`) or `brew install poppler` on macOS."
        ) from exc


def _clean(text: str) -> str:
    """NFKC + strip bidi control chars.  Mirrors our extraction layer."""
    text = unicodedata.normalize("NFKC", text)
    return _BIDI_CONTROL_RE.sub("", text)


def _scan_spec_codes_and_priorities(text: str) -> tuple[
    dict[str, str],   # code -> raw context line
    dict[str, int],   # code -> 1/2/3 (best guess priority)
    set[str],         # codes flagged NCA-conditional
]:
    """Walk the document line-by-line, collecting every spec row.

    Two code formats coexist in the source:
      * dotted:    DOMAIN.<ctl>.<spec>     e.g. DG.1.1, BIA.3.2
      * non-dotted: DOMAIN<ctl>.<spec>     e.g. DC1.1, DC2.3        (DC only)

    For each, we look back to find the nearest 'أولوية ١/٢/٣' or NCA-clause
    on the same line or one of the few preceding lines.
    """
    dotted = re.compile(r"\b([A-Z]{2,4})\.(\d{1,2})\.(\d{1,2})\b")
    flat = re.compile(r"\b([A-Z]{2,4})(\d{1,2})\.(\d{1,2})\b")
    prio_re = re.compile(r"أولوية\s+([١٢٣123])")
    nca_re = re.compile(r"حسب\s+لوائح")

    spec_codes: dict[str, str] = {}
    spec_priorities: dict[str, int] = {}
    spec_nca: set[str] = set()

    lines = text.splitlines()
    # Build a sliding window over recent lines so we can look back from a
    # spec-code hit to its priority cell.  Pass-1 used 4 lines; observed
    # cases where the priority cell ends up 10+ lines from the code on
    # multi-line table rows in the source layout, so we widen to 18 and
    # narrow forward to 2 (priority cell is almost always BEFORE the code
    # in right-to-left Arabic table layout when rendered LTR by pdftotext).
    window = 18
    fwd_window = 2

    for i, line in enumerate(lines):
        hits: list[tuple[str, str, str]] = []
        for m in dotted.finditer(line):
            dom, ctl, sp = m.group(1), m.group(2), m.group(3)
            if dom in ASSESSABLE_DOMAINS:
                hits.append((dom, ctl, sp))
        for m in flat.finditer(line):
            dom, ctl, sp = m.group(1), m.group(2), m.group(3)
            if dom in ASSESSABLE_DOMAINS:
                # Avoid double-counting: if both regexes find the same code
                # (impossible by definition, since one has a dot and the
                # other doesn't), de-dupe by normalised key below.
                hits.append((dom, ctl, sp))
        if not hits:
            continue

        # Look for priority annotation in a wide back-window + a small
        # forward-window.  Prefer the closest match.
        prio = None
        nca = False
        best_distance = None
        for j in range(max(0, i - window), min(len(lines), i + fwd_window + 1)):
            ml = prio_re.search(lines[j])
            if ml:
                d = abs(j - i)
                if best_distance is None or d < best_distance:
                    prio = int(ml.group(1).translate(_AR_DIGITS))
                    best_distance = d
        for j in range(max(0, i - window), min(len(lines), i + fwd_window + 1)):
            if nca_re.search(lines[j]):
                nca = True
                break

        for dom, ctl, sp in hits:
            code = f"{dom}.{int(ctl)}.{int(sp)}"
            spec_codes[code] = line.strip()
            if prio is not None and code not in spec_priorities:
                spec_priorities[code] = prio
            if nca:
                spec_nca.add(code)

    return spec_codes, spec_priorities, spec_nca


def _scan_controls(text: str, spec_codes: dict[str, str]) -> dict[str, dict[str, str]]:
    """Find every control header (DOMAIN.<n>) and capture its arabic name.

    The DMS PDF emits a control header as a row like:
        DG.1   رقم تعريف الضابط    ... <name> ...   اسم الضابط
    We anchor on the literal "اسم الضابط" tag at the right end of the
    header row and capture the text immediately before it (the control name).
    """
    # All control codes implied by the specs we collected.
    implied = sorted({".".join(c.split(".")[:2]) for c in spec_codes.keys()})
    controls: dict[str, dict[str, str]] = {c: {"name_ar": "", "description_ar": ""} for c in implied}

    # Best-effort name capture.  We sweep the text looking for "DG.1" patterns
    # followed by the control-name signal phrase.
    code_re = re.compile(r"\b([A-Z]{2,4})\.(\d{1,2})(?!\.\d)")
    name_signal = "اسم الضابط"

    lines = text.splitlines()
    for i, line in enumerate(lines):
        for m in code_re.finditer(line):
            dom, ctl = m.group(1), m.group(2)
            if dom not in ASSESSABLE_DOMAINS:
                continue
            code = f"{dom}.{int(ctl)}"
            if code not in controls:
                continue
            # Look on this line and the next two for the name signal phrase.
            for j in range(i, min(len(lines), i + 3)):
                if name_signal in lines[j]:
                    # The name is the run of Arabic between the code and the signal.
                    # We use a tolerant capture: everything between the code and
                    # the phrase, trimmed.
                    text_after = lines[j]
                    idx_sig = text_after.find(name_signal)
                    candidate = text_after[:idx_sig].strip()
                    # Drop the leading "DG.1" if it's at the start.
                    candidate = re.sub(r"^[A-Z]{2,4}\.\d{1,2}\b", "", candidate).strip()
                    candidate = re.sub(r"رقم تعريف الضابط\s*", "", candidate).strip()
                    if candidate and not controls[code]["name_ar"]:
                        controls[code]["name_ar"] = candidate
                    break

    return controls


def _build_domain_rows(spec_codes: dict[str, str]) -> list[DomainRow]:
    domain_names = {
        "BIA": ("ذكاء الأعمال والتحليلات", "Business Intelligence & Analytics"),
        "DAM": ("النمذجة وهيكلة البيانات", "Data Architecture & Modelling"),
        "DC":  ("تصنيف البيانات", "Data Classification"),
        "DCM": ("إدارة المحتوى والوثائق", "Document & Content Management"),
        "DG":  ("حوكمة البيانات", "Data Governance"),
        "DO":  ("تخزين وحفظ البيانات", "Data Storage & Operations"),
        "DQ":  ("جودة البيانات", "Data Quality"),
        "DSI": ("تكامل البيانات ومشاركتها", "Data Sharing & Integration"),
        "DVR": ("تحقيق القيمة من البيانات", "Data Value Realization"),
        "FOI": ("حرية المعلومات", "Freedom of Information"),
        "MCM": ("البيانات الوصفية ودليل البيانات", "Metadata & Catalogue Management"),
        "OD":  ("البيانات المفتوحة", "Open Data"),
        "PDP": ("حماية البيانات الشخصية", "Personal Data Protection"),
        "RMD": ("إدارة البيانات المرجعية والرئيسية", "Reference & Master Data"),
    }
    seen = sorted({c.split(".")[0] for c in spec_codes.keys()})
    rows: list[DomainRow] = []
    for i, code in enumerate(seen):
        name_ar, name_en = domain_names.get(code, (code, code))
        rows.append(DomainRow(code=code, name_ar=name_ar, name_en=name_en, sort_order=i))
    return rows


def _build_control_rows(controls: dict[str, dict[str, str]]) -> list[ControlRow]:
    rows: list[ControlRow] = []
    by_domain_sort: dict[str, int] = defaultdict(int)
    for code in sorted(controls.keys(), key=lambda c: (c.split(".")[0], int(c.split(".")[1]))):
        dom = code.split(".")[0]
        name_ar = controls[code]["name_ar"] or code
        rows.append(
            ControlRow(
                domain_code=dom,
                code=code,
                name_ar=name_ar,
                description_ar=controls[code].get("description_ar"),
                sort_order=by_domain_sort[dom],
            )
        )
        by_domain_sort[dom] += 1
    return rows


def _build_spec_rows(
    spec_codes: dict[str, str],
    spec_priorities: dict[str, int],
    spec_nca: set[str],
) -> list[SpecRow]:
    rows: list[SpecRow] = []
    by_control_sort: dict[str, int] = defaultdict(int)
    for code in sorted(spec_codes.keys(), key=_spec_sort_key):
        parts = code.split(".")
        control = f"{parts[0]}.{parts[1]}"
        priority = spec_priorities.get(code, 0)
        rows.append(
            SpecRow(
                control_code=control,
                code=code,
                name_ar=code,           # filled in by Stage C from the Req PDF
                priority=priority,
                nca_conditional=code in spec_nca,
                raw_source={"dms_pdf_line": spec_codes[code]},
                sort_order=by_control_sort[control],
            )
        )
        by_control_sort[control] += 1
    return rows


def _spec_sort_key(code: str) -> tuple[str, int, int]:
    a, b, c = code.split(".")
    return a, int(b), int(c)


__all__ = ["parse_dms_pdf", "ASSESSABLE_DOMAINS"]

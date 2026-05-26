"""Stage C — parse the 14 domain Req PDFs.

Each `<domain> Req.pdf` carries, per spec:
  * the standard's official question text  -> spec.search_query  (the optimal
    RAG retrieval query)
  * acceptance criteria                    -> spec.acceptance_criteria
  * descriptions of maturity levels 0..5   -> spec.maturity_levels (JSONB)
  * supporting-evidence codes              -> embedded in maturity_levels

Strategy: extract per-page text with our ported PDF extractor, then split
each Req PDF into spec-sized chunks anchored on spec-code occurrences.
For each chunk: take the surrounding sentence as the search_query, and
look for the maturity-level table rows (`المستوى ٠`, `المستوى ١`, ...
`المستوى ٥` or the named equivalents) to build the maturity_levels dict.

This stage is BEST-EFFORT — extraction quality varies across Req PDFs.
Anything we can't parse falls through with a `null` field that the
Phase-2 ingestion layer or a manual editor can fill in later.  Counts and
gaps are surfaced in the ParseReport.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from typing import Any

from app.products.ndmo_compliance.extraction import extract_document

from .models import ParseReport

logger = logging.getLogger(__name__)

# Domain code -> Req-PDF filename (as uploaded).  The "Metadata" Req maps to
# the MCM domain code per the project spec.
DOMAIN_TO_REQ_FILE: dict[str, str] = {
    "BIA":  "BIA Req.pdf",
    "DAM":  "DAM Req.pdf",
    "DC":   "DC Req.pdf",
    "DCM":  "DCM Req.pdf",
    "DG":   "DG Req.pdf",
    "DO":   "DO Req.pdf",
    "DQ":   "DQ Req.pdf",
    "DSI":  "DSI Req.pdf",
    "DVR":  "DVR Req.pdf",
    "FOI":  "FOI Req.pdf",
    "MCM":  "Metadata Req.pdf",
    "OD":   "OD.pdf",                # filename variant — no " Req"
    "PDP":  "PDP Req.pdf",
    "RMD":  "RMD Req.pdf",
}

# Both numbering schemes the standards use.
_CODE_RE = re.compile(r"\b([A-Z]{2,4})\.?(\d{1,2})\.(\d{1,2})\b")

# Maturity-level signal phrases (Arabic).  Multiple shapes are observed
# across the Req PDFs: "المستوى ٠", "مستوى 0:", "المستوى رقم 1", and
# "المستوى الأول/الثاني/...".  Cover all of them.
_LEVEL_HEADER_RE = re.compile(
    r"(?:المستوى|مستوى)\s*(?:رقم\s*)?([٠-٥0-5])"
)
_LEVEL_ORDINAL_RE = re.compile(
    r"(?:المستوى|مستوى)\s+(الأول|الثاني|الثالث|الرابع|الخامس|السادس|الصفر)"
)
_ORDINAL_TO_LEVEL: dict[str, int] = {
    "الصفر": 0, "الأول": 1, "الثاني": 2, "الثالث": 3,
    "الرابع": 4, "الخامس": 5, "السادس": 5,  # SADIS sometimes used as 5 in source
}

_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_all_req_pdfs(
    input_dir: Path,
) -> tuple[dict[str, dict[str, Any]], ParseReport]:
    """Return ``{spec_code: { search_query, acceptance_criteria, maturity_levels, raw_text }}``."""
    input_dir = Path(input_dir)
    report = ParseReport(stage="C.parse_req_pdfs")
    result: dict[str, dict[str, Any]] = {}

    pdfs_found = 0
    for domain_code, fname in DOMAIN_TO_REQ_FILE.items():
        pdf = input_dir / fname
        if not pdf.exists():
            report.warnings.append(f"Missing Req PDF for {domain_code}: {fname}")
            continue
        pdfs_found += 1
        try:
            spec_data = _parse_one_req(pdf, domain_code)
        except Exception as exc:  # noqa: BLE001 — log and continue
            report.errors.append(f"{fname}: {exc}")
            continue
        for code, payload in spec_data.items():
            result.setdefault(code, payload)
        logger.info("Parsed %s -> %d spec entries", fname, len(spec_data))

    report.counts = {
        "req_pdfs_parsed": pdfs_found,
        "specs_with_maturity_levels": sum(1 for v in result.values() if v.get("maturity_levels")),
        "specs_with_search_query": sum(1 for v in result.values() if v.get("search_query")),
        "specs_with_acceptance_criteria": sum(1 for v in result.values() if v.get("acceptance_criteria")),
    }
    return result, report


# ---------- per-PDF parsing ------------------------------------------------ #


def _parse_one_req(pdf: Path, domain_code: str) -> dict[str, dict[str, Any]]:
    """Walk one domain Req PDF and emit a payload per spec code found.

    Observation: the NDMO Req PDFs list every "هل ...؟" question in the
    domain SUMMARY section (before the per-spec deep-dive pages), in the
    same order as the spec codes appear later.  We extract both lists,
    pair by ordinal, and fall back to the in-chunk question if any spec
    code appears after its own question section.
    """
    pages = extract_document(pdf)
    # Process per page to keep the question-extraction regex bounded.
    page_texts = [unicodedata.normalize("NFKC", p.text) for p in pages]
    full_text = "\n\n".join(page_texts)

    # All "هل ...؟" questions in document order, extracted per page (cap each
    # candidate at 300 chars to avoid catastrophic backtracking on docs that
    # have many "هل" tokens but no "؟" near them).
    questions: list[str] = []
    q_re = re.compile(r"هل\s[^\n؟?]{10,300}[؟?]")
    for pt in page_texts:
        for m in q_re.finditer(pt):
            questions.append(m.group(0).strip())
    seen: set[str] = set()
    questions_dedup: list[str] = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            questions_dedup.append(q)

    # All spec codes for this domain, in document order.
    matches = [m for m in _CODE_RE.finditer(full_text) if m.group(1) == domain_code]

    # De-duplicate spec-code list while preserving first-seen order.
    code_first_idx: dict[str, int] = {}
    for m in matches:
        code = f"{m.group(1)}.{int(m.group(2))}.{int(m.group(3))}"
        code_first_idx.setdefault(code, m.start())
    ordered_codes = sorted(code_first_idx.keys(), key=lambda c: code_first_idx[c])

    # Pair question[k] ↔ ordered_codes[k] when both lists line up.
    paired: dict[str, str] = {}
    if questions_dedup and ordered_codes:
        n = min(len(questions_dedup), len(ordered_codes))
        for k in range(n):
            paired[ordered_codes[k]] = questions_dedup[k]

    # Walk per-spec snippets for the remaining fields.
    chunks: list[tuple[str, int, int]] = []
    for idx, code in enumerate(ordered_codes):
        start = code_first_idx[code]
        end = code_first_idx[ordered_codes[idx + 1]] if idx + 1 < len(ordered_codes) else len(full_text)
        chunks.append((code, start, end))

    out: dict[str, dict[str, Any]] = {}
    for code, start, end in chunks:
        snippet = full_text[start:end].strip()
        out[code] = {
            "search_query": paired.get(code) or _extract_question(snippet),
            "acceptance_criteria": _extract_acceptance_criteria(snippet),
            "maturity_levels": _extract_maturity_levels(snippet),
            "raw_text_snippet": snippet[:4000],
            "raw_source_file": pdf.name,
        }
    return out


def _extract_question(snippet: str) -> str | None:
    """Return the first Arabic question sentence found in the snippet.

    NDMO requirement questions almost always start with the interrogative
    "هل" (does/is) and end with "؟".  We anchor on "هل" so we don't accidentally
    return mid-sentence fragments ending in a question mark.
    """
    m = re.search(r"(هل\s[^؟?\n]{10,500}[؟?])", snippet)
    if m:
        return m.group(1).strip()
    # Fallback: any line ending in ؟ or ?
    m = re.search(r"([^.!؟?\n]{20,500}[؟?])", snippet)
    if m:
        return m.group(1).strip()
    return None


def _extract_acceptance_criteria(snippet: str) -> str | None:
    """Best-effort: capture the paragraph following 'معايير القبول' if present."""
    m = re.search(r"معايير\s+القبول[:\s]+(.+?)(?:\n\n|المستوى|$)", snippet, re.DOTALL)
    if m:
        return m.group(1).strip()
    return None


def _extract_maturity_levels(snippet: str) -> dict[str, Any]:
    """Extract per-level descriptions.

    Combines two regex passes:
      * digit form:   "مستوى 0:", "المستوى ٢", "المستوى رقم 3"
      * ordinal form: "المستوى الأول", "المستوى الثاني" ...
    Output: { "0": {description_ar: ...}, ..., "5": {description_ar: ...} }
    """
    levels: dict[str, Any] = {}
    matches: list[tuple[int, int, int]] = []  # (start, end_of_header, level_int)
    for m in _LEVEL_HEADER_RE.finditer(snippet):
        level_str = m.group(1).translate(_AR_DIGITS)
        try:
            lvl = int(level_str)
        except ValueError:
            continue
        if 0 <= lvl <= 5:
            matches.append((m.start(), m.end(), lvl))
    for m in _LEVEL_ORDINAL_RE.finditer(snippet):
        lvl = _ORDINAL_TO_LEVEL.get(m.group(1))
        if lvl is not None:
            matches.append((m.start(), m.end(), lvl))
    matches.sort()
    for i, (_, header_end, lvl) in enumerate(matches):
        next_start = matches[i + 1][0] if i + 1 < len(matches) else min(header_end + 1500, len(snippet))
        body = snippet[header_end:next_start].strip(" :.\n")
        if body and str(lvl) not in levels:
            levels[str(lvl)] = {"description_ar": body[:1500]}
    return levels


__all__ = ["parse_all_req_pdfs", "DOMAIN_TO_REQ_FILE"]

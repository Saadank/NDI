"""Arabic text normalization.

Adapted from content-miner's normalization pipeline, with ONE intentional
deviation from Cortex (documented below).

Source files in content-miner:
  * extractors/file_extractor.py       (NFKC + optional bidi.get_display)
  * extractors/pdf/content_miner_pdf_extractor.py::normalize_text
    (NFKC + bidi-control stripping + ligature fixes + arabic_reshaper.reshape)

Deviation: we DROP the final arabic_reshaper.reshape() call.  Cortex applies
reshape to produce contextual presentation-form ligatures (Unicode FBxx/FExx
blocks) suitable for display in renderers that don't shape Arabic on their
own.  For our pipeline (Claude API + Qdrant retrieval) we want base Arabic
letters (U+0600-06FF) because that is what modern tokenizers and embedders
expect; reshape-form text degrades retrieval recall and LLM accuracy.

To restore exact Cortex parity, re-add `import arabic_reshaper` and append
`text = arabic_reshaper.reshape(text)` at the end of
normalize_for_digital_pdf.
"""

from __future__ import annotations

import re
import unicodedata

from bidi.algorithm import get_display

# Bidi & invisible Arabic control characters that pollute PDF text.
# This is the content-miner regex plus the LRE/RLE/PDF marks we observed
# wrapping every line in the NDMO standards document.
_BIDI_CONTROL_RE = re.compile(
    r"[‎‏؜۝۞ۥۦ۩"
    r"‪‫‬‭‮"
    r"⁦⁧⁨⁩]"
)

# Three concrete ligature fixes that content-miner applies after NFKC.
# These show up in some Saudi government PDFs where the publishing tool
# emitted a non-canonical composed form.
_LIGATURE_FIXES = [
    ("اال", "الا"),
    ("األ", "الأ"),
    ("اإل", "الإ"),
]


def normalize_for_digital_pdf(text: str) -> str:
    """Pipeline applied to text extracted from a *digital* PDF (PyMuPDF).

    Steps (in order — order matters):
      1. strip whitespace
      2. NFKC normalization     -> collapses presentation-form codepoints
                                    (U+FB50–U+FDFF, U+FE70–U+FEFF) to base
                                    Arabic letters (U+0600–U+06FF).
      3. remove bidi/invisible control characters
      4. apply three known ligature fixes

    Note 1: bidi.get_display is intentionally NOT applied here.  Digital-PDF
    text from PyMuPDF is already in logical order; running bidi a second
    time would *reverse* it.  Matches content_miner_pdf_extractor.py
    (the call is present but commented out in the original).

    Note 2: arabic_reshaper.reshape is intentionally NOT applied.  See
    module docstring — we want base letters, not presentation forms.
    """
    text = text.strip()
    text = unicodedata.normalize("NFKC", text)
    text = _BIDI_CONTROL_RE.sub("", text)
    for src, dst in _LIGATURE_FIXES:
        text = text.replace(src, dst)
    return text


def normalize_for_ocr(text: str) -> str:
    """Pipeline applied to text returned by an OCR engine (PaddleOCR).

    Steps:
      1. NFKC normalization
      2. bidi.get_display    -> OCR returns visual (left-to-right reading)
                                order; we convert to logical order for storage.

    Bidi-control stripping and ligature fixes are NOT applied to OCR output —
    OCR doesn't insert those marks.  This mirrors content-miner's file
    extractor (NFKC + optional bidi.get_display when fix_rtl is True).
    """
    text = unicodedata.normalize("NFKC", text)
    text = get_display(text)
    return text

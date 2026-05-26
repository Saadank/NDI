"""Top-level entry point for document extraction.

Dispatches to the right extractor based on a cheap "is this PDF digital?"
heuristic, then chunks the result.

Usage::

    pages = extract_document(Path("/path/to/file.pdf"))
    chunks = chunk_pages(pages)
"""

from __future__ import annotations

import logging
from pathlib import Path

from .chunker import chunk_pages
from .models import Chunk, PageText
from .pdf_text_extractor import extract_digital_pdf, is_digital_pdf

logger = logging.getLogger(__name__)


def extract_document(path: Path) -> list[PageText]:
    """Extract per-page text from any supported file.

    Currently:
      * .pdf — uses PyMuPDF if the PDF is digital; otherwise PaddleOCR.
      * other extensions — caller is expected to convert to PDF first
        (LibreOffice / unoconv) in the storing stage; not handled here.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix != ".pdf":
        raise ValueError(
            f"extract_document currently supports only .pdf; got {suffix}. "
            f"Convert other formats to PDF in the storing stage."
        )

    if is_digital_pdf(path):
        logger.info("Extracting %s via PyMuPDF (digital PDF path)", path.name)
        return extract_digital_pdf(path)

    # Image-only / scanned PDF -> OCR.  Import locally so the PaddleOCR
    # model is not pulled in for the common digital-PDF case.
    logger.info("Extracting %s via PaddleOCR (scanned PDF path)", path.name)
    from .paddle_ocr_extractor import extract_with_paddle_ocr

    return extract_with_paddle_ocr(path)


__all__ = ["extract_document", "chunk_pages", "PageText", "Chunk"]

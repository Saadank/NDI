"""Digital-PDF text extractor — port of ContentMinerPdfExtractor.

Strategy: PyMuPDF gives us text blocks per page; we rasterise each page,
let cv2 detect column gutters, sort blocks by column-then-y, then apply
Arabic normalization (NFKC + bidi-control stripping + ligature fixes +
arabic_reshaper.reshape).  NO bidi.get_display — see arabic_text.py.

Bug fix vs the original content-miner source: the upstream version
references a bare `source` variable inside extract_impl where it should
have been `data_source`.  Fixed here.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path

import cv2
import numpy as np
import pymupdf

from .arabic_text import normalize_for_digital_pdf
from .column_sort import sort_blocks
from .models import PageText

logger = logging.getLogger(__name__)

# Render at 2x zoom for accurate gutter detection — same as content-miner.
_ZOOM_FACTOR = 2.0


def extract_digital_pdf(pdf_path: Path) -> list[PageText]:
    """Extract text from a digital (non-scanned) PDF.

    Returns one PageText per page.  Each carries page_number (1-indexed for
    user-facing citations) and source_file (the basename).
    """
    pdf_path = Path(pdf_path)
    doc = pymupdf.open(pdf_path)
    try:
        return _get_pages(doc, source_file=pdf_path.name)
    finally:
        doc.close()


def _get_pages(doc: pymupdf.Document, source_file: str) -> list[PageText]:
    pages: list[PageText] = []
    for page_index, page in enumerate(doc):
        page_image = _get_page_image(page)
        blocks = page.get_text("dict", sort=True)["blocks"]
        cleaned = _remove_empty_spans(blocks)
        sorted_blocks = sort_blocks(page_image, cleaned)

        page_text_parts: list[str] = []
        for block in sorted_blocks:
            if block["type"] != 0:  # 0 = text, 1 = image
                continue
            block_text_parts: list[str] = []
            for line in block["lines"]:
                for span in line["spans"]:
                    raw = span["text"]
                    if not raw or not raw.strip():
                        continue
                    block_text_parts.append(normalize_for_digital_pdf(raw))
            if block_text_parts:
                page_text_parts.append(" ".join(block_text_parts))

        page_text = "\n\n".join(page_text_parts).strip()
        pages.append(
            PageText(
                text=page_text,
                page_number=page_index + 1,  # 1-indexed for user-facing citations
                source_file=source_file,
                metadata={"extractor": "pymupdf"},
            )
        )
    return pages


def _remove_empty_spans(blocks: list[dict]) -> list[dict]:
    """Strip spans whose text is whitespace-only, then drop now-empty lines/blocks."""
    temp = deepcopy(blocks)
    for i, block in enumerate(blocks):
        if block["type"] == 1:
            continue
        for j, line in enumerate(block["lines"]):
            for k, span in enumerate(line["spans"]):
                if not span["text"].strip():
                    temp[i]["lines"][j]["spans"][k] = None

    cleaned: list[dict] = []
    for block in temp:
        if block["type"] == 1:
            cleaned.append(block)
            continue
        cleaned_lines = []
        for line in block["lines"]:
            spans = [s for s in line["spans"] if s is not None]
            if spans:
                line_copy = deepcopy(line)
                line_copy["spans"] = spans
                cleaned_lines.append(line_copy)
        if cleaned_lines:
            block_copy = deepcopy(block)
            block_copy["lines"] = cleaned_lines
            cleaned.append(block_copy)
    return cleaned


def _get_page_image(page: pymupdf.Page) -> np.ndarray:
    """Rasterise a PyMuPDF page at 2x zoom for cv2 gutter detection."""
    mat = pymupdf.Matrix(_ZOOM_FACTOR, _ZOOM_FACTOR)
    pixmap = page.get_pixmap(matrix=mat, alpha=False)
    img_array = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
        pixmap.height, pixmap.width, pixmap.n
    )
    if pixmap.n == 3:
        return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
    if pixmap.n == 4:
        return cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
    return img_array


def is_digital_pdf(pdf_path: Path, min_chars: int = 50) -> bool:
    """Cheap heuristic: does this PDF contain extractable text, or is it scanned?

    Inspects the first few pages with PyMuPDF.  If they yield enough text
    we treat the PDF as digital and skip OCR.  Otherwise we fall through
    to PaddleOCR.
    """
    pdf_path = Path(pdf_path)
    doc = pymupdf.open(pdf_path)
    try:
        total = 0
        for page in doc[: min(3, doc.page_count)]:
            total += len(page.get_text("text").strip())
            if total >= min_chars:
                return True
        return total >= min_chars
    finally:
        doc.close()

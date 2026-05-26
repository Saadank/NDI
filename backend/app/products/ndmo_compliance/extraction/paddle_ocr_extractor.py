"""Arabic-first PaddleOCR extractor.

Settings preserved VERBATIM from Cortex (content-miner/extractors/visual/
paddle_ocr.py):
  * PaddleOCR(lang="ar")          — only construction argument
  * fix_rtl = True                — applies bidi.get_display after NFKC
  * predict() API (PaddleOCR 3.x) — returns rec_texts / rec_scores / rec_polys

Environment toggle: PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python must be
set BEFORE importing paddleocr to avoid the C++ binding crashing on some
hosts; we set it lazily inside the function so it doesn't pollute the
module-load path of callers that never use OCR.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np
from pdf2image import convert_from_path
from PIL import Image

from .arabic_text import normalize_for_ocr
from .models import BoundingBox, OcrResultItem, PageText
from .ocr_output_formatter import items_to_page_texts

logger = logging.getLogger(__name__)

_ocr_engine: Any | None = None


def _get_engine() -> Any:
    """Lazy-construct a singleton PaddleOCR engine configured for Arabic.

    Construction downloads the Arabic model on first call (~50 MB into
    ~/.paddleocr/), so we cache the engine for the process lifetime.
    """
    global _ocr_engine
    if _ocr_engine is None:
        os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
        from paddleocr import PaddleOCR  # noqa: PLC0415 — local import keeps cold callers fast

        # Cortex setting: lang="ar" only.  No det/rec/angle overrides.
        _ocr_engine = PaddleOCR(lang="ar")
    return _ocr_engine


def extract_with_paddle_ocr(pdf_or_image_path: Path) -> list[PageText]:
    """Run PaddleOCR over every page of a PDF (or a single image)."""
    path = Path(pdf_or_image_path)
    suffix = path.suffix.lower()

    items: list[OcrResultItem] = []
    if suffix == ".pdf":
        images = convert_from_path(str(path))
        for page_index, image in enumerate(images):
            page_items = _extract_from_image(image)
            for it in page_items:
                it.page_number = page_index + 1  # 1-indexed
            items.extend(page_items)
    else:
        page_items = _extract_from_image(Image.open(path))
        for it in page_items:
            it.page_number = 1
        items.extend(page_items)

    per_page = items_to_page_texts(items, is_line_based=True)
    pages: list[PageText] = []
    for page_num in sorted(per_page.keys()):
        # Cortex's fix_rtl=True pipeline: NFKC then bidi.get_display.
        cleaned = normalize_for_ocr(per_page[page_num])
        pages.append(
            PageText(
                text=cleaned,
                page_number=page_num,
                source_file=path.name,
                metadata={"extractor": "paddleocr", "lang": "ar"},
            )
        )
    return pages


def _extract_from_image(image: Image.Image) -> list[OcrResultItem]:
    engine = _get_engine()
    image_np = np.array(image)
    results = engine.predict(image_np)  # PaddleOCR 3.x API
    return _to_items(results)


def _to_items(results: Any) -> list[OcrResultItem]:
    """Convert PaddleOCR 3.x output to our OcrResultItem list."""
    items: list[OcrResultItem] = []
    if not results:
        return items
    page = results[0]
    rec_texts = page.get("rec_texts", [])
    rec_scores = page.get("rec_scores", [])
    rec_polys = page.get("rec_polys", [])
    for i in range(len(rec_texts)):
        try:
            poly = rec_polys[i]
            bb = BoundingBox(
                x1=float(poly[0][0]),
                y1=float(poly[0][1]),
                x2=float(poly[1][0]),
                y2=float(poly[1][1]),
            )
        except (IndexError, TypeError):
            bb = None
        items.append(
            OcrResultItem(
                text=rec_texts[i],
                confidence=float(rec_scores[i]) if i < len(rec_scores) else None,
                bounding_box=bb,
            )
        )
    return items

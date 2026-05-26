"""Document extraction + chunking for NDMO Compliance.

Self-contained port of EntropySA/content-miner (the Cortex extraction layer).
No git submodule, no external service. Settings preserved verbatim from Cortex:

  * Digital PDFs  -> PyMuPDF + Arabic normalization (NFKC, bidi-control
    stripping, ligature fixes, arabic_reshaper.reshape).  NO bidi.get_display.
  * Image PDFs    -> PaddleOCR(lang="ar") + fix_rtl=True (so bidi.get_display
    runs after NFKC).
  * Chunker       -> 500-word chunks with 50-word overlap, retaining
    page_number and source_file in every chunk's metadata.  (NEW — Cortex
    has no chunker; one page per Chunk in cortex.)

The asymmetry around bidi.get_display is intentional and load-bearing:
pymupdf returns text in logical order so a second bidi pass would reverse
it; PaddleOCR returns visual order, so bidi.get_display is needed.

Bug fix vs Cortex: content_miner_pdf_extractor.py used `source.path` where
`data_source.path` was meant; that's fixed here.
"""

from .extractor import extract_document, Chunk, PageText
from .chunker import chunk_pages

__all__ = ["extract_document", "Chunk", "PageText", "chunk_pages"]

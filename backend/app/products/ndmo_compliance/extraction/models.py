"""Minimal data model for the extraction layer.

A subset of content-miner's domain types — only what NDMO actually needs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class BoundingBox:
    """Axis-aligned bounding box in image pixel coordinates."""

    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(slots=True)
class OcrResultItem:
    """A single OCR detection (one word/line)."""

    text: str
    confidence: float | None = None
    bounding_box: BoundingBox | None = None
    page_number: int | None = None


@dataclass(slots=True)
class PageText:
    """Cleaned text for one page of one source file.

    Both the digital-PDF extractor and the OCR extractor produce a list of
    PageText objects.  Each one carries everything the chunker needs to keep
    page-level provenance with each downstream chunk.
    """

    text: str
    page_number: int
    source_file: str  # the original filename, not a path
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Chunk:
    """A 500-word window of text from a source file.

    `page_number` is the page the chunk *starts* on.  When a chunk straddles
    a page boundary we include `spans_pages` for citation accuracy.
    """

    text: str
    page_number: int
    source_file: str
    chunk_index: int  # ordinal within the document
    word_count: int
    spans_pages: list[int]  # all pages this chunk contains text from
    metadata: dict[str, Any] = field(default_factory=dict)

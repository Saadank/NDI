"""500-word chunker with 50-word overlap.

NEW relative to Cortex — content-miner has no chunker (each page is one
TextContent; cortex's content_embedding_task then embeds each TextContent
as one Chunk).  For NDMO we need fixed-size windows to keep retrieval
predictable, while still preserving page-level citations.

Design:
  * The document is flattened into one ordered word stream, each word
    tagged with its origin page_number.
  * We slide a window of CHUNK_SIZE words across the stream, stepping
    by (CHUNK_SIZE - OVERLAP).
  * Each chunk records: the page it starts on, the full list of pages it
    spans (for citations), and the source filename.
  * Word splitting is whitespace-based; we DO NOT split inside an Arabic
    word.  Each chunk is at most CHUNK_SIZE words; if the document is
    shorter than that we emit a single short chunk.

Arabic-specific note: in NFKC-normalized base Arabic, whitespace is the
canonical word separator (just like in Latin scripts).  No special
tokenization required.
"""

from __future__ import annotations

from collections.abc import Iterable

from .models import Chunk, PageText

CHUNK_SIZE = 500
OVERLAP = 50
_STEP = CHUNK_SIZE - OVERLAP


def chunk_pages(pages: Iterable[PageText]) -> list[Chunk]:
    """Turn an ordered list of PageText into a list of Chunks.

    Pages must already be in document order.  Empty pages contribute no
    words but their numbers are preserved in the span-tracking.
    """
    pages = list(pages)
    if not pages:
        return []

    source_file = pages[0].source_file

    # Flatten into a single (word, page_number) stream.
    word_stream: list[tuple[str, int]] = []
    for page in pages:
        text = page.text or ""
        for word in text.split():
            word_stream.append((word, page.page_number))

    if not word_stream:
        return []

    chunks: list[Chunk] = []
    chunk_index = 0
    i = 0
    n = len(word_stream)
    while i < n:
        window = word_stream[i : i + CHUNK_SIZE]
        words = [w for w, _ in window]
        page_set: list[int] = []
        seen = set()
        for _, p in window:
            if p not in seen:
                seen.add(p)
                page_set.append(p)
        chunks.append(
            Chunk(
                text=" ".join(words),
                page_number=window[0][1],
                source_file=source_file,
                chunk_index=chunk_index,
                word_count=len(words),
                spans_pages=page_set,
            )
        )
        chunk_index += 1
        if i + CHUNK_SIZE >= n:
            break
        i += _STEP
    return chunks

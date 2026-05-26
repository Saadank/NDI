"""Group OCR detections into reading order and emit per-page text.

Port of content-miner/utils/ocr_output_formatter.py.  Uses bbox-y1 with a
median-height epsilon for line grouping, then sorts each line by x1, then
joins lines with newlines.
"""

from __future__ import annotations

from .models import OcrResultItem


def items_to_page_texts(
    items: list[OcrResultItem],
    is_line_based: bool = True,
) -> dict[int, str]:
    """Return ``{page_number: text}`` for every page represented in ``items``."""
    separator = "\n" if is_line_based else " "

    pages: dict[int, list[OcrResultItem]] = {}
    for item in items:
        page = item.page_number if item.page_number is not None else 0
        pages.setdefault(page, []).append(item)

    page_texts: dict[int, str] = {}
    for page_num in sorted(pages.keys()):
        page_items = pages[page_num]

        # Dynamic epsilon based on median glyph height.
        heights = [
            item.bounding_box.y2 - item.bounding_box.y1
            for item in page_items
            if item.bounding_box
        ]
        if heights:
            sorted_heights = sorted(heights)
            median_height = sorted_heights[len(sorted_heights) // 2]
            epsilon = median_height * 0.5
        else:
            epsilon = 0.0

        page_items_sorted = sorted(
            page_items,
            key=lambda x: x.bounding_box.y1 if x.bounding_box else 0,
        )

        lines: list[list[OcrResultItem]] = []
        current_line: list[OcrResultItem] = []
        for item in page_items_sorted:
            if not current_line:
                current_line.append(item)
                continue
            first_y = current_line[0].bounding_box.y1 if current_line[0].bounding_box else 0
            current_y = item.bounding_box.y1 if item.bounding_box else 0
            if abs(current_y - first_y) <= epsilon:
                current_line.append(item)
            else:
                lines.append(current_line)
                current_line = [item]
        if current_line:
            lines.append(current_line)

        for line in lines:
            line.sort(key=lambda x: x.bounding_box.x1 if x.bounding_box else 0)
        lines.sort(key=lambda line: line[0].bounding_box.y1 if line[0].bounding_box else 0)

        line_texts = [separator.join(item.text for item in line) for line in lines]
        page_texts[page_num] = "\n".join(line_texts)

    return page_texts

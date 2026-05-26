"""PyMuPDF block sorter — port of content-miner/utils/sort_pymupdf_blocks.py.

Detects vertical gutters in the rasterised page via Otsu binarization, then
assigns each text block to a column based on its x-centre, then sorts
top-to-bottom within each column.  Important for multi-column Arabic layouts
where naive top-to-bottom flow zigzags between columns.
"""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np


def sort_blocks(image: np.ndarray, blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort PyMuPDF text blocks into natural reading order.

    Parameters
    ----------
    image : np.ndarray
        Rasterised page image (grayscale or BGR).
    blocks : list[dict]
        PyMuPDF blocks from ``page.get_text("dict", sort=True)["blocks"]``,
        each with a ``bbox`` key ``[x0, y0, x1, y1]``.

    Returns
    -------
    list[dict]
        Same blocks, reordered into approximate reading order.
    """
    h, w = image.shape[:2]

    # 1. Binarize text vs background via Otsu.
    if image.ndim == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()
    _, bw = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)

    # 2. Vertical projection -> find low-density gutters.
    col_counts = np.sum(bw > 0, axis=0).astype(np.float32)
    if col_counts.max() > 0:
        col_norm = col_counts / col_counts.max()
    else:
        col_norm = col_counts

    gutter_thresh = 0.05
    gutter_mask = col_norm < gutter_thresh

    min_gutter_width = max(5, int(w * 0.02))
    gutters: list[tuple[int, int]] = []
    i = 0
    while i < w:
        if gutter_mask[i]:
            start = i
            while i < w and gutter_mask[i]:
                i += 1
            end = i
            if (end - start) >= min_gutter_width:
                gutters.append((start, end))
        else:
            i += 1

    boundaries = [0] + [(s + e) // 2 for s, e in gutters] + [w]
    column_ranges = [(boundaries[i], boundaries[i + 1]) for i in range(len(boundaries) - 1)]

    # 3. Assign blocks to columns.
    def find_col(x_center: float) -> int:
        for col_idx, (x0, x1) in enumerate(column_ranges):
            if x0 <= x_center < x1:
                return col_idx
        dists = [abs(x_center - (x0 + x1) / 2) for x0, x1 in column_ranges]
        return int(np.argmin(dists))

    indexed: list[tuple[int, float, int, dict[str, Any]]] = []
    for idx, blk in enumerate(blocks):
        x0, y0, x1, y1 = blk["bbox"]
        xc = (x0 + x1) / 2
        col = find_col(xc)
        indexed.append((col, y0, idx, blk))

    # For Arabic right-to-left documents we want rightmost column first.
    # We invert the column index so high-x columns come first.
    max_col = max((c for c, _, _, _ in indexed), default=0)
    indexed.sort(key=lambda t: (max_col - t[0], t[1], t[2]))

    return [blk for _, _, _, blk in indexed]

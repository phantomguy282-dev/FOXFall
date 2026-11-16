"""
layout.py
Responsive layout helpers: dynamic terminal measurement, adaptive widths,
centering and vertical padding. Every screen recomputes on each frame so
maximize/resize events are picked up immediately.
"""

from __future__ import annotations

from typing import List, Tuple

from ui import components as C

MIN_WIDTH = 60
MAX_WIDTH = 220


def usable_size() -> Tuple[int, int]:
    """Terminal size clamped to sane bounds."""
    cols, rows = C.terminal_size()
    return max(MIN_WIDTH, min(MAX_WIDTH, cols)), max(18, rows)


def content_width(cols: int, margins: int = 0) -> int:
    """Full available content width (rules span the whole terminal)."""
    return max(MIN_WIDTH, cols - margins)


def body_width(cols: int) -> int:
    """Text width inside the body block (indented, capped for readability)."""
    return max(40, min(110, cols - 6))


def pad_vertical(lines: List[str], rows: int, content_height: int) -> List[str]:
    """
    Distribute empty space so content sits balanced: keep footer pinned by
    padding after the header area. content_height excludes header/footer.
    """
    deficit = rows - len(lines)
    if deficit <= 0:
        return lines
    top = deficit // 3          # 1/3 above, rest below (footer hugs bottom)
    return [""] * top + lines + [""] * (deficit - top)


def progress_width(cols: int) -> int:
    """Progress bar adapts: 30% of width, bounded."""
    return max(20, min(80, int(cols * 0.45)))


def history_row_width(cols: int) -> int:
    return max(40, cols - 4)

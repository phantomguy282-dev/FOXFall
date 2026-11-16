"""
fox.py
Reusable ASCII fox logo component.

A multi-line fox face rendered from characters, aligned for Cascadia Code.
Colors: orange fur, amber inner ear, cream muzzle/chest, dark outlines.
Each part is pre-colored; the component returns final ANSI strings.
Theme-aware: fox themes expose fox_orange/fox_amber/fox_cream/fox_dark;
other themes fall back to their banner/highlight/bright/border colors.
"""

from __future__ import annotations

from typing import List, Optional

from ui import components as C
from ui.themes import Theme

# Token art: {O} fur orange, {A} amber (ears), {C} cream (muzzle), {W} accents.
# A classic 9-column fox head: pointed ears, bright eyes, cream muzzle.
FOX_ROWS = [
    " {A}/{O}\\___{A}/{O}\\ ",
    "{O}( {W}o{O}   o {O})",
    " {O}\\{C}  ^  {O}/ ",
    "  {C}\\___/  ",
]


def _palette(theme: Theme) -> dict:
    """Token -> hex, derived from the active theme."""
    orange = getattr(theme, "fox_orange", None) or theme.banner
    amber = getattr(theme, "fox_amber", None) or theme.highlight
    cream = getattr(theme, "fox_cream", None) or theme.bright
    dark = getattr(theme, "fox_dark", None) or theme.border
    white = theme.bright
    return {"{O}": orange, "{A}": amber, "{C}": cream, "{D}": dark, "{W}": white}


def fox_lines(theme: Theme, max_width: Optional[int] = None) -> List[str]:
    """Colorized fox art rows, clipped to max_width when given."""
    pal = _palette(theme)
    out: List[str] = []
    for raw in FOX_ROWS:
        line = ""
        i = 0
        while i < len(raw):
            if raw.startswith("{", i):
                end = raw.find("}", i)
                token = raw[i:end + 1]
                color = pal.get(token)
                if color:
                    line += C.fg(color, "")
                i = end + 1
                continue
            line += raw[i]
            i += 1
        line = line.rstrip()
        if max_width:
            line = C.clip_visible(line, max_width)
        out.append(line)
    return out


def fox_block(theme: Theme, cols: int, tagline: str = "") -> List[str]:
    """Fox centered next to the FOXFALL wordmark (header block)."""
    art = fox_lines(theme)
    width = max((C.visible_len(l) for l in art), default=0)
    gap = 5
    lines: List[str] = []
    wordmark = C.fg(theme.banner, C.bold("F  O  X  F  A  L  L"))
    subtitle = C.fg(theme.dim, tagline) if tagline else ""
    for row in art:
        padded = row + " " * max(0, width - C.visible_len(row)) + " " * gap
        if len(lines) == 1:
            padded += wordmark
        elif len(lines) == 2 and subtitle:
            padded += subtitle
        lines.append(padded)
    # center the whole block within cols
    block_width = max(C.visible_len(l) for l in lines)
    left = max(0, (cols - block_width) // 2)
    return [C.clip_visible(" " * left + l, cols) for l in lines]


def fox_face(theme: Theme) -> str:
    """Compact single-line fox face for footers/status."""
    orange = getattr(theme, "fox_orange", None) or theme.banner
    return (C.fg(orange, "/\\_/\\") + " "
            + C.fg(orange, "( o.o )") + " "
            + C.fg(orange, "> ^ <"))

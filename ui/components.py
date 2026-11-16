"""
components.py
Reusable text widgets: rules, rails, platform chips, progress bars, tables.
Pure ANSI (no external deps) so the render is fast and terminal-native,
mirroring the reference screenshot (dark bg, dark-red rules, gray text,
green platform tags, red reverse-video selection chip).
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import List, Optional

from .themes import Theme

# ---------------------------------------------------------------- ANSI
ESC = "\x1b"
RESET = f"{ESC}[0m"


def _supports_color() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    return sys.stdout.isatty() or os.environ.get("WT_SESSION") or (
        os.environ.get("TERM") not in (None, "", "dumb"))


COLOR_ENABLED = _supports_color()


def fg(hexcolor: str, text: str) -> str:
    """Color text with a hex color (converted to nearest xterm-256)."""
    if not COLOR_ENABLED:
        return text
    code = _hex_to_256(hexcolor)
    return f"{ESC}[38;5;{code}m{text}{RESET}"


def bg(hexcolor: str, text: str) -> str:
    if not COLOR_ENABLED:
        return text
    code = _hex_to_256(hexcolor)
    return f"{ESC}[48;5;{code}m{text}{RESET}"


def bold(text: str) -> str:
    if not COLOR_ENABLED:
        return text
    return f"{ESC}[1m{text}{RESET}"


def dim_text(text: str) -> str:
    if not COLOR_ENABLED:
        return text
    return f"{ESC}[2m{text}{RESET}"


def _hex_to_256(hexcolor: str) -> int:
    hexcolor = hexcolor.lstrip("#")
    try:
        r = int(hexcolor[0:2], 16)
        g = int(hexcolor[2:4], 16)
        b = int(hexcolor[4:6], 16)
    except (ValueError, IndexError):
        return 7
    # grayscale ramp
    if abs(r - g) < 10 and abs(g - b) < 10:
        if r < 8:
            return 16
        if r > 248:
            return 231
        return 232 + int(round((r - 8) / 247.0 * 23))
    # 6x6x6 cube
    def idx(v: int) -> int:
        return 0 if v < 48 else (1 if v < 115 else (int((v - 35) / 40)))
    return 16 + 36 * idx(r) + 6 * idx(g) + idx(b)


# ---------------------------------------------------------------- layout helpers
def terminal_size(fallback=(100, 30)) -> tuple[int, int]:
    try:
        cols, rows = shutil.get_terminal_size(fallback)
        return cols, rows
    except Exception:
        return fallback


def visible_len(text: str) -> int:
    """Length excluding ANSI escape sequences."""
    out, i = 0, 0
    while i < len(text):
        if text[i] == ESC and i + 1 < len(text) and text[i + 1] == "[":
            j = text.find("m", i)
            i = j + 1 if j != -1 else len(text)
            continue
        if ord(text[i]) > 0xFFFF or 0x1F300 <= ord(text[i]) <= 0x1FAFF:
            out += 2
        else:
            out += 1
        i += 1
    return out


def pad_center(text: str, width: int) -> str:
    raw = visible_len(text)
    left = max(0, (width - raw) // 2)
    right = max(0, width - raw - left)
    return " " * left + text + " " * right


def clip_visible(text: str, width: int) -> str:
    """Truncate to width visible cells preserving ANSI codes."""
    if width <= 0:
        return ""
    out: List[str] = []
    cur = 0
    i = 0
    while i < len(text) and cur < width:
        ch = text[i]
        if ch == ESC and i + 1 < len(text) and text[i + 1] == "[":
            j = text.find("m", i)
            if j == -1:
                break
            out.append(text[i:j + 1])
            i = j + 1
            continue
        if ord(ch) > 0xFFFF or 0x1F300 <= ord(ch) <= 0x1FAFF:
            w = 2
        else:
            w = 1
        if cur + w > width:
            out.append("~")
            break
        out.append(ch)
        cur += w
        i += 1
    return "".join(out)


# ---------------------------------------------------------------- widgets
def horizontal_rule(theme: Theme, width: int) -> str:
    """Full-width dark-red rule, like reference lines."""
    return fg(theme.border, "\u2501" * width)


def left_rail(theme: Theme, height: int) -> str:
    """Vertical double-line rail on the left border (x21..22 in reference)."""
    return fg(theme.border, "\u2551")


def platform_chip(tag: str, theme: Theme) -> str:
    """[YT] / [IG] / [TT] tag in highlight color."""
    return fg(theme.highlight, tag)


def status_tag(status: str, theme: Theme) -> str:
    mapping = {
        "pending": (theme.dim, "[..]"),
        "preparing": (theme.warn, "[*]"),
        "downloading": (theme.warn, "[*]"),
        "merging": (theme.warn, "[~]"),
        "done": (theme.accent, "[OK]"),
        "error": (theme.error, "[x]"),
        "cancelled": (theme.dim, "[x]"),
    }
    color, tag = mapping.get(status, (theme.dim, "[?]"))
    return fg(color, tag)


def progress_bar(percent: float, width: int, theme: Theme,
                 fill_color: Optional[str] = None) -> str:
    """Block progress bar like premium CLIs."""
    width = max(10, width)
    filled = int(round(max(0.0, min(100.0, percent)) / 100.0 * width))
    color = fill_color or theme.progress_fill
    bar = "\u2588" * filled
    empty = "\u2591" * (width - filled)
    return fg(color, bar) + fg(theme.progress_empty, empty)


def format_size(num_bytes: float) -> str:
    if not num_bytes:
        return "--"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if num_bytes < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(num_bytes)} {unit}"
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return "--"


def format_eta(seconds: int, status: str = "downloading") -> str:
    """
    Render ETA for the UI.
      status done   -> "Completed"
      unknown (-1)  -> "Calculating..."
      valid > 0     -> m:ss / h:mm:ss
    """
    if status in ("done", "merging"):
        return "Completed" if status == "done" else "Finalizing..."
    if seconds is None or seconds < 0:
        return "Calculating..."
    if seconds == 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    m, s = divmod(int(seconds), 60)
    h, m2 = divmod(m, 60)
    if h:
        return f"{h}:{m2:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def format_speed(bps: float) -> str:
    if not bps:
        return "--"
    return f"{format_size(bps)}/s"


def menu_line(number: str, label: str, theme: Theme, selected: bool = False) -> str:
    """Menu row; selected rows render as reverse-video chip like the reference."""
    if selected:
        inner = f" {number}  {label} "
        inner = inner + " " * max(0, 30 - len(inner))
        return bg(theme.select_bg, fg(theme.select_fg, bold(inner)))
    return f" {fg(theme.accent, number)}  {fg(theme.text, label)}"

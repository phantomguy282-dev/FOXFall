"""
animations.py
Startup animation: fox logo reveal + FOXFALL wordmark + init messages
+ orange loading bar. Optional (settings.startup_animation) and skippable.
"""

from __future__ import annotations

import sys
import time
from typing import List

from ui import components as C
from ui.fox import fox_block
from ui.themes import Theme


def _hide_cursor() -> None:
    sys.stdout.write("\x1b[?25l")
    sys.stdout.flush()


def _show_cursor() -> None:
    sys.stdout.write("\x1b[?25h")
    sys.stdout.flush()


def clear() -> None:
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()


def spinner_frame(i: int) -> str:
    return ["|", "/", "-", "\\"][i % 4]


DEFAULT_MESSAGES = [
    "Initializing FOXFall...",
    "Loading fox theme...",
    "Detecting FFmpeg...",
    "Initializing download engine...",
    "Checking network...",
    "Interface ready.",
]


def startup_frame_lines(theme: Theme, cols: int, tagline: str) -> List[str]:
    """Static startup screen (also used as the non-animated render)."""
    lines: List[str] = []
    lines += fox_block(theme, cols, tagline)
    lines.append("")
    lines.append(C.horizontal_rule(theme, cols))
    return lines


def run_startup_animation(theme: Theme, enabled: bool = True,
                          messages: List[str] | None = None) -> None:
    """Progressive fox + messages + orange progress. Fast (~1.5s)."""
    if messages is None:
        messages = DEFAULT_MESSAGES
    cols, _rows = C.terminal_size()
    tagline = "Multi-Platform Video Downloader"

    if not enabled or not C.COLOR_ENABLED or not sys.stdout.isatty():
        clear()
        for line in startup_frame_lines(theme, cols, tagline):
            print(line)
        print()
        for msg in messages:
            print(f"  {C.fg(theme.accent, '[OK]')} {C.fg(theme.text, msg)}")
        print()
        return
    try:
        _hide_cursor()
        clear()
        frame = startup_frame_lines(theme, cols, tagline)
        # progressive reveal of the fox block
        for line in frame:
            print(C.clip_visible(line, cols))
            sys.stdout.flush()
            time.sleep(0.09)
        print()
        idx = 0
        for msg in messages:
            for _step in range(2):
                spin = C.fg(theme.warn, spinner_frame(idx))
                idx += 1
                sys.stdout.write("\r  " + spin + " " + C.fg(theme.text, msg) + "   ")
                sys.stdout.flush()
                time.sleep(0.04)
            sys.stdout.write("\r  " + C.fg(theme.accent, "[OK]") + " "
                             + C.fg(theme.text, msg) + "   \n")
            sys.stdout.flush()
        # orange loading bar flourish
        width = min(44, cols - 8)
        for step in range(width + 1):
            bar = C.progress_bar(step / width * 100, width, theme)
            sys.stdout.write("\r" + " " * 4 + bar)
            sys.stdout.flush()
            time.sleep(0.010)
        sys.stdout.write("\n")
        time.sleep(0.12)
        clear()
    except KeyboardInterrupt:
        clear()
    finally:
        _show_cursor()

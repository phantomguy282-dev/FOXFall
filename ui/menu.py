"""
menu.py
Thin menu registry kept separate from rendering (interface.py does the drawing).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

MenuItem = Tuple[str, str]  # (key, label)

MAIN_MENU: List[MenuItem] = [
    ("1", "New Download"),
    ("2", "Download Queue"),
    ("3", "Download History"),
    ("4", "Settings"),
    ("0", "Exit"),
]


def shortcuts() -> Dict[str, str]:
    return {key: label for key, label in MAIN_MENU}

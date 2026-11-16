"""
keys.py
Centralized keyboard shortcut management.

Single source of truth for shortcut keys and their labels so no two global
actions can accidentally share a binding. Screens request bindings from here
and render footers from SHORTCUT_LABELS.
"""

from __future__ import annotations

from typing import Dict

# Global/main-menu shortcuts
MAIN_SHORTCUTS: Dict[str, str] = {
    "1": "New Download",
    "2": "Download Queue",
    "3": "Download History",
    "4": "Settings",
    "5": "Diagnostics",
    "Q": "Quit",
    "ESC": "Back",
}

SETTINGS_SHORTCUTS: Dict[str, str] = {
    "UP/DOWN": "Select setting",
    "LEFT/RIGHT": "Change value",
    "ENTER": "Confirm",
    "ESC": "Back",
}


def footer_text(screen: str = "main") -> str:
    if screen == "settings":
        return "   ".join(f"{k} {v}" for k, v in SETTINGS_SHORTCUTS.items())
    if screen == "main":
        return ("[1] New Download  [2] Queue  [3] History  "
                "[4] Settings  [5] Diagnostics  [Q] Quit")
    return ""


# Quit confirmation prompt text (spec section 4)
QUIT_PROMPT = "Are you sure you want to quit FOXFall? [Y/N]"
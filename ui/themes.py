"""
themes.py
Centralized theme definitions.

Themes:
  fox      - fox identity: orange/amber/cream on dark warm background (default)
  original - the reference.png crimson design
  dark     - neutral dark theme

Every theme carries fox_* tokens so the fox logo stays recognizable while
still fitting each palette. All colors are xterm-256-friendly hex values.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    key: str
    name: str
    border: str       # horizontal rules / separators
    banner: str       # wordmark / FIGlet
    text: str         # normal text
    dim: str          # secondary text
    bright: str       # emphasized text
    accent: str       # [OK] / status accents
    warn: str         # warnings
    error: str        # errors
    highlight: str    # platform tag chips [YT]
    select_bg: str    # reverse-video selection background
    select_fg: str    # reverse-video selection text
    progress_fill: str
    progress_empty: str
    # fox tokens (fall back to core colors when absent)
    fox_orange: str = ""
    fox_amber: str = ""
    fox_cream: str = ""
    fox_dark: str = ""


THEMES: dict[str, Theme] = {
    "fox": Theme(
        key="fox", name="Fox (orange)",
        border="#F28C28",
        banner="#F28C28",
        text="#FFF1D6",
        dim="#A89A8B",
        bright="#FFF1D6",
        accent="#8BCF8B",
        warn="#FFB347",
        error="#FF6666",
        highlight="#FFB347",
        select_bg="#F28C28",
        select_fg="#17120F",
        progress_fill="#F28C28",
        progress_empty="#241A15",
        fox_orange="#F28C28",
        fox_amber="#FFB347",
        fox_cream="#FFF1D6",
        fox_dark="#241A15",
    ),
    "original": Theme(
        key="original", name="Original (crimson reference)",
        border="#870000",
        banner="#D70000",
        text="#BCBCBC",
        dim="#6C6C6C",
        bright="#EEEEEE",
        accent="#87D787",
        warn="#D7AF00",
        error="#D70000",
        highlight="#87D787",
        select_bg="#D70000",
        select_fg="#0C0C0C",
        progress_fill="#D70000",
        progress_empty="#474747",
        fox_orange="#D75F00",
        fox_amber="#D78700",
        fox_cream="#EEEEEE",
        fox_dark="#870000",
    ),
    "dark": Theme(
        key="dark", name="Dark (neutral)",
        border="#555555",
        banner="#EEEEEE",
        text="#BCBCBC",
        dim="#6C6C6C",
        bright="#FFFFFF",
        accent="#87D787",
        warn="#D7AF00",
        error="#FF6666",
        highlight="#87D7FF",
        select_bg="#444444",
        select_fg="#FFFFFF",
        progress_fill="#87D7FF",
        progress_empty="#333333",
        fox_orange="#F28C28",
        fox_amber="#FFB347",
        fox_cream="#EEEEEE",
        fox_dark="#333333",
    ),
}

DEFAULT_THEME = "fox"

# Settings screen choices, in spec order.
THEME_CHOICES = ["fox", "original", "dark"]


def get_theme(key: str | None = None) -> Theme:
    if not key:
        from core import settings as settings_mod
        key = settings_mod.get("theme", DEFAULT_THEME)
    return THEMES.get(key, THEMES[DEFAULT_THEME])


def list_themes() -> list[str]:
    return list(THEMES.keys())


def theme_display(key: str) -> str:
    return THEMES[key].name if key in THEMES else key

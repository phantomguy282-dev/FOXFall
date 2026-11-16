"""
tests/test_components.py
ANSI widget correctness: visible length, clipping, progress bar, ANSI filter.
"""

from ui import components as C
from ui.themes import get_theme


def test_visible_len_plain():
    assert C.visible_len("hello") == 5


def test_visible_len_ignores_ansi():
    colored = C.fg("#ff0000", "abc")
    assert C.visible_len(colored) == 3


def test_visible_len_color_enabled_guard():
    # works whether or not color is enabled
    assert C.visible_len(C.bold("x")) == 1


def test_theme_migration_crimson_to_original():
    theme = get_theme("original")
    assert theme.key == "original"
    assert theme.border == "#870000"


def test_fox_theme_tokens():
    theme = get_theme("fox")
    assert theme.fox_orange == "#F28C28"
    assert theme.fox_amber == "#FFB347"
    assert theme.fox_cream == "#FFF1D6"
    assert theme.select_bg == "#F28C28"


def test_get_theme_fallback_unknown():
    assert get_theme("nope").key == "fox"


def test_clip_visible_preserves_codes():
    theme = get_theme()
    text = C.fg(theme.banner, "abcdefgh")
    out = C.clip_visible(text, 4)
    assert C.visible_len(out) <= 4
    assert "\x1b[" in out or not C.COLOR_ENABLED


def test_clip_visible_wide_chars():
    assert C.clip_visible("😀😀", 3) == "😀~"


def test_pad_center():
    out = C.pad_center("abc", 11)
    assert C.visible_len(out) == 11
    assert out.strip() == "abc"


def test_progress_bar_fill_proportional():
    theme = get_theme()
    bar10 = C.progress_bar(50, 10, theme)
    assert C.visible_len(bar10) == 10
    full = C.progress_bar(100, 10, theme)
    assert "\u2588" * 10 in full
    empty = C.progress_bar(0, 10, theme)
    assert "\u2588" not in empty


def test_format_size():
    assert C.format_size(512) == "512 B"
    assert C.format_size(2048) == "2.0 KB"
    assert C.format_size(1024 ** 3) == "1.0 GB"
    assert C.format_size(0) == "--"


def test_format_eta():
    assert C.format_eta(0, status="done") == "Completed"
    assert C.format_eta(59) == "59s"
    assert C.format_eta(61) == "1:01"
    assert C.format_eta(3661) == "1:01:01"
    assert C.format_eta(-1) == "Calculating..."


def test_menu_line_selection():
    theme = get_theme()
    plain = C.menu_line("[1]", "YouTube", theme, selected=False)
    sel = C.menu_line("[1]", "YouTube", theme, selected=True)
    assert C.visible_len(plain) > 0
    assert C.visible_len(sel) > 0

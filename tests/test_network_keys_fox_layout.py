"""
tests/test_network_keys_fox_layout.py
Network diagnostics classification, keyboard dispatcher mapping, fox
component shape, layout responsiveness.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ------------------------------------------------------------ network
def test_classify_error_categories():
    from utils.network import classify_error
    assert classify_error("<urlopen error [Errno 11001] getaddrinfo failed>") == "dns"
    assert classify_error("certificate verify failed: certificate expired") == "ssl"
    assert classify_error("HTTP Error 429: Too Many Requests") == "rate_limit"
    assert classify_error("Sign in to confirm you're not a bot") == "rate_limit"
    assert classify_error("Private video. Sign in if you've been granted access") == "private"
    assert classify_error("Unsupported URL: https://x") == "unsupported"
    assert classify_error("Unable to download webpage: timed out") == "timeout"
    assert classify_error("HTTP Error 502: Bad Gateway") == "http"
    assert classify_error("connection reset by peer") == "timeout"
    assert classify_error("") == "unknown"
    assert classify_error("weird unexpected error text") == "other"


def test_humanize_error_truthful():
    from utils.network import humanize_error
    msg = humanize_error("getaddrinfo failed for www.youtube.com")
    assert "DNS" in msg
    msg = humanize_error("Sign in to confirm you're not a bot")
    assert "limiting" in msg or "bot" in msg


def test_check_results_tag():
    from utils.network import CheckResult
    assert CheckResult("t", True).tag() == "[OK]"
    assert CheckResult("t", False).tag() == "[x]"


def test_check_dns_real():
    from utils.network import check_dns
    result = check_dns("localhost", timeout=5)
    assert result.ok


def test_report_lines():
    from utils.network import DiagnosticsReport, CheckResult
    report = DiagnosticsReport()
    report.add(CheckResult("a", True, "detail"))
    report.add(CheckResult("b", False))
    lines = report.lines()
    assert len(lines) == 2 and "[OK]" in lines[0] and "[x]" in lines[1]
    assert not report.all_ok


# ------------------------------------------------------------ keys
def test_main_shortcuts_q_is_quit():
    from ui.keys import MAIN_SHORTCUTS
    assert MAIN_SHORTCUTS["Q"] == "Quit"
    # queue has its own binding
    assert "2" in MAIN_SHORTCUTS


def test_quit_prompt_text():
    from ui.keys import QUIT_PROMPT
    assert "[Y/N]" in QUIT_PROMPT


def test_read_key_importable_both_platforms():
    from ui.interface import read_key  # noqa: F401


# ------------------------------------------------------------ fox
def test_fox_lines_shape():
    from ui.fox import fox_lines
    from ui.themes import get_theme
    lines = fox_lines(get_theme("fox"))
    assert len(lines) == 4
    assert all(C.visible_len if False else len(l.strip()) > 0 for l in lines)
    # recognizable ears + eyes present in plain text
    plain = " ".join(l for l in lines)
    assert "o" in plain and "^" in plain


def test_fox_block_contains_wordmark():
    from ui.fox import fox_block
    from ui.themes import get_theme
    block = fox_block(get_theme("fox"), 100, "tagline here")
    assert any("F  O  X  F  A  L  L" in l for l in block)
    assert any("tagline here" in l for l in block)


def test_fox_adapts_to_small_width():
    from ui.fox import fox_block
    from ui.themes import get_theme
    from ui import components as C
    block = fox_block(get_theme("fox"), 40, "t")
    assert all(C.visible_len(l) <= 40 for l in block)


def test_fox_face_single_line():
    from ui.fox import fox_face
    from ui.themes import get_theme
    face = fox_face(get_theme("fox"))
    assert "( o.o )" in face


def test_fox_face_text_plain():
    from ui.interface import fox_face_text
    from ui.themes import get_theme
    text = fox_face_text(get_theme("fox"))
    assert "\x1b" not in text
    assert "o.o" in text


import ui.components as C  # noqa: E402


# ------------------------------------------------------------ layout
def test_usable_size_bounds():
    from ui.layout import usable_size
    cols, rows = usable_size()
    assert 60 <= cols <= 220
    assert rows >= 18


def test_progress_width_adapts():
    from ui.layout import progress_width
    assert progress_width(80) == 36
    assert progress_width(200) == 80
    assert progress_width(60) >= 20


def test_body_width_capped():
    from ui.layout import body_width
    assert body_width(200) == 110
    assert body_width(80) >= 40

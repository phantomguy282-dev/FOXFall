"""
tests/test_eta.py
ETA computation correctness (regression for the stuck 0.0 bug) and
format_eta display states.
"""

import pytest

from core.downloader import ETA_UNKNOWN, compute_eta


def test_ytdlp_eta_preferred_when_valid():
    assert compute_eta(100, 1000, 500.0, ytdlp_eta=7) == 7


def test_fallback_computed_from_speed():
    # remaining 900 bytes at 300 B/s => 3s
    assert compute_eta(100, 1000, 300.0, ytdlp_eta=None) == 3


def test_unknown_when_no_speed_and_no_eta():
    assert compute_eta(100, 1000, 0.0, ytdlp_eta=None) == ETA_UNKNOWN


def test_zero_remaining_is_zero():
    assert compute_eta(1000, 1000, 500.0, ytdlp_eta=None) == 0
    assert compute_eta(1200, 1000, 500.0, ytdlp_eta=None) == 0


def test_never_negative_or_nan():
    result = compute_eta(100, 1000, float("nan"), ytdlp_eta=float("nan"))
    assert result == ETA_UNKNOWN
    assert compute_eta(100, 1000, -50.0, ytdlp_eta=-3) == ETA_UNKNOWN or \
        compute_eta(100, 1000, -50.0, ytdlp_eta=-3) >= 0


def test_inf_speed_guarded():
    assert compute_eta(100, 1000, float("inf"), ytdlp_eta=None) == ETA_UNKNOWN


def test_no_total_known():
    # unknown total but yt-dlp gave eta -> use it
    assert compute_eta(0, 0, 0.0, ytdlp_eta=42) == 42
    # nothing at all and nothing remaining -> 0 (nothing left to wait for)
    assert compute_eta(0, 0, 0.0, ytdlp_eta=None) == 0


def test_ytdlp_eta_zero_falls_through_to_estimate():
    # eta=0 from yt-dlp is not trustworthy when bytes remain
    assert compute_eta(100, 1000, 100.0, ytdlp_eta=0) == 9


# ---------------------------------------------------------------- display
def test_format_eta_calculating_state():
    from ui.components import format_eta
    assert format_eta(ETA_UNKNOWN) == "Calculating..."
    assert format_eta(-1) == "Calculating..."
    assert format_eta(None) == "Calculating..."


def test_format_eta_completed_state():
    from ui.components import format_eta
    assert format_eta(0, status="done") == "Completed"
    assert format_eta(0, status="merging") == "Finalizing..."


def test_format_eta_valid_seconds():
    from ui.components import format_eta
    assert format_eta(45) == "45s"
    assert format_eta(90) == "1:30"
    assert format_eta(3725) == "1:02:05"


# ---------------------------------------------------------------- progress hook
def test_progress_hook_uses_compute_eta():
    from core.downloader import Downloader
    from core.video_info import QualityOption
    dl = Downloader("https://youtu.be/x", QualityOption("Best", "best"), "mp4", ".")
    # yt-dlp gives no eta, but speed+total known -> computed
    dl._progress_hook({"status": "downloading", "downloaded_bytes": 100,
                       "total_bytes": 1100, "speed": 100.0, "eta": None})
    assert dl.state.eta == 10
    # yt-dlp gives a real eta -> used directly (never 0.0 stuck)
    dl._progress_hook({"status": "downloading", "downloaded_bytes": 200,
                       "total_bytes": 1200, "speed": 100.0, "eta": 5})
    assert dl.state.eta == 5


def test_queue_items_have_independent_progress():
    from core.downloader import ProgressState
    a, b = ProgressState(), ProgressState()
    a.downloaded, a.total, a.eta = 10, 100, 5
    assert b.downloaded == 0 and b.eta == 0  # no shared state

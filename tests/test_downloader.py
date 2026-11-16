"""
tests/test_downloader.py
Filename sanitization, quality option derivation, error translation,
progress-state behavior with mocked yt-dlp hooks.
"""

from unittest import mock

import pytest

from core.downloader import Downloader, sanitize_filename, ProgressState
from core.video_info import QualityOption, build_quality_options, build_format_list
from utils.validators import friendly_ytdlp_error


# ------------------------------------------------------------ filenames
@pytest.mark.parametrize("raw,expected", [
    ("Normal Title", "Normal Title"),
    ("bad:chars|here?", "bad_chars_here_"),
    ("  spaced   out  ", "spaced out"),
    ("", "video"),
    ('quote"and\\slash/', "quote_and_slash_"),
    ("trailing dots...", "trailing dots"),
])
def test_sanitize_filename(raw, expected):
    assert sanitize_filename(raw) == expected


def test_sanitize_filename_length_limit():
    out = sanitize_filename("x" * 500)
    assert len(out) <= 180


# ------------------------------------------------------------ quality options
def _fake_info(heights, audio_only=True, exts=("mp4", "webm")):
    fmts = []
    for h in heights:
        fmts.append({"height": h, "vcodec": "avc1", "acodec": "mp4a", "ext": "mp4"})
        fmts.append({"height": h, "vcodec": "vp9", "acodec": "opus", "ext": "webm"})
    if audio_only:
        fmts.append({"height": None, "vcodec": "none", "acodec": "mp4a", "ext": "m4a"})
    return {"formats": fmts}


def test_quality_options_only_available_heights():
    opts = build_quality_options(_fake_info([1080, 720, 480]))
    labels = [o.label for o in opts]
    assert "1080p" in labels and "720p" in labels and "480p" in labels
    assert "2160p" not in labels and "1440p" not in labels
    assert "360p" not in labels
    assert labels[0] == "Best available"


def test_quality_options_descending():
    opts = build_quality_options(_fake_info([360, 1080, 720, 2160]))
    heights = [o.height for o in opts if o.height]
    assert heights == sorted(heights, reverse=True)


def test_quality_options_include_audio():
    opts = build_quality_options(_fake_info([720]))
    assert any(o.kind == "audio" for o in opts)


def test_build_format_list():
    assert build_format_list(_fake_info([720])) == ["mp4", "webm", "mp3"]
    assert build_format_list({"formats": [{"vcodec": "vp9", "ext": "webm", "height": 720}]}) == \
        ["webm", "mp3"]


# ------------------------------------------------------------ downloader
def test_progress_hook_updates_state():
    dl = Downloader("https://youtu.be/x", QualityOption("Best", "best"), "mp4", ".")
    dl._progress_hook({"status": "downloading", "downloaded_bytes": 500,
                       "total_bytes": 1000, "speed": 250.0, "eta": 2,
                       "filename": "f.mp4"})
    st = dl.state
    assert st.status == "downloading"
    assert st.percent == 50.0
    assert st.speed == 250.0
    dl._progress_hook({"status": "finished"})
    assert st.status == "merging"


def test_cancel_raises_inside_hook():
    dl = Downloader("https://youtu.be/x", QualityOption("Best", "best"), "mp4", ".")
    dl.cancel()
    import core.downloader as cd
    fake_ytdlp = mock.MagicMock()
    fake_ytdlp.utils.DownloadCancelled = type("DC", (Exception,), {})
    with mock.patch.object(cd, "yt_dlp", fake_ytdlp):
        with pytest.raises(Exception):
            dl._progress_hook({"status": "downloading"})


def test_ydl_opts_no_overwrite():
    dl = Downloader("https://youtu.be/x", QualityOption("Best", "best"), "mp4", "out")
    opts = dl._ydl_opts()
    assert opts["nooverwrites"] is True
    assert opts["overwrites"] is False


def test_ydl_opts_mp3_requires_ffmpeg():
    dl = Downloader("https://youtu.be/x", QualityOption("MP3", "bestaudio", kind="audio"),
                    "mp3", "out", ffmpeg_dir=None)
    with pytest.raises(RuntimeError, match="FFmpeg"):
        dl._ydl_opts()


def test_ydl_opts_mp3_with_ffmpeg():
    import tempfile, os
    d = tempfile.mkdtemp()
    dl = Downloader("https://youtu.be/x", QualityOption("MP3", "bestaudio", kind="audio"),
                    "mp3", "out", ffmpeg_dir=d)
    opts = dl._ydl_opts()
    pp = opts["postprocessors"][0]
    assert pp["preferredcodec"] == "mp3"


# ------------------------------------------------------------ errors
@pytest.mark.parametrize("raw,category", [
    ("ERROR: [youtube] abc: Sign in to confirm you're not a bot", "rate_limit"),
    ("ERROR: [youtube] abc: Private video. Sign in if granted access", "private"),
    ("ERROR: Video unavailable", "private"),
    ("ERROR: HTTP Error 429: Too Many Requests", "rate_limit"),
    ("ERROR: HTTP Error 403: Forbidden", "forbidden"),
    ("ERROR: Solve the challenge to continue", "captcha"),
    ("ERROR: Unexpected response from webpage request; please report this issue",
     "outdated_extractor"),
    ("ERROR: Unable to download webpage: timed out", "timeout"),
    ("<urlopen error [Errno 11001] getaddrinfo failed>", "dns"),
    ("ERROR: Unsupported URL: https://x", "unsupported"),
    ("ERROR: Requested merging but ffmpeg is not installed", "ffmpeg"),
])
def test_error_classification(raw, category):
    from utils.network import classify_error
    assert classify_error(raw) == category


def test_dns_error_never_mislabeled():
    from utils.network import classify_error
    # a generic socket error is NOT dns
    assert classify_error("connection reset by peer") != "dns"


def test_friendly_errors_use_truthful_categories():
    msg = friendly_ytdlp_error(Exception("ERROR: Video unavailable"))
    assert "cannot access" in msg or "unavailable" in msg.lower()

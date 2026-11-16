"""
tests/test_video_info.py
Metadata assembly with mocked yt-dlp (no network).
"""

from unittest import mock

import pytest

from core.video_info import fetch_info, VideoInfo


def _mock_ydl(info_dict):
    """
    Build a mock yt_dlp module whose YoutubeDL().extract_info returns info_dict.
    """
    mod = mock.MagicMock()
    ydl_instance = mock.MagicMock()
    ydl_instance.__enter__ = mock.Mock(return_value=ydl_instance)
    ydl_instance.__exit__ = mock.Mock(return_value=False)
    ydl_instance.extract_info = mock.Mock(return_value=info_dict)
    mod.YoutubeDL = mock.MagicMock(return_value=ydl_instance)
    mod.utils.DownloadError = type("DownloadError", (Exception,), {})
    return mod


BASE = {
    "webpage_url": "https://www.youtube.com/watch?v=abc",
    "title": "Test Video \n second line",
    "uploader": "Channel",
    "duration": 125,
    "view_count": 4321,
    "thumbnail": "https://thumb/x.jpg",
    "description": "desc",
    "extractor_key": "Youtube",
    "formats": [
        {"height": 1080, "vcodec": "avc1", "acodec": "none", "ext": "mp4"},
        {"height": 1080, "vcodec": "avc1", "acodec": "mp4a", "ext": "mp4"},
        {"height": 720, "vcodec": "avc1", "acodec": "mp4a", "ext": "mp4"},
        {"height": None, "vcodec": "none", "acodec": "mp4a", "ext": "m4a"},
    ],
}


def test_fetch_info_basic(monkeypatch):
    import core.video_info as vi
    monkeypatch.setattr(vi, "yt_dlp", _mock_ydl(BASE))
    info = fetch_info("https://www.youtube.com/watch?v=abc")
    assert info.title == "Test Video second line"
    assert info.duration == 125
    assert info.duration_text == "2:05"
    assert any(q.label == "1080p" for q in info.qualities)
    assert any(q.label == "720p" for q in info.qualities)
    assert not any(q.label == "2160p" for q in info.qualities)
    assert "mp3" in info.formats


def test_fetch_info_playlist_takes_first(monkeypatch):
    import core.video_info as vi
    info_dict = {"entries": [BASE, dict(BASE, title="second")], "title": "playlist"}
    monkeypatch.setattr(vi, "yt_dlp", _mock_ydl(info_dict))
    info = fetch_info("url")
    assert info.title == "Test Video second line" or info.title.startswith("Test Video")


def test_fetch_info_empty_playlist_raises(monkeypatch):
    import core.video_info as vi
    monkeypatch.setattr(vi, "yt_dlp", _mock_ydl({"entries": []}))
    with pytest.raises(RuntimeError, match="No downloadable"):
        fetch_info("url")


def test_duration_text_hours():
    info = VideoInfo(url="u", duration=7325)
    assert info.duration_text == "2:02:05"

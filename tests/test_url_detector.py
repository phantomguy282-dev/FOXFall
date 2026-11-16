"""
tests/test_url_detector.py
Platform detection across desktop / mobile / short URL variants.
"""

import pytest

from core.url_detector import detect_platform, is_supported_url


YOUTUBE_URLS = [
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtube.com/watch?v=dQw4w9WgXcQ",
    "https://m.youtube.com/watch?v=dQw4w9WgXcQ",
    "https://youtu.be/dQw4w9WgXcQ",
    "https://www.youtube.com/shorts/abcd1234",
    "https://www.youtube.com/watch?v=abc&feature=shared",
    "https://www.youtube-nocookie.com/embed/xyz",
    "https://music.youtube.com/watch?v=abc",
]
INSTAGRAM_URLS = [
    "https://www.instagram.com/reel/CqAbCdEfGhI/",
    "https://instagram.com/reel/CqAbCdEfGhI/",
    "https://www.instagram.com/p/CqAbCdEfGhI/",
    "https://m.instagram.com/reel/CqAbCdEfGhI/?igsh=abc",
    "https://instagr.am/p/CqAbCdEfGhI/",
]
TIKTOK_URLS = [
    "https://www.tiktok.com/@user/video/7234567890123456789",
    "https://vm.tiktok.com/ZMabcdef12/",
    "https://vt.tiktok.com/ZSabcdef12/",
    "https://m.tiktok.com/v/7234567890.html",
    "https://www.tiktok.com/t/ZTabcdef/",
]

INVALID_URLS = [
    "",
    "not a url",
    "https://example.com/video/123",
    "https://vimeo.com/123456",
    "https://facebook.com/watch/?v=1",
    "https://www.google.com",
    "ftp://youtube.com/watch?v=abc",
    "https://youtubee.com/watch?v=abc",
    "youtube fake",
]


@pytest.mark.parametrize("url", YOUTUBE_URLS)
def test_detects_youtube(url):
    assert detect_platform(url).key == "youtube"


@pytest.mark.parametrize("url", INSTAGRAM_URLS)
def test_detects_instagram(url):
    assert detect_platform(url).key == "instagram"


@pytest.mark.parametrize("url", TIKTOK_URLS)
def test_detects_tiktok(url):
    assert detect_platform(url).key == "tiktok"


@pytest.mark.parametrize("url", INVALID_URLS)
def test_rejects_invalid(url):
    assert detect_platform(url) is None
    assert not is_supported_url(url)


def test_case_insensitive_host():
    assert detect_platform("https://WWW.YOUTUBE.COM/watch?v=1").key == "youtube"


def test_missing_scheme_still_detected():
    assert is_supported_url("www.youtube.com/watch?v=abc")
    assert is_supported_url("youtu.be/abc")

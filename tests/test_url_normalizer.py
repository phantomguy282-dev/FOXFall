"""
tests/test_url_normalizer.py
Tracking param stripping, required param preservation, scheme fixing.
(No network: redirect resolution tested separately with mocks.)
"""

from unittest import mock

from core.url_normalizer import (
    ensure_scheme, normalize, strip_tracking_params, resolve_redirect,
)


def test_ensure_scheme_adds_https():
    assert ensure_scheme("youtube.com/watch?v=x") == "https://youtube.com/watch?v=x"
    assert ensure_scheme("https://youtu.be/x") == "https://youtu.be/x"


def test_strips_tracking_but_keeps_video_id():
    url = ("https://www.youtube.com/watch?v=dQw4w9WgXcQ"
           "&si=tracking123&utm_source=share&feature=youtu.be")
    out = strip_tracking_params(url)
    assert "v=dQw4w9WgXcQ" in out
    assert "si=" not in out
    assert "utm_source" not in out


def test_strips_instagram_share_params():
    url = "https://www.instagram.com/reel/ABC123/?igsh=MWxyz123&fbclid=junk"
    out = strip_tracking_params(url)
    assert "igsh" not in out and "fbclid" not in out
    assert "/reel/ABC123/" in out


def test_keeps_unknown_params():
    url = "https://www.youtube.com/watch?v=abc&customflag=1"
    out = strip_tracking_params(url)
    assert "customflag=1" in out


def test_normalize_end_to_end():
    out = normalize("https://www.youtube.com/watch?v=abc&&utm_content=x")
    assert out == "https://www.youtube.com/watch?v=abc"


def test_resolve_redirect_follows_location():
    resp = mock.Mock()
    resp.status_code = 301
    resp.headers = {"Location": "https://www.tiktok.com/@u/video/123"}
    with mock.patch.dict("sys.modules", {"requests": mock.MagicMock(head=lambda *a, **k: resp)}):
        # simulate requests module attribute
        import sys
        fake = sys.modules["requests"]
        fake.head = lambda *a, **k: resp
        out = resolve_redirect("https://vm.tiktok.com/ABC123/")
    assert out == "https://www.tiktok.com/@u/video/123"


def test_resolve_redirect_no_network_ok():
    # network failure must fall back to original URL, never raise
    with mock.patch.dict("sys.modules", {"requests": None}):
        out = resolve_redirect("https://vm.tiktok.com/XYZ/")
    assert out == "https://vm.tiktok.com/XYZ/"

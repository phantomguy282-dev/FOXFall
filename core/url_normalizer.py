"""
url_normalizer.py
URL cleaning / normalization and safe short-link resolution.

Goals:
  * Strip tracking parameters that do not identify the video.
  * Preserve parameters required to identify the video (e.g. ?v= on YouTube).
  * Resolve shortened links (youtu.be already canonical; vm./vt.tiktok.com,
    instagr.am and share links need redirect resolution) safely, following a
    bounded number of redirects without executing any platform scripts.
  * Never invent/rewrite hosts blindly -- yt-dlp handles the final URL.
"""

from __future__ import annotations

import re
from typing import Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .url_detector import detect_platform

# Parameters considered tracking / noise per platform.
_TRACKING_PARAMS = {
    "common": [
        "fbclid", "gclid", "utm_source", "utm_medium", "utm_campaign",
        "utm_term", "utm_content", "utm_id", "utm_source_url", "si",
        "_nc_cat", "_nc_sid", "_nc_ohc", "_nc_ht", "_nc_gid", "igsh",
        "igshid", "ig_web_button_share_sheet", "app_platform", "app_id",
        "share_app_id", "share_link_id", "tt_from", "refer", "referrer",
        "spm", "xlink", "is_from_webapp", "sender_device", "sender_id",
        "web_id", "checksum", "shp", "short_link", "redirect",
    ],
    "youtube": ["feature", "pp", "app", "persist_app", "time_continue",
                "t", "start", "bp", "ab_channel", "source_ve_path"],
    "instagram": [],
    "tiktok": [],
}

# Parameters that MUST be preserved (video identity).
_REQUIRED_PARAMS = {"youtube": {"v"}, "instagram": set(), "tiktok": set()}

_SHORT_HOSTS = {"vm.tiktok.com", "vt.tiktok.com", "m.tiktok.com",
                "instagr.am", "youtu.be"}

_MAX_REDIRECTS = 5
_RESOLVE_TIMEOUT = 10
_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/126.0.0.0 Safari/537.36")

_SLASHES = re.compile(r"/{2,}")


def _scheme_missing(url: str) -> bool:
    return not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url)


def ensure_scheme(url: str) -> str:
    """Add https:// when the URL has no scheme."""
    url = url.strip()
    if _scheme_missing(url):
        return "https://" + url
    return url


def strip_tracking_params(url: str) -> str:
    """Remove known tracking query parameters, keep video identity params."""
    url = ensure_scheme(url)
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    if not parsed.query:
        return url
    platform = detect_platform(url)
    platform_key = platform.key if platform else "common"

    keep: Dict[str, str] = {}
    try:
        pairs = parse_qsl(parsed.query, keep_blank_values=True)
    except ValueError:
        return url

    required = _REQUIRED_PARAMS.get(platform_key, set())
    blocked = set(_TRACKING_PARAMS["common"]) | set(_TRACKING_PARAMS.get(platform_key, []))

    for key, value in pairs:
        if key in required:
            keep[key] = value
        elif key in blocked:
            continue
        else:
            # keep unknown params except obviously empty ones
            if value != "" or key in required:
                keep[key] = value

    new_query = urlencode(keep)
    return urlunparse(parsed._replace(query=new_query))


def collapse_slashes(url: str) -> str:
    """Collapse duplicated slashes in path portion only."""
    url = ensure_scheme(url)
    try:
        parsed = urlparse(url)
    except ValueError:
        return url
    path = _SLASHES.sub("/", parsed.path)
    return urlunparse(parsed._replace(path=path))


def normalize(url: str) -> str:
    """Full normalization pipeline (no network access)."""
    url = ensure_scheme(url.strip())
    url = collapse_slashes(url)
    url = strip_tracking_params(url)
    return url


def resolve_redirect(url: str, max_redirects: int = _MAX_REDIRECTS) -> str:
    """
    Follow HTTP redirects of short links safely.

    Returns the final URL, or the original URL if resolution fails
    (yt-dlp will then attempt extraction on the original link anyway).
    """
    url = ensure_scheme(url)
    try:
        # Import here so that a missing requests dependency does not break
        # the whole app: requests is part of yt-dlp's ecosystem but we do
        # not want a hard import failure at module import time.
        import requests  # type: ignore
    except ImportError:
        return url

    current = url
    try:
        for _ in range(max_redirects):
            response = requests.head(
                current,
                allow_redirects=False,
                timeout=_RESOLVE_TIMEOUT,
                headers={"User-Agent": _USER_AGENT},
            )
            if 300 <= response.status_code < 400:
                location = response.headers.get("Location", "")
                if not location:
                    return current
                current = urljoin_s(current, location)
            else:
                # Some hosts do not answer HEAD: retry with GET on the first hop.
                if response.status_code in (403, 405) and current == url:
                    response = requests.get(
                        current,
                        allow_redirects=False,
                        timeout=_RESOLVE_TIMEOUT,
                        headers={"User-Agent": _USER_AGENT},
                        stream=True,
                    )
                    if 300 <= response.status_code < 400:
                        location = response.headers.get("Location", "")
                        if location:
                            current = urljoin_s(current, location)
                            continue
                    response.close()
                    return current
                return current
        return current
    except Exception:
        return url


def urljoin_s(base: str, location: str) -> str:
    """Resolve *location* against *base* (thin wrapper around urljoin)."""
    from urllib.parse import urljoin
    return urljoin(base, location)


def normalize_full(url: str, resolve: bool = True) -> str:
    """
    Normalize and, when the URL is a short/share link, resolve redirects.
    Falls back silently to the plain normalized URL on network problems.
    TikTok URLs go through the dedicated tiktok.canonicalize() path which
    handles short links and username-less URLs via the public mobile page.
    """
    normalized = normalize(url)
    if not resolve:
        return normalized
    try:
        parsed = urlparse(normalized)
        host = (parsed.netloc or "").lower()
    except ValueError:
        return normalized

    platform = detect_platform(normalized)
    if platform and platform.key == "tiktok":
        from .tiktok import canonicalize
        return normalize(canonicalize(normalized))

    if host in _SHORT_HOSTS:
        resolved = resolve_redirect(normalized)
        return normalize(resolved) if resolved else normalized
    return normalized

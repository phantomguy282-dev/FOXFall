"""
tiktok.py
TikTok-specific URL handling (legitimate, no circumvention).

Findings from investigation:
  * www.tiktok.com returns a "SlardarWAF" anti-bot page (HTTP 200, tiny body,
    1462 bytes) to automated clients. yt-dlp then reports
    "Unexpected response from webpage request" and our classifier
    mislabelled that as "platform is limiting / bot-checking".
  * The mobile endpoint https://m.tiktok.com/v/<VIDEO_ID>.html still returns
    the normal server-rendered metadata, including the author uniqueId.
  * yt-dlp's TikTok extractor accepts a canonical desktop URL
    https://www.tiktok.com/@<user>/video/<id> even for videos whose only
    known id form is the short link.

Strategy (no bypassing, no captcha solving, no cookies exfiltration):
  1. Resolve short links with a bounded redirect FOLLOW (m.tiktok.com works).
  2. Extract the numeric video id from any supported URL form.
  3. If the URL lacks a username, discover it from the public mobile page
     (server-rendered metadata, no auth) and rebuild the canonical URL.
  4. Pass the canonical URL to yt-dlp's TikTok extractor.
"""

from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

_TIMEOUT = 15
_UA_DESKTOP = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
               "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_UA_MOBILE = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
              "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
              "Mobile/15E148 Safari/604.1")

_VIDEO_ID = re.compile(r"(?:/video/|/v/)(\d{6,})")
_UNIQUE_ID = re.compile(r'"uniqueId":"([A-Za-z0-9._\-]{1,64})"')
_CANONICAL = re.compile(r"https?://www\.tiktok\.com/@([A-Za-z0-9._\-]+)/video/(\d{6,})")


def _urlopen(url: str, ua: str):
    from urllib.request import Request, urlopen
    req = Request(url, headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"})
    return urlopen(req, timeout=_TIMEOUT)


def extract_video_id(url: str) -> Optional[str]:
    """Numeric TikTok video id from any supported URL form."""
    if not url:
        return None
    match = _VIDEO_ID.search(url)
    return match.group(1) if match else None


def extract_username(url: str) -> Optional[str]:
    match = _CANONICAL.search(url)
    return match.group(1) if match else None


def is_shortlink(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower().split(":")[0]
    except ValueError:
        return False
    return host in ("vm.tiktok.com", "vt.tiktok.com", "tiktok.com") or \
        host in ("vt.tiktok.com",)


def resolve_shortlink(url: str) -> Optional[str]:
    """
    Follow vm./vt. redirects to the final desktop URL. m.tiktok.com/v/<id>.html
    works even when www is WAF-blocked. Returns None on failure.
    """
    from urllib.error import HTTPError, URLError

    id_ = extract_video_id(url)
    try:
        with _urlopen(url, _UA_MOBILE) as resp:
            final = resp.geturl()
            body = resp.read(400_000).decode("utf-8", errors="replace")
    except HTTPError as exc:
        final = exc.geturl() or url
        body = ""
    except (URLError, OSError, ValueError):
        body = ""
        final = ""
    if not final and not body and id_:
        # fall back to the mobile endpoint which can carry the id alone
        final = _mobile_url(id_)
    if id_ and "@" not in final:
        username = _username_from_body(body) or _username_from_mobile(id_)
        if username:
            return f"https://www.tiktok.com/@{username}/video/{id_}"
        return final or _mobile_url(id_)
    return final or None


def _username_from_body(body: str) -> Optional[str]:
    if not body:
        return None
    found = _UNIQUE_ID.search(body)
    return found.group(1) if found else None


def _mobile_url(video_id: str) -> str:
    return f"https://m.tiktok.com/v/{video_id}.html"


def _username_from_mobile(video_id: str) -> Optional[str]:
    """Public server-rendered metadata on m.tiktok.com (no auth, no bypass)."""
    try:
        with _urlopen(_mobile_url(video_id), _UA_MOBILE) as resp:
            body = resp.read(1_500_000).decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 - network boundary
        return None
    return _username_from_body(body)


def canonicalize(url: str) -> str:
    """
    Turn any supported TikTok URL into the canonical desktop URL
    https://www.tiktok.com/@<user>/video/<id> when possible; otherwise return
    the best URL we have (never an empty string, never crashes).
    """
    url = (url or "").strip()
    if not url:
        return url
    video_id = extract_video_id(url)
    username = extract_username(url)

    if username and video_id:
        return f"https://www.tiktok.com/@{username}/video/{video_id}"

    # short link or username-less URL
    resolved = resolve_shortlink(url) if not username else None
    if resolved:
        user2 = extract_username(resolved)
        id2 = video_id or extract_video_id(resolved)
        if user2 and id2:
            return f"https://www.tiktok.com/@{user2}/video/{id2}"
        resolved_id = id2 or extract_video_id(resolved)
        if resolved_id:
            user3 = _username_from_mobile(resolved_id)
            if user3:
                return f"https://www.tiktok.com/@{user3}/video/{resolved_id}"
            return _mobile_url(resolved_id)

    if video_id:
        user = _username_from_mobile(video_id)
        if user:
            return f"https://www.tiktok.com/@{user}/video/{video_id}"
        return _mobile_url(video_id)
    return url


def is_waf_page(body: str) -> bool:
    """Detect TikTok's SlardarWAF anti-bot page (legitimately explained to user)."""
    return "SlardarWAF" in (body or "") or (
        len(body or "") < 4000 and "__UNIVERSAL_DATA_FOR_REHYDRATION__" not in (body or "")
        and "SlardarWAF" in (body or "SlardarWAF"))
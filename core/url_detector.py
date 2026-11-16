"""
url_detector.py
Detect which platform a URL belongs to (YouTube, Instagram, TikTok or unknown).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse


@dataclass(frozen=True)
class Platform:
    """Simple platform descriptor."""

    key: str          # short internal key: youtube / instagram / tiktok
    name: str         # display name: YouTube / Instagram / TikTok
    icon: str         # text icon: [YT] / [IG] / [TT]
    color: str        # ui theme color key


PLATFORMS = {
    "youtube": Platform("youtube", "YouTube", "[YT]", "red"),
    "instagram": Platform("instagram", "Instagram", "[IG]", "magenta"),
    "tiktok": Platform("tiktok", "TikTok", "[TT]", "cyan"),
}

_YOUTUBE_HOSTS = re.compile(
    r"(^|\.)(youtube\.com|youtu\.be|youtube-nocookie\.com)$", re.IGNORECASE
)
_INSTAGRAM_HOSTS = re.compile(r"(^|\.)(instagram\.com|instagr\.am)$", re.IGNORECASE)
_TIKTOK_HOSTS = re.compile(r"(^|\.)(tiktok\.com)$", re.IGNORECASE)


def _host_of(url: str) -> str:
    """Return lowercase host of a URL (adds scheme if missing)."""
    candidate = url.strip()
    if not candidate:
        return ""
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        host = urlparse(candidate).netloc.lower()
    except ValueError:
        return ""
    host = host.split("@")[-1]          # strip userinfo if any
    host = host.split(":")[0]           # strip port
    return host


def detect_platform(url: str) -> Optional[Platform]:
    """Detect the platform of *url*. Returns Platform or None if unsupported."""
    if not url or not isinstance(url, str):
        return None
    url = url.strip()
    if not url or " " in url or not url.lower().startswith(("http://", "https://", "www.", "m.", "youtu.be", "instagram", "tiktok", "instagr.am")):
        # allow missing scheme but require a plausible site prefix
        if not url.lower().startswith(("www.", "m.", "youtu", "insta", "tiktok")):
            return None
    host = _host_of(url)
    if not host:
        return None
    if _YOUTUBE_HOSTS.search(host):
        return PLATFORMS["youtube"]
    if _INSTAGRAM_HOSTS.search(host):
        return PLATFORMS["instagram"]
    if _TIKTOK_HOSTS.search(host):
        return PLATFORMS["tiktok"]
    return None


def is_supported_url(url: str) -> bool:
    """True if *url* points to one of the supported platforms."""
    return detect_platform(url) is not None

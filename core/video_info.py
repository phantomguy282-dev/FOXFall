"""
video_info.py
Fetch video metadata using yt-dlp (pure Python, no subprocess needed).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

from .url_detector import Platform

try:
    import yt_dlp  # type: ignore
except ImportError:  # pragma: no cover
    yt_dlp = None


@dataclass
class QualityOption:
    """One selectable quality/format row."""

    label: str          # e.g. "1080p (MP4)" or "Best available"
    format_selector: str  # yt-dlp format string, e.g. "bestvideo[height<=1080]+bestaudio/best[height<=1080]"
    height: Optional[int] = None
    kind: str = "video"   # video | audio

    def __str__(self) -> str:  # pragma: no cover - display only
        return self.label


@dataclass
class VideoInfo:
    """Metadata preview shown before downloading."""

    url: str
    title: str = "(unknown)"
    platform: Optional[Platform] = None
    uploader: str = ""
    duration: Optional[int] = None        # seconds
    view_count: Optional[int] = None
    thumbnail: str = ""                   # thumbnail URL (terminal-safe preview only)
    description_short: str = ""
    qualities: List[QualityOption] = field(default_factory=list)
    formats: List[str] = field(default_factory=list)  # mp4 / webm / mp3
    extractor: str = ""
    live: bool = False

    @property
    def duration_text(self) -> str:
        if not self.duration:
            return "--:--"
        s = int(self.duration)
        h, rem = divmod(s, 3600)
        m, sec = divmod(rem, 60)
        if h:
            return f"{h}:{m:02d}:{sec:02d}"
        return f"{m}:{sec:02d}"


def _sanitize_title(raw: str) -> str:
    return re.sub(r"\s+", " ", (raw or "")).strip()


def _format_height(h) -> Optional[int]:
    try:
        return int(h) if h else None
    except (TypeError, ValueError):
        return None


def build_quality_options(info_dict: dict) -> List[QualityOption]:
    """
    Derive quality options from yt-dlp info dict.
    Only heights actually present in the formats list are offered.
    """
    heights = set()
    has_audio_only = False
    exts = set()
    for f in info_dict.get("formats") or []:
        if f.get("vcodec") in (None, "none"):
            if f.get("acodec") not in (None, "none"):
                has_audio_only = True
            continue
        h = _format_height(f.get("height"))
        if h:
            heights.add(h)
        if f.get("ext"):
            exts.add(str(f["ext"]).lower())

    options: List[QualityOption] = []
    # Best available first
    options.append(QualityOption(
        label="Best available",
        format_selector="bestvideo*+bestaudio/best",
        height=None,
        kind="video",
    ))

    wanted = [2160, 1440, 1080, 720, 480, 360]
    for h in wanted:
        if h in heights:
            options.append(QualityOption(
                label=f"{h}p",
                format_selector=(
                    f"bestvideo[height<={h}]+bestaudio/"
                    f"best[height<={h}]/best[height<={h}]"
                ),
                height=h,
                kind="video",
            ))

    # Sort video qualities descending by height (best first, then 2160...)
    options[1:] = sorted(options[1:], key=lambda q: -(q.height or 0))

    if has_audio_only or True:  # audio extraction always offered when ffmpeg exists
        options.append(QualityOption(
            label="MP3 (audio only)",
            format_selector="bestaudio/best",
            height=None,
            kind="audio",
        ))

    return options


def build_format_list(info_dict: dict) -> List[str]:
    exts = set()
    for f in info_dict.get("formats") or []:
        if f.get("vcodec") not in (None, "none") and f.get("ext"):
            exts.add(str(f["ext"]).lower())
    out = []
    for e in ("mp4", "webm"):
        if e in exts:
            out.append(e)
    out.append("mp3")  # extraction path (requires ffmpeg; validated at download time)
    return out or ["mp4", "mp3"]


def fetch_info(url: str, platform: Optional[Platform] = None,
               timeout: int = 20) -> VideoInfo:
    """
    Fetch metadata for *url* via yt-dlp. Raises yt_dlp.utils.DownloadError
    on invalid/private/unavailable videos (callers translate to friendly text).
    """
    if yt_dlp is None:
        raise RuntimeError("yt-dlp is not installed")

    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "noplaylist": True,
        "socket_timeout": timeout,
        "extract_flat": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        raw = ydl.extract_info(url, download=False)

    # Playlist guard: take first entry if a single-entry playlist slipped in
    if "entries" in raw:
        entries = [e for e in raw["entries"] if e]
        if not entries:
            raise RuntimeError("No downloadable video found at that URL")
        raw = entries[0]

    info = VideoInfo(
        url=raw.get("webpage_url") or url,
        title=_sanitize_title(raw.get("title")),
        platform=platform,
        uploader=raw.get("uploader") or raw.get("channel") or "",
        duration=raw.get("duration"),
        view_count=raw.get("view_count"),
        thumbnail=raw.get("thumbnail") or "",
        description_short=(raw.get("description") or "")[:160],
        qualities=build_quality_options(raw),
        formats=build_format_list(raw),
        extractor=raw.get("extractor_key") or raw.get("extractor") or "",
        live=bool(raw.get("is_live")),
    )
    return info

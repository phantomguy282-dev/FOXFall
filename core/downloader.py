"""
downloader.py
yt-dlp based download engine with progress hooks. One download per instance.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional

from .video_info import QualityOption

try:
    import yt_dlp  # type: ignore
except ImportError:  # pragma: no cover
    yt_dlp = None


@dataclass
class ProgressState:
    """Live snapshot of one download, updated by yt-dlp hooks."""

    status: str = "pending"       # pending | preparing | downloading | merging | done | error | cancelled
    filename: str = ""
    downloaded: int = 0
    total: int = 0
    speed: float = 0.0            # bytes/sec
    eta: int = 0                  # seconds
    percent: float = 0.0
    error: str = ""
    filepath: str = ""
    fragments: str = ""

    def snapshot(self) -> Dict:
        return {
            "status": self.status,
            "filename": self.filename,
            "downloaded": self.downloaded,
            "total": self.total,
            "speed": self.speed,
            "eta": self.eta,
            "percent": self.percent,
            "error": self.error,
            "filepath": self.filepath,
            "fragments": self.fragments,
        }


_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

# Sentinel: ETA genuinely unknown (no yt-dlp value AND no computable estimate)
ETA_UNKNOWN = -1


def compute_eta(downloaded: int, total: int, speed: float,
                ytdlp_eta=None) -> int:
    """
    Reliable ETA in seconds.

    1. Prefer the actual ETA supplied by yt-dlp when valid (> 0).
    2. Otherwise estimate: remaining_bytes / current_speed.
    3. When neither is possible return ETA_UNKNOWN (-1) so the UI can show
       "Calculating..." instead of a false 0.0.
    Never returns negative (other than the sentinel), NaN or infinity.
    """
    # 1) yt-dlp supplied value
    try:
        if ytdlp_eta is not None:
            eta_val = float(ytdlp_eta)
            if eta_val == eta_val and eta_val > 0 and eta_val != float("inf"):
                return int(eta_val)
    except (TypeError, ValueError):
        pass

    remaining = max(0, int(total or 0) - int(downloaded or 0))
    if remaining <= 0:
        return 0
    # 2) compute from speed
    try:
        spd = float(speed or 0.0)
        if spd > 0 and spd == spd and spd != float("inf"):
            return max(1, int(remaining / spd))
    except (TypeError, ValueError):
        pass
    return ETA_UNKNOWN


def sanitize_filename(name: str, fallback: str = "video") -> str:
    """Windows-safe filename."""
    name = _INVALID_FILENAME.sub("_", name or "")
    name = name.strip(" .")
    name = re.sub(r"\s+", " ", name)
    if not name:
        name = fallback
    return name[:180]


class Downloader:
    """
    Runs a single yt-dlp download in a worker thread.
    Reports progress through ProgressState (polled by the UI).
    """

    def __init__(self, url: str, quality: QualityOption, fmt: str,
                 output_dir: str, ffmpeg_dir: Optional[str] = None):
        self.url = url
        self.quality = quality
        self.fmt = fmt.lower()
        self.output_dir = output_dir
        self.ffmpeg_dir = ffmpeg_dir
        self._ffmpeg_available = bool(ffmpeg_dir)
        self.state = ProgressState()
        self._cancel_requested = False
        self._thread: Optional[threading.Thread] = None
        self._start_time = 0.0

    # ------------------------------------------------------------------ #
    # hooks
    # ------------------------------------------------------------------ #
    def _progress_hook(self, d) -> None:
        state = self.state
        if self._cancel_requested:
            raise yt_dlp.utils.DownloadCancelled()

        phase = d.get("status")
        if phase == "downloading":
            state.status = "downloading"
            state.filename = d.get("filename") or state.filename
            state.downloaded = int(d.get("downloaded_bytes") or 0)
            total = d.get("total_bytes") or d.get("total_bytes_estimate")
            state.total = int(total or 0)
            state.speed = float(d.get("speed") or 0.0)
            state.eta = compute_eta(
                downloaded=state.downloaded,
                total=state.total,
                speed=state.speed,
                ytdlp_eta=d.get("eta"),
            )
            frag = d.get("fragment_index")
            frag_count = d.get("fragment_count")
            if frag is not None and frag_count:
                state.fragments = f"frag {frag}/{frag_count}"
            if state.total:
                state.percent = min(100.0, state.downloaded / state.total * 100.0)
        elif phase == "finished":
            state.downloaded = state.total or state.downloaded
            state.percent = 100.0 if state.total else state.percent
            state.status = "merging"
            state.eta = 0  # finished: no remaining time

    def cancel(self) -> None:
        self._cancel_requested = True

    # ------------------------------------------------------------------ #
    # options
    # ------------------------------------------------------------------ #
    def _ydl_opts(self) -> Dict:
        outtmpl_base = os.path.join(self.output_dir, "%(title)s.%(ext)s")
        opts: Dict = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "progress_hooks": [self._progress_hook],
            "outtmpl": outtmpl_base,
            # never overwrite existing files silently: suffix part numbers
            "overwrites": False,
            "nooverwrites": True,
            "continuedl": True,
            "retries": 3,
            "fragment_retries": 3,
            "socket_timeout": 30,
            "windowsfilenames": True,
            "restrictfilenames": False,
            "trim_file_name": 180,
        }
        if self.ffmpeg_dir and os.path.isdir(self.ffmpeg_dir):
            opts["ffmpeg_location"] = self.ffmpeg_dir

        if self.quality.kind == "audio" or self.fmt == "mp3":
            if not self.ffmpeg_dir:
                raise RuntimeError(
                    "MP3 extraction requires FFmpeg, which was not found. "
                    "Choose a video format instead or install FFmpeg."
                )
            opts["format"] = "bestaudio/best"
            opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }]
        else:
            if self._ffmpeg_available:
                # Always end the selector chain with an unconditional
                # fallback so a valid video never fails with
                # "Requested format is not available".
                opts["format"] = (
                    f"{self.quality.format_selector}/bestvideo*+bestaudio/best"
                )
                if self.fmt in ("mp4", "webm"):
                    opts["merge_output_format"] = self.fmt
                    opts["postprocessors"] = [{
                        "key": "FFmpegVideoRemuxer",
                        "preferedformat": self.fmt,
                    }]
            else:
                # No FFmpeg: prefer a progressive format (audio+video muxed)
                # so downloads still succeed. Progressive streams top out at
                # ~720p on YouTube; if none exists (DASH-only video), fall
                # back to best single stream and let yt-dlp report honestly.
                height_filter = f"[height<={self.quality.height}]" if self.quality.height else ""
                if self.quality.height:
                    opts["format"] = (
                        f"best[height<={self.quality.height}][vcodec!=none][acodec!=none]/"
                        f"best[height<={self.quality.height}]/best"
                    )
                else:
                    opts["format"] = "best[vcodec!=none][acodec!=none]/best"
        return opts

    # ------------------------------------------------------------------ #
    # execution
    # ------------------------------------------------------------------ #
    def _run(self) -> None:
        state = self.state
        try:
            if yt_dlp is None:
                raise RuntimeError("yt-dlp is not installed")
            state.status = "preparing"
            self._start_time = time.time()
            with yt_dlp.YoutubeDL(self._ydl_opts()) as ydl:
                info = ydl.extract_info(self.url, download=True)
                if info and "entries" in info:
                    entries = [e for e in info["entries"] if e]
                    info = entries[0] if entries else info
                # prepare_filename on the FINAL info dict reflects the
                # post-processed container; the progress-hook filename may be
                # an intermediate format file (.f301.mp4 etc.), which must
                # never be treated as the result.
                base_guess = ydl.prepare_filename(info) if info else ""
            state.filepath = self._resolve_final_path(base_guess or state.filename)
            state.status = "done"
            state.percent = 100.0
        except yt_dlp.utils.DownloadCancelled if yt_dlp else Exception:
            state.status = "cancelled"
        except Exception as exc:  # noqa: BLE001 - surface to UI
            if self._cancel_requested:
                state.status = "cancelled"
            else:
                state.status = "error"
                state.error = str(exc)

    def _resolve_final_path(self, prepared: str) -> str:
        """
        yt-dlp post-processing may change the extension (mp3/remux) and the
        progress-hook filename can be an intermediate format file. Prefer the
        most recently written real file matching the base stem; verify it
        exists before returning it.
        """
        base = prepared or ""
        if base:
            base_dir = os.path.dirname(base) or self.output_dir
            stem = os.path.splitext(os.path.basename(base))[0]
            # drop yt-dlp format-suffixes like ".f301" from the stem
            stem = re.sub(r"\.f\d+$", "", stem)
            try:
                candidates = [
                    os.path.join(base_dir, f)
                    for f in os.listdir(base_dir)
                    if f.startswith(stem) and not re.search(r"\.f\d+\.", f)
                    and not f.endswith((".part", ".ytdl", ".tmp"))
                ]
                if candidates:
                    return max(candidates, key=os.path.getmtime)
            except OSError:
                pass
        # Last resort: newest media file written in the output dir since we
        # started. This guarantees a real file is reported when yt-dlp had to
        # sanitize the title differently than prepare_filename suggested.
        try:
            media = [
                os.path.join(self.output_dir, f)
                for f in os.listdir(self.output_dir)
                if f.lower().endswith((".mp4", ".webm", ".mkv", ".mp3", ".m4a"))
                and os.path.getmtime(os.path.join(self.output_dir, f))
                >= self._start_time - 1
            ]
            if media:
                return max(media, key=os.path.getmtime)
        except OSError:
            pass
        return base

    def start(self) -> threading.Thread:
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="foxfall-download")
        self._thread.start()
        return self._thread

    def run_blocking(self) -> ProgressState:
        self.start().join()
        return self.state

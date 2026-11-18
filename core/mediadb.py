"""
mediadb.py
Media Library index: scans real local media files, extracts metadata with
FFprobe, generates thumbnail files with FFmpeg, and persists everything to
JSON in the user-data directory.

Design:
  * Index file   : <user-data>/config/library.json
  * Thumbnail dir: <user-data>/thumbs/
  * Entries keyed by absolute path (dedupe by construction).
  * Scan runs incrementally: files whose mtime+size are unchanged keep their
    stored metadata/thumbnail, so rescans are fast and recoverable.
  * Missing/inaccessible files are flagged "missing" — never silently removed.
  * Scanning is incremental and state-saving, so an interrupted scan resumes.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
from typing import Any, Callable, Dict, List, Optional

MEDIA_EXTS = {".mp4", ".webm", ".mkv", ".avi", ".mov", ".m4a",
              ".mp3", ".wav", ".flac", ".aac", ".ogg"}


def user_data_dir(explicit: Optional[str] = None) -> str:
    if explicit or os.environ.get("FOXFall_USER_DATA"):
        return explicit or os.environ["FOXFall_USER_DATA"]
    appdata = os.environ.get("APPDATA")
    if appdata:
        return os.path.join(appdata, "FOXFall")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return root


def index_path(explicit: Optional[str] = None) -> str:
    return os.path.join(user_data_dir(explicit), "config", "library.json")


def thumbs_dir(explicit: Optional[str] = None) -> str:
    return os.path.join(user_data_dir(explicit), "thumbs")


class MediaLibrary:
    """Persistent media index with ffprobe metadata + ffmpeg thumbnails."""

    def __init__(self, user_data: Optional[str] = None,
                 ffmpeg_dir: Optional[str] = None):
        self.user_data = user_data
        self.ffmpeg_dir = ffmpeg_dir or ""
        self._lock = threading.Lock()
        self._cancel = threading.Event()

    # ------------------------------------------------------------- paths
    def _index_file(self) -> str:
        return index_path(self.user_data)

    def _thumb_dir(self) -> str:
        d = thumbs_dir(self.user_data)
        os.makedirs(d, exist_ok=True)
        return d

    # ------------------------------------------------------------- io
    def load(self) -> Dict[str, Any]:
        try:
            with open(self._index_file(), "r", encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and isinstance(data.get("entries"), dict):
                data.setdefault("version", 1)
                return data
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError):
            pass
        return {"version": 1, "entries": {}, "favorites": []}

    def save(self, data: Dict[str, Any]) -> bool:
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self._index_file()), exist_ok=True)
                tmp = self._index_file() + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2)
                os.replace(tmp, self._index_file())
                return True
            except OSError:
                return False

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _thumb_key(path: str, mtime: float, size: int) -> str:
        h = hashlib.sha1(f"{path}|{mtime}|{size}".encode("utf-8")).hexdigest()[:16]
        return h + ".jpg"

    def _ffprobe(self, path: str) -> Optional[Dict[str, Any]]:
        exe = os.path.join(self.ffmpeg_dir,
                           "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if not os.path.isfile(exe):
            return None
        try:
            out = subprocess.run(
                [exe, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", path],
                capture_output=True, text=True, timeout=30)
            data = json.loads(out.stdout or "{}")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return None
        fmt = data.get("format", {})
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        try:
            dur = float(fmt.get("duration") or 0)
        except (TypeError, ValueError):
            dur = 0
        m, s = divmod(int(dur), 60)
        h, m2 = divmod(m, 60)
        try:
            size = int(fmt.get("size") or 0)
        except (TypeError, ValueError):
            size = 0
        return {
            "container": fmt.get("format_name", ""),
            "duration": dur,
            "duration_text": (f"{h}:{m2:02d}:{s:02d}" if h
                              else f"{m:02d}:{s:02d}") if dur else "",
            "resolution": (f"{video.get('width')}x{video.get('height')}"
                           if video else ""),
            "vcodec": video.get("codec_name", "") if video else "",
            "acodec": audio.get("codec_name", "") if audio else "",
            "bitrate_kbps": (int(fmt.get("bit_rate") or 0) // 1000
                             if fmt.get("bit_rate") else 0),
            "size": size,
            "streams": len(streams),
            "has_video": video is not None,
            "has_audio": audio is not None,
        }

    def _thumbnail(self, path: str, duration: float,
                   key: str) -> Optional[str]:
        exe = os.path.join(self.ffmpeg_dir,
                           "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if not os.path.isfile(exe):
            return None
        out = os.path.join(self._thumb_dir(), key)
        if os.path.isfile(out) and os.path.getsize(out) > 0:
            return out  # cached
        # timestamp ~10% into the video, min 1s, capped
        ts = max(1.0, min(duration * 0.1, duration - 1)) if duration > 2 else 0.5
        try:
            subprocess.run(
                [exe, "-v", "quiet", "-ss", str(ts), "-i", path,
                 "-frames:v", "1", "-q:v", "4", "-y", out],
                capture_output=True, timeout=45)
            if os.path.isfile(out) and os.path.getsize(out) > 0:
                return out
        except (subprocess.TimeoutExpired, OSError):
            pass
        # try a frame at 0s as fallback
        try:
            subprocess.run(
                [exe, "-v", "quiet", "-i", path, "-frames:v", "1", "-y", out],
                capture_output=True, timeout=30)
            if os.path.isfile(out) and os.path.getsize(out) > 0:
                return out
        except (subprocess.TimeoutExpired, OSError):
            pass
        return None

    # ------------------------------------------------------------- scanning
    def collect_files(self, extra_dirs: Optional[List[str]] = None) -> List[str]:
        """Media files from the download dir + any user-added folders."""
        from core import settings as settings_mod
        root = settings_mod.resolve_download_dir()
        folders = {root}
        for d in (extra_dirs or []):
            if d and os.path.isdir(d):
                folders.add(d)
        found = []
        for folder in folders:
            for dirpath, _dirnames, filenames in os.walk(folder):
                for name in filenames:
                    ext = os.path.splitext(name)[1].lower()
                    if ext in MEDIA_EXTS:
                        found.append(os.path.join(dirpath, name))
        return sorted(found)

    def scan(self, extra_dirs: Optional[List[str]] = None,
             progress: Optional[Callable[[int, int, str], None]] = None,
             on_entry: Optional[Callable[[Dict[str, Any]], None]] = None
             ) -> Dict[str, Any]:
        """
        Incremental, resumable scan. Emits progress(scanned, total, path).
        Existing entries with unchanged mtime+size keep metadata/thumbnails.
        """
        if not self.ffmpeg_dir or not os.path.isdir(self.ffmpeg_dir):
            return {"error": "FFmpeg/FFprobe not available - cannot index media."}

        self._cancel.clear()
        files = self.collect_files(extra_dirs)
        data = self.load()
        entries: Dict[str, Any] = data["entries"]
        total = len(files)
        scanned = 0

        for path in files:
            if self._cancel.is_set():
                break  # save partial state; resumable
            scanned += 1
            if progress:
                progress(min(scanned, total), total, path)
            try:
                st = os.stat(path)
                mtime, size = st.st_mtime, st.st_size
            except OSError:
                continue
            old = entries.get(path)
            if old and not old.get("missing") and \
                    old.get("mtime") == mtime and old.get("size") == size:
                old["missing"] = False
                continue  # unchanged

            meta = self._ffprobe(path)
            if meta is None:
                # corrupted/unsupported: keep a minimal placeholder entry
                entries[path] = {
                    "path": path, "title": os.path.basename(path),
                    "mtime": mtime, "size": size, "missing": False,
                    "error": "ffprobe failed", "thumb": "",
                    "indexed_at": time.time(),
                }
            else:
                key = self._thumb_key(path, mtime, size)
                thumb = self._thumbnail(path, meta["duration"], key) \
                    if meta["has_video"] else ""
                entries[path] = {
                    "path": path,
                    "title": os.path.splitext(os.path.basename(path))[0],
                    "mtime": mtime, "size": size,
                    "duration": meta["duration"],
                    "duration_text": meta["duration_text"],
                    "resolution": meta["resolution"],
                    "vcodec": meta["vcodec"], "acodec": meta["acodec"],
                    "container": meta["container"],
                    "bitrate_kbps": meta["bitrate_kbps"],
                    "streams": meta["streams"],
                    "has_video": meta["has_video"],
                    "has_audio": meta["has_audio"],
                    "thumb": thumb or "",
                    "missing": False,
                    "indexed_at": time.time(),
                }
            data["entries"] = entries
            self.save(data)  # resumable: state saved after every file
            if on_entry:
                on_entry(entries[path])

        # mark vanished files as missing (keep entries; user decides removal)
        known = set(files)
        for path, entry in entries.items():
            if path not in known and not entry.get("missing"):
                entry["missing"] = True
        data["entries"] = entries
        self.save(data)
        data["last_scan"] = time.time()
        self.save(data)
        return {"scanned": scanned, "total": total,
                "indexed": len(entries), "cancelled": self._cancel.is_set()}

    def cancel_scan(self) -> None:
        self._cancel.set()

    # ------------------------------------------------------------- queries
    def list_entries(self, query: str = "", sort: str = "date",
                     include_missing: bool = False) -> List[Dict[str, Any]]:
        data = self.load()
        entries: List[Dict[str, Any]] = []
        for path, e in data["entries"].items():
            if e.get("missing") and not include_missing:
                continue
            if query and query.lower() not in e.get("title", "").lower():
                continue
            e = dict(e)
            e["favorite"] = path in data.get("favorites", [])
            entries.append(e)
        if sort == "name":
            entries.sort(key=lambda e: e.get("title", "").lower())
        elif sort == "size":
            entries.sort(key=lambda e: -(e.get("size") or 0))
        else:  # date
            entries.sort(key=lambda e: -(e.get("mtime") or 0))
        return entries

    def set_favorite(self, path: str, fav: bool) -> bool:
        data = self.load()
        favs = set(data.get("favorites", []))
        if fav:
            favs.add(path)
        else:
            favs.discard(path)
        data["favorites"] = sorted(favs)
        return self.save(data)

    def remove_entry(self, path: str) -> bool:
        data = self.load()
        if path in data["entries"]:
            del data["entries"][path]
            data["favorites"] = [f for f in data.get("favorites", []) if f != path]
            return self.save(data)
        return False

    def entry_count(self) -> int:
        return len(self.load()["entries"])
"""
FOXFall desktop backend.

A long-lived process that speaks newline-delimited JSON over stdio.
Electron spawns it hidden (CREATE_NO_WINDOW) and forwards events to the
renderer. One download ID per request; progress events carry real yt-dlp
hook data only.

Protocol (each line is one JSON object):
  -> {"id": <n>, "action": "...", "payload": {...}}
  <- {"id": <n>, "ok": true, "result": {...}}          response
  <- {"event": "download_progress", "download_id": "...", "progress": {...}}
  <- {"event": "metadata", "request_id": <n>, "info": {...}}
  <- {"event": "log", "level": "...", "message": "..."}
"""
from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from typing import Any, Callable, Dict, Optional

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
# Packaged desktop layout: resources/backend/server.py with core/, utils/ and
# foxfall_version.py placed alongside under resources/.
_RESOURCES = os.path.dirname(os.path.abspath(__file__))
for _path in (_RESOURCES, os.path.dirname(_RESOURCES)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core import history as history_mod          # noqa: E402
from core import settings as settings_mod        # noqa: E402
from core.download_manager import DownloadManager  # noqa: E402
from core.downloader import Downloader, ETA_UNKNOWN  # noqa: E402
from core.mediadb import MediaLibrary            # noqa: E402
from core.url_detector import detect_platform    # noqa: E402
from core.url_normalizer import normalize_full   # noqa: E402
from core.video_info import fetch_info, VideoInfo  # noqa: E402
from utils.ffmpeg import diagnostics_text, ffmpeg_dir  # noqa: E402
from utils.network import classify_error, run_full_diagnostics  # noqa: E402
from foxfall_version import APP_NAME, TAGLINE, __version__  # noqa: E402

import yt_dlp  # noqa: E402

_write_lock = threading.Lock()


def emit(obj: Dict[str, Any]) -> None:
    """Thread-safe stdout emit of one JSON object."""
    line = json.dumps(obj, ensure_ascii=False, default=str)
    with _write_lock:
        sys.stdout.write(line + "\n")
        sys.stdout.flush()


def _progress_payload(state) -> Dict[str, Any]:
    return {
        "status": state.status,
        "percentage": round(state.percent, 1),
        "downloaded_bytes": state.downloaded,
        "total_bytes": state.total,
        "speed": state.speed,
        "eta": state.eta,
        "eta_unknown": state.eta == ETA_UNKNOWN,
        "filepath": state.filepath,
        "filename": os.path.basename(state.filepath) if state.filepath else "",
        "fragments": state.fragments,
        "error": state.error,
    }


class BackendApp:
    def __init__(self) -> None:
        self.manager = DownloadManager()
        self.manager.on_change = self._broadcast_queue
        self._items_by_id: Dict[str, Any] = {}
        self._thumb_cache: Dict[str, str] = {}
        self._queue_evt = threading.Event()
        self._last_queue_signature = ""
        self._analysis_cache: Dict[str, "VideoInfo"] = {}
        self._analysis_ts: Dict[str, float] = {}
        self._user_data: str = os.environ.get("FOXFall_USER_DATA", '')
        self._tool_procs: Dict[str, subprocess.Popen] = {}
        self._tool_outputs: Dict[str, str] = {}

    # ------------------------------------------------------------- events
    def _broadcast_queue(self) -> None:
        items = []
        for item in self.manager.queue:
            dl_id = self._id_for(item)
            items.append({
                "download_id": dl_id,
                "title": item.info.title,
                "platform": item.platform_key,
                "quality": item.quality.label,
                "format": item.fmt,
                "progress": _progress_payload(item.state),
            })
        emit({"event": "queue_status", "items": items})

    def _id_for(self, item) -> str:
        for dl_id, candidate in self._items_by_id.items():
            if candidate is item:
                return dl_id
        dl_id = uuid.uuid4().hex[:12]
        self._items_by_id[dl_id] = item
        return dl_id

    def _poll_loop(self) -> None:
        """Background poller: starts queued items and pushes progress events."""
        while True:
            active = False
            # Sequential queue: launch the next pending item if idle.
            try:
                self.manager.start_next()
            except Exception as exc:  # noqa: BLE001
                emit({"event": "log", "level": "error",
                      "message": f"start_next failed: {exc}"})
            for item in list(self.manager.queue):
                if item.status in ("preparing", "downloading", "merging"):
                    active = True
                    emit({
                        "event": "download_progress",
                        "download_id": self._id_for(item),
                        "progress": _progress_payload(item.state),
                    })
                elif item.status in ("done", "error", "cancelled"):
                    self.manager.record_finished(item)
                    emit({
                        "event": "download_finished",
                        "download_id": self._id_for(item),
                        "progress": _progress_payload(item.state),
                    })
            snapshot = self.queue_snapshot()
            signature = json.dumps(snapshot, sort_keys=True, default=str)
            if signature != self._last_queue_signature:
                self._last_queue_signature = signature
                emit({"event": "queue_status", "items": snapshot})
            if not active:
                self._queue_evt.wait(timeout=0.5)
                self._queue_evt.clear()
            else:
                self._queue_evt.wait(timeout=0.25)
                self._queue_evt.clear()

    def queue_snapshot(self):
        items = []
        for item in self.manager.queue:
            items.append({
                "download_id": self._id_for(item),
                "title": item.info.title,
                "platform": item.platform_key,
                "quality": item.quality.label,
                "format": item.fmt,
                "progress": _progress_payload(item.state),
            })
        return items

    # ------------------------------------------------------------- actions
    def ping(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return {"pong": True, "version": __version__}

    def get_app_info(self, payload):
        return {
            "name": APP_NAME,
            "version": __version__,
            "tagline": TAGLINE,
            "yt_dlp": yt_dlp.version.__version__,
            "ffmpeg": diagnostics_text(),
            "python": sys.version.split()[0],
        }

    def get_settings(self, payload):
        return settings_mod.load()

    def set_settings(self, payload):
        allowed = {k: v for k, v in payload.items()
                   if k in settings_mod.DEFAULTS}
        ok = settings_mod.save({**settings_mod.load(), **allowed})
        return {"saved": ok}

    def analyze_url(self, payload):
        raw = str(payload.get("url", "")).strip()
        if not raw:
            return {"error": "empty url"}
        url = normalize_full(raw)
        platform = detect_platform(url)
        if not platform:
            return {"error": "Unsupported URL. FOXFall supports YouTube, "
                             "Instagram and TikTok links."}
        try:
            info = fetch_info(url, platform, timeout=30)
        except Exception as exc:  # noqa: BLE001
            category = classify_error(str(exc))
            return {"error": human_error(category, str(exc)),
                    "category": category}
        quality = [{
            "label": q.label, "kind": q.kind,
            "height": q.height, "format_selector": q.format_selector,
        } for q in info.qualities]
        formats = info.formats or ["mp4"]
        # cache for the following start_download call (10 min TTL)
        import time as _time
        self._analysis_cache[url] = info
        self._analysis_ts[url] = _time.time()
        return {
            "url": url,
            "title": info.title,
            "platform": platform.key,
            "platform_name": platform.name,
            "uploader": info.uploader,
            "duration": info.duration,
            "duration_text": info.duration_text,
            "views": info.view_count,
            "thumbnail": info.thumbnail,
            "qualities": quality,
            "formats": formats,
            "live": info.live,
        }

    def start_download(self, payload):
        raw = str(payload.get("url", "")).strip()
        quality_label = str(payload.get("quality", "best"))
        fmt = str(payload.get("format", "mp4")).lower()
        url = normalize_full(raw)
        platform = detect_platform(url)
        if not platform:
            return {"error": "unsupported url"}
        # Reuse the metadata produced by the preceding analyze_url call.
        # Re-fetching seconds later triggers platform throttling and can
        # return an empty format list ("Requested format is not available").
        import time as _time
        info = self._analysis_cache.get(url)
        if info is not None and _time.time() - self._analysis_ts.get(url, 0) > 600:
            info = None
        if info is None:
            try:
                info = fetch_info(url, platform, timeout=30)
            except Exception as exc:  # noqa: BLE001
                category = classify_error(str(exc))
                return {"error": human_error(category, str(exc)),
                        "category": category}
        if not info.qualities:
            return {"error": "No downloadable formats were returned for this video. "
                             "It may be restricted or region-locked."}

        quality = next((q for q in info.qualities if q.label == quality_label),
                       info.qualities[0])
        if fmt == "mp3":
            quality = next((q for q in info.qualities if q.kind == "audio"),
                           quality)
        dest = settings_mod.resolve_download_dir()
        item = self.manager.enqueue(info, quality, fmt, dest)
        from core.downloader import Downloader
        item.downloader = Downloader(item.info.url, item.quality, item.fmt,
                                     item.output_dir, ffmpeg_dir=ffmpeg_dir())
        try:
            emit({"event": "log", "level": "debug",
                  "message": f"dl opts format={item.downloader._ydl_opts().get('format')} "
                             f"ffmpeg={item.downloader.ffmpeg_dir}"})
        except Exception as _e:  # noqa: BLE001
            emit({"event": "log", "level": "debug", "message": f"precheck: {_e}"})
        dl_id = self._id_for(item)
        self._queue_evt.set()
        self._broadcast_queue()
        return {
            "download_id": dl_id,
            "title": info.title,
            "platform": platform.key,
            "quality": quality.label,
            "format": fmt,
        }

    def cancel_download(self, payload):
        dl_id = str(payload.get("download_id", ""))
        item = self._items_by_id.get(dl_id)
        if not item:
            return {"error": "unknown download id"}
        self.manager.cancel(item)
        self._queue_evt.set()
        return {"cancelling": True}

    def retry_download(self, payload):
        dl_id = str(payload.get("download_id", ""))
        item = self._items_by_id.get(dl_id)
        if not item:
            return {"error": "unknown download id"}
        self.manager.retry(item, settings_mod.resolve_download_dir())
        from core.downloader import Downloader
        item.downloader = Downloader(item.info.url, item.quality, item.fmt,
                                     item.output_dir, ffmpeg_dir=ffmpeg_dir())
        self._queue_evt.set()
        return {"restarted": True}

    def list_queue(self, payload):
        return {"items": self.queue_snapshot()}

    def list_history(self, payload):
        items = history_mod.list_items(limit=int(payload.get("limit") or 100))
        return {"items": items}

    def clear_history(self, payload):
        removed = history_mod.clear()
        return {"removed": removed}

    def remove_history(self, payload):
        try:
            entry_id = int(payload.get("id"))
        except (TypeError, ValueError):
            return {"error": "invalid id"}
        return {"removed": history_mod.remove(entry_id)}

    def run_diagnostics(self, payload):
        report = run_full_diagnostics()
        return {"checks": [
            {"name": r.name, "ok": r.ok, "detail": r.detail,
             "elapsed_ms": r.elapsed_ms}
            for r in report.results
        ], "all_ok": report.all_ok}

    def check_backend_updates(self, payload):
        return {
            "yt_dlp": yt_dlp.version.__version__,
            "app": __version__,
            "ffmpeg": diagnostics_text(),
        }

    # ------------------------------------------------------------- library
    def _library(self) -> MediaLibrary:
        return MediaLibrary(user_data=self._user_data,
                            ffmpeg_dir=ffmpeg_dir() or "")

    def library_scan(self, payload):
        """Incremental background scan; emits library_progress events."""
        lib = self._library()

        def progress(scanned, total, path):
            emit({"event": "library_progress", "scanned": scanned,
                  "total": total, "path": path})

        def on_entry(entry):
            emit({"event": "library_entry", "entry": entry})

        def worker():
            try:
                result = lib.scan(extra_dirs=payload.get("extra_dirs"),
                                  progress=progress, on_entry=on_entry)
                emit({"event": "library_scan_done", "result": result})
            except Exception as exc:  # noqa: BLE001
                emit({"event": "library_scan_done",
                      "result": {"error": str(exc)}})

        threading.Thread(target=worker, daemon=True,
                         name="foxfall-library-scan").start()
        return {"started": True}

    def library_cancel_scan(self, payload):
        self._library().cancel_scan()
        return {"cancelling": True}

    def library_list(self, payload):
        lib = self._library()
        entries = lib.list_entries(
            query=str(payload.get("query", "")),
            sort=str(payload.get("sort", "date")),
            include_missing=bool(payload.get("include_missing")))
        return {"items": entries,
                "count": len(entries),
                "last_scan": lib.load().get("last_scan")}

    def library_set_favorite(self, payload):
        return {"updated": self._library().set_favorite(
            str(payload.get("path", "")), bool(payload.get("favorite")))}

    def library_remove(self, payload):
        return {"removed": self._library().remove_entry(
            str(payload.get("path", "")))}

    def library_count(self, payload):
        return {"count": self._library().entry_count()}

    # ------------------------------------------------------------- tools
    def _tool_ffmpeg(self) -> Optional[str]:
        fdir = ffmpeg_dir()
        if not fdir:
            return None
        exe = os.path.join(fdir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        return exe if os.path.isfile(exe) else None

    def tool_convert_start(self, payload):
        exe = self._tool_ffmpeg()
        if not exe:
            return {"error": "FFmpeg not available."}
        src = str(payload.get("input", ""))
        out = str(payload.get("output", ""))
        vcodec = str(payload.get("vcodec", "libx264"))
        if not os.path.isfile(src):
            return {"error": "input file not found"}
        if not out:
            return {"error": "output path required"}
        if os.path.abspath(src) == os.path.abspath(out):
            return {"error": "output must differ from input"}
        op_id = uuid.uuid4().hex[:12]
        self._run_tool(op_id, [exe, "-y", "-i", src,
                               "-c:v", vcodec, "-c:a", "aac", out],
                       out, "Converting")
        return {"operation_id": op_id}

    def tool_extract_start(self, payload):
        exe = self._tool_ffmpeg()
        if not exe:
            return {"error": "FFmpeg not available."}
        src = str(payload.get("input", ""))
        out = str(payload.get("output", ""))
        fmt = str(payload.get("format", "mp3")).lower()
        codecs = {"mp3": "libmp3lame", "aac": "aac", "flac": "flac",
                  "wav": "pcm_s16le", "ogg": "libvorbis"}
        if fmt not in codecs:
            return {"error": f"unsupported audio format: {fmt}"}
        if not os.path.isfile(src):
            return {"error": "input file not found"}
        if not out:
            return {"error": "output path required"}
        op_id = uuid.uuid4().hex[:12]
        self._run_tool(op_id, [exe, "-y", "-i", src, "-vn",
                               "-c:a", codecs[fmt], out],
                       out, "Extracting audio")
        return {"operation_id": op_id}

    def tool_thumbnail(self, payload):
        exe = self._tool_ffmpeg()
        if not exe:
            return {"error": "FFmpeg not available."}
        src = str(payload.get("input", ""))
        out = str(payload.get("output", ""))
        ts = payload.get("timestamp", 1)
        try:
            ts = max(0.0, min(float(ts), 36000.0))
        except (TypeError, ValueError):
            return {"error": "invalid timestamp"}
        if not os.path.isfile(src):
            return {"error": "input file not found"}
        if not out:
            return {"error": "output path required"}
        try:
            subprocess.run([exe, "-v", "quiet", "-ss", str(ts), "-i", src,
                            "-frames:v", "1", "-y", out],
                           capture_output=True, timeout=60)
        except (subprocess.TimeoutExpired, OSError) as exc:
            return {"error": f"ffmpeg failed: {exc}"}
        if not os.path.isfile(out) or os.path.getsize(out) == 0:
            return {"error": "thumbnail was not generated (invalid file or timestamp?)"}
        return {"output": out, "size": os.path.getsize(out)}

    def tool_cancel(self, payload):
        op_id = str(payload.get("operation_id", ""))
        proc = self._tool_procs.get(op_id)
        if proc and proc.poll() is None:
            proc.kill()
            # remove the partial output, never the input
            out = self._tool_outputs.get(op_id, "")
            if out and os.path.isfile(out):
                try:
                    os.remove(out)
                except OSError:
                    pass
            return {"cancelled": True}
        return {"error": "unknown or already finished operation"}

    def _run_tool(self, op_id: str, args: List[str], output: str, label: str):
        """
        Run an FFmpeg tool operation.

        Fixes applied:
          * stderr is drained in a thread — a full pipe buffer previously
            blocked ffmpeg forever on long conversions.
          * `-progress pipe:1 -nostats` added so real progress data flows on
            stdout, which the monitor parses into tool_progress events.
        """
        if "-progress" not in args and args[0].lower().find("ffmpeg") != -1:
            args = args[:1] + ["-progress", "pipe:1", "-nostats"] + args[1:]
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)
        self._tool_procs[op_id] = proc
        self._tool_outputs[op_id] = output

        # drain stderr so a full pipe can never deadlock ffmpeg
        def drain_stderr():
            for _ in proc.stderr:
                pass

        threading.Thread(target=drain_stderr, daemon=True,
                         name=f"foxfall-stderr-{op_id}").start()

        def monitor():
            total = None
            for line in proc.stdout:
                line = line.strip()
                m = re.search(r"Duration: (\d+):(\d+):(\d+\.\d+)", line)
                if m:
                    total = (int(m.group(1)) * 3600 + int(m.group(2)) * 60
                             + float(m.group(3)))
                if line.startswith("out_time_ms=") and total:
                    try:
                        done = int(line.split("=", 1)[1]) / 1_000_000
                        emit({"event": "tool_progress", "operation_id": op_id,
                              "percentage": min(100.0, done / total * 100),
                              "label": label})
                    except (ValueError, ZeroDivisionError):
                        pass
            code = proc.wait()
            ok = code == 0 and os.path.isfile(output) and \
                os.path.getsize(output) > 0
            if not ok and os.path.isfile(output) and os.path.getsize(output) == 0:
                try:
                    os.remove(output)
                except OSError:
                    pass
            emit({"event": "tool_finished", "operation_id": op_id,
                  "ok": ok, "output": output if ok else "",
                  "error": "" if ok else f"{label} failed (ffmpeg exit {code})"})

        threading.Thread(target=monitor, daemon=True,
                         name=f"foxfall-tool-{op_id}").start()

    def tool_probe(self, payload):
        """Inspect a local media file with FFprobe (real implementation)."""
        from utils.ffmpeg import ffmpeg_dir
        import subprocess
        path = str(payload.get("path", "")).strip()
        if not path or not os.path.isfile(path):
            return {"error": "file not found"}
        fdir = ffmpeg_dir()
        if not fdir:
            return {"error": "FFprobe requires FFmpeg, which was not found."}
        exe = os.path.join(fdir, "ffprobe.exe" if os.name == "nt" else "ffprobe")
        if not os.path.isfile(exe):
            return {"error": "ffprobe not found in the FFmpeg directory."}
        try:
            out = subprocess.run(
                [exe, "-v", "quiet", "-print_format", "json",
                 "-show_format", "-show_streams", path],
                capture_output=True, text=True, timeout=30)
            data = json.loads(out.stdout or "{}")
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError) as exc:
            return {"error": f"ffprobe failed: {exc}"}

        fmt = data.get("format", {})
        streams = data.get("streams", [])
        video = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
        dur = float(fmt.get("duration") or 0)
        m, s = divmod(int(dur), 60)
        h, m2 = divmod(m, 60)
        size = int(fmt.get("size") or 0)
        size_mb = size / (1024 * 1024)
        return {
            "container": fmt.get("format_name", ""),
            "duration_text": (f"{h}:{m2:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}") if dur else "",
            "resolution": (f"{video.get('width')}x{video.get('height')}" if video else ""),
            "vcodec": (video.get("codec_name") if video else ""),
            "acodec": (audio.get("codec_name") if audio else ""),
            "bitrate": (f"{int(fmt.get('bit_rate') or 0) // 1000} kbps"
                        if fmt.get("bit_rate") else ""),
            "size_text": f"{size_mb:.1f} MB" if size else "",
            "streams": len(streams),
        }


def human_error(category: str, raw: str) -> str:
    from utils.network import humanize_error
    return humanize_error(raw)


def pick_directory(payload):
    # Not available over stdio: handled by Electron dialog. Kept for protocol
    # completeness.
    return {"error": "handled by Electron"}


HANDLERS: Dict[str, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    "ping": lambda p: {"pong": True, "version": __version__},
    "get_app_info": BackendApp().get_app_info,
}


def main() -> None:
    app = BackendApp()
    threading.Thread(target=app._poll_loop, daemon=True,
                     name="foxfall-poller").start()

    emit({"event": "ready", "version": __version__,
          "app": APP_NAME, "ffmpeg_ok": bool(ffmpeg_dir())})

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        request_id = None
        try:
            request = json.loads(raw_line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            request_id = request.get("id")
            action = str(request.get("action", ""))
            payload = request.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}

            handler = getattr(app, f"api_{action}", None) or \
                HANDLERS.get(action)
            if handler is None:
                method = getattr(app, action.replace("-", "_"), None)
                if callable(method) and not action.startswith("_"):
                    handler = method
            if handler is None:
                raise ValueError(f"unknown action: {action}")

            result = handler(payload)
            if request_id is not None:
                emit({"id": request_id, "ok": True, "result": result})
        except Exception as exc:  # noqa: BLE001 - report per-request errors
            if request_id is not None:
                emit({"id": request_id, "ok": False,
                      "error": str(exc)[:400]})
            else:
                emit({"event": "log", "level": "error",
                      "message": str(exc)[:400]})


if __name__ == "__main__":
    main()
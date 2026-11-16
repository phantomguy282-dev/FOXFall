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
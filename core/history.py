"""
history.py
Download history persistence (JSON, bounded, deduped by URL+quality).
"""

from __future__ import annotations

import copy
import json
import os
import threading
import time
from typing import Any, Dict, List, Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(_PROJECT_ROOT, "config")
HISTORY_PATH = os.path.join(HISTORY_DIR, "history.json")

_lock = threading.Lock()


def _history_path() -> str:
    """Packaged desktop app keeps history in per-user app data."""
    try:
        from core.settings import _paths
        _config_dir, _config_path = _paths()
        return os.path.join(os.path.dirname(_config_path), "history.json")
    except Exception:  # noqa: BLE001 - fallback to legacy location
        return HISTORY_PATH


def _empty() -> Dict[str, Any]:
    return {"items": [], "next_id": 1}


def _load() -> Dict[str, Any]:
    try:
        with open(_history_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict) and isinstance(data.get("items"), list):
            data.setdefault("next_id", 1)
            return data
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError):
        pass
    return _empty()


def _save(data: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(_history_path()), exist_ok=True)
        tmp = _history_path() + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, _history_path())
    except OSError:
        pass


def add(url: str, platform: str, title: str, quality: str, fmt: str,
        filepath: str, filesize: int = 0, status: str = "completed",
        error: str = "") -> int:
    """
    Append one history entry (status: completed | failed | cancelled).
    Returns the entry id.
    """
    with _lock:
        data = _load()
        entry = {
            "id": data.get("next_id", 1),
            "url": url,
            "platform": platform,
            "title": title,
            "quality": quality,
            "format": fmt,
            "filepath": filepath,
            "filesize": int(filesize or 0),
            "status": status,
            "error": error[:200],
            "timestamp": time.time(),
        }
        data["next_id"] = int(data.get("next_id", 1)) + 1
        data["items"].insert(0, entry)
        _save(data)
        return entry["id"]


def trim(limit: int) -> int:
    """Keep only the newest *limit* entries. Returns removed count."""
    with _lock:
        data = _load()
        items = data.get("items", [])
        removed = max(0, len(items) - max(1, limit))
        if removed:
            data["items"] = items[:limit]
            _save(data)
        return removed


def list_items(limit: Optional[int] = None,
               status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return history entries, newest first."""
    data = _load()
    items = data.get("items", [])
    if status:
        items = [i for i in items if i.get("status") == status]
    if limit:
        items = items[:limit]
    return copy.deepcopy(items)


def find_duplicates(url: str) -> List[Dict[str, Any]]:
    """Completed entries for the same URL (duplicate-download detection)."""
    url = (url or "").strip().rstrip("/").lower()
    if not url:
        return []
    return [i for i in list_items(status="completed")
            if str(i.get("url", "")).strip().rstrip("/").lower() == url]


def clear() -> int:
    """Erase all history. Returns prior entry count."""
    with _lock:
        data = _load()
        count = len(data.get("items", []))
        _save(_empty())
        return count


def remove(entry_id: int) -> bool:
    with _lock:
        data = _load()
        before = len(data["items"])
        data["items"] = [i for i in data["items"] if i.get("id") != entry_id]
        changed = len(data["items"]) != before
        if changed:
            _save(data)
        return changed

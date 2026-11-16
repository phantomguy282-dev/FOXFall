"""
settings.py
Persistent JSON settings with defaults + validation.
"""

from __future__ import annotations

import copy
import json
import os
import threading
from typing import Any, Dict

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(_PROJECT_ROOT, "config")
CONFIG_PATH = os.path.join(CONFIG_DIR, "settings.json")

DEFAULTS: Dict[str, Any] = {
    "download_dir": "",                  # empty = <project>/downloads
    "preferred_format": "mp4",           # mp4 | webm | mp3
    "default_quality": "best",           # best | 2160 | 1440 | 1080 | 720 | 480 | 360 | mp3
    "startup_animation": True,
    "sound_effects": False,
    "check_updates": True,
    "show_notifications": True,
    "theme": "fox",                      # theme key from ui/themes.py
    "max_concurrent_downloads": 1,
    "history_limit": 500,
}

_VALID = {
    "preferred_format": {"mp4", "webm", "mp3"},
    "default_quality": {"best", "2160", "1440", "1080", "720", "480", "360", "mp3"},
    "theme": {"fox", "original", "dark"},
}

_lock = threading.Lock()


def _coerce(key: str, value: Any) -> Any:
    """Return a sanitized value for *key*, or None when invalid."""
    if key not in DEFAULTS:
        return None
    default = DEFAULTS[key]
    try:
        if isinstance(default, bool):
            return bool(value)
        if isinstance(default, int):
            v = int(value)
            if key == "max_concurrent_downloads":
                v = max(1, min(4, v))
            if key == "history_limit":
                v = max(10, min(5000, v))
            return v
        if isinstance(default, str):
            v = str(value)
            if key in _VALID and v not in _VALID[key]:
                return None
            if key == "download_dir":
                v = v.strip()
            return v
    except (TypeError, ValueError):
        return None
    return None


def load() -> Dict[str, Any]:
    """Load settings from disk, merging over defaults. Never raises."""
    data = copy.deepcopy(DEFAULTS)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            stored = json.load(fh)
        if isinstance(stored, dict):
            for key, value in stored.items():
                clean = _coerce(key, value)
                if clean is not None or (key == "download_dir" and isinstance(value, str)):
                    data[key] = clean if clean is not None else ""
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError):
        pass
    return data


def save(settings: Dict[str, Any]) -> bool:
    """Persist settings atomically. Returns True on success.
    Fails when any invalid value is supplied (strict validation)."""
    clean: Dict[str, Any] = {}
    for key, value in settings.items():
        if key == "download_dir":
            clean[key] = str(value or "").strip()
            continue
        if key not in DEFAULTS:
            return False
        result = _coerce(key, value)
        if result is None:
            return False
        clean[key] = result
    with _lock:
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            tmp = CONFIG_PATH + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(clean, fh, indent=4)
                fh.write("\n")
            os.replace(tmp, CONFIG_PATH)
            return True
        except OSError:
            return False


def get(key: str, default: Any = None) -> Any:
    settings = load()
    return settings.get(key, DEFAULTS.get(key, default))


def set_key(key: str, value: Any) -> bool:
    settings = load()
    settings[key] = value
    return save(settings)


def resolve_download_dir(settings: Dict[str, Any] | None = None) -> str:
    """Absolute download directory (creates it when missing)."""
    s = settings or load()
    directory = s.get("download_dir") or ""
    if not directory:
        directory = os.path.join(_PROJECT_ROOT, "downloads")
    directory = os.path.abspath(directory)
    try:
        os.makedirs(directory, exist_ok=True)
    except OSError:
        directory = os.path.join(_PROJECT_ROOT, "downloads")
        os.makedirs(directory, exist_ok=True)
    return directory

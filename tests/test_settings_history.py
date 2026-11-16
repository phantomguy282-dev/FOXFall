"""
tests/test_settings_history.py
Persistence, defaults, validation, history lifecycle.
"""

import json

import pytest

from core import settings as settings_mod
from core import history as history_mod


# ---------------------------------------------------------------- settings
def test_defaults_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", str(tmp_path / "settings.json"))
    s = settings_mod.load()
    assert s["preferred_format"] == "mp4"
    assert s["theme"] == "fox"
    assert s["startup_animation"] is True


def test_save_and_reload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", str(tmp_path / "settings.json"))
    data = settings_mod.load()
    data["preferred_format"] = "webm"
    data["download_dir"] = str(tmp_path / "dl")
    assert settings_mod.save(data)
    s = settings_mod.load()
    assert s["preferred_format"] == "webm"
    assert s["download_dir"] == str(tmp_path / "dl")


def test_invalid_values_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", str(tmp_path / "settings.json"))
    assert not settings_mod.save({"preferred_format": "avi"})
    assert not settings_mod.save({"default_quality": "9999p"})
    assert settings_mod.load()["preferred_format"] == "mp4"


def test_corrupt_file_falls_back_to_defaults(tmp_path, monkeypatch):
    cfg = tmp_path / "settings.json"
    cfg.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", str(cfg))
    s = settings_mod.load()
    assert s["theme"] == "fox"


def test_resolve_download_dir_creates_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", str(tmp_path / "settings.json"))
    target = tmp_path / "mydownloads"
    s = {"download_dir": str(target)}
    out = settings_mod.resolve_download_dir(s)
    assert target.is_dir()
    assert out == str(target)


def test_resolve_download_dir_fallback_default(tmp_path, monkeypatch):
    monkeypatch.setattr(settings_mod, "CONFIG_PATH", str(tmp_path / "settings.json"))
    s = {"download_dir": ""}
    out = settings_mod.resolve_download_dir(s)
    assert out.endswith("downloads")


# ---------------------------------------------------------------- history
@pytest.fixture()
def hist_path(tmp_path, monkeypatch):
    p = tmp_path / "history.json"
    monkeypatch.setattr(history_mod, "HISTORY_PATH", str(p))
    return p


def test_history_add_and_list(hist_path):
    history_mod.add("https://youtu.be/1", "youtube", "Video One", "1080p", "mp4",
                    "/dl/a.mp4", 1234, "completed")
    history_mod.add("https://youtu.be/2", "tiktok", "Video Two", "best", "mp3",
                    "", 0, "failed", error="rate limited")
    items = history_mod.list_items()
    assert len(items) == 2
    assert items[0]["title"] == "Video Two"        # newest first
    assert items[0]["status"] == "failed"


def test_history_status_filter(hist_path):
    history_mod.add("u1", "youtube", "A", "best", "mp4", "f", 0, "completed")
    history_mod.add("u2", "youtube", "B", "best", "mp4", "", 0, "failed")
    assert all(i["status"] == "completed" for i in history_mod.list_items(status="completed"))


def test_history_duplicates(hist_path):
    url = "https://youtu.be/dup"
    history_mod.add(url, "youtube", "A", "1080p", "mp4", "f1", 10, "completed")
    history_mod.add(url.upper() + "/", "youtube", "A2", "720p", "mp4", "f2", 10, "completed")
    assert len(history_mod.find_duplicates(url)) == 2


def test_history_clear(hist_path):
    for n in range(3):
        history_mod.add(f"u{n}", "youtube", "t", "best", "mp4", "", 0, "completed")
    assert history_mod.clear() == 3
    assert history_mod.list_items() == []


def test_history_trim(hist_path):
    for n in range(10):
        history_mod.add(f"u{n}", "youtube", "t", "best", "mp4", "", 0, "completed")
    removed = history_mod.trim(5)
    assert removed == 5
    assert len(history_mod.list_items()) == 5

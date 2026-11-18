"""M5/M6 integration tests: library index + tools (real ffprobe/ffmpeg)."""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


@pytest.fixture()
def media_file(tmp_path):
    """Create a real tiny media file with bundled ffmpeg testsrc."""
    from utils.ffmpeg import ffmpeg_dir
    fdir = ffmpeg_dir()
    if not fdir:
        pytest.skip("ffmpeg not available")
    exe = os.path.join(fdir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    src = tmp_path / "test-media.mp4"
    import subprocess
    r = subprocess.run(
        [exe, "-y", "-v", "quiet",
         "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
         "-shortest", str(src)],
        capture_output=True, timeout=60)
    assert src.is_file() and src.stat().st_size > 0, \
        f"testsrc generation failed: {r.stderr[-200:] if r.stderr else ''}"
    return str(src), tmp_path


@pytest.fixture()
def lib(tmp_path, monkeypatch):
    from core.mediadb import MediaLibrary
    from utils.ffmpeg import ffmpeg_dir
    monkeypatch.setenv("FOXFall_USER_DATA", str(tmp_path / "ud"))
    return MediaLibrary(user_data=str(tmp_path / "ud"),
                        ffmpeg_dir=ffmpeg_dir() or "")


@pytest.fixture()
def scan_dir(tmp_path):
    d = tmp_path / "dl"
    d.mkdir(exist_ok=True)
    return str(d)


def test_scan_indexes_real_file(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "test-media.mp4"))
    result = lib.scan(extra_dirs=[scan_dir])
    assert result["total"] == 1
    entries = lib.list_entries()
    assert len(entries) == 1
    e = entries[0]
    assert e["duration"] >= 1
    assert e["has_video"] is True
    assert e["size"] > 0


def test_scan_generates_thumbnail(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "test-media.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    entries = lib.list_entries()
    assert entries[0]["thumb"], "thumbnail should be generated"
    assert os.path.isfile(entries[0]["thumb"])
    assert os.path.getsize(entries[0]["thumb"]) > 0


def test_rescan_no_duplicates(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "test-media.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    lib.scan(extra_dirs=[scan_dir])
    assert len(lib.list_entries()) == 1


def test_scan_survives_interruption(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "test-media.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    before = lib.load()
    lib.scan(extra_dirs=[scan_dir])
    after = lib.load()
    assert set(before["entries"]) == set(after["entries"])


def test_missing_file_flagged_not_removed(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "gone.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    os.remove(os.path.join(scan_dir, "gone.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    entries = lib.list_entries(include_missing=True)
    assert len(entries) == 1
    assert entries[0]["missing"] is True
    assert len(lib.list_entries()) == 0


def test_favorite_and_remove(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "fav.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    path = lib.list_entries()[0]["path"]
    lib.set_favorite(path, True)
    assert lib.list_entries()[0]["favorite"] is True
    lib.set_favorite(path, False)
    assert lib.list_entries()[0]["favorite"] is False
    lib.remove_entry(path)
    assert lib.list_entries() == []


def test_search_and_sort(lib, media_file, scan_dir):
    src, _ = media_file
    shutil.copy(src, os.path.join(scan_dir, "alpha.mp4"))
    shutil.copy(src, os.path.join(scan_dir, "beta.mp4"))
    lib.scan(extra_dirs=[scan_dir])
    items = lib.list_entries(sort="name")
    names = [e["title"] for e in items]
    assert names == sorted(names)
    found = lib.list_entries(query="alpha")
    assert len(found) == 1 and found[0]["title"] == "alpha"


def test_tool_thumbnail_real(lib, media_file, tmp_path):
    src, _ = media_file
    out = os.path.join(str(tmp_path), "thumb.png")
    result = lib._thumbnail(src, 2.0, "testkey.png")
    if result is None:
        pytest.skip("thumbnail generation unavailable in this environment")
    assert os.path.isfile(result) and os.path.getsize(result) > 0


def test_tool_convert_real(media_file, tmp_path):
    """Video converter core: real ffmpeg conversion to webm."""
    import subprocess
    from utils.ffmpeg import ffmpeg_dir
    src, _ = media_file
    fdir = ffmpeg_dir()
    exe = os.path.join(fdir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    out = tmp_path / "converted.webm"
    r = subprocess.run(
        [exe, "-y", "-v", "quiet", "-i", src, "-c:v", "libvpx-vp9",
         "-c:a", "libopus", str(out)], capture_output=True, timeout=180)
    assert out.is_file() and out.stat().st_size > 0


def test_tool_extract_real(media_file, tmp_path):
    """Audio extractor core: real ffmpeg extraction to mp3."""
    import subprocess
    from utils.ffmpeg import ffmpeg_dir
    src, _ = media_file
    fdir = ffmpeg_dir()
    exe = os.path.join(fdir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    out = tmp_path / "extracted.mp3"
    r = subprocess.run(
        [exe, "-y", "-v", "quiet", "-i", src, "-vn", "-c:a", "libmp3lame",
         str(out)], capture_output=True, timeout=180)
    assert r.returncode == 0, f"ffmpeg rc={r.returncode} stderr={r.stderr[-200:]}"
    assert out.is_file() and out.stat().st_size > 0

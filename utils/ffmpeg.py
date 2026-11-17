"""
ffmpeg.py
Locate / verify / report the bundled FFmpeg. Dedicated utility per project rules.

Layout:  foxfall/bin/ffmpeg/ffmpeg.exe + ffprobe.exe (portable, bundled)
Order:   project bin/ffmpeg -> project bin -> PATH -> common install dirs.
An executable is only accepted if it actually RUNS (-version succeeds).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUNDLED_DIR = os.path.join(_PROJECT_ROOT, "bin", "ffmpeg")  # recommended layout
ALT_BUNDLED_DIR = os.path.join(_PROJECT_ROOT, "bin")        # legacy layout


def _frozen_bundled_dir() -> Optional[str]:
    """
    Locate FFmpeg in frozen/packaged layouts:
      - Electron + PyInstaller backend exe at
        <resources>/backend/foxfall-backend/foxfall-backend.exe
        -> FFmpeg at <resources>/bin/ffmpeg
      - PyInstaller onedir generic: exe_dir/ffmpeg
      - Electron python-runtime layout: <resources>/bin/ffmpeg via exe 3 up
      - PyInstaller onefile: sys._MEIPASS/ffmpeg
    """
    if not getattr(sys, "frozen", False):
        return None
    exe_dir = os.path.dirname(os.path.abspath(sys.executable))
    base = getattr(sys, "_MEIPASS", None)

    candidates = [
        os.path.join(exe_dir, "..", "..", "..", "bin", "ffmpeg"),  # backend exe
        os.path.join(exe_dir, "..", "..", "bin", "ffmpeg"),
        os.path.join(exe_dir, "bin", "ffmpeg"),
        os.path.join(exe_dir, "ffmpeg"),
        os.path.join(exe_dir, "_internal", "ffmpeg"),
    ]
    if base:
        candidates.append(os.path.join(base, "ffmpeg"))
    for c in candidates:
        c2 = os.path.normpath(c)
        if os.path.isfile(os.path.join(c2, _exe("ffmpeg"))):
            return c2
    return None


def _exe(name: str) -> str:
    return name + (".exe" if os.name == "nt" else "")


def _runs(exe_path: str) -> bool:
    """True when the executable actually executes (-version)."""
    try:
        out = subprocess.run([exe_path, "-version"], capture_output=True,
                             text=True, timeout=10)
        return out.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ffmpeg_dir() -> Optional[str]:
    """
    Directory containing a *working* ffmpeg.exe (and preferably ffprobe.exe).
    Order: bin/ffmpeg -> bin -> PATH -> common Windows locations.
    """
    candidates = [BUNDLED_DIR, ALT_BUNDLED_DIR]
    frozen = _frozen_bundled_dir()
    if frozen:
        candidates.insert(0, frozen)
    for directory in candidates:
        exe = os.path.join(directory, _exe("ffmpeg"))
        if os.path.isfile(exe) and _runs(exe):
            return directory

    found = shutil.which("ffmpeg")
    if found and _runs(found):
        return os.path.dirname(os.path.abspath(found))

    common = [
        r"C:\ffmpeg\bin",
        r"C:\ffmpeg\ffmpeg\bin",
        r"C:\Program Files\ffmpeg\bin",
        r"C:\Program Files (x86)\ffmpeg\bin",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "ffmpeg", "bin"),
    ]
    for c in common:
        if c and os.path.isfile(os.path.join(c, _exe("ffmpeg"))) and _runs(os.path.join(c, _exe("ffmpeg"))):
            return c
    return None


# backward-compatible aliases used by older modules
find_ffmpeg_dir = ffmpeg_dir
has_ffmpeg = lambda: ffmpeg_dir() is not None  # noqa: E731


def ffmpeg_exe() -> Optional[str]:
    directory = ffmpeg_dir()
    return os.path.join(directory, _exe("ffmpeg")) if directory else None


def ffprobe_exe() -> Optional[str]:
    directory = ffmpeg_dir()
    if not directory:
        return None
    probe = os.path.join(directory, _exe("ffprobe"))
    return probe if os.path.isfile(probe) else None


def ffmpeg_version() -> str:
    """'x.y' style version string or '' when unavailable."""
    exe = ffmpeg_exe()
    if not exe:
        return ""
    try:
        out = subprocess.run([exe, "-version"], capture_output=True,
                             text=True, timeout=10)
        first = (out.stdout or "").splitlines()
        if first:
            parts = first[0].split()
            if len(parts) >= 3:
                return parts[2].split("-")[0]
    except (OSError, subprocess.TimeoutExpired):
        pass
    return ""


def diagnostics_text() -> str:
    """One-line diagnostic summary used by the diagnostics screen."""
    directory = ffmpeg_dir()
    if not directory:
        return ("FFmpeg: NOT FOUND - run repair (downloads portable build "
                "into bin\\ffmpeg) or place ffmpeg.exe there manually.")
    probe = "yes" if ffprobe_exe() else "no"
    return f"FFmpeg: v{ffmpeg_version()} at {directory} (ffprobe: {probe})"


def repair_available() -> bool:
    """True when automatic repair (download) is possible on this platform."""
    return os.name == "nt"


def repair_ffmpeg(log=print) -> bool:
    """
    Attempt automatic repair: download the official gyan.dev essentials
    build and extract ffmpeg.exe/ffprobe.exe into bin/ffmpeg.
    Returns True on success. Uses only the official distribution.
    """
    if not repair_available():
        log("[x] Automatic repair is only supported on Windows.")
        return False
    try:
        import io
        import zipfile
        from urllib.request import Request, urlopen

        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        log("[*] Downloading official FFmpeg build (gyan.dev)...")
        request = Request(url, headers={"User-Agent": "foxfall/1.0"})
        with urlopen(request, timeout=180) as response:
            payload = response.read()
        log(f"[OK] Downloaded {len(payload) / 1e6:.1f} MB. Extracting...")
        os.makedirs(BUNDLED_DIR, exist_ok=True)
        wanted = {"ffmpeg.exe", "ffprobe.exe"}
        with zipfile.ZipFile(io.BytesIO(payload)) as zf:
            for name in zf.namelist():
                base = os.path.basename(name)
                if base.lower() in wanted:
                    data = zf.read(name)
                    with open(os.path.join(BUNDLED_DIR, base), "wb") as fh:
                        fh.write(data)
        exe = ffmpeg_exe()
        if exe and _runs(exe):
            log(f"[OK] FFmpeg {ffmpeg_version()} installed at {BUNDLED_DIR}")
            return True
        log("[x] Extraction finished but the executable did not run.")
        return False
    except Exception as exc:  # noqa: BLE001
        log(f"[x] FFmpeg repair failed: {exc}")
        return False

"""
FOXFall - main entry point.
Launch: python main.py  (or double-click run.bat / FOXFall.exe)
"""

from __future__ import annotations

import os
import sys


def _force_utf8_streams() -> None:
    """
    The default Windows console code page (cp1252/cp437) cannot encode the
    box-drawing characters used by the UI. Python 3.7+ supports switching the
    console to UTF-8 via code page 65001; reconfigure the text streams too so
    a packaged FOXFall.exe behaves exactly like a source run.
    """
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except Exception:  # noqa: BLE001 - best effort only
            pass
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def _ensure_tty_or_exit() -> None:
    """A double-clicked exe with no console attached would fail obscurely."""
    if os.name == "nt" and sys.stdout is None:
        raise SystemExit(1)


_ensure_tty_or_exit()
_force_utf8_streams()

# Ensure project root is importable regardless of working directory
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ui.interface import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
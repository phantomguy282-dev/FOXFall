"""
FOXFall - main entry point.
Launch: python main.py  (or double-click run.bat)
"""

from __future__ import annotations

import os
import sys

# Ensure project root is importable regardless of working directory
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from ui.interface import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())

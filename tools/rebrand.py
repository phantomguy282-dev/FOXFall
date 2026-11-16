"""FOXFall rebranding script: replaces FOXFall branding with FOXFall.

Applied once during the migration; kept in tools/ for reference.
"""
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEXT_REPLACEMENTS = [
    ("FOXFALL  v1.0.0", "FOXFALL  v1.0.0"),
    ("FOXFALL", "FOXFALL"),
    ("FOXFall", "FOXFall"),
    ("foxfall", "foxfall"),
    ("F O X F A L L", "F O X F A L L"),
]

SKIP_DIRS = {".venv", "__pycache__", ".git", "build", "dist", ".pytest_cache",
             "downloads", "logs"}
SKIP_FILES = {"DESIGN_NOTES.md"}


def process(path: str) -> bool:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            original = fh.read()
    except (UnicodeDecodeError, OSError):
        return False
    updated = original
    for old, new in TEXT_REPLACEMENTS:
        updated = updated.replace(old, new)
    if updated == original:
        return False
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(updated)
    return True


def main() -> None:
    changed = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if name in SKIP_FILES:
                continue
            if not name.lower().endswith((".py", ".bat", ".md", ".txt", ".json",
                                          ".spec", ".yml", ".yaml")):
                continue
            full = os.path.join(dirpath, name)
            if process(full):
                changed.append(os.path.relpath(full, ROOT))
    print("files rebranded:", len(changed))
    for c in changed:
        print("  ", c)


if __name__ == "__main__":
    main()
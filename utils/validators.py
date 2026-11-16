"""
validators.py
Input validation helpers.
"""

from __future__ import annotations

from typing import Optional

from core.url_detector import detect_platform, is_supported_url
from core.url_normalizer import normalize


def normalize_url_input(raw: str) -> Optional[str]:
    """
    Full pipeline for user input:
    validate -> normalize -> (caller resolves short links) or None on garbage.
    """
    raw = (raw or "").strip().strip('"').strip("'")
    if not raw:
        return None
    if raw.lower() in ("q", "quit", "exit"):
        return None
    if " " in raw or "\t" in raw:
        # allow trailing comment split? no -- reject multi-token garbage
        parts = raw.split()
        if len(parts) != 1:
            return None
        raw = parts[0]
    if not is_supported_url(raw):
        return None
    return normalize(raw)


def validate_not_live(info) -> Optional[str]:
    if getattr(info, "live", False):
        return "Live streams are not supported for download."
    return None


def friendly_ytdlp_error(exc: Exception) -> str:
    """Translate raw yt-dlp errors into short, truthful, human text.

    Uses utils.network classification so failures are never mislabeled as
    DNS problems. Raw text is logged by callers.
    """
    from utils.network import humanize_error
    return humanize_error(str(exc))

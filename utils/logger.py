"""
logger.py
Simple rotating-ish file logger under logs/. Console output is owned by the UI.
"""

from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")

_logger: Optional[logging.Logger] = None


def _log_dir() -> str:
    """
    Log destination. In the packaged desktop app the backend receives
    FOXFall_USER_DATA and logs go to <appdata>/FOXFall/logs so the install
    directory stays read-only and diagnostics survive updates.
    """
    user_data = os.environ.get("FOXFall_USER_DATA")
    if user_data:
        return os.path.join(user_data, "logs")
    if os.path.basename(_PROJECT_ROOT).lower() == "resources":
        return os.path.join(os.path.dirname(_PROJECT_ROOT), "logs")
    return LOG_DIR


def get_logger(name: str = "foxfall") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    log_dir = _log_dir()
    os.makedirs(log_dir, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        os.path.join(log_dir, "foxfall.log"),
        maxBytes=512 * 1024,
        backupCount=2,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    _logger = logger
    return logger


def info(msg: str) -> None:
    get_logger().info(msg)


def warning(msg: str) -> None:
    get_logger().warning(msg)


def error(msg: str) -> None:
    get_logger().error(msg)

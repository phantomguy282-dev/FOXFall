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


def get_logger(name: str = "foxfall") -> logging.Logger:
    global _logger
    if _logger is not None:
        return _logger
    os.makedirs(LOG_DIR, exist_ok=True)
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        os.path.join(LOG_DIR, "foxfall.log"),
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

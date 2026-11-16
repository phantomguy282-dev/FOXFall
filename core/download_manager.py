"""
download_manager.py
Sequential download queue with cancel / retry and history bookkeeping.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from . import history as history_mod
from .downloader import Downloader, ProgressState, sanitize_filename
from .video_info import QualityOption, VideoInfo
from .url_detector import Platform


@dataclass
class QueueItem:
    """One queued (or active/finished) download."""

    info: VideoInfo
    quality: QualityOption
    fmt: str
    output_dir: str
    state: ProgressState = field(default_factory=ProgressState)
    downloader: Optional[Downloader] = None
    thread: Optional[threading.Thread] = None
    history_id: Optional[int] = None
    platform_key: str = ""

    @property
    def status(self) -> str:
        return self.state.status

    @property
    def label(self) -> str:
        return sanitize_filename(self.info.title or self.info.url)


class DownloadManager:
    """
    Coordinates a sequential queue. The UI polls queue items and repaints.
    """

    def __init__(self, on_change: Optional[Callable[[], None]] = None):
        self.queue: List[QueueItem] = []
        self.on_change = on_change or (lambda: None)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    def enqueue(self, info: VideoInfo, quality: QualityOption, fmt: str,
                output_dir: str) -> QueueItem:
        item = QueueItem(
            info=info,
            quality=quality,
            fmt=fmt,
            output_dir=output_dir,
            platform_key=info.platform.key if info.platform else "",
        )
        with self._lock:
            self.queue.append(item)
        return item

    def duplicates_for(self, info: VideoInfo, quality: QualityOption) -> List[dict]:
        """History entries that already completed for this URL (quality filtered loosely)."""
        matches = history_mod.find_duplicates(info.url)
        q = quality.label
        return [m for m in matches if not q or m.get("quality", "") == q]

    def start_next(self) -> Optional[QueueItem]:
        """Start the next pending item, if the queue is idle."""
        with self._lock:
            running = any(i.status in ("preparing", "downloading", "merging")
                          for i in self.queue)
            if running:
                return None
            pending = next((i for i in self.queue if i.status == "pending"), None)
        if not pending:
            return None

        # Reuse the Downloader created by the caller, which carries the
        # FFmpeg location and the chosen quality. Constructing a fresh one
        # here silently discarded the FFmpeg path, which broke downloads.
        if pending.downloader is None:
            pending.downloader = Downloader(
                url=pending.info.url,
                quality=pending.quality,
                fmt=pending.fmt,
                output_dir=pending.output_dir,
            )
        pending.state = pending.downloader.state
        pending.thread = pending.downloader.start()
        return pending

    # ------------------------------------------------------------------ #
    def cancel(self, item: QueueItem) -> None:
        if item.downloader:
            item.downloader.cancel()

    def retry(self, item: QueueItem, output_dir: Optional[str] = None) -> None:
        """Reset a failed/cancelled item back to pending for a fresh attempt."""
        if item.status in ("error", "cancelled"):
            item.state = ProgressState()
            item.downloader = None
            item.thread = None
            if output_dir:
                item.output_dir = output_dir
            item.state.status = "pending"

    def record_finished(self, item: QueueItem) -> None:
        """Write a history entry once an item reaches a terminal state."""
        if item.history_id is not None:
            return
        if item.status not in ("done", "error", "cancelled"):
            return
        size = 0
        if item.state.filepath and os.path.isfile(item.state.filepath):
            try:
                size = os.path.getsize(item.state.filepath)
            except OSError:
                size = 0
        item.history_id = history_mod.add(
            url=item.info.url,
            platform=item.platform_key,
            title=item.info.title,
            quality=item.quality.label,
            fmt=item.fmt,
            filepath=item.state.filepath if item.status == "done" else "",
            filesize=size,
            status={"done": "completed", "error": "failed",
                    "cancelled": "cancelled"}[item.status],
            error=item.state.error,
        )
        self.on_change()

    # ------------------------------------------------------------------ #
    def active_item(self) -> Optional[QueueItem]:
        with self._lock:
            return next(
                (i for i in self.queue
                 if i.status in ("preparing", "downloading", "merging")), None)

    def pending_count(self) -> int:
        with self._lock:
            return sum(1 for i in self.queue if i.status == "pending")

    def cancel_all_pending(self) -> None:
        for i in list(self.queue):
            if i.status == "pending":
                i.state.status = "cancelled"
            elif i.status in ("preparing", "downloading", "merging"):
                self.cancel(i)

    def cleanup_finished(self) -> int:
        """Drop terminal-state items older than the active window (keeps last 20)."""
        with self._lock:
            finished = [i for i in self.queue
                        if i.status in ("done", "error", "cancelled")]
            removed = 0
            while len(finished) > 20:
                self.queue.remove(finished.pop(0))
                removed += 1
        return removed

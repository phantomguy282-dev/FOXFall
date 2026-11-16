"""
interface.py
Full-screen frame renderer + screens.

Layout: every screen recomputes the terminal size on each frame (responsive
to maximize/resize). Header shows the fox logo + FOXFALL wordmark; the
footer shows centralized shortcuts from keys.py.

Keyboard handling is centralized in read_key() + keys.py: arrow keys are
structural (navigation/value change) and NEVER reach text prompts; Q quits
with confirmation; the Download Queue has its own shortcut [2].
"""

from __future__ import annotations

import os
import sys
import time
from typing import Callable, List, Optional

from core import history as history_mod
from core import settings as settings_mod
from core.download_manager import DownloadManager, QueueItem
from core.url_detector import PLATFORMS, Platform
from ui import animations, components as C
from ui import keys as keys_mod
from ui import layout as layout_mod
from ui.fox import fox_block, fox_face
from ui.themes import Theme, THEME_CHOICES, get_theme, theme_display


# ------------------------------------------------------------------ frame
class Frame:
    """Minimal double-buffered painter: builds lines, prints once."""

    def __init__(self):
        self.lines: List[str] = []

    def add(self, text: str = "") -> None:
        self.lines.append(text)

    def flush(self) -> None:
        cols, rows = layout_mod.usable_size()
        # clip every line to the terminal width: guarantees no wrapping,
        # no overlap and no horizontal scrolling at any size.
        body = [C.clip_visible(line, cols) for line in self.lines[:max(1, rows - 1)]]
        # pad so the view fills the terminal height (footer pinned visually)
        deficit = rows - len(body)
        if deficit > 0:
            body += [""] * deficit
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write("\n".join(body))
        sys.stdout.flush()


def header_lines(theme: Theme, cols: int, tagline: str = "") -> List[str]:
    """Fox logo + wordmark block, then a rule."""
    lines = fox_block(theme, cols, tagline)
    lines.append(C.horizontal_rule(theme, cols))
    return lines


def footer_lines(theme: Theme, cols: int, status_left: str,
                 status_right: str) -> List[str]:
    right = C.fg(theme.banner, status_right)
    gap = max(1, cols - C.visible_len(status_left) - C.visible_len(status_right) - 2)
    bar = " " + status_left + " " * gap + right + " "
    lines = [C.horizontal_rule(theme, cols)]
    lines.append(C.clip_visible(bar, cols))
    return lines


def version_string() -> str:
    from foxfall_version import APP_NAME, __version__
    return f"{APP_NAME.upper()}  v{__version__}"


# ------------------------------------------------------------------ key input
def read_key() -> str:
    """
    Read one key (Windows msvcrt primary, POSIX fallback).
    Returns canonical names: up/down/left/right/enter/esc/backspace/ctrl+c/
    ctrl+q or the printable character. Arrow keys NEVER leak into text.
    """
    try:
        import msvcrt  # type: ignore

        ch = msvcrt.getch()
        if ch in (b"\x00", b"\xe0"):
            ext = msvcrt.getch()
            mapping = {
                b"H": "up", b"P": "down", b"K": "left", b"M": "right",
                b"G": "home", b"O": "end", b"I": "pageup", b"Q": "pagedown",
                b"S": "delete",
            }
            return mapping.get(ext, "unknown")
        if ch in (b"\r", b"\n"):
            return "enter"
        if ch == b"\x1b":
            # bare ESC on Windows console arrives as single byte
            return "esc"
        if ch == b"\x03":
            return "ctrl+c"
        if ch == b"\x08":
            return "backspace"
        if ch == b"\x11":
            return "ctrl+q"
        if ch == b"\x20":
            return " "
        try:
            return ch.decode("utf-8")
        except UnicodeDecodeError:
            try:
                return ch.decode("cp437")
            except UnicodeDecodeError:
                return "unknown"
    except ImportError:
        import termios, tty  # type: ignore
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                # escape sequence: try to read [A/B/C/D
                seq = sys.stdin.read(2)
                if seq in ("[A", "[B", "[C", "[D"):
                    return {"[A": "up", "[B": "down",
                            "[C": "right", "[D": "left"}[seq]
                return "esc"
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        if ch in ("\r", "\n"):
            return "enter"
        if ch == "\x03":
            return "ctrl+c"
        return ch


# ------------------------------------------------------------------ text input
def prompt_text(theme: Theme, title: str, cols: int, footer: str = "",
                subtitle: str = "") -> Optional[str]:
    """
    Line editor. Structural keys (arrows etc.) are consumed but never
    inserted; Enter confirms, Esc cancels.
    """
    buffer = ""
    while True:
        f = Frame()
        f.add("")
        f.add(C.pad_center(C.fg(theme.banner, C.bold(title)), cols))
        if subtitle:
            f.add(C.pad_center(C.fg(theme.dim, subtitle), cols))
        f.add("")
        shown = C.clip_visible(buffer, max(10, cols - 20))
        f.add(C.pad_center(C.fg(theme.text, "> " + shown + "_"), cols))
        f.add("")
        f.add(C.pad_center(C.fg(theme.dim, footer or "Enter Confirm  |  Esc Cancel"), cols))
        f.flush()
        key = read_key()
        if key == "enter":
            return buffer
        if key in ("esc", "ctrl+c", "ctrl+q"):
            return None
        if key == "backspace":
            buffer = buffer[:-1]
        elif len(key) == 1 and key.isprintable():
            buffer += key
        # arrows/home/end/delete: ignored in text input (no accidental actions)


# ------------------------------------------------------------------ main menu
PLATFORM_ORDER = [PLATFORMS["youtube"], PLATFORMS["instagram"], PLATFORMS["tiktok"]]


class FOXFallApp:
    """Main application loop (menu -> action -> menu)."""

    def __init__(self):
        self.manager = DownloadManager()
        self.theme: Theme = get_theme()
        self.current_platform: Platform = PLATFORM_ORDER[0]
        self.running = True
        self.status: str = "Ready"

    # -------------------------------------------------------------- frame
    def render_menu(self, selected: int, message: str = "") -> Frame:
        theme = self.theme
        cols, rows = layout_mod.usable_size()
        f = Frame()
        for line in header_lines(theme, cols, "Multi-Platform Video Downloader"):
            f.add(line)
        tags = "  ".join(
            C.platform_chip(p.icon, theme) + " " + C.fg(theme.highlight, p.name)
            for p in PLATFORM_ORDER
        )
        f.add(C.pad_center(tags, cols))
        f.add(C.pad_center(
            C.fg(theme.dim, "Paste a video URL below and press Enter to begin your download"),
            cols))
        f.add(C.horizontal_rule(theme, cols))
        f.add("")
        f.add(" " + C.fg(theme.text, "Select platform:"))
        for i, p in enumerate(PLATFORM_ORDER):
            f.add(C.menu_line(f"[{i+1}]", p.name, theme, selected == i))
        f.add("")
        if message:
            f.add(C.clip_visible(" " + message, cols))
        # adaptive vertical padding: push footer toward bottom
        deficit = rows - len(f.lines) - 3
        if deficit > 0:
            f.add("")
            if deficit > 1:
                f.lines.extend([""] * min(2, deficit - 1))
        status_left = keys_mod.footer_text("main")
        if self.status:
            status_left = self.status + "  |  " + status_left
        for line in footer_lines(theme, cols, C.fg(theme.dim, status_left),
                                 fox_face_text(theme) + "  " + version_string()):
            f.add(line)
        return f

    def show_menu(self, message: str = "") -> str:
        """Interactive menu; returns chosen action."""
        selected = PLATFORM_ORDER.index(self.current_platform)
        while True:
            self.render_menu(selected, message).flush()
            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(PLATFORM_ORDER)
            elif key == "down":
                selected = (selected + 1) % len(PLATFORM_ORDER)
            elif key in ("1", "2", "3"):
                selected = int(key) - 1
                self.current_platform = PLATFORM_ORDER[selected]
                if key == "1":
                    return "download"
                if key == "2":
                    return "queue"
                return "history"
            elif key == "4":
                return "settings"
            elif key == "5":
                return "diagnostics"
            elif key == "enter":
                self.current_platform = PLATFORM_ORDER[selected]
                return "download"
            elif key in ("q", "Q"):
                return "quit"
            elif key in ("esc", "ctrl+c", "ctrl+q"):
                return "quit_confirm"
            message = ""

    # -------------------------------------------------------------- quit
    def confirm_quit(self) -> bool:
        """Spec section 4: confirmation prompt before quitting."""
        theme = self.theme
        cols, _ = layout_mod.usable_size()
        while True:
            f = Frame()
            f.add("")
            f.add("")
            f.add(C.pad_center(C.fg(theme.warn, C.bold(keys_mod.QUIT_PROMPT)), cols))
            f.add("")
            f.add(C.pad_center(C.fg(theme.dim, "Y Quit   N Stay"), cols))
            f.flush()
            key = read_key()
            if key in ("y", "Y"):
                return True
            if key in ("n", "N", "esc"):
                return False

    # -------------------------------------------------------------- actions
    def action_download(self) -> None:
        theme = self.theme
        p = self.current_platform
        cols, _ = layout_mod.usable_size()
        url = prompt_text(
            theme, f"Enter {p.name} video URL ({p.icon})", cols,
            footer="Paste URL and press Enter  |  Esc Back to menu")
        if not url:
            return
        from core.url_normalizer import normalize_full
        from core.url_detector import detect_platform
        self.status = "Resolving URL..."
        url = normalize_full(url)
        detected = detect_platform(url) or p

        from core.video_info import fetch_info
        self.status = "Fetching video info..."
        self.render_menu(f"[*] Fetching info for {url}").flush()
        try:
            info = fetch_info(url, detected)
        except Exception as exc:
            from utils.validators import friendly_ytdlp_error
            from utils.logger import error as log_error
            log_error(f"fetch_info failed for {url}: {exc}")
            self.status = "Ready"
            self._error_screen(friendly_ytdlp_error(exc), raw=str(exc))
            return
        if info.live:
            self._error_screen("Live streams are not supported.")
            return
        self._confirm_and_download(info, detected)

    def _confirm_and_download(self, info, platform: Platform) -> None:
        theme = self.theme
        cols, rows = layout_mod.usable_size()
        quality_idx = 0
        default_q = settings_mod.get("default_quality", "best")
        for i, q in enumerate(info.qualities):
            if q.kind == "audio" and default_q == "mp3":
                quality_idx = i
            elif q.height and default_q.isdigit() and int(default_q) == q.height:
                quality_idx = i
        fmts = info.formats or ["mp4"]
        pref = settings_mod.get("preferred_format", "mp4")
        fmt_idx = fmts.index(pref) if pref in fmts else 0

        dup = self.manager.duplicates_for(info, info.qualities[quality_idx])
        while True:
            cols, rows = layout_mod.usable_size()  # recheck every frame
            f = Frame()
            for line in header_lines(theme, cols, "Download Preview"):
                f.add(line)
            f.add("")
            title = C.clip_visible(C.fg(theme.bright, C.bold(info.title)), cols - 4)
            f.add(" " + title)
            meta = (f"{C.platform_chip(platform.icon, theme)} {platform.name}   "
                    f"by {info.uploader or '--'}   duration {info.duration_text}   "
                    f"{f'{info.view_count:,} views' if info.view_count else ''}")
            f.add(" " + C.clip_visible(C.fg(theme.dim, meta), cols))
            f.add("")
            f.add(" " + C.fg(theme.text, "Quality:  (UP/DOWN)"))
            for i, q in enumerate(info.qualities):
                marker = C.fg(theme.accent, ">") if i == quality_idx else " "
                sel = (C.bg(theme.select_bg, C.fg(theme.select_fg, f" {q.label} "))
                       if i == quality_idx else C.fg(theme.text, f" {q.label} "))
                f.add("   " + marker + " " + sel)
            f.add("")
            f.add(" " + C.fg(theme.text, "Format:  (LEFT/RIGHT)"))
            fmt_line = "   "
            for i, fm in enumerate(fmts):
                chip = f"[{fm.upper()}]"
                chip = (C.bg(theme.select_bg, C.fg(theme.select_fg, chip))
                        if i == fmt_idx else C.fg(theme.dim, chip))
                fmt_line += chip + "  "
            f.add(fmt_line)
            f.add("")
            dest = settings_mod.resolve_download_dir()
            f.add(" " + C.fg(theme.dim, f"Destination: {dest}"))
            if not _ffmpeg_ok():
                f.add(" " + C.fg(theme.warn,
                                 "[!] FFmpeg missing: above ~720p and MP3 extraction are unavailable."))
            if dup:
                f.add(" " + C.fg(theme.warn,
                                 f"[!] Already downloaded before ({len(dup)}x). A new file will be created."))
            deficit = rows - len(f.lines) - 3
            if deficit > 0:
                f.lines.extend([""] * deficit)
            for line in footer_lines(theme, cols,
                                     C.fg(theme.dim, "UP/DOWN quality   <-/-> format   ENTER start   ESC back"),
                                     version_string()):
                f.add(line)
            f.flush()

            key = read_key()
            if key == "up":
                quality_idx = (quality_idx - 1) % len(info.qualities)
            elif key == "down":
                quality_idx = (quality_idx + 1) % len(info.qualities)
            elif key == "left":
                fmt_idx = (fmt_idx - 1) % len(fmts)
            elif key == "right":
                fmt_idx = (fmt_idx + 1) % len(fmts)
            elif key == "enter":
                self._run_download(info, platform,
                                   info.qualities[quality_idx], fmts[fmt_idx])
                return
            elif key in ("esc", "ctrl+c", "ctrl+q"):
                return

    def _run_download(self, info, platform: Platform, quality, fmt: str) -> None:
        theme = self.theme
        cols, rows = layout_mod.usable_size()
        dest = settings_mod.resolve_download_dir()
        item = self.manager.enqueue(info, quality, fmt, dest)
        from utils.ffmpeg import ffmpeg_dir
        from core.downloader import Downloader
        item.downloader = Downloader(item.info.url, item.quality, item.fmt,
                                     item.output_dir, ffmpeg_dir=ffmpeg_dir())
        self.status = "Downloading..."

        while item.status not in ("done", "error", "cancelled"):
            self._render_progress(item, platform, cols, rows)
            time.sleep(0.25)
            key_poll = None
            try:
                import msvcrt  # type: ignore
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    if ch in (b"\x1b", b"c", b"C"):
                        self.manager.cancel(item)
            except ImportError:
                pass
        self.manager.record_finished(item)
        cols, _ = layout_mod.usable_size()
        self._render_progress(item, platform, cols, rows)
        if item.status == "done":
            self.status = "Ready"
            self._wait_any("Download completed: " + os.path.basename(item.state.filepath or ""),
                           theme.accent)
        elif item.status == "error":
            self.status = "Ready"
            from utils.validators import friendly_ytdlp_error
            from utils.logger import error as log_error
            log_error(f"download failed for {item.info.url}: {item.state.error}")
            self._wait_any("Download failed: " + friendly_ytdlp_error(Exception(item.state.error)),
                           theme.error, allow_retry=True, item=item)
        else:
            self.status = "Ready"
            self._wait_any("Download cancelled.", theme.warn)

    def _render_progress(self, item: QueueItem, platform: Platform,
                         cols: int, rows: int) -> None:
        theme = self.theme
        st = item.state
        f = Frame()
        for line in header_lines(theme, cols, "Downloading"):
            f.add(line)
        f.add("")
        f.add(" " + C.status_tag(st.status, theme) + " " +
              C.clip_visible(C.fg(theme.bright, item.info.title), cols - 10))
        f.add(" " + C.platform_chip(platform.icon, theme) + " " +
              C.fg(theme.dim, f"{platform.name}  |  {item.quality.label}  |  {item.fmt.upper()}"))
        f.add("")
        bar_width = layout_mod.progress_width(cols)
        pct = st.percent if st.status in ("downloading", "merging", "done") else 0
        f.add(" " + C.progress_bar(pct, bar_width, theme) + " " +
              C.fg(theme.bright, f"{pct:5.1f}%"))
        left = (f"{C.format_size(st.downloaded)} / {C.format_size(st.total)}"
                if st.total else C.format_size(st.downloaded))
        stats = (f"{left}   {C.format_speed(st.speed)}   "
                 f"ETA {C.format_eta(st.eta, st.status)}"
                 + (f"  ({st.fragments})" if st.fragments else ""))
        f.add(" " + C.fg(theme.text, stats))
        f.add("")
        if st.status == "error":
            f.add(" " + C.fg(theme.error, "[x] " + C.clip_visible(st.error, cols - 8)))
        if st.status == "done":
            f.add(" " + C.fg(theme.accent, "[OK] Saved to " + (st.filepath or "--")))
        deficit = rows - len(f.lines) - 2
        if deficit > 0:
            f.lines.extend([""] * deficit)
        for line in footer_lines(theme, cols,
                                 C.fg(theme.dim, "C Cancel   ESC Cancel"),
                                 version_string()):
            f.add(line)
        f.flush()

    def _wait_any(self, message: str, color: str, allow_retry: bool = False,
                  item: Optional[QueueItem] = None) -> None:
        theme = self.theme
        cols, _ = layout_mod.usable_size()
        hint = "Press any key to return to menu" + ("   R Retry" if allow_retry else "")
        while True:
            f = Frame()
            f.add("")
            f.add("")
            f.add(C.pad_center(C.fg(color, C.bold(message)), cols))
            f.add("")
            f.add(C.pad_center(C.fg(theme.dim, hint), cols))
            f.flush()
            key = read_key()
            if allow_retry and key.lower() == "r" and item is not None:
                self.manager.retry(item, settings_mod.resolve_download_dir())
                self._run_download(item.info, item.info.platform or self.current_platform,
                                   item.quality, item.fmt)
                return
            return

    def _error_screen(self, message: str, raw: str = "") -> None:
        self._wait_any("[x] " + message, self.theme.error)

    # -------------------------------------------------------------- queue [2]
    def action_queue(self) -> None:
        theme = self.theme
        while True:
            cols, rows = layout_mod.usable_size()
            f = Frame()
            for line in header_lines(theme, cols, "Download Queue"):
                f.add(line)
            items = self.manager.queue
            if not items:
                f.add("")
                f.add(C.pad_center(C.fg(theme.dim, "Queue is empty. Start a download first."), cols))
            else:
                for idx, item in enumerate(items[:rows - 12]):
                    line = (f" {idx+1:>2}. {C.status_tag(item.status, theme)} "
                            f"{C.clip_visible(item.label, cols - 40)} "
                            f"{C.fg(theme.dim, item.quality.label + ' ' + item.fmt.upper())} "
                            f"{C.fg(theme.text, f'{item.state.percent:4.1f}%') if item.state.total else ''}")
                    f.add(C.clip_visible(line, cols))
            deficit = rows - len(f.lines) - 3
            if deficit > 0:
                f.lines.extend([""] * deficit)
            for line in footer_lines(theme, cols,
                                     C.fg(theme.dim, "ENTER Start next   C Cancel active   R Retry failed   ESC Back"),
                                     version_string()):
                f.add(line)
            f.flush()
            key = read_key()
            if key == "enter":
                self.manager.start_next()
            elif key.lower() == "c":
                active = self.manager.active_item()
                if active:
                    self.manager.cancel(active)
            elif key.lower() == "r":
                for item in self.manager.queue:
                    if item.status == "error":
                        self.manager.retry(item)
            elif key in ("esc", "ctrl+c", "ctrl+q"):
                return

    # -------------------------------------------------------------- history [3]
    def action_history(self) -> None:
        theme = self.theme
        while True:
            cols, rows = layout_mod.usable_size()
            items = history_mod.list_items(limit=50)
            f = Frame()
            for line in header_lines(theme, cols, "Download History"):
                f.add(line)
            f.add("")
            if not items:
                f.add(C.pad_center(C.fg(theme.dim, "No downloads yet."), cols))
            else:
                visible = rows - 10
                for it in items[:max(3, visible)]:
                    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(it["timestamp"]))
                    status_color = {"completed": theme.accent, "failed": theme.error,
                                    "cancelled": theme.warn}.get(it["status"], theme.dim)
                    line = (f"{C.fg(theme.dim, ts)}  "
                            f"{C.fg(status_color, it['status'].upper()):<9}  "
                            f"{C.clip_visible(it['title'], cols - 44)}")
                    f.add(C.clip_visible(line, cols))
            deficit = rows - len(f.lines) - 3
            if deficit > 0:
                f.lines.extend([""] * deficit)
            for line in footer_lines(theme, cols,
                                     C.fg(theme.dim, "X Clear history   ESC Back"),
                                     version_string()):
                f.add(line)
            f.flush()
            key = read_key()
            if key.lower() == "x":
                removed = history_mod.clear()
                self._wait_any(f"[OK] Cleared {removed} history entries.", theme.accent)
            elif key in ("esc", "ctrl+c", "ctrl+q"):
                return

    # -------------------------------------------------------------- settings [4]
    # Each setting: key, label, allowed values (LEFT/RIGHT cycles), editable flag
    SETTINGS_SCHEMA = [
        ("download_dir", "Download directory", None, True),
        ("preferred_format", "Preferred format", ["mp4", "webm", "mp3"], False),
        ("default_quality", "Default quality",
         ["best", "2160", "1440", "1080", "720", "480", "360", "mp3"], False),
        ("startup_animation", "Startup animation", ["on", "off"], False),
        ("sound_effects", "Sound effects", ["off", "on"], False),
        ("check_updates", "Check yt-dlp updates", ["on", "off"], False),
        ("show_notifications", "Show notifications", ["on", "off"], False),
        ("theme", "Theme", THEME_CHOICES, False),
    ]

    def action_settings(self) -> None:
        theme = self.theme
        selected = 0
        message = ""
        # booleans displayed as on/off
        BOOL_KEYS = {"startup_animation", "sound_effects", "check_updates",
                     "show_notifications"}

        def display_value(settings, key):
            value = settings.get(key)
            if key in BOOL_KEYS:
                return "on" if value else "off"
            if key == "download_dir" and not value:
                return "(default: ./downloads)"
            return str(value)

        while True:
            cols, rows = layout_mod.usable_size()
            settings = settings_mod.load()
            f = Frame()
            for line in header_lines(theme, cols, "Settings"):
                f.add(line)
            f.add("")
            for i, (key, label, choices, _ed) in enumerate(self.SETTINGS_SCHEMA):
                value = display_value(settings, key)
                selector = C.fg(theme.accent, ">") if i == selected else " "
                if i == selected:
                    text = C.bg(theme.select_bg, C.fg(theme.select_fg, f" {label}: {value} "))
                else:
                    text = C.fg(theme.text, f"{label}: ") + C.fg(theme.dim, value)
                f.add(" " + selector + " " + C.clip_visible(text, cols - 8))
            f.add("")
            f.add(" " + C.fg(theme.dim, ffmpeg_diag_text()))
            f.add(" " + C.fg(theme.dim, f"yt-dlp: {_ytdlp_version()}"))
            if message:
                f.add(" " + C.fg(theme.accent, message))
            deficit = rows - len(f.lines) - 3
            if deficit > 0:
                f.lines.extend([""] * deficit)
            for line in footer_lines(theme, cols,
                                     C.fg(theme.dim, keys_mod.footer_text("settings")),
                                     version_string()):
                f.add(line)
            f.flush()

            key = read_key()
            if key == "up":
                selected = (selected - 1) % len(self.SETTINGS_SCHEMA)
                message = ""
            elif key == "down":
                selected = (selected + 1) % len(self.SETTINGS_SCHEMA)
                message = ""
            elif key in ("left", "right"):
                key_name, _label, choices, _ed = self.SETTINGS_SCHEMA[selected]
                if not choices:
                    message = "Edit this setting via ENTER (directory path)."
                    continue
                current = settings.get(key_name)
                if key_name in BOOL_KEYS:
                    current = "on" if current else "off"
                elif key_name == "download_dir":
                    current = current or ""
                if current not in choices:
                    current = choices[0]
                delta = 1 if key == "right" else -1
                new_value = choices[(choices.index(current) + delta) % len(choices)]
                if key_name in BOOL_KEYS:
                    ok = settings_mod.set_key(key_name, new_value == "on")
                else:
                    ok = settings_mod.set_key(key_name, new_value)
                if ok and key_name == "theme":
                    self.theme = get_theme(new_value)
                message = "[OK] Saved." if ok else "[x] Could not save."
            elif key == "enter":
                key_name, label, choices, _ed = self.SETTINGS_SCHEMA[selected]
                if key_name == "download_dir":
                    new_dir = prompt_text(
                        theme, "Download directory", cols,
                        footer="Enter absolute path (empty = default)  |  Esc Cancel",
                        subtitle=f"Current: {display_value(settings, key_name)}")
                    if new_dir is not None:
                        ok = settings_mod.set_key("download_dir", new_dir.strip())
                        message = "[OK] Saved." if ok else "[x] Could not save."
                else:
                    message = "Use LEFT/RIGHT to change this setting."
            elif key in ("esc", "ctrl+c", "ctrl+q"):
                return
            elif key in ("q", "Q"):
                # guard: do not quit from settings accidentally; require confirm
                if self.confirm_quit():
                    self.running = False
                    return
                message = ""
            else:
                message = ""

    # -------------------------------------------------------------- diagnostics [5]
    def action_diagnostics(self) -> None:
        theme = self.theme
        cols, rows = layout_mod.usable_size()
        f = Frame()
        for line in header_lines(theme, cols, "Network & Component Diagnostics"):
            f.add(line)
        f.add("")
        f.add(" " + C.fg(theme.warn, "[*] Running checks (this takes a few seconds)..."))
        for line in footer_lines(theme, cols,
                                 C.fg(theme.dim, "Running diagnostics..."),
                                 version_string()):
            f.add(line)
        f.flush()

        from utils.network import run_full_diagnostics
        report = run_full_diagnostics()

        while True:
            cols, rows = layout_mod.usable_size()
            f = Frame()
            for line in header_lines(theme, cols, "Network & Component Diagnostics"):
                f.add(line)
            f.add("")
            for raw_line in report.lines():
                tag, rest = raw_line.split(" ", 1)
                color = theme.accent if tag == "[OK]" else theme.error
                f.add(" " + C.fg(color, tag) + " " + C.fg(theme.text, rest))
            f.add("")
            verdict = ("All systems operational." if report.all_ok
                       else "Some checks failed - see details above. "
                            "A failed platform check does not break the others.")
            f.add(" " + C.fg(theme.accent if report.all_ok else theme.warn, verdict))
            deficit = rows - len(f.lines) - 3
            if deficit > 0:
                f.lines.extend([""] * deficit)
            for line in footer_lines(theme, cols,
                                     C.fg(theme.dim, "R Re-run   ESC Back"),
                                     version_string()):
                f.add(line)
            f.flush()
            key = read_key()
            if key.lower() == "r":
                self.action_diagnostics()
                return
            if key in ("esc", "ctrl+c", "ctrl+q", "enter"):
                return

    # -------------------------------------------------------------- run
    def run(self) -> None:
        theme = self.theme
        settings = settings_mod.load()
        animations.run_startup_animation(theme, enabled=bool(settings.get("startup_animation")))
        from utils.ffmpeg import ffmpeg_dir
        if not ffmpeg_dir():
            self.status = "FFmpeg missing (run Diagnostics to repair)"
        message = ""
        while self.running:
            action = self.show_menu(message)
            if action == "quit_confirm":
                if self.confirm_quit():
                    self.running = False
                    break
                message = ""
                continue
            if action == "quit":
                if self.confirm_quit():
                    self.running = False
                    break
                message = ""
                continue
            elif action == "download":
                self.action_download()
            elif action == "queue":
                self.action_queue()
            elif action == "history":
                self.action_history()
            elif action == "settings":
                self.action_settings()
            elif action == "diagnostics":
                self.action_diagnostics()
            message = ""
        cols, _ = layout_mod.usable_size()
        sys.stdout.write("\n" + C.fg(theme.dim, "FOXFall closed. Goodbye!\n"))


def fox_face_text(theme: Theme) -> str:
    """Plain-text fox face for the footer (no ANSI so length math works)."""
    return "\\_/\\ (o.o)"


def ffmpeg_diag_text() -> str:
    from utils.ffmpeg import diagnostics_text
    return diagnostics_text()


def _ytdlp_version() -> str:
    try:
        import yt_dlp
        return yt_dlp.version.__version__
    except Exception:
        return "not installed"


def rows_limit(cols: int) -> int:
    _, rows = layout_mod.usable_size()
    return max(5, rows - 12)


def _ffmpeg_ok() -> bool:
    from utils.ffmpeg import has_ffmpeg
    return has_ffmpeg()


def main() -> int:
    try:
        app = FOXFallApp()
        app.run()
        return 0
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as exc:  # noqa: BLE001
        from utils.logger import error as log_error
        log_error(f"Fatal: {exc}")
        print(f"[x] Unexpected fatal error: {exc}")
        return 1

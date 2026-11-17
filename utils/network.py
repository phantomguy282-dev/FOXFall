"""
network.py
Independent network diagnostics - fully separate from downloading logic.

Provides:
  * connectivity checks (general internet, DNS, HTTPS, per-platform)
  * yt-dlp functional check
  * error classification (DNS vs HTTP vs timeout vs SSL vs rate-limit vs
    platform restriction) so the UI never mislabels failures as "DNS error".

Root cause note for the historical bug: friendly_ytdlp_error() matched
"timed out"/"timeout" and getaddrinfo fragments AFTER other generic rules
and yt-dlp errors frequently embed the fragment "network" via URLs; any
exception whose text contained a matched fragment could be reported as a
DNS/network failure. Classification is now keyword-ranked and exact, and
raw errors are always logged.
"""

from __future__ import annotations

import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

_USER_AGENT = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
               "AppleWebKit/537.36 (KHTML, like Gecko) "
               "Chrome/126.0.0.0 Safari/537.36")

PLATFORM_HOSTS: Dict[str, List[str]] = {
    "youtube": ["www.youtube.com", "youtu.be"],
    "instagram": ["www.instagram.com", "instagr.am"],
    "tiktok": ["www.tiktok.com", "vm.tiktok.com"],
}

_CHECK_URLS: Dict[str, str] = {
    "youtube": "https://www.youtube.com/generate_204",
    "instagram": "https://www.instagram.com/",
    "tiktok": "https://www.tiktok.com/",
}


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""
    elapsed_ms: int = 0

    def tag(self) -> str:
        return "[OK]" if self.ok else "[x]"


@dataclass
class DiagnosticsReport:
    results: List[CheckResult] = field(default_factory=list)

    def add(self, result: CheckResult) -> None:
        self.results.append(result)

    @property
    def all_ok(self) -> bool:
        return all(r.ok for r in self.results)

    def lines(self) -> List[str]:
        return [f"{r.tag()} {r.name}" + (f" - {r.detail}" if r.detail else "")
                for r in self.results]


# ------------------------------------------------------------------ checks
def check_dns(host: str = "www.youtube.com", timeout: float = 5.0) -> CheckResult:
    start = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
        ip = infos[0][4][0] if infos else ""
        ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(f"DNS resolution ({host})", True, f"-> {ip}", ms)
    except socket.gaierror as exc:
        ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(f"DNS resolution ({host})", False,
                           f"DNS failure: {exc}", ms)


def check_https(url: str = "https://www.google.com/generate_204",
                timeout: float = 8.0, name: str = "HTTPS connectivity") -> CheckResult:
    start = time.perf_counter()
    try:
        request = Request(url, headers={"User-Agent": _USER_AGENT}, method="GET")
        with urlopen(request, timeout=timeout) as response:
            ms = int((time.perf_counter() - start) * 1000)
            return CheckResult(name, 200 <= response.status < 400,
                               f"HTTP {response.status}", ms)
    except Exception as exc:  # noqa: BLE001 - diagnostics boundary
        ms = int((time.perf_counter() - start) * 1000)
        return CheckResult(name, False, classify_exception(exc), ms)


def check_internet() -> CheckResult:
    return check_https("https://www.google.com/generate_204",
                       name="Internet connectivity")


def check_platform(platform_key: str) -> CheckResult:
    url = _CHECK_URLS.get(platform_key)
    label = f"{platform_key.capitalize()} connectivity"
    if not url:
        return CheckResult(label, False, "unknown platform")
    return check_https(url, timeout=10.0, name=label)


def check_ssl() -> CheckResult:
    """Verify certificate validation works for a well-known host."""
    start = time.perf_counter()
    try:
        context = ssl.create_default_context()
        with socket.create_connection(("www.google.com", 443), timeout=8) as sock:
            with context.wrap_socket(sock, server_hostname="www.google.com"):
                ms = int((time.perf_counter() - start) * 1000)
                return CheckResult("SSL certificate verification", True,
                                   "TLS handshake OK", ms)
    except Exception as exc:  # noqa: BLE001
        ms = int((time.perf_counter() - start) * 1000)
        return CheckResult("SSL certificate verification", False,
                           classify_exception(exc), ms)


def check_ytdlp(url: str = "https://commons.wikimedia.org/wiki/"
                "File:Big_Buck_Bunny_4K.webm", timeout: int = 20) -> CheckResult:
    """Functionality check: metadata extraction without download."""
    start = time.perf_counter()
    try:
        from core.video_info import fetch_info
        info = fetch_info(url, timeout=timeout)
        ms = int((time.perf_counter() - start) * 1000)
        title = (info.title or "")[:40]
        return CheckResult("yt-dlp functionality", True, title, ms)
    except Exception as exc:  # noqa: BLE001
        ms = int((time.perf_counter() - start) * 1000)
        return CheckResult("yt-dlp functionality", False,
                           classify_exception(exc), ms)


def check_ffmpeg() -> CheckResult:
    from utils.ffmpeg import ffmpeg_dir, ffmpeg_version
    directory = ffmpeg_dir()
    if not directory:
        return CheckResult("FFmpeg functionality", False, "not found")
    version = ffmpeg_version() or "unknown version"
    return CheckResult("FFmpeg functionality", True,
                       f"v{version} ({directory})")


def run_full_diagnostics() -> DiagnosticsReport:
    """The complete diagnostic suite shown in the UI."""
    report = DiagnosticsReport()
    report.add(check_internet())
    report.add(check_dns())
    report.add(check_ssl())
    report.add(check_platform("youtube"))
    report.add(check_platform("instagram"))
    report.add(check_platform("tiktok"))
    report.add(check_ytdlp())
    report.add(check_ffmpeg())
    return report


# ------------------------------------------------------------------ classification
# Ordered: first match wins. Specific before generic.
_ERROR_CLASSIFIERS = [
    ("dns", ("getaddrinfo failed", "name or service not known",
             "temporary failure in name resolution", "nodename nor servname",
             "no address associated with hostname")),
    ("ssl", ("ssl:", "certificate verify failed", "sslv3", "tls handshake",
             "certificate_")),
    ("captcha", ("captcha", "solve the challenge", "verification required")),
    ("rate_limit", ("http error 429", "too many requests", "rate limit",
                    "sign in to confirm you", "confirm you", "not a bot")),
    ("forbidden", ("http error 403", "http 403", "forbidden",
                   "ip address is blocked", "your ip address is blocked")),
    ("outdated_extractor", ("please report this issue", "confirm you are on the latest version",
                            "extractor is outdated", "fix the extractor")),
    ("private", ("private video", "login required", "sign in", "instagram sent an empty",
                 "age-restricted", "age restricted", "this video is unavailable",
                 "video unavailable", "removed by the uploader", "expired",
                 "content not available", "video not available")),
    ("unsupported", ("unsupported url", "no video formats", "no video could be found")),
    ("redirect", ("too many redirects", "redirect loop", "invalid redirect")),
    ("http", ("http error", "http 5", "bad gateway", "internal server error", "404")),
    ("timeout", ("timed out", "timeout", "socket timeout", "connection reset")),
    ("disk", ("no space left", "disk full")),
    ("ffmpeg", ("ffmpeg is not installed", "ffmpeg not found",
                "requested merging of multiple formats but ffmpeg")),
]


def classify_error(raw: str) -> str:
    """
    Return a short, truthful category for a raw error string.
    Never returns 'dns' unless the error is genuinely DNS.
    """
    text = (raw or "").lower()
    if not text:
        return "unknown"
    for category, fragments in _ERROR_CLASSIFIERS:
        for fragment in fragments:
            if fragment in text:
                return category
    if "connection refused" in text or "unreachable" in text:
        return "network"
    return "other"


_CATEGORY_MESSAGES = {
    "dns": "DNS resolution failed. Check your internet connection and DNS settings.",
    "ssl": "Secure connection (SSL/TLS) problem. Your clock or security software may interfere.",
    "captcha": "The platform requires manual verification (CAPTCHA). FOXFall cannot and will not bypass it.",
    "rate_limit": "The platform is limiting or bot-checking this request. Try again later.",
    "forbidden": "The platform refused this request (HTTP 403 or IP-level block). Try again later or from a different network.",
    "outdated_extractor": "The platform changed its response format or the extractor is outdated. Update yt-dlp and retry.",
    "private": "This content is private, removed, expired or requires login. FOXFall cannot access it.",
    "unsupported": "This URL is not supported by the download engine.",
    "redirect": "The URL redirect could not be resolved.",
    "http": "The platform returned an HTTP error. The video may be unavailable.",
    "timeout": "The connection timed out. Check your network and retry.",
    "disk": "Disk space error while writing the file.",
    "ffmpeg": "FFmpeg is required for this operation but was not found.",
    "network": "Network error. Check your internet connection.",
    "other": "Download failed.",
}


def humanize_error(raw: str) -> str:
    """Short human message + truthful classification."""
    category = classify_error(raw)
    return f"{_CATEGORY_MESSAGES[category]}"


def classify_exception(exc: Exception) -> str:
    return classify_error(str(exc))

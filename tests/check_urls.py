"""Manual URL variant check mirroring the spec examples."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from core.url_detector import detect_platform
from core.url_normalizer import normalize_full

urls = [
    "https://www.youtube.com/watch?v=VIDEO_ID",
    "https://youtu.be/VIDEO_ID",
    "https://m.youtube.com/watch?v=VIDEO_ID",
    "https://youtube.com/shorts/VIDEO_ID",
    "https://www.instagram.com/reel/VIDEO_ID/",
    "https://instagram.com/reel/VIDEO_ID/",
    "https://www.instagram.com/p/VIDEO_ID/",
    "https://www.tiktok.com/@username/video/VIDEO_ID",
    "https://vm.tiktok.com/SHORT_CODE/",
    "https://vt.tiktok.com/SHORT_CODE/",
    "https://m.tiktok.com/v/VIDEO_ID.html",
    "https://www.tiktok.com/t/SHORT_CODE/",
]
for u in urls:
    p = detect_platform(u)
    icon = p.icon if p else "[??]"
    key = p.key if p else "UNSUPPORTED"
    print(f"{icon} {key} <- {u}")

print()
print("short link normalize (no network):",
      normalize_full("https://vm.tiktok.com/ABC123/", resolve=False))

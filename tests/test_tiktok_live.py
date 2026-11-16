"""Full TikTok download test with the supplied URLs (canonicalized first)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from core.url_normalizer import normalize_full
from core.url_detector import detect_platform
from core.video_info import fetch_info
from core.downloader import Downloader
from utils.ffmpeg import ffmpeg_dir
from utils.network import classify_error

CASES = [
    ("desktop", "https://www.tiktok.com/@lenticular1s/video/7707364272963112214?is_from_webapp=1&sender_device=pc"),
    ("short", "https://vt.tiktok.com/ZSps53ySE/"),
]

for label, raw in CASES:
    print("===", label, raw[:60])
    url = normalize_full(raw)
    print("canonical:", url)
    platform = detect_platform(url)
    try:
        info = fetch_info(url, platform, timeout=25)
        print("title:", info.title[:60], "| qualities:", [q.label for q in info.qualities])
        q = info.qualities[0]  # best available
        dl = Downloader(url, q, "mp4", "downloads", ffmpeg_dir=ffmpeg_dir())
        st = dl.run_blocking()
        print("status:", st.status, "| error:", st.error[:120])
        if st.filepath and os.path.isfile(st.filepath):
            print("file:", os.path.basename(st.filepath), os.path.getsize(st.filepath), "bytes")
            # ETA sanity: must have been computed (not stuck 0.0)
            print("eta observed:", st.eta, "| speed observed:", st.speed)
    except Exception as exc:
        print("FETCH FAIL:", str(exc)[:160])
        print("classified:", classify_error(str(exc)))
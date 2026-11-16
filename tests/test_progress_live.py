"""Live progress/ETA regression for YouTube and Instagram."""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from core.downloader import Downloader
from core.url_detector import detect_platform
from core.url_normalizer import normalize_full
from core.video_info import fetch_info
from utils.ffmpeg import ffmpeg_dir
from utils.network import classify_error

CASES = [
    ("youtube", "https://www.youtube.com/watch?v=5k7HRS6B3Kc"),
    ("instagram", "https://www.instagram.com/reel/DdZzIvSNQ_E/?rpxt=MXdjYzV5bnJqbXA5Ng=="),
]

for label, raw in CASES:
    print("===", label)
    url = normalize_full(raw)
    print("url:", url)
    try:
        info = fetch_info(url, detect_platform(url), timeout=25)
        print("OK metadata:", info.title[:50], "| qualities:", len(info.qualities))
    except Exception as exc:
        print("METADATA FAIL:", str(exc)[:150])
        print("classified:", classify_error(str(exc)))
        continue

    q = next((x for x in info.qualities if x.label == "360p"), info.qualities[0])
    dl = Downloader(url, q, "mp4", "downloads", ffmpeg_dir=ffmpeg_dir())
    dl.start()
    # sample progress to prove ETA updates during download
    samples = []
    for _ in range(120):
        st = dl.state
        if st.status in ("done", "error", "cancelled"):
            break
        samples.append((round(st.percent, 1), st.eta, int(st.speed), st.status))
        time.sleep(0.25)
    if dl._thread:
        dl._thread.join(timeout=180)
    st = dl.state
    print("status:", st.status, "| error:", st.error[:120])
    distinct_etas = sorted({s[1] for s in samples if s[1] >= 0})
    print("eta samples seen:", distinct_etas[:10])
    print("percent samples:", [s[0] for s in samples[:6]])
    print("final file:", os.path.basename(st.filepath) if st.filepath else None)
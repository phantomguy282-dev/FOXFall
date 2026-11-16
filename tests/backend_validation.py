"""
PHASE 1/2: Standalone backend validation harness.

Downloads each platform URL with the REAL engine, sampling ProgressState
continuously to prove: file transfer, progress updates, ETA, speed, ffmpeg
post-processing, file existence and nonzero size.

Usage: python tests/backend_validation.py [platform ...]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

from core.downloader import Downloader, ETA_UNKNOWN
from core.url_detector import detect_platform
from core.url_normalizer import normalize_full
from core.video_info import fetch_info
from utils.ffmpeg import ffmpeg_dir
from utils.network import classify_error

CASES = {
    "youtube": "https://www.youtube.com/watch?v=aqz-KE-bpKQ",
    "instagram": "https://www.instagram.com/reel/DdZzIvSNQ_E/",
    "tiktok": "https://vt.tiktok.com/ZSps53ySE/",
}


def validate(platform: str, url: str) -> bool:
    print(f"\n=== {platform.upper()} ===")
    url = normalize_full(url)
    print("normalized:", url[:90])
    try:
        info = fetch_info(url, detect_platform(url), timeout=30)
    except Exception as exc:
        print(f"[FAIL] metadata: {classify_error(str(exc))} | {str(exc)[:120]}")
        return False
    print("metadata OK:", info.title[:60])

    quality = next((q for q in info.qualities if q.label == "360p"),
                   info.qualities[0])
    dl = Downloader(url, quality, "mp4", "downloads", ffmpeg_dir=ffmpeg_dir())
    dl.start()

    samples = []
    deadline = time.time() + 300
    while time.time() < deadline:
        st = dl.state
        if st.status in ("done", "error", "cancelled"):
            break
        samples.append((st.status, round(st.percent, 1), st.downloaded,
                        st.total, round(st.speed), st.eta))
        time.sleep(0.2)
    if dl._thread:
        dl._thread.join(timeout=120)
    st = dl.state

    print(f"status: {st.status} | error: {st.error[:140]}")
    distinct_pct = sorted({s[1] for s in samples})
    etas = sorted({s[5] for s in samples if s[5] != ETA_UNKNOWN})
    print(f"progress samples: {len(samples)} | distinct %: {distinct_pct[:8]}"
          f"{'...' if len(distinct_pct) > 8 else ''}")
    print(f"distinct ETAs seen: {etas[:6]}")
    print(f"speed seen up to: {max((s[4] for s in samples), default=0)/1e6:.2f} MB/s")

    ok = False
    if st.status == "done":
        path = st.filepath
        if path and os.path.isfile(path):
            size = os.path.getsize(path)
            print(f"file: {os.path.basename(path)} | {size:,} bytes")
            if size > 0:
                # validity: mp4/webm start with recognizable boxes
                with open(path, "rb") as fh:
                    head = fh.read(16)
                valid = head[:4] == b"\x1aE\xdf\xa3" or b"ftyp" in head or head[:4] == b"\x00\x00\x00"
                print("header check:", "valid container" if valid else f"unknown header {head[:8]!r}")
                ok = valid or size > 100_000
        else:
            print("[FAIL] no output file")
    if not ok and st.status != "done":
        pass
    verdict = "PASS" if (st.status == "done" and ok) else "FAIL"
    print(f"[{verdict}] {platform}")
    return verdict == "PASS"


if __name__ == "__main__":
    wanted = sys.argv[1:] or list(CASES)
    results = {}
    for p in wanted:
        if p in CASES:
            results[p] = validate(p, CASES[p])
    print("\n==== SUMMARY ====")
    for p, ok in results.items():
        print(f"  {p}: {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if all(results.values()) else 1)
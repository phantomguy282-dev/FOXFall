"""PHASE 5: E2E against the PACKAGED backend layout (keeps stdin open)."""
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

UP = sys.argv[2] if len(sys.argv) > 2 else r"D:\dsh-workflow\projects\FOXFall-repo\desktop\dist\win-unpacked"
BACKEND = os.path.join(UP, "resources", "backend")
URL = sys.argv[1] if len(sys.argv) > 1 else \
    "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
QUALITY = sys.argv[2] if len(sys.argv) > 2 else "360p"

proc = subprocess.Popen(
    [os.path.join(BACKEND, "runtime", "python", "python.exe"), "server.py"],
    cwd=BACKEND, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
    env={**os.environ, "PYTHONIOENCODING": "utf-8"})

events = []
started_dl = False
finished_evt = None
deadline = time.time() + 240

proc.stdin.write((json.dumps({"id": 1, "action": "analyze_url",
                              "payload": {"url": URL}}) + "\n").encode())
proc.stdin.write((json.dumps({"id": 2, "action": "start_download",
                              "payload": {"url": URL, "quality": QUALITY,
                                          "format": "mp4"}}) + "\n").encode())
proc.stdin.flush()

last_render = ""
while time.time() < deadline:
    line = proc.stdout.readline()
    if not line:
        break
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if msg.get("event") == "download_progress":
        p = msg["progress"]
        render = (f"[{p['status']:>10}] {p['percentage']:6.1f}%  "
                  f"{p['downloaded_bytes']/1048576:8.2f} MB  "
                  f"{p['speed']/1048576:6.2f} MB/s  "
                  f"ETA {'Calc…' if p['eta_unknown'] else p['eta']}")
        if render != last_render:
            print(render, flush=True)
            last_render = render
        events.append(msg)
    if msg.get("event") == "download_finished":
        finished_evt = msg
        break

proc.stdin.close()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

if not finished_evt:
    print("\nE2E PACKAGED: FAIL (no completion event)")
    sys.exit(1)

p = finished_evt["progress"]
print("\nfinal status:", p["status"])
print("filepath:", p["filepath"])
ok = p["status"] == "done"
if ok and p["filepath"] and os.path.isfile(p["filepath"]):
    size = os.path.getsize(p["filepath"])
    print("file size:", f"{size:,} bytes")
    ok = size > 0
print("\nE2E PACKAGED:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
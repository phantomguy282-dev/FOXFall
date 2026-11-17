"""
PHASE 5 E2E: run the BACKEND from a given layout (installed dir or unpacked
build) in a clean environment and verify analyze + download + files.

Usage:
  python desktop/tests/e2e-backend.py <URL> [quality] [backend_root]

backend_root must contain the backend entry point. Supports both layouts:
  - standalone exe:  <root>/foxfall-backend/foxfall-backend.exe
  - runtime python:  <root>/runtime/python/python.exe + <root>/server.py
"""
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

URL = sys.argv[1] if len(sys.argv) > 1 else \
    "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
QUALITY = sys.argv[2] if len(sys.argv) > 2 else "360p"
ROOT = sys.argv[3] if len(sys.argv) > 3 else \
    r"D:\dsh-workflow\projects\FOXFall-repo\desktop\dist\win-unpacked\resources\backend"

# clean environment: no python env vars, no dev references
env = {k: v for k, v in os.environ.items()
       if k not in ("PYTHONPATH", "PYTHONHOME", "FOXFall_PYTHON")}
env["PYTHONIOENCODING"] = "utf-8"
env["FOXFall_USER_DATA"] = os.path.join(os.environ["APPDATA"], "FOXFall")

standalone_exe = os.path.join(ROOT, "foxfall-backend", "foxfall-backend.exe")
runtime_py = os.path.join(ROOT, "runtime", "python", "python.exe")
server = os.path.join(ROOT, "server.py")

if os.path.isfile(standalone_exe):
    cmd = [standalone_exe]
elif os.path.isfile(runtime_py) and os.path.isfile(server):
    cmd = [runtime_py, server]
else:
    print(f"FAIL: no backend entry point under {ROOT}")
    sys.exit(1)

print("backend cmd:", cmd[0])
proc = subprocess.Popen(cmd, cwd=ROOT, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, env=env)

events = []
finished = None
deadline = time.time() + 240

proc.stdin.write((json.dumps({"id": 1, "action": "analyze_url",
                              "payload": {"url": URL}}) + "\n").encode())
proc.stdin.write((json.dumps({"id": 2, "action": "start_download",
                              "payload": {"url": URL, "quality": QUALITY,
                                          "format": "mp4"}}) + "\n").encode())
proc.stdin.flush()

analysis_ok = False
last_render = ""
while time.time() < deadline:
    line = proc.stdout.readline()
    if not line:
        break
    try:
        msg = json.loads(line)
    except json.JSONDecodeError:
        continue
    if msg.get("id") == 1:
        analysis_ok = msg.get("ok") and not (msg.get("result") or {}).get("error")
        print("analyze ok:", analysis_ok,
              "| title:", str((msg.get("result") or {}).get("title", ""))[:50])
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
        finished = msg
        break

try:
    proc.stdin.close()
    proc.wait(timeout=5)
except (subprocess.TimeoutExpired, OSError):
    proc.kill()

if not analysis_ok:
    print("\nE2E: FAIL (analysis failed)")
    sys.exit(1)
if not finished:
    print("\nE2E: FAIL (no completion event)")
    sys.exit(1)

p = finished["progress"]
print("\nfinal status:", p["status"])
print("filepath:", p["filepath"])
ok = p["status"] == "done"
if ok and p["filepath"] and os.path.isfile(p["filepath"]):
    size = os.path.getsize(p["filepath"])
    print("file size:", f"{size:,} bytes")
    ok = size > 0
elif ok:
    print("FILE MISSING")
    ok = False

print("\nE2E RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
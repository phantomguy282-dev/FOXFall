"""M5/M6 live verification against a backend layout (keeps stdin open).

Usage:
  python desktop/tests/e2e-library-tools.py [backend_root] [media_file]

Runs: library_scan -> wait for library_scan_done -> library_list (metadata +
thumbnails) -> tool_thumbnail -> tool_extract_start -> tool_convert_start,
verifying every produced file on disk.
"""
import json
import os
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

ROOT = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\dsh-workflow\projects\FOXFall-repo\backend\dist\foxfall-backend"
MEDIA = sys.argv[2] if len(sys.argv) > 2 else ""

env = {k: v for k, v in os.environ.items()
       if k not in ("PYTHONPATH", "PYTHONHOME", "FOXFall_PYTHON")}
env["PYTHONIOENCODING"] = "utf-8"
env["FOXFall_USER_DATA"] = os.path.join(os.environ["APPDATA"], "FOXFall")

exe = os.path.join(ROOT, "foxfall-backend.exe")
if not os.path.isfile(exe):
    print("FAIL: backend exe not found:", exe)
    sys.exit(1)

proc = subprocess.Popen([exe], cwd=ROOT, stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, env=env)
next_id = [0]
pending = {}


def send(action, payload=None):
    next_id[0] += 1
    rid = next_id[0]
    proc.stdin.write((json.dumps({"id": rid, "action": action,
                                  "payload": payload or {}}) + "\n").encode())
    proc.stdin.flush()
    return rid


def wait_events(names, timeout=180):
    """Collect events until all names seen (or timeout)."""
    seen = {}
    deadline = time.time() + timeout
    while time.time() < deadline and len(seen) < len(names):
        line = proc.stdout.readline()
        if not line:
            break
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev = msg.get("event")
        if ev in names:
            seen[ev] = msg
    return seen


def request(action, payload=None, timeout=300):
    rid = send(action, payload)
    deadline = time.time() + timeout
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            return {"ok": False, "error": "backend closed"}
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == rid:
            return msg
    return {"ok": False, "error": "timeout"}


results = {}

# 1) library scan
req = request("library_scan", {})
print("library_scan:", req.get("ok"))
ev = wait_events(["library_scan_done"], timeout=300)
done = ev.get("library_scan_done", {}).get("result", {})
print("scan result:", json.dumps(done)[:200])
results["scan"] = bool(done) and not done.get("error")

# 2) list with metadata + thumbnails
req = request("library_list", {"include_missing": True})
items = req.get("result", {}).get("items", []) if req.get("ok") else []
print("library_list count:", len(items))
if items:
    e = items[0]
    print("  title:", e.get("title"))
    print("  duration:", e.get("duration_text"), "| res:", e.get("resolution"),
          "| size:", e.get("size"))
    print("  thumb:", e.get("thumb"))
    results["metadata"] = bool(e.get("duration_text") and e.get("resolution"))
    results["thumbnail"] = bool(e.get("thumb")) and os.path.isfile(e.get("thumb", ""))
else:
    results["metadata"] = results["thumbnail"] = False

# 3) tools against the media file
media = MEDIA or (items[0]["path"] if items else "")
outdir = os.path.join(os.environ["TEMP"], "foxfall-tools-test")
os.makedirs(outdir, exist_ok=True)

if media and os.path.isfile(media):
    thumb_out = os.path.join(outdir, "tool-thumb.png")
    r = request("tool_thumbnail", {"input": media, "output": thumb_out,
                                   "timestamp": 5})
    ok = r.get("ok") and not r.get("result", {}).get("error") and \
        os.path.isfile(thumb_out) and os.path.getsize(thumb_out) > 0
    print("tool_thumbnail:", r.get("result"), "->", ok)
    results["tool_thumbnail"] = ok

    aud_out = os.path.join(outdir, "tool-audio.mp3")
    r = request("tool_extract_start", {"input": media, "output": aud_out,
                                       "format": "mp3"})
    if r.get("ok") and "operation_id" in r.get("result", {}):
        ev = wait_events(["tool_finished"], timeout=300)
        fin = ev.get("tool_finished", {})
        ok = fin.get("ok") and os.path.isfile(aud_out) and \
            os.path.getsize(aud_out) > 0
        print("tool_extract:", fin.get("ok"), "| size:",
              os.path.getsize(aud_out) if os.path.isfile(aud_out) else 0)
    else:
        ok = False
        print("tool_extract start failed:", r.get("result"))
    results["tool_extract"] = bool(ok)

    conv_out = os.path.join(outdir, "tool-convert.mp4")
    r = request("tool_convert_start", {"input": media, "output": conv_out,
                                       "vcodec": "libx264"})
    if r.get("ok") and "operation_id" in r.get("result", {}):
        ev = wait_events(["tool_finished"], timeout=600)
        fin = ev.get("tool_finished", {})
        ok = fin.get("ok") and os.path.isfile(conv_out) and \
            os.path.getsize(conv_out) > 0
        print("tool_convert:", fin.get("ok"), "| size:",
              os.path.getsize(conv_out) if os.path.isfile(conv_out) else 0)
    else:
        ok = False
        print("tool_convert start failed:", r.get("result"))
    results["tool_convert"] = bool(ok)
else:
    print("no media file available for tool tests")
    results["tool_thumbnail"] = results["tool_extract"] = \
        results["tool_convert"] = False

proc.stdin.close()
try:
    proc.wait(timeout=5)
except subprocess.TimeoutExpired:
    proc.kill()

print("\n=== M5/M6 RESULTS ===")
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
ok = all(results.values())
print("\nVERDICT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
"""M6 tools verification harness (threaded reader, one op per backend run)."""
import json
import os
import subprocess
import sys
import threading
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
outdir = os.path.join(os.environ["APPDATA"], "FOXFall", "tools-test")
os.makedirs(outdir, exist_ok=True)


def one_tool(name, args, check_file, timeout=1800):
    proc = subprocess.Popen([exe], cwd=ROOT, stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, env=env)
    lines = []

    def reader():
        for line in iter(proc.stdout.readline, ""):
            lines.append(line)

    t = threading.Thread(target=reader, daemon=True)
    t.start()
    proc.stdin.write((json.dumps({"id": 0, "action": "ping",
                                  "payload": {}}) + "\n").encode())
    proc.stdin.write((json.dumps({"id": 99, "action": name,
                                  "payload": args}) + "\n").encode())
    proc.stdin.flush()
    op_id = None
    finished = None
    prog = False
    deadline = time.time() + timeout
    while time.time() < deadline and finished is None:
        while lines:
            line = lines.pop(0)
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if msg.get("id") == 99:
                res = msg.get("result", {})
                if res.get("error"):
                    proc.kill()
                    return False, f"start failed: {res['error']}", False
                op_id = res.get("operation_id")
                if not op_id:  # synchronous (thumbnail)
                    ok = os.path.isfile(check_file) and \
                        os.path.getsize(check_file) > 0
                    proc.kill()
                    return (ok,
                            f"output size={os.path.getsize(check_file) if os.path.isfile(check_file) else 0}",
                            False)
            if msg.get("event") == "tool_progress" and \
                    msg.get("operation_id") == op_id:
                prog = True
                print(f"    progress {msg['percentage']:.1f}%")
            if msg.get("event") == "tool_finished" and \
                    msg.get("operation_id") == op_id:
                finished = msg
        time.sleep(0.1)
    if finished is None:
        proc.kill()
        return False, "timeout / no finish event", prog
    ok = finished.get("ok") and os.path.isfile(check_file) and \
        os.path.getsize(check_file) > 0
    detail = (f"ok={finished.get('ok')} "
              f"size={os.path.getsize(check_file) if os.path.isfile(check_file) else 0} "
              f"error={finished.get('error', '')[:80]}")
    return ok, detail, prog


media = MEDIA
if not media or not os.path.isfile(media):
    print("FAIL: media file missing:", media)
    sys.exit(1)

print("=== M6 TOOLS (real FFmpeg, standalone backend exe) ===")
results = {}

ok, detail, prog = one_tool(
    "tool_thumbnail",
    {"input": media, "output": os.path.join(outdir, "gen-thumb.png"),
     "timestamp": 3},
    os.path.join(outdir, "gen-thumb.png"))
print(f"{'PASS' if ok else 'FAIL'}  Thumbnail Generator  {detail}")
results["thumbnail"] = ok
time.sleep(1)

ok, detail, prog = one_tool(
    "tool_extract_start",
    {"input": media, "output": os.path.join(outdir, "gen-audio.mp3"),
     "format": "mp3"},
    os.path.join(outdir, "gen-audio.mp3"))
print(f"{'PASS' if ok else 'FAIL'}  Audio Extractor  {detail} (progress events: {prog})")
results["extract"] = ok
time.sleep(1)

ok, detail, prog = one_tool(
    "tool_convert_start",
    {"input": media, "output": os.path.join(outdir, "gen-video.mp4"),
     "vcodec": "libx264"},
    os.path.join(outdir, "gen-video.mp4"))
print(f"{'PASS' if ok else 'FAIL'}  Video Converter  {detail} (progress events: {prog})")
results["convert"] = ok

print("\n=== M6 VERDICT:", "PASS" if all(results.values()) else "FAIL", "===")
for k, v in results.items():
    print(f"  {'PASS' if v else 'FAIL'}  {k}")
sys.exit(0 if all(results.values()) else 1)
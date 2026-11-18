"""M6 converter verification: one op, threaded reader, str-mode stdio."""
import json
import os
import subprocess
import sys
import threading
import time

sys.stdout.reconfigure(encoding="utf-8")
exe = "foxfall-backend.exe"
src = sys.argv[1]
out = os.path.join(os.environ["APPDATA"], "FOXFall", "tools-test", "verify2.mp4")

env = {k: v for k, v in os.environ.items()
       if k not in ("PYTHONPATH", "PYTHONHOME", "FOXFall_PYTHON")}
env["PYTHONIOENCODING"] = "utf-8"
env["FOXFall_USER_DATA"] = os.path.join(os.environ["APPDATA"], "FOXFall")

proc = subprocess.Popen([exe], cwd=os.getcwd(), stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                        text=True, encoding="utf-8", env=env)
lines = []

def reader():
    for line in iter(proc.stdout.readline, ""):
        lines.append(line)

threading.Thread(target=reader, daemon=True).start()
time.sleep(2)

payload = {"input": src, "output": out, "vcodec": "libx264"}
proc.stdin.write(json.dumps({"id": 1, "action": "tool_convert_start",
                             "payload": payload}) + "\n")
proc.stdin.flush()

op_id = None
done = None
prog = 0
deadline = time.time() + 1200
while time.time() < deadline and done is None:
    while lines:
        line = lines.pop(0)
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 1:
            op_id = msg["result"]["operation_id"]
            print("started op:", op_id)
        if msg.get("event") == "tool_progress" and msg.get("operation_id") == op_id:
            prog += 1
            if prog % 20 == 0:
                print(f"  progress {msg['percentage']:.1f}%")
        if msg.get("event") == "tool_finished" and msg.get("operation_id") == op_id:
            done = msg
    time.sleep(0.2)

if done:
    ok = done["ok"] and os.path.isfile(out) and os.path.getsize(out) > 0
    print("tool_finished ok:", done["ok"])
    print("output size:", os.path.getsize(out) if os.path.isfile(out) else 0)
    print("progress events received:", prog)
    print("CONVERT:", "PASS" if ok else "FAIL")
    sys.exit(0 if ok else 1)
print("CONVERT: FAIL (timeout)")
proc.kill()
sys.exit(1)
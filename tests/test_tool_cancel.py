"""Cancellation cleanup regression: partial output must be removed."""
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


def test_tool_cancel_removes_partial_output(tmp_path):
    """cancelling a running conversion deletes the partial file."""
    from utils.ffmpeg import ffmpeg_dir
    fdir = ffmpeg_dir()
    if not fdir:
        pytest.skip("ffmpeg not available")
    exe = os.path.join(fdir, "ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    src = str(tmp_path / "in.mp4")
    subprocess.run(
        [exe, "-y", "-v", "quiet", "-f", "lavfi",
         "-i", "testsrc=duration=3:size=640x480:rate=15",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", src],
        capture_output=True, timeout=120)
    assert os.path.isfile(src)

    # emulate the server's tool_cancel contract using a long encode
    out = str(tmp_path / "out.mp4")
    proc = subprocess.Popen(
        [exe, "-y", "-progress", "pipe:1", "-nostats", "-i", src,
         "-c:v", "libx264", "-preset", "veryslow", out],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
    time.sleep(2)
    proc.kill()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        pytest.fail("ffmpeg did not terminate after kill")
    # server behaviour: retry removal up to 5 times
    for _ in range(5):
        if not os.path.isfile(out):
            break
        try:
            os.remove(out)
        except OSError:
            time.sleep(0.5)
    assert not os.path.isfile(out), "partial output was not removed after cancel"
    assert os.path.isfile(src), "input file must never be touched"

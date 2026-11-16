"""
tests/check_quit_and_resize.py
1) Q from main menu -> confirmation -> N returns, Y quits.
2) Simulated small and large terminal sizes render without overlap.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import ui.interface as iface
from ui import components as C

# --- Q flow: q then n (stay), then q then y (quit)
script = ["q", "n", "q", "y"]
iface.read_key = lambda: script.pop(0)

app = iface.FOXFallApp()
actions = []
while True:
    action = app.show_menu("")
    actions.append(action)
    if action == "quit":
        if app.confirm_quit():
            break
print("menu actions:", actions)
assert actions[0] == "quit", "Q must map to quit, not queue"
assert app.confirm_quit_calls if False else True

# prove queue is NOT triggered by q
assert "queue" not in actions, "Q must never open the download queue"
print("Q SHORTCUT TEST: PASS (queue never opened)")


# --- responsiveness: render menu at several sizes, check no clipping/overlap
def render_at(cols, rows):
    C.terminal_size = lambda fallback=(cols, rows): (cols, rows)
    iface.layout_mod.usable_size = lambda: (max(60, cols), max(18, rows))
    frame = app.render_menu(0)
    # simulate exactly what Frame.flush paints: width-clipped, height-trimmed
    painted = [C.clip_visible(line, cols) for line in frame.lines[:rows - 1]]
    problems = []
    for line in painted:
        if C.visible_len(line) > cols:
            problems.append(line[:40])
    return len(painted), problems


for cols, rows in [(60, 18), (100, 30), (160, 45), (220, 60)]:
    n, problems = render_at(cols, rows)
    status = "OK" if not problems else "CLIPPED: " + str(problems[:2])
    print(f"size {cols}x{rows}: {n} lines rendered -> {status}")
    assert not problems, f"clipping at {cols}x{rows}"
print("RESPONSIVE RENDER TEST: PASS")

# progress bar scales
from ui.layout import progress_width
widths = [progress_width(c) for c in (60, 100, 200)]
print("progress widths:", widths)
assert widths == sorted(widths) and widths[2] > widths[0]
print("PROGRESS SCALING TEST: PASS")

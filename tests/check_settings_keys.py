"""
tests/check_settings_keys.py
Simulates the Settings screen keyboard flow with a mocked read_key so we can
prove arrow keys navigate and never trigger the old text-prompt bug, and
that LEFT/RIGHT change values and ESC exits.

The navigation path is derived from SETTINGS_SCHEMA so it stays correct if
the schema changes.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8")

import ui.interface as iface
from core import settings as settings_mod

app = iface.FOXFallApp()
schema = iface.FOXFallApp.SETTINGS_SCHEMA
keys = [entry[0] for entry in schema]
theme_idx = keys.index("theme")

# start from defaults, then: go to last (theme), RIGHT (-> next theme),
# then walk back to the top and ESC out.
from ui.themes import THEME_CHOICES
settings_mod.set_key("theme", "fox")
start_theme = "fox"
expected_next = THEME_CHOICES[(THEME_CHOICES.index(start_theme) + 1) % len(THEME_CHOICES)]

SEQUENCE = ["down"] * theme_idx + ["right"] + ["up"] * theme_idx + ["esc"]
captured = []
script = list(SEQUENCE)


def fake_read_key():
    key = script.pop(0) if script else "esc"
    captured.append(key)
    return key


iface.read_key = fake_read_key
app.action_settings()

s = settings_mod.load()
print("keys pressed:", " ".join(captured))
print("theme:", s["theme"], "(expected", expected_next + ")")
assert s["theme"] == expected_next, f"expected {expected_next}, got {s['theme']}"

# second pass: LEFT once -> back to the starting theme
script = ["down"] * theme_idx + ["left"] + ["esc"]
captured.clear()
app.action_settings()
s = settings_mod.load()
assert s["theme"] == start_theme, f"expected {start_theme}, got {s['theme']}"
print("theme cycled back to:", s["theme"])

settings_mod.set_key("theme", "fox")
print("SETTINGS KEYBOARD TEST: PASS (arrow navigation, no stray prompts)")
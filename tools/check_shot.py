"""Inspect the app screenshot: detect broken-image placeholders or foreign UI."""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

path = os.path.join(os.environ.get("TEMP", ""), "foxfall-app.png")
if not os.path.isfile(path):
    # look at the deployed screenshot instead
    path = r"D:\dsh-workflow\projects\FOXFall-website\assets\app-screenshot.png"
img = Image.open(path).convert("RGB")
print("size:", img.size)
# broken-image placeholders render as small icon with border on white/light bg.
# Count near-white pixels (Electron broken image usually on transparent/light)
w, h = img.size
light = sum(1 for y in range(0, h, 4) for x in range(0, w, 4)
            if sum(img.getpixel((x, y))) > 600)
total = (w // 4) * (h // 4)
print(f"near-white pixels: {light}/{total} ({100*light/total:.1f}%)")
# dominant colors
from collections import Counter
c = Counter()
for y in range(0, h, 6):
    for x in range(0, w, 6):
        px = img.getpixel((x, y))
        c[(px[0] // 32, px[1] // 32, px[2] // 32)] += 1
for color, n in c.most_common(6):
    print(f"  rgb~{tuple(v*32 for v in color)}: {n}")
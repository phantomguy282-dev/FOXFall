import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

exe = Image.open(os.path.join(os.environ["TEMP"], "exe-icon3.png")).convert("RGBA")
sup = Image.open("desktop-icon.png").convert("RGBA").resize(exe.size)


def diff(a, b):
    n = total = 0
    for y in range(a.height):
        for x in range(a.width):
            pa, pb = a.getpixel((x, y)), b.getpixel((x, y))
            total += 1
            if abs(pa[0] - pb[0]) + abs(pa[1] - pb[1]) + abs(pa[2] - pb[2]) > 90:
                n += 1
    return n / total


print(f"exe icon {exe.size} vs desktop-icon.png: "
      f"{diff(exe, sup) * 100:.1f}% pixels differ (low = same artwork)")
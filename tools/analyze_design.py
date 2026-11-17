"""Analyze the design-reference screenshots programmatically.

For each image: dimensions, dominant palette, and a coarse ASCII layout map
(brightness blocks) so the structure of the UI can be inferred without
seeing the picture.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")
from collections import Counter

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIR = os.path.join(ROOT, "design-references")
CHARS = " .:-=+*#%@"


def analyze(path: str) -> None:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    print(f"\n===== {os.path.basename(path)}  {w}x{h} =====")

    # dominant colors (quantized)
    small = img.resize((max(1, w // 4), max(1, h // 4)))
    counts = Counter()
    for px in small.get_flattened_data() if hasattr(small, "get_flattened_data") \
            else list(small.getdata()):
        counts[(px[0] // 24 * 24, px[1] // 24 * 24, px[2] // 24 * 24)] += 1
    total = sum(counts.values())
    print("palette:")
    for color, n in counts.most_common(7):
        pct = 100 * n / total
        print(f"  #{color[0]:02X}{color[1]:02X}{color[2]:02X}  {pct:5.1f}%")

    # layout map 100x34
    g = img.convert("L").resize((100, 34))
    print("layout map:")
    for y in range(34):
        row = ""
        for x in range(100):
            v = g.getpixel((x, y))
            row += CHARS[min(9, int(v / 25.6))]
        print(row)


if __name__ == "__main__":
    names = sys.argv[1:] or sorted(os.listdir(DIR))
    for name in names:
        analyze(os.path.join(DIR, name))
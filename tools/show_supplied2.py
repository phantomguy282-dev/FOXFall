"""Detailed inspection of the supplied icons: colors, alpha, content bbox."""
import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image
from collections import Counter

for name in ("desktop-icon.png", "icon.png"):
    img = Image.open(name).convert("RGBA")
    alpha = img.split()[3]
    bbox = alpha.getbbox()
    print(f"--- {name} {img.size} content bbox: {bbox} ---")
    small = img.crop(bbox).resize((48, 24))
    chars = " .:-=+*#%@"
    for y in range(24):
        row = ""
        for x in range(48):
            r, g, b, a = small.getpixel((x, y))
            if a < 100:
                row += " "
                continue
            lum = (r * 0.3 + g * 0.6 + b * 0.1) / 255
            row += chars[min(9, int(lum * 9.99))]
        print(row)
    colors = Counter(
        (p[0] // 32, p[1] // 32, p[2] // 32)
        for p in img.getdata() if p[3] > 100)
    print("top colors:", [(tuple(v * 32 for v in c), n) for c, n in colors.most_common(5)])
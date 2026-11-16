import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

chars = " .:-=+*#%@"
for name in ("desktop-icon.png", "icon.png"):
    img = Image.open(name).convert("RGBA")
    print(f"--- {name} {img.size} ---")
    small = img.resize((40, 20))
    for y in range(20):
        row = ""
        for x in range(40):
            px = small.getpixel((x, y))
            if not isinstance(px, tuple):
                row += " "
                continue
            r, g, b, a = px
            if a < 100:
                row += " "
                continue
            lum = (r * 0.3 + g * 0.6 + b * 0.1) / 255
            row += chars[min(9, int(lum * 9.99))]
        print(row)

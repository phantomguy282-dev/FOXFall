import sys

sys.stdout.reconfigure(encoding="utf-8")
from PIL import Image

img = Image.open("assets/foxfall.ico").convert("RGBA").resize((48, 24))
chars = " .:-=+*#%@"
for y in range(24):
    row = ""
    for x in range(48):
        px = img.getpixel((x, y))
        if not isinstance(px, tuple) or px[3] < 100:
            row += " "
            continue
        lum = (px[0] * 0.3 + px[1] * 0.6 + px[2] * 0.1) / 255
        row += chars[min(9, int(lum * 9.99))]
    print(row)
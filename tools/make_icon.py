"""FOXFall application icon: autumn fox head, orange/cream/dark.

Drawn programmatically with Pillow (head + ears + white muzzle + eyes),
renders crisp at 16..256 px, exported as multi-resolution .ico + PNGs.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

ORANGE = (242, 140, 40, 255)
DEEP = (217, 101, 32, 255)
AMBER = (255, 179, 71, 255)
CREAM = (255, 241, 214, 255)
WHITE = (255, 255, 255, 255)
DARK = (17, 17, 17, 255)
BROWN = (41, 26, 19, 255)
TRANSPARENT = (0, 0, 0, 0)

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "assets")


def draw_fox(size: int) -> Image.Image:
    """Fox head scaled to size (square)."""
    img = Image.new("RGBA", (size, size), TRANSPARENT)
    d = ImageDraw.Draw(img)
    s = size / 256.0  # design space is 256x256

    def P(*pts):
        return [(x * s, y * s) for x, y in pts]

    # left ear (triangle)
    d.polygon(P((30, 20), (92, 62), (34, 108)), fill=ORANGE)
    d.polygon(P((48, 44), (78, 62), (50, 88)), fill=AMBER)   # inner ear
    # right ear
    d.polygon(P((226, 20), (164, 62), (222, 108)), fill=ORANGE)
    d.polygon(P((208, 44), (178, 62), (206, 88)), fill=AMBER)
    # head (big rounded triangle)
    d.polygon(P((30, 70), (226, 70), (128, 238)), fill=ORANGE)
    # cheek shading (deep orange sides)
    d.polygon(P((30, 70), (74, 78), (98, 160), (72, 150)), fill=DEEP)
    d.polygon(P((226, 70), (182, 78), (158, 160), (184, 150)), fill=DEEP)
    # white muzzle (lower center triangle)
    d.polygon(P((78, 130), (178, 130), (128, 238)), fill=CREAM)
    # eyes
    d.ellipse([int(78 * s), int(92 * s), int(108 * s), int(122 * s)], fill=DARK)
    d.ellipse([int(148 * s), int(92 * s), int(178 * s), int(122 * s)], fill=DARK)
    # eye highlights
    d.ellipse([int(86 * s), int(98 * s), int(96 * s), int(108 * s)], fill=WHITE)
    d.ellipse([int(156 * s), int(98 * s), int(166 * s), int(108 * s)], fill=WHITE)
    # nose
    d.polygon(P((112, 196), (144, 196), (128, 220)), fill=DARK)
    return img


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    # master at 1024 for the website hero
    big = draw_fox(1024)
    big.save(os.path.join(OUT_DIR, "fox-1024.png"))
    # ico with all classic sizes
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw_fox(sz) for sz in sizes]
    frames[-1].save(os.path.join(OUT_DIR, "foxfall.ico"),
                    format="ICO", sizes=[(s, s) for s in sizes],
                    append_images=frames[:-1])
    for sz in (16, 32, 48, 64, 128, 256, 512):
        draw_fox(sz).save(os.path.join(OUT_DIR, f"fox-{sz}.png"))
    print("icon assets written to", OUT_DIR)


if __name__ == "__main__":
    main()
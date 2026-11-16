"""
FOXFall 2.1 professional application icon.

Design: rounded-square dark-brown tile with a subtle autumn gradient,
geometric fox head built from layered triangles (orange fur, amber inner
ears, cream muzzle), dark almond eyes with white highlights, dark nose.
Strong silhouette, no text, recognizable from 16 px up.

Outputs: assets/foxfall.ico (16..256), assets/fox-*.png (16..1024).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw, ImageFilter

ORANGE = (242, 140, 40, 255)
DEEP = (217, 101, 32, 255)
AMBER = (255, 179, 71, 255)
CREAM = (255, 241, 214, 255)
WHITE = (255, 255, 255, 255)
DARK = (23, 15, 10, 255)
BROWN = (41, 26, 19, 255)
BROWN_HI = (54, 36, 26, 255)
TRANSPARENT = (0, 0, 0, 0)

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_icon(size: int) -> Image.Image:
    """Render the icon at any size using proportional coordinates."""
    s = size
    img = Image.new("RGBA", (s, s), TRANSPARENT)
    d = ImageDraw.Draw(img)
    u = s / 512.0  # design space 512x512

    # --- tile: rounded square with vertical gradient (dark brown) ---------
    tile = Image.new("RGBA", (s, s), TRANSPARENT)
    td = ImageDraw.Draw(tile)
    td.rounded_rectangle([int(8 * u)] * 2 + [int(s - 8 * u)] * 2,
                         radius=int(96 * u), fill=BROWN)
    # gradient overlay (top warm highlight -> bottom darker)
    grad = Image.new("RGBA", (s, s), TRANSPARENT)
    gd = ImageDraw.Draw(grad)
    for y in range(s):
        t = y / max(1, s - 1)
        c = (int(54 + (33 - 54) * t), int(36 + (24 - 36) * t),
             int(26 + (17 - 26) * t), 255)
        gd.line([(0, y), (s, y)], fill=c)
    # clip gradient to tile shape
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([int(8 * u)] * 2 + [int(s - 8 * u)] * 2,
                                           radius=int(96 * u), fill=255)
    img.paste(Image.composite(grad, img, mask), (0, 0),
              Image.composite(grad, tile, mask).split()[3])
    d = ImageDraw.Draw(img)

    # --- fox head geometry (proportional points) --------------------------
    def P(*pts):
        return [(int(x * u), int(y * u)) for x, y in pts]

    # outer ears (tall triangles with concave tips)
    d.polygon(P((128, 92), (232, 156), (118, 236)), fill=ORANGE)
    d.polygon(P((384, 92), (280, 156), (394, 236)), fill=ORANGE)
    # inner ears
    d.polygon(P((150, 132), (212, 168), (140, 214)), fill=AMBER)
    d.polygon(P((362, 132), (300, 168), (372, 214)), fill=AMBER)
    # head: wide hexagonal face
    d.polygon(P((108, 170), (404, 170), (428, 250), (256, 428), (84, 250)),
              fill=ORANGE)
    # side shading (deep orange)
    d.polygon(P((108, 170), (168, 178), (150, 280), (96, 246)), fill=DEEP)
    d.polygon(P((404, 170), (344, 178), (362, 280), (416, 246)), fill=DEEP)
    # forehead darker wedge (adds depth)
    d.polygon(P((196, 170), (316, 170), (256, 258)), fill=DEEP)
    # cream muzzle
    d.polygon(P((168, 268), (344, 268), (256, 428)), fill=CREAM)
    # cheek fur notches (small dark cuts for texture)
    d.polygon(P((96, 250), (140, 236), (118, 292)), fill=BROWN)
    d.polygon(P((416, 250), (372, 236), (394, 292)), fill=BROWN)
    # eyes: almonds with highlights
    eye_y, eye_h = 218, 34
    for cx in (176, 336):
        d.ellipse([int(cx - 46 * u), int(eye_y * u),
                   int(cx + 46 * u), int((eye_y + eye_h) * u)], fill=DARK)
        d.ellipse([int(cx - 26 * u), int((eye_y + 6) * u),
                   int(cx - 2 * u), int((eye_y + 22) * u)], fill=WHITE)
    # nose
    d.polygon(P((222, 336), (290, 336), (256, 384)), fill=DARK)
    # subtle top shine on head
    shine = Image.new("RGBA", (s, s), TRANSPARENT)
    sd = ImageDraw.Draw(shine)
    sd.ellipse(P((150, 150), (380, 240)), fill=(255, 255, 255, 26))
    shine = shine.filter(ImageFilter.GaussianBlur(int(6 * u)))
    img = Image.alpha_composite(img, shine)
    return img


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    frames = [draw_icon(x) for x in sizes]
    frames[-1].save(os.path.join(OUT, "foxfall.ico"), format="ICO",
                    sizes=[(x, x) for x in sizes],
                    append_images=frames[:-1])
    big = draw_icon(1024)
    big.save(os.path.join(OUT, "fox-1024.png"))
    for x in (16, 24, 32, 48, 64, 128, 256, 512):
        draw_icon(x).save(os.path.join(OUT, f"fox-{x}.png"))
    print("icon assets regenerated:", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
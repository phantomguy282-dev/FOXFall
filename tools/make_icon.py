"""
Build the Windows application icon from the SUPPLIED desktop-icon.png.
Preserves the original PNG untouched; converts it to a proper
multi-resolution ICO (16/24/32/48/64/128/256) using high-quality
Lanczos downsampling. Also refreshes derived app PNGs from icon.png.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def center_on_square(img: Image.Image, canvas: int = 512) -> Image.Image:
    """Place the icon content centered on a transparent square canvas."""
    img = img.convert("RGBA")
    bbox = img.split()[3].getbbox() or (0, 0, img.width, img.height)
    content = img.crop(bbox)
    # scale content to fit with padding
    scale = min((canvas - 2 * int(canvas * 0.08)) / content.width,
                (canvas - 2 * int(canvas * 0.08)) / content.height)
    new_size = (max(1, int(content.width * scale)),
                max(1, int(content.height * scale)))
    content = content.resize(new_size, Image.LANCZOS)
    canvas_img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    canvas_img.paste(content,
                     ((canvas - content.width) // 2,
                      (canvas - content.height) // 2),
                     content)
    return canvas_img


def main() -> None:
    src = os.path.join(ROOT, "desktop-icon.png")
    if not os.path.isfile(src):
        print("ERROR: desktop-icon.png not found at repo root")
        sys.exit(1)

    original = Image.open(src)
    print(f"source: desktop-icon.png {original.size} {original.mode} (preserved)")

    square = center_on_square(original, 512)

    # multi-resolution ICO
    frames = []
    for size in ICO_SIZES:
        resized = square.resize((size, size), Image.LANCZOS)
        # Windows ico needs a hard edge at tiny sizes: sharpen alpha slightly
        frames.append(resized)
    out_ico = os.path.join(ROOT, "assets", "foxfall.ico")
    frames[-1].save(out_ico, format="ICO",
                    sizes=[(x, x) for x in ICO_SIZES],
                    append_images=frames[:-1])
    print(f"written: assets/foxfall.ico ({os.path.getsize(out_ico)} bytes, "
          f"{len(ICO_SIZES)} resolutions)")

    # derived PNGs from the same source (desktop + website use)
    big = square.resize((1024, 1024), Image.LANCZOS)
    big.save(os.path.join(ROOT, "assets", "fox-1024.png"))
    for x in (16, 24, 32, 48, 64, 128, 256, 512):
        square.resize((x, x), Image.LANCZOS).save(
            os.path.join(ROOT, f"assets/fox-{x}.png"))
    print("written: assets/fox-*.png refreshed from desktop-icon.png")


if __name__ == "__main__":
    main()
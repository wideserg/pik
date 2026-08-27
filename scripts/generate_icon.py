"""Generate Pik tray icons from assets/pik-source.png (or procedural fallback).

Master source: assets/pik-source.png — dark squircle, white pin, blue head.
Outputs: assets/pik.png (64), assets/pik-256.png, assets/pik.ico (16/32/48/256).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ASSETS = Path(__file__).resolve().parent.parent / "assets"
SOURCE_PNG = ASSETS / "pik-source.png"
ICO_SIZES = (16, 32, 48, 256)

PIN_BLUE = (74, 158, 255, 255)
PIN_DARK = (30, 90, 180, 255)
PRICE_GOLD = (255, 210, 80, 255)
OUTLINE = (20, 20, 20, 255)


def draw_pik(size: int) -> Image.Image:
    """Procedural fallback when pik-source.png is missing."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64.0

    head_r = int(14 * s)
    cx, cy = int(32 * s), int(22 * s)
    draw.ellipse(
        (cx - head_r, cy - head_r, cx + head_r, cy + head_r),
        fill=PIN_BLUE,
        outline=OUTLINE,
        width=max(1, int(2 * s)),
    )

    tip_x, tip_y = int(32 * s), int(58 * s)
    body = [
        (cx - int(10 * s), cy + int(8 * s)),
        (cx + int(10 * s), cy + int(8 * s)),
        (tip_x, tip_y),
    ]
    draw.polygon(body, fill=PIN_DARK, outline=OUTLINE)

    hole_r = int(5 * s)
    draw.ellipse(
        (cx - hole_r, cy - hole_r, cx + hole_r, cy + hole_r),
        fill=(255, 255, 255, 230),
        outline=OUTLINE,
        width=max(1, int(1 * s)),
    )

    tag_w = int(16 * s)
    tag_h = int(10 * s)
    tx, ty = int(40 * s), int(38 * s)
    draw.rounded_rectangle(
        (tx, ty, tx + tag_w, ty + tag_h),
        radius=int(2 * s),
        fill=PRICE_GOLD,
        outline=OUTLINE,
        width=max(1, int(1 * s)),
    )
    draw.text((tx + int(4 * s), ty + int(1 * s)), "$", fill=OUTLINE)

    return img


def _load_source() -> Image.Image:
    if SOURCE_PNG.exists():
        return Image.open(SOURCE_PNG).convert("RGBA")
    return draw_pik(1024)


def _center_crop(img: Image.Image, fraction: float) -> Image.Image:
    w, h = img.size
    nw, nh = int(w * fraction), int(h * fraction)
    left = (w - nw) // 2
    top = (h - nh) // 2
    return img.crop((left, top, left + nw, top + nh))


def resize_mark(source: Image.Image, size: int) -> Image.Image:
    if size == 16:
        cropped = _center_crop(source, 0.86)
        out = cropped.resize((size, size), Image.Resampling.LANCZOS)
        out = out.filter(ImageFilter.UnsharpMask(radius=0.6, percent=140, threshold=2))
        out = ImageEnhance.Contrast(out).enhance(1.08)
        return out
    return source.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    source = _load_source()
    used_source = SOURCE_PNG.exists()

    png_path = ASSETS / "pik.png"
    resize_mark(source, 64).save(png_path, format="PNG")

    master_path = ASSETS / "pik-256.png"
    resize_mark(source, 256).save(master_path, format="PNG")

    ico_images = [resize_mark(source, s) for s in ICO_SIZES]
    ico_path = ASSETS / "pik.ico"
    ico_images[-1].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=ico_images[:-1],
    )

    src_note = f"from {SOURCE_PNG.name}" if used_source else "procedural fallback"
    print(f"Wrote {ico_path}, {png_path}, {master_path} ({src_note})")


if __name__ == "__main__":
    main()

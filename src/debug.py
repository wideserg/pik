"""Debug captures: logs always; PNG dumps when enabled."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path

from hotkey import hklog

ROOT_DIR = Path(__file__).resolve().parent.parent
DUMP_DIR = ROOT_DIR / "debug-captures"

_enabled = False
_seq = 0


def is_enabled() -> bool:
    if _enabled:
        return True
    return os.environ.get("PIK_DEBUG", "").strip().lower() in ("1", "true", "yes")


def set_enabled(on: bool) -> None:
    global _enabled
    _enabled = on
    if on:
        DUMP_DIR.mkdir(parents=True, exist_ok=True)
    hklog(f"debug captures={'on' if is_enabled() else 'off'} dir={DUMP_DIR}")


def next_stamp() -> str:
    global _seq
    _seq += 1
    return f"{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:-3]}_{_seq:03d}"


def dump_capture(full, crop, ix: int, iy: int, band: tuple[int, int] | None, extra=None) -> str:
    """Save full (cursor + band overlay) and cropped strip. Returns stamp."""
    DUMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = next_stamp()
    try:
        from PIL import ImageDraw

        marked = full.copy()
        draw = ImageDraw.Draw(marked)
        draw.line([(ix - 10, iy), (ix + 10, iy)], fill=(255, 0, 0))
        draw.line([(ix, iy - 10), (ix, iy + 10)], fill=(255, 0, 0))
        if band is not None:
            top, bottom = band
            draw.rectangle(
                [0, top, max(0, full.width - 1), max(top, bottom - 1)],
                outline=(0, 255, 0),
            )
        marked.save(DUMP_DIR / f"{stamp}_full.png")
        crop.save(DUMP_DIR / f"{stamp}_crop.png")
        if extra is not None:
            extra.save(DUMP_DIR / f"{stamp}_ocr.png")
    except Exception as e:
        hklog(f"debug dump failed {e!r}")
        return ""
    hklog(f"debug dump {stamp}_full.png {stamp}_crop.png")
    return stamp

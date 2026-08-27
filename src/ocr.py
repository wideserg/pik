"""Screenshot + Windows.Media.Ocr around the cursor. Fails soft (returns "")."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

try:
    import mss
    from PIL import Image
except ImportError:
    mss = None  # type: ignore
    Image = None  # type: ignore

try:
    from winocr import recognize_pil_sync
except ImportError:
    recognize_pil_sync = None  # type: ignore

CAPTURE_WIDTH_DIP = 420
CAPTURE_HEIGHT_DIP = 70
CURSOR_X_FRACTION = 0.25  # cursor ~centered-left in the strip

MONITOR_DEFAULTTONEAREST = 2
MDT_EFFECTIVE_DPI = 0


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def _get_dpi_scale(x: int, y: int) -> float:
    pt = POINT(x, y)
    monitor = ctypes.windll.user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    dpi_x = wintypes.UINT()
    dpi_y = wintypes.UINT()
    try:
        ctypes.windll.shcore.GetDpiForMonitor(
            monitor, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
        )
        return dpi_x.value / 96.0
    except Exception:
        return 1.0


def _monitor_for_point(sct: "mss.mss", x: int, y: int) -> dict:
    for mon in sct.monitors[1:]:
        if (
            mon["left"] <= x < mon["left"] + mon["width"]
            and mon["top"] <= y < mon["top"] + mon["height"]
        ):
            return mon
    return sct.monitors[1]


def _capture_region(x: int, y: int) -> Image.Image | None:
    if mss is None or Image is None:
        return None

    scale = _get_dpi_scale(x, y)
    width = max(1, int(CAPTURE_WIDTH_DIP * scale))
    height = max(1, int(CAPTURE_HEIGHT_DIP * scale))
    left = x - int(width * CURSOR_X_FRACTION)
    top = y - height // 2

    try:
        with mss.mss() as sct:
            mon = _monitor_for_point(sct, x, y)
            left = max(mon["left"], min(left, mon["left"] + mon["width"] - width))
            top = max(mon["top"], min(top, mon["top"] + mon["height"] - height))
            shot = sct.grab({"left": left, "top": top, "width": width, "height": height})
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        return None


def ocr_at_cursor(x: int | None = None, y: int | None = None) -> str:
    """Capture a horizontal strip around the cursor and OCR it (en-US)."""
    if recognize_pil_sync is None:
        return ""

    if x is None or y is None:
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        x, y = pt.x, pt.y

    img = _capture_region(x, y)
    if img is None:
        return ""

    try:
        result = recognize_pil_sync(img, "en-US")
        text = (result.get("text") if isinstance(result, dict) else str(result)).strip()
        return text
    except Exception:
        return ""

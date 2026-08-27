"""Screenshot + Windows.Media.Ocr around the cursor. Fails soft (returns "")."""

from __future__ import annotations

import ctypes
import time
import traceback
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

from debug import DUMP_DIR, dump_capture, is_enabled
from hotkey import hklog

CAPTURE_WIDTH_DIP = 420
CAPTURE_HEIGHT_DIP = 70
CURSOR_X_FRACTION = 0.25  # cursor ~centered-left in the strip
INK_DELTA = 28
MIN_INK_FRAC = 0.02
BAND_GAP_PX = 2
BAND_PAD_PX = 8
MIN_OCR_HEIGHT = 64
OCR_SCALE = 2

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


def _median_luma(gray: "Image.Image") -> int:
    hist = gray.histogram()
    half = (gray.width * gray.height + 1) // 2
    acc = 0
    for value, count in enumerate(hist):
        acc += count
        if acc >= half:
            return value
    return 0


def _row_ink(gray: "Image.Image", bg: int) -> list[int]:
    pix = gray.load()
    w, h = gray.size
    counts = [0] * h
    for y in range(h):
        n = 0
        for x in range(w):
            if abs(pix[x, y] - bg) >= INK_DELTA:
                n += 1
        counts[y] = n
    return counts


def _bands(counts: list[int], min_ink: int) -> list[tuple[int, int]]:
    raw: list[tuple[int, int]] = []
    start: int | None = None
    for i, n in enumerate(counts):
        if n >= min_ink:
            if start is None:
                start = i
        elif start is not None:
            raw.append((start, i))
            start = None
    if start is not None:
        raw.append((start, len(counts)))

    merged: list[tuple[int, int]] = []
    for a, b in raw:
        if merged and a - merged[-1][1] <= BAND_GAP_PX:
            merged[-1] = (merged[-1][0], b)
        else:
            merged.append((a, b))
    return merged


def _ink_band_at(img: "Image.Image", cy: int) -> tuple[int, int] | None:
    gray = img.convert("L")
    bg = _median_luma(gray)
    min_ink = max(4, int(gray.width * MIN_INK_FRAC))
    bands = _bands(_row_ink(gray, bg), min_ink)
    if not bands:
        return None

    cy = max(0, min(cy, gray.height - 1))
    for a, b in bands:
        if a <= cy < b:
            return a, b
    return min(bands, key=lambda ab: abs((ab[0] + ab[1]) / 2 - cy))


def _crop_line(img: "Image.Image", cy: int) -> tuple["Image.Image", int]:
    band = _ink_band_at(img, cy)
    if band is None:
        return img, cy
    top, bottom = band
    top = max(0, top - BAND_PAD_PX)
    bottom = min(img.height, bottom + BAND_PAD_PX)
    if bottom - top < 8 or bottom - top >= int(img.height * 0.8):
        return img, cy
    return img.crop((0, top, img.width, bottom)), cy - top


def crop_to_cursor_line(img: "Image.Image", cy: int) -> "Image.Image":
    """Keep only the ink band under cy (one list row). No band → original."""
    cropped, _ = _crop_line(img, cy)
    return cropped


def _bg_rgb(img: "Image.Image") -> tuple[int, int, int]:
    rgb = img.convert("RGB")
    w, h = rgb.size
    pix = rgb.load()
    samples: list[tuple[int, int, int]] = []
    step = max(1, w // 40)
    for y in (0, h - 1):
        for x in range(0, w, step):
            samples.append(pix[x, y])
    if not samples:
        return (20, 20, 20)

    def med(xs: list[int]) -> int:
        xs = sorted(xs)
        return xs[len(xs) // 2]

    rs, gs, bs = zip(*samples)
    return med(list(rs)), med(list(gs)), med(list(bs))


def prepare_for_ocr(
    img: "Image.Image",
    cy: int,
    min_h: int = MIN_OCR_HEIGHT,
    scale: int = OCR_SCALE,
) -> tuple["Image.Image", int]:
    """Windows.Media.Ocr returns empty on ~26px-tall UI strips. Pad + upscale."""
    rgb = img.convert("RGB")
    w, h = rgb.size
    if h < min_h:
        pad = min_h - h
        top = pad // 2
        canvas = Image.new("RGB", (w, min_h), _bg_rgb(rgb))
        canvas.paste(rgb, (0, top))
        rgb = canvas
        cy += top
    if scale > 1:
        rgb = rgb.resize((rgb.width * scale, rgb.height * scale), Image.Resampling.LANCZOS)
        cy *= scale
    return rgb, int(cy)


def _line_span_y(line: dict) -> tuple[float, float] | None:
    ys: list[tuple[float, float]] = []
    for word in line.get("words") or []:
        rect = word.get("bounding_rect") or {}
        y = rect.get("y")
        h = rect.get("height")
        if y is None:
            continue
        top = float(y)
        bottom = top + float(h or 0)
        ys.append((top, bottom))
    if not ys:
        return None
    return min(t for t, _ in ys), max(b for _, b in ys)


def line_text_at(result: dict, cy: int) -> str:
    """Pick the OCR line whose box covers cy (else nearest). Not the joined blob."""
    lines = result.get("lines") or []
    if not lines:
        return str(result.get("text") or "").strip()

    covering: list[tuple[float, dict]] = []
    nearest: tuple[float, dict] | None = None
    for line in lines:
        span = _line_span_y(line)
        if span is None:
            continue
        top, bottom = span
        if top <= cy <= bottom:
            covering.append((bottom - top, line))
            continue
        mid = (top + bottom) / 2
        dist = abs(mid - cy)
        if nearest is None or dist < nearest[0]:
            nearest = (dist, line)

    if covering:
        line = min(covering, key=lambda item: item[0])[1]
        return str(line.get("text") or "").strip()
    if nearest is not None:
        return str(nearest[1].get("text") or "").strip()
    return str(result.get("text") or "").strip()


def _mean_luma(img: "Image.Image") -> float:
    try:
        from PIL import ImageStat

        return float(ImageStat.Stat(img.convert("L")).mean[0])
    except Exception:
        return -1.0


def _capture_region(x: int, y: int) -> tuple["Image.Image", int, int] | None:
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
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            return img, x - left, y - top
    except Exception as e:
        hklog(f"ocr mss grab fail {type(e).__name__}: {e}")
        return None


def _recognize(img: "Image.Image", cy: int) -> tuple[str, int, str]:
    """Return (picked text, line count, raw text)."""
    result = recognize_pil_sync(img, "en-US")
    if isinstance(result, dict):
        n_lines = len(result.get("lines") or [])
        raw = str(result.get("text") or "")
        text = line_text_at(result, cy)
        return text, n_lines, raw
    raw = str(result)
    return raw.strip(), -1, raw


def ocr_at_cursor(x: int | None = None, y: int | None = None) -> str:
    """Capture a strip around the cursor, crop to that line, OCR it (en-US)."""
    t0 = time.perf_counter()
    if recognize_pil_sync is None:
        hklog("ocr skip: winocr not importable")
        return ""

    if x is None or y is None:
        pt = POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
        x, y = pt.x, pt.y

    captured = _capture_region(x, y)
    if captured is None:
        ms = (time.perf_counter() - t0) * 1000
        hklog(f"ocr capture failed @({x},{y}) {ms:.0f}ms")
        return ""
    full, ix, iy = captured
    band = _ink_band_at(full, iy)
    crop, cy = _crop_line(full, iy)
    luma = _mean_luma(full)
    prepared, pcy = prepare_for_ocr(crop, cy)
    stamp = ""
    if is_enabled():
        stamp = dump_capture(full, crop, ix, iy, band, extra=prepared)

    try:
        text, n_lines, raw = _recognize(prepared, pcy)
        src = "crop"
        if not text:
            prepared_full, fcy = prepare_for_ocr(full, iy)
            text, n_lines, raw = _recognize(prepared_full, fcy)
            src = "full-fallback"
            if is_enabled() and stamp:
                prepared_full.save(DUMP_DIR / f"{stamp}_ocr_full.png")
        ms = (time.perf_counter() - t0) * 1000
        black = " BLACK" if 0 <= luma < 12 else ""
        hklog(
            f"ocr @({x},{y}) src={src} full={full.size} crop={crop.size} "
            f"prep={prepared.size} cy={pcy} luma={luma:.0f}{black} band={band} "
            f"lines={n_lines} raw={raw[:80]!r} pick={text!r} {ms:.0f}ms dump={stamp or '-'}"
        )
        return text
    except Exception as e:
        ms = (time.perf_counter() - t0) * 1000
        hklog(f"ocr fail {type(e).__name__}: {e} {ms:.0f}ms dump={stamp or '-'}")
        if is_enabled():
            hklog(traceback.format_exc())
        return ""

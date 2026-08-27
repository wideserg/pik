"""Read UI Automation text under the mouse cursor, with OCR fallback."""

import ctypes
import re
from ctypes import wintypes

try:
    import uiautomation as auto
except ImportError:
    auto = None  # type: ignore

from ocr import ocr_at_cursor
from hotkey import hklog

_GENERIC_RE = re.compile(
    r"^(?:chrome[_\s]?widgetwin[_\s]?\d*|cursor|pane|window|list|tree)$",
    re.I,
)
_GENERIC_JUNK = re.compile(
    r"^(?:chrome widgetwin \d+|cursor|pane|window|list|tree)"
    r"(?: (?:chrome widgetwin \d+|cursor|pane|window|list|tree|\d+))*$",
    re.I,
)
_FAMILY_RE = re.compile(
    r"\b(gpt|grok|claude|gemini|composer|glm|kimi|sonnet|opus|haiku)\b",
    re.I,
)
# Cursor/VS Code chrome. ControlFromPoint often punches through the model
# picker onto the editor behind it ("Editor Group 1 (empty)"); a digit
# made that look "useful" and skipped OCR. Second hover usually works
# because the list item's UIA tree has caught up.
_WORKBENCH_RE = re.compile(
    r"\beditor group\b|\bside bar\b|\bactivity bar\b|\bstatus bar\b"
    r"|\bauxiliary bar\b|\btitle bar\b|\bmenu bar\b",
    re.I,
)


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos() -> tuple[int, int]:
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def uia_is_useful(parts: list[str]) -> bool:
    if not parts:
        return False

    joined = " ".join(str(p).strip() for p in parts if p and str(p).strip()).strip()
    if not joined:
        return False

    normalized = re.sub(r"[\s_]+", " ", joined).strip()
    if _GENERIC_JUNK.match(normalized):
        return False

    tokens = [t for t in re.split(r"[\s_]+", joined) if t]
    if tokens and all(_GENERIC_RE.match(t) for t in tokens):
        return False

    has_family = bool(_FAMILY_RE.search(joined))
    if _WORKBENCH_RE.search(normalized) and not has_family:
        return False

    has_digit = bool(re.search(r"\d", joined))
    return has_digit or has_family


def _safe_str(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def _control_value(ctrl) -> str | None:
    try:
        vp = ctrl.GetValuePattern()
        if vp:
            return _safe_str(vp.Value)
    except Exception:
        pass
    try:
        lp = ctrl.GetLegacyIAccessiblePattern()
        if lp:
            return _safe_str(lp.Value)
    except Exception:
        pass
    return None


def _read_uia_parts(x: int, y: int) -> list[str]:
    parts: list[str] = []

    if auto is None:
        return parts

    try:
        ctrl = auto.ControlFromPoint(x, y)
    except Exception as e:
        hklog(f"uia ControlFromPoint fail @({x},{y}) {type(e).__name__}: {e}")
        return parts

    if not ctrl:
        hklog(f"uia ControlFromPoint None @({x},{y})")
        return parts

    try:
        hklog(
            f"uia hit @({x},{y}) type={ctrl.ControlTypeName!s} "
            f"class={ctrl.ClassName!r} name={ctrl.Name!r} id={ctrl.AutomationId!r}"
        )
    except Exception as e:
        hklog(f"uia hit @({x},{y}) meta fail {e!r}")

    def add(text: str | None):
        if text:
            parts.append(text)

    add(_safe_str(ctrl.Name))
    add(_safe_str(ctrl.AutomationId))
    add(_safe_str(ctrl.HelpText))
    add(_control_value(ctrl))

    parent = ctrl.GetParentControl()
    for _ in range(3):
        if not parent:
            break
        add(_safe_str(parent.Name))
        parent = parent.GetParentControl()

    return parts


def read_text_at_cursor() -> tuple[list[str], tuple[int, int], bool]:
    """Return (haystack parts, cursor pos, used_ocr)."""
    x, y = get_cursor_pos()
    parts = _read_uia_parts(x, y)
    useful = uia_is_useful(parts)
    hklog(f"uia useful={useful} parts={parts!r}")

    if useful:
        return parts, (x, y), False

    ocr_text = ocr_at_cursor(x, y)
    if ocr_text:
        return [ocr_text], (x, y), True

    hklog("ocr empty → miss")
    return parts, (x, y), False

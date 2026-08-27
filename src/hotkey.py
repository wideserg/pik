"""Layout-independent Alt+P via WH_KEYBOARD_LL (physical scan code)."""

import atexit
import ctypes
import queue
import sys
import threading
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012

LLKHF_EXTENDED = 0x01
LLKHF_INJECTED = 0x10
LLKHF_ALTDOWN = 0x20
LLKHF_UP = 0x80

VK_MENU = 0x12
VK_CONTROL = 0x11
VK_LCONTROL = 0xA2
VK_RCONTROL = 0xA3
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LWIN = 0x5B
VK_RWIN = 0x5C
VK_P = 0x50

# US QWERTY physical P key (layout-independent). RU: З.
SCAN_CODE_P = 0x19

LRESULT = (
    ctypes.c_longlong if ctypes.sizeof(ctypes.c_void_p) == 8 else ctypes.c_long
)

LOG_PATH = Path(__file__).resolve().parent.parent / "pik-hotkey.log"

_hook: int | None = None
_hook_thread_id: int | None = None
_events: queue.Queue | None = None
_atexit_registered = False
_p_combo_active = False
_ready = threading.Event()
_log_lock = threading.Lock()


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_ulonglong),
    ]


LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

user32.SetWindowsHookExW.argtypes = (
    ctypes.c_int,
    LowLevelKeyboardProc,
    wintypes.HINSTANCE,
    wintypes.DWORD,
)
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.UnhookWindowsHookEx.argtypes = (wintypes.HHOOK,)
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.CallNextHookEx.argtypes = (
    wintypes.HHOOK,
    ctypes.c_int,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
user32.CallNextHookEx.restype = LRESULT
user32.GetAsyncKeyState.argtypes = (ctypes.c_int,)
user32.GetAsyncKeyState.restype = wintypes.SHORT
user32.GetMessageW.argtypes = (
    ctypes.POINTER(wintypes.MSG),
    wintypes.HWND,
    ctypes.c_uint,
    ctypes.c_uint,
)
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = (
    wintypes.DWORD,
    ctypes.c_uint,
    wintypes.WPARAM,
    wintypes.LPARAM,
)
user32.PostThreadMessageW.restype = wintypes.BOOL
kernel32.GetCurrentThreadId.restype = wintypes.DWORD
kernel32.GetCurrentThreadId.argtypes = ()


def hklog(msg: str) -> None:
    line = f"{datetime.now().strftime('%H:%M:%S.%f')[:-3]} [pik-hotkey] {msg}"
    with _log_lock:
        try:
            with LOG_PATH.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
                f.flush()
        except OSError:
            pass
        try:
            if sys.stdout is not None:
                enc = getattr(sys.stdout, "encoding", None) or "utf-8"
                text = line.encode(enc, errors="replace").decode(enc, errors="replace")
                print(text, flush=True)
        except (AttributeError, OSError, UnicodeEncodeError):
            pass


def _physical_scan(kb: KBDLLHOOKSTRUCT) -> int:
    """Hardware scan from KBDLLHOOKSTRUCT (ignore vkCode for matching)."""
    sc = kb.scanCode
    low = sc & 0xFF
    if low:
        return low
    high = (sc >> 16) & 0xFF
    if high:
        return high
    return 0


def _is_key_up(wp: int, kb: KBDLLHOOKSTRUCT) -> bool:
    return bool(wp & 0x01) or bool(kb.flags & LLKHF_UP)


def _key_down(vk: int) -> bool:
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def _flags_bits(flags: int) -> str:
    parts: list[str] = []
    if flags & LLKHF_EXTENDED:
        parts.append("EXTENDED")
    if flags & LLKHF_INJECTED:
        parts.append("INJECTED")
    if flags & LLKHF_ALTDOWN:
        parts.append("ALTDOWN")
    if flags & LLKHF_UP:
        parts.append("UP")
    return "|".join(parts) or "-"


def _is_p_key(kb: KBDLLHOOKSTRUCT, scan: int) -> bool:
    return scan == SCAN_CODE_P or kb.vkCode == VK_P


def _pass(n_code: int, w_param, l_param) -> LRESULT:
    return user32.CallNextHookEx(_hook, n_code, w_param, l_param)


def _hook_callback_inner(
    n_code: int, w_param: wintypes.WPARAM, l_param: wintypes.LPARAM
) -> LRESULT:
    global _p_combo_active

    if n_code < 0:
        return _pass(n_code, w_param, l_param)

    kb = ctypes.cast(l_param, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
    wp = int(w_param)
    scan_raw = int(kb.scanCode)
    scan = _physical_scan(kb)
    flags = int(kb.flags)
    vk = int(kb.vkCode)
    is_up = _is_key_up(wp, kb)
    is_keydown = wp in (WM_KEYDOWN, WM_SYSKEYDOWN) and not is_up
    alt_flag = bool(flags & LLKHF_ALTDOWN)
    alt_async = _key_down(VK_MENU)
    alt_down = alt_flag or alt_async
    lmenu_down = _key_down(VK_LMENU)
    rmenu_down = _key_down(VK_RMENU)
    lctrl_down = _key_down(VK_LCONTROL)
    rctrl_down = _key_down(VK_RCONTROL)
    ctrl_down = _key_down(VK_CONTROL)
    # AltGr (RU Right Alt) = VK_RMENU + phantom Ctrl. Ignore Ctrl while RMENU is down.
    # Real Ctrl+Alt (Left Alt): LCONTROL/CONTROL without RMENU.
    real_ctrl = ctrl_down and not rmenu_down
    win_down = _key_down(VK_LWIN) or _key_down(VK_RWIN)
    is_p = _is_p_key(kb, scan)

    kbd = (
        f"wParam=0x{wp:04X} vk=0x{vk:02X} scan=0x{scan_raw:X} scan8=0x{scan:02X} "
        f"flags=0x{flags:02X} {_flags_bits(flags)} "
        f"alt(flag={int(alt_flag)} async={int(alt_async)}) "
        f"ctrl={int(ctrl_down)} lctrl={int(lctrl_down)} rctrl={int(rctrl_down)} "
        f"lmenu={int(lmenu_down)} rmenu={int(rmenu_down)} win={int(win_down)}"
    )

    if alt_down and is_keydown and not is_p:
        hklog(f"alt-held down {kbd} -> next")
    elif alt_down and is_keydown:
        hklog(f"alt-held down {kbd}")

    skip = None
    if is_p:
        if is_up:
            skip = "keyup"
            _p_combo_active = False
        elif not is_keydown:
            skip = "not-keydown"
        elif not alt_down:
            skip = "no-alt"
        elif real_ctrl:
            skip = "ctrl"
        elif win_down:
            skip = "win"
        elif _p_combo_active:
            skip = "repeat"

    interesting = scan == SCAN_CODE_P or (is_p and is_keydown)
    if interesting:
        if skip:
            hklog(f"scan/P skip {skip} {kbd} -> next")
        else:
            try:
                if _events is None:
                    hklog(f"scan/P FIRE but _events is None {kbd} -> eat")
                else:
                    _events.put(True)
                    hklog(f"scan/P FIRE _events.put {kbd} -> eat")
            except Exception as e:
                hklog(f"scan/P FIRE put failed {e!r} {kbd} -> eat")
            _p_combo_active = True
            return 1

    return _pass(n_code, w_param, l_param)


def _hook_callback(
    n_code: int, w_param: wintypes.WPARAM, l_param: wintypes.LPARAM
) -> LRESULT:
    try:
        return _hook_callback_inner(n_code, w_param, l_param)
    except Exception as e:
        hklog(f"callback exception: {e!r}")
        try:
            return user32.CallNextHookEx(_hook, n_code, w_param, l_param)
        except Exception:
            return 0


# Module-level ref prevents GC of the ctypes callback (hook dies silently otherwise).
_hook_proc_ref: LowLevelKeyboardProc = LowLevelKeyboardProc(_hook_callback)


def unhook() -> None:
    global _hook, _hook_thread_id
    if _hook is not None:
        ok = bool(user32.UnhookWindowsHookEx(_hook))
        hklog(f"unhook handle={_hook} ok={ok}")
        _hook = None
    else:
        hklog("unhook skipped (handle=NULL)")
    if _hook_thread_id is not None:
        user32.PostThreadMessageW(_hook_thread_id, WM_QUIT, 0, 0)
        _hook_thread_id = None


def _hook_thread_main(events: queue.Queue) -> None:
    global _hook, _hook_thread_id, _events

    _events = events
    _hook_thread_id = int(kernel32.GetCurrentThreadId())
    hklog(f"hook thread start tid={_hook_thread_id} events={events is not None}")

    # WH_KEYBOARD_LL: hMod MUST be NULL — callback lives in this process, not a DLL.
    h = user32.SetWindowsHookExW(WH_KEYBOARD_LL, _hook_proc_ref, None, 0)
    err = ctypes.get_last_error()
    _hook = int(h) if h else None
    if not _hook:
        hklog(f"SetWindowsHookEx FAILED handle=NULL last_error={err}")
        _ready.set()
        return

    hklog(f"hook installed handle={_hook} last_error={err}")
    _ready.set()

    try:
        msg = wintypes.MSG()
        while True:
            r = int(user32.GetMessageW(ctypes.byref(msg), None, 0, 0))
            if r == 0:
                break
            if r == -1:
                hklog(f"GetMessageW failed last_error={ctypes.get_last_error()}")
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        hklog("message pump exit")
    except Exception as e:
        hklog(f"message pump exception: {e!r}")


def start_hotkey_listener(events: queue.Queue) -> threading.Thread:
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(unhook)
        _atexit_registered = True

    _ready.clear()
    thread = threading.Thread(
        target=_hook_thread_main, args=(events,), daemon=True, name="pik-hotkey"
    )
    thread.start()
    if not _ready.wait(timeout=2.0):
        hklog("hook thread did not signal ready within 2s")
    elif _hook is None:
        hklog("hook thread ready but handle is NULL")
    return thread

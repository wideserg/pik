"""Cursor model price overlay — hotkey loop + price cards + Pik launch UX."""

import atexit
import queue
import sys
import threading
from pathlib import Path

import ctypes
from ctypes import wintypes

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from match import format_card_fields, match_model  # noqa: E402
from overlay import CardManager  # noqa: E402
from prices import ensure_daily_refresh, load_state, save_state  # noqa: E402
from read_ui import read_text_at_cursor  # noqa: E402
from theme import set_theme  # noqa: E402
from tray import TrayIcon  # noqa: E402
from welcome import WelcomeWindow  # noqa: E402

MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
VK_P = 0x50
HOTKEY_ID = 1
WM_HOTKEY = 0x0312

user32 = ctypes.windll.user32


def _unregister_hotkey():
    user32.UnregisterHotKey(None, HOTKEY_ID)


def hotkey_listener(events: queue.Queue):
    if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_ALT, VK_P):
        raise RuntimeError("Failed to register Ctrl+Alt+P hotkey (already in use?)")
    atexit.register(_unregister_hotkey)

    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
            events.put(True)
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


def main():
    state = load_state()
    theme_name = state.get("theme", "dark")
    set_theme(theme_name)

    refresh = ensure_daily_refresh(state)

    manager = CardManager()
    welcome: WelcomeWindow | None = None
    tray: TrayIcon | None = None

    def on_theme_change(name: str) -> None:
        nonlocal theme_name
        theme_name = name
        state["theme"] = name
        save_state(state)

    def show_welcome() -> None:
        nonlocal welcome, theme_name
        theme_name = state.get("theme", "dark")
        set_theme(theme_name)
        if welcome is None or not welcome.exists:
            welcome = WelcomeWindow(manager.root, refresh, theme_name, on_theme_change)
        welcome.show()

    show_welcome()

    def quit_app() -> None:
        if tray is not None:
            tray.stop()
        manager.root.destroy()

    tray = TrayIcon(manager.root, on_open=show_welcome, on_quit=quit_app)
    tray.start()

    models = refresh.models
    events: queue.Queue = queue.Queue()

    def handle_hotkey():
        parts, (x, y), used_ocr = read_text_at_cursor()
        model, haystack = match_model(parts, models)

        if model:
            fields = format_card_fields(model)
            if used_ocr:
                fields["hint"] = "ocr"
        else:
            snippet = haystack.strip() or "no UI text"
            if len(snippet) > 100:
                snippet = snippet[:97] + "..."
            fields = {
                "title": snippet,
                "meta": "",
                "prices": "no price",
                "cache": None,
                "hint": None,
            }

        manager.show(x, y, fields)

    def poll_hotkey():
        try:
            while True:
                events.get_nowait()
                handle_hotkey()
        except queue.Empty:
            pass
        manager.root.after(50, poll_hotkey)

    thread = threading.Thread(target=hotkey_listener, args=(events,), daemon=True)
    thread.start()
    poll_hotkey()

    if sys.stdout is not None:
        try:
            print("Pik running — Ctrl+Alt+P for prices, tray to open/quit")
        except OSError:
            pass
    manager.run()


if __name__ == "__main__":
    main()

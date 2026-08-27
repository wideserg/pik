"""Cursor model price overlay — hotkey loop + price cards + Pik launch UX."""

import queue
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
sys.path.insert(0, str(SRC_DIR))

from hotkey import hklog, start_hotkey_listener, unhook  # noqa: E402
from match import format_card_fields, match_model  # noqa: E402
from overlay import CardManager  # noqa: E402
from prices import ensure_daily_refresh, load_state, save_state  # noqa: E402
from read_ui import read_text_at_cursor  # noqa: E402
from debug import DUMP_DIR, is_enabled, set_enabled  # noqa: E402
from theme import set_theme  # noqa: E402
from tray import TrayIcon  # noqa: E402
from welcome import WelcomeWindow  # noqa: E402

def main():
    argv = sys.argv[1:]
    if "--debug" in argv:
        set_enabled(True)
    elif is_enabled():
        set_enabled(True)
    hklog(f"Pik start debug={is_enabled()} dumps={DUMP_DIR}")
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
        unhook()
        if tray is not None:
            tray.stop()
        manager.root.destroy()

    tray = TrayIcon(manager.root, on_open=show_welcome, on_quit=quit_app)
    tray.start()

    models = refresh.models
    events: queue.Queue = queue.Queue()

    def handle_hotkey():
        hklog("hotkey fired, reading UI…")
        parts, (x, y), used_ocr = read_text_at_cursor()
        model, haystack = match_model(parts, models)
        snippet = (haystack.strip() or "no UI text")
        if len(snippet) > 100:
            snippet = snippet[:97] + "..."
        src = "ocr" if used_ocr else "uia"

        if model:
            hklog(f"match {model.get('name', '?')!r} via {src} haystack={snippet!r}")
            fields = format_card_fields(model)
            if used_ocr:
                fields["hint"] = "ocr"
        else:
            hklog(f"miss via {src} haystack={snippet!r}")
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

    start_hotkey_listener(events)
    poll_hotkey()

    if sys.stdout is not None:
        try:
            print("Pik running — Alt+P for prices, tray to open/quit")
        except OSError:
            pass
    manager.run()


if __name__ == "__main__":
    main()

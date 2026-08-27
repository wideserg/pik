"""System tray icon for Pik."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import pystray
from PIL import Image

ROOT_DIR = Path(__file__).resolve().parent.parent
ICON_ICO = ROOT_DIR / "assets" / "pik.ico"
ICON_PNG = ROOT_DIR / "assets" / "pik.png"


def _load_icon_image() -> Image.Image:
    for path in (ICON_PNG, ICON_ICO):
        if path.exists():
            return Image.open(path).convert("RGBA")
    raise FileNotFoundError(f"Tray icon not found: {ICON_PNG} or {ICON_ICO}")


class TrayIcon:
    def __init__(
        self,
        tk_root,
        on_open: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._tk_root = tk_root
        self._on_open = on_open
        self._on_quit = on_quit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def _marshal(self, fn: Callable[[], None]) -> None:
        self._tk_root.after(0, fn)

    def _menu_open(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._marshal(self._on_open)

    def _menu_quit(self, _icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        self._marshal(self._on_quit)

    def _default_action(self, icon: pystray.Icon) -> None:
        self._marshal(self._on_open)

    def start(self) -> None:
        image = _load_icon_image()
        menu = pystray.Menu(
            pystray.MenuItem("Open", self._menu_open, default=True),
            pystray.MenuItem("Quit", self._menu_quit),
        )
        self._icon = pystray.Icon("Pik", image, "Pik", menu, on_activate=self._default_action)
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon is not None:
            self._icon.stop()

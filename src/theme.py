"""Shared light/dark palettes for Pik UI."""

from typing import Literal

ThemeName = Literal["dark", "light"]

_PALETTES: dict[ThemeName, dict[str, str]] = {
    "dark": {
        "bg": "#1e1e1e",
        "fg": "#f0f0f0",
        "fg_dim": "#cccccc",
        "fg_muted": "#666666",
        "accent": "#4a9eff",
        "border": "#333333",
        "btn_bg": "#2a2a2a",
        "btn_active": "#3a3a3a",
        "chip_bg": "#2a2a2a",
        "chip_border": "#444444",
        "panel_bg": "#252525",
        "panel_accent": "#305078",
    },
    "light": {
        "bg": "#f7f7f7",
        "fg": "#1a1a1a",
        "fg_dim": "#444444",
        "fg_muted": "#888888",
        "accent": "#0066cc",
        "border": "#cccccc",
        "btn_bg": "#e8e8e8",
        "btn_active": "#d0d0d0",
        "chip_bg": "#eeeeee",
        "chip_border": "#d0d0d0",
        "panel_bg": "#efefef",
        "panel_accent": "#94bde5",
    },
}

_current: ThemeName = "dark"


def get_theme() -> ThemeName:
    return _current


def set_theme(name: str) -> ThemeName:
    global _current
    _current = "light" if name == "light" else "dark"
    return _current


def get_palette(name: str | None = None) -> dict[str, str]:
    theme = _current if name is None else ("light" if name == "light" else "dark")
    return _PALETTES[theme]

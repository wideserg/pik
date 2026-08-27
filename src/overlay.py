"""Interactive price card overlay — hover-pause, pin, drag."""

import ctypes
import tkinter as tk
from ctypes import wintypes
from typing import Any

from theme import get_palette

GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
SM_XVIRTUALSCREEN = 76
SM_YVIRTUALSCREEN = 77
SM_CXVIRTUALSCREEN = 78
SM_CYVIRTUALSCREEN = 79
MONITOR_DEFAULTTONEAREST = 2

FONT_TITLE = ("Segoe UI", 10, "bold")
FONT_BODY = ("Segoe UI", 9)
FONT_HINT = ("Segoe UI", 7)
MAX_WIDTH = 300
CARD_PAD = 10
HIDE_MS = 4000
TICK_MS = 75
MAX_CARDS = 8
PROGRESS_H = 3
CURSOR_OFFSET = (16, 20)


def _hwnd(toplevel: tk.Toplevel) -> int:
    toplevel.update_idletasks()
    hwnd = int(toplevel.winfo_id())
    parent = ctypes.windll.user32.GetParent(hwnd)
    return parent or hwnd


def _apply_win_styles(toplevel: tk.Toplevel) -> None:
    hwnd = _hwnd(toplevel)
    user32 = ctypes.windll.user32
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    style |= WS_EX_TOOLWINDOW
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)


class _RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class _MONITORINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_ulong),
        ("rcMonitor", _RECT),
        ("rcWork", _RECT),
        ("dwFlags", ctypes.c_ulong),
    ]


def _work_area_at(x: int, y: int) -> tuple[int, int, int, int]:
    user32 = ctypes.windll.user32
    pt = wintypes.POINT(x, y)
    monitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
    if monitor:
        info = _MONITORINFO()
        info.cbSize = ctypes.sizeof(_MONITORINFO)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            work = info.rcWork
            return work.left, work.top, work.right, work.bottom
    left = user32.GetSystemMetrics(SM_XVIRTUALSCREEN)
    top = user32.GetSystemMetrics(SM_YVIRTUALSCREEN)
    width = user32.GetSystemMetrics(SM_CXVIRTUALSCREEN)
    height = user32.GetSystemMetrics(SM_CYVIRTUALSCREEN)
    return left, top, left + width, top + height


def _clamp_to_work_area(
    x: int, y: int, width: int, height: int, work: tuple[int, int, int, int]
) -> tuple[int, int]:
    left, top, right, bottom = work
    work_w = right - left
    work_h = bottom - top
    if width >= work_w:
        x = left
    else:
        x = min(max(x, left), right - width)
    if height >= work_h:
        y = top
    else:
        y = min(max(y, top), bottom - height)
    return x, y


def _pointer_over(widget: tk.Misc) -> bool:
    x, y = widget.winfo_pointerxy()
    w = widget.winfo_containing(x, y)
    while w is not None:
        if w == widget:
            return True
        w = w.master
    return False


class PriceCard:
    def __init__(self, manager: "CardManager", fields: dict[str, Any]):
        self.manager = manager
        self.fields = fields
        self.pinned = False
        self._hovered = False
        self._remaining_ms = HIDE_MS
        self._tick_id: str | None = None
        self._drag_offset: tuple[int, int] | None = None

        p = get_palette()
        bg = p["bg"]
        fg = p["fg"]
        fg_dim = p["fg_dim"]
        fg_muted = p["fg_muted"]
        accent = p["accent"]
        border = p["border"]

        self.win = tk.Toplevel(manager.root)
        self.win.withdraw()
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.configure(bg=border)

        outer = tk.Frame(self.win, bg=border, padx=1, pady=1)
        outer.pack(fill=tk.BOTH, expand=True)

        self._body = tk.Frame(outer, bg=bg, padx=CARD_PAD, pady=CARD_PAD)
        self._body.pack(fill=tk.BOTH, expand=True)

        header = tk.Frame(self._body, bg=bg)
        header.pack(fill=tk.X, anchor="n")

        wrap = MAX_WIDTH - 2 * CARD_PAD - 52
        self._title = tk.Label(
            header,
            text=fields.get("title", ""),
            bg=bg,
            fg=fg,
            font=FONT_TITLE,
            justify=tk.LEFT,
            anchor="w",
            wraplength=wrap,
        )
        self._title.pack(side=tk.LEFT, fill=tk.X, expand=True)

        btn_frame = tk.Frame(header, bg=bg)
        btn_frame.pack(side=tk.RIGHT)

        self._pin_btn = tk.Label(
            btn_frame,
            text="📌",
            bg=bg,
            fg=fg_dim,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self._pin_btn.pack(side=tk.LEFT, padx=(4, 0))
        self._pin_btn.bind("<Button-1>", self._toggle_pin)

        self._close_btn = tk.Label(
            btn_frame,
            text="×",
            bg=bg,
            fg=fg_dim,
            font=("Segoe UI", 11),
            cursor="hand2",
        )
        self._close_btn.pack(side=tk.LEFT, padx=(2, 0))
        self._close_btn.bind("<Button-1>", lambda _e: self.destroy())

        self._labels: list[tk.Label] = []
        for key, fg_color, font in (
            ("meta", fg_dim, FONT_BODY),
            ("prices", fg, FONT_BODY),
            ("cache", fg_dim, FONT_BODY),
        ):
            text = fields.get(key) or ""
            if not text:
                continue
            lbl = tk.Label(
                self._body,
                text=text,
                bg=bg,
                fg=fg_color,
                font=font,
                justify=tk.LEFT,
                anchor="w",
                wraplength=MAX_WIDTH - 2 * CARD_PAD,
            )
            lbl.pack(anchor="w", pady=(2, 0))
            self._labels.append(lbl)

        hint = fields.get("hint")
        if hint:
            lbl = tk.Label(
                self._body,
                text=hint,
                bg=bg,
                fg=fg_muted,
                font=FONT_HINT,
                justify=tk.LEFT,
                anchor="w",
            )
            lbl.pack(anchor="w", pady=(4, 0))
            self._labels.append(lbl)

        self._progress = tk.Canvas(
            self._body,
            width=1,
            height=PROGRESS_H,
            bg=bg,
            highlightthickness=0,
            bd=0,
        )
        self._progress.pack(fill=tk.X, pady=(6, 0))
        self._progress_bar = self._progress.create_rectangle(
            0, 0, 0, PROGRESS_H, fill=accent, outline=""
        )
        self._accent = accent
        self._fg_dim = fg_dim

        self._title.bind("<Button-1>", self._drag_start)
        self._title.bind("<B1-Motion>", self._drag_motion)
        self._title.config(cursor="fleur")

        self._bind_hover_recursive(outer)
        self.win.protocol("WM_DELETE_WINDOW", self.destroy)

    def _bind_hover_recursive(self, widget: tk.Misc) -> None:
        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        for child in widget.winfo_children():
            self._bind_hover_recursive(child)

    def _on_enter(self, _event=None) -> None:
        self._hovered = True

    def _on_leave(self, _event=None) -> None:
        self.win.after_idle(self._sync_hover)

    def _sync_hover(self) -> None:
        if self.win.winfo_exists():
            self._hovered = _pointer_over(self.win)

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_offset = (event.x_root - self.win.winfo_x(), event.y_root - self.win.winfo_y())

    def _drag_motion(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        ox, oy = self._drag_offset
        self.win.geometry(f"+{event.x_root - ox}+{event.y_root - oy}")

    def _toggle_pin(self, _event=None) -> None:
        self.pinned = not self.pinned
        if self.pinned:
            self._pin_btn.config(fg=self._accent)
            self._progress.pack_forget()
        else:
            self._pin_btn.config(fg=self._fg_dim)
            self._remaining_ms = HIDE_MS
            self._progress.pack(fill=tk.X, pady=(6, 0))
            self._schedule_tick()

    def _update_progress(self) -> None:
        if self.pinned:
            return
        self._progress.update_idletasks()
        width = self._progress.winfo_width()
        if width <= 1:
            return
        fraction = max(0.0, min(1.0, self._remaining_ms / HIDE_MS))
        fill_w = int(width * fraction)
        self._progress.coords(self._progress_bar, 0, 0, fill_w, PROGRESS_H)

    def _clamp_position(self, anchor_x: int, anchor_y: int) -> None:
        self.win.update_idletasks()
        width = self.win.winfo_width()
        height = self.win.winfo_height()
        if width <= 1 or height <= 1:
            return
        work = _work_area_at(anchor_x, anchor_y)
        x, y = _clamp_to_work_area(self.win.winfo_x(), self.win.winfo_y(), width, height, work)
        self.win.geometry(f"+{x}+{y}")

    def _tick(self) -> None:
        self._tick_id = None
        if not self.win.winfo_exists():
            return

        self._sync_hover()

        if self.pinned:
            self._schedule_tick()
            return

        if not self._hovered:
            self._remaining_ms = max(0, self._remaining_ms - TICK_MS)
            self._update_progress()
            if self._remaining_ms <= 0:
                self.destroy()
                return

        self._schedule_tick()

    def _schedule_tick(self) -> None:
        if self._tick_id is not None:
            self.win.after_cancel(self._tick_id)
        self._tick_id = self.win.after(TICK_MS, self._tick)

    def show(self, x: int, y: int) -> None:
        ox, oy = CURSOR_OFFSET
        self.win.deiconify()
        self.win.geometry(f"+{x + ox}+{y + oy}")
        self._clamp_position(x + ox, y + oy)
        self.win.lift()
        self.win.update_idletasks()
        self._clamp_position(x + ox, y + oy)
        _apply_win_styles(self.win)
        self._remaining_ms = HIDE_MS
        self._update_progress()
        self._schedule_tick()

    def destroy(self) -> None:
        if self._tick_id is not None:
            try:
                self.win.after_cancel(self._tick_id)
            except tk.TclError:
                pass
            self._tick_id = None
        self.manager.remove(self)
        try:
            self.win.destroy()
        except tk.TclError:
            pass


class CardManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self._cards: list[PriceCard] = []

    def show(self, x: int, y: int, fields: dict) -> None:
        self._evict_if_needed()
        card = PriceCard(self, fields)
        card.show(x, y)
        self._cards.append(card)

    def remove(self, card: PriceCard) -> None:
        if card in self._cards:
            self._cards.remove(card)

    def _evict_if_needed(self) -> None:
        while len(self._cards) >= MAX_CARDS:
            unpinned = [c for c in self._cards if not c.pinned]
            victim = unpinned[0] if unpinned else self._cards[0]
            victim.destroy()

    def run(self) -> None:
        self.root.mainloop()

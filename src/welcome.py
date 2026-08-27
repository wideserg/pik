"""Pik welcome window — daily refresh summary and theme picker."""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from overlay import _work_area_at
from prices import RefreshResult
from theme import get_palette, set_theme

WELCOME_WIDTH = 420
FONT_TITLE = ("Segoe UI", 14, "bold")
FONT_BODY = ("Segoe UI", 10)
FONT_BTN = ("Segoe UI", 9)
FONT_CHIP = ("Segoe UI Semibold", 9)
FONT_PANEL_LABEL = ("Segoe UI", 8)


class WelcomeWindow:
    def __init__(
        self,
        root: tk.Tk,
        refresh: RefreshResult,
        theme_name: str,
        on_theme_change: Callable[[str], None],
    ):
        self._root = root
        self._refresh = refresh
        self._theme_name = theme_name
        self._on_theme_change = on_theme_change
        self._win: tk.Toplevel | None = None
        self._theme_var = tk.StringVar(value=theme_name)

    @property
    def exists(self) -> bool:
        return self._win is not None and self._win.winfo_exists()

    def show(self) -> None:
        if self.exists:
            self._win.deiconify()
            self._win.lift()
            self._win.focus_force()
            return
        self._build()

    def _build(self) -> None:
        p = get_palette(self._theme_name)
        win = tk.Toplevel(self._root)
        self._win = win
        win.title("Pik")
        win.resizable(False, False)
        win.configure(bg=p["bg"])
        win.protocol("WM_DELETE_WINDOW", self._close)

        outer = tk.Frame(win, bg=p["bg"], padx=20, pady=16)
        outer.pack(fill=tk.BOTH, expand=True)

        tk.Label(
            outer,
            text="Pik",
            bg=p["bg"],
            fg=p["accent"],
            font=FONT_TITLE,
            anchor="w",
        ).pack(anchor="w")

        tk.Label(
            outer,
            text="Hey — I'm Pik, your model-price sidekick.",
            bg=p["bg"],
            fg=p["fg"],
            font=FONT_BODY,
            justify=tk.LEFT,
            anchor="w",
            wraplength=WELCOME_WIDTH - 40,
        ).pack(anchor="w", pady=(10, 6))

        self._build_shortcut_row(outer, p)

        self._build_prices_panel(outer, p)

        tk.Label(
            outer,
            text="Have a ridiculously good AI day.",
            bg=p["bg"],
            fg=p["fg"],
            font=FONT_BODY,
            justify=tk.LEFT,
            anchor="w",
            wraplength=WELCOME_WIDTH - 40,
        ).pack(anchor="w", pady=(10, 12))

        theme_row = tk.Frame(outer, bg=p["bg"])
        theme_row.pack(fill=tk.X, pady=(0, 12))

        tk.Label(
            theme_row,
            text="Theme",
            bg=p["bg"],
            fg=p["fg_muted"],
            font=FONT_BTN,
        ).pack(side=tk.LEFT, padx=(0, 8))

        for label, value in (("Light", "light"), ("Dark", "dark")):
            rb = tk.Radiobutton(
                theme_row,
                text=label,
                variable=self._theme_var,
                value=value,
                command=self._on_theme_toggle,
                bg=p["bg"],
                fg=p["fg"],
                selectcolor=p["btn_active"],
                activebackground=p["bg"],
                activeforeground=p["fg"],
                font=FONT_BTN,
                indicatoron=False,
                padx=10,
                pady=4,
                bd=0,
                highlightthickness=0,
            )
            rb.pack(side=tk.LEFT, padx=(0, 6))

        close_btn = tk.Button(
            outer,
            text="Got it",
            command=self._close,
            bg=p["btn_bg"],
            fg=p["fg"],
            activebackground=p["btn_active"],
            activeforeground=p["fg"],
            font=FONT_BTN,
            relief=tk.FLAT,
            padx=16,
            pady=6,
            cursor="hand2",
        )
        close_btn.pack(anchor="e")

        win.update_idletasks()
        height = win.winfo_reqheight()
        win.geometry(f"{WELCOME_WIDTH}x{height}")
        self._center(win)

    def _build_shortcut_row(self, parent: tk.Frame, p: dict[str, str]) -> None:
        row = tk.Frame(parent, bg=p["bg"])
        row.pack(anchor="w", pady=(0, 8))

        tk.Label(
            row,
            text="Hover a model in the picker, then hit ",
            bg=p["bg"],
            fg=p["fg"],
            font=FONT_BODY,
        ).pack(side=tk.LEFT)

        chips = tk.Frame(row, bg=p["bg"])
        chips.pack(side=tk.LEFT)

        for i, key in enumerate(("Ctrl", "Alt", "P")):
            if i:
                tk.Label(
                    chips,
                    text="+",
                    bg=p["bg"],
                    fg=p["fg_muted"],
                    font=FONT_BODY,
                ).pack(side=tk.LEFT, padx=2)
            chip = tk.Frame(
                chips,
                bg=p["chip_bg"],
                highlightbackground=p["chip_border"],
                highlightthickness=1,
            )
            chip.pack(side=tk.LEFT)
            tk.Label(
                chip,
                text=key,
                bg=p["chip_bg"],
                fg=p["fg"],
                font=FONT_CHIP,
                padx=5,
                pady=1,
            ).pack()

    def _build_prices_panel(self, parent: tk.Frame, p: dict[str, str]) -> None:
        lines = self._body_lines()
        if not lines:
            return

        panel = tk.Frame(parent, bg=p["panel_bg"])
        panel.pack(anchor="w", fill=tk.X, pady=(0, 4))

        row = tk.Frame(panel, bg=p["panel_bg"])
        row.pack(fill=tk.X)

        tk.Frame(row, bg=p["panel_accent"], width=3).pack(side=tk.LEFT, fill=tk.Y)

        content = tk.Frame(row, bg=p["panel_bg"], padx=10, pady=8)
        content.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(
            content,
            text="Prices",
            bg=p["panel_bg"],
            fg=p["fg_muted"],
            font=FONT_PANEL_LABEL,
            anchor="w",
        ).pack(anchor="w", pady=(0, 4))

        for line in lines:
            tk.Label(
                content,
                text=line,
                bg=p["panel_bg"],
                fg=p["fg_dim"],
                font=FONT_BODY,
                justify=tk.LEFT,
                anchor="w",
                wraplength=WELCOME_WIDTH - 70,
            ).pack(anchor="w", pady=(0, 2))

    def _body_lines(self) -> list[str]:
        r = self._refresh
        lines: list[str] = []

        if r.skipped:
            lines.append("Prices are fresh from earlier today. I didn't nag the docs twice.")
            return lines

        if r.fetch_failed:
            lines.append("Couldn't reach Cursor's docs — keeping yesterday's menu.")
            return lines

        if r.refreshed:
            lines.append("I refreshed Cursor's price list.")
            diff = r.diff
            if diff and diff.has_changes():
                summary, extra = diff.summary_lines(max_lines=8)
                lines.extend(summary)
                if extra:
                    lines.append(f"+{extra} more")
            else:
                lines.append("Nothing moved. Same menu, same numbers. (That's a win.)")

        return lines

    def _center(self, win: tk.Toplevel) -> None:
        win.update_idletasks()
        width = win.winfo_width()
        height = win.winfo_height()
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        cx, cy = sw // 2, sh // 2
        work = _work_area_at(cx, cy)
        left, top, right, bottom = work
        x = left + (right - left - width) // 2
        y = top + (bottom - top - height) // 2
        win.geometry(f"+{x}+{y}")

    def _on_theme_toggle(self) -> None:
        name = self._theme_var.get()
        self._theme_name = name
        set_theme(name)
        self._on_theme_change(name)
        if self._win is not None:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None
        self._build()

    def _close(self) -> None:
        if self._win is not None:
            try:
                self._win.withdraw()
            except tk.TclError:
                pass

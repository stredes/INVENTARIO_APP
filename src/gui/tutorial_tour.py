from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, List, Optional


class InteractiveTour:
    def __init__(
        self,
        root: tk.Misc,
        steps: List[dict],
        *,
        start_index: int = 0,
        on_close: Optional[Callable[[], None]] = None,
    ) -> None:
        self.root = root
        self.steps = steps
        self.index = max(0, min(start_index, len(steps) - 1)) if steps else 0
        self.on_close = on_close

        self._root_x = 0
        self._root_y = 0
        self._root_w = 0
        self._root_h = 0
        self._bind_id = None
        self._active_bind_id = None
        self._deactive_bind_id = None

        self._build_overlay()
        self._build_card()
        self._bind_focus_hooks()
        self._sync_geometry()
        self._set_topmost(True)
        self._show_step(self.index)

    def _build_overlay(self) -> None:
        self.overlay = tk.Toplevel(self.root)
        self.overlay.overrideredirect(True)
        try:
            self.overlay.transient(self.root)
        except Exception:
            pass
        self._use_transparent = False
        self._transparent_color = "#ff00ff"
        self.overlay.configure(bg="#000000")
        try:
            self.overlay.attributes("-alpha", 0.45)
        except Exception:
            try:
                self._use_transparent = True
                self.overlay.configure(bg=self._transparent_color)
                self.overlay.attributes("-transparentcolor", self._transparent_color)
            except Exception:
                self._use_transparent = False

        self.canvas = tk.Canvas(
            self.overlay,
            highlightthickness=0,
            bd=0,
            bg=(self._transparent_color if self._use_transparent else "#000000"),
        )
        self.canvas.pack(fill="both", expand=True)
        self.overlay.bind("<Button-1>", lambda _e: None)

    def _build_card(self) -> None:
        self.card_win = tk.Toplevel(self.root)
        self.card_win.overrideredirect(True)
        self.card_win.transient(self.root)
        self.card_win.bind("<Escape>", lambda _e: self.close())

        frame = ttk.Frame(self.card_win, padding=12, relief="raised", borderwidth=1)
        frame.pack(fill="both", expand=True)

        header = ttk.Frame(frame)
        header.pack(fill="x")
        self.lbl_title = ttk.Label(header, text="", font=("", 11, "bold"))
        self.lbl_title.pack(side="left")
        self.btn_close = ttk.Button(header, text="x", width=3, command=self.close)
        self.btn_close.pack(side="right")

        self.lbl_body = ttk.Label(frame, text="", justify="left", wraplength=380)
        self.lbl_body.pack(fill="x", pady=(8, 8))

        footer = ttk.Frame(frame)
        footer.pack(fill="x")
        self.lbl_counter = ttk.Label(footer, text="")
        self.lbl_counter.pack(side="left")

        self.btn_prev = ttk.Button(footer, text="Anterior", command=self.prev)
        self.btn_skip = ttk.Button(footer, text="Saltar", command=self.close)
        self.btn_next = ttk.Button(footer, text="Siguiente", command=self.next)
        self.btn_next.pack(side="right")
        self.btn_skip.pack(side="right", padx=(0, 6))
        self.btn_prev.pack(side="right", padx=(0, 6))

    def _sync_geometry(self) -> None:
        try:
            self.root.update_idletasks()
            self._root_w = max(1, int(self.root.winfo_width()))
            self._root_h = max(1, int(self.root.winfo_height()))
            self._root_x = int(self.root.winfo_rootx())
            self._root_y = int(self.root.winfo_rooty())
        except Exception:
            return

        self.overlay.geometry(f"{self._root_w}x{self._root_h}+{self._root_x}+{self._root_y}")
        self.canvas.configure(width=self._root_w, height=self._root_h)

        if self._bind_id is None:
            try:
                self._bind_id = self.root.bind("<Configure>", lambda _e: self._on_root_configure(), add="+")
            except Exception:
                self._bind_id = None

    def _bind_focus_hooks(self) -> None:
        if self._active_bind_id is None:
            try:
                self._active_bind_id = self.root.bind("<Activate>", lambda _e: self._set_topmost(True), add="+")
            except Exception:
                self._active_bind_id = None
        if self._deactive_bind_id is None:
            try:
                self._deactive_bind_id = self.root.bind("<Deactivate>", lambda _e: self._set_topmost(False), add="+")
            except Exception:
                self._deactive_bind_id = None

    def _set_topmost(self, enabled: bool) -> None:
        for win in (self.overlay, self.card_win):
            try:
                win.attributes("-topmost", bool(enabled))
            except Exception:
                pass
        if enabled:
            try:
                self.overlay.lift(self.root)
                self.card_win.lift(self.overlay)
                self.card_win.focus_force()
            except Exception:
                pass

    def _on_root_configure(self) -> None:
        self._sync_geometry()
        self._show_step(self.index, refresh_only=True)

    def _resolve_target(self, getter: Optional[Callable[[], tk.Widget]]) -> Optional[tk.Widget]:
        if getter is None:
            return None
        try:
            widget = getter()
        except Exception:
            return None
        if widget is None:
            return None
        try:
            if not widget.winfo_ismapped():
                return None
        except Exception:
            return None
        return widget

    def _target_rect(self, widget: tk.Widget, pad: int = 6) -> tuple[int, int, int, int]:
        self.root.update_idletasks()
        x1 = widget.winfo_rootx() - self._root_x - pad
        y1 = widget.winfo_rooty() - self._root_y - pad
        x2 = x1 + widget.winfo_width() + (pad * 2)
        y2 = y1 + widget.winfo_height() + (pad * 2)
        x1 = max(0, x1)
        y1 = max(0, y1)
        x2 = min(self._root_w, x2)
        y2 = min(self._root_h, y2)
        return x1, y1, x2, y2

    def _draw_overlay(self, rect: Optional[tuple[int, int, int, int]]) -> None:
        self.canvas.delete("dim")
        self.canvas.delete("focus")
        if self._use_transparent:
            if rect:
                x1, y1, x2, y2 = rect
                self.canvas.create_rectangle(0, 0, self._root_w, y1, fill="#000000", outline="", stipple="gray50", tags="dim")
                self.canvas.create_rectangle(0, y2, self._root_w, self._root_h, fill="#000000", outline="", stipple="gray50", tags="dim")
                self.canvas.create_rectangle(0, y1, x1, y2, fill="#000000", outline="", stipple="gray50", tags="dim")
                self.canvas.create_rectangle(x2, y1, self._root_w, y2, fill="#000000", outline="", stipple="gray50", tags="dim")
            else:
                self.canvas.create_rectangle(0, 0, self._root_w, self._root_h, fill="#000000", outline="", stipple="gray50", tags="dim")
        else:
            self.canvas.create_rectangle(0, 0, self._root_w, self._root_h, fill="#000000", outline="", tags="dim")
        if rect:
            x1, y1, x2, y2 = rect
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#ffcc00", width=3, tags="focus")

    def _place_card(self, rect: Optional[tuple[int, int, int, int]]) -> None:
        self.card_win.update_idletasks()
        cw = self.card_win.winfo_reqwidth()
        ch = self.card_win.winfo_reqheight()
        margin = 16

        if rect:
            x1, y1, x2, y2 = rect
            candidates = [
                (x2 + margin, y1),
                (x1 - margin - cw, y1),
                (x1, y2 + margin),
                (x1, y1 - margin - ch),
            ]
            x = None
            y = None
            for cx, cy in candidates:
                if 0 <= cx <= (self._root_w - cw) and 0 <= cy <= (self._root_h - ch):
                    x, y = cx, cy
                    break
            if x is None or y is None:
                x = max(0, min(self._root_w - cw, x1))
                y = max(0, min(self._root_h - ch, y2 + margin))
        else:
            x = max(0, int((self._root_w - cw) / 2))
            y = max(0, int((self._root_h - ch) / 2))

        self.card_win.geometry(f"{cw}x{ch}+{self._root_x + x}+{self._root_y + y}")

    def _show_step(self, idx: int, *, refresh_only: bool = False) -> None:
        if not self.steps:
            return
        idx = max(0, min(idx, len(self.steps) - 1))
        self.index = idx

        step = self.steps[idx]
        if not refresh_only:
            before = step.get("before")
            if callable(before):
                try:
                    before()
                except Exception:
                    pass

        title = step.get("title", "")
        body = step.get("body", "")
        self.lbl_title.config(text=title)
        self.lbl_body.config(text=body)
        self.lbl_counter.config(text=f"{idx + 1} / {len(self.steps)}")
        self.btn_prev.config(state=("disabled" if idx == 0 else "normal"))
        self.btn_next.config(state=("disabled" if idx >= len(self.steps) - 1 else "normal"))

        target = self._resolve_target(step.get("target"))
        rect = self._target_rect(target) if target else None
        self._draw_overlay(rect)
        self._place_card(rect)

    def next(self) -> None:
        self._show_step(self.index + 1)

    def prev(self) -> None:
        self._show_step(self.index - 1)

    def close(self) -> None:
        try:
            if self._bind_id is not None:
                self.root.unbind("<Configure>", self._bind_id)
        except Exception:
            pass
        try:
            if self._active_bind_id is not None:
                self.root.unbind("<Activate>", self._active_bind_id)
        except Exception:
            pass
        try:
            if self._deactive_bind_id is not None:
                self.root.unbind("<Deactivate>", self._deactive_bind_id)
        except Exception:
            pass
        try:
            self.overlay.destroy()
        except Exception:
            pass
        try:
            self.card_win.destroy()
        except Exception:
            pass
        if self.on_close:
            try:
                self.on_close()
            except Exception:
                pass

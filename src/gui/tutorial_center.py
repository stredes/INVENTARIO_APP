from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Dict, List, Optional


class TutorialCenter(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        modules: Dict[str, List[str]],
        start_module: Optional[str] = None,
        on_open_module: Optional[Callable[[str], None]] = None,
        on_start_tour: Optional[Callable[[str], None]] = None,
    ) -> None:
        super().__init__(parent)
        self.title("Tutoriales")
        self.geometry("860x520")
        self.minsize(760, 420)
        self.transient(parent)

        self._modules = modules
        self._module_names = list(modules.keys())
        self._on_open_module = on_open_module
        self._on_start_tour = on_start_tour
        self._current_module = start_module if start_module in modules else self._module_names[0]
        self._step_index = 0

        self._build_ui()
        self._select_module(self._current_module)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=10)
        root.pack(fill="both", expand=True)

        left = ttk.Frame(root)
        left.pack(side="left", fill="y")

        ttk.Label(left, text="Modulos", font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))
        self.lst = tk.Listbox(left, height=14, exportselection=False)
        for name in self._module_names:
            self.lst.insert("end", name)
        self.lst.pack(fill="y", expand=False)
        self.lst.bind("<<ListboxSelect>>", self._on_select)

        right = ttk.Frame(root)
        right.pack(side="left", fill="both", expand=True, padx=(16, 0))

        self.lbl_title = ttk.Label(right, text="", font=("", 12, "bold"))
        self.lbl_title.pack(anchor="w")

        self.lbl_step = ttk.Label(right, text="", justify="left", wraplength=560)
        self.lbl_step.pack(anchor="w", pady=(10, 8), fill="x")

        self.lbl_counter = ttk.Label(right, text="", foreground="#666666")
        self.lbl_counter.pack(anchor="w")

        btns = ttk.Frame(right)
        btns.pack(fill="x", pady=(14, 0))
        self.btn_prev = ttk.Button(btns, text="Anterior", command=self._prev_step)
        self.btn_next = ttk.Button(btns, text="Siguiente", command=self._next_step)
        self.btn_reset = ttk.Button(btns, text="Reiniciar", command=self._reset_steps)
        self.btn_open = ttk.Button(btns, text="Ir al modulo", command=self._open_module)
        self.btn_start = ttk.Button(btns, text="Iniciar guia", command=self._start_tour)

        self.btn_prev.pack(side="left")
        self.btn_next.pack(side="left", padx=6)
        self.btn_reset.pack(side="left", padx=6)
        self.btn_start.pack(side="right", padx=6)
        self.btn_open.pack(side="right")

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _on_select(self, _evt=None) -> None:
        try:
            idx = int(self.lst.curselection()[0])
            name = self._module_names[idx]
            self._select_module(name)
        except Exception:
            pass

    def _select_module(self, name: str) -> None:
        if name not in self._modules:
            return
        self._current_module = name
        self._step_index = 0
        self.lbl_title.config(text=f"Tutorial: {name}")
        try:
            idx = self._module_names.index(name)
            self.lst.selection_clear(0, "end")
            self.lst.selection_set(idx)
            self.lst.see(idx)
        except Exception:
            pass
        self._render_step()

    def _render_step(self) -> None:
        steps = self._modules.get(self._current_module, [])
        total = max(1, len(steps))
        idx = max(0, min(self._step_index, total - 1))
        self._step_index = idx
        text = steps[idx] if steps else "Sin pasos definidos."
        self.lbl_step.config(text=text)
        self.lbl_counter.config(text=f"Paso {idx + 1} de {total}")
        self.btn_prev.config(state=("disabled" if idx == 0 else "normal"))
        self.btn_next.config(state=("disabled" if idx >= total - 1 else "normal"))

    def _next_step(self) -> None:
        self._step_index += 1
        self._render_step()

    def _prev_step(self) -> None:
        self._step_index -= 1
        self._render_step()

    def _reset_steps(self) -> None:
        self._step_index = 0
        self._render_step()

    def _open_module(self) -> None:
        if self._on_open_module:
            try:
                self._on_open_module(self._current_module)
            except Exception:
                pass

    def _start_tour(self) -> None:
        if self._on_start_tour:
            try:
                self._on_start_tour(self._current_module)
            except Exception:
                pass

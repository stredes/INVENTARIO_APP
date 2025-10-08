# src/gui/widgets/command_palette.py
from __future__ import annotations
"""
Paleta de comandos (Ctrl+K) para Tkinter/ttk.

Características:
- Lista acciones (label, callback, keywords, categoría, atajo textual).
- Búsqueda "fuzzy" con difflib + heurísticas (prefijo / substring / keywords).
- Proveedor dinámico opcional: provider(query) -> list[CommandAction].
- Persistencia simple de popularidad/MRU en config/commands_usage.ini.
- Navegación: ↑/↓, Enter, Doble-click, Esc (cerrar), Alt+1..9 (ejecución rápida).

Uso mínimo:
    from src.gui.widgets.command_palette import CommandPalette, CommandAction

    def open_palette(root):
        actions = [
            CommandAction(id="go_products", label="Ir a Productos", callback=lambda: show_products(), keywords=["productos", "stock"]),
            CommandAction(id="new_po", label="Nueva Orden de Compra", callback=lambda: create_po(), category="Compras", shortcut="Ctrl+N"),
            CommandAction(id="print", label="Imprimir listado actual", callback=print_current, keywords=["pdf", "export"]),
        ]
        CommandPalette.open(root, actions=actions)  # o provider=mi_provider

Hook recomendado en tu MainWindow:
    self.bind_all("<Control-k>", lambda e: CommandPalette.open(self.winfo_toplevel(), actions=...))
"""

import configparser
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Callable, Iterable, List, Optional

import tkinter as tk
from tkinter import ttk


# ----------------------------- Modelo de acción ---------------------------- #

@dataclass(frozen=True)
class CommandAction:
    """
    Acción que puede ejecutar la paleta.
    - id: identificador estable para persistencia (único).
    - label: texto visible (lo que se busca).
    - callback: función sin argumentos (usa lambda para pasar args).
    - keywords: sinónimos/palabras relacionadas para mejorar la búsqueda.
    - category: grupo visual ("Inventario", "Ventas", etc.).
    - shortcut: texto decorativo ("Ctrl+N", "F9"...).
    """
    id: str
    label: str
    callback: Callable[[], Any]
    keywords: Iterable[str] = field(default_factory=tuple)
    category: Optional[str] = None
    shortcut: Optional[str] = None


# ------------------------------- Persistencia ------------------------------ #

USAGE_PATH = Path("config/commands_usage.ini")


def _load_usage() -> dict:
    cfg = configparser.ConfigParser()
    if USAGE_PATH.exists():
        cfg.read(USAGE_PATH, encoding="utf-8")
    return {k: int(v) for k, v in cfg.items("counts")} if cfg.has_section("counts") else {}


def _save_usage(counts: dict) -> None:
    cfg = configparser.ConfigParser()
    cfg["counts"] = {k: str(v) for k, v in counts.items()}
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with USAGE_PATH.open("w", encoding="utf-8") as f:
        cfg.write(f)


# ------------------------------- Paleta UI -------------------------------- #

class CommandPalette(tk.Toplevel):
    """
    Ventana flotante modal-suave para ejecutar acciones.
    Cree con CommandPalette.open(root, actions=..., provider=...).

    No instanciar directamente salvo que quieras manejar el ciclo manualmente.
    """

    # Singleton por root (evita abrir múltiples instancias superpuestas)
    _instances: dict[int, "CommandPalette"] = {}

    @classmethod
    def open(
        cls,
        root: tk.Tk | tk.Toplevel,
        *,
        actions: Optional[List[CommandAction]] = None,
        provider: Optional[Callable[[str], List[CommandAction]]] = None,
        title: str = "Comandos",
        limit: int = 12,
    ) -> "CommandPalette":
        """
        Abre (o reusa) la paleta para el root dado.
        - actions: lista estática (si no usas provider).
        - provider: función que devuelve acciones para un query.
        - limit: máximo de resultados a mostrar.
        """
        key = int(root.winfo_id())
        inst = cls._instances.get(key)
        if inst is not None and inst.winfo_exists():
            # Reusar: traer al frente y limpiar query
            inst._limit = limit
            inst._set_data(actions, provider)
            inst._reset_and_show()
            return inst

        inst = cls(root, actions=actions, provider=provider, title=title, limit=limit)
        cls._instances[key] = inst
        return inst

    # ------------------------------------------------------------------ #

    def __init__(
        self,
        master: tk.Misc,
        *,
        actions: Optional[List[CommandAction]] = None,
        provider: Optional[Callable[[str], List[CommandAction]]] = None,
        title: str = "Comandos",
        limit: int = 12,
    ) -> None:
        super().__init__(master)

        self.title(title)
        self.transient(master)          # ventana asociada a master
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self._limit = limit

        # Data
        self._static_actions: List[CommandAction] = list(actions or [])
        self._provider = provider
        self._usage = _load_usage()

        # Estado
        self._query = tk.StringVar()
        self._hint = tk.StringVar(value="Enter: ejecutar • Esc: cerrar • ↑/↓: navegar • Alt+1..9: ejecutar")
        self._list_items: List[CommandAction] = []

        # Layout principal
        pad = 12
        frm = ttk.Frame(self, padding=(pad, pad, pad, 8))
        frm.grid(row=0, column=0, sticky="nsew")
        self.columnconfigure(0, weight=1)

        # Entrada de búsqueda
        self._entry = ttk.Entry(frm, textvariable=self._query, width=52)
        self._entry.grid(row=0, column=0, padx=0, pady=(0, 6), sticky="we")
        self._entry.bind("<KeyRelease>", self._on_query_change)

        # Lista de resultados
        self._list = tk.Listbox(frm, height=self._limit, activestyle="dotbox")
        self._list.grid(row=1, column=0, sticky="we")
        self._list.bind("<Double-1>", lambda e: self._run_selected())
        self._list.bind("<Return>", lambda e: self._run_selected())
        self._list.bind("<Escape>", lambda e: self._close())

        # Hint / ayuda
        ttk.Label(frm, textvariable=self._hint, style="InfoBadge.TLabel").grid(
            row=2, column=0, sticky="w", pady=(6, 0)
        )

        # Keybindings globales
        self.bind("<Escape>", lambda e: self._close())
        self.bind("<Return>", lambda e: self._run_selected())
        self.bind("<Up>", lambda e: self._move(-1))
        self.bind("<Down>", lambda e: self._move(1))
        # Alt+1..9 -> ejecutar item N
        for n in range(1, 10):
            self.bind(f"<Alt-KeyPress-{n}>", self._run_index_factory(n - 1))

        # Centrado relativo a master
        self.update_idletasks()
        w, h = 560, 340
        x = master.winfo_rootx() + (master.winfo_width() - w) // 2
        y = master.winfo_rooty() + (master.winfo_height() - h) // 3
        self.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")

        # Modal suave
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        # Inicial
        self._refresh_results("")
        self.after(50, self._entry.focus_set)

    # ------------------------------- API interna -------------------------- #

    def _set_data(
        self,
        actions: Optional[List[CommandAction]],
        provider: Optional[Callable[[str], List[CommandAction]]],
    ) -> None:
        if actions is not None:
            self._static_actions = list(actions)
        if provider is not None:
            self._provider = provider

    def _reset_and_show(self) -> None:
        self.deiconify()
        self._query.set("")
        self._refresh_results("")
        self.grab_set()
        self.focus_force()
        self.after(30, self._entry.focus_set)

    def _on_query_change(self, *_):
        self._refresh_results(self._query.get())

    # ------------------------------- Búsqueda ------------------------------ #

    def _refresh_results(self, query: str) -> None:
        query = (query or "").strip()
        # 1) Conseguir candidatos
        if self._provider:
            try:
                candidates = list(self._provider(query))
            except Exception:
                candidates = []
        else:
            candidates = list(self._static_actions)

        # 2) Rankear
        scored = []
        for act in candidates:
            score = self._score_action(act, query)
            if score <= 0 and query:
                continue
            scored.append((score, act))

        # Si query vacío, ordenar por popularidad → label
        if not query:
            scored.sort(key=lambda t: (-self._usage.get(t[1].id, 0), t[1].label.casefold()))
        else:
            scored.sort(key=lambda t: (-t[0], t[1].label.casefold()))

        # 3) Poblar lista
        self._list.delete(0, "end")
        self._list_items = [a for _, a in scored[: self._limit]]

        for idx, act in enumerate(self._list_items, start=1):
            cat = f"  [{act.category}]" if act.category else ""
            shc = f"  · {act.shortcut}" if act.shortcut else ""
            prefix = f"{idx}. " if idx <= 9 else ""
            self._list.insert("end", f"{prefix}{act.label}{cat}{shc}")

        # Selección inicial
        if self._list_items:
            self._list.selection_clear(0, "end")
            self._list.selection_set(0)
            self._list.activate(0)

    def _score_action(self, act: CommandAction, query: str) -> float:
        """
        Heurística de ranking:
          +200 match exacto del label
          +120 prefijo del label
          +80  substring en label
          +30  similitud difusa (0..1)*30
          +15  substring en keywords (cada una)
          +pop popularidad (5 por uso)
        """
        q = query.casefold()
        label = act.label.casefold()
        kws = " ".join([str(k).casefold() for k in act.keywords or []])

        score = 0.0
        if not q:
            # Solo popularidad cuando no hay query
            score += 5.0 * self._usage.get(act.id, 0)
            return score

        if label == q:
            score += 200
        if label.startswith(q):
            score += 120
        if q in label:
            score += 80

        ratio = SequenceMatcher(None, q, label).ratio()
        score += ratio * 30.0

        if kws:
            if q in kws:
                score += 15
            else:
                # algo de fuzzy también sobre keywords
                score += SequenceMatcher(None, q, kws).ratio() * 10.0

        score += 5.0 * self._usage.get(act.id, 0)
        return score

    # ----------------------------- Interacción ----------------------------- #

    def _move(self, delta: int) -> None:
        if not self._list_items:
            return
        cur = self._list.curselection()
        idx = cur[0] if cur else 0
        idx = max(0, min(len(self._list_items) - 1, idx + delta))
        self._list.selection_clear(0, "end")
        self._list.selection_set(idx)
        self._list.activate(idx)
        self._list.see(idx)

    def _run_selected(self) -> None:
        sel = self._list.curselection()
        idx = sel[0] if sel else 0
        if 0 <= idx < len(self._list_items):
            self._run_action(self._list_items[idx])

    def _run_index_factory(self, idx0: int):
        def _handler(event=None):
            if 0 <= idx0 < len(self._list_items):
                self._run_action(self._list_items[idx0])
        return _handler

    def _run_action(self, action: CommandAction) -> None:
        # Popularidad/MRU
        self._usage[action.id] = self._usage.get(action.id, 0) + 1
        try:
            _save_usage(self._usage)
        except Exception:
            pass

        # Cerrar antes de ejecutar (UX más fluida)
        self._close()
        try:
            action.callback()
        except Exception as ex:
            # Fallback simple de error (no rompemos la app)
            self._show_error(str(ex))

    # ------------------------------ Cierre -------------------------------- #

    def _close(self) -> None:
        try:
            self.grab_release()
        except Exception:
            pass
        self.withdraw()
        self.destroy()

    # --------------------------- Mensaje de error -------------------------- #

    def _show_error(self, text: str) -> None:
        """
        Muestra un error pequeño en la parte inferior por unos segundos.
        (Idealmente usar un Toast externo. Aquí lo dejamos mínimo.)
        """
        try:
            lbl = ttk.Label(self, text=f"Error: {text}", style="DangerBadge.TLabel")
            lbl.place(relx=0.02, rely=0.92)
            self.after(2500, lbl.destroy)
        except Exception:
            pass

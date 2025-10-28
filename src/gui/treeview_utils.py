from __future__ import annotations

from typing import Iterable
import tkinter as tk
from tkinter import ttk


def center_treeview(tree: ttk.Treeview, *, stretch: bool | None = None) -> None:
    """
    Centra encabezados y celdas de un ttk.Treeview.
    - Aplica a la columna '#0' y a todas las columnas declaradas.
    - Si `stretch` es None, respeta el valor actual. Si es bool, lo fija.
    """
    # Encabezados: se puede configurar también vía estilo, pero lo dejamos explícito.
    tree.heading("#0", anchor="center")
    if stretch is None:
        tree.column("#0", anchor="center")
    else:
        tree.column("#0", anchor="center", stretch=stretch)

    for col in tree.cget("columns") or ():
        tree.heading(col, anchor="center")
        if stretch is None:
            tree.column(col, anchor="center")
        else:
            tree.column(col, anchor="center", stretch=stretch)


def center_all_treeviews(root: tk.Misc, *, stretch: bool | None = None) -> None:
    """Busca recursivamente y centra todos los Treeview existentes bajo `root`."""
    for widget in root.winfo_children():
        if isinstance(widget, ttk.Treeview):
            center_treeview(widget, stretch=stretch)
        # Recursión: frames, notebooks, etc.
        if isinstance(widget, (ttk.Frame, tk.Frame, ttk.Notebook, tk.Toplevel, ttk.LabelFrame)):
            center_all_treeviews(widget, stretch=stretch)


def apply_default_treeview_styles():
    """
    Opcional: centra los encabezados por estilo para cualquier Treeview nuevo.
    (El cuerpo de las celdas sigue necesitando `center_treeview` porque ttk
    no expone el 'anchor' de celdas vía estilo.)
    """
    style = ttk.Style()
    # For a consistent look across platforms
    # No forzamos un tema (para no interferir con menús nativos)
    # Headings centrados y con leve fondo
    style.configure(
        "Treeview.Heading",
        anchor="center",
        font=("Segoe UI", 14, "bold"),
        padding=(4, 6),
        relief="flat",
        background="#D5EAF7",
    )
    # Rows: slightly larger height for readability
    style.configure(
        "Treeview",
        font=("Segoe UI", 14),
        rowheight=28,
    )


def apply_professional_style_to(tree: ttk.Treeview) -> None:
    """Ensure the Treeview uses the global style and is centered."""
    center_treeview(tree)
    try:
        tree.configure(style="Treeview")
    except Exception:
        pass


def enable_treeview_sort(tree: ttk.Treeview) -> None:
    """Añade ordenamiento al click en encabezados.

    - Texto: orden A→Z por defecto, alterna Z→A en clics sucesivos.
    - Números/moneda: orden mayor→menor por defecto, alterna.
    - Detecta números intentando convertir quitando símbolos ($, CLP, %, separadores).
    """
    try:
        cols = list(tree.cget("columns") or [])
    except Exception:
        cols = []
    if not cols:
        return

    if not hasattr(tree, "_sort_state"):
        tree._sort_state = {}  # type: ignore[attr-defined]

    def _to_number(v: str):
        s = str(v or "").strip()
        s = s.replace("$", "").replace("CLP", "").replace("%", "").strip()
        # Normaliza separadores: quita miles (.) y usa coma como miles posible
        s = s.replace(".", "").replace(",", ".")
        try:
            return float(s)
        except Exception:
            return None

    def _sort_by(col: str):
        children = tree.get_children("")
        data = []
        all_numeric = True
        for iid in children:
            val = tree.set(iid, col)
            num = _to_number(val)
            if num is None and str(val).strip() != "":
                all_numeric = False
            data.append((num if num is not None else val, iid))

        # Dirección por defecto según tipo
        prev = getattr(tree, "_sort_state", {}).get(col, None)  # type: ignore[attr-defined]
        if all_numeric:
            default_desc = True
            reverse = (prev is None) or (prev is False)
            # Si numérico, queremos mayor→menor por defecto
            reverse = True if prev is None else not prev
        else:
            # Texto: A→Z por defecto
            reverse = False if prev is None else not prev

        # Ordena
        if all_numeric:
            keyfunc = lambda x: (float('-inf') if x[0] == '' else x[0])
        else:
            keyfunc = lambda x: str(x[0]).lower()
        data.sort(key=keyfunc, reverse=reverse)

        # Reordenar items
        for index, (_val, iid) in enumerate(data):
            tree.move(iid, "", index)

        # Guarda estado (True si orden descendente)
        tree._sort_state[col] = reverse  # type: ignore[attr-defined]

    # Asigna comando a cada encabezado
    for c in cols:
        try:
            tree.heading(c, command=lambda cc=c: _sort_by(cc))
        except Exception:
            pass


def enable_auto_center_for_new_treeviews():
    """
    Monkeys‑patch ttk.Treeview to auto‑centrar columnas al crearse el widget.
    Llama a `center_treeview` con `after_idle` para no interferir con layouts.
    Ejecutar una vez al inicio de la app.
    """
    if getattr(ttk.Treeview, "_center_patch_applied", False):
        return

    _orig_init = ttk.Treeview.__init__

    def _patched_init(self, *args, **kwargs):
        _orig_init(self, *args, **kwargs)
        try:
            # Tras construcción, aplica estilo y centra encabezados/celdas
            self.after_idle(lambda w=self: apply_professional_style_to(w))
        except Exception:
            pass

    ttk.Treeview.__init__ = _patched_init  # type: ignore[assignment]
    ttk.Treeview._center_patch_applied = True  # type: ignore[attr-defined]

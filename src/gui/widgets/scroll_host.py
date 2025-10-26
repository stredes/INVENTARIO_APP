from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Type, Optional


class ScrollHost(ttk.Frame):
    """
    Contenedor scrollable para alojar vistas existentes sin modificarlas.
    - Crea un Canvas + Scrollbar vertical.
    - Inserta el frame de la vista dentro del canvas.
    - Rueda del ratón desplaza el canvas salvo cuando el widget
      origen sea un Treeview/TkSheet (para no interferir con tablas).
    """

    def __init__(self, master: tk.Misc, view_cls: Type[ttk.Frame]):
        super().__init__(master)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        # Frame interno donde vive la vista
        self.inner = ttk.Frame(self.canvas)
        self._win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")

        # Instancia de la vista real
        self.content_view: ttk.Frame = view_cls(self.inner)
        self.content_view.pack(fill="both", expand=True)

        # Actualiza región de scroll al cambiar tamaño
        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Rueda del ratón en todo el contenedor
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.bind_all(seq, self._on_mousewheel, add="+")

    # ----------------- eventos -----------------
    def _on_inner_configure(self, _e=None):
        try:
            self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        except Exception:
            pass

    def _on_canvas_configure(self, event):
        try:
            # Ajusta el ancho del inner al del canvas
            self.canvas.itemconfigure(self._win, width=event.width)
        except Exception:
            pass

    def _origin_is_table(self, widget: tk.Misc) -> bool:
        """True si el widget origen es una tabla (Treeview/tksheet) para no interferir."""
        try:
            # Treeview
            if isinstance(widget, ttk.Treeview):
                return True
            # TkSheet expone clase "Tksheet" o similares
            wclass = str(widget.winfo_class()).lower()
            if "tksheet" in wclass:
                return True
        except Exception:
            pass
        return False

    def _on_mousewheel(self, event):
        # Aplica solo si el evento ocurre dentro de este contenedor
        try:
            if not str(event.widget).startswith(str(self)):
                return
            if self._origin_is_table(event.widget):
                return
            if event.delta:
                self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                if event.num == 4:
                    self.canvas.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.canvas.yview_scroll(1, "units")
        except Exception:
            pass
        # No "break" global para no bloquear otros scroll en tablas


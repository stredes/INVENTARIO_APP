from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional


class ReceptionLinkDialog(tk.Toplevel):
    """Diálogo para vincular la OC seleccionada con un documento (Factura/Guía)."""

    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("Vincular recepción")
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[dict] = None

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Tipo de documento:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.var_tipo = tk.StringVar(value="Factura")
        box = ttk.Frame(frm)
        box.grid(row=0, column=1, sticky="w")
        ttk.Radiobutton(box, text="Factura", variable=self.var_tipo, value="Factura").pack(side="left", padx=2)
        ttk.Radiobutton(box, text="Guía", variable=self.var_tipo, value="Guía").pack(side="left", padx=2)

        ttk.Label(frm, text="N° documento:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.var_numdoc = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_numdoc, width=24).grid(row=1, column=1, sticky="w")

        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Cancelar", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(btns, text="Vincular", command=self._ok).pack(side="right", padx=4)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

    def _ok(self):
        self.result = {
            "tipo_doc": self.var_tipo.get().strip() or None,
            "numero_documento": self.var_numdoc.get().strip() or None,
        }
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


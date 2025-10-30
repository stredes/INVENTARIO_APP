from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional


class ReceptionDialog(tk.Toplevel):
    """Diálogo simple para recepcionar una OC.

    Devuelve en `result` un dict con:
      - numero_documento: str | None
      - f_documento: str | None (dd/mm/YYYY)
      - f_contable: str | None
      - f_venc: str | None
      - receive_all: bool
    """

    def __init__(self, parent: tk.Misc, *, title: str = "Recepcionar OC"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self.result: Optional[dict] = None

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="N° documento:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.var_numdoc = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_numdoc, width=24).grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="F. documento (dd/mm/aaaa):").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.var_fdoc = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_fdoc, width=16).grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="F. contable (dd/mm/aaaa):").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        self.var_fcont = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_fcont, width=16).grid(row=2, column=1, sticky="w")

        ttk.Label(frm, text="F. venc. (dd/mm/aaaa):").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        self.var_fvenc = tk.StringVar()
        ttk.Entry(frm, textvariable=self.var_fvenc, width=16).grid(row=3, column=1, sticky="w")

        self.var_all = tk.BooleanVar(value=True)
        ttk.Checkbutton(frm, text="Recepcionar todo lo pendiente", variable=self.var_all).grid(row=4, column=0, columnspan=2, sticky="w", padx=4, pady=(8, 4))

        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Cancelar", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(btns, text="Aceptar", command=self._ok).pack(side="right", padx=4)

        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self._cancel())

    def _ok(self) -> None:
        self.result = dict(
            numero_documento=self.var_numdoc.get().strip() or None,
            f_documento=self.var_fdoc.get().strip() or None,
            f_contable=self.var_fcont.get().strip() or None,
            f_venc=self.var_fvenc.get().strip() or None,
            receive_all=bool(self.var_all.get()),
        )
        self.destroy()

    def _cancel(self) -> None:
        self.result = None
        self.destroy()


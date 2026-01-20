from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, List, Tuple, Optional


class ReceptionQtyDialog(tk.Toplevel):
    """
    Permite editar cantidades a recepcionar por línea para una OC.

    Recibe una lista de líneas: (prod_id, nombre, pendiente)
    Devuelve en `result` un dict {prod_id: qty_a_recibir} o None si cancela.
    """

    def __init__(self, parent: tk.Misc, lines: List[Tuple[int, str, int]], *, title: str = "Cantidades a recepcionar"):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.grab_set()

        self._lines = lines
        self._vars: Dict[int, tk.IntVar] = {}
        self.result: Optional[Dict[int, int]] = None

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        header = ttk.Frame(frm)
        header.grid(row=0, column=0, sticky="we")
        ttk.Label(header, text="Producto", width=40).grid(row=0, column=0, sticky="w")
        ttk.Label(header, text="Pendiente", width=12, anchor="center").grid(row=0, column=1)
        ttk.Label(header, text="A recibir", width=12, anchor="center").grid(row=0, column=2)

        body = ttk.Frame(frm)
        body.grid(row=1, column=0, sticky="we")

        for r, (pid, name, pending) in enumerate(lines, start=0):
            ttk.Label(body, text=str(name), width=40).grid(row=r, column=0, sticky="w", padx=2, pady=2)
            ttk.Label(body, text=str(pending), width=12, anchor="center").grid(row=r, column=1, padx=2)
            v = tk.IntVar(value=int(pending))
            self._vars[int(pid)] = v
            sp = ttk.Spinbox(body, from_=0, to=max(0, int(pending)), textvariable=v, width=10, justify="center")
            sp.grid(row=r, column=2, padx=2)

        ctrl = ttk.Frame(frm)
        ctrl.grid(row=2, column=0, sticky="e", pady=(8, 0))
        ttk.Button(ctrl, text="Cancelar", style="Danger.TButton", command=self._cancel).pack(side="right", padx=4)
        ttk.Button(ctrl, text="Aceptar", command=self._ok).pack(side="right", padx=4)

        self.bind("<Return>", lambda _e=None: self._ok())
        self.bind("<Escape>", lambda _e=None: self._cancel())

    def _ok(self):
        res: Dict[int, int] = {}
        for pid, var in self._vars.items():
            try:
                qty = int(var.get())
            except Exception:
                qty = 0
            res[int(pid)] = max(0, int(qty))
        # Validación mínima: al menos una línea con > 0
        if not any(q > 0 for q in res.values()):
            if not messagebox.askyesno("Recepción", "No seleccionó cantidades a recepcionar. ¿Continuar?"):
                return
        self.result = res
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()


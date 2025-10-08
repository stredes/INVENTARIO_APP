from __future__ import annotations
import sys
import subprocess
import tkinter as tk
from tkinter import ttk
from typing import List, Optional

try:
    import win32print  # Solo Windows
except Exception:
    win32print = None


def _list_printers() -> List[str]:
    """
    Devuelve lista de nombres de impresoras instaladas.
    - Windows: via win32print.EnumPrinters
    - Linux/macOS: via `lpstat -p` (si existe)
    """
    if sys.platform.startswith("win") and win32print:
        try:
            return [p[2] for p in win32print.EnumPrinters(2)]
        except Exception:
            return []
    try:
        out = subprocess.check_output(["lpstat", "-p"], text=True, stderr=subprocess.DEVNULL)
        names: List[str] = []
        for line in out.splitlines():
            if line.startswith("printer "):
                parts = line.split()
                if len(parts) >= 2:
                    names.append(parts[1])
        return names
    except Exception:
        return []


class PrinterSelectDialog(tk.Toplevel):
    """
    Diálogo modal para elegir impresora.
    self.result -> nombre seleccionado o None si cancela.
    """
    def __init__(self, master: tk.Misc, initial: Optional[str] = None):
        super().__init__(master)
        self.title("Seleccionar impresora")
        self.resizable(False, False)
        self.result: Optional[str] = None

        printers = _list_printers()
        if not printers:
            printers = ["(No se detectaron impresoras en el sistema)"]

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Impresora:").grid(row=0, column=0, sticky="e", padx=6, pady=6)

        self.var = tk.StringVar(value=initial if initial in printers else printers[0])
        self.cmb = ttk.Combobox(frm, textvariable=self.var, values=printers,
                                width=48, state="readonly")
        self.cmb.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        btns = ttk.Frame(frm)
        btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(12, 0))
        btn_accept = ttk.Button(btns, text="Aceptar", command=self._on_accept)
        btn_cancel = ttk.Button(btns, text="Cancelar", command=self._on_cancel)
        btn_accept.pack(side="right", padx=5)
        btn_cancel.pack(side="right")

        frm.columnconfigure(1, weight=1)
        self.grab_set()
        self.transient(master)
        self.wait_visibility()
        self.cmb.focus_set()

        # Soporte para Enter/Escape
        self.bind("<Return>", lambda e: self._on_accept())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _on_accept(self):
        val = self.var.get().strip()
        if val and "No se detectaron" not in val:
            self.result = val
        else:
            self.result = None
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

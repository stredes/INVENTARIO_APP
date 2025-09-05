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
        # PRINTER_ENUM_LOCAL (2): impresoras locales instaladas
        return [p[2] for p in win32print.EnumPrinters(2)]
    # Otros SO: intentar lpstat
    try:
        out = subprocess.check_output(["lpstat", "-p"], text=True, stderr=subprocess.DEVNULL)
        names: List[str] = []
        for line in out.splitlines():
            # formato típico: "printer HP_LaserJet_Pro ... "
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
            printers = ["(No se detectaron impresoras)"]

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Impresora:").grid(row=0, column=0, sticky="e", padx=6, pady=6)

        self.var = tk.StringVar(value=initial or (printers[0] if printers else ""))
        self.cmb = ttk.Combobox(frm, textvariable=self.var, values=printers,
                                width=48, state="readonly")
        self.cmb.grid(row=0, column=1, sticky="we", padx=6, pady=6)

        btns = ttk.Frame(frm)
        btns.grid(row=1, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancelar", command=self._on_cancel).pack(side="right", padx=5)
        ttk.Button(btns, text="Aceptar", command=self._on_accept).pack(side="right")

        frm.columnconfigure(1, weight=1)
        self.grab_set()
        self.transient(master)
        self.wait_visibility()
        self.cmb.focus_set()

    def _on_accept(self):
        val = self.var.get().strip()
        if val and "No se detectaron" not in val and "(pywin32" not in val:
            self.result = val
        else:
            self.result = None
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List


class BluetoothScanDialog(tk.Toplevel):
    """
    Diálogo muy simple para explorar dispositivos Bluetooth cercanos.
    - Requiere 'bleak' instalado para realizar el escaneo BLE.
    - Si no está disponible, muestra instrucciones.
    Este diálogo es informativo; la impresión depende de que la
    impresora esté instalada como impresora de Windows.
    """

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.title("Explorar Bluetooth (experimental)")
        self.resizable(True, True)

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        self.lst = tk.Listbox(frm, height=10)
        self.lst.pack(fill="both", expand=True)

        bar = ttk.Frame(frm)
        bar.pack(fill="x", pady=(8, 0))
        ttk.Button(bar, text="Escanear", command=self._scan).pack(side="left")
        ttk.Button(bar, text="Cerrar", command=self.destroy).pack(side="right")

        self._info = ttk.Label(frm, text="", foreground="#666")
        self._info.pack(anchor="w", pady=(6, 0))

        self.transient(master)
        self.grab_set()
        self.wait_visibility()

    def _scan(self) -> None:
        try:
            import asyncio
            from bleak import BleakScanner  # type: ignore
        except Exception:
            messagebox.showinfo(
                "Bluetooth",
                "Para escanear dispositivos BLE instala el paquete 'bleak' (pip install bleak).\n"
                "Si tu impresora Bluetooth está instalada como impresora de Windows,\n"
                "aparecerá en el selector de impresoras estándar.",
                parent=self,
            )
            return

        self._info.configure(text="Buscando dispositivos…")
        self.lst.delete(0, "end")

        async def _do_scan():
            devs = await BleakScanner.discover(timeout=5.0)
            return devs

        try:
            devs = asyncio.run(_do_scan())
        except RuntimeError:
            # Si ya hay loop en ejecución (embedding), usar create_task
            loop = asyncio.get_event_loop()
            devs = loop.run_until_complete(_do_scan())
        except Exception as ex:
            messagebox.showerror("Bluetooth", f"Error al escanear: {ex}", parent=self)
            return

        if not devs:
            self._info.configure(text="No se encontraron dispositivos BLE.")
            return

        for d in devs:
            name = d.name or "(sin nombre)"
            self.lst.insert("end", f"{name}  [{d.address}]")
        self._info.configure(text="Doble clic para copiar dirección al portapapeles.")

        def _copy(_evt=None):
            sel = self.lst.curselection()
            if not sel:
                return
            text = self.lst.get(sel[0])
            addr = text.split("[")[-1].rstrip("]") if "[" in text else text
            try:
                self.clipboard_clear()
                self.clipboard_append(addr)
                self.update()
            except Exception:
                pass

        self.lst.bind("<Double-1>", _copy)


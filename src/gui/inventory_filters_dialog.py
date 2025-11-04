from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.reports.inventory_reports import InventoryFilter

class InventoryFiltersDialog(tk.Toplevel):
    """Diálogo modal para filtros + tipo de informe de inventario."""

    def __init__(self, master: tk.Misc, initial: Optional[InventoryFilter] = None):
        super().__init__(master)
        self.title("Filtros de Inventario")
        self.resizable(False, False)
        self.result: Optional[InventoryFilter] = None

        # Variables de filtro, con valores iniciales si se proveen
        self.var_rtype = tk.StringVar(value=getattr(initial, "report_type", "venta"))
        self.var_nombre = tk.StringVar(value=getattr(initial, "nombre_contains", ""))
        self.var_sku = tk.StringVar(value=getattr(initial, "sku_contains", ""))
        self.var_unidad = tk.StringVar(value=getattr(initial, "unidad_equals", ""))
        self.var_stock_min = tk.StringVar(value=str(getattr(initial, "stock_min", "") or ""))
        self.var_stock_max = tk.StringVar(value=str(getattr(initial, "stock_max", "") or ""))
        self.var_precio_min = tk.StringVar(value=str(getattr(initial, "precio_min", "") or ""))
        self.var_precio_max = tk.StringVar(value=str(getattr(initial, "precio_max", "") or ""))
        self.var_bajo_min = tk.BooleanVar(value=getattr(initial, "solo_bajo_minimo", False))
        self.var_sobre_max = tk.BooleanVar(value=getattr(initial, "solo_sobre_maximo", False))
        self.var_order = tk.StringVar(value=getattr(initial, "order_by", "nombre"))
        # Trazabilidad (exclusivos)
        self.var_lote = tk.StringVar(value=getattr(initial, "lote_contains", ""))
        self.var_serie = tk.StringVar(value=getattr(initial, "serie_contains", ""))
        self.var_asc = tk.BooleanVar(value=getattr(initial, "order_asc", True))

        pad = dict(padx=6, pady=4)
        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # Tipo de informe
        ttk.Label(frm, text="Tipo de informe:").grid(row=0, column=0, sticky="e", **pad)
        ttk.Combobox(frm, textvariable=self.var_rtype,
                     values=["venta", "compra", "completo"], state="readonly",
                     width=12).grid(row=0, column=1, sticky="w", **pad)

        # Nombre
        ttk.Label(frm, text="Nombre contiene:").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.var_nombre, width=28).grid(row=1, column=1, sticky="w", **pad)

        # SKU
        ttk.Label(frm, text="SKU contiene:").grid(row=2, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.var_sku, width=28).grid(row=2, column=1, sticky="w", **pad)

        # Unidad
        ttk.Label(frm, text="Unidad =").grid(row=3, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.var_unidad, width=12).grid(row=3, column=1, sticky="w", **pad)

        # Stock min/max
        ttk.Label(frm, text="Stock min/max:").grid(row=4, column=0, sticky="e", **pad)
        r4 = ttk.Frame(frm)
        r4.grid(row=4, column=1, sticky="w")
        ttk.Entry(r4, textvariable=self.var_stock_min, width=8).pack(side="left")
        ttk.Label(r4, text=" - ").pack(side="left")
        ttk.Entry(r4, textvariable=self.var_stock_max, width=8).pack(side="left")

        # Precio min/max
        ttk.Label(frm, text="Precio min/max (*venta/compra):").grid(row=5, column=0, sticky="e", **pad)
        r5 = ttk.Frame(frm)
        r5.grid(row=5, column=1, sticky="w")
        ttk.Entry(r5, textvariable=self.var_precio_min, width=8).pack(side="left")
        ttk.Label(r5, text=" - ").pack(side="left")
        ttk.Entry(r5, textvariable=self.var_precio_max, width=8).pack(side="left")

        # Lote / Serie (exclusivos)
        ttk.Label(frm, text="Lote contiene:").grid(row=6, column=0, sticky="e", **pad)
        e_lote = ttk.Entry(frm, textvariable=self.var_lote, width=28)
        e_lote.grid(row=6, column=1, sticky="w", **pad)
        ttk.Label(frm, text="Serie contiene:").grid(row=7, column=0, sticky="e", **pad)
        e_serie = ttk.Entry(frm, textvariable=self.var_serie, width=28)
        e_serie.grid(row=7, column=1, sticky="w", **pad)
        # Enforce exclusivity live
        def _sync_exclusive(*_):
            try:
                if (self.var_lote.get() or '').strip():
                    if (self.var_serie.get() or '').strip():
                        self.var_serie.set('')
                elif (self.var_serie.get() or '').strip():
                    if (self.var_lote.get() or '').strip():
                        self.var_lote.set('')
            except Exception:
                pass
        try:
            self.var_lote.trace_add('write', _sync_exclusive)
            self.var_serie.trace_add('write', _sync_exclusive)
        except Exception:
            pass

        # Solo bajo mínimo / sobre máximo
        ttk.Checkbutton(frm, text="Solo bajo mínimo", variable=self.var_bajo_min).grid(row=8, column=0, sticky="w", columnspan=2, **pad)
        ttk.Checkbutton(frm, text="Solo sobre máximo", variable=self.var_sobre_max).grid(row=9, column=0, sticky="w", columnspan=2, **pad)

        # Ordenar por
        ttk.Label(frm, text="Ordenar por:").grid(row=10, column=0, sticky="e", **pad)
        r8 = ttk.Frame(frm)
        r8.grid(row=10, column=1, sticky="w")
        ttk.Combobox(r8, textvariable=self.var_order,
                     values=["nombre", "sku", "stock", "p_compra", "p_venta"],
                     width=12, state="readonly").pack(side="left", padx=(0, 6))
        ttk.Checkbutton(r8, text="Asc", variable=self.var_asc).pack(side="left")

        # Botones
        btns = ttk.Frame(frm)
        btns.grid(row=11, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(btns, text="Cancelar", command=self._on_cancel).pack(side="right", padx=5)
        ttk.Button(btns, text="Aceptar", command=self._on_accept).pack(side="right")

        for i in range(2):
            frm.columnconfigure(i, weight=1)

        self.grab_set()
        self.transient(master)
        self.wait_visibility()
        self.focus()

    def _to_int(self, s: str) -> Optional[int]:
        s = s.strip()
        try:
            return int(s) if s else None
        except ValueError:
            return None

    def _to_float(self, s: str) -> Optional[float]:
        s = s.strip()
        try:
            return float(s) if s else None
        except ValueError:
            return None

    def _on_accept(self):
        self.result = InventoryFilter(
            report_type=self.var_rtype.get(),
            nombre_contains=self.var_nombre.get().strip() or None,
            sku_contains=self.var_sku.get().strip() or None,
            unidad_equals=self.var_unidad.get().strip() or None,
            stock_min=self._to_int(self.var_stock_min.get()),
            stock_max=self._to_int(self.var_stock_max.get()),
            precio_min=self._to_float(self.var_precio_min.get()),
            precio_max=self._to_float(self.var_precio_max.get()),
            solo_bajo_minimo=self.var_bajo_min.get(),
            solo_sobre_maximo=self.var_sobre_max.get(),
            order_by=self.var_order.get(),
            order_asc=self.var_asc.get(),
            lote_contains=(self.var_lote.get().strip() or None),
            serie_contains=(self.var_serie.get().strip() or None),
        )
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()

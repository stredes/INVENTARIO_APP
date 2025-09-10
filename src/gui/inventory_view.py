# src/gui/inventory_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
import webbrowser

from src.data.database import get_session
from src.data.models import Product
from src.data.repository import ProductRepository
from src.utils.helpers import (
    get_inventory_limits,
    set_inventory_limits,
    get_inventory_refresh_ms,
    set_inventory_refresh_ms,
)

# ==== Reportes / filtros ====
from src.reports.inventory_reports import (
    InventoryFilter,
    InventoryReportService,
    generate_inventory_xlsx,
    print_inventory_report,
)
from src.gui.inventory_filters_dialog import InventoryFiltersDialog
from src.gui.printer_select_dialog import PrinterSelectDialog

# Rejilla real (tksheet) o fallback Treeview
from src.gui.widgets.grid_table import GridTable


class InventoryView(ttk.Frame):
    """
    Vista de Inventario con grid real (tksheet) o fallback Treeview:
    - Resaltado por min/max (colores críticos persistentes).
    - Auto-refresco configurable.
    - Filtros + Exportar XLSX + Imprimir.
    - Columnas por 'venta' / 'compra' / 'completo'.
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        # --- Estado / repos ---
        self.session = get_session()
        self.repo = ProductRepository(self.session)

        self._auto_job: Optional[str] = None
        self._auto_enabled = tk.BooleanVar(value=True)

        # Configuración inicial
        min_v, max_v = get_inventory_limits()
        self._crit_min = tk.IntVar(value=min_v)
        self._crit_max = tk.IntVar(value=max_v)
        self._refresh_ms = tk.IntVar(value=get_inventory_refresh_ms())

        # Filtro activo
        self._current_filter = InventoryFilter()

        # Mapeo de filas mostradas → IDs (para selección/imprimir/exportar)
        self._last_row_ids: List[int] = []

        # --- Encabezado ---
        header = ttk.Frame(self)
        header.pack(fill="x", expand=False)
        ttk.Label(header, text="Inventario (refresco automático)", font=("", 11, "bold")).pack(side="left")

        ttk.Button(header, text="Imprimir", command=self._on_print).pack(side="right", padx=4)
        ttk.Button(header, text="Exportar XLSX", command=self._on_export_xlsx).pack(side="right", padx=4)
        ttk.Button(header, text="Filtros…", command=self._on_filters).pack(side="right", padx=4)
        ttk.Button(header, text="Refrescar ahora", command=self.refresh_table).pack(side="right", padx=4)
        ttk.Checkbutton(header, text="Auto", variable=self._auto_enabled, command=self._on_toggle_auto).pack(side="right")

        # --- Tabla (GridTable) ---
        self.table = GridTable(self)
        self.table.pack(fill="both", expand=True, pady=(8, 10))

        # --- Panel Configuración ---
        cfg = ttk.Labelframe(self, text="Configuración de límites críticos y refresco", padding=10)
        cfg.pack(fill="x", expand=False)

        ttk.Label(cfg, text="Mínimo crítico:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(cfg, from_=0, to=999999, textvariable=self._crit_min, width=10).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(cfg, text="Máximo crítico:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(cfg, from_=0, to=999999, textvariable=self._crit_max, width=10).grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(cfg, text="Refresco (ms):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        ttk.Spinbox(cfg, from_=500, to=60000, increment=500, textvariable=self._refresh_ms, width=10).grid(row=0, column=5, sticky="w", padx=4, pady=4)

        ttk.Button(cfg, text="Guardar", command=self._on_save_config).grid(row=0, column=6, padx=8)
        for i in range(7):
            cfg.columnconfigure(i, weight=1)

        # Primera carga + auto
        self.refresh_table()
        self._schedule_auto()

    # ====================== columnas y filas ====================== #
    def _columns_for(self, report_type: str) -> List[str]:
        if report_type == "venta":
            return ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Venta"]
        if report_type == "compra":
            return ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Compra"]
        return ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Compra", "P. Venta"]

    def _rows_from_products(self, products: List[Product], report_type: str):
        """
        Devuelve (rows, colors, ids)
          rows  : lista de listas con valores para la tabla
          colors: color de fondo por fila (None / "#ffdddd" / "#fff6cc")
          ids   : IDs de producto para mapear selección
        """
        rows, colors, ids = [], [], []
        min_v = int(self._crit_min.get())
        max_v = int(self._crit_max.get())

        for p in products:
            stock = int(p.stock_actual or 0)
            color = None
            if stock < min_v:
                color = "#ffdddd"    # bajo
            elif stock > max_v:
                color = "#fff6cc"    # alto

            base = [p.id, p.nombre, p.sku, p.unidad_medida or "", stock]
            if report_type == "venta":
                row = base + [f"{float(p.precio_venta or 0):.2f}"]
            elif report_type == "compra":
                row = base + [f"{float(p.precio_compra or 0):.2f}"]
            else:
                row = base + [f"{float(p.precio_compra or 0):.2f}", f"{float(p.precio_venta or 0):.2f}"]

            rows.append(row); colors.append(color); ids.append(int(p.id))
        return rows, colors, ids

    # ================================ UI actions ================================ #
    def refresh_table(self):
        """Carga productos sin filtros y pinta por min/max (grid real si hay tksheet)."""
        try:
            products: List[Product] = (
                self.session.query(Product)
                .order_by(Product.nombre.asc())
                .all()
            )
            self._populate_table(products)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo refrescar el inventario:\n{e}")

    def _populate_table(self, products: List[Product]) -> None:
        cols = self._columns_for(self._current_filter.report_type)
        rows, colors, ids = self._rows_from_products(products, self._current_filter.report_type)
        self._last_row_ids = ids

        # 1) Cargar datos en la grilla (tksheet o fallback Treeview)
        self.table.set_data(cols, rows)

        # 2) Aplicar colores críticos por fila
        #    GridTable se encarga de no pisar el zebrado y de resaltar en tksheet.
        try:
            self.table.set_row_backgrounds(colors)
        except Exception:
            pass

        # 3) Si el tema cambió en caliente, re-aplica paleta
        try:
            self.table.theme_refresh()
        except Exception:
            pass

    def _on_save_config(self):
        """Persiste límites y ms de refresco, reprograma el auto y refresca la tabla."""
        try:
            min_v = int(self._crit_min.get())
            max_v = int(self._crit_max.get())
            ms = int(self._refresh_ms.get())
            set_inventory_limits(min_v, max_v)
            set_inventory_refresh_ms(ms)
            self._cancel_auto()
            self._schedule_auto()
            self.refresh_table()
            messagebox.showinfo("OK", "Configuración guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar configuración:\n{e}")

    def _on_toggle_auto(self):
        if self._auto_enabled.get():
            self._schedule_auto()
        else:
            self._cancel_auto()

    # ----------------------------- Auto-refresh ----------------------------- #
    def _tick(self):
        self.refresh_table()
        if self._auto_enabled.get():
            self._auto_job = self.after(self._refresh_ms.get(), self._tick)

    def _schedule_auto(self):
        if self._auto_enabled.get():
            self._auto_job = self.after(self._refresh_ms.get(), self._tick)

    def _cancel_auto(self):
        if self._auto_job:
            try:
                self.after_cancel(self._auto_job)
            except Exception:
                pass
            self._auto_job = None

    # ---------------------- Filtros, exportación, impresión ---------------------- #
    def _selected_ids(self) -> List[int]:
        """IDs de filas seleccionadas (tksheet o fallback Treeview)."""
        # tksheet
        if hasattr(self.table, "sheet"):
            try:
                sel_rows = sorted(set(self.table.sheet.get_selected_rows()))
            except Exception:
                try:
                    cells = self.table.sheet.get_selected_cells()
                    sel_rows = sorted({r for r, _c in cells})
                except Exception:
                    sel_rows = []
            return [self._last_row_ids[i] for i in sel_rows if 0 <= i < len(self._last_row_ids)]

        # Treeview fallback
        tv = getattr(self.table, "_fallback", None)
        ids: List[int] = []
        if tv is not None:
            for iid in tv.selection():
                try:
                    idx = tv.index(iid)
                    ids.append(self._last_row_ids[idx])
                except Exception:
                    pass
        return ids

    def _on_filters(self):
        dlg = InventoryFiltersDialog(self, initial=self._current_filter)
        self.wait_window(dlg)
        if dlg.result:
            self._current_filter = dlg.result
            try:
                svc = InventoryReportService(self.session)
                products = svc.fetch(self._current_filter)
                self._populate_table(products)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo aplicar filtros:\n{e}")

    def _on_export_xlsx(self):
        ids = self._selected_ids()
        flt = self._current_filter
        if ids:
            flt = InventoryFilter(**{**flt.__dict__, "ids_in": ids})
        try:
            path = generate_inventory_xlsx(self.session, flt, "Listado de Inventario")
            webbrowser.open(str(path))
            messagebox.showinfo("OK", f"Exportado a:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def _on_print(self):
        ids = self._selected_ids()
        flt = self._current_filter
        if ids:
            flt = InventoryFilter(**{**flt.__dict__, "ids_in": ids})

        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return

        printer_name = dlg.result
        try:
            path = print_inventory_report(self.session, flt, "Listado de Inventario", printer_name=printer_name)
            messagebox.showinfo("Impresión", f"Enviado a '{printer_name}'.\nArchivo: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir:\n{e}")

    # --------- Interfaz homogénea con MainWindow --------- #
    def print_current(self):
        self._on_print()

    def refresh_lookups(self):
        self.refresh_table()

    def destroy(self):
        self._cancel_auto()
        super().destroy()

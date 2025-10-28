# src/gui/inventory_view.py
# -*- coding: utf-8 -*-
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
    get_inventory_refresh_ms,
)

# ==== Reportes / filtros ====
from src.reports.inventory_reports import (
    InventoryFilter,
    InventoryReportService,
    generate_inventory_xlsx,
    print_inventory_report,
)
from src.gui.inventory_filters_dialog import InventoryFiltersDialog
from src.utils.inventory_thresholds import get_thresholds as _get_prod_limits, set_thresholds as _set_prod_limits
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
    - Footer con totales: Σ P. Compra y Σ P. Venta (de los productos mostrados).
    """

    # ============================ init / estado ============================ #
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
        ttk.Label(
            header,
            text="Inventario (refresco automático)",
            font=("", 11, "bold"),
        ).pack(side="left")

        ttk.Button(header, text="Imprimir", command=self._on_print).pack(side="right", padx=4)
        ttk.Button(header, text="Exportar XLSX", command=self._on_export_xlsx).pack(side="right", padx=4)
        ttk.Button(header, text="Filtros…", command=self._on_filters).pack(side="right", padx=4)
        ttk.Button(header, text="Refrescar ahora", command=self.refresh_table).pack(side="right", padx=4)
        ttk.Checkbutton(header, text="Auto", variable=self._auto_enabled, command=self._on_toggle_auto).pack(side="right")

        # --- Tabla (GridTable) ---
        self.table = GridTable(self)
        self.table.pack(fill="both", expand=True, pady=(8, 10))

        # --- Footer de totales ---
        # Muestra Σ P. Compra y Σ P. Venta de lo actualmente listado
        footer = ttk.Frame(self)
        footer.pack(fill="x", expand=False, pady=(0, 10))

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(0, 6))

        # Etiquetas alineadas a la derecha
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)
        footer.grid_columnconfigure(2, weight=0)
        footer.grid_columnconfigure(3, weight=0)

        ttk.Label(footer, text="Totales mostrados:", font=("", 10, "bold")).grid(row=0, column=0, sticky="e", padx=6)

        ttk.Label(footer, text="Σ P. Compra:").grid(row=0, column=1, sticky="e", padx=(6, 2))
        self._lbl_total_compra = ttk.Label(footer, text="$ 0.00", font=("", 10, "bold"))
        self._lbl_total_compra.grid(row=0, column=2, sticky="w", padx=(0, 12))

        ttk.Label(footer, text="Σ P. Venta:").grid(row=0, column=3, sticky="e", padx=(6, 2))
        self._lbl_total_venta = ttk.Label(footer, text="$ 0.00", font=("", 10, "bold"))
        self._lbl_total_venta.grid(row=0, column=4, sticky="w")

        # Leyenda (colorímetro) en la esquina inferior derecha
        self._legend = ttk.Frame(footer)
        self._legend.grid(row=0, column=5, sticky="e", padx=6)
        self._build_legend()

        # --- Límites por producto seleccionado ---
        prod_cfg = ttk.Labelframe(self, text="Límites críticos del producto seleccionado", padding=10)
        prod_cfg.pack(fill="x", expand=False, pady=(6, 10))
        self._sel_min = tk.IntVar(value=0)
        self._sel_max = tk.IntVar(value=0)
        ttk.Label(prod_cfg, text="Mínimo:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(prod_cfg, from_=0, to=999999, textvariable=self._sel_min, width=10).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(prod_cfg, text="Máximo:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(prod_cfg, from_=0, to=999999, textvariable=self._sel_max, width=10).grid(row=0, column=3, sticky="w", padx=4, pady=4)
        ttk.Button(prod_cfg, text="Guardar límites del producto", command=self._on_save_selected_limits).grid(row=0, column=4, padx=8)

        # Primera carga + auto
        self.refresh_table()
        self._schedule_auto()

    # ====================== columnas y filas ====================== #
    def _columns_for(self, report_type: str) -> List[str]:
        """Define las columnas visibles según el tipo de reporte."""
        if report_type == "venta":
            return ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Venta"]
        if report_type == "compra":
            return ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Compra"]
        return ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Compra", "P. Venta"]

    def _rows_from_products(self, products: List[Product], report_type: str):
        """
        Devuelve (rows, colors, ids)
          rows  : lista de listas con valores para la tabla
          colors: color de fondo por fila (None / rango por color)
          ids   : IDs de producto para mapear selección
        """
        rows, colors, ids = [], [], []
        min_def = int(self._crit_min.get())
        max_def = int(self._crit_max.get())

        for p in products:
            stock = int(p.stock_actual or 0)
            # lee límites por producto si existen; si no, usa defaults
            min_v, max_v = _get_prod_limits(int(p.id), min_def, max_def)
            # Colores por rango respecto a límites
            very_low_thr = max(0, int(min_v * 0.5))
            very_high_thr = int(max_v * 1.25)
            color = None
            if stock <= very_low_thr:
                color = "#ffb3b3"    # muy bajo (rojo fuerte)
            elif stock < min_v:
                color = "#ffdddd"    # bajo (rojo claro)
            elif stock > very_high_thr:
                color = "#ffe08a"    # muy alto (amarillo/naranja)
            elif stock > max_v:
                color = "#fff6cc"    # alto (amarillo claro)

            base = [p.id, p.nombre, p.sku, p.unidad_medida or "", stock]
            if report_type == "venta":
                row = base + [self._fmt_money(p.precio_venta)]
            elif report_type == "compra":
                row = base + [self._fmt_money(p.precio_compra)]
            else:
                row = base + [self._fmt_money(p.precio_compra), self._fmt_money(p.precio_venta)]

            rows.append(row)
            colors.append(color)
            ids.append(int(p.id))
        return rows, colors, ids

    # ======================= helpers de totales / formato ======================= #
    @staticmethod
    def _fmt_money(value) -> str:
        """Formatea números a '$ 1,234.56'. (Cambiar si prefieres es-CL exacto)."""
        try:
            return f"$ {float(value or 0):,.2f}"
        except Exception:
            return "$ 0.00"

    @staticmethod
    def _compute_totals(products: List[Product]) -> tuple[float, float]:
        """
        Suma precios unitarios sobre la lista mostrada.
        Retorna: (total_compra, total_venta)
        """
        total_compra = 0.0
        total_venta = 0.0
        for p in products:
            total_compra += float(p.precio_compra or 0)
            total_venta += float(p.precio_venta or 0)
        return total_compra, total_venta

    def _update_footer_totals(self, products: List[Product]) -> None:
        """Actualiza las etiquetas del footer con los totales actuales."""
        total_compra, total_venta = self._compute_totals(products)
        self._lbl_total_compra.config(text=self._fmt_money(total_compra))
        self._lbl_total_venta.config(text=self._fmt_money(total_venta))

    # ================================ acciones UI ================================ #
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
        """
        Pinta la tabla con productos y aplica colores críticos.
        También actualiza el footer de totales con base en 'products'.
        """
        cols = self._columns_for(self._current_filter.report_type)
        rows, colors, ids = self._rows_from_products(products, self._current_filter.report_type)
        self._last_row_ids = ids

        # 1) Cargar datos en la grilla (tksheet o fallback Treeview)
        self.table.set_data(cols, rows)

        # 2) Refrescar tema (si cambió) y luego aplicar colores críticos por fila
        try:
            self.table.theme_refresh()
        except Exception:
            pass
        try:
            self.table.set_row_backgrounds(colors)
        except Exception:
            pass

        # 4) Actualizar totales del footer
        self._update_footer_totals(products)
        # 5) Enlazar selección → actualizar panel límites
        try:
            if hasattr(self.table, "sheet"):
                self.table.sheet.extra_bindings([("cell_select", lambda e: self._update_selected_limits_panel())])
            tv = getattr(self.table, "_fallback", None)
            if tv is not None:
                tv.bind("<<TreeviewSelect>>", lambda _e: self._update_selected_limits_panel())
        except Exception:
            pass

    # ----------------------- Leyenda de colores ----------------------- #
    def _build_legend(self):
        """Leyenda robusta al cambio de tema: usa Canvas para los parches de color."""
        for c in self._legend.winfo_children():
            c.destroy()

        canvas = tk.Canvas(self._legend, height=16, highlightthickness=0, bd=0)
        canvas.pack(side="left")

        items = [
            ("#ffb3b3", "Muy bajo"),
            ("#ffdddd", "Bajo"),
            ("#fff6cc", "Alto"),
            ("#ffe08a", "Muy alto"),
        ]
        x = 0
        for color, label in items:
            canvas.create_rectangle(x, 2, x + 18, 14, fill=color, outline="#808080")
            x += 22
            t = ttk.Label(self._legend, text=label)
            t.pack(side="left", padx=(2, 8))
        # Ajustar ancho del canvas a los parches dibujados
        canvas.config(width=x)

    # ---------------- Límites por producto (panel) ---------------- #
    def _update_selected_limits_panel(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        pid = int(ids[0])
        mn_def = int(self._crit_min.get()); mx_def = int(self._crit_max.get())
        mn, mx = _get_prod_limits(pid, mn_def, mx_def)
        try:
            self._sel_min.set(int(mn)); self._sel_max.set(int(mx))
        except Exception:
            pass

    def _on_save_selected_limits(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Inventario", "Seleccione un producto en la tabla.")
            return
        pid = int(ids[0])
        try:
            mn = int(self._sel_min.get()); mx = int(self._sel_max.get())
        except Exception:
            messagebox.showwarning("Inventario", "Valores inválidos para mínimo/máximo.")
            return
        if mn < 0 or mx < 0:
            messagebox.showwarning("Inventario", "Los límites deben ser ≥ 0.")
            return
        if mx and mn and mx < mn:
            messagebox.showwarning("Inventario", "Máximo no puede ser menor que Mínimo.")
            return
        _set_prod_limits(pid, mn, mx)
        self.refresh_table()

    # (El bloque de configuración por defecto se eliminó por solicitud)

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
        # tksheet backend
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
        """Abre diálogo de filtros, aplica y actualiza tabla + totales."""
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
        """Exporta XLSX con filtro actual (o con selección de IDs si la hay)."""
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
        """Imprime con filtro actual (o con selección de IDs si la hay)."""
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

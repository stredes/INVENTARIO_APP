from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
from pathlib import Path
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
from src.gui.printer_select_dialog import PrinterSelectDialog  # diálogo de selección de impresora


class InventoryView(ttk.Frame):
    """
    Vista de Inventario con:
    - Tabla de productos y stock actual
    - Resaltado por límites críticos (min / max)
    - Auto-refresco configurable (ms)
    - Panel de configuración para límites y refresco
    - Filtros avanzados + Exportar XLSX + Imprimir (con selección de impresora)
    - Treeview que se adapta a 'venta' / 'compra' / 'completo'
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

        # Filtro activo para informes (estado local)
        self._current_filter = InventoryFilter()  # report_type por defecto viene del dataclass

        # --- Encabezado ---
        header = ttk.Frame(self)
        header.pack(fill="x", expand=False)
        ttk.Label(header, text="Inventario (refresco automático)", font=("", 11, "bold")).pack(side="left")

        # Botones: Filtros, Exportar, Imprimir
        ttk.Button(header, text="Imprimir", command=self._on_print).pack(side="right", padx=4)
        ttk.Button(header, text="Exportar XLSX", command=self._on_export_xlsx).pack(side="right", padx=4)
        ttk.Button(header, text="Filtros…", command=self._on_filters).pack(side="right", padx=4)

        ttk.Button(header, text="Refrescar ahora", command=self.refresh_table).pack(side="right", padx=4)
        ttk.Checkbutton(header, text="Auto", variable=self._auto_enabled, command=self._on_toggle_auto).pack(side="right")

        # --- Tabla ---
        self.tree = ttk.Treeview(
            self,
            columns=("id", "nombre", "sku", "unidad", "stock", "p_compra", "p_venta"),
            show="headings",
            height=16,
            selectmode="extended",   # Selección múltiple para informes parciales
        )
        self.tree.pack(fill="both", expand=True, pady=(8, 10))

        # Tags (colores por estado de stock)
        self.tree.tag_configure("low", background="#ffdddd")      # rojo claro (stock < min)
        self.tree.tag_configure("high", background="#fff6cc")     # amarillo claro (stock > max)
        self.tree.tag_configure("ok", background="")              # normal

        # Aplicar columnas al tipo inicial
        self._apply_tree_columns(self._current_filter.report_type)

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

    # -------- Helpers de Treeview (columnas dinámicas) --------
    def _apply_tree_columns(self, report_type: str):
        """
        Ajusta las columnas del Treeview según el tipo de informe:
        - 'venta'   : ... + P. Venta
        - 'compra'  : ... + P. Compra
        - 'completo': ... + P. Compra + P. Venta
        """
        if report_type == "venta":
            cols = ("id", "nombre", "sku", "unidad", "stock", "p_venta")
            headers = {
                "id": "ID", "nombre": "Producto", "sku": "SKU",
                "unidad": "Unidad", "stock": "Stock", "p_venta": "P. Venta"
            }
            widths = {"id": 60, "nombre": 260, "sku": 140, "unidad": 80, "stock": 90, "p_venta": 100}
        elif report_type == "compra":
            cols = ("id", "nombre", "sku", "unidad", "stock", "p_compra")
            headers = {
                "id": "ID", "nombre": "Producto", "sku": "SKU",
                "unidad": "Unidad", "stock": "Stock", "p_compra": "P. Compra"
            }
            widths = {"id": 60, "nombre": 260, "sku": 140, "unidad": 80, "stock": 90, "p_compra": 100}
        else:  # completo
            cols = ("id", "nombre", "sku", "unidad", "stock", "p_compra", "p_venta")
            headers = {
                "id": "ID", "nombre": "Producto", "sku": "SKU",
                "unidad": "Unidad", "stock": "Stock", "p_compra": "P. Compra", "p_venta": "P. Venta"
            }
            widths = {"id": 60, "nombre": 260, "sku": 140, "unidad": 80, "stock": 90, "p_compra": 100, "p_venta": 100}

        self.tree["columns"] = cols
        for c in cols:
            self.tree.heading(c, text=headers[c])
            anchor = "e" if c in ("stock", "p_compra", "p_venta") else ("center" if c in ("id", "unidad") else "w")
            self.tree.column(c, width=widths[c], anchor=anchor)

    def _row_values_for(self, p: Product, report_type: str):
        base = [
            p.id,
            p.nombre,
            p.sku,
            p.unidad_medida or "",
            int(p.stock_actual or 0),
        ]
        if report_type == "venta":
            return tuple(base + [f"{float(p.precio_venta or 0):.2f}"])
        if report_type == "compra":
            return tuple(base + [f"{float(p.precio_compra or 0):.2f}"])
        # completo
        return tuple(base + [
            f"{float(p.precio_compra or 0):.2f}",
            f"{float(p.precio_venta or 0):.2f}",
        ])

    # ----------------------------------
    # UI actions
    # ----------------------------------
    def refresh_table(self):
        """Carga productos sin filtros y colorea por min/max."""
        min_v = self._crit_min.get()
        max_v = self._crit_max.get()
        if min_v < 0:
            min_v = 0; self._crit_min.set(0)
        if max_v < min_v:
            max_v = min_v; self._crit_max.set(min_v)

        try:
            # Limpiar grilla
            for iid in self.tree.get_children():
                self.tree.delete(iid)

            rows: List[Product] = (
                self.session.query(Product)
                .order_by(Product.nombre.asc())
                .all()
            )
            for p in rows:
                stock = int(p.stock_actual or 0)
                tag = "ok"
                if stock < min_v:
                    tag = "low"
                elif stock > max_v:
                    tag = "high"

                vals = self._row_values_for(p, self._current_filter.report_type)
                self.tree.insert("", "end", values=vals, tags=(tag,))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo refrescar el inventario:\n{e}")

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
        """Activa/desactiva el refresco automático."""
        if self._auto_enabled.get():
            self._schedule_auto()
        else:
            self._cancel_auto()

    # ----------------------------------
    # Auto-refresh (after)
    # ----------------------------------
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

    # ----------------------------------
    # Filtros, exportación e impresión
    # ----------------------------------
    def _selected_ids(self) -> List[int]:
        """IDs de filas seleccionadas (para imprimir/exportar solo selección)."""
        ids: List[int] = []
        for iid in self.tree.selection():
            vals = self.tree.item(iid, "values")
            if not vals:
                continue
            try:
                ids.append(int(vals[0]))
            except Exception:
                pass
        return ids

    def _on_filters(self):
        """Abre diálogo de filtros, aplica y repuebla grilla con resultados."""
        dlg = InventoryFiltersDialog(self, initial=self._current_filter)
        self.wait_window(dlg)
        if dlg.result:
            self._current_filter = dlg.result
            # Ajustar columnas del Treeview al tipo elegido
            self._apply_tree_columns(self._current_filter.report_type)
            self._refresh_table_with_filter()

    def _refresh_table_with_filter(self):
        """Consulta con InventoryReportService y repuebla la grilla coloreando por min/max."""
        try:
            for iid in self.tree.get_children():
                self.tree.delete(iid)

            svc = InventoryReportService(self.session)
            rows = svc.fetch(self._current_filter)

            min_v = self._crit_min.get()
            max_v = self._crit_max.get()
            for p in rows:
                stock = int(p.stock_actual or 0)
                tag = "ok"
                if stock < min_v:
                    tag = "low"
                elif stock > max_v:
                    tag = "high"

                vals = self._row_values_for(p, self._current_filter.report_type)
                self.tree.insert("", "end", values=vals, tags=(tag,))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo aplicar filtros:\n{e}")

    def _on_export_xlsx(self):
        """Genera un XLSX (todo o solo selección) y lo abre con la app asociada."""
        ids = self._selected_ids()
        flt = self._current_filter
        if ids:
            # Clona filtro actual y aplica selección
            flt = InventoryFilter(**{**flt.__dict__, "ids_in": ids})
        try:
            path = generate_inventory_xlsx(self.session, flt, "Listado de Inventario")
            webbrowser.open(str(path))
            messagebox.showinfo("OK", f"Exportado a:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def _on_print(self):
        """
        Genera el XLSX y lo envía a impresión:
        - Muestra diálogo para elegir impresora
        - Pasa el nombre elegido al backend (Excel/COM o LibreOffice --pt)
        """
        ids = self._selected_ids()
        flt = self._current_filter
        if ids:
            flt = InventoryFilter(**{**flt.__dict__, "ids_in": ids})

        # Selección de impresora
        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return  # Cancelado o no hay impresoras

        printer_name = dlg.result

        try:
            path = print_inventory_report(self.session, flt, "Listado de Inventario", printer_name=printer_name)
            messagebox.showinfo("Impresión", f"Enviado a '{printer_name}'.\nArchivo: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir:\n{e}")

    # ----------------------------------
    # Interfaz homogénea con MainWindow
    # ----------------------------------
    def refresh_lookups(self):
        self.refresh_table()

    def destroy(self):
        self._cancel_auto()
        super().destroy()

# src/gui/reports_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.data.database import get_session
from src.data.models import Customer, Supplier
from src.gui.widgets.grid_table import GridTable
from src.gui.printer_select_dialog import PrinterSelectDialog

# Agregador de reportes
from src.reports.report_center import (
    REPORTS,                 # catÃ¡logo de reportes
    fetch_preview,           # obtiene (columns, rows) para previsualizar
    export_report_xlsx,      # exporta a xlsx (o csv si falta openpyxl)
    print_report_generic,    # impresiÃ³n genÃ©rica (exporta y envÃ­a a impresora)
)

# Helpers lookups
def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def _one_month_ago_str() -> str:
    return (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")


class ReportsView(ttk.Frame):
    """
    Centro de Informes:
      - Selector de reporte (lista izquierda)
      - Filtros dinÃ¡micos por reporte
      - PrevisualizaciÃ³n en grilla
      - Exportar XLSX e Imprimir
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()

        # Estado de lookups
        self._customers: List[Customer] = []
        self._suppliers: List[Supplier] = []

        # Estado UI / filtros
        self._current_key: Optional[str] = None
        self._filter_vars: Dict[str, Any] = {}   # por reporte

        # Layout principal: Izquierda (selector) / Derecha (filtros + preview + acciones)
        root = ttk.Panedwindow(self, orient="horizontal")
        root.pack(fill="both", expand=True)

        # -------- Panel Izquierdo: lista de reportes --------
        left = ttk.Frame(root, padding=(0, 0, 8, 0))
        root.add(left, weight=1)

        ttk.Label(left, text="Informes disponibles", font=("", 10, "bold")).pack(anchor="w", pady=(0, 6))

        self.lst_reports = tk.Listbox(left, height=12, exportselection=False)
        self.lst_reports.pack(fill="both", expand=True)
        for k, meta in REPORTS.items():
            self.lst_reports.insert("end", meta["title"])
        self.lst_reports.bind("<<ListboxSelect>>", self._on_report_change)

        # -------- Panel Derecho: filtros + acciones + preview --------
        right = ttk.Frame(root)
        root.add(right, weight=4)

        # Acciones arriba
        top = ttk.Frame(right)
        top.pack(fill="x")
        ttk.Button(top, text="Generar", command=self._on_generate).pack(side="left", padx=4)
        ttk.Button(top, text="Exportar XLSX", command=self._on_export).pack(side="left", padx=4)
        ttk.Button(top, text="Imprimirâ€¦", command=self._on_print).pack(side="left", padx=4)

        # Marco de filtros
        self.frm_filters = ttk.Labelframe(right, text="Filtros", padding=10)
        self.frm_filters.pack(fill="x", pady=(8, 8))

        # Preview
        self.table = GridTable(right, height=16)
        self.table.pack(fill="both", expand=True)

        # Carga lookups y selecciona primer reporte
        self._load_lookups()
        if REPORTS:
            self.lst_reports.selection_set(0)
            self._on_report_change()

    # ======================= UI de filtros dinÃ¡micos ======================= #
    def _clear_filters_ui(self):
        for child in self.frm_filters.winfo_children():
            child.destroy()
        self._filter_vars.clear()

    def _load_lookups(self):
        # Clientes / Proveedores para filtros
        try:
            self._customers = self.session.query(Customer).order_by(Customer.razon_social.asc()).all()
        except Exception:
            self._customers = []
        try:
            self._suppliers = self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all()
        except Exception:
            self._suppliers = []

    def _on_report_change(self, _evt=None):
        sel = self.lst_reports.curselection()
        if not sel:
            return
        idx = sel[0]
        key = list(REPORTS.keys())[idx]
        self._current_key = key

        self._clear_filters_ui()
        meta = REPORTS[key]
        schema = meta.get("filters", {})

        # Construye controles segÃºn schema
        row = 0
        # Rango de fechas
        if schema.get("date_range"):
            ttk.Label(self.frm_filters, text="Desde (YYYY-MM-DD):").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            var_from = tk.StringVar(value=_one_month_ago_str())
            ttk.Entry(self.frm_filters, textvariable=var_from, width=14).grid(row=row, column=1, sticky="w", padx=4, pady=2)
            ttk.Label(self.frm_filters, text="Hasta:").grid(row=row, column=2, sticky="e", padx=4, pady=2)
            var_to = tk.StringVar(value=_today_str())
            ttk.Entry(self.frm_filters, textvariable=var_to, width=14).grid(row=row, column=3, sticky="w", padx=4, pady=2)
            self._filter_vars["date_from"] = var_from
            self._filter_vars["date_to"] = var_to
            row += 1

        # Cliente
        if schema.get("customer"):
            ttk.Label(self.frm_filters, text="Cliente:").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            cmb = ttk.Combobox(self.frm_filters, state="readonly", width=40,
                               values=[(c.razon_social or "").strip() for c in self._customers])
            cmb.grid(row=row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
            self._filter_vars["customer_idx"] = cmb
            row += 1

        # Proveedor
        if schema.get("supplier"):
            ttk.Label(self.frm_filters, text="Proveedor:").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            cmb = ttk.Combobox(self.frm_filters, state="readonly", width=40,
                               values=[(s.razon_social or "").strip() for s in self._suppliers])
            cmb.grid(row=row, column=1, columnspan=3, sticky="w", padx=4, pady=2)
            self._filter_vars["supplier_idx"] = cmb
            row += 1

        # Tipo de inventario (venta/compra/completo)
        if schema.get("inventory_type"):
            ttk.Label(self.frm_filters, text="Inventario (vista):").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            cmb = ttk.Combobox(self.frm_filters, state="readonly", width=20,
                               values=["completo", "venta", "compra"])
            cmb.set("completo")
            cmb.grid(row=row, column=1, sticky="w", padx=4, pady=2)
            self._filter_vars["inventory_type"] = cmb
            row += 1

        # Margen mÃ­nimo (para lista de precios)
        if schema.get("min_margin"):
            ttk.Label(self.frm_filters, text="Margen >= %:").grid(row=row, column=0, sticky="e", padx=4, pady=2)
            m = tk.DoubleVar(value=0.0)
            ttk.Spinbox(self.frm_filters, from_=0, to=1000, increment=0.5, textvariable=m, width=8)\
                .grid(row=row, column=1, sticky="w", padx=4, pady=2)
            self._filter_vars["min_margin"] = m
            row += 1

        # Ajuste de columnas
        for c in range(4):
            self.frm_filters.columnconfigure(c, weight=1)

        # Genera vista por defecto
        self._on_generate()

    # ============================ Acciones ============================ #
    def _collect_filters(self) -> Dict[str, Any]:
        """Lee los widgets de filtros y retorna un dict estÃ¡ndar."""
        d: Dict[str, Any] = {}
        if "date_from" in self._filter_vars:
            d["date_from"] = self._filter_vars["date_from"].get().strip()
        if "date_to" in self._filter_vars:
            d["date_to"] = self._filter_vars["date_to"].get().strip()
        if "customer_idx" in self._filter_vars:
            idx = self._filter_vars["customer_idx"].current()
            d["customer_id"] = (self._customers[idx].id if idx is not None and idx >= 0 and idx < len(self._customers) else None)
        if "supplier_idx" in self._filter_vars:
            idx = self._filter_vars["supplier_idx"].current()
            d["supplier_id"] = (self._suppliers[idx].id if idx is not None and idx >= 0 and idx < len(self._suppliers) else None)
        if "inventory_type" in self._filter_vars:
            d["inventory_type"] = self._filter_vars["inventory_type"].get()
        if "min_margin" in self._filter_vars:
            try:
                d["min_margin"] = float(self._filter_vars["min_margin"].get())
            except Exception:
                d["min_margin"] = 0.0
        return d

    def _on_generate(self):
        if not self._current_key:
            return
        try:
            filters = self._collect_filters()
            cols, rows = fetch_preview(self.session, self._current_key, filters)
            self.table.set_data(cols, rows)
        except ValueError as ve:
            messagebox.showwarning("Filtros", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el informe:\n{e}")

    def _on_export(self):
        if not self._current_key:
            return
        try:
            filters = self._collect_filters()
            path = export_report_xlsx(self.session, self._current_key, filters)
            messagebox.showinfo("ExportaciÃ³n", f"Archivo generado:\n{path}")
        except ValueError as ve:
            messagebox.showwarning("Filtros", str(ve))
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def _on_print(self):
        if not self._current_key:
            return
        filters = self._collect_filters()

        # Seleccionar impresora
        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if not getattr(dlg, "result", None):
            return
        printer = dlg.result

        try:
            print_report_generic(self.session, self._current_key, filters, printer_name=printer)
            messagebox.showinfo("ImpresiÃ³n", f"Informe enviado a '{printer}'.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir:\n{e}")

# src/gui/report_center.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Tuple
from pathlib import Path
import csv
import datetime as dt

from src.data.database import get_session
from src.data.models import (
    Product, Supplier, Customer,
    Purchase, PurchaseDetail,
    Sale, SaleDetail,
)
from src.gui.widgets.grid_table import GridTable

# Inventario: reutilizamos tu servicio y export/print nativos
from src.reports.inventory_reports import (
    InventoryFilter,
    InventoryReportService,
    generate_inventory_xlsx,
    print_inventory_report,
)
from src.gui.printer_select_dialog import PrinterSelectDialog


# ----------------------------- Utilidades ----------------------------- #
def _parse_date(s: str) -> Optional[dt.datetime]:
    """
    Convierte 'YYYY-MM-DD' en datetime al inicio del dÃ­a.
    Devuelve None si estÃ¡ vacÃ­o o formateado incorrectamente.
    """
    s = (s or "").strip()
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return dt.datetime(int(y), int(m), int(d), 0, 0, 0)
    except Exception:
        return None


def _range_to_datetimes(d_from: Optional[dt.datetime], d_to: Optional[dt.datetime]) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    """
    Si hay fecha hasta, la mueve al fin del dÃ­a 23:59:59 para incluirla.
    """
    if d_to is not None:
        d_to = d_to + dt.timedelta(hours=23, minutes=59, seconds=59)
    return d_from, d_to


# --------------------------- Vista principal -------------------------- #
class ReportCenter(ttk.Frame):
    """
    Centro de Informes:
      - Inventario (completo, compra, venta)
      - Ventas (resumen por venta, detalle por Ã­tem, top productos)
      - Compras (resumen por compra, detalle por Ã­tem)
      - Listados (productos, proveedores, clientes)
    """

    # DefiniciÃ³n de informes disponibles
    REPORTS = [
        ("inventory_full",   "Inventario â€“ Completo"),
        ("inventory_compra", "Inventario â€“ Compra"),
        ("inventory_venta",  "Inventario â€“ Venta"),
        ("sales_period",         "Ventas por perÃ­odo"),
        ("sales_detail_period",  "Detalle de ventas por perÃ­odo"),
        ("sales_top_products",   "Top productos vendidos por perÃ­odo"),
        ("purchases_period",        "Compras por perÃ­odo"),
        ("purchases_detail_period", "Detalle de compras por perÃ­odo"),
        ("products_list",   "Listado de productos"),
        ("suppliers_list",  "Listado de proveedores"),
        ("customers_list",  "Listado de clientes"),
    ]

    # Estados sugeridos (puedes ajustar segÃºn tus flujos)
    SALES_STATES = ["(Todos)", "Confirmada", "Pendiente", "Cancelada", "Eliminada"]
    PURCH_STATES = ["(Todos)", "Completada", "Pendiente", "Cancelada", "Eliminada"]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.svc_inventory = InventoryReportService(self.session)

        # cache de filas actuales mostradas (para export/print)
        self._current_cols: List[str] = []
        self._current_rows: List[List] = []
        self._current_report_key: str = ""

        # --------- Encabezado / selector ---------
        top = ttk.Frame(self); top.pack(fill="x", expand=False)
        ttk.Label(top, text="Informe:", font=("", 10, "bold")).pack(side="left")

        self.cmb_report = ttk.Combobox(
            top, state="readonly",
            values=[name for _key, name in self.REPORTS],
            width=36
        )
        self.cmb_report.current(0)
        self.cmb_report.pack(side="left", padx=8)
        self.cmb_report.bind("<<ComboboxSelected>>", lambda _e: self._on_report_changed())

        ttk.Button(top, text="Ejecutar", command=self._run_report).pack(side="right", padx=4)
        self.btn_export = ttk.Button(top, text="Exportar", command=self._on_export)
        self.btn_export.pack(side="right", padx=4)

        # --------- Filtros comunes ---------
        filt = ttk.Labelframe(self, text="Filtros", padding=8)
        filt.pack(fill="x", expand=False, pady=(8, 4))

        # Rango de fechas (YYYY-MM-DD)
        ttk.Label(filt, text="Desde (YYYY-MM-DD):").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.var_date_from = tk.StringVar()
        ent_from = ttk.Entry(filt, textvariable=self.var_date_from, width=14)
        ent_from.grid(row=0, column=1, sticky="w")

        ttk.Label(filt, text="Hasta (YYYY-MM-DD):").grid(row=0, column=2, sticky="e", padx=8)
        self.var_date_to = tk.StringVar()
        ent_to = ttk.Entry(filt, textvariable=self.var_date_to, width=14)
        ent_to.grid(row=0, column=3, sticky="w")

        # Estado (para ventas/compras)
        ttk.Label(filt, text="Estado:").grid(row=0, column=4, sticky="e", padx=8)
        self.cmb_state = ttk.Combobox(filt, state="readonly", values=self.SALES_STATES, width=14)
        self.cmb_state.current(0)
        self.cmb_state.grid(row=0, column=5, sticky="w")

        # BotÃ³n de filtros avanzados de inventario (abre tu diÃ¡logo)
        self.btn_inventory_filters = ttk.Button(filt, text="Filtros inventarioâ€¦", command=self._open_inventory_filters)
        self.btn_inventory_filters.grid(row=0, column=6, sticky="w", padx=8)

        # Filtros adicionales comunes (ventas/compras)
        ttk.Label(filt, text="Cliente/Proveedor contiene:").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.var_party = tk.StringVar()
        ttk.Entry(filt, textvariable=self.var_party, width=24).grid(row=1, column=1, sticky="w")

        ttk.Label(filt, text="Producto/SKU contiene:").grid(row=1, column=2, sticky="e", padx=8)
        self.var_product = tk.StringVar()
        ttk.Entry(filt, textvariable=self.var_product, width=24).grid(row=1, column=3, sticky="w")

        ttk.Label(filt, text="Total >=").grid(row=1, column=4, sticky="e", padx=8)
        self.var_total_min = tk.StringVar()
        ttk.Entry(filt, textvariable=self.var_total_min, width=10).grid(row=1, column=5, sticky="w")
        ttk.Label(filt, text="Total <=").grid(row=1, column=6, sticky="e", padx=8)
        self.var_total_max = tk.StringVar()
        ttk.Entry(filt, textvariable=self.var_total_max, width=10).grid(row=1, column=7, sticky="w")

        # Ajuste de columnas grid
        for i in range(8):
            filt.columnconfigure(i, weight=1)

        # --------- Rejilla de resultados ---------
        self.table = GridTable(self, height=18)
        self.table.pack(fill="both", expand=True, pady=(8, 10))

        # Mensaje de status
        self.var_status = tk.StringVar(value="Listo.")
        ttk.Label(self, textvariable=self.var_status).pack(anchor="w")

        # Estado interno de filtros inventario
        self._inv_filter: InventoryFilter = InventoryFilter()

        # Inicializa controles segÃºn el primer informe
        self._on_report_changed()

    # ---------------------- Handlers de UI ---------------------- #
    def _on_report_changed(self):
        """Muestra/oculta filtros segÃºn el informe activo y cambia texto de Exportar."""
        key = self._current_report_key = self._current_report_key_from_ui()

        # Por defecto: exporta a CSV
        self.btn_export.config(text="Exportar CSV")

        # Filtros visibles por tipo
        # Inventario: sin fechas / estado; con botÃ³n de filtros avanzados
        is_inventory = key.startswith("inventory_")
        self._set_filters_visible(
            show_dates=False if is_inventory else self._report_uses_dates(key),
            state_values=[] if is_inventory else (self.SALES_STATES if key.startswith("sales_") else (self.PURCH_STATES if key.startswith("purchases_") else []))
        )
        # Inventario â†’ exportar XLSX / imprimir disponibles
        if is_inventory:
            self.btn_export.config(text="Exportar XLSX")

        # Limpia estado
        self.var_status.set("Listo.")
        self._current_cols = []
        self._current_rows = []
        self.table.set_data(["(sin datos)"], [])

    def _set_filters_visible(self, show_dates: bool, state_values: List[str]):
        """Activa/oculta entradas de fecha y rellena estados apropiados."""
        # Entradas de fecha: mostrar/ocultar
        for child in self.children_of_type(ttk.Labelframe):
            pass  # por claridad; no necesitamos ocultar el Labelframe completo

        # Simplemente habilitamos/deshabilitamos
        # (Entradas siguen a la vista pero no afectan si estÃ¡n vacÃ­as)
        # Estado
        if state_values:
            self.cmb_state.configure(values=state_values)
            self.cmb_state.current(0)
            self.cmb_state.state(["!disabled"])
        else:
            self.cmb_state.set("")
            self.cmb_state.state(["disabled"])

        # BotÃ³n filtros inventario
        if self._current_report_key.startswith("inventory_"):
            self.btn_inventory_filters.state(["!disabled"])
        else:
            self.btn_inventory_filters.state(["disabled"])

    def children_of_type(self, klass):
        return [w for w in self.winfo_children() if isinstance(w, klass)]

    def _current_report_key_from_ui(self) -> str:
        name = self.cmb_report.get().strip()
        for k, n in self.REPORTS:
            if n == name:
                return k
        return self.REPORTS[0][0]

    def _report_uses_dates(self, key: str) -> bool:
        return key.endswith("_period") or key.endswith("_detail_period") or key.endswith("_products")

    # ---------------------- Inventario (filtros) ---------------------- #
    def _open_inventory_filters(self):
        """Abre el diÃ¡logo de filtros avanzados de inventario y los guarda localmente."""
        try:
            from src.gui.inventory_filters_dialog import InventoryFiltersDialog
        except Exception:
            messagebox.showwarning("Inventario", "El diÃ¡logo de filtros no estÃ¡ disponible.")
            return

        dlg = InventoryFiltersDialog(self, initial=self._inv_filter)
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self._inv_filter = dlg.result
            self.var_status.set("Filtros de inventario actualizados.")

    # ---------------------- Ejecutar informe ---------------------- #
    def _run_report(self):
        key = self._current_report_key_from_ui()
        try:
            if key.startswith("inventory_"):
                self._run_inventory_report(key)
            elif key.startswith("sales_"):
                self._run_sales_report(key)
            elif key.startswith("purchases_"):
                self._run_purchases_report(key)
            elif key.endswith("_list"):
                self._run_list_report(key)
            else:
                raise ValueError(f"Informe no soportado: {key}")

            # Volcar a grid
            self.table.set_data(self._current_cols, self._current_rows)
            # Ajuste ancho de columnas (GridTable ya maneja widths por defecto; aquÃ­ dejamos autosize)
            self.var_status.set(f"{len(self._current_rows)} fila(s).")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo ejecutar el informe:\n{e}")

    # ---------------------- Inventario ---------------------- #
    def _run_inventory_report(self, key: str):
        rtype = "completo"
        if key == "inventory_compra":
            rtype = "compra"
        elif key == "inventory_venta":
            rtype = "venta"

        flt = InventoryFilter(**{**self._inv_filter.__dict__, "report_type": rtype})
        rows_prod: List[Product] = self.svc_inventory.fetch(flt)

        # Columnas y filas
        if rtype == "venta":
            cols = ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Venta"]
        elif rtype == "compra":
            cols = ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Compra"]
        else:
            cols = ["ID", "Producto", "SKU", "Unidad", "Stock", "P. Compra", "P. Venta"]

        data: List[List] = []
        for p in rows_prod:
            base = [p.id, p.nombre, p.sku, p.unidad_medida or "", int(p.stock_actual or 0)]
            if rtype == "venta":
                row = base + [f"{float(p.precio_venta or 0):.2f}"]
            elif rtype == "compra":
                row = base + [f"{float(p.precio_compra or 0):.2f}"]
            else:
                row = base + [f"{float(p.precio_compra or 0):.2f}", f"{float(p.precio_venta or 0):.2f}"]
            data.append(row)

        self._current_cols = cols
        self._current_rows = data

    # ---------------------- Ventas ---------------------- #
    def _get_date_filters(self):
        d_from = _parse_date(self.var_date_from.get())
        d_to = _parse_date(self.var_date_to.get())
        return _range_to_datetimes(d_from, d_to)

    def _run_sales_report(self, key: str):
        d_from, d_to = self._get_date_filters()
        state = (self.cmb_state.get() or "").strip()
        party_like = (self.var_party.get() or "").strip()
        prod_like = (self.var_product.get() or "").strip()
        def _num(s: str):
            try:
                return float((s or "").replace(".", "").replace(",", ".")) if s else None
            except Exception:
                return None
        tmin = _num(self.var_total_min.get())
        tmax = _num(self.var_total_max.get())

        if key == "sales_period":
            # Resumen por venta
            q = (
                self.session.query(Sale, Customer)
                .join(Customer, Customer.id == Sale.id_cliente)
            )
            if d_from:
                q = q.filter(Sale.fecha_venta >= d_from)
            if d_to:
                q = q.filter(Sale.fecha_venta <= d_to)
            if state and state != "(Todos)":
                q = q.filter(Sale.estado == state)
            if party_like:
                like = f"%{party_like}%"
                q = q.filter((Customer.razon_social.ilike(like)) | (Customer.rut.ilike(like)))
            if tmin is not None:
                q = q.filter(Sale.total_venta >= tmin)
            if tmax is not None:
                q = q.filter(Sale.total_venta <= tmax)

            cols = ["ID", "Fecha", "Cliente", "Estado", "Total"]
            rows = []
            for s, c in q.order_by(Sale.id.desc()):
                rows.append([
                    s.id,
                    s.fecha_venta.strftime("%Y-%m-%d %H:%M"),
                    getattr(c, "razon_social", "") or "-",
                    s.estado,
                    f"{float(s.total_venta or 0):.2f}",
                ])
            self._current_cols, self._current_rows = cols, rows

        elif key == "sales_detail_period":
            # Detalle por Ã­tem
            q = (
                self.session.query(Sale, SaleDetail, Product, Customer)
                .join(SaleDetail, SaleDetail.id_venta == Sale.id)
                .join(Product, Product.id == SaleDetail.id_producto)
                .join(Customer, Customer.id == Sale.id_cliente)
            )
            if d_from:
                q = q.filter(Sale.fecha_venta >= d_from)
            if d_to:
                q = q.filter(Sale.fecha_venta <= d_to)
            if state and state != "(Todos)":
                q = q.filter(Sale.estado == state)
            if party_like:
                like = f"%{party_like}%"
                q = q.filter((Customer.razon_social.ilike(like)) | (Customer.rut.ilike(like)))
            if prod_like:
                likep = f"%{prod_like}%"
                q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))
            if tmin is not None:
                q = q.filter(Sale.total_venta >= tmin)
            if tmax is not None:
                q = q.filter(Sale.total_venta <= tmax)

            cols = ["Venta ID", "Fecha", "Cliente", "ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]
            rows = []
            for s, det, prod, cust in q.order_by(Sale.id.desc()):
                rows.append([
                    s.id,
                    s.fecha_venta.strftime("%Y-%m-%d %H:%M"),
                    getattr(cust, "razon_social", "") or "-",
                    prod.id,
                    prod.nombre,
                    float(det.cantidad or 0),
                    f"{float(det.precio_unitario or 0):.2f}",
                    f"{float(det.subtotal or 0):.2f}",
                ])
            self._current_cols, self._current_rows = cols, rows

        else:  # sales_top_products
            from sqlalchemy.sql import func
            qty = func.sum(SaleDetail.cantidad).label("qty")
            total = func.sum(SaleDetail.subtotal).label("total")
            q = (
                self.session.query(
                    Product.id.label("pid"),
                    Product.nombre.label("pname"),
                    qty,
                    total,
                )
                .join(SaleDetail, SaleDetail.id_producto == Product.id)
                .join(Sale, Sale.id == SaleDetail.id_venta)
                .group_by(Product.id, Product.nombre)
            )
            if d_from:
                q = q.filter(Sale.fecha_venta >= d_from)
            if d_to:
                q = q.filter(Sale.fecha_venta <= d_to)
            if state and state != "(Todos)":
                q = q.filter(Sale.estado == state)
            if prod_like:
                likep = f"%{prod_like}%"
                q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))

            # Ordenar por cantidad descendente usando la expresiÃ³n agregada
            q = q.order_by(qty.desc())
            cols = ["ID Prod", "Producto", "Unidades vendidas", "Total"]
            rows = []
            for pid, pname, qty, total in q:
                rows.append([pid, pname, float(qty or 0), f"{float(total or 0):.2f}"])
            self._current_cols, self._current_rows = cols, rows

    # ---------------------- Compras ---------------------- #
    def _run_purchases_report(self, key: str):
        d_from, d_to = self._get_date_filters()
        state = (self.cmb_state.get() or "").strip()
        party_like = (self.var_party.get() or "").strip()
        prod_like = (self.var_product.get() or "").strip()
        def _num(s: str):
            try:
                return float((s or "").replace(".", "").replace(",", ".")) if s else None
            except Exception:
                return None
        tmin = _num(self.var_total_min.get())
        tmax = _num(self.var_total_max.get())

        if key == "purchases_period":
            q = (
                self.session.query(Purchase, Supplier)
                .join(Supplier, Supplier.id == Purchase.id_proveedor)
            )
            if d_from:
                q = q.filter(Purchase.fecha_compra >= d_from)
            if d_to:
                q = q.filter(Purchase.fecha_compra <= d_to)
            if state and state != "(Todos)":
                q = q.filter(Purchase.estado == state)
            if party_like:
                like = f"%{party_like}%"
                q = q.filter((Supplier.razon_social.ilike(like)) | (Supplier.rut.ilike(like)))
            if tmin is not None:
                q = q.filter(Purchase.total_compra >= tmin)
            if tmax is not None:
                q = q.filter(Purchase.total_compra <= tmax)

            cols = ["ID", "Fecha", "Proveedor", "Estado", "Total"]
            rows = []
            for pur, sup in q.order_by(Purchase.id.desc()):
                rows.append([
                    pur.id,
                    pur.fecha_compra.strftime("%Y-%m-%d %H:%M"),
                    getattr(sup, "razon_social", "") or "-",
                    pur.estado,
                    f"{float(pur.total_compra or 0):.2f}",
                ])
            self._current_cols, self._current_rows = cols, rows

        else:  # purchases_detail_period
            q = (
                self.session.query(Purchase, PurchaseDetail, Product, Supplier)
                .join(PurchaseDetail, PurchaseDetail.id_compra == Purchase.id)
                .join(Product, Product.id == PurchaseDetail.id_producto)
                .join(Supplier, Supplier.id == Purchase.id_proveedor)
            )
            if d_from:
                q = q.filter(Purchase.fecha_compra >= d_from)
            if d_to:
                q = q.filter(Purchase.fecha_compra <= d_to)
            if state and state != "(Todos)":
                q = q.filter(Purchase.estado == state)
            if party_like:
                like = f"%{party_like}%"
                q = q.filter((Supplier.razon_social.ilike(like)) | (Supplier.rut.ilike(like)))
            if prod_like:
                likep = f"%{prod_like}%"
                q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))

            cols = ["Compra ID", "Fecha", "Proveedor", "ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]
            rows = []
            for pur, det, prod, sup in q.order_by(Purchase.id.desc()):
                rows.append([
                    pur.id,
                    pur.fecha_compra.strftime("%Y-%m-%d %H:%M"),
                    getattr(sup, "razon_social", "") or "-",
                    prod.id,
                    prod.nombre,
                    float(det.cantidad or 0),
                    f"{float(det.precio_unitario or 0):.2f}",
                    f"{float(det.subtotal or 0):.2f}",
                ])
            self._current_cols, self._current_rows = cols, rows

    # ---------------------- Listados simples ---------------------- #
    def _run_list_report(self, key: str):
        if key == "products_list":
            cols = ["ID", "Nombre", "CÃ³digo", "Unidad", "P. Compra", "P. Venta", "Stock"]
            rows = []
            for p in self.session.query(Product).order_by(Product.nombre.asc()):
                rows.append([
                    p.id, p.nombre or "", p.sku or "", p.unidad_medida or "",
                    f"{float(p.precio_compra or 0):.2f}", f"{float(p.precio_venta or 0):.2f}",
                    int(p.stock_actual or 0),
                ])
            self._current_cols, self._current_rows = cols, rows
            return

        if key == "suppliers_list":
            cols = ["ID", "RazÃ³n social", "RUT", "Contacto", "TelÃ©fono", "Email", "DirecciÃ³n"]
            rows = []
            for s in self.session.query(Supplier).order_by(Supplier.razon_social.asc()):
                rows.append([
                    s.id, s.razon_social or "", s.rut or "", s.contacto or "",
                    s.telefono or "", s.email or "", s.direccion or "",
                ])
            self._current_cols, self._current_rows = cols, rows
            return

        if key == "customers_list":
            cols = ["ID", "RazÃ³n social", "RUT", "Contacto", "TelÃ©fono", "Email", "DirecciÃ³n"]
            rows = []
            for c in self.session.query(Customer).order_by(Customer.razon_social.asc()):
                rows.append([
                    c.id, c.razon_social or "", c.rut or "", c.contacto or "",
                    c.telefono or "", c.email or "", c.direccion or "",
                ])
            self._current_cols, self._current_rows = cols, rows
            return

        raise ValueError(f"Listado no soportado: {key}")

    # ---------------------- Exportar / Imprimir ---------------------- #
    def _on_export(self):
        key = self._current_report_key_from_ui()
        if not self._current_cols:
            messagebox.showwarning("Exportar", "Ejecuta un informe primero.")
            return

        # Inventario â†’ usa tu generador XLSX (y permite imprimir)
        if key.startswith("inventory_"):
            try:
                rtype = "completo"
                if key == "inventory_compra":
                    rtype = "compra"
                elif key == "inventory_venta":
                    rtype = "venta"

                flt = InventoryFilter(**{**self._inv_filter.__dict__, "report_type": rtype})
                path = generate_inventory_xlsx(self.session, flt, f"Inventario ({rtype})")
                messagebox.showinfo("Exportar", f"Generado:\n{path}")
            except Exception as e:
                messagebox.showerror("Exportar", f"No se pudo generar XLSX:\n{e}")
            return

        # Resto â†’ CSV plano sin dependencias
        try:
            outdir = Path("reports")
            outdir.mkdir(parents=True, exist_ok=True)
            stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
            fname = f"{key}_{stamp}.csv"
            fpath = outdir / fname

            with fpath.open("w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(self._current_cols)
                for row in self._current_rows:
                    writer.writerow(row)

            messagebox.showinfo("Exportar", f"CSV guardado en:\n{fpath}")
        except Exception as e:
            messagebox.showerror("Exportar", f"No se pudo exportar CSV:\n{e}")

    def print_inventory(self):
        """Atajo para imprimir el inventario con tu backend."""
        key = self._current_report_key_from_ui()
        if not key.startswith("inventory_"):
            messagebox.showwarning("Imprimir", "Selecciona un informe de Inventario.")
            return

        rtype = "completo"
        if key == "inventory_compra":
            rtype = "compra"
        elif key == "inventory_venta":
            rtype = "venta"

        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if not getattr(dlg, "result", None):
            return
        printer_name = dlg.result
        try:
            flt = InventoryFilter(**{**self._inv_filter.__dict__, "report_type": rtype})
            path = print_inventory_report(self.session, flt, f"Inventario ({rtype})", printer_name=printer_name)
            messagebox.showinfo("ImpresiÃ³n", f"Enviado a '{printer_name}'.\nArchivo: {path}")
        except Exception as e:
            messagebox.showerror("Imprimir", f"No se pudo imprimir:\n{e}")

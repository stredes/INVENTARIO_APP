# src/reports/report_center.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Tuple
from pathlib import Path
import csv
import datetime as dt
import webbrowser

from src.data.database import get_session
from src.data.models import (
    Product, Supplier, Customer,
    Purchase, PurchaseDetail,
    Sale, SaleDetail,
)
from src.gui.widgets.grid_table import GridTable

# Inventario: servicio + exportar/imprimir
from src.reports.inventory_reports import (
    InventoryFilter,
    InventoryReportService,
    generate_inventory_xlsx,
    print_inventory_report,
)
from src.gui.printer_select_dialog import PrinterSelectDialog


# ----------------------------- Utilidades ----------------------------- #
def _parse_date(s: str) -> Optional[dt.datetime]:
    """Convierte YYYY-MM-DD en datetime al inicio del día. None si vacío/incorrecto."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return dt.datetime(int(y), int(m), int(d), 0, 0, 0)
    except Exception:
        return None


def _range_to_datetimes(d_from: Optional[dt.datetime], d_to: Optional[dt.datetime]) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
    """Si hay fecha hasta, muévela a 23:59:59 para incluirla completa."""
    if d_to is not None:
        d_to = d_to + dt.timedelta(hours=23, minutes=59, seconds=59)
    return d_from, d_to


# --------------------------- Vista principal -------------------------- #
class ReportCenter(ttk.Frame):
    """
    Centro de Informes:
      - Inventario (completo, compra, venta)
      - Ventas (resumen por venta, detalle por período, top productos)
      - Compras (resumen por compra, detalle por período)
      - Listados (productos, proveedores, clientes)
    """

    # Definición de informes disponibles
    REPORTS = [
        ("inventory_full",   "Inventario — Completo"),
        ("inventory_compra", "Inventario — Compra"),
        ("inventory_venta",  "Inventario — Venta"),
        ("sales_period",         "Ventas por período"),
        ("sales_detail_period",  "Detalle de ventas por período"),
        ("sales_top_products",   "Top productos vendidos por período"),
        ("purchases_period",        "Compras por período"),
        ("purchases_detail_period", "Detalle de compras por período"),
        ("products_list",   "Listado de productos"),
        ("suppliers_list",  "Listado de proveedores"),
        ("customers_list",  "Listado de clientes"),
    ]

    SALES_STATES = ["(Todos)", "Confirmada", "Pendiente", "Cancelada", "Eliminada", "Pagada", "Reservada"]
    PURCH_STATES = ["(Todos)", "Completada", "Pendiente", "Cancelada", "Eliminada", "Por pagar", "Incompleta"]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.svc_inventory = InventoryReportService(self.session)

        # cache para exportar/imprimir
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

        # --------- Filtros ---------
        filt = ttk.Labelframe(self, text="Filtros", padding=8)
        filt.pack(fill="x", expand=False, pady=(8, 4))

        ttk.Label(filt, text="Desde (YYYY-MM-DD):").grid(row=0, column=0, sticky="e", padx=4, pady=3)
        self.var_date_from = tk.StringVar(); ttk.Entry(filt, textvariable=self.var_date_from, width=14).grid(row=0, column=1, sticky="w")
        ttk.Label(filt, text="Hasta (YYYY-MM-DD):").grid(row=0, column=2, sticky="e", padx=8)
        self.var_date_to = tk.StringVar(); ttk.Entry(filt, textvariable=self.var_date_to, width=14).grid(row=0, column=3, sticky="w")

        ttk.Label(filt, text="Estado:").grid(row=0, column=4, sticky="e", padx=8)
        self.cmb_state = ttk.Combobox(filt, state="readonly", width=14, values=self.SALES_STATES)
        self.cmb_state.grid(row=0, column=5, sticky="w")
        try:
            self.cmb_state.current(0)
        except Exception:
            pass

        ttk.Label(filt, text="Tercero (nombre/rut):").grid(row=1, column=0, sticky="e", padx=4, pady=3)
        self.var_party = tk.StringVar(); ttk.Entry(filt, textvariable=self.var_party, width=26).grid(row=1, column=1, sticky="w")
        ttk.Label(filt, text="Producto (nombre/sku):").grid(row=1, column=2, sticky="e", padx=8)
        self.var_product = tk.StringVar(); ttk.Entry(filt, textvariable=self.var_product, width=26).grid(row=1, column=3, sticky="w")

        ttk.Label(filt, text="Total min:").grid(row=1, column=4, sticky="e")
        self.var_total_min = tk.StringVar(); ttk.Entry(filt, textvariable=self.var_total_min, width=12).grid(row=1, column=5, sticky="w")
        ttk.Label(filt, text="Total max:").grid(row=1, column=6, sticky="e")
        self.var_total_max = tk.StringVar(); ttk.Entry(filt, textvariable=self.var_total_max, width=12).grid(row=1, column=7, sticky="w")

        # --------- Tabla ---------
        self.table = GridTable(self, height=16)
        self.table.pack(fill="both", expand=True, pady=(8, 0))

        self._on_report_changed()  # set estados apropiados

    # ---------------------- Helpers de filtros ---------------------- #
    def _get_date_filters(self) -> Tuple[Optional[dt.datetime], Optional[dt.datetime]]:
        d_from = _parse_date(self.var_date_from.get())
        d_to = _parse_date(self.var_date_to.get())
        return _range_to_datetimes(d_from, d_to)

    def _on_report_changed(self) -> None:
        idx = self.cmb_report.current() or 0
        key = self.REPORTS[idx][0]
        self._current_report_key = key
        # Cambiar combo de estado según informe
        if key.startswith("sales_"):
            self.cmb_state["values"] = self.SALES_STATES
            try: self.cmb_state.current(0)
            except Exception: pass
        elif key.startswith("purchases_"):
            self.cmb_state["values"] = self.PURCH_STATES
            try: self.cmb_state.current(0)
            except Exception: pass
        else:
            # Inventario y listados no usan estado
            self.cmb_state["values"] = ["(Todos)"]
            try: self.cmb_state.current(0)
            except Exception: pass

    # ------------------------- Ejecución ------------------------- #
    def _run_report(self) -> None:
        try:
            idx = self.cmb_report.current() or 0
            key, _name = self.REPORTS[idx]
            if key.startswith("inventory_"):
                self._run_inventory_report(key)
            elif key.startswith("sales_"):
                self._run_sales_report(key)
            elif key.startswith("purchases_"):
                self._run_purchases_report(key)
            else:
                self._run_list_report(key)
            # Cargar en tabla
            self.table.set_data(self._current_cols, self._current_rows)
        except Exception as e:
            messagebox.showerror("Informes", f"No se pudo ejecutar el informe:\n{e}")

    # ---------------------- Inventario ---------------------- #
    def _run_inventory_report(self, key: str) -> None:
        kind = "completo" if key.endswith("full") else ("compra" if key.endswith("compra") else "venta")
        flt = InventoryFilter(report_type=("completo" if kind == "completo" else ("compra" if kind == "compra" else "venta")))
        products = self.svc_inventory.fetch(flt)
        cols = ["ID", "Producto", "SKU", "Unidad", "Stock"]
        rows: List[List] = []
        for p in products:
            rows.append([p.id, p.nombre or "", p.sku or "", p.unidad_medida or "", int(p.stock_actual or 0)])
        self._current_cols, self._current_rows = cols, rows

    # ------------------------ Ventas ------------------------ #
    def _run_sales_report(self, key: str) -> None:
        d_from, d_to = self._get_date_filters()
        state = (self.cmb_state.get() or "").strip()
        party_like = (self.var_party.get() or "").strip()
        prod_like = (self.var_product.get() or "").strip()
        def _num(s: str):
            try:
                return float((s or "").replace(".", "").replace(",", ".")) if s else None
            except Exception:
                return None
        tmin = _num(self.var_total_min.get()); tmax = _num(self.var_total_max.get())

        if key == "sales_period":
            q = self.session.query(Sale, Customer).join(Customer, Customer.id == Sale.id_cliente)
            if d_from: q = q.filter(Sale.fecha_venta >= d_from)
            if d_to:   q = q.filter(Sale.fecha_venta <= d_to)
            if state and state != "(Todos)": q = q.filter(Sale.estado == state)
            if party_like:
                like = f"%{party_like}%"; q = q.filter((Customer.razon_social.ilike(like)) | (Customer.rut.ilike(like)))
            if tmin is not None: q = q.filter(Sale.total_venta >= tmin)
            if tmax is not None: q = q.filter(Sale.total_venta <= tmax)
            cols = ["ID", "Fecha", "Cliente", "Estado", "Total"]; rows = []
            for s, c in q.order_by(Sale.id.desc()):
                rows.append([s.id, s.fecha_venta.strftime("%Y-%m-%d %H:%M"), getattr(c, "razon_social", "") or "-", s.estado, f"{float(s.total_venta or 0):.2f}"])
            self._current_cols, self._current_rows = cols, rows
        elif key == "sales_detail_period":
            q = (self.session.query(Sale, SaleDetail, Product, Customer)
                 .join(SaleDetail, SaleDetail.id_venta == Sale.id)
                 .join(Product, Product.id == SaleDetail.id_producto)
                 .join(Customer, Customer.id == Sale.id_cliente))
            if d_from: q = q.filter(Sale.fecha_venta >= d_from)
            if d_to:   q = q.filter(Sale.fecha_venta <= d_to)
            if state and state != "(Todos)": q = q.filter(Sale.estado == state)
            if party_like:
                like = f"%{party_like}%"; q = q.filter((Customer.razon_social.ilike(like)) | (Customer.rut.ilike(like)))
            if prod_like:
                likep = f"%{prod_like}%"; q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))
            if tmin is not None: q = q.filter(Sale.total_venta >= tmin)
            if tmax is not None: q = q.filter(Sale.total_venta <= tmax)
            cols = ["Venta ID", "Fecha", "Cliente", "ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]; rows = []
            for s, det, prod, cust in q.order_by(Sale.id.desc()):
                rows.append([s.id, s.fecha_venta.strftime("%Y-%m-%d %H:%M"), getattr(cust, "razon_social", "") or "-", prod.id, prod.nombre, float(det.cantidad or 0), f"{float(det.precio_unitario or 0):.2f}", f"{float(det.subtotal or 0):.2f}"])
            self._current_cols, self._current_rows = cols, rows
        else:  # sales_top_products
            from sqlalchemy.sql import func
            qty = func.sum(SaleDetail.cantidad).label("qty")
            total = func.sum(SaleDetail.subtotal).label("total")
            q = (self.session.query(Product.id.label("pid"), Product.nombre.label("pname"), qty, total)
                 .join(SaleDetail, SaleDetail.id_producto == Product.id)
                 .join(Sale, Sale.id == SaleDetail.id_venta)
                 .group_by(Product.id, Product.nombre))
            if d_from: q = q.filter(Sale.fecha_venta >= d_from)
            if d_to:   q = q.filter(Sale.fecha_venta <= d_to)
            if state and state != "(Todos)": q = q.filter(Sale.estado == state)
            if prod_like:
                likep = f"%{prod_like}%"; q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))
            q = q.order_by(qty.desc())
            cols = ["ID Prod", "Producto", "Unidades vendidas", "Total"]; rows = []
            for pid, pname, qty_v, total_v in q:
                rows.append([pid, pname, float(qty_v or 0), f"{float(total_v or 0):.2f}"])
            self._current_cols, self._current_rows = cols, rows

    # ---------------------- Compras ---------------------- #
    def _run_purchases_report(self, key: str) -> None:
        d_from, d_to = self._get_date_filters()
        state = (self.cmb_state.get() or "").strip()
        party_like = (self.var_party.get() or "").strip()
        prod_like = (self.var_product.get() or "").strip()
        def _num(s: str):
            try:
                return float((s or "").replace(".", "").replace(",", ".")) if s else None
            except Exception:
                return None
        tmin = _num(self.var_total_min.get()); tmax = _num(self.var_total_max.get())

        if key == "purchases_period":
            q = self.session.query(Purchase, Supplier).join(Supplier, Supplier.id == Purchase.id_proveedor)
            if d_from: q = q.filter(Purchase.fecha_compra >= d_from)
            if d_to:   q = q.filter(Purchase.fecha_compra <= d_to)
            if state and state != "(Todos)": q = q.filter(Purchase.estado == state)
            if party_like:
                like = f"%{party_like}%"; q = q.filter((Supplier.razon_social.ilike(like)) | (Supplier.rut.ilike(like)))
            if tmin is not None: q = q.filter(Purchase.total_compra >= tmin)
            if tmax is not None: q = q.filter(Purchase.total_compra <= tmax)
            cols = ["ID", "Fecha", "Proveedor", "Estado", "Total"]; rows = []
            for p, s in q.order_by(Purchase.id.desc()):
                rows.append([p.id, p.fecha_compra.strftime("%Y-%m-%d %H:%M"), getattr(s, "razon_social", "") or "-", p.estado, f"{float(p.total_compra or 0):.2f}"])
            self._current_cols, self._current_rows = cols, rows
        else:  # purchases_detail_period
            q = (self.session.query(Purchase, PurchaseDetail, Product, Supplier)
                 .join(PurchaseDetail, PurchaseDetail.id_compra == Purchase.id)
                 .join(Product, Product.id == PurchaseDetail.id_producto)
                 .join(Supplier, Supplier.id == Purchase.id_proveedor))
            if d_from: q = q.filter(Purchase.fecha_compra >= d_from)
            if d_to:   q = q.filter(Purchase.fecha_compra <= d_to)
            if state and state != "(Todos)": q = q.filter(Purchase.estado == state)
            if party_like:
                like = f"%{party_like}%"; q = q.filter((Supplier.razon_social.ilike(like)) | (Supplier.rut.ilike(like)))
            if prod_like:
                likep = f"%{prod_like}%"; q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))
            if tmin is not None: q = q.filter(Purchase.total_compra >= tmin)
            if tmax is not None: q = q.filter(Purchase.total_compra <= tmax)
            cols = ["Compra ID", "Fecha", "Proveedor", "ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]; rows = []
            for pur, det, prod, sup in q.order_by(Purchase.id.desc()):
                rows.append([pur.id, pur.fecha_compra.strftime("%Y-%m-%d %H:%M"), getattr(sup, "razon_social", "") or "-", prod.id, prod.nombre, float(det.cantidad or 0), f"{float(det.precio_unitario or 0):.2f}", f"{float(det.subtotal or 0):.2f}"])
            self._current_cols, self._current_rows = cols, rows

    # ------------------------ Listados ------------------------ #
    def _run_list_report(self, key: str) -> None:
        if key == "products_list":
            cols = ["ID", "Producto", "SKU", "Unidad", "P. Compra", "P. Venta", "Stock"]; rows = []
            for p in self.session.query(Product).order_by(Product.nombre.asc()).all():
                rows.append([p.id, p.nombre or "", p.sku or "", p.unidad_medida or "", f"{float(p.precio_compra or 0):.2f}", f"{float(p.precio_venta or 0):.2f}", int(p.stock_actual or 0)])
        elif key == "suppliers_list":
            cols = ["ID", "Razón social", "RUT", "Contacto", "Teléfono", "Email"]; rows = []
            for s in self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all():
                rows.append([s.id, s.razon_social or "", s.rut or "", s.contacto or "", s.telefono or "", s.email or ""])
        else:  # customers_list
            cols = ["ID", "Razón social", "RUT", "Contacto", "Teléfono", "Email"]; rows = []
            for c in self.session.query(Customer).order_by(Customer.razon_social.asc()).all():
                rows.append([c.id, c.razon_social or "", c.rut or "", c.contacto or "", c.telefono or "", c.email or ""])
        self._current_cols, self._current_rows = cols, rows

    # -------------------- Exportar / Imprimir -------------------- #
    def _on_export(self) -> None:
        try:
            key = self._current_report_key or self.REPORTS[self.cmb_report.current() or 0][0]
            if key.startswith("inventory_"):
                # Genera XLSX con el servicio dedicado
                flt = InventoryFilter(report_type=("completo" if key.endswith("full") else ("compra" if key.endswith("compra") else "venta")))
                path = generate_inventory_xlsx(self.session, flt, "Listado de Inventario")
                webbrowser.open(str(path))
                messagebox.showinfo("OK", f"Exportado a:\n{path}")
                return
            # CSV simple para el resto
            out = Path.home() / "Downloads" / "informe.csv"
            with out.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                if self._current_cols: w.writerow(self._current_cols)
                for r in self._current_rows:
                    w.writerow(r)
            webbrowser.open(str(out))
            messagebox.showinfo("OK", f"Exportado a:\n{out}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def print_current(self) -> None:
        # Solo inventario tiene backend de impresión dedicado
        key = self._current_report_key or self.REPORTS[self.cmb_report.current() or 0][0]
        if not key.startswith("inventory_"):
            messagebox.showinfo("Impresión", "Sólo compatible con informes de Inventario.")
            return
        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        printer_name = dlg.result
        try:
            flt = InventoryFilter(report_type=("completo" if key.endswith("full") else ("compra" if key.endswith("compra") else "venta")))
            path = print_inventory_report(self.session, flt, "Listado de Inventario", printer_name=printer_name)
            messagebox.showinfo("Impresión", f"Enviado a '{printer_name}'.\nArchivo: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir:\n{e}")


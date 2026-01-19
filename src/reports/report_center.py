# src/reports/report_center.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Tuple
from pathlib import Path
import csv
import datetime as dt
import webbrowser
from decimal import Decimal

from src.data.database import get_session
from src.data.models import (
    Product, Supplier, Customer,
    Purchase, PurchaseDetail, Reception,
    Sale,
)
from src.gui.widgets.grid_table import GridTable

# Stock real: servicio + exportar/imprimir
from src.reports.inventory_reports import (
    InventoryFilter,
    InventoryReportService,
    generate_inventory_xlsx,
    print_inventory_report,
)
from src.gui.printer_select_dialog import PrinterSelectDialog
from src.utils.printers import get_document_printer


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
      - Stock real
      - Facturas o guias (por pagar / por cobrar)
      - Ordenes de compra (resumen y detalle por proveedor/producto)
      - Ventas por periodo
      - Inversion monetaria por producto
    """

    # Definición de informes disponibles
    REPORTS = [
        ("stock_real", "Stock real"),
        ("payables_docs", "Facturas o guias que debo"),
        ("receivables_docs", "Facturas o guias pendientes que me deben"),
        ("purchase_orders", "Ordenes de compra (resumen)"),
        ("purchase_by_supplier_product", "Ordenes de compra por proveedor y producto"),
        ("sales_period", "Ventas por periodo"),
        ("investment_by_product", "Inversion monetaria por producto"),
    ]

    SALES_STATES = ["(Todos)", "Pagada", "Confirmada", "Pendiente", "Cancelada", "Eliminada"]
    RECEIVABLE_STATES = ["(Todos)", "Confirmada", "Pendiente"]
    PURCH_STATES = ["(Todos)", "Completada", "Pendiente", "Cancelada", "Eliminada", "Por pagar", "Incompleta"]
    PAYABLE_STATES = ["(Todos)", "Por pagar", "Pendiente", "Incompleta"]

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
        # Cambiar combo de estado segun informe
        if key == "sales_period":
            self.cmb_state["values"] = self.SALES_STATES
            try: self.cmb_state.current(0)
            except Exception: pass
        elif key == "receivables_docs":
            self.cmb_state["values"] = self.RECEIVABLE_STATES
            try: self.cmb_state.current(0)
            except Exception: pass
        elif key in ("purchase_orders", "purchase_by_supplier_product"):
            self.cmb_state["values"] = self.PURCH_STATES
            try: self.cmb_state.current(0)
            except Exception: pass
        elif key == "payables_docs":
            self.cmb_state["values"] = self.PAYABLE_STATES
            try: self.cmb_state.current(0)
            except Exception: pass
        else:
            self.cmb_state["values"] = ["(Todos)"]
            try: self.cmb_state.current(0)
            except Exception: pass

    # ------------------------- Ejecución ------------------------- #
    def _run_report(self) -> None:
        try:
            idx = self.cmb_report.current() or 0
            key, _name = self.REPORTS[idx]
            if key == "stock_real":
                self._run_stock_report()
            elif key in ("sales_period", "receivables_docs"):
                self._run_sales_report(key)
            elif key in ("purchase_orders", "purchase_by_supplier_product", "payables_docs"):
                self._run_purchases_report(key)
            elif key == "investment_by_product":
                self._run_investment_report()
            else:
                self._current_cols, self._current_rows = [], []
            # Cargar en tabla
            self.table.set_data(self._current_cols, self._current_rows)
        except Exception as e:
            messagebox.showerror("Informes", f"No se pudo ejecutar el informe:\n{e}")

    # ---------------------- Stock real ---------------------- #
    def _run_stock_report(self) -> None:
        flt = InventoryFilter(report_type="completo")
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
        def _num(s: str):
            try:
                return float((s or "").replace(".", "").replace(",", ".")) if s else None
            except Exception:
                return None
        tmin = _num(self.var_total_min.get()); tmax = _num(self.var_total_max.get())

        q = self.session.query(Sale, Customer).join(Customer, Customer.id == Sale.id_cliente)
        if d_from: q = q.filter(Sale.fecha_venta >= d_from)
        if d_to:   q = q.filter(Sale.fecha_venta <= d_to)

        if key == "receivables_docs":
            if not state or state == "(Todos)":
                q = q.filter(Sale.estado.in_(self.RECEIVABLE_STATES[1:]))
            else:
                q = q.filter(Sale.estado == state)
        else:
            if state and state != "(Todos)":
                q = q.filter(Sale.estado == state)

        if party_like:
            like = f"%{party_like}%"
            q = q.filter((Customer.razon_social.ilike(like)) | (Customer.rut.ilike(like)))
        if tmin is not None: q = q.filter(Sale.total_venta >= tmin)
        if tmax is not None: q = q.filter(Sale.total_venta <= tmax)

        cols = ["ID", "Fecha", "Cliente", "Estado", "Total"]
        rows: List[List] = []
        for s, c in q.order_by(Sale.id.desc()):
            rows.append([
                s.id,
                s.fecha_venta.strftime("%Y-%m-%d %H:%M"),
                getattr(c, "razon_social", "") or "-",
                s.estado,
                f"{float(s.total_venta or 0):.2f}",
            ])
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

        def _fmt_date(val: Optional[dt.datetime], with_time: bool = False) -> str:
            if not val:
                return ""
            return val.strftime("%Y-%m-%d %H:%M") if with_time else val.strftime("%Y-%m-%d")

        if key == "purchase_by_supplier_product":
            q = (self.session.query(Purchase, PurchaseDetail, Product, Supplier)
                 .join(PurchaseDetail, PurchaseDetail.id_compra == Purchase.id)
                 .join(Product, Product.id == PurchaseDetail.id_producto)
                 .join(Supplier, Supplier.id == Purchase.id_proveedor))
            if d_from: q = q.filter(Purchase.fecha_compra >= d_from)
            if d_to:   q = q.filter(Purchase.fecha_compra <= d_to)
            if state and state != "(Todos)":
                q = q.filter(Purchase.estado == state)
            if party_like:
                like = f"%{party_like}%"
                q = q.filter((Supplier.razon_social.ilike(like)) | (Supplier.rut.ilike(like)))
            if prod_like:
                likep = f"%{prod_like}%"
                q = q.filter((Product.nombre.ilike(likep)) | (Product.sku.ilike(likep)))
            if tmin is not None: q = q.filter(Purchase.total_compra >= tmin)
            if tmax is not None: q = q.filter(Purchase.total_compra <= tmax)
            cols = ["Proveedor", "Compra ID", "Fecha", "Producto", "SKU", "Cant.", "Precio", "Subtotal", "Estado"]
            rows: List[List] = []
            for pur, det, prod, sup in q.order_by(Purchase.id.desc()):
                rows.append([
                    getattr(sup, "razon_social", "") or "-",
                    pur.id,
                    _fmt_date(pur.fecha_compra, True),
                    prod.nombre or "",
                    prod.sku or "",
                    float(det.cantidad or 0),
                    f"{float(det.precio_unitario or 0):.2f}",
                    f"{float(det.subtotal or 0):.2f}",
                    pur.estado,
                ])
            self._current_cols, self._current_rows = cols, rows
            return

        q = self.session.query(Purchase, Supplier).join(Supplier, Supplier.id == Purchase.id_proveedor)
        if d_from: q = q.filter(Purchase.fecha_compra >= d_from)
        if d_to:   q = q.filter(Purchase.fecha_compra <= d_to)

        if key == "payables_docs":
            if not state or state == "(Todos)":
                q = q.filter(Purchase.estado.in_(self.PAYABLE_STATES[1:]))
            else:
                q = q.filter(Purchase.estado == state)
        else:
            if state and state != "(Todos)":
                q = q.filter(Purchase.estado == state)

        if party_like:
            like = f"%{party_like}%"
            q = q.filter((Supplier.razon_social.ilike(like)) | (Supplier.rut.ilike(like)))
        if tmin is not None: q = q.filter(Purchase.total_compra >= tmin)
        if tmax is not None: q = q.filter(Purchase.total_compra <= tmax)

        if key == "payables_docs":
            purchases = q.order_by(Purchase.id.desc()).all()
            purchase_ids = [p.id for p, _s in purchases]
            docs_by_purchase: dict[int, list[str]] = {}
            if purchase_ids:
                for rec in (self.session.query(Reception)
                            .filter(Reception.id_compra.in_(purchase_ids))
                            .order_by(Reception.fecha.asc())):
                    label = f"{rec.tipo_doc or 'Doc'} {rec.numero_documento or ''}".strip()
                    docs_by_purchase.setdefault(rec.id_compra, []).append(label)

            cols = ["Compra ID", "Fecha", "Proveedor", "Estado", "Total", "Docs"]
            rows: List[List] = []
            for p, s in purchases:
                docs = docs_by_purchase.get(p.id) or []
                rows.append([
                    p.id,
                    _fmt_date(p.fecha_compra, True),
                    getattr(s, "razon_social", "") or "-",
                    p.estado,
                    f"{float(p.total_compra or 0):.2f}",
                    " | ".join(docs) if docs else "Sin doc",
                ])
            self._current_cols, self._current_rows = cols, rows
            return

        cols = ["ID", "Fecha", "Proveedor", "Estado", "Total", "Doc", "F. doc", "Venc."]
        rows: List[List] = []
        for p, s in q.order_by(Purchase.id.desc()):
            rows.append([
                p.id,
                _fmt_date(p.fecha_compra, True),
                getattr(s, "razon_social", "") or "-",
                p.estado,
                f"{float(p.total_compra or 0):.2f}",
                p.numero_documento or "",
                _fmt_date(p.fecha_documento),
                _fmt_date(p.fecha_vencimiento),
            ])
        self._current_cols, self._current_rows = cols, rows

    # -------------------- Inversion por producto -------------------- #
    def _run_investment_report(self) -> None:
        cols = ["ID", "Producto", "SKU", "Stock", "P. compra", "Inversion"]
        data: List[tuple[Decimal, List]] = []
        total = Decimal("0")
        for p in self.session.query(Product).order_by(Product.nombre.asc()).all():
            stock = int(p.stock_actual or 0)
            precio = Decimal(p.precio_compra or 0)
            inversion = precio * Decimal(stock)
            total += inversion
            row = [
                p.id,
                p.nombre or "",
                p.sku or "",
                stock,
                f"{float(precio or 0):.2f}",
                f"{float(inversion or 0):.2f}",
            ]
            data.append((inversion, row))
        data.sort(key=lambda item: item[0], reverse=True)
        rows = [row for _inv, row in data]
        rows.append(["", "TOTAL", "", "", "", f"{float(total or 0):.2f}"])
        self._current_cols, self._current_rows = cols, rows

    # -------------------- Exportar / Imprimir -------------------- #
    def _on_export(self) -> None:
        try:
            key = self._current_report_key or self.REPORTS[self.cmb_report.current() or 0][0]
            if key == "stock_real":
                flt = InventoryFilter(report_type="completo")
                path = generate_inventory_xlsx(self.session, flt, "Stock real")
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
        key = self._current_report_key or self.REPORTS[self.cmb_report.current() or 0][0]
        if key != "stock_real":
            messagebox.showinfo("Impresión", "Solo compatible con el informe de Stock real.")
            return
        # Usar impresora predeterminada si está configurada; de lo contrario preguntar
        printer_name = get_document_printer()
        if not printer_name:
            dlg = PrinterSelectDialog(self)
            self.wait_window(dlg)
            if not dlg.result:
                return
            printer_name = dlg.result
        try:
            flt = InventoryFilter(report_type="completo")
            path = print_inventory_report(self.session, flt, "Stock real", printer_name=printer_name)
            messagebox.showinfo("Impresión", f"Enviado a '{printer_name}'.\nArchivo: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir:\n{e}")


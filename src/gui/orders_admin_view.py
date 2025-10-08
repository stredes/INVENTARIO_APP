# src/gui/orders_admin_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Callable

from src.data.database import get_session
from src.data.models import (
    Supplier, Customer, Product,
    Purchase, PurchaseDetail,
    Sale, SaleDetail,
)
from src.core.inventory_manager import InventoryManager
from src.core.purchase_manager import PurchaseManager
from src.core.sales_manager import SalesManager

# Grilla tipo hoja (tksheet si está instalado; si no, Treeview)
from src.gui.widgets.grid_table import GridTable


class OrdersAdminView(ttk.Frame):
    """
    Administra Órdenes de Compra y Órdenes de Venta:
    - Listado de OC/OV con estado
    - Ver detalle (ítems)
    - Marcar Confirmada/Completada (ajusta stock)
    - Cancelar / Eliminar (revierte stock si corresponde)
    """

    # ----- Columnas (titulos + anchos) -----
    PUR_COLS = ["ID", "Fecha", "Proveedor", "Estado", "Total"]
    PUR_W    = [70, 130, 280, 120, 120]

    PUR_DET_COLS = ["ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]
    PUR_DET_W    = [80, 320, 80, 110, 130]

    SALE_COLS = ["ID", "Fecha", "Cliente", "Estado", "Total"]
    SALE_W    = [70, 130, 280, 120, 120]

    SALE_DET_COLS = ["ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]
    SALE_DET_W    = [80, 320, 80, 110, 130]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.inventory = InventoryManager(self.session)
        self.pm = PurchaseManager(self.session)
        self.sm = SalesManager(self.session)

        # Mapeos fila -> id (para selección)
        self._pur_ids: List[int] = []
        self._sale_ids: List[int] = []

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # --- TAB COMPRAS ---
        self.tab_compra = ttk.Frame(nb, padding=8)
        nb.add(self.tab_compra, text="Compras")
        self._init_purchase_tab(self.tab_compra)

        # --- TAB VENTAS ---
        self.tab_venta = ttk.Frame(nb, padding=8)
        nb.add(self.tab_venta, text="Ventas")
        self._init_sales_tab(self.tab_venta)

        # carga inicial
        self._load_purchases()
        self._load_sales()

    # ----------------- Utilidades de grilla -----------------
    def _apply_col_widths(self, table: GridTable, widths: List[int]) -> None:
        """Ajusta anchos en tksheet y en fallback Treeview."""
        if hasattr(table, "sheet"):
            try:
                for i, w in enumerate(widths):
                    table.sheet.column_width(i, width=w)
            except Exception:
                pass
        tv = getattr(table, "_fallback", None)
        if tv is not None:
            cols = list(tv["columns"]) if tv["columns"] else []
            for i, c in enumerate(cols):
                tv.column(c, width=widths[i] if i < len(widths) else 120, anchor=("center" if i == 0 else "w"))

    def _set_table_data(self, table: GridTable, cols: List[str], widths: List[int], rows: List[List]) -> None:
        table.set_data(cols, rows)
        self._apply_col_widths(table, widths)

    def _selected_row_index(self, table: GridTable) -> Optional[int]:
        """Índice de fila seleccionada (o None)."""
        if hasattr(table, "sheet"):
            try:
                rows = list(table.sheet.get_selected_rows())
                if rows:
                    return sorted(rows)[0]
                cells = table.sheet.get_selected_cells()
                if cells:
                    return sorted({r for r, _ in cells})[0]
            except Exception:
                return None
            return None
        tv = getattr(table, "_fallback", None)
        if tv is None:
            return None
        sel = tv.selection()
        if not sel:
            return None
        try:
            return tv.index(sel[0])
        except Exception:
            return None

    # ----------- Utilidades DB + feedback ----------- #
    def _handle_db_action(self, action: Callable, success_msg: str, reload_func: Callable):
        try:
            action()
            self.session.commit()
            reload_func()
            messagebox.showinfo("Éxito", success_msg)
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"Ocurrió un error:\n{e}")

    # ================== Inicialización pestaña COMPRAS ================== #
    def _init_purchase_tab(self, parent):
        top_c = ttk.Frame(parent); top_c.pack(fill="x")
        ttk.Button(top_c, text="Actualizar", command=self._load_purchases).pack(side="left", padx=4)
        ttk.Button(top_c, text="Marcar COMPLETADA (sumar stock)", command=self._purchase_mark_completed).pack(side="left", padx=4)
        ttk.Button(top_c, text="Cancelar (reversa si completada)", command=self._purchase_cancel).pack(side="left", padx=4)
        ttk.Button(top_c, text="Eliminar (reversa si completada)", command=self._purchase_delete).pack(side="left", padx=4)

        # Listado de compras
        self.tbl_pur = GridTable(parent, height=10)
        self.tbl_pur.pack(fill="both", expand=True, pady=(6, 4))
        # Selección (tksheet)
        if hasattr(self.tbl_pur, "sheet"):
            try:
                self.tbl_pur.sheet.extra_bindings([("cell_select", lambda e: self._on_purchase_selected())])
            except Exception:
                pass
        # Selección (fallback Treeview)
        tv = getattr(self.tbl_pur, "_fallback", None)
        if tv is not None:
            tv.bind("<<TreeviewSelect>>", lambda _e: self._on_purchase_selected())

        # Detalle de compra
        self.tbl_pur_det = GridTable(parent, height=8)
        self.tbl_pur_det.pack(fill="both", expand=False)

        # Inicializa headers vacíos
        self._set_table_data(self.tbl_pur, self.PUR_COLS, self.PUR_W, [])
        self._set_table_data(self.tbl_pur_det, self.PUR_DET_COLS, self.PUR_DET_W, [])

    # =================== Inicialización pestaña VENTAS ================== #
    def _init_sales_tab(self, parent):
        top_v = ttk.Frame(parent); top_v.pack(fill="x")
        ttk.Button(top_v, text="Actualizar", command=self._load_sales).pack(side="left", padx=4)
        ttk.Button(top_v, text="Marcar CONFIRMADA (descontar stock)", command=self._sale_mark_confirmed).pack(side="left", padx=4)
        ttk.Button(top_v, text="Cancelar (reversa si confirmada)", command=self._sale_cancel).pack(side="left", padx=4)
        ttk.Button(top_v, text="Eliminar (reversa si confirmada)", command=self._sale_delete).pack(side="left", padx=4)

        # Listado de ventas
        self.tbl_sale = GridTable(parent, height=10)
        self.tbl_sale.pack(fill="both", expand=True, pady=(6, 4))
        if hasattr(self.tbl_sale, "sheet"):
            try:
                self.tbl_sale.sheet.extra_bindings([("cell_select", lambda e: self._on_sale_selected())])
            except Exception:
                pass
        tv = getattr(self.tbl_sale, "_fallback", None)
        if tv is not None:
            tv.bind("<<TreeviewSelect>>", lambda _e: self._on_sale_selected())

        # Detalle de venta
        self.tbl_sale_det = GridTable(parent, height=8)
        self.tbl_sale_det.pack(fill="both", expand=False)

        # Inicializa headers vacíos
        self._set_table_data(self.tbl_sale, self.SALE_COLS, self.SALE_W, [])
        self._set_table_data(self.tbl_sale_det, self.SALE_DET_COLS, self.SALE_DET_W, [])

    # ============================= Compras ============================= #
    def _load_purchases(self):
        rows: List[List] = []
        self._pur_ids = []

        q = (
            self.session.query(Purchase, Supplier)
            .join(Supplier, Supplier.id == Purchase.id_proveedor)
            .order_by(Purchase.id.desc())
        )
        for pur, sup in q:
            fecha = pur.fecha_compra.strftime("%Y-%m-%d %H:%M")
            proveedor = getattr(sup, "razon_social", "") or "-"
            rows.append([pur.id, fecha, proveedor, pur.estado, f"{pur.total_compra:.2f}"])
            self._pur_ids.append(int(pur.id))

        self._set_table_data(self.tbl_pur, self.PUR_COLS, self.PUR_W, rows)
        # Limpia detalle
        self._set_table_data(self.tbl_pur_det, self.PUR_DET_COLS, self.PUR_DET_W, [])

    def _on_purchase_selected(self, _evt: object | None = None):
        pid = self._get_selected_purchase_id()
        if pid is not None:
            self._load_purchase_details(pid)

    def _get_selected_purchase_id(self) -> Optional[int]:
        idx = self._selected_row_index(self.tbl_pur)
        if idx is None or idx < 0 or idx >= len(self._pur_ids):
            return None
        return self._pur_ids[idx]

    def _load_purchase_details(self, purchase_id: int):
        rows: List[List] = []
        q = (
            self.session.query(PurchaseDetail, Product)
            .join(Product, Product.id == PurchaseDetail.id_producto)
            .filter(PurchaseDetail.id_compra == purchase_id)
        )
        for det, prod in q:
            rows.append([prod.id, prod.nombre, det.cantidad, f"{det.precio_unitario:.2f}", f"{det.subtotal:.2f}"])

        self._set_table_data(self.tbl_pur_det, self.PUR_DET_COLS, self.PUR_DET_W, rows)

    def _get_selected_purchase(self) -> Optional[Purchase]:
        pid = self._get_selected_purchase_id()
        return self.session.get(Purchase, pid) if pid else None

    def _purchase_mark_completed(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        if str(pur.estado).strip().lower() == "completada":
            messagebox.showinfo("Compras", "Esta compra ya está COMPLETADA.")
            return

        def action():
            for det in pur.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Compra {pur.id}",
                )
            pur.estado = "Completada"

        self._handle_db_action(
            action,
            f"Compra {pur.id} marcada como COMPLETADA y stock actualizado.",
            self._load_purchases
        )

    def _purchase_cancel(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return

        def action():
            self.pm.cancel_purchase(pur.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Compra {pur.id} cancelada.",
            self._load_purchases
        )

    def _purchase_delete(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar compra {pur.id}?"):
            return

        def action():
            self.pm.delete_purchase(pur.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Compra {pur.id} eliminada.",
            self._load_purchases
        )

    # ============================== Ventas ============================= #
    def _load_sales(self):
        rows: List[List] = []
        self._sale_ids = []

        q = (
            self.session.query(Sale, Customer)
            .join(Customer, Customer.id == Sale.id_cliente)
            .order_by(Sale.id.desc())
        )
        for sale, cust in q:
            if str(sale.estado).strip().lower() == "eliminada":
                continue
            fecha = sale.fecha_venta.strftime("%Y-%m-%d %H:%M")
            cliente = getattr(cust, "razon_social", "") or "-"
            rows.append([sale.id, fecha, cliente, sale.estado, f"{sale.total_venta:.2f}"])
            self._sale_ids.append(int(sale.id))

        self._set_table_data(self.tbl_sale, self.SALE_COLS, self.SALE_W, rows)
        # Limpia detalle
        self._set_table_data(self.tbl_sale_det, self.SALE_DET_COLS, self.SALE_DET_W, [])

    def _on_sale_selected(self, _evt: object | None = None):
        sid = self._get_selected_sale_id()
        if sid is not None:
            self._load_sale_details(sid)

    def _get_selected_sale_id(self) -> Optional[int]:
        idx = self._selected_row_index(self.tbl_sale)
        if idx is None or idx < 0 or idx >= len(self._sale_ids):
            return None
        return self._sale_ids[idx]

    def _load_sale_details(self, sale_id: int):
        rows: List[List] = []
        q = (
            self.session.query(SaleDetail, Product)
            .join(Product, Product.id == SaleDetail.id_producto)
            .filter(SaleDetail.id_venta == sale_id)
        )
        for det, prod in q:
            rows.append([prod.id, prod.nombre, det.cantidad, f"{det.precio_unitario:.2f}", f"{det.subtotal:.2f}"])

        self._set_table_data(self.tbl_sale_det, self.SALE_DET_COLS, self.SALE_DET_W, rows)

    def _get_selected_sale(self) -> Optional[Sale]:
        sid = self._get_selected_sale_id()
        return self.session.get(Sale, sid) if sid else None

    def _sale_mark_confirmed(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        if str(sale.estado).strip().lower() == "confirmada":
            messagebox.showinfo("Ventas", "Esta venta ya está CONFIRMADA.")
            return

        def action():
            for det in sale.details:
                self.inventory.register_exit(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Venta {sale.id}",
                )
            sale.estado = "Confirmada"

        self._handle_db_action(
            action,
            f"Venta {sale.id} marcada como CONFIRMADA y stock actualizado.",
            self._load_sales
        )

    def _sale_cancel(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return

        def action():
            self.sm.cancel_sale(sale.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Venta {sale.id} cancelada.",
            self._load_sales
        )

    def _sale_delete(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar venta {sale.id}?"):
            return

        def action():
            self.sm.delete_sale(sale.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Venta {sale.id} eliminada.",
            self._load_sales
        )

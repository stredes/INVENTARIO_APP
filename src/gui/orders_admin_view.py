from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional

from src.data.database import get_session
from src.data.models import (
    Supplier, Customer, Product,
    Purchase, PurchaseDetail,
    Sale, SaleDetail,
)
from src.core.inventory_manager import InventoryManager
from src.core.purchase_manager import PurchaseManager
from src.core.sales_manager import SalesManager


class OrdersAdminView(ttk.Frame):
    """
    Administra Órdenes de Compra y Órdenes de Venta:
    - Listado de OC/OV con estado
    - Ver detalle (ítems)
    - Marcar Confirmada/Completada (aplica stock)
    - Cancelar (revierte stock si estaba confirmada/completada)
    - Eliminar (revierte si corresponde)
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.inventory = InventoryManager(self.session)
        self.pm = PurchaseManager(self.session)
        self.sm = SalesManager(self.session)

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        # --- TAB COMPRAS ---
        self.tab_compra = ttk.Frame(nb, padding=8)
        nb.add(self.tab_compra, text="Compras")

        top_c = ttk.Frame(self.tab_compra); top_c.pack(fill="x")
        ttk.Button(top_c, text="Actualizar", command=self._load_purchases)\
            .pack(side="left", padx=4)
        ttk.Button(top_c, text="Marcar COMPLETADA (sumar stock)", command=self._purchase_mark_completed)\
            .pack(side="left", padx=4)
        ttk.Button(top_c, text="Cancelar (reversa si completada)", command=self._purchase_cancel)\
            .pack(side="left", padx=4)
        ttk.Button(top_c, text="Eliminar (reversa si completada)", command=self._purchase_delete)\
            .pack(side="left", padx=4)

        self.tree_pur = ttk.Treeview(
            self.tab_compra,
            columns=("id", "fecha", "proveedor", "estado", "total"),
            show="headings", height=10
        )
        for cid, txt, w, anc in [
            ("id", "ID", 70, "center"),
            ("fecha", "Fecha", 130, "w"),
            ("proveedor", "Proveedor", 280, "w"),
            ("estado", "Estado", 120, "center"),
            ("total", "Total", 120, "e"),
        ]:
            self.tree_pur.heading(cid, text=txt)
            self.tree_pur.column(cid, width=w, anchor=anc)
        self.tree_pur.pack(fill="both", expand=True, pady=(6, 4))
        self.tree_pur.bind("<<TreeviewSelect>>", self._on_purchase_selected)

        self.tree_pur_det = ttk.Treeview(
            self.tab_compra,
            columns=("prod_id", "producto", "cant", "precio", "subtotal"),
            show="headings", height=8
        )
        for cid, txt, w, anc in [
            ("prod_id", "ID Prod", 80, "center"),
            ("producto", "Producto", 320, "w"),
            ("cant", "Cant.", 80, "e"),
            ("precio", "Precio", 110, "e"),
            ("subtotal", "Subtotal", 130, "e"),
        ]:
            self.tree_pur_det.heading(cid, text=txt)
            self.tree_pur_det.column(cid, width=w, anchor=anc)
        self.tree_pur_det.pack(fill="both", expand=False)

        # --- TAB VENTAS ---
        self.tab_venta = ttk.Frame(nb, padding=8)
        nb.add(self.tab_venta, text="Ventas")

        top_v = ttk.Frame(self.tab_venta); top_v.pack(fill="x")
        ttk.Button(top_v, text="Actualizar", command=self._load_sales)\
            .pack(side="left", padx=4)
        ttk.Button(top_v, text="Marcar CONFIRMADA (descontar stock)", command=self._sale_mark_confirmed)\
            .pack(side="left", padx=4)
        ttk.Button(top_v, text="Cancelar (reversa si confirmada)", command=self._sale_cancel)\
            .pack(side="left", padx=4)
        ttk.Button(top_v, text="Eliminar (reversa si confirmada)", command=self._sale_delete)\
            .pack(side="left", padx=4)

        self.tree_sale = ttk.Treeview(
            self.tab_venta,
            columns=("id", "fecha", "cliente", "estado", "total"),
            show="headings", height=10
        )
        for cid, txt, w, anc in [
            ("id", "ID", 70, "center"),
            ("fecha", "Fecha", 130, "w"),
            ("cliente", "Cliente", 280, "w"),
            ("estado", "Estado", 120, "center"),
            ("total", "Total", 120, "e"),
        ]:
            self.tree_sale.heading(cid, text=txt)
            self.tree_sale.column(cid, width=w, anchor=anc)
        self.tree_sale.pack(fill="both", expand=True, pady=(6, 4))
        self.tree_sale.bind("<<TreeviewSelect>>", self._on_sale_selected)

        self.tree_sale_det = ttk.Treeview(
            self.tab_venta,
            columns=("prod_id", "producto", "cant", "precio", "subtotal"),
            show="headings", height=8
        )
        for cid, txt, w, anc in [
            ("prod_id", "ID Prod", 80, "center"),
            ("producto", "Producto", 320, "w"),
            ("cant", "Cant.", 80, "e"),
            ("precio", "Precio", 110, "e"),
            ("subtotal", "Subtotal", 130, "e"),
        ]:
            self.tree_sale_det.heading(cid, text=txt)
            self.tree_sale_det.column(cid, width=w, anchor=anc)
        self.tree_sale_det.pack(fill="both", expand=False)

        # carga inicial
        self._load_purchases()
        self._load_sales()

    # ----------------------- Compras -----------------------
    def _load_purchases(self):
        for i in self.tree_pur.get_children():
            self.tree_pur.delete(i)
        q = (
            self.session.query(Purchase, Supplier)
            .join(Supplier, Supplier.id == Purchase.id_proveedor)
            .order_by(Purchase.id.desc())
        )
        for pur, sup in q:
            fecha = pur.fecha_compra.strftime("%Y-%m-%d %H:%M")
            proveedor = getattr(sup, "razon_social", "") or "-"
            self.tree_pur.insert(
                "", "end",
                iid=f"p_{pur.id}",
                values=(pur.id, fecha, proveedor, pur.estado, f"{pur.total_compra:.2f}")
            )
        # limpiar detalle
        for i in self.tree_pur_det.get_children():
            self.tree_pur_det.delete(i)

    def _on_purchase_selected(self, _evt=None):
        sel = self.tree_pur.selection()
        if not sel:
            return
        pid = int(self.tree_pur.item(sel[0], "values")[0])
        self._load_purchase_details(pid)

    def _load_purchase_details(self, purchase_id: int):
        for i in self.tree_pur_det.get_children():
            self.tree_pur_det.delete(i)
        q = (
            self.session.query(PurchaseDetail, Product)
            .join(Product, Product.id == PurchaseDetail.id_producto)
            .filter(PurchaseDetail.id_compra == purchase_id)
        )
        for det, prod in q:
            self.tree_pur_det.insert(
                "", "end",
                values=(prod.id, prod.nombre, det.cantidad, f"{det.precio_unitario:.2f}", f"{det.subtotal:.2f}")
            )

    def _get_selected_purchase(self) -> Optional[Purchase]:
        sel = self.tree_pur.selection()
        if not sel:
            return None
        pid = int(self.tree_pur.item(sel[0], "values")[0])
        return self.session.get(Purchase, pid)

    def _purchase_mark_completed(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        if pur.estado.lower() == "completada":
            messagebox.showinfo("Compras", "Esta compra ya está COMPLETADA.")
            return
        try:
            # aplicar entradas de stock por cada detalle
            for det in pur.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Compra {pur.id}",
                )
            pur.estado = "Completada"
            self.session.commit()
            self._load_purchases()
            messagebox.showinfo("Compras", f"Compra {pur.id} marcada como COMPLETADA y stock actualizado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo completar la compra:\n{e}")

    def _purchase_cancel(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        try:
            self.pm.cancel_purchase(pur.id, revert_stock=True)
            self._load_purchases()
            messagebox.showinfo("Compras", f"Compra {pur.id} cancelada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cancelar:\n{e}")

    def _purchase_delete(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar compra {pur.id}?"):
            return
        try:
            self.pm.delete_purchase(pur.id, revert_stock=True)
            self._load_purchases()
            messagebox.showinfo("Compras", f"Compra {pur.id} eliminada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

    # ------------------------ Ventas -----------------------
    def _load_sales(self):
        for i in self.tree_sale.get_children():
            self.tree_sale.delete(i)
        q = (
            self.session.query(Sale, Customer)
            .join(Customer, Customer.id == Sale.id_cliente)
            .order_by(Sale.id.desc())
        )
        for sale, cust in q:
            # OCULTAR ventas eliminadas
            if str(sale.estado).strip().lower() == "eliminada":
                continue
            fecha = sale.fecha_venta.strftime("%Y-%m-%d %H:%M")
            cliente = getattr(cust, "razon_social", "") or "-"
            self.tree_sale.insert(
                "", "end",
                iid=f"s_{sale.id}",
                values=(sale.id, fecha, cliente, sale.estado, f"{sale.total_venta:.2f}")
            )
        for i in self.tree_sale_det.get_children():
            self.tree_sale_det.delete(i)

    def _on_sale_selected(self, _evt=None):
        sel = self.tree_sale.selection()
        if not sel:
            return
        sid = int(self.tree_sale.item(sel[0], "values")[0])
        self._load_sale_details(sid)

    def _load_sale_details(self, sale_id: int):
        for i in self.tree_sale_det.get_children():
            self.tree_sale_det.delete(i)
        q = (
            self.session.query(SaleDetail, Product)
            .join(Product, Product.id == SaleDetail.id_producto)
            .filter(SaleDetail.id_venta == sale_id)
        )
        for det, prod in q:
            self.tree_sale_det.insert(
                "", "end",
                values=(prod.id, prod.nombre, det.cantidad, f"{det.precio_unitario:.2f}", f"{det.subtotal:.2f}")
            )

    def _get_selected_sale(self) -> Optional[Sale]:
        sel = self.tree_sale.selection()
        if not sel:
            return None
        sid = int(self.tree_sale.item(sel[0], "values")[0])
        return self.session.get(Sale, sid)

    def _sale_mark_confirmed(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        if sale.estado.lower() == "confirmada":
            messagebox.showinfo("Ventas", "Esta venta ya está CONFIRMADA.")
            return
        try:
            for det in sale.details:
                self.inventory.register_exit(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Venta {sale.id}",
                )
            sale.estado = "Confirmada"
            self.session.commit()
            self._load_sales()
            messagebox.showinfo("Ventas", f"Venta {sale.id} marcada como CONFIRMADA y stock actualizado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo confirmar la venta:\n{e}")

    def _sale_cancel(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        try:
            self.sm.cancel_sale(sale.id, revert_stock=True)
            self._load_sales()
            messagebox.showinfo("Ventas", f"Venta {sale.id} cancelada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cancelar:\n{e}")

    def _sale_delete(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        if not messagebox.askyesno("Confirmar", f"¿Eliminar venta {sale.id}?"):
            return
        try:
            self.sm.delete_sale(sale.id, revert_stock=True)
            self._load_sales()
            messagebox.showinfo("Ventas", f"Venta {sale.id} eliminada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

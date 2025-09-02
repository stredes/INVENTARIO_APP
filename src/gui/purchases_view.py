from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List

from src.data.database import get_session
from src.data.models import Product, Supplier
from src.data.repository import ProductRepository, SupplierRepository
from src.core import PurchaseManager, PurchaseItem
from src.utils.po_generator import generate_po_to_downloads


class PurchasesView(ttk.Frame):
    """
    Crear compras + Generar OC + ADMIN (cancelar/eliminar compra por ID con reversa de stock).
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.pm = PurchaseManager(self.session)

        self.repo_prod = ProductRepository(self.session)
        self.repo_sup = SupplierRepository(self.session)

        self.products: List[Product] = []
        self.suppliers: List[Supplier] = []

        # ---------- Encabezado ----------
        top = ttk.Labelframe(self, text="Encabezado de compra", padding=10)
        top.pack(fill="x", expand=False)

        ttk.Label(top, text="Proveedor:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_supplier = ttk.Combobox(top, state="readonly", width=40)
        self.cmb_supplier.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        self.var_apply = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Impactar stock (Completada)", variable=self.var_apply).grid(row=0, column=2, padx=10)

        # ---------- Detalle ----------
        det = ttk.Labelframe(self, text="Detalle de compra", padding=10)
        det.pack(fill="x", expand=False, pady=(10, 0))

        ttk.Label(det, text="Producto:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_product = ttk.Combobox(det, state="readonly", width=40)
        self.cmb_product.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Cantidad:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.ent_qty = ttk.Entry(det, width=10); self.ent_qty.insert(0, "1")
        self.ent_qty.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Precio Unit.:").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.ent_price = ttk.Entry(det, width=12); self.ent_price.insert(0, "0")
        self.ent_price.grid(row=0, column=5, sticky="w", padx=4, pady=4)

        ttk.Button(det, text="Agregar ítem", command=self._on_add_item).grid(row=0, column=6, padx=8)

        # Tabla de detalle
        self.tree = ttk.Treeview(
            self,
            columns=("prod_id", "producto", "cant", "precio", "subtotal"),
            show="headings", height=10
        )
        for cid, text, w, anchor in [
            ("prod_id", "ID", 60, "center"),
            ("producto", "Producto", 300, "w"),
            ("cant", "Cant.", 80, "e"),
            ("precio", "Precio", 100, "e"),
            ("subtotal", "Subtotal", 120, "e"),
        ]:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, pady=(10, 0))

        # Total + acciones
        bottom = ttk.Frame(self); bottom.pack(fill="x", expand=False, pady=10)
        self.lbl_total = ttk.Label(bottom, text="Total: 0.00", font=("", 11, "bold")); self.lbl_total.pack(side="left")
        ttk.Button(bottom, text="Eliminar ítem", command=self._on_delete_item).pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar OC (PDF en Descargas)", command=self._on_generate_po_downloads).pack(side="right", padx=6)
        ttk.Button(bottom, text="Confirmar compra", command=self._on_confirm_purchase).pack(side="right", padx=6)

        # ---------- Admin CRUD Compra ----------
        admin = ttk.Labelframe(self, text="Administrar compras (Cancelar / Eliminar)", padding=10)
        admin.pack(fill="x", expand=False, pady=(10,0))
        ttk.Label(admin, text="ID Compra:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.ent_pur_id = ttk.Entry(admin, width=10); self.ent_pur_id.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(admin, text="Cancelar (reversa stock si completada)", command=self._on_cancel_purchase).grid(row=0, column=2, padx=6)
        ttk.Button(admin, text="Eliminar (reversa si completada)", command=self._on_delete_purchase).grid(row=0, column=3, padx=6)

        self.refresh_lookups()

    # ---------- Lookups ----------
    def refresh_lookups(self):
        self.suppliers = self.session.query(Supplier).order_by(Supplier.nombre.asc()).all()
        self.cmb_supplier["values"] = [f"{s.id} - {s.nombre}" for s in self.suppliers]
        if self.suppliers and not self.cmb_supplier.get():
            self.cmb_supplier.current(0)

        self.products = self.session.query(Product).order_by(Product.nombre.asc()).all()
        self.cmb_product["values"] = [f"{p.id} - {p.nombre} [{p.sku}]" for p in self.products]
        if self.products and not self.cmb_product.get():
            self.cmb_product.current(0)

    # ---------- Acciones UI ----------
    def _on_add_item(self):
        try:
            prod_idx = self.cmb_product.current()
            if prod_idx < 0:
                messagebox.showwarning("Validación", "Seleccione un producto."); return
            p = self.products[prod_idx]
            qty = int(self.ent_qty.get()); price = float(self.ent_price.get())
            if qty <= 0 or price <= 0:
                messagebox.showwarning("Validación", "Cantidad y precio deben ser > 0."); return
            subtotal = qty * price
            self.tree.insert("", "end", values=(p.id, p.nombre, qty, f"{price:.2f}", f"{subtotal:.2f}"))
            self._update_total()
            self.ent_qty.delete(0,"end"); self.ent_qty.insert(0,"1")
            self.ent_price.delete(0,"end"); self.ent_price.insert(0,"0")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo agregar el ítem:\n{e}")

    def _on_delete_item(self):
        for item in self.tree.selection(): self.tree.delete(item)
        self._update_total()

    def _update_total(self):
        total = 0.0
        for iid in self.tree.get_children():
            vals = self.tree.item(iid, "values")
            total += float(vals[4])
        self.lbl_total.config(text=f"Total: {total:.2f}")

    def _collect_items(self) -> List[dict]:
        items: List[dict] = []
        for iid in self.tree.get_children():
            prod_id, name, qty, price, sub = self.tree.item(iid, "values")
            items.append({"id": int(prod_id), "nombre": str(name), "cantidad": int(qty), "precio": float(price), "subtotal": float(sub)})
        return items

    def _get_selected_supplier_dict(self) -> dict:
        idx = self.cmb_supplier.current()
        if idx < 0:
            raise RuntimeError("Seleccione un proveedor")
        s = self.suppliers[idx]
        return {"id": s.id, "nombre": s.nombre, "contacto": s.contacto, "telefono": s.telefono, "email": s.email, "direccion": s.direccion}

    def _on_confirm_purchase(self):
        try:
            items = self._collect_items()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem."); return
            sup = self._get_selected_supplier_dict()
            pm_items = [PurchaseItem(product_id=it["id"], cantidad=it["cantidad"], precio_unitario=it["precio"]) for it in items]
            self.pm.create_purchase(
                supplier_id=sup["id"],
                items=pm_items,
                estado="Completada" if self.var_apply.get() else "Pendiente",
                apply_to_stock=self.var_apply.get(),
            )
            for iid in self.tree.get_children(): self.tree.delete(iid)
            self._update_total()
            messagebox.showinfo("OK", "Compra creada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo confirmar la compra:\n{e}")

    def _on_generate_po_downloads(self):
        try:
            items = self._collect_items()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem a la OC."); return
            sup = self._get_selected_supplier_dict()
            po_number = f"OC-{sup['id']}-{self._stamp()}"
            out_path = generate_po_to_downloads(
                po_number=po_number, supplier=sup, items=items, currency="CLP", notes=None, auto_open=True
            )
            messagebox.showinfo("OC generada", f"Orden de Compra creada en Descargas:\n{out_path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar la OC:\n{e}")

    def _on_cancel_purchase(self):
        try:
            pid = int(self.ent_pur_id.get())
            self.pm.cancel_purchase(pid, revert_stock=True)
            messagebox.showinfo("OK", f"Compra {pid} cancelada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cancelar:\n{e}")

    def _on_delete_purchase(self):
        try:
            pid = int(self.ent_pur_id.get())
            if not messagebox.askyesno("Confirmar", f"¿Eliminar compra {pid}?"):
                return
            self.pm.delete_purchase(pid, revert_stock=True)
            messagebox.showinfo("OK", f"Compra {pid} eliminada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

    @staticmethod
    def _stamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d-%H%M%S")

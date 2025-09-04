from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Dict, Callable

from src.data.database import get_session
from src.data.models import Product, Customer
from src.data.repository import ProductRepository, CustomerRepository
from src.core import SalesManager, SaleItem
from src.utils.so_generator import generate_so_to_downloads


class SalesView(ttk.Frame):
    """
    Crear ventas + Generar OV + ADMIN (cancelar/eliminar venta por ID con reversa de stock).
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.sm = SalesManager(self.session)
        self.repo_prod = ProductRepository(self.session)
        self.repo_cust = CustomerRepository(self.session)

        self.products: List[Product] = []
        self.customers: List[Customer] = []

        # ---------- Encabezado ----------
        top = ttk.Labelframe(self, text="Encabezado de venta", padding=10)
        top.pack(fill="x", expand=False)

        ttk.Label(top, text="Cliente:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_customer = ttk.Combobox(top, state="readonly", width=50)
        self.cmb_customer.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        self.var_apply = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Descontar stock (Confirmada)", variable=self.var_apply)\
            .grid(row=0, column=2, padx=10)

        # ---------- Detalle ----------
        det = ttk.Labelframe(self, text="Detalle de venta", padding=10)
        det.pack(fill="x", expand=False, pady=(10, 0))

        ttk.Label(det, text="Producto:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_product = ttk.Combobox(det, state="readonly", width=45)
        self.cmb_product.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        # Autocompletar precio al cambiar de producto
        self.cmb_product.bind("<<ComboboxSelected>>", self._on_product_change)

        ttk.Label(det, text="Cantidad:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.ent_qty = ttk.Entry(det, width=10)
        self.ent_qty.insert(0, "1")
        self.ent_qty.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Precio (venta):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.ent_price = ttk.Entry(det, width=12)
        self.ent_price.insert(0, "0")
        self.ent_price.grid(row=0, column=5, sticky="w", padx=4, pady=4)

        ttk.Button(det, text="Agregar ítem", command=self._on_add_item)\
            .grid(row=0, column=6, padx=8)

        # ---------- Tabla ----------
        self.tree = ttk.Treeview(
            self,
            columns=("prod_id", "producto", "cant", "precio", "subtotal"),
            show="headings",
            height=10,
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

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", expand=False, pady=10)
        self.lbl_total = ttk.Label(bottom, text="Total: 0.00", font=("", 11, "bold"))
        self.lbl_total.pack(side="left")
        ttk.Button(bottom, text="Eliminar ítem", command=self._on_delete_item)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar OV (PDF en Descargas)", command=self._on_generate_so_downloads)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Confirmar venta", command=self._on_confirm_sale)\
            .pack(side="right", padx=6)

        # ---------- Admin CRUD Venta ----------
        admin = ttk.Labelframe(self, text="Administrar ventas (Cancelar / Eliminar)", padding=10)
        admin.pack(fill="x", expand=False, pady=(10, 0))
        ttk.Label(admin, text="ID Venta:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.ent_sale_id = ttk.Entry(admin, width=10)
        self.ent_sale_id.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(admin, text="Cancelar (reversa stock si confirmada)", command=self._on_cancel_sale)\
            .grid(row=0, column=2, padx=6)
        ttk.Button(admin, text="Eliminar (reversa si confirmada)", command=self._on_delete_sale)\
            .grid(row=0, column=3, padx=6)

        self.refresh_lookups()

    # -------------------- Lookups --------------------
    def refresh_lookups(self):
        # Clientes por razón social
        self.customers = self.session.query(Customer)\
            .order_by(Customer.razon_social.asc()).all()
        self.cmb_customer["values"] = [self._display_customer(c) for c in self.customers]
        if self.customers and not self.cmb_customer.get():
            self.cmb_customer.current(0)

        # Productos por nombre
        self.products = self.session.query(Product).order_by(Product.nombre.asc()).all()
        self.cmb_product["values"] = [f"{p.id} - {p.nombre} [{p.sku}]" for p in self.products]
        if self.products and not self.cmb_product.get():
            self.cmb_product.current(0)
            # precargar precio del primero
            self._fill_price_from_selected_product()

    def _display_customer(self, c: Customer) -> str:
        rut = getattr(c, "rut", "") or ""
        rs = getattr(c, "razon_social", "") or ""
        if rut and rs:
            return f"{rut} — {rs}"
        return rs or rut or f"Cliente {c.id}"

    def _get_selected_customer(self) -> Optional[Customer]:
        idx = self.cmb_customer.current()
        if idx is None or idx < 0:
            return None
        return self.customers[idx]

    # -------------------- UI helpers --------------------
    def _on_product_change(self, _evt=None):
        self._fill_price_from_selected_product()

    def _fill_price_from_selected_product(self):
        idx = self.cmb_product.current()
        if idx is None or idx < 0 or idx >= len(self.products):
            return
        p = self.products[idx]
        try:
            pv = float(p.precio_venta or 0)
            if pv > 0:
                self.ent_price.delete(0, "end")
                self.ent_price.insert(0, f"{pv:.2f}")
        except Exception:
            pass

    # -------------------- Ítems --------------------
    def _on_add_item(self):
        try:
            idx = self.cmb_product.current()
            if idx is None or idx < 0:
                messagebox.showwarning("Validación", "Seleccione un producto.")
                return
            p = self.products[idx]

            # Cantidad
            qty = int(float(self.ent_qty.get()))
            if qty <= 0:
                messagebox.showwarning("Validación", "La cantidad debe ser > 0.")
                return

            # Precio: si no se indicó, usar precio_venta del producto
            try:
                price = float(self.ent_price.get())
            except ValueError:
                price = 0.0
            if price <= 0:
                price = float(p.precio_venta or 0)
            if price <= 0:
                messagebox.showwarning("Validación", "Ingrese un precio válido (> 0).")
                return

            subtotal = qty * price
            self.tree.insert("", "end",
                             values=(p.id, p.nombre, qty, f"{price:.2f}", f"{subtotal:.2f}"))
            self._update_total()

            self.ent_qty.delete(0, "end"); self.ent_qty.insert(0, "1")
            self._fill_price_from_selected_product()

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo agregar el ítem:\n{e}")

    def _on_delete_item(self):
        for item in self.tree.selection():
            self.tree.delete(item)
        self._update_total()

    def _update_total(self):
        total = 0.0
        for iid in self.tree.get_children():
            try:
                total += float(self.tree.item(iid, "values")[4])
            except Exception:
                pass
        self.lbl_total.config(text=f"Total: {total:.2f}")

    def _collect_items(self) -> List[dict]:
        items: List[dict] = []
        for iid in self.tree.get_children():
            prod_id, name, qty, price, sub = self.tree.item(iid, "values")
            items.append({
                "id": int(prod_id),
                "nombre": str(name),
                "cantidad": int(float(qty)),
                "precio": float(price),
                "subtotal": float(sub),
            })
        return items

    def _get_selected_customer_dict(self) -> Dict[str, Optional[str]]:
        c = self._get_selected_customer()
        if not c:
            raise RuntimeError("Seleccione un cliente")
        return {
            "id": c.id,
            "razon_social": getattr(c, "razon_social", None),
            "rut": getattr(c, "rut", None),
            "contacto": c.contacto,
            "telefono": c.telefono,
            "email": c.email,
            "direccion": c.direccion,
        }

    # -------------------- Acciones Venta --------------------
    def _resolve_create_sale(self) -> Callable:
        """
        Devuelve el método adecuado del SalesManager para crear una venta.
        Soporta distintos nombres posibles para compatibilidad.
        """
        for name in ("create_sale", "create", "register_sale", "add_sale"):
            if hasattr(self.sm, name):
                return getattr(self.sm, name)
        raise AttributeError("SalesManager no expone un método para crear ventas (create_sale/create/...)")

    def _on_confirm_sale(self):
        try:
            items = self._collect_items()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem.")
                return
            cust = self._get_selected_customer()
            if not cust:
                messagebox.showwarning("Validación", "Seleccione un cliente.")
                return

            sm_items = [
                SaleItem(product_id=it["id"], cantidad=it["cantidad"], precio_unitario=it["precio"])
                for it in items
            ]

            create_fn = self._resolve_create_sale()
            create_fn(
                customer_id=cust.id,
                items=sm_items,
                estado="Confirmada" if self.var_apply.get() else "Borrador",
                apply_to_stock=self.var_apply.get(),
            )

            # Limpiar detalle
            for iid in list(self.tree.get_children()):
                self.tree.delete(iid)
            self._update_total()

            messagebox.showinfo("OK", "Venta registrada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo confirmar la venta:\n{e}")

    def _on_generate_so_downloads(self):
        try:
            items = self._collect_items()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem.")
                return
            cust = self._get_selected_customer_dict()
            so_number = f"OV-{cust['id']}-{self._stamp()}"
            out = generate_so_to_downloads(
                so_number=so_number,
                customer=cust,
                items=items,
                currency="CLP",
                notes=None,
                auto_open=True,
            )
            messagebox.showinfo("OV generada", f"Orden de Venta creada en Descargas:\n{out}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar la OV:\n{e}")

    def _on_cancel_sale(self):
        try:
            sid = int(self.ent_sale_id.get())
            self.sm.cancel_sale(sid, revert_stock=True)
            messagebox.showinfo("OK", f"Venta {sid} cancelada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo cancelar:\n{e}")

    def _on_delete_sale(self):
        try:
            sid = int(self.ent_sale_id.get())
            if not messagebox.askyesno("Confirmar", f"¿Eliminar venta {sid}?"):
                return
            self.sm.delete_sale(sid, revert_stock=True)
            messagebox.showinfo("OK", f"Venta {sid} eliminada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

    @staticmethod
    def _stamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d-%H%M%S")

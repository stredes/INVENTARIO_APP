from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Dict

from src.data.database import get_session
from src.data.models import Product, Supplier
from src.data.repository import ProductRepository, SupplierRepository
from src.core import PurchaseManager, PurchaseItem
from src.utils.po_generator import generate_po_to_downloads
# NUEVO: import del generador de cotización
from src.utils.quote_generator import generate_quote_to_downloads as generate_quote_downloads
# NUEVO: widget de autocompletado
from src.gui.widgets.autocomplete_combobox import AutoCompleteCombobox

IVA_RATE = 0.19  # 19% IVA por defecto


class PurchasesView(ttk.Frame):
    """
    Módulo de Compras:
    - Seleccionas Proveedor y Productos (AHORA: productos filtrados por proveedor)
    - El Precio Unitario se calcula automático: precio_compra * (1 + IVA)
    - Confirmas compra (puede sumar stock)
    - Generas Orden de Compra (PDF) a Descargas
    - (Nuevo) Generas Cotización (PDF) a Descargas sin afectar stock
    - (Nuevo) Autocompletado de productos por ID/nombre/SKU
    - (Nuevo) Validación: NO se permiten productos de proveedor distinto al seleccionado.
    """

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.pm = PurchaseManager(self.session)
        self.repo_prod = ProductRepository(self.session)
        self.repo_supp = SupplierRepository(self.session)

        self.products: List[Product] = []   # dataset actual (filtrado por proveedor)
        self.suppliers: List[Supplier] = []

        # ---------- Encabezado ----------
        head = ttk.Labelframe(self, text="Encabezado de compra", padding=10)
        head.pack(fill="x", expand=False)

        ttk.Label(head, text="Proveedor:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_supplier = ttk.Combobox(head, state="readonly", width=50)
        self.cmb_supplier.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        # Al cambiar proveedor, se filtra el dataset de productos
        self.cmb_supplier.bind("<<ComboboxSelected>>", self._on_supplier_selected)

        self.var_apply = tk.BooleanVar(value=True)
        ttk.Checkbutton(head, text="Sumar stock (Completada)", variable=self.var_apply).grid(row=0, column=2, padx=10)

        # ---------- Detalle ----------
        det = ttk.Labelframe(self, text="Detalle de compra", padding=10)
        det.pack(fill="x", expand=False, pady=(8, 0))

        ttk.Label(det, text="Producto:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        # ANTES: ttk.Combobox
        # AHORA: autocomplete que permite escribir para filtrar
        self.cmb_product = AutoCompleteCombobox(det, width=45, state="normal")
        self.cmb_product.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.cmb_product.bind("<<ComboboxSelected>>", self._on_product_change)

        ttk.Label(det, text="Cantidad:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.ent_qty = ttk.Entry(det, width=10)
        self.ent_qty.insert(0, "1")
        self.ent_qty.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Precio Unit. (c/IVA):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.var_price = tk.StringVar(value="0.00")
        self.ent_price = ttk.Entry(det, textvariable=self.var_price, width=14, state="readonly")
        self.ent_price.grid(row=0, column=5, sticky="w", padx=4, pady=4)

        ttk.Button(det, text="Agregar ítem", command=self._on_add_item).grid(row=0, column=6, padx=8)

        # ---------- Tabla ----------
        self.tree = ttk.Treeview(
            self,
            columns=("prod_id", "producto", "cant", "precio", "subtotal"),
            show="headings",
            height=12,
        )
        for cid, text, w, anchor in [
            ("prod_id", "ID", 60, "center"),
            ("producto", "Producto", 300, "w"),
            ("cant", "Cant.", 80, "e"),
            ("precio", "Precio (c/IVA)", 120, "e"),
            ("subtotal", "Subtotal", 120, "e"),
        ]:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, pady=(10, 0))

        # ---------- Total + Acciones ----------
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", expand=False, pady=10)
        self.lbl_total = ttk.Label(bottom, text="Total: 0.00", font=("", 11, "bold"))
        self.lbl_total.pack(side="left")

        ttk.Button(bottom, text="Eliminar ítem", command=self._on_delete_item).pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar OC (PDF en Descargas)", command=self._on_generate_po_downloads).pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar Cotización (PDF)", command=self._on_generate_quote_downloads).pack(side="right", padx=6)
        ttk.Button(bottom, text="Confirmar compra", command=self._on_confirm_purchase).pack(side="right", padx=6)

        # Inicializa proveedores y dataset de productos (filtrado)
        self.refresh_lookups()

    # ======================== Lookups ========================
    def refresh_lookups(self):
        """Carga proveedores; selecciona uno por defecto y filtra productos."""
        # Proveedores por razón social
        self.suppliers = self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all()
        self.cmb_supplier["values"] = [self._display_supplier(s) for s in self.suppliers]
        if self.suppliers and not self.cmb_supplier.get():
            self.cmb_supplier.current(0)

        # Cargar dataset de productos según proveedor seleccionado
        self._on_supplier_selected()

    def _on_supplier_selected(self, _evt=None):
        """Cuando cambia el proveedor, filtra el dataset de productos y limpia selección."""
        sup = self._selected_supplier()
        if sup:
            # Solo productos del proveedor seleccionado
            self.products = self.repo_prod.get_by_supplier(sup.id)
        else:
            # Fallback: todos (no recomendado, pero evita dejar vacío)
            self.products = self.session.query(Product).order_by(Product.nombre.asc()).all()

        # Configurar dataset del autocompletado
        def _disp(p: Product) -> str:
            sku = getattr(p, "sku", "") or ""
            return f"{p.id} - {p.nombre}" + (f" [{sku}]" if sku else "")

        def _keys(p: Product):
            # Buscar por ID, nombre, SKU (y alias comunes)
            return [
                str(getattr(p, "id", "")),
                str(getattr(p, "nombre", "") or getattr(p, "name", "")),
                str(getattr(p, "sku", "") or getattr(p, "codigo", "") or getattr(p, "code", "")),
            ]

        self.cmb_product.set_dataset(self.products, keyfunc=_disp, searchkeys=_keys)
        self.cmb_product.set("")  # limpiar selección visible
        self._update_price_field()

    def _display_supplier(self, s: Supplier) -> str:
        rut = getattr(s, "rut", "") or ""
        rs = getattr(s, "razon_social", "") or ""
        if rut and rs:
            return f"{rut} — {rs}"
        return rs or rut or f"Proveedor {s.id}"

    # ======================== Precio con IVA ========================
    def _price_with_iva(self, p: Product) -> float:
        base = float(p.precio_compra or 0.0)
        return round(base * (1.0 + IVA_RATE), 2)

    def _selected_product(self) -> Optional[Product]:
        # Primero intentamos tomar el objeto real desde el autocomplete
        it = self.cmb_product.get_selected_item()
        if it is not None:
            return it
        # Fallback por índice visible (si el usuario navegó con flechas)
        try:
            idx = self.cmb_product.current()
        except Exception:
            idx = -1
        if idx is not None and 0 <= idx < len(self.products):
            return self.products[idx]
        return None

    def _selected_supplier(self) -> Optional[Supplier]:
        idx = self.cmb_supplier.current()
        if idx is None or idx < 0:
            return None
        return self.suppliers[idx]

    def _update_price_field(self):
        p = self._selected_product()
        price = self._price_with_iva(p) if p else 0.0
        self.var_price.set(f"{price:.2f}")

    def _on_product_change(self, _evt=None):
        self._update_price_field()

    # ======================== Ítems ========================
    def _on_add_item(self):
        """Agrega un ítem validando que el producto pertenezca al proveedor seleccionado."""
        try:
            sup = self._selected_supplier()
            if not sup:
                messagebox.showwarning("Validación", "Seleccione un proveedor.")
                return

            p = self._selected_product()
            if not p:
                messagebox.showwarning("Validación", "Seleccione un producto.")
                return

            # VALIDACIÓN CLAVE: el producto debe pertenecer al proveedor de la compra
            if getattr(p, "id_proveedor", None) != sup.id:
                messagebox.showerror(
                    "Proveedor incorrecto",
                    "El producto seleccionado no corresponde al proveedor de la compra."
                )
                return

            try:
                qty = int(float(self.ent_qty.get()))
            except ValueError:
                messagebox.showwarning("Validación", "Cantidad inválida.")
                return
            if qty <= 0:
                messagebox.showwarning("Validación", "La cantidad debe ser > 0.")
                return

            price = self._price_with_iva(p)
            if price <= 0:
                messagebox.showwarning("Validación", "El producto no tiene precio de compra válido.")
                return

            subtotal = qty * price
            self.tree.insert("", "end", values=(p.id, p.nombre, qty, f"{price:.2f}", f"{subtotal:.2f}"))
            self._update_total()

            # reset mínimo
            self.ent_qty.delete(0, "end"); self.ent_qty.insert(0, "1")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo agregar el ítem:\n{e}")

    def _on_delete_item(self):
        for iid in self.tree.selection():
            self.tree.delete(iid)
        self._update_total()

    def _update_total(self):
        total = 0.0
        for iid in self.tree.get_children():
            try:
                total += float(self.tree.item(iid, "values")[4])
            except Exception:
                pass
        self.lbl_total.config(text=f"Total: {total:.2f}")

    def _collect_items_for_manager(self) -> List[PurchaseItem]:
        items: List[PurchaseItem] = []
        for iid in self.tree.get_children():
            prod_id, _name, scnt, sprice, _sub = self.tree.item(iid, "values")
            items.append(
                PurchaseItem(
                    product_id=int(prod_id),
                    cantidad=int(float(scnt)),
                    precio_unitario=float(sprice),  # ya viene con IVA
                )
            )
        return items

    def _collect_items_for_pdf(self) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for iid in self.tree.get_children():
            prod_id, name, scnt, sprice, ssub = self.tree.item(iid, "values")
            rows.append({
                "id": int(prod_id),
                "nombre": str(name),
                "cantidad": int(float(scnt)),
                "precio": float(sprice),
                "subtotal": float(ssub),
            })
        return rows

    # ======================== Acciones ========================
    def _on_confirm_purchase(self):
        """Confirma compra usando PurchaseManager (que también valida coherencia)."""
        try:
            sup = self._selected_supplier()
            if not sup:
                messagebox.showwarning("Validación", "Seleccione un proveedor.")
                return
            items = self._collect_items_for_manager()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem.")
                return

            # Validación extra en UI: por si editaron manualmente la tabla
            # (la capa core también valida, pero esto mejora la UX)
            for it in items:
                p: Optional[Product] = self.session.get(Product, it.product_id)
                if not p or getattr(p, "id_proveedor", None) != sup.id:
                    messagebox.showerror(
                        "Proveedor incorrecto",
                        f"El producto id={it.product_id} no corresponde al proveedor seleccionado."
                    )
                    return

            self.pm.create_purchase(
                supplier_id=sup.id,
                items=items,
                estado="Completada" if self.var_apply.get() else "Pendiente",
                apply_to_stock=self.var_apply.get(),  # suma stock si confirmada
            )

            # limpiar
            for iid in list(self.tree.get_children()):
                self.tree.delete(iid)
            self._update_total()
            self.cmb_product.set("")  # limpiar selección de producto tras confirmar
            messagebox.showinfo("OK", "Compra registrada correctamente.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo confirmar la compra:\n{e}")

    def _on_generate_po_downloads(self):
        try:
            sup = self._selected_supplier()
            if not sup:
                messagebox.showwarning("Validación", "Seleccione un proveedor.")
                return
            items = self._collect_items_for_pdf()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem.")
                return

            po_number = f"OC-{sup.id}-{self._stamp()}"
            supplier_dict = {
                "id": str(sup.id),
                "nombre": getattr(sup, "razon_social", None) or "",  # compat con po_generator
                "contacto": getattr(sup, "contacto", ""),
                "telefono": getattr(sup, "telefono", ""),
                "email": getattr(sup, "email", ""),
                "direccion": getattr(sup, "direccion", ""),
            }
            out = generate_po_to_downloads(
                po_number=po_number,
                supplier=supplier_dict,
                items=items,
                currency="CLP",
                notes=None,
                auto_open=True,
            )
            messagebox.showinfo("OC generada", f"Orden de Compra creada en Descargas:\n{out}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar la OC:\n{e}")

    # NUEVO: handler para generar COTIZACIÓN sin afectar stock
    def _on_generate_quote_downloads(self):
        """
        Genera una 'COTIZACIÓN' en PDF con la info de la tabla,
        sin guardar la compra ni modificar stock. Guarda en Descargas.
        """
        try:
            sup = self._selected_supplier()
            if not sup:
                messagebox.showwarning("Validación", "Seleccione un proveedor.")
                return

            items = self._collect_items_for_pdf()
            if not items:
                messagebox.showwarning("Validación", "Agregue al menos un ítem.")
                return

            quote_number = f"COT-{sup.id}-{self._stamp()}"
            supplier_dict = {
                "id": str(sup.id),
                "nombre": getattr(sup, "razon_social", "") or "",
                "contacto": getattr(sup, "contacto", "") or "",
                "telefono": getattr(sup, "telefono", "") or "",
                "email": getattr(sup, "email", "") or "",
                "direccion": getattr(sup, "direccion", "") or "",
            }

            out = generate_quote_downloads(
                quote_number=quote_number,
                supplier=supplier_dict,
                items=items,
                currency="CLP",
                notes=None,
                auto_open=True,   # abrir automáticamente el PDF
            )
            messagebox.showinfo("Cotización generada", f"Cotización creada en Descargas:\n{out}")

        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar la Cotización:\n{e}")

    @staticmethod
    def _stamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d-%H%M%S")

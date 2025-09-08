from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
from pathlib import Path

from src.data.database import get_session
from src.data.models import Product, Supplier
from src.data.repository import ProductRepository, SupplierRepository
from src.gui.widgets.product_image_box import ProductImageBox  # <-- recuadro imagen


class ProductsView(ttk.Frame):
    """
    CRUD de Productos.
    - Recuadro de imagen (esquina superior izquierda) con Cargar/Ver/Quitar
    - Código (SKU)
    - Precio Compra (neto), IVA %, %Ganancia -> calculados (IVA, P+IVA)
    - Precio Venta (editable)
    - **NUEVO**: Proveedor (obligatorio) vía Combobox
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = ProductRepository(self.session)
        self.repo_sup = SupplierRepository(self.session)

        self._editing_id: Optional[int] = None
        self._current_product: Optional[Product] = None
        self._suppliers: List[Supplier] = []  # cache de proveedores para Combobox

        # ---------- Estado (variables UI) ----------
        self.var_nombre = tk.StringVar()
        self.var_codigo = tk.StringVar()        # mostrado como "Código", mapeado a .sku
        self.var_unidad = tk.StringVar(value="unidad")

        self.var_pc = tk.DoubleVar(value=0.0)         # precio compra (neto)
        self.var_iva = tk.DoubleVar(value=19.0)       # IVA %
        self.var_margen = tk.DoubleVar(value=30.0)    # % ganancia
        self.var_iva_monto = tk.DoubleVar(value=0.0)  # monto del IVA (calc)
        self.var_pmasiva = tk.DoubleVar(value=0.0)    # precio + IVA (calc)
        self.var_pventa = tk.DoubleVar(value=0.0)     # precio venta (calc; editable)

        # ---------- Formulario ----------
        frm = ttk.Labelframe(self, text="Producto", padding=10)
        frm.pack(fill="x", expand=False)

        # Panel izquierda: IMAGEN
        left = ttk.Frame(frm)
        # aumentamos rowspan para abarcar nueva fila de Proveedor
        left.grid(row=0, column=0, rowspan=7, sticky="nw", padx=(0, 12))
        self.img_box = ProductImageBox(left, width=180, height=180)
        self.img_box.grid(row=0, column=0, sticky="nw")

        # Panel derecha: CAMPOS
        right = ttk.Frame(frm)
        right.grid(row=0, column=1, sticky="nw")

        # Fila 0: Nombre / Código
        ttk.Label(right, text="Nombre:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(right, textvariable=self.var_nombre, width=35).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(right, text="Código:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(right, textvariable=self.var_codigo, width=20).grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # Fila 1: Precio Compra / IVA %
        ttk.Label(right, text="Precio Compra (neto):").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ent_pc = ttk.Entry(right, textvariable=self.var_pc, width=12)
        ent_pc.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(right, text="IVA %:").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        sp_iva = ttk.Spinbox(right, from_=0, to=100, increment=0.5, textvariable=self.var_iva, width=8)
        sp_iva.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Fila 2: % Ganancia / Unidad
        ttk.Label(right, text="% Ganancia:").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        sp_margen = ttk.Spinbox(right, from_=0, to=1000, increment=0.5, textvariable=self.var_margen, width=8)
        sp_margen.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(right, text="Unidad:").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        self.cmb_unidad = ttk.Combobox(
            right, textvariable=self.var_unidad,
            values=["unidad", "caja", "bolsa", "kg", "lt"],
            width=15, state="readonly"
        )
        self.cmb_unidad.grid(row=2, column=3, sticky="w", padx=4, pady=4)

        # Fila 3: Monto IVA / Precio + IVA
        ttk.Label(right, text="Monto IVA:").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ent_iva_monto = ttk.Entry(right, textvariable=self.var_iva_monto, width=12, state="readonly")
        ent_iva_monto.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(right, text="Precio + IVA:").grid(row=3, column=2, sticky="e", padx=4, pady=4)
        ent_pmasiva = ttk.Entry(right, textvariable=self.var_pmasiva, width=12, state="readonly")
        ent_pmasiva.grid(row=3, column=3, sticky="w", padx=4, pady=4)

        # Fila 4: Precio Venta
        ttk.Label(right, text="Precio Venta:").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ent_pventa = ttk.Entry(right, textvariable=self.var_pventa, width=12)
        ent_pventa.grid(row=4, column=1, sticky="w", padx=4, pady=4)

        # Fila 5: **Proveedor**
        ttk.Label(right, text="Proveedor:").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        self.cmb_supplier = ttk.Combobox(right, state="readonly", width=35)
        self.cmb_supplier.grid(row=5, column=1, columnspan=3, sticky="we", padx=4, pady=4)

        # Botones
        btns = ttk.Frame(right)
        btns.grid(row=6, column=0, columnspan=4, pady=8, sticky="w")

        self.btn_save = ttk.Button(btns, text="Agregar", command=self._on_add)
        self.btn_update = ttk.Button(btns, text="Guardar cambios", command=self._on_update, state="disabled")
        self.btn_delete = ttk.Button(btns, text="Eliminar", command=self._on_delete, state="disabled")
        self.btn_clear = ttk.Button(btns, text="Limpiar", command=self._clear_form)

        self.btn_save.pack(side="left", padx=4)
        self.btn_update.pack(side="left", padx=4)
        self.btn_delete.pack(side="left", padx=4)
        self.btn_clear.pack(side="left", padx=4)

        # ---------- Tabla ----------
        self.tree = ttk.Treeview(
            self,
            columns=("id", "nombre", "codigo", "pcompra", "iva", "iva_monto", "pmasiva", "margen", "pventa", "unidad"),
            show="headings", height=14
        )
        for cid, text, w, anchor in [
            ("id", "ID", 50, "center"),
            ("nombre", "Nombre", 220, "w"),
            ("codigo", "Código", 120, "w"),
            ("pcompra", "P. Compra", 90, "e"),
            ("iva", "IVA %", 70, "e"),
            ("iva_monto", "Monto IVA", 90, "e"),
            ("pmasiva", "P. + IVA", 90, "e"),
            ("margen", "Margen %", 90, "e"),
            ("pventa", "P. Venta", 90, "e"),
            ("unidad", "Unidad", 90, "center"),
        ]:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=w, anchor=anchor)

        self.tree.pack(fill="both", expand=True, pady=(10, 0))
        self.tree.bind("<Double-1>", self._on_row_dblclick)

        # Recalcular automáticamente
        for w in (ent_pc, sp_iva, sp_margen, ent_pventa):
            w.bind("<KeyRelease>", self._on_auto_calc)
        sp_iva.bind("<<Increment>>", self._on_auto_calc)
        sp_iva.bind("<<Decrement>>", self._on_auto_calc)
        sp_margen.bind("<<Increment>>", self._on_auto_calc)
        sp_margen.bind("<<Decrement>>", self._on_auto_calc)

        # Datos iniciales
        self.refresh_lookups()   # carga proveedores en el combo
        self._load_table()
        self._recalc_prices()

    # ---------- Cálculos ----------
    def _recalc_prices(self):
        """Calcula IVA, P+IVA y sugiere pventa (redondeo a entero)."""
        try:
            pc = float(self.var_pc.get() or 0)
            iva = float(self.var_iva.get() or 0)
            mg  = float(self.var_margen.get() or 0)

            monto_iva = pc * (iva / 100.0)
            pmasiva   = pc + monto_iva
            pventa    = pmasiva * (1.0 + mg / 100.0)

            self.var_iva_monto.set(round(monto_iva))
            self.var_pmasiva.set(round(pmasiva))
            self.var_pventa.set(round(pventa))
        except Exception:
            pass

    def _on_auto_calc(self, _evt=None):
        self._recalc_prices()

    # ---------- CRUD ----------
    def _on_add(self):
        try:
            data = self._read_form()
            if not data:
                return
            prod = Product(**data)
            self.session.add(prod)
            self.session.commit()

            # Ahora existe ID -> el recuadro puede aceptar imagen
            self._current_product = prod
            self.img_box.set_product(prod.id, on_image_changed=self._on_image_changed)

            self._clear_form()
            self._load_table()
            messagebox.showinfo("OK", f"Producto '{data['nombre']}' creado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo crear el producto:\n{e}")

    def _on_update(self):
        if self._editing_id is None:
            return
        try:
            data = self._read_form()
            if not data:
                return
            p = self.repo.get(self._editing_id)
            if not p:
                messagebox.showwarning("Aviso", "Registro no encontrado.")
                return
            p.nombre = data["nombre"]
            p.sku = data["sku"]
            p.precio_compra = data["precio_compra"]
            p.precio_venta = data["precio_venta"]
            p.unidad_medida = data["unidad_medida"]
            p.id_proveedor = data["id_proveedor"]  # **NUEVO**: guardar proveedor
            # image_path lo actualiza el callback _on_image_changed
            self.session.commit()
            self._clear_form()
            self._load_table()
            messagebox.showinfo("OK", "Producto actualizado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo actualizar:\n{e}")

    def _on_delete(self):
        if self._editing_id is None:
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este producto?"):
            return
        try:
            self.repo.delete(self._editing_id)
            self.session.commit()
            self._clear_form()
            self._load_table()
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

    def _on_row_dblclick(self, _event=None):
        """Carga la fila seleccionada al formulario."""
        sel = self.tree.selection()
        if not sel:
            return

        vals = self.tree.item(sel[0], "values")
        # 0 id, 1 nombre, 2 codigo, 3 pcompra, 4 iva, 5 iva_monto, 6 pmasiva, 7 margen, 8 pventa, 9 unidad

        self._editing_id = int(vals[0])
        self._current_product = self.repo.get(self._editing_id)

        self.var_nombre.set(vals[1])
        self.var_codigo.set(vals[2])

        # pcompra
        try: self.var_pc.set(float(vals[3]))
        except Exception: self.var_pc.set(0.0)

        # iva % (UI ref)
        try: self.var_iva.set(float(vals[4]))
        except Exception: self.var_iva.set(19.0)

        # monto iva
        try: self.var_iva_monto.set(float(vals[5]))
        except Exception: self.var_iva_monto.set(0.0)

        # p + iva
        try: self.var_pmasiva.set(float(vals[6]))
        except Exception: self.var_pmasiva.set(0.0)

        # margen %
        try: self.var_margen.set(float(vals[7]))
        except Exception: self.var_margen.set(30.0)

        # p venta
        try: self.var_pventa.set(float(vals[8]))
        except Exception: self.var_pventa.set(0.0)

        # unidad
        try: self.var_unidad.set(vals[9] or "unidad")
        except Exception: self.var_unidad.set("unidad")

        # Mostrar imagen del producto seleccionado
        if self._current_product and self._current_product.id:
            self.img_box.set_product(self._current_product.id, on_image_changed=self._on_image_changed)
        else:
            self.img_box.set_product(None)

        # Seleccionar proveedor actual del producto
        self._select_supplier_for_current_product()

        self.btn_save.config(state="disabled")
        self.btn_update.config(state="normal")
        self.btn_delete.config(state="normal")

    # ---------- Imagen: callback ----------
    def _on_image_changed(self, new_path: Optional[Path]):
        """Se dispara al cargar/quitar imagen desde ProductImageBox."""
        if not self._current_product:
            return
        self._current_product.image_path = (str(new_path) if new_path else None)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()

    # ---------- Utilidades ----------
    def _read_form(self) -> Optional[dict]:
        """Valida y transforma el formulario a dict para Product (sin stock_actual)."""
        try:
            nombre = self.var_nombre.get().strip()
            codigo = self.var_codigo.get().strip()
            unidad = self.var_unidad.get()
            pc = float(self.var_pc.get())
            pventa = float(self.var_pventa.get())

            if not nombre or not codigo:
                messagebox.showwarning("Validación", "Nombre y Código son obligatorios.")
                return None
            if pc <= 0:
                messagebox.showwarning("Validación", "Precio de compra debe ser > 0.")
                return None
            if pventa <= 0:
                messagebox.showwarning("Validación", "Precio de venta debe ser > 0.")
                return None

            # Proveedor obligatorio
            idx = self.cmb_supplier.current()
            if idx is None or idx < 0 or idx >= len(self._suppliers):
                messagebox.showwarning("Validación", "Seleccione un proveedor.")
                return None
            proveedor = self._suppliers[idx]

            return dict(
                nombre=nombre,
                sku=codigo,
                precio_compra=pc,
                precio_venta=pventa,     # persistimos venta final (con IVA y margen)
                unidad_medida=unidad,
                id_proveedor=proveedor.id,  # **NUEVO**: vínculo a proveedor
            )
        except ValueError:
            messagebox.showwarning("Validación", "Revisa números (PC/IVA/Margen/Precios).")
            return None

    def _clear_form(self):
        self._editing_id = None
        self._current_product = None
        self.var_nombre.set("")
        self.var_codigo.set("")
        self.var_unidad.set("unidad")
        self.var_pc.set(0.0)
        self.var_iva.set(19.0)
        self.var_margen.set(30.0)
        self.var_iva_monto.set(0.0)
        self.var_pmasiva.set(0.0)
        self.var_pventa.set(0.0)
        self.img_box.set_product(None)  # limpia preview
        self.btn_save.config(state="normal")
        self.btn_update.config(state="disabled")
        self.btn_delete.config(state="disabled")
        # limpiar selección de proveedor (si hay dataset cargado)
        try:
            self.cmb_supplier.set("")
        except Exception:
            pass

    def _load_table(self):
        """
        Carga los productos y calcula columnas derivadas para mostrar:
        - IVA %: usa el valor actual de la UI como referencia (no está en BD).
        - Monto IVA y P. + IVA se calculan desde precio_compra e IVA actual.
        - Margen % se estima desde precio_venta y P. + IVA (aprox).
        """
        for i in self.tree.get_children():
            self.tree.delete(i)

        prods: List[Product] = self.session.query(Product).order_by(Product.id.desc()).all()
        iva_ref = float(self.var_iva.get() or 19.0)

        for p in prods:
            pc = float(p.precio_compra)
            iva_monto = round(pc * (iva_ref / 100.0))
            pmasiva = round(pc + iva_monto)
            try:
                pv = float(p.precio_venta)
                margen = max(0.0, (pv / max(1.0, pmasiva) - 1.0) * 100.0)
            except Exception:
                pv = float(p.precio_venta)
                margen = 0.0

            self.tree.insert(
                "", "end",
                values=(
                    p.id,
                    p.nombre,
                    p.sku,                         # mostrado como "Código"
                    f"{pc:.0f}",                   # pcompra
                    f"{iva_ref:.1f}",              # iva %
                    f"{iva_monto:.0f}",            # monto iva
                    f"{pmasiva:.0f}",              # p + iva
                    f"{margen:.1f}",               # margen estimado
                    f"{pv:.0f}",                   # p venta
                    p.unidad_medida or "",         # unidad
                )
            )

    def refresh_lookups(self):
        """Carga proveedores al combobox."""
        self._suppliers = self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all()
        def _disp(s: Supplier) -> str:
            rut = (s.rut or "").strip()
            rs = (s.razon_social or "").strip()
            return f"{rs} — {rut}" if rut else rs
        self.cmb_supplier["values"] = [_disp(s) for s in self._suppliers]
        # No autoseleccionamos para obligar selección explícita en 'Agregar'

    # ---------- helpers ----------
    def _select_supplier_for_current_product(self):
        """Selecciona en el combo el proveedor del producto cargado (si existe)."""
        try:
            if not self._current_product:
                self.cmb_supplier.set("")
                return
            pid = getattr(self._current_product, "id_proveedor", None)
            if pid is None:
                self.cmb_supplier.set("")
                return
            idx = next((i for i, s in enumerate(self._suppliers) if s.id == pid), -1)
            if idx >= 0:
                self.cmb_supplier.current(idx)
            else:
                # Si el proveedor del producto no está en la lista (fue borrado), limpiamos.
                self.cmb_supplier.set("")
        except Exception:
            self.cmb_supplier.set("")

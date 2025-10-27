# src/gui/products_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
from pathlib import Path

from src.data.database import get_session
from src.data.models import Product, Supplier, Location
from src.data.repository import ProductRepository, SupplierRepository, LocationRepository
from src.gui.widgets.product_image_box import ProductImageBox  # <-- recuadro imagen

# Grilla tipo hoja (tksheet si está, o fallback Treeview)
from src.gui.widgets.grid_table import GridTable


def calcular_precios(pc: float, iva: float, margen: float) -> tuple[float, float, float]:
    """Calcula monto IVA, precio + IVA y precio venta sugerido."""
    monto_iva = pc * (iva / 100.0)
    pmasiva = pc + monto_iva
    pventa = pmasiva * (1.0 + margen / 100.0)
    return round(monto_iva), round(pmasiva), round(pventa)


class ProductsView(ttk.Frame):
    """
    CRUD de Productos con grilla tipo hoja:
    - Recuadro de imagen (Cargar/Ver/Quitar)
    - Código (SKU)
    - Precio Compra (neto), IVA %, %Ganancia -> calcula (IVA, P+IVA)
    - Precio Venta (editable)
    - Proveedor (obligatorio) vía Combobox
    """

    COLS = ["ID", "Nombre", "Código", "P. Compra", "IVA %", "Monto IVA", "P. + IVA", "Margen %", "P. Venta", "Unidad"]
    COL_WIDTHS = [50, 220, 120, 90, 70, 90, 90, 90, 90, 90]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = ProductRepository(self.session)
        self.repo_sup = SupplierRepository(self.session)
        self.repo_loc = LocationRepository(self.session)

        self._editing_id: Optional[int] = None
        self._current_product: Optional[Product] = None
        self._suppliers: List[Supplier] = []
        self._locations: List[Location] = []

        # cache tabla (para doble click en tksheet / tree)
        self._rows_cache: List[List[str]] = []
        self._id_by_index: List[int] = []

        # ---------- Estado (variables UI) ----------
        self.var_nombre = tk.StringVar()
        self.var_codigo = tk.StringVar()
        self.var_unidad = tk.StringVar(value="unidad")
        self.var_pc = tk.DoubleVar(value=0.0)
        self.var_iva = tk.DoubleVar(value=19.0)
        self.var_margen = tk.DoubleVar(value=30.0)
        self.var_iva_monto = tk.DoubleVar(value=0.0)
        self.var_pmasiva = tk.DoubleVar(value=0.0)
        self.var_pventa = tk.DoubleVar(value=0.0)

        # ---------- Formulario ----------
        frm = ttk.Labelframe(self, text="Producto", padding=10)
        frm.pack(fill="x", expand=False)

        # Panel izquierda: IMAGEN
        left = ttk.Frame(frm)
        left.grid(row=0, column=0, rowspan=7, sticky="nw", padx=(0, 12))
        self.img_box = ProductImageBox(left, width=180, height=180)
        self.img_box.grid(row=0, column=0, sticky="nw")

        # Panel derecha: CAMPOS
        right = ttk.Frame(frm)
        right.grid(row=0, column=1, sticky="nw")

        # Fila 0: Nombre / Código
        ttk.Label(right, text="Nombre:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ent_nombre = ttk.Entry(right, textvariable=self.var_nombre, width=35)
        ent_nombre.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.ent_nombre = ent_nombre  # para foco

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

        # Fila 5: Proveedor
        ttk.Label(right, text="Proveedor:").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        self.cmb_supplier = ttk.Combobox(right, state="readonly", width=35)
        self.cmb_supplier.grid(row=5, column=1, columnspan=3, sticky="we", padx=4, pady=4)

        # Fila 6: Ubicación
        ttk.Label(right, text="Ubicación:").grid(row=6, column=0, sticky="e", padx=4, pady=4)
        self.cmb_location = ttk.Combobox(right, state="readonly", width=28)
        self.cmb_location.grid(row=6, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(right, text="Admin. ubicaciones...", command=self._open_locations_manager).grid(row=6, column=2, columnspan=2, sticky="w", padx=4, pady=4)

        # Botones
        btns = ttk.Frame(right)
        btns.grid(row=7, column=0, columnspan=4, pady=8, sticky="w")

        self.btn_save = ttk.Button(btns, text="Agregar", command=self._on_add)
        self.btn_update = ttk.Button(btns, text="Guardar cambios", command=self._on_update, state="disabled")
        self.btn_delete = ttk.Button(btns, text="Eliminar", command=self._on_delete, state="disabled")
        self.btn_clear = ttk.Button(btns, text="Limpiar", command=self._clear_form)

        self.btn_save.pack(side="left", padx=4)
        self.btn_update.pack(side="left", padx=4)
        self.btn_delete.pack(side="left", padx=4)
        self.btn_clear.pack(side="left", padx=4)

        # ---------- Tabla (GridTable) ----------
        self.table = GridTable(self, height=14)
        self.table.pack(fill="both", expand=True, pady=(10, 0))

        # Doble click para editar (tksheet + fallback)
        if hasattr(self.table, "sheet"):
            try:
                self.table.sheet.extra_bindings([("double_click", lambda e: self._on_row_dblclick())])
            except Exception:
                pass
        tv = getattr(self.table, "_fallback", None)
        if tv is not None:
            tv.bind("<Double-1>", lambda e: self._on_row_dblclick())
            # Limpia formulario si clic en encabezado
            tv.bind("<Button-1>", self._on_tree_click)

        # Recalcular automáticamente
        for w in (ent_pc, sp_iva, sp_margen, ent_pventa):
            w.bind("<KeyRelease>", self._on_auto_calc)
        sp_iva.bind("<<Increment>>", self._on_auto_calc)
        sp_iva.bind("<<Decrement>>", self._on_auto_calc)
        sp_margen.bind("<<Increment>>", self._on_auto_calc)
        sp_margen.bind("<<Decrement>>", self._on_auto_calc)

        # Datos iniciales
        self.refresh_lookups()
        self._load_table()
        self._recalc_prices()
        self.ent_nombre.focus_set()

    # ----------------- Utilidades de grilla ----------------- #
    def _apply_column_widths(self) -> None:
        """Ajusta anchos de columnas en tksheet y en fallback Treeview."""
        if hasattr(self.table, "sheet"):
            try:
                for i, w in enumerate(self.COL_WIDTHS):
                    self.table.sheet.column_width(i, width=w)
            except Exception:
                pass
        tv = getattr(self.table, "_fallback", None)
        if tv is not None:
            tv["columns"] = list(self.COLS)
            for i, name in enumerate(self.COLS):
                tv.heading(name, text=name, anchor="center")
                tv.column(name, width=self.COL_WIDTHS[i], anchor="center")
            try:
                from src.gui.treeview_utils import enable_treeview_sort
                enable_treeview_sort(tv)
            except Exception:
                pass

    def _set_table_data(self, rows: List[List[str]]) -> None:
        self.table.set_data(self.COLS, rows)
        self._apply_column_widths()

    def _selected_row_index(self) -> Optional[int]:
        """Índice de fila seleccionada (o None)."""
        if hasattr(self.table, "sheet"):
            try:
                rows = list(self.table.sheet.get_selected_rows())
                if rows:
                    return sorted(rows)[0]
                cells = self.table.sheet.get_selected_cells()
                if cells:
                    return sorted({r for r, _ in cells})[0]
            except Exception:
                return None
            return None
        tv = getattr(self.table, "_fallback", None)
        if tv is None:
            return None
        sel = tv.selection()
        if not sel:
            return None
        try:
            return tv.index(sel[0])
        except Exception:
            return None

    # ---------- Cálculos ----------
    def _recalc_prices(self):
        """Calcula IVA, P+IVA y sugiere pventa (redondeo a entero)."""
        try:
            pc = float(self.var_pc.get() or 0)
            iva = float(self.var_iva.get() or 0)
            mg = float(self.var_margen.get() or 0)
            monto_iva, pmasiva, pventa = calcular_precios(pc, iva, mg)
            self.var_iva_monto.set(monto_iva)
            self.var_pmasiva.set(pmasiva)
            self.var_pventa.set(pventa)
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
            for k, v in data.items():
                setattr(p, k, v)
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
        idx = self._selected_row_index()
        if idx is None or idx < 0 or idx >= len(self._rows_cache):
            return
        vals = self._rows_cache[idx]
        # 0 id, 1 nombre, 2 código, 3 pcompra, 4 iva, 5 iva_monto, 6 pmasiva, 7 margen, 8 pventa, 9 unidad
        self._editing_id = int(vals[0])
        self._current_product = self.repo.get(self._editing_id)
        self.var_nombre.set(vals[1])
        self.var_codigo.set(vals[2])
        try: self.var_pc.set(float(vals[3] or 0))
        except Exception: self.var_pc.set(0.0)
        try: self.var_iva.set(float(vals[4] or 19.0))
        except Exception: self.var_iva.set(19.0)
        try: self.var_iva_monto.set(float(vals[5] or 0))
        except Exception: self.var_iva_monto.set(0.0)
        try: self.var_pmasiva.set(float(vals[6] or 0))
        except Exception: self.var_pmasiva.set(0.0)
        try: self.var_margen.set(float(vals[7] or 30.0))
        except Exception: self.var_margen.set(30.0)
        try: self.var_pventa.set(float(vals[8] or 0))
        except Exception: self.var_pventa.set(0.0)
        try: self.var_unidad.set(vals[9] or "unidad")
        except Exception: self.var_unidad.set("unidad")

        if self._current_product and self._current_product.id:
            self.img_box.set_product(self._current_product.id, on_image_changed=self._on_image_changed)
        else:
            self.img_box.set_product(None)

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
            idx = self.cmb_supplier.current()
            if idx is None or idx < 0 or idx >= len(self._suppliers):
                messagebox.showwarning("Validación", "Seleccione un proveedor.")
                return None
            proveedor = self._suppliers[idx]
            # Ubicación (opcional)
            location_id = None
            try:
                li = self.cmb_location.current()
                if li is not None and li >= 0 and li < len(self._locations):
                    location_id = self._locations[li].id
            except Exception:
                location_id = None
            return dict(
                nombre=nombre,
                sku=codigo,
                precio_compra=pc,
                precio_venta=pventa,
                unidad_medida=unidad,
                id_proveedor=proveedor.id,
                id_ubicacion=location_id,
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
        self.img_box.set_product(None)
        self.btn_save.config(state="normal")
        self.btn_update.config(state="disabled")
        self.btn_delete.config(state="disabled")
        try:
            self.cmb_supplier.set("")
        except Exception:
            pass
        # Limpia selección en la grilla y foco en nombre
        try:
            if hasattr(self.table, "sheet"):
                self.table.sheet.deselect("all")
            else:
                tv = getattr(self.table, "_fallback", None)
                if tv is not None:
                    tv.selection_remove(tv.selection())
        except Exception:
            pass
        self.after(100, lambda: self.ent_nombre.focus_set())

    def _load_table(self):
        """Carga los productos y calcula columnas derivadas para mostrar."""
        prods: List[Product] = self.session.query(Product).order_by(Product.id.desc()).all()
        iva_ref = float(self.var_iva.get() or 19.0)

        self._rows_cache = []
        self._id_by_index = []

        for p in prods:
            pc = float(p.precio_compra or 0)
            iva_monto, pmasiva, _ = calcular_precios(pc, iva_ref, 0)
            try:
                pv = float(p.precio_venta or 0)
                margen = max(0.0, (pv / max(1.0, pmasiva) - 1.0) * 100.0)
            except Exception:
                pv = float(p.precio_venta or 0)
                margen = 0.0
            row = [
                p.id,
                p.nombre or "",
                p.sku or "",
                f"{pc:.0f}",
                f"{iva_ref:.1f}",
                f"{iva_monto:.0f}",
                f"{pmasiva:.0f}",
                f"{margen:.1f}",
                f"{pv:.0f}",
                p.unidad_medida or "",
            ]
            self._rows_cache.append(row)
            self._id_by_index.append(int(p.id))

        self._set_table_data(self._rows_cache)

    def refresh_lookups(self):
        """Carga proveedores y ubicaciones a los combobox."""
        self._suppliers = self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all()
        self._locations = self.session.query(Location).order_by(Location.nombre.asc()).all()

        def _disp(s: Supplier) -> str:
            rut = (s.rut or "").strip()
            rs = (s.razon_social or "").strip()
            return f"{rs} — {rut}" if rut else rs

        self.cmb_supplier["values"] = [_disp(s) for s in self._suppliers]
        # Selecciona automáticamente si solo hay un proveedor
        if len(self._suppliers) == 1:
            self.cmb_supplier.current(0)
        # Ubicaciones
        if hasattr(self, 'cmb_location'):
            try:
                self.cmb_location["values"] = [(l.nombre or "").strip() for l in self._locations]
            except Exception:
                pass

    def _select_supplier_for_current_product(self):
        """Selecciona en los combos proveedor y ubicación del producto cargado (si existe)."""
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
                self.cmb_supplier.set("")
        except Exception:
            self.cmb_supplier.set("")
        # Ubicación
        try:
            if not self._current_product:
                self.cmb_location.set("")
            else:
                lid = getattr(self._current_product, "id_ubicacion", None)
                idx = next((i for i, l in enumerate(self._locations) if l.id == lid), -1)
                if idx >= 0:
                    self.cmb_location.current(idx)
                else:
                    self.cmb_location.set("")
        except Exception:
            try:
                self.cmb_location.set("")
            except Exception:
                pass

    def _open_locations_manager(self):
        try:
            from src.gui.locations_manager import LocationsManager
        except Exception:
            messagebox.showerror("Ubicaciones", "No se pudo cargar el administrador de ubicaciones.")
            return
        dlg = LocationsManager(self.session, parent=self)
        self.wait_window(dlg)
        # Refrescar lista tras cerrar
        self.refresh_lookups()
        self._select_supplier_for_current_product()

    # ---------- Solo fallback: limpiar selección al click de encabezado ----------
    def _on_tree_click(self, event):
        tv = getattr(self.table, "_fallback", None)
        if tv is None:
            return
        region = tv.identify("region", event.x, event.y)
        if region == "heading":
            tv.selection_remove(tv.selection())
            self._clear_form()

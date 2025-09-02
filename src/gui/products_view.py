from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional

from src.data.database import get_session
from src.data.models import Product
from src.data.repository import ProductRepository


class ProductsView(ttk.Frame):
    """
    CRUD de Productos (sin tocar stock aquí).
    - Código (antes "SKU") -> se guarda en Product.sku
    - Precio Compra (neto, sin IVA)
    - IVA % (default 19)
    - % Ganancia (default 30)
    - Monto IVA (calculado, solo lectura)
    - Precio + IVA (calculado, solo lectura)
    - Precio Venta (calculado, editable si quieres ajustar)
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = ProductRepository(self.session)

        self._editing_id: Optional[int] = None

        # ---------- Estado (variables) ----------
        self.var_nombre = tk.StringVar()
        self.var_codigo = tk.StringVar()        # mostrado como "Código", mapeado a .sku
        self.var_unidad = tk.StringVar(value="unidad")

        self.var_pc = tk.DoubleVar(value=0.0)         # precio compra (neto)
        self.var_iva = tk.DoubleVar(value=19.0)       # IVA %
        self.var_margen = tk.DoubleVar(value=30.0)    # % ganancia
        self.var_iva_monto = tk.DoubleVar(value=0.0)  # monto del IVA (calc)
        self.var_pmasiva = tk.DoubleVar(value=0.0)    # precio + IVA (calc)
        self.var_pventa = tk.DoubleVar(value=0.0)     # precio venta (calc base margen; editable)

        # ---------- Formulario ----------
        frm = ttk.Labelframe(self, text="Producto", padding=10)
        frm.pack(fill="x", expand=False)

        # Fila 0: Nombre / Código
        ttk.Label(frm, text="Nombre:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(frm, textvariable=self.var_nombre, width=35).grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Código:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(frm, textvariable=self.var_codigo, width=20).grid(row=0, column=3, sticky="w", padx=4, pady=4)

        # Fila 1: Precio Compra / IVA %
        ttk.Label(frm, text="Precio Compra (neto):").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ent_pc = ttk.Entry(frm, textvariable=self.var_pc, width=12)
        ent_pc.grid(row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="IVA %:").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        sp_iva = ttk.Spinbox(frm, from_=0, to=100, increment=0.5, textvariable=self.var_iva, width=8)
        sp_iva.grid(row=1, column=3, sticky="w", padx=4, pady=4)

        # Fila 2: % Ganancia / Unidad
        ttk.Label(frm, text="% Ganancia:").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        sp_margen = ttk.Spinbox(frm, from_=0, to=1000, increment=0.5, textvariable=self.var_margen, width=8)
        sp_margen.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Unidad:").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        self.cmb_unidad = ttk.Combobox(
            frm, textvariable=self.var_unidad,
            values=["unidad", "caja", "bolsa", "kg", "lt"],
            width=15, state="readonly"
        )
        self.cmb_unidad.grid(row=2, column=3, sticky="w", padx=4, pady=4)

        # Fila 3: Monto IVA / Precio + IVA
        ttk.Label(frm, text="Monto IVA:").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ent_iva_monto = ttk.Entry(frm, textvariable=self.var_iva_monto, width=12, state="readonly")
        ent_iva_monto.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(frm, text="Precio + IVA:").grid(row=3, column=2, sticky="e", padx=4, pady=4)
        ent_pmasiva = ttk.Entry(frm, textvariable=self.var_pmasiva, width=12, state="readonly")
        ent_pmasiva.grid(row=3, column=3, sticky="w", padx=4, pady=4)

        # Fila 4: Precio Venta
        ttk.Label(frm, text="Precio Venta:").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ent_pventa = ttk.Entry(frm, textvariable=self.var_pventa, width=12)
        ent_pventa.grid(row=4, column=1, sticky="w", padx=4, pady=4)

        # Botones
        btns = ttk.Frame(frm)
        btns.grid(row=5, column=0, columnspan=4, pady=8)

        self.btn_save = ttk.Button(btns, text="Agregar", command=self._on_add)
        self.btn_update = ttk.Button(btns, text="Guardar cambios", command=self._on_update, state="disabled")
        self.btn_delete = ttk.Button(btns, text="Eliminar", command=self._on_delete, state="disabled")
        self.btn_clear = ttk.Button(btns, text="Limpiar", command=self._clear_form)

        self.btn_save.pack(side="left", padx=4)
        self.btn_update.pack(side="left", padx=4)
        self.btn_delete.pack(side="left", padx=4)
        self.btn_clear.pack(side="left", padx=4)

        for i in range(4):
            frm.columnconfigure(i, weight=1)

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

        # Triggers de recálculo
        for w in (ent_pc, sp_iva, sp_margen, ent_pventa):
            w.bind("<KeyRelease>", self._on_auto_calc)
        sp_iva.bind("<<Increment>>", self._on_auto_calc)
        sp_iva.bind("<<Decrement>>", self._on_auto_calc)
        sp_margen.bind("<<Increment>>", self._on_auto_calc)
        sp_margen.bind("<<Decrement>>", self._on_auto_calc)

        self._load_table()
        self._recalc_prices()

    # ---------- Cálculos ----------
    def _recalc_prices(self):
        """
        Calcula:
          monto_iva = pc * (iva/100)
          pmasiva   = pc + monto_iva
          pventa    = pmasiva * (1 + margen/100)
        Redondeo a pesos (0 decimales).
        """
        try:
            pc = float(self.var_pc.get() or 0)
            iva = float(self.var_iva.get() or 0)
            mg  = float(self.var_margen.get() or 0)

            monto_iva = pc * (iva / 100.0)
            pmasiva   = pc + monto_iva
            pventa    = pmasiva * (1.0 + mg / 100.0)

            # Redondeo a pesos CLP
            monto_iva = round(monto_iva)
            pmasiva   = round(pmasiva)
            pventa    = round(pventa)

            self.var_iva_monto.set(monto_iva)
            self.var_pmasiva.set(pmasiva)
            # Sugerimos el pventa calculado (usuario puede editarlo)
            self.var_pventa.set(pventa)
        except Exception:
            # No detener la UI por errores de tipeo transitorios
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
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
        self._editing_id = int(vals[0])
        self.var_nombre.set(vals[1])
        self.var_codigo.set(vals[2])

        # Recupera valores numéricos desde la fila seleccionada
        try: self.var_pc.set(float(vals[3]));   except Exception: self.var_pc.set(0.0)
        try: self.var_iva.set(float(vals[4]));  except Exception: self.var_iva.set(19.0)
        try: self.var_iva_monto.set(float(vals[5])); except Exception: self.var_iva_monto.set(0.0)
        try: self.var_pmasiva.set(float(vals[6]));   except Exception: self.var_pmasiva.set(0.0)
        try: self.var_margen.set(float(vals[7]));    except Exception: self.var_margen.set(30.0)
        try: self.var_pventa.set(float(vals[8]));    except Exception: self.var_pventa.set(0.0)

        self.var_unidad.set(vals[9] or "unidad")

        self.btn_save.config(state="disabled")
        self.btn_update.config(state="normal")
        self.btn_delete.config(state="normal")

    # ---------- Utilidades ----------
    def _read_form(self) -> Optional[dict]:
        """
        Valida y transforma el formulario a dict para el modelo Product.
        Nota: stock_actual no se edita aquí.
        """
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

            # Guardamos "código" en el campo sku
            return dict(
                nombre=nombre,
                sku=codigo,
                precio_compra=pc,
                precio_venta=pventa,     # persistimos venta final (con IVA y margen)
                unidad_medida=unidad,
            )
        except ValueError:
            messagebox.showwarning("Validación", "Revisa números (PC/IVA/Margen/Precios).")
            return None

    def _clear_form(self):
        self._editing_id = None
        self.var_nombre.set("")
        self.var_codigo.set("")
        self.var_unidad.set("unidad")
        self.var_pc.set(0.0)
        self.var_iva.set(19.0)
        self.var_margen.set(30.0)
        self.var_iva_monto.set(0.0)
        self.var_pmasiva.set(0.0)
        self.var_pventa.set(0.0)
        self.btn_save.config(state="normal")
        self.btn_update.config(state="disabled")
        self.btn_delete.config(state="disabled")

    def _load_table(self):
        """
        Carga los productos y calcula columnas derivadas para mostrar:
        - IVA %: se usa el valor actual de la UI como referencia (no está en BD).
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

            # margen aproximado: pv = pmasiva * (1 + m/100)
            # => m = (pv/pmasiva - 1) * 100
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
        pass

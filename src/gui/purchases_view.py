from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Dict
from pathlib import Path
from decimal import Decimal

from src.data.database import get_session
from src.data.models import Product, Supplier
from src.data.repository import ProductRepository, SupplierRepository
from src.core import PurchaseManager, PurchaseItem
from src.utils.po_generator import generate_po_to_downloads
from src.utils.quote_generator import generate_quote_to_downloads as generate_quote_downloads
from src.utils.helpers import get_po_payment_method
from src.gui.widgets.autocomplete_combobox import AutoCompleteCombobox
from src.utils.money import D, q2, fmt_2, mul
from src.gui.treeview_utils import apply_default_treeview_styles, enable_auto_center_for_new_treeviews

IVA_RATE = Decimal("0.19")  # 19% IVA por defecto


class PurchasesView(ttk.Frame):
    """
    Módulo de Compras:
    - Seleccionas Proveedor y Productos (filtrados por proveedor)
    - El Precio Unitario se calcula automático: precio_compra * (1 + IVA)
    - Confirmas compra (puede sumar stock)
    - Generas Orden de Compra (PDF) a Descargas
    - Generas Cotización (PDF) a Descargas sin afectar stock
    - Autocompletado de productos por ID/nombre/SKU
    - Validación: NO se permiten productos de proveedor distinto al seleccionado.
    """

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        try:
            apply_default_treeview_styles()
            enable_auto_center_for_new_treeviews()
        except Exception:
            pass

        self.session = get_session()
        self.pm = PurchaseManager(self.session)
        self.repo_prod = ProductRepository(self.session)
        self.repo_supp = SupplierRepository(self.session)

        self.products: List[Product] = []
        self.suppliers: List[Supplier] = []

        # ---------- Encabezado ----------
        head = ttk.Labelframe(self, text="Encabezado de compra", padding=10)
        head.pack(fill="x", expand=False)

        ttk.Label(head, text="Proveedor:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_supplier = ttk.Combobox(head, state="readonly", width=50)
        self.cmb_supplier.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.cmb_supplier.bind("<<ComboboxSelected>>", self._on_supplier_selected)

        self.var_apply = tk.BooleanVar(value=True)
        ttk.Checkbutton(head, text="Sumar stock (Completada)", variable=self.var_apply).grid(row=0, column=2, padx=10)

        # Estado + forma de pago (acordeón = combobox)
        ttk.Label(head, text="Estado:").grid(row=0, column=3, sticky="e", padx=4)
        self.ESTADOS = ("Completada", "Por pagar", "Pendiente", "Cancelada", "Eliminada")
        self.cmb_estado = ttk.Combobox(head, state="readonly", width=14, values=self.ESTADOS)
        self.cmb_estado.set("Pendiente")
        self.cmb_estado.grid(row=0, column=4, sticky="w", padx=4)
        self.cmb_estado.bind("<<ComboboxSelected>>", lambda _e=None: self._on_estado_change())

        ttk.Label(head, text="Pago:").grid(row=0, column=5, sticky="e", padx=4)
        self.PAGOS = ("Crédito 30 días", "Efectivo", "Débito", "Transferencia", "Cheque")
        self.cmb_pago = ttk.Combobox(head, state="readonly", width=18, values=self.PAGOS)
        self.cmb_pago.set(get_po_payment_method())
        self.cmb_pago.grid(row=0, column=6, sticky="w", padx=4)

        # ---- Campos adicionales de cabecera ----
        ttk.Label(head, text="Número doc:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        self.var_numdoc = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_numdoc, width=18).grid(row=1, column=1, sticky="w")

        ttk.Label(head, text="F. documento:").grid(row=1, column=2, sticky="e")
        self.var_fdoc = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_fdoc, width=12).grid(row=1, column=3, sticky="w")

        ttk.Label(head, text="F. contable:").grid(row=1, column=4, sticky="e")
        self.var_fcont = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_fcont, width=12).grid(row=1, column=5, sticky="w")

        ttk.Label(head, text="F. venc.: ").grid(row=1, column=6, sticky="e")
        self.var_fvenc = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_fvenc, width=12).grid(row=1, column=7, sticky="w")

        ttk.Label(head, text="Moneda:").grid(row=2, column=0, sticky="e")
        self.var_moneda = tk.StringVar(value="PESO CHILENO")
        ttk.Combobox(head, textvariable=self.var_moneda, values=["PESO CHILENO", "USD", "EUR"], width=18, state="readonly").grid(row=2, column=1, sticky="w")

        ttk.Label(head, text="Tasa cambio:").grid(row=2, column=2, sticky="e")
        self.var_tc = tk.StringVar(value="1")
        ttk.Entry(head, textvariable=self.var_tc, width=10).grid(row=2, column=3, sticky="w")

        ttk.Label(head, text="U. negocio:").grid(row=2, column=4, sticky="e")
        self.var_uneg = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_uneg, width=16).grid(row=2, column=5, sticky="w")

        ttk.Label(head, text="Proporcionalidad:").grid(row=2, column=6, sticky="e")
        self.var_prop = tk.StringVar(value="Ventas Afectos")
        ttk.Combobox(head, textvariable=self.var_prop, values=["Ventas Afectos", "Ventas Exentas", "Mixto"], width=16, state="readonly").grid(row=2, column=7, sticky="w")

        ttk.Label(head, text="Tipo dcto:").grid(row=3, column=0, sticky="e")
        self.var_tpdcto = tk.StringVar(value="Monto")
        ttk.Combobox(head, textvariable=self.var_tpdcto, values=["Monto", "Porcentaje"], width=10, state="readonly").grid(row=3, column=1, sticky="w")

        ttk.Label(head, text="Descuento:").grid(row=3, column=2, sticky="e")
        self.var_dcto = tk.StringVar(value="0")
        ttk.Entry(head, textvariable=self.var_dcto, width=10).grid(row=3, column=3, sticky="w")

        ttk.Label(head, text="Ajuste IVA:").grid(row=3, column=4, sticky="e")
        self.var_ajiva = tk.StringVar(value="0")
        ttk.Entry(head, textvariable=self.var_ajiva, width=10).grid(row=3, column=5, sticky="w")

        ttk.Label(head, text="Stock:").grid(row=3, column=6, sticky="e")
        self.var_stockpol = tk.StringVar(value="No Mueve")
        ttk.Combobox(head, textvariable=self.var_stockpol, values=["No Mueve", "Mueve"], width=10, state="readonly").grid(row=3, column=7, sticky="w")

        ttk.Label(head, text="Referencia:").grid(row=4, column=0, sticky="e")
        self.var_ref = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_ref, width=40).grid(row=4, column=1, columnspan=3, sticky="we")

        ttk.Label(head, text="Ajuste imp:").grid(row=4, column=4, sticky="e")
        self.var_ajimp = tk.StringVar(value="0")
        ttk.Entry(head, textvariable=self.var_ajimp, width=10).grid(row=4, column=5, sticky="w")

        # ---------- Detalle ----------
        det = ttk.Labelframe(self, text="Detalle de compra", padding=10)
        det.pack(fill="x", expand=False, pady=(8, 0))

        ttk.Label(det, text="Producto:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_product = AutoCompleteCombobox(det, width=45, state="normal")
        self.cmb_product.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.cmb_product.bind("<<ComboboxSelected>>", self._on_product_change)

        ttk.Label(det, text="Cantidad:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.ent_qty = ttk.Entry(det, width=10)
        self.ent_qty.insert(0, "1")
        self.ent_qty.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Precio Unit. (neto):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.var_price = tk.StringVar(value="0.00")
        self.ent_price = ttk.Entry(det, textvariable=self.var_price, width=14, state="readonly")
        self.ent_price.grid(row=0, column=5, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Desc. %:").grid(row=0, column=6, sticky="e", padx=4, pady=4)
        self.var_disc = tk.StringVar(value="0")
        self.ent_disc = ttk.Entry(det, textvariable=self.var_disc, width=6)
        self.ent_disc.grid(row=0, column=7, sticky="w", padx=4, pady=4)

        ttk.Button(det, text="Agregar ítem", command=self._on_add_item).grid(row=0, column=8, padx=8)

        # ---------- Tabla ----------
        self.tree = ttk.Treeview(
            self,
            columns=("prod_id", "producto", "cant", "precio", "desc_pct", "subtotal"),
            show="headings",
            height=12,
        )
        for cid, text, w in [
            ("prod_id", "ID", 60),
            ("producto", "Producto", 300),
            ("cant", "Cant.", 80),
            ("precio", "Precio (neto)", 120),
            ("desc_pct", "Desc. %", 80),
            ("subtotal", "Subtotal", 120),
        ]:
            self.tree.heading(cid, text=text, anchor="center")
            self.tree.column(cid, width=w, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(10, 0))
        # Ordenar por click en encabezados
        try:
            from src.gui.treeview_utils import enable_treeview_sort
            enable_treeview_sort(self.tree)
        except Exception:
            pass

        # ---------- Total + Acciones ----------
        bottom = ttk.Frame(self)
        bottom.pack(fill="x", expand=False, pady=10)
        self.lbl_total = ttk.Label(bottom, text="Total: 0.00", font=("", 11, "bold"))
        self.lbl_total.pack(side="left")

        ttk.Button(bottom, text="Eliminar ítem", command=self._on_delete_item).pack(side="right", padx=6)
        ttk.Button(bottom, text="Limpiar tabla", command=self._on_clear_table).pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar OC (PDF en Descargas)", command=self._on_generate_po_downloads).pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar Cotización (PDF)", command=self._on_generate_quote_downloads).pack(side="right", padx=6)
        ttk.Button(bottom, text="Guardar compra", command=self._on_confirm_purchase).pack(side="right", padx=6)

        # Inicializa proveedores y dataset de productos (filtrado)
        self.refresh_lookups()
    # ======================== Lookups ========================
    def refresh_lookups(self):
        """Carga proveedores y productos según proveedor seleccionado."""

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
        self.cmb_product.set("")  # limpiar selecciÃ³n visible
        self._update_price_field()

    def _display_supplier(self, s: Supplier) -> str:
        rut = getattr(s, "rut", "") or ""
        rs = getattr(s, "razon_social", "") or ""
        if rut and rs:
            return f"{rut} – {rs}"
        return rs or rut or f"Proveedor {s.id}"

    # ======================== Precio con IVA ========================
    def _price_with_iva(self, p: Product) -> Decimal:
        base = D(getattr(p, "precio_compra", 0) or 0)
        return q2(base)

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
        price = self._price_with_iva(p) if p else Decimal(0)
        self.var_price.set(fmt_2(price))

    def _on_product_change(self, _evt=None):
        self._update_price_field()

    # ======================== Ítems ========================
    def _on_add_item(self):
        """Agrega un ítem validando que el producto pertenezca al proveedor seleccionado y no esté duplicado."""
        try:
            sup = self._selected_supplier()
            if not sup:
                self._warn("Seleccione un proveedor.")
                return

            p = self._selected_product()
            if not p:
                self._warn("Seleccione un producto.")
                return

            # VALIDACIÓN CLAVE: el producto debe pertenecer al proveedor de la compra
            if getattr(p, "id_proveedor", None) != sup.id:
                self._error("El producto seleccionado no corresponde al proveedor de la compra.")
                return

            try:
                qty = int(float(self.ent_qty.get()))
            except ValueError:
                self._warn("Cantidad inválida.")
                return
            if qty <= 0:
                self._warn("La cantidad debe ser > 0.")
                return

            price = self._price_with_iva(p)
            if price <= 0:
                self._warn("El producto no tiene precio de compra válido.")
                return

            # Descuento % (0..100)
            try:
                disc_pct = float(str(self.var_disc.get() or "0").replace(",", "."))
            except Exception:
                disc_pct = 0.0
            if disc_pct < 0:
                disc_pct = 0.0
            if disc_pct > 100:
                disc_pct = 100.0
            disc_rate = D(disc_pct) / D(100)

            # Evita duplicados (opcional)
            for iid in self.tree.get_children():
                if str(p.id) == str(self.tree.item(iid, "values")[0]):
                    self._warn("Este producto ya está en la tabla.")
                    return

            # Subtotal con descuento aplicado (descuento sobre el neto antes de IVA)
            # Aquí trabajamos a nivel "precio con IVA", por simplicidad: aplicamos el % directo
            price_bruto = q2(D(price) * (D(1) + IVA_RATE))
            subtotal = q2(D(qty) * price_bruto * (D(1) - disc_rate))
            self.tree.insert("", "end", values=(p.id, p.nombre, qty, fmt_2(price), f"{disc_pct:.1f}", fmt_2(subtotal)))
            self._update_total()

            # reset mínimo
            self.ent_qty.delete(0, "end"); self.ent_qty.insert(0, "1")
            self.cmb_product.set("")
            self.cmb_product.focus_set()
        except Exception as e:
            self._error(f"No se pudo agregar el ítem:\n{e}")

    def _on_delete_item(self):
        for iid in self.tree.selection():
            self.tree.delete(iid)
        self._update_total()

    def _on_clear_table(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._update_total()

    def _update_total(self):
        total = D(0)
        for iid in self.tree.get_children():
            try:
                total += D(self.tree.item(iid, "values")[5])
            except Exception:
                pass
        self.lbl_total.config(text=f"Total: {fmt_2(total)}")

    def _collect_items_for_manager(self) -> List[PurchaseItem]:
        items: List[PurchaseItem] = []
        for iid in self.tree.get_children():
            prod_id, _name, scnt, sprice, sdisc, _sub = self.tree.item(iid, "values")
            # Aplicamos descuento al precio unitario para reflejar el total mostrado
            try:
                disc_pct = D(str(sdisc).replace("%", ""))
            except Exception:
                disc_pct = D(0)
            disc_rate = disc_pct / D(100)
            price_eff = q2(D(sprice) * (D(1) + IVA_RATE) * (D(1) - disc_rate))
            items.append(
                PurchaseItem(
                    product_id=int(prod_id),
                    cantidad=int(float(scnt)),
                    precio_unitario=price_eff,  # con IVA y descuento aplicado
                )
            )
        return items

    def _collect_items_for_pdf(self) -> List[Dict[str, object]]:
        rows: List[Dict[str, object]] = []
        for iid in self.tree.get_children():
            prod_id, name, scnt, sprice, sdisc, ssub = self.tree.item(iid, "values")
            try:
                disc_pct = D(str(sdisc).replace("%", ""))
            except Exception:
                disc_pct = D(0)
            try:
                p: Optional[Product] = self.session.get(Product, int(prod_id))
                unidad = getattr(p, "unidad_medida", None) or "U"
            except Exception:
                unidad = "U"
            rows.append({
                "id": int(prod_id),
                "nombre": str(name),
                "cantidad": int(float(scnt)),
                "precio": q2(D(sprice) * (D(1) + IVA_RATE)),          # con IVA (precio bruto)
                "subtotal": D(ssub),          # con IVA y descuento ya aplicado
                "dcto_pct": disc_pct,         # usado por OC
                "descuento_porcentaje": disc_pct,  # compat para cotizaciÃ³n
                "dcto": disc_pct,             # compat alternativa
                "unidad": unidad,
            })
        return rows

    # ======================== Acciones ========================
    def _on_confirm_purchase(self):
        """Confirma compra usando PurchaseManager (que también valida coherencia)."""
        try:
            sup = self._selected_supplier()
            if not sup:
                self._warn("Seleccione un proveedor.")
                return
            items = self._collect_items_for_manager()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return

            # Validación extra en UI: por si editaron manualmente la tabla
            # (la capa core también valida, pero esto mejora la UX)
            for it in items:
                p: Optional[Product] = self.session.get(Product, it.product_id)
                if not p or getattr(p, "id_proveedor", None) != sup.id:
                    self._error(f"El producto id={it.product_id} no corresponde al proveedor seleccionado.")
                    return

            estado = (getattr(self, 'cmb_estado', None).get() if hasattr(self, 'cmb_estado') else "Completada") or "Completada"
            sp = (self.var_stockpol.get() if hasattr(self, 'var_stockpol') else "No Mueve") or "No Mueve"
            apply_to_stock = (sp.lower() != "no mueve") and (estado in ("Completada", "Por pagar"))

            pur = self.pm.create_purchase(
                supplier_id=sup.id,
                items=items,
                estado=estado,
                apply_to_stock=apply_to_stock,
            )

            # Guardar cabecera extendida
            try:
                from datetime import datetime
                f = lambda s: datetime.strptime(s.strip(), "%d/%m/%Y") if s and s.strip() else None
                pur.numero_documento = (getattr(self, 'var_numdoc', tk.StringVar()).get() or "").strip() or None
                pur.fecha_documento = f(getattr(self, 'var_fdoc', tk.StringVar()).get())
                pur.fecha_contable = f(getattr(self, 'var_fcont', tk.StringVar()).get())
                pur.fecha_vencimiento = f(getattr(self, 'var_fvenc', tk.StringVar()).get())
                pur.moneda = (getattr(self, 'var_moneda', tk.StringVar()).get() or None)
                try:
                    pur.tasa_cambio = D(getattr(self, 'var_tc', tk.StringVar(value='1')).get() or '1')
                except Exception:
                    pur.tasa_cambio = D(1)
                pur.unidad_negocio = (getattr(self, 'var_uneg', tk.StringVar()).get() or None)
                pur.proporcionalidad = (getattr(self, 'var_prop', tk.StringVar()).get() or None)
                pur.tipo_descuento = (getattr(self, 'var_tpdcto', tk.StringVar()).get() or None)
                try:
                    pur.descuento = D(getattr(self, 'var_dcto', tk.StringVar(value='0')).get() or '0')
                except Exception:
                    pur.descuento = D(0)
                try:
                    pur.ajuste_iva = D(getattr(self, 'var_ajiva', tk.StringVar(value='0')).get() or '0')
                except Exception:
                    pur.ajuste_iva = D(0)
                pur.stock_policy = sp
                pur.referencia = (getattr(self, 'var_ref', tk.StringVar()).get() or None)
                try:
                    pur.ajuste_impuesto = D(getattr(self, 'var_ajimp', tk.StringVar(value='0')).get() or '0')
                except Exception:
                    pur.ajuste_impuesto = D(0)
                self.session.commit()
            except Exception:
                self.session.rollback(); self.session.commit()

            # limpiar
            self._on_clear_table()
            self.cmb_product.set("")
            self.cmb_product.focus_set()
            self._info("Compra registrada correctamente.")
        except Exception as e:
            self._error(f"No se pudo confirmar la compra:\n{e}")

    def _on_generate_po_downloads(self):
        try:
            sup = self._selected_supplier()
            if not sup:
                self._warn("Seleccione un proveedor.")
                return
            items = self._collect_items_for_pdf()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return

            po_number = f"OC-{sup.id}-{self._stamp()}"
            # Construir notas con metadatos de cabecera
            try:
                notes_lines = []
                nd = (getattr(self, 'var_numdoc', tk.StringVar()).get() or '').strip()
                if nd: notes_lines.append(f"N° Doc: {nd}")
                fd = (getattr(self, 'var_fdoc', tk.StringVar()).get() or '').strip()
                if fd: notes_lines.append(f"F. Documento: {fd}")
                fc = (getattr(self, 'var_fcont', tk.StringVar()).get() or '').strip()
                if fc: notes_lines.append(f"F. Contable: {fc}")
                fv = (getattr(self, 'var_fvenc', tk.StringVar()).get() or '').strip()
                if fv: notes_lines.append(f"F. Venc.: {fv}")
                mon = (getattr(self, 'var_moneda', tk.StringVar(value='PESO CHILENO')).get() or '').strip()
                if mon: notes_lines.append(f"Moneda: {mon}")
                tc = (getattr(self, 'var_tc', tk.StringVar(value='1')).get() or '').strip()
                if tc: notes_lines.append(f"Tasa cambio: {tc}")
                un = (getattr(self, 'var_uneg', tk.StringVar()).get() or '').strip()
                if un: notes_lines.append(f"U. negocio: {un}")
                pr = (getattr(self, 'var_prop', tk.StringVar()).get() or '').strip()
                if pr: notes_lines.append(f"Proporcionalidad: {pr}")
                rf = (getattr(self, 'var_ref', tk.StringVar()).get() or '').strip()
                if rf: notes_lines.append(f"Referencia: {rf}")
                ajiva = (getattr(self, 'var_ajiva', tk.StringVar(value='0')).get() or '').strip()
                if ajiva: notes_lines.append(f"Ajuste IVA: {ajiva}")
                ajimp = (getattr(self, 'var_ajimp', tk.StringVar(value='0')).get() or '').strip()
                if ajimp: notes_lines.append(f"Ajuste impuesto: {ajimp}")
                notes = " | ".join(notes_lines) if notes_lines else None
            except Exception:
                notes = None
            supplier_dict = {
                "id": str(sup.id),
                "nombre": getattr(sup, "razon_social", None) or "",
                "contacto": getattr(sup, "contacto", ""),
                "telefono": getattr(sup, "telefono", ""),
                "email": getattr(sup, "email", ""),
                "direccion": getattr(sup, "direccion", ""),
                "pago": (getattr(self, 'cmb_pago', None).get() if hasattr(self, 'cmb_pago') else get_po_payment_method()),
            }
            out = generate_po_to_downloads(\n                po_number=po_number,\n                supplier=supplier_dict,\n                items=items,\n                currency=\"CLP\",\n                notes=notes,\n                auto_open=True,
            )
            self._info(f"Orden de Compra creada en Descargas:\n{out}")
        except Exception as e:
            self._error(f"No se pudo generar la OC:\n{e}")

    def _on_generate_quote_downloads(self):
        """
        Genera una 'COTIZACIÓN' en PDF con la info de la tabla,
        sin guardar la compra ni modificar stock. Guarda en Descargas.
        """
        try:
            sup = self._selected_supplier()
            if not sup:
                self._warn("Seleccione un proveedor.")
                return

            items = self._collect_items_for_pdf()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return

            quote_number = f"COT-{sup.id}-{self._stamp()}"
            supplier_dict = {
                "id": str(sup.id),
                "nombre": getattr(sup, "razon_social", "") or "",
                "contacto": getattr(sup, "contacto", "") or "",
                "telefono": getattr(sup, "telefono", "") or "",
                "email": getattr(sup, "email", "") or "",
                "direccion": getattr(sup, "direccion", "") or "",
                "pago": (getattr(self, 'cmb_pago', None).get() if hasattr(self, 'cmb_pago') else get_po_payment_method()),
            }

            out = generate_quote_downloads(\n                quote_number=quote_number,\n                supplier=supplier_dict,\n                items=items,\n                currency=\"CLP\",\n                notes=notes,\n                auto_open=True,   # abrir automáticamente el PDF
            )
            self._info(f"Cotización creada en Descargas:\n{out}")

        except Exception as e:
            self._error(f"No se pudo generar la Cotización:\n{e}")

    @staticmethod
    def _stamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    # ======================== Mensajes ========================
    def _warn(self, msg: str):
        messagebox.showwarning("Validación", msg)

    def _error(self, msg: str):
        messagebox.showerror("Error", msg)

    def _info(self, msg: str):
        messagebox.showinfo("OK", msg)

    # ======================== Informe Compras ========================
    def _selected_filter_supplier(self) -> Optional[Supplier]:
        it = getattr(self, 'flt_supplier', None)
        if it is None:
            return None
        sel = it.get_selected_item()
        if sel is not None:
            return sel
        try:
            idx = it.current()
            if idx is not None and idx >= 0 and idx < len(self.suppliers):
                return self.suppliers[idx]
        except Exception:
            pass
        return None

    def _selected_filter_product(self) -> Optional[Product]:
        it = getattr(self, 'flt_product', None)
        if it is None:
            return None
        sel = it.get_selected_item()
        if sel is not None:
            return sel
        try:
            idx = it.current()
            if idx is not None and idx >= 0 and idx < len(self.products):
                return self.products[idx]
        except Exception:
            pass
        return None

    @staticmethod
    def _parse_ddmmyyyy(s: str):
        from datetime import datetime
        d, m, y = s.strip().split("/")
        return datetime(int(y), int(m), int(d))

    def _query_purchases_between(self, d_from, d_to, *, supplier_id: Optional[int], product_id: Optional[int], estado: Optional[str], total_min: Optional[float], total_max: Optional[float]):
        from sqlalchemy import and_
        from datetime import datetime
        from src.data.models import Purchase, PurchaseDetail

        start_dt = datetime.combine(d_from, datetime.min.time())
        end_dt = datetime.combine(d_to, datetime.max.time())

        q = self.session.query(Purchase).filter(
            and_(getattr(Purchase, "fecha_compra") >= start_dt,
                 getattr(Purchase, "fecha_compra") <= end_dt)
        )

        if estado:
            q = q.filter(getattr(Purchase, "estado") == estado)








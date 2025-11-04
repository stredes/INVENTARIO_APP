from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Dict
from pathlib import Path
from decimal import Decimal

from src.data.database import get_session
from src.data.models import Product, Supplier, Purchase, PurchaseDetail, Location
from src.gui.widgets.autocomplete_combobox import AutoCompleteCombobox
from src.data.repository import ProductRepository, SupplierRepository
from src.core import PurchaseManager, PurchaseItem
from src.core.inventory_manager import InventoryManager
from src.utils.po_generator import generate_po_to_downloads
from src.utils.quote_generator import generate_quote_to_downloads as generate_quote_downloads
from src.utils.helpers import get_po_payment_method, get_ui_purchases_mode, set_ui_purchases_mode
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
        self.inv = InventoryManager(self.session)
        self.repo_prod = ProductRepository(self.session)
        self.repo_supp = SupplierRepository(self.session)
        # Catálogo de ubicaciones (para trazabilidad)
        try:
            self._all_locations: List[Location] = self.session.query(Location).order_by(Location.nombre.asc()).all()
        except Exception:
            self._all_locations = []

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
        self.ESTADOS = ("Pendiente", "Incompleta", "Por pagar", "Completada", "Cancelada", "Eliminada")
        self.cmb_estado = ttk.Combobox(head, state="readonly", width=14, values=self.ESTADOS)
        self.cmb_estado.set("Pendiente")
        self.cmb_estado.grid(row=0, column=4, sticky="w", padx=4)
        self.cmb_estado.bind("<<ComboboxSelected>>", lambda _e=None: self._on_estado_change())

        ttk.Label(head, text="Pago:").grid(row=0, column=5, sticky="e", padx=4)
        self.PAGOS = ("Crédito 30 días", "Efectivo", "Débito", "Transferencia", "Cheque")
        self.cmb_pago = ttk.Combobox(head, state="readonly", width=18, values=self.PAGOS)
        # Corrección visual de acentos en opciones de pago
        try:
            self.cmb_pago["values"] = ("Crédito 30 días", "Efectivo", "Débito", "Transferencia", "Cheque")
        except Exception:
            pass
        self.cmb_pago.set(get_po_payment_method())
        self.cmb_pago.grid(row=0, column=6, sticky="w", padx=4)
        # Modo: Compra vs Recepcion
        ttk.Label(head, text="Modo:").grid(row=0, column=7, sticky="e", padx=4)
        self.var_mode = tk.StringVar(value="Compra")
        self.cmb_mode = ttk.Combobox(head, textvariable=self.var_mode, values=["Compra", "Recepcion"], width=12, state="readonly")
        self.cmb_mode.grid(row=0, column=8, sticky="w", padx=4)
        try:
            self.var_mode.set(get_ui_purchases_mode("Compra"))
        except Exception:
            pass
        try:
            self.cmb_mode.bind("<<ComboboxSelected>>", lambda _e=None: self._on_mode_change())
        except Exception:
            pass

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
        # Ajusta política inicial de stock según estado por defecto
        try:
            self._on_estado_change()
        except Exception:
            pass


        ttk.Label(head, text="Referencia:").grid(row=4, column=0, sticky="e")
        self.var_ref = tk.StringVar()
        ttk.Entry(head, textvariable=self.var_ref, width=40).grid(row=4, column=1, columnspan=3, sticky="we")

        ttk.Label(head, text="Ajuste imp:").grid(row=4, column=4, sticky="e")
        self.var_ajimp = tk.StringVar(value="0")
        ttk.Entry(head, textvariable=self.var_ajimp, width=10).grid(row=4, column=5, sticky="w")

        # ---- Trazabilidad (solo Recepción): Lote / Serie / Vencimiento ----
        # (Deprecated en header) Lote/Serie/Venc — se muestran ahora en el bloque Detalle
        self.var_lote = tk.StringVar(); self.var_serie = tk.StringVar(); self.var_has_venc = tk.BooleanVar(value=False); self.var_venc = tk.StringVar()
        self._head_trace_widgets = []
        _lbl_lote = ttk.Label(head, text="Lote:"); _lbl_lote.grid(row=5, column=0, sticky="e"); self._head_trace_widgets.append(_lbl_lote)
        _ent_lote = ttk.Entry(head, textvariable=self.var_lote, width=18); _ent_lote.grid(row=5, column=1, sticky="w"); self._head_trace_widgets.append(_ent_lote)
        _lbl_serie = ttk.Label(head, text="Serie:"); _lbl_serie.grid(row=5, column=2, sticky="e"); self._head_trace_widgets.append(_lbl_serie)
        _ent_serie = ttk.Entry(head, textvariable=self.var_serie, width=18); _ent_serie.grid(row=5, column=3, sticky="w"); self._head_trace_widgets.append(_ent_serie)
        _chk_v = ttk.Checkbutton(head, text="Con venc.", variable=self.var_has_venc); _chk_v.grid(row=5, column=4, sticky="e"); self._head_trace_widgets.append(_chk_v)
        _ent_v = ttk.Entry(head, textvariable=self.var_venc, width=12); _ent_v.grid(row=5, column=5, sticky="w"); self._head_trace_widgets.append(_ent_v)
        # Ocultar por defecto en header (el editor vive en Detalle)
        try:
            for w in self._head_trace_widgets:
                w.grid_remove()
        except Exception:
            pass
        # Exclusividad Lote/Serie
        def _excl_sync(*_):
            try:
                if (self.var_lote.get() or '').strip():
                    if (self.var_serie.get() or '').strip():
                        self.var_serie.set('')
                elif (self.var_serie.get() or '').strip():
                    if (self.var_lote.get() or '').strip():
                        self.var_lote.set('')
            except Exception:
                pass
        try:
            self.var_lote.trace_add('write', _excl_sync)
            self.var_serie.trace_add('write', _excl_sync)
        except Exception:
            pass

        # Widgets visibles solo en modo Recepción (marcados por coordenadas)
        self._receipt_only_widgets = []
        try:
            coords = {
                (1,0),(1,1),  # Nº doc
                (1,2),(1,3),  # F. documento
                (1,4),(1,5),  # F. contable
                (1,6),(1,7),  # F. venc.
                (2,0),(2,1),  # Moneda
                (2,2),(2,3),  # Tasa cambio
                (2,4),(2,5),  # U. negocio
                (2,6),(2,7),  # Proporcionalidad
                (3,0),(3,1),  # Tipo dcto
                (3,2),(3,3),  # Descuento
                (3,4),(3,5),  # Ajuste IVA
                (3,6),(3,7),  # Stock
                (4,4),(4,5),  # Ajuste imp
            }
            for w in head.winfo_children():
                gi = w.grid_info()
                rc = (int(gi.get('row', -1)), int(gi.get('column', -1)))
                if rc in coords:
                    self._receipt_only_widgets.append(w)
        except Exception:
            pass
        # Aplicar visibilidad inicial según modo guardado
        try:
            self._on_mode_change()
        except Exception:
            pass

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

        # Estado interno para trazabilidad (sin UI en Detalle)
        self.tr_lote = tk.StringVar(); self.tr_serie = tk.StringVar(); self.tr_has_venc = tk.BooleanVar(value=False); self.tr_venc = tk.StringVar()
        self._trace_by_prod: Dict[int, Dict[str, object]] = {}
        self._current_reception_id: Optional[int] = None
        self._current_po_id: Optional[int] = None

        # Editor de trazabilidad (debajo del bloque Detalle; oculto por defecto)
        self._trace_frame = ttk.Labelframe(det, text="Trazabilidad del ítem seleccionado (Recepción)", padding=8)
        # Colocar ocupando el ancho del bloque Detalle
        self._trace_frame.grid(row=1, column=0, columnspan=9, sticky="we", pady=(6, 0))
        # Construcción de widgets dentro del frame
        self._tr_lbl_l = ttk.Label(self._trace_frame, text="Lote:")
        self._tr_ent_l = ttk.Entry(self._trace_frame, textvariable=self.tr_lote, width=18)
        self._tr_lbl_s = ttk.Label(self._trace_frame, text="Serie:")
        self._tr_ent_s = ttk.Entry(self._trace_frame, textvariable=self.tr_serie, width=18)
        self._tr_chk_v = ttk.Checkbutton(self._trace_frame, text="Con venc.", variable=self.tr_has_venc)
        self._tr_ent_v = ttk.Entry(self._trace_frame, textvariable=self.tr_venc, width=12)
        # Ubicación
        # Acordeón de ubicación (colapsable) con autocompletar
        self._tr_loc = tk.StringVar()
        self._loc_header = ttk.Button(self._trace_frame, text="Ubicación ▸", command=lambda: self._toggle_loc_panel())
        self._loc_panel = ttk.Frame(self._trace_frame)
        self._tr_lbl_loc = ttk.Label(self._loc_panel, text="Seleccionar:")
        self._tr_ac_loc = AutoCompleteCombobox(self._loc_panel, width=28, state="normal")
        # Dataset de ubicaciones
        try:
            def _loc_disp(l: Location) -> str:
                nm = (getattr(l, 'nombre', '') or '').strip()
                return nm or f"Ubicación {l.id}"
            def _loc_keys(l: Location):
                return [str(getattr(l, 'id', '')), (getattr(l, 'nombre', '') or '').strip()]
            self._tr_ac_loc.set_dataset(self._all_locations, keyfunc=_loc_disp, searchkeys=_loc_keys)
            self._loc_name_by_id = {int(l.id): (l.nombre or '') for l in self._all_locations}
            self._loc_id_by_name = {v: k for k, v in self._loc_name_by_id.items() if v}
        except Exception:
            self._loc_name_by_id = {}
            self._loc_id_by_name = {}
        self._tr_btns = ttk.Frame(self._trace_frame)
        ttk.Button(self._tr_btns, text="Guardar", command=self._on_trace_save).pack(side="left", padx=2)
        ttk.Button(self._tr_btns, text="Limpiar", command=self._on_trace_clear).pack(side="left", padx=2)
        # Layout (grilla interna)
        self._tr_lbl_l.grid(row=0, column=0, sticky="e", padx=4, pady=2)
        self._tr_ent_l.grid(row=0, column=1, sticky="w")
        self._tr_lbl_s.grid(row=0, column=2, sticky="e", padx=4)
        self._tr_ent_s.grid(row=0, column=3, sticky="w")
        self._tr_chk_v.grid(row=0, column=4, sticky="e", padx=4)
        self._tr_ent_v.grid(row=0, column=5, sticky="w")
        # Cantidad a recibir + pendiente
        self.tr_qty = tk.IntVar(value=0)
        self._tr_lbl_qty = ttk.Label(self._trace_frame, text="Cant.:")
        self._tr_sp_qty = ttk.Spinbox(self._trace_frame, from_=0, to=999999, textvariable=self.tr_qty, width=8)
        self._tr_lbl_pend = ttk.Label(self._trace_frame, text="Pendiente: -")
        self._tr_lbl_qty.grid(row=0, column=6, sticky="e", padx=4)
        self._tr_sp_qty.grid(row=0, column=7, sticky="w")
        self._tr_lbl_pend.grid(row=0, column=8, sticky="w", padx=6)
        # Acordeón header en la fila siguiente
        self._loc_header.grid(row=1, column=0, sticky="w", padx=4, pady=(4, 0))
        # Panel contenido (inicialmente oculto)
        self._tr_lbl_loc.grid(row=0, column=0, sticky="e", padx=4)
        self._tr_ac_loc.grid(row=0, column=1, sticky="w")
        # Colocar panel en la grilla pero colapsado
        self._loc_panel.grid(row=2, column=0, columnspan=12, sticky="w", padx=2)
        self._loc_panel.grid_remove()
        self._tr_btns.grid(row=0, column=11, padx=8)
        # Conjunto para show/hide
        self._trace_widgets_det = [self._trace_frame]
        # Ocultar inicialmente; se muestra en modo Recepción + edición
        try:
            self._trace_frame.grid_remove()
        except Exception:
            pass

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

        # Enlazar selección/doble-clic para refrescar trazabilidad en el editor
        try:
            self.tree.bind('<<TreeviewSelect>>', lambda _e=None: self._on_trace_load_from_selection())
            self.tree.bind('<Double-1>', lambda _e=None: self._on_trace_load_from_selection())
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
        self.cmb_product.set("")  # limpiar selección visible
        self._update_price_field()

    def _on_estado_change(self):
        """Ajusta política de stock/checkbox según el estado seleccionado.

        - Completada / Por pagar: permite mover stock (activa var_apply=True y setea 'Mueve').
        - Otros estados: no mueve stock (var_apply=False, 'No Mueve').
        """
        try:
            est = (self.cmb_estado.get() or '').strip()
        except Exception:
            est = ''
        try:
            if est in ('Completada', 'Por pagar'):
                self.var_apply.set(True)
                try:
                    self.var_stockpol.set('Mueve')
                except Exception:
                    pass
            else:
                self.var_apply.set(False)
                try:
                    self.var_stockpol.set('No Mueve')
                except Exception:
                    pass
        except Exception:
            pass

    def _on_mode_change(self):
        """Muestra/oculta campos de cabecera según el modo y persiste preferencia."""
        try:
            mode = (self.var_mode.get() or "Compra").strip()
        except Exception:
            mode = "Compra"
        # Persistir
        try:
            set_ui_purchases_mode(mode)
        except Exception:
            pass
        # Visibilidad
        is_receipt = mode.lower().startswith("recep")
        try:
            for w in getattr(self, "_receipt_only_widgets", []) or []:
                try:
                    if is_receipt:
                        # Restaurar grid si estaba oculto
                        if str(w.winfo_manager()) != "grid":
                            w.grid()
                    else:
                        w.grid_remove()
                except Exception:
                    pass
        except Exception:
            pass
        # Mostrar/Ocultar editor de trazabilidad del Detalle solo en Recepción
        try:
            # Solo mostrar si estamos editando una recepción existente
            edit_mode = bool(getattr(self, '_edit_reception_mode', False))
            if is_receipt and edit_mode:
                try:
                    self._trace_frame.grid()
                except Exception:
                    pass
            else:
                try:
                    self._trace_frame.grid_remove()
                except Exception:
                    pass
        except Exception:
            pass

    def _display_supplier(self, s: Supplier) -> str:
        rut = getattr(s, "rut", "") or ""
        rs = getattr(s, "razon_social", "") or ""
        if rut and rs:
            return f"{rut} - {rs}"
        return rs or rut or f"Proveedor {s.id}"

    # ======================== Precio con IVA ========================
    def _price_with_iva(self, p: Product) -> Decimal:
        base = D(getattr(p, "precio_compra", 0) or 0)
        return q2(base)

    def _current_iva_rate(self) -> Decimal:
        """Retorna la tasa de IVA como Decimal (por defecto 0.19).
        En esta vista no existe un control de IVA editable, por lo que usamos la
        constante IVA_RATE. Si más adelante agregas un campo IVA%, puedes leerlo aquí.
        """
        try:
            return D(IVA_RATE)
        except Exception:
            return D("0.19")

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
        def _num(s: str) -> Decimal:
            """Parsea números robustamente desde strings con $/miles/coma decimal.
            - "1.234,56" -> 1234.56
            - "1,234.56" -> 1234.56
            - "180.00"   -> 180.00
            - "$ 3.240"  -> 3240
            """
            try:
                s = str(s or '').replace('$','').replace('CLP','').replace('%','').strip()
                if not s:
                    return D(0)
                # decidir separador decimal por la última ocurrencia
                if ',' in s and '.' in s:
                    if s.rfind(',') > s.rfind('.'):
                        # miles=., decimal=,
                        s = s.replace('.', '').replace(',', '.')
                    else:
                        # miles=,, decimal=.
                        s = s.replace(',', '')
                elif ',' in s:
                    # solo coma: úsala como decimal
                    s = s.replace(',', '.')
                # else: solo punto o entero
                return D(s)
            except Exception:
                return D(0)
        for iid in self.tree.get_children():
            prod_id, _name, scnt, sprice, sdisc, _sub = self.tree.item(iid, "values")
            # Aplicamos descuento al precio unitario para reflejar el total mostrado
            try:
                disc_pct = _num(sdisc)
            except Exception:
                disc_pct = D(0)
            disc_rate = disc_pct / D(100)
            iva_rate = self._current_iva_rate()
            price_eff = q2(_num(sprice) * (D(1) + iva_rate) * (D(1) - disc_rate))
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
        # Normalizador local para valores con formato ($, miles, coma decimal)
        def _num(s: str) -> Decimal:
            try:
                s = str(s or '').replace('$','').replace('CLP','').replace('%','').strip()
                if not s:
                    return D(0)
                if ',' in s and '.' in s:
                    if s.rfind(',') > s.rfind('.'):
                        s = s.replace('.', '').replace(',', '.')
                    else:
                        s = s.replace(',', '')
                elif ',' in s:
                    s = s.replace(',', '.')
                return D(s)
            except Exception:
                return D(0)
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
            iva_rate = self._current_iva_rate()
            rows.append({
                "id": int(prod_id),
                "nombre": str(name),
                "cantidad": int(float(scnt)),
                "precio": q2(_num(sprice) * (D(1) + iva_rate)),          # con IVA (precio bruto)
                "subtotal": D(ssub),          # con IVA y descuento ya aplicado
                "dcto_pct": disc_pct,         # usado por OC
                "descuento_porcentaje": disc_pct,  # compat para cotización
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
            # Modo Recepcion: solo entradas de stock
            try:
                mode = (self.var_mode.get() if hasattr(self, 'var_mode') else 'Compra') or 'Compra'
            except Exception:
                mode = 'Compra'
            if str(mode).lower().startswith('recep'):
                # Si venimos vinculados a una OC, aplicar recepción coherente (recibe pendientes)
                po_id = getattr(self, '_current_po_id', None)
                if po_id:
                    po = self.session.get(Purchase, int(po_id))
                    if po:
                        # Intentar inferir tipo de documento desde la recepción vinculada
                        tipo_doc = None
                        try:
                            from src.data.models import Reception
                            rec_id = getattr(self, '_current_reception_id', None)
                            if rec_id:
                                rec = self.session.get(Reception, int(rec_id))
                                if rec is not None:
                                    tipo_doc = getattr(rec, 'tipo_doc', None)
                        except Exception:
                            tipo_doc = None
                        self._apply_reception_for_po(po, tipo_doc=tipo_doc)
                        return
                # Fallback: entradas simples con trazabilidad por ítem seleccionado
                for iid in self.tree.get_children():
                    vals = self.tree.item(iid, "values")
                    try:
                        prod_id = int(vals[0]); qty = int(float(vals[2]))
                    except Exception:
                        continue
                    if qty <= 0:
                        continue
                    tr = (self._trace_by_prod.get(prod_id) or {})
                    lote = (tr.get('lote') or None)
                    serie = (tr.get('serie') or None)
                    venc = (tr.get('venc') or None)
                    # Ubicación prioriza la trazabilidad; si no, toma la ubicación por defecto del producto
                    loc_id = None
                    try:
                        loc_id = (tr.get('loc_id') if isinstance(tr, dict) else None)
                        if not loc_id:
                            p = self.session.get(Product, int(prod_id))
                            if p and getattr(p, 'id_ubicacion', None):
                                loc_id = int(getattr(p, 'id_ubicacion'))
                    except Exception:
                        loc_id = None
                    if lote and serie:
                        serie = None
                self.inv.register_entry(
                    product_id=prod_id, cantidad=qty, motivo=f"Recepción {self._stamp()}",
                        lote=str(lote) if lote else None, serie=str(serie) if serie else None, fecha_vencimiento=venc,
                        reception_id=getattr(self, '_current_reception_id', None),
                        location_id=loc_id
                    )
                try:
                    self.session.commit()
                except Exception:
                    self.session.rollback(); self.session.commit()
                self._on_clear_table()
                self._info("Recepción registrada.")
                return

            # Validación extra en UI: por si editaron manualmente la tabla
            # (la capa core también valida, pero esto mejora la UX)
            for it in items:
                p: Optional[Product] = self.session.get(Product, it.product_id)
                if not p or getattr(p, "id_proveedor", None) != sup.id:
                    self._error(f"El producto id={it.product_id} no corresponde al proveedor seleccionado.")
                    return

            estado = (getattr(self, 'cmb_estado', None).get() if hasattr(self, 'cmb_estado') else "Completada") or "Completada"
            # Unifica política de movimiento de stock: usa el checkbox var_apply
            apply_to_stock = bool(getattr(self, 'var_apply', tk.BooleanVar(value=True)).get()) and (estado in ("Completada", "Por pagar"))

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
                sp = (getattr(self, 'var_stockpol', tk.StringVar(value='No Mueve')).get() or 'No Mueve')
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
            # Bloquear generación en modo Recepción
            try:
                if str((self.var_mode.get() or "")).lower().startswith("recep"):
                    self._warn("En modo Recepción no se generan documentos.")
                    return
            except Exception:
                pass
            sup = self._selected_supplier()
            if not sup:
                self._warn("Seleccione un proveedor.")
                return
            items = self._collect_items_for_pdf()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return

            # Número de OC secuencial (OC-000000, OC-000001, ...)
            try:
                from src.utils.helpers import make_po_number
                po_number = make_po_number()
            except Exception:
                po_number = f"OC-{self._stamp()}"
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
            out = generate_po_to_downloads(
                po_number=po_number,
                supplier=supplier_dict,
                items=items,
                currency="CLP",
                notes=notes,
                auto_open=True,
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
            # Construir notas (igual que en OC)
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
                "nombre": getattr(sup, "razon_social", "") or "",
                "contacto": getattr(sup, "contacto", "") or "",
                "telefono": getattr(sup, "telefono", "") or "",
                "email": getattr(sup, "email", "") or "",
                "direccion": getattr(sup, "direccion", "") or "",
                "pago": (getattr(self, 'cmb_pago', None).get() if hasattr(self, 'cmb_pago') else get_po_payment_method()),
            }

            out = generate_quote_downloads(
                quote_number=quote_number,
                supplier=supplier_dict,
                items=items,
                currency="CLP",
                notes=notes,
                auto_open=True,
            )
            self._info(f"Cotización creada en Descargas:\n{out}")

        except Exception as e:
            self._error(f"No se pudo generar la Cotización:\n{e}")

    @staticmethod
    def _stamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d-%H%M%S")
    # ======================== Recepción desde Órdenes ========================
    def load_purchase_for_reception(self, purchase_id: int, *, rec_id: int | None = None, tipo_doc: str | None = None, numero_doc: str | None = None, lote: str | None = None, serie: str | None = None, has_venc: bool | None = None, f_venc: str | None = None) -> None:
        try:
            po = self.session.get(Purchase, int(purchase_id))
            if not po:
                self._error(f"No se encontró la OC {purchase_id}.")
                return
            try:
                self.var_mode.set("Recepcion")
                self._on_mode_change()
            except Exception:
                pass
            self.refresh_lookups()
            try:
                pid = int(po.id_proveedor)
                idx = next((i for i, s in enumerate(self.suppliers) if int(s.id) == pid), -1)
                if idx >= 0:
                    self.cmb_supplier.current(idx)
            except Exception:
                pass
            for iid in self.tree.get_children():
                self.tree.delete(iid)
            # Construye tabla con pendientes y dataset para posible edición
            pending_lines = []  # (prod_id, name, pending)
            for det in po.details:
                try:
                    pending = int(det.cantidad or 0) - int(getattr(det, "received_qty", 0) or 0)
                except Exception:
                    pending = 0
                if pending <= 0:
                    continue
                p = self.session.get(Product, det.id_producto)
                if not p:
                    continue
                price = self._price_with_iva(p)
                price_bruto = q2(D(price) * (D(1) + IVA_RATE))
                subtotal = q2(D(pending) * price_bruto)
                self.tree.insert("", "end", values=(p.id, p.nombre, pending, fmt_2(price), "0", fmt_2(subtotal)))
                pending_lines.append((int(p.id), str(p.nombre), int(pending)))
            if numero_doc:
                try:
                    self.var_numdoc.set(numero_doc)
                except Exception:
                    pass
            # Prefill trazabilidad si llegó desde Órdenes
            try:
                if lote:
                    self.var_lote.set(lote)
                if serie:
                    self.var_serie.set(serie)
                if bool(has_venc):
                    self.var_has_venc.set(True)
                    if f_venc:
                        self.var_venc.set(str(f_venc))
            except Exception:
                pass
            try:
                self._current_reception_id = int(rec_id) if rec_id is not None else None
                self._current_po_id = int(po.id)
                # Modo edición si venimos con una recepción existente
                self._edit_reception_mode = bool(self._current_reception_id)
                self._on_mode_change()  # fuerza mostrar editor si corresponde
            except Exception:
                self._current_reception_id = None; self._current_po_id = int(po.id); self._edit_reception_mode = False
            # Prefill trazabilidad si llegó desde Órdenes
            try:
                if lote:
                    self.var_lote.set(lote)
                if serie:
                    self.var_serie.set(serie)
                if bool(has_venc):
                    self.var_has_venc.set(True)
                    if f_venc:
                        self.var_venc.set(str(f_venc))
            except Exception:
                pass
            # Guardar id de recepción actual (si hay)
            try:
                self._current_reception_id = int(rec_id) if rec_id is not None else None
            except Exception:
                self._current_reception_id = None
            self._update_total()
            # Si es Guía, permitir edición de cantidades a recepcionar por línea
            is_guia = False
            try:
                is_guia = (str(tipo_doc or "").lower().startswith("gu"))
            except Exception:
                is_guia = False

            received_by: Dict[int, int] | None = None
            if is_guia and pending_lines:
                try:
                    from src.gui.reception_qty_dialog import ReceptionQtyDialog
                    dlg = ReceptionQtyDialog(self, pending_lines, title=f"Recepción OC {po.id} (Guía)")
                    self.wait_window(dlg)
                    if dlg.result is None:
                        return  # cancelado
                    received_by = dlg.result
                except Exception:
                    received_by = None

            if not messagebox.askyesno("Recepción", f"OC {po.id}: ¿Desea confirmar esta recepción ahora?"):
                return
            self._apply_reception_for_po(po, received_by_prod=received_by, tipo_doc=tipo_doc)
        except Exception as ex:
            self._error(f"No se pudo preparar la recepción:\n{ex}")

    def _apply_reception_for_po(self, po: Purchase, *, received_by_prod: Dict[int, int] | None = None, tipo_doc: str | None = None) -> None:
        """
        Aplica la recepción a la OC:
        - Si received_by_prod es None: recepciona todo lo pendiente.
        - Si viene un dict: recepciona por producto las cantidades indicadas (capped al pendiente).
        - Suma stock solo si la OC estaba Pendiente.
        - Estado final si está totalmente recepcionada:
            * Factura -> 'Completada'
            * Guía    -> 'Por pagar'
        """
        estado_actual = str(getattr(po, "estado", "")).strip()
        add_stock = estado_actual in ("Pendiente", "Incompleta")
        any_received = False
        try:
            # Cargar trazabilidad por producto (si existe guardada en el editor)

            # Si estamos editando una recepción existente: actualizar trazabilidad sin mover stock
            edit_mode = bool(getattr(self, '_edit_reception_mode', False)) and bool(getattr(self, '_current_reception_id', None))
            if edit_mode:
                try:
                    from src.data.models import StockEntry
                    rec_id = int(getattr(self, '_current_reception_id', 0) or 0)
                    # ¿Ya existen movimientos para esta recepción?
                    existing = (
                        self.session.query(StockEntry.id)
                        .filter(StockEntry.id_recepcion == rec_id)
                        .limit(1)
                        .all()
                    )
                    if existing:
                        # Actualiza trazabilidad sobre movimientos existentes
                        for pid, tr in (self._trace_by_prod or {}).items():
                            lote = (tr.get('lote') or None)
                            serie = (tr.get('serie') or None)
                            venc = (tr.get('venc') or None)
                            if lote and serie:
                                serie = None
                            q = (
                                self.session.query(StockEntry)
                                .filter(StockEntry.id_recepcion == rec_id)
                                .filter(StockEntry.id_producto == int(pid))
                            )
                            for se in q:
                                se.lote = str(lote) if lote else None
                                se.serie = str(serie) if serie else None
                                se.fecha_vencimiento = venc
                                # También actualiza ubicación si viene en la trazabilidad;
                                # si no, usa la ubicación por defecto del producto.
                                try:
                                    loc_id = tr.get('loc_id') if isinstance(tr, dict) else None
                                    if not loc_id:
                                        p = self.session.get(Product, int(pid))
                                        if p and getattr(p, 'id_ubicacion', None):
                                            loc_id = int(getattr(p, 'id_ubicacion'))
                                    se.id_ubicacion = int(loc_id) if loc_id else None
                                except Exception:
                                    pass
                        self.session.commit()
                        self._info('Recepción actualizada.')
                        return
                    # Si no existen movimientos todavía, seguimos abajo con el flujo normal de creación
                except Exception:
                    # Si falla la comprobación, continuar con flujo normal
                    pass

            for det in po.details:
                # Pendiente por línea
                try:
                    pending = int(det.cantidad or 0) - int(getattr(det, "received_qty", 0) or 0)
                except Exception:
                    pending = 0
                if pending <= 0:
                    continue
                # Cantidad a recepcionar esta vez
                if received_by_prod is None:
                    # Si hay cantidad guardada en el editor, úsala
                    try:
                        tr_rec = self._trace_by_prod.get(int(det.id_producto)) or {}
                        tr_qty_val = int(tr_rec.get('qty') or 0)
                    except Exception:
                        tr_qty_val = 0
                    if tr_qty_val > 0:
                        to_recv = min(int(pending), tr_qty_val)
                    else:
                        to_recv = int(pending)
                else:
                    to_recv = int(max(0, int(received_by_prod.get(int(det.id_producto), 0))))
                    if to_recv > pending:
                        to_recv = int(pending)
                if to_recv <= 0:
                    continue
                # Por defecto, usa lo guardado para este producto; si no hay, intenta header (compat)
                tr = (self._trace_by_prod.get(int(det.id_producto)) or {})
                lote = (tr.get('lote') or None)
                serie = (tr.get('serie') or None)
                venc = (tr.get('venc') or None)
                if not (lote or serie or venc):
                    try:
                        lote = (self.var_lote.get() or '').strip() or None
                        serie = (self.var_serie.get() or '').strip() or None
                        if lote and serie:
                            serie = None
                        if bool(self.var_has_venc.get()):
                            s = (self.var_venc.get() or '').strip()
                            if s:
                                venc = self._parse_ddmmyyyy(s)
                    except Exception:
                        pass
                if add_stock:
                    # Determinar ubicación: primero la guardada en trazabilidad, si no la del producto
                    loc_id = None
                    try:
                        loc_id = (tr.get('loc_id') if isinstance(tr, dict) else None)
                        if not loc_id:
                            p = self.session.get(Product, int(det.id_producto))
                            if p and getattr(p, 'id_ubicacion', None):
                                loc_id = int(getattr(p, 'id_ubicacion'))
                    except Exception:
                        loc_id = None
                    self.inv.register_entry(
                        product_id=int(det.id_producto), cantidad=int(to_recv),
                        motivo=f"Recepción {po.id}",
                        lote=str(lote) if lote else None,
                        serie=str(serie) if serie else None,
                        fecha_vencimiento=venc,
                        reception_id=getattr(self, '_current_reception_id', None),
                        location_id=loc_id
                    )
                det.received_qty = int(getattr(det, "received_qty", 0) or 0) + int(to_recv)
                if to_recv > 0:
                    any_received = True

            # Si suma stock y quedó totalmente recepcionada, ajusta estado según tipo_doc
            all_rec = True
            for d in po.details:
                if int(getattr(d, "received_qty", 0) or 0) < int(d.cantidad or 0):
                    all_rec = False
                    break
            if all_rec and any_received:
                td = (tipo_doc or "").lower()
                if td.startswith("fact"):
                    po.estado = "Completada"
                elif td.startswith("gu"):
                    po.estado = "Por pagar"
                else:
                    # Fallback
                    if add_stock:
                        po.estado = "Por pagar"
            elif any_received:
                # Recepción parcial
                po.estado = "Incompleta"

            self.session.commit()
            self._on_clear_table()
            self._info(f"Recepción de OC {po.id} confirmada.")
        except Exception as ex:
            self.session.rollback()
            self._error(f"No se pudo confirmar la recepción:\n{ex}")

    # ======================== Editor de trazabilidad ========================
    def _trace_selected_product_id(self) -> Optional[int]:
        sel = self.tree.selection()
        if not sel:
            return None
        try:
            vals = self.tree.item(sel[0], 'values')
            return int(vals[0])
        except Exception:
            return None

    def _on_trace_load_from_selection(self):
        pid = self._trace_selected_product_id()
        if pid is None:
            self._on_trace_clear()
            return
        tr = self._trace_by_prod.get(int(pid)) or {}
        # Si no hay datos en memoria y estamos editando una recepción, intenta cargar desde DB
        if not tr and bool(getattr(self, '_edit_reception_mode', False)) and getattr(self, '_current_reception_id', None):
            try:
                from src.data.models import StockEntry
                rec_id = int(getattr(self, '_current_reception_id', 0) or 0)
                se = (
                    self.session.query(StockEntry)
                    .filter(StockEntry.id_recepcion == rec_id)
                    .filter(StockEntry.id_producto == int(pid))
                    .order_by(StockEntry.id.desc())
                    .first()
                )
                if se is not None:
                    tr = {
                        'lote': getattr(se, 'lote', None) or None,
                        'serie': getattr(se, 'serie', None) or None,
                        'venc': getattr(se, 'fecha_vencimiento', None) or None,
                        'loc_id': getattr(se, 'id_ubicacion', None) or None,
                    }
                    self._trace_by_prod[int(pid)] = tr
            except Exception:
                pass
        # Fallback a ubicación por defecto del producto si no hay trazabilidad cargada
        if not tr.get('loc_id'):
            try:
                p = self.session.get(Product, int(pid))
                if p and getattr(p, 'id_ubicacion', None):
                    tr['loc_id'] = int(getattr(p, 'id_ubicacion'))
                    self._trace_by_prod[int(pid)] = tr
            except Exception:
                pass
        try:
            self.tr_lote.set(str(tr.get('lote') or ''))
            self.tr_serie.set(str(tr.get('serie') or ''))
            v = tr.get('venc');
            self.tr_has_venc.set(bool(v))
            self.tr_venc.set(v.strftime('%d/%m/%Y') if v else '')
            # Ubicación
            loc_id = tr.get('loc_id')
            if loc_id and loc_id in getattr(self, '_loc_name_by_id', {}):
                try:
                    self._tr_ac_loc.set(self._loc_name_by_id[int(loc_id)])
                except Exception:
                    self._tr_loc.set(self._loc_name_by_id[int(loc_id)])
            else:
                try:
                    self._tr_ac_loc.set('')
                except Exception:
                    self._tr_loc.set('')
            # Cantidad y pendiente
            pend = None
            try:
                # calcular pendiente desde la OC si está disponible
                if getattr(self, '_current_po_id', None):
                    det = (
                        self.session.query(PurchaseDetail)
                        .filter(PurchaseDetail.id_compra == int(self._current_po_id))
                        .filter(PurchaseDetail.id_producto == int(pid))
                        .first()
                    )
                    if det is not None:
                        pend = max(0, int(getattr(det, 'cantidad', 0) or 0) - int(getattr(det, 'received_qty', 0) or 0))
            except Exception:
                pend = None
            if pend is None:
                # fallback: usa la cantidad mostrada en la fila
                try:
                    vals = self.tree.item(self.tree.selection()[0], 'values')
                    pend = int(float(vals[2]))
                except Exception:
                    pend = 0
            try:
                self._tr_lbl_pend.config(text=f"Pendiente: {pend}")
            except Exception:
                pass
            # set qty saved or pending
            try:
                q_saved = tr.get('qty')
                q_val = int(q_saved) if q_saved is not None else int(pend)
                self.tr_qty.set(max(0, q_val))
            except Exception:
                self.tr_qty.set(int(pend or 0))
        except Exception:
            self.tr_lote.set(''); self.tr_serie.set(''); self.tr_has_venc.set(False); self.tr_venc.set('')
            try: self._tr_loc.set('')
            except Exception: pass

    def _on_trace_clear(self):
        try:
            self.tr_lote.set(''); self.tr_serie.set(''); self.tr_has_venc.set(False); self.tr_venc.set('')
            self._tr_loc.set('')
            self.tr_qty.set(0)
            try:
                self._tr_lbl_pend.config(text="Pendiente: -")
            except Exception:
                pass
        except Exception:
            pass

    def _on_trace_save(self):
        pid = self._trace_selected_product_id()
        if pid is None:
            self._warn('Seleccione un ítem en la tabla para aplicar trazabilidad.')
            return
        lote = (self.tr_lote.get() or '').strip()
        serie = (self.tr_serie.get() or '').strip()
        if lote and serie:
            # Exclusivo: prioriza lote
            serie = ''
        venc = None
        if bool(self.tr_has_venc.get()):
            s = (self.tr_venc.get() or '').strip()
            if s:
                try:
                    venc = self._parse_ddmmyyyy(s)
                except Exception:
                    self._warn('Fecha de vencimiento inválida. Use dd/mm/aaaa.')
                    return
        self._trace_by_prod[int(pid)] = {
            'lote': (lote or None),
            'serie': (serie or None),
            'venc': venc,
            'loc_id': (self._tr_ac_loc.get_selected_item().id if getattr(self._tr_ac_loc, 'get_selected_item', None) and self._tr_ac_loc.get_selected_item() is not None else (self._loc_id_by_name.get(self._tr_ac_loc.get()) if getattr(self, '_loc_id_by_name', None) else None)),
            'qty': (int(self.tr_qty.get()) if str(self.tr_qty.get()).strip() != '' else None),
        }
        self._info('Trazabilidad guardada para el producto seleccionado.')

    def _toggle_loc_panel(self):
        try:
            if str(self._loc_panel.winfo_manager()) == 'grid':
                self._loc_panel.grid_remove()
                try: self._loc_header.config(text="Ubicación ▸")
                except Exception: pass
            else:
                self._loc_panel.grid()
                try: self._loc_header.config(text="Ubicación ▾")
                except Exception: pass
        except Exception:
            pass

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










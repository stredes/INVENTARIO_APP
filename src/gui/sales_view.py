from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Dict, Callable
from decimal import Decimal

from src.data.database import get_session
from src.data.models import Product, Customer
from src.data.repository import ProductRepository, CustomerRepository
from src.core import SalesManager, SaleItem
from src.utils.so_generator import generate_so_to_downloads
from src.utils.quote_generator import generate_quote_to_downloads
from src.gui.widgets.autocomplete_combobox import AutoCompleteCombobox
from src.reports.sales_report_pdf import generate_sales_report_to_downloads
from sqlalchemy import and_
from src.utils.money import D, q2, fmt_2
from src.gui.treeview_utils import apply_default_treeview_styles, enable_auto_center_for_new_treeviews

class SalesView(ttk.Frame):
    """
    Crear ventas + Generar OV + ADMIN (cancelar / marcar eliminada).
    Selector de estado y lógica de stock:
      - Pagada -> puede descontar stock (si checkbox activo)
      - Reservada / Cancelada -> no descuenta
    Informe de Ventas con filtros + exportación CSV/PDF a Descargas.
    """

    ESTADOS = ["Pagada", "Confirmada", "Pendiente", "Cancelada", "Eliminada"]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        try:
            apply_default_treeview_styles()
            enable_auto_center_for_new_treeviews()
        except Exception:
            pass

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
        ttk.Checkbutton(top, text="Descontar stock (Confirmada/Pagada)", variable=self.var_apply)\
            .grid(row=0, column=2, padx=10)

        # Estado y forma de pago en el encabezado (igual que Compras)
        ttk.Label(top, text="Estado:").grid(row=0, column=3, sticky="e", padx=4)
        self.cmb_estado = ttk.Combobox(top, state="readonly", width=14, values=self.ESTADOS)
        self.cmb_estado.current(0)
        self.cmb_estado.grid(row=0, column=4, sticky="w", padx=4)

        ttk.Label(top, text="Pago:").grid(row=0, column=5, sticky="e", padx=4)
        self.PAGOS = ("Contado", "Débito", "Transferencia", "Crédito 30 días")
        self.cmb_pago = ttk.Combobox(top, state="readonly", width=18, values=self.PAGOS)
        try:
            self.cmb_pago["values"] = ("Contado", "Débito", "Transferencia", "Crédito 30 días")
        except Exception:
            pass
        self.cmb_pago.set("Contado")
        self.cmb_pago.grid(row=0, column=6, sticky="w", padx=4)

        # ---------- Modo Cajero de ventas (POS) ----------
        self._cashier_mode = tk.BooleanVar(value=False)
        cashier_bar = ttk.Frame(self)
        cashier_bar.pack(fill="x", expand=False, pady=(8, 0))
        ttk.Checkbutton(
            cashier_bar,
            text="Modo cajero de ventas",
            variable=self._cashier_mode,
            command=lambda: self._toggle_cashier_ui(),
        ).pack(side="left")

        self._cashier_frame = ttk.Labelframe(self, text="Cajero de ventas", padding=8)
        self._cashier_frame.pack_forget()

        ttk.Label(self._cashier_frame, text="Escanear SKU:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.ent_scan = ttk.Entry(self._cashier_frame, width=28)
        self.ent_scan.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.ent_scan.bind("<Return>", lambda _e: self._on_scan_enter())

        ttk.Button(self._cashier_frame, text="Agregar", command=self._on_scan_enter).grid(row=0, column=2, padx=6)
        ttk.Button(self._cashier_frame, text="Cobrar (F12)", command=self._on_quick_checkout).grid(row=0, column=3, padx=6)

        try:
            self.bind_all("<F12>", lambda _e: self._on_quick_checkout())
            self.bind_all("<Control-l>", lambda _e: self._focus_scan())
        except Exception:
            pass

        # ---------- Detalle ----------
        det = ttk.Labelframe(self, text="Detalle de venta", padding=10)
        det.pack(fill="x", expand=False, pady=(10, 0))

        ttk.Label(det, text="Producto:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_product = AutoCompleteCombobox(det, width=45, state="normal")
        self.cmb_product.grid(row=0, column=1, sticky="w", padx=4, pady=4)
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
            .grid(row=0, column=8, padx=8)

        # Campos ampliados
        self.var_det_nro = tk.StringVar(value="1")
        self.var_prod_code = tk.StringVar(value="")
        self.var_prod_desc = tk.StringVar(value="")
        self.var_unidad = tk.StringVar(value="Unidades")
        self.var_desc_tipo = tk.StringVar(value="Monto")
        self.var_desc_val = tk.DoubleVar(value=0.0)
        self.var_ccosto = tk.StringVar(value="1001 - Ventas")
        self.var_moneda = tk.StringVar(value="PESO CHILENO")
        self.var_tasa = tk.DoubleVar(value=1.0)
        self.var_monto_neto = tk.DoubleVar(value=0.0)

        ttk.Label(det, text="Número detalle").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_det_nro, width=10, state="readonly").grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Código de producto").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_prod_code, width=18, state="readonly").grid(row=1, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Descripción").grid(row=1, column=4, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_prod_desc, width=36, state="readonly").grid(row=1, column=5, columnspan=3, sticky="we", padx=4, pady=4)

        ttk.Label(det, text="Unidad").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        cb_unid = ttk.Combobox(det, textvariable=self.var_unidad, state="readonly",
                                values=["Unidades", "Caja", "Bolsa", "kg", "lt", "ml"])
        cb_unid.grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Tipo desc").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        cb_tipo = ttk.Combobox(det, textvariable=self.var_desc_tipo, state="readonly",
                                values=["Monto", "Porcentaje"])
        cb_tipo.grid(row=2, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Descuento").grid(row=2, column=4, sticky="e", padx=4, pady=4)
        ent_desc = ttk.Entry(det, textvariable=self.var_desc_val, width=12)
        ent_desc.grid(row=2, column=5, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Monto neto").grid(row=2, column=6, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_monto_neto, width=14, state="readonly").grid(row=2, column=7, sticky="w", padx=4, pady=4)

        # ---------- Tabla ----------
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, pady=(10, 0))
        columns = ("id", "nombre", "cantidad", "precio", "dcto", "subtotal")
        self.tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        for cid, text, w in [
            ("id", "ID", 70),
            ("nombre", "Producto", 320),
            ("cantidad", "Cant.", 80),
            ("precio", "Precio", 110),
            ("dcto", "Dcto %", 70),
            ("subtotal", "Subtotal", 120),
        ]:
            self.tree.heading(cid, text=text, anchor="center")
            self.tree.column(cid, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Button-4>", self._on_mousewheel)
        self.tree.bind("<Button-5>", self._on_mousewheel)
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

        ttk.Button(bottom, text="Eliminar ítem", command=self._on_delete_item)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Limpiar tabla", command=self._on_clear_table)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar Cotización (PDF)", command=self._on_generate_sales_quote)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar OV (PDF en Descargas)", command=self._on_generate_so_downloads)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Guardar venta", command=self._on_confirm_sale)\
            .pack(side="right", padx=6)

        self.refresh_lookups()

    @staticmethod
    def _fmt_clp(value) -> str:
        """CLP con miles y sin decimales (p.ej., $1.234.567)."""
        try:
            n = float(value or 0)
            s = f"${n:,.0f}"
            return s.replace(",", ".")
        except Exception:
            return "$ 0"

        # ---------- Encabezado ----------
        top = ttk.Labelframe(self, text="Encabezado de venta", padding=10)
        top.pack(fill="x", expand=False)

        ttk.Label(top, text="Cliente:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_customer = ttk.Combobox(top, state="readonly", width=50)
        self.cmb_customer.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        self.var_apply = tk.BooleanVar(value=True)
        ttk.Checkbutton(top, text="Descontar stock (Confirmada/Pagada)", variable=self.var_apply)\
            .grid(row=0, column=2, padx=10)

        # Estado y forma de pago en el encabezado (igual que Compras)
        ttk.Label(top, text="Estado:").grid(row=0, column=3, sticky="e", padx=4)
        self.cmb_estado = ttk.Combobox(top, state="readonly", width=14, values=self.ESTADOS)
        self.cmb_estado.current(0)
        self.cmb_estado.grid(row=0, column=4, sticky="w", padx=4)

        ttk.Label(top, text="Pago:").grid(row=0, column=5, sticky="e", padx=4)
        self.PAGOS = ("Contado", "Débito", "Transferencia", "Crédito 30 días")
        self.cmb_pago = ttk.Combobox(top, state="readonly", width=18, values=self.PAGOS)
        try:
            self.cmb_pago["values"] = ("Contado", "Débito", "Transferencia", "Crédito 30 días")
        except Exception:
            pass
        self.cmb_pago.set("Contado")
        self.cmb_pago.grid(row=0, column=6, sticky="w", padx=4)

        # ---------- Modo Cajero de ventas (POS) ----------
        self._cashier_mode = tk.BooleanVar(value=False)
        cashier_bar = ttk.Frame(self)
        cashier_bar.pack(fill="x", expand=False, pady=(8, 0))
        ttk.Checkbutton(
            cashier_bar,
            text="Modo cajero de ventas",
            variable=self._cashier_mode,
            command=lambda: self._toggle_cashier_ui(),
        ).pack(side="left")

        self._cashier_frame = ttk.Labelframe(self, text="Cajero de ventas", padding=8)
        # Oculto por defecto; se muestra al activar el modo
        self._cashier_frame.pack_forget()

        ttk.Label(self._cashier_frame, text="Escanear SKU:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.ent_scan = ttk.Entry(self._cashier_frame, width=28)
        self.ent_scan.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.ent_scan.bind("<Return>", lambda _e: self._on_scan_enter())

        ttk.Button(self._cashier_frame, text="Agregar", command=self._on_scan_enter).grid(row=0, column=2, padx=6)
        ttk.Button(self._cashier_frame, text="Cobrar (F12)", command=self._on_quick_checkout).grid(row=0, column=3, padx=6)

        # Atajos de teclado útiles en cajero
        try:
            self.bind_all("<F12>", lambda _e: self._on_quick_checkout())
            self.bind_all("<Control-l>", lambda _e: self._focus_scan())
        except Exception:
            pass

        # ---------- Detalle ----------
        det = ttk.Labelframe(self, text="Detalle de venta", padding=10)
        det.pack(fill="x", expand=False, pady=(10, 0))

        ttk.Label(det, text="Producto:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.cmb_product = AutoCompleteCombobox(det, width=45, state="normal")
        self.cmb_product.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.cmb_product.bind("<<ComboboxSelected>>", self._on_product_change)

        ttk.Label(det, text="Cantidad:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.ent_qty = ttk.Entry(det, width=10)
        self.ent_qty.insert(0, "1")
        self.ent_qty.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(det, text="Precio (venta):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.ent_price = ttk.Entry(det, width=12)
        self.ent_price.insert(0, "0")
        self.ent_price.grid(row=0, column=5, sticky="w", padx=4, pady=4)

        # (Se eliminó el campo duplicado de Dcto (%) en cabecera)

        ttk.Button(det, text="Agregar ítem", command=self._on_add_item)\
            .grid(row=0, column=8, padx=8)

        # ----- Campos ampliados de Detalle (como en la referencia) -----
        # Variables de estado
        self.var_det_nro = tk.StringVar(value="1")
        self.var_prod_code = tk.StringVar(value="")
        self.var_prod_desc = tk.StringVar(value="")
        self.var_unidad = tk.StringVar(value="Unidades")
        self.var_desc_tipo = tk.StringVar(value="Monto")  # Monto | Porcentaje
        self.var_desc_val = tk.DoubleVar(value=0.0)
        self.var_ccosto = tk.StringVar(value="1001 - Ventas")
        self.var_moneda = tk.StringVar(value="PESO CHILENO")
        self.var_tasa = tk.DoubleVar(value=1.0)
        self.var_monto_neto = tk.DoubleVar(value=0.0)

        # Fila 1: Número detalle / Código de producto / Descripción
        ttk.Label(det, text="Número detalle").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_det_nro, width=10, state="readonly").grid(row=1, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Código de producto").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_prod_code, width=18, state="readonly").grid(row=1, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Descripción").grid(row=1, column=4, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_prod_desc, width=36, state="readonly").grid(row=1, column=5, columnspan=3, sticky="we", padx=4, pady=4)

        # Fila 2: Unidad / Tipo desc / Descuento / Monto neto unitario
        ttk.Label(det, text="Unidad").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(det, textvariable=self.var_unidad, state="readonly", width=12,
                     values=["Unidades", "Caja", "Bolsa", "kg", "lt", "ml"]).grid(row=2, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Tipo desc").grid(row=2, column=2, sticky="e", padx=4, pady=4)
        cb_tipo = ttk.Combobox(det, textvariable=self.var_desc_tipo, state="readonly", width=12,
                               values=["Monto", "Porcentaje"])
        cb_tipo.grid(row=2, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Descuento").grid(row=2, column=4, sticky="e", padx=4, pady=4)
        ent_desc = ttk.Entry(det, textvariable=self.var_desc_val, width=12)
        ent_desc.grid(row=2, column=5, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Monto neto").grid(row=2, column=6, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_monto_neto, width=14, state="readonly").grid(row=2, column=7, sticky="w", padx=4, pady=4)

        # Fila 3: Centro de costo / Moneda / Tasa de cambio
        ttk.Label(det, text="Centro de costo").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(det, textvariable=self.var_ccosto, state="readonly", width=18,
                     values=["1001 - Ventas", "1002 - Exportaciones", "1003 - Servicios"]).grid(row=3, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Moneda").grid(row=3, column=2, sticky="e", padx=4, pady=4)
        ttk.Combobox(det, textvariable=self.var_moneda, state="readonly", width=18,
                     values=["PESO CHILENO", "USD", "EUR"]).grid(row=3, column=3, sticky="w", padx=4, pady=4)
        ttk.Label(det, text="Tasa de cambio").grid(row=3, column=4, sticky="e", padx=4, pady=4)
        ttk.Entry(det, textvariable=self.var_tasa, width=12).grid(row=3, column=5, sticky="w", padx=4, pady=4)

        # Eventos para recalcular neto unitario y mantener la compatibilidad con Dcto %
        try:
            self.ent_price.bind("<KeyRelease>", lambda _e: self._recalc_net())
            ent_desc.bind("<KeyRelease>", lambda _e: self._recalc_net())
            cb_tipo.bind('<<ComboboxSelected>>', lambda _e: self._recalc_net())
        except Exception:
            pass

        # ---------- Tabla + Scrollbar ----------
        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, pady=(10, 0))
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("prod_id", "producto", "cant", "precio", "dcto", "subtotal"),
            show="headings",
            height=8,
        )
        for cid, text, w in [
            ("prod_id", "ID", 60),
            ("producto", "Producto", 300),
            ("cant", "Cant.", 80),
            ("precio", "Precio", 100),
            ("dcto", "Dcto %", 70),
            ("subtotal", "Subtotal", 120),
        ]:
            self.tree.heading(cid, text=text, anchor="center")
            self.tree.column(cid, width=w, anchor="center")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Soporte de rueda del ratón (Windows/macOS/Linux)
        self.tree.bind("<MouseWheel>", self._on_mousewheel)
        self.tree.bind("<Button-4>", self._on_mousewheel)   # Linux scroll up
        self.tree.bind("<Button-5>", self._on_mousewheel)   # Linux scroll down
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

        # Estado ya está en el encabezado; no lo repetimos en el footer

        ttk.Button(bottom, text="Eliminar ítem", command=self._on_delete_item)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Limpiar tabla", command=self._on_clear_table)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar Cotización (PDF)", command=self._on_generate_sales_quote)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Generar OV (PDF en Descargas)", command=self._on_generate_so_downloads)\
            .pack(side="right", padx=6)
        ttk.Button(bottom, text="Guardar venta", command=self._on_confirm_sale)\
            .pack(side="right", padx=6)

        # (Se removieron los paneles de Administración e Informe de Ventas)
        self.refresh_lookups()
        
    # ==================== Modo Cajero (POS) ==================== #
    def _toggle_cashier_ui(self) -> None:
        try:
            if self._cashier_mode.get():
                self._cashier_frame.pack(fill="x", expand=False, pady=(6, 0))
                # Sugerir estado Pagada y pago Contado, sin forzarlo
                try:
                    if self.cmb_estado.get() == "" or self.cmb_estado.get() == "Confirmada":
                        self.cmb_estado.set("Pagada")
                    if hasattr(self, "cmb_pago") and not self.cmb_pago.get():
                        self.cmb_pago.set("Contado")
                except Exception:
                    pass
                self.after(10, self._focus_scan)
            else:
                self._cashier_frame.pack_forget()
        except Exception:
            pass

    def _focus_scan(self) -> None:
        try:
            self.ent_scan.focus_set()
            self.ent_scan.select_range(0, "end")
        except Exception:
            pass

    def _on_scan_enter(self) -> None:
        code = (self.ent_scan.get() or "").strip()
        if not code:
            return
        try:
            p = self.repo_prod.get_by_sku(code)
            if not p:
                self._warn(f"SKU no encontrado: {code}")
                self._focus_scan()
                return
            # Precio base desde producto; si no existe, usar 0 (con validación más abajo)
            price = D(getattr(p, "precio_venta", 0) or 0)
            if price <= 0:
                self._warn(f"El producto '{p.nombre}' no tiene precio de venta definido.")
                self._focus_scan()
                return

            # ¿Ya existe en la tabla? -> incrementa cantidad
            iid_found = None
            for iid in self.tree.get_children():
                try:
                    if str(self.tree.item(iid, "values")[0]) == str(p.id):
                        iid_found = iid
                        break
                except Exception:
                    pass

            if iid_found:
                vals = list(self.tree.item(iid_found, "values"))
                try:
                    qty = int(float(vals[2])) + 1
                except Exception:
                    qty = 1
                try:
                    unit_price = D(vals[3])
                except Exception:
                    unit_price = price
                disc_pct = 0.0
                subtotal = fmt_2(q2(D(qty) * q2(unit_price)))
                self.tree.item(iid_found, values=(p.id, p.nombre, qty, fmt_2(unit_price), f"{disc_pct:.1f}", subtotal))
            else:
                qty = 1
                disc_pct = 0.0
                subtotal = fmt_2(q2(D(qty) * q2(price)))
                self.tree.insert("", "end", values=(p.id, p.nombre, qty, fmt_2(price), f"{disc_pct:.1f}", subtotal))

            self._update_total()
        finally:
            # Limpiar y volver a enfocar
            try:
                self.ent_scan.delete(0, "end")
                self._focus_scan()
            except Exception:
                pass

    def _on_quick_checkout(self) -> None:
        """Confirma venta como 'Pagada' y genera boleta PDF (Descargas).
        Requiere cliente seleccionado.
        """
        try:
            # 1) Tomar snapshot de ítems y cliente
            items = self._collect_items()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return
            cust = self._get_selected_customer()
            if not cust:
                self._warn("Seleccione un cliente.")
                return

            # 2) Construir items para SalesManager
            sm_items = [
                SaleItem(product_id=it["id"], cantidad=it["cantidad"], precio_unitario=it["precio"])
                for it in items
            ]

            # 3) Crear venta como 'Pagada'
            estado = "Pagada"
            apply_to_stock = self.var_apply.get()  # Pagada descuenta stock si está activo
            create_fn = self._resolve_create_sale()
            sale = create_fn(
                customer_id=cust.id,
                items=sm_items,
                estado=estado,
                apply_to_stock=apply_to_stock,
            )

            # 4) Generar Boleta POS (ticket 80mm) en Descargas
            try:
                from datetime import datetime
                from src.reports.pos_receipt import generate_pos_ticket_to_downloads

                row_items = []
                for it in items:
                    # Intentar SKU (código) para mostrar
                    try:
                        pid = int(it["id"])  # para buscar SKU
                        p = self.repo_prod.get(pid)
                        sku = getattr(p, "sku", "") if p else ""
                    except Exception:
                        sku = ""
                    row_items.append({
                        "codigo": sku,
                        "descripcion": it["nombre"],
                        "cantidad": it["cantidad"],
                        "precio": float(it["precio"]),
                        "subtotal": float(it["subtotal"]),
                    })

                sale_dt = getattr(sale, "fecha_venta", None) or datetime.now()
                folio = f"VENTA-{getattr(sale, 'id', '')}"
                # Estructura de cliente compacta para el ticket
                cust_min = {
                    "id": getattr(cust, "id", None),
                    "razon_social": getattr(cust, "razon_social", "") or "",
                    "rut": getattr(cust, "rut", "") or "",
                }
                pago = None
                try:
                    pago = self.cmb_pago.get()
                except Exception:
                    pago = None

                out = generate_pos_ticket_to_downloads(
                    folio=folio,
                    fecha=sale_dt,
                    customer=cust_min,
                    items=row_items,
                    payment=pago,
                    width_mm=80.0,
                    iva_percent=19.0,
                    auto_open=True,
                )
                self._info(f"Venta registrada y boleta generada:\n{out}")
            except Exception:
                # Si el PDF falla, al menos informar venta creada
                self._info("Venta registrada (Pagada). No se pudo generar la boleta.")

            # 5) Limpiar UI
            self._on_clear_table()
        except Exception as e:
            self._error(f"No se pudo finalizar la venta:\n{e}")

    # -------------------- Lookups --------------------
    def refresh_lookups(self):
        """Carga clientes y productos en los combos y autocompletados.
        Tolerante: si los widgets aún no existen (llamado temprano desde pestañas), sale.
        """
        # Protección ante llamadas tempranas desde MainWindow._on_tab_change
        if not hasattr(self, "cmb_customer") or not hasattr(self, "cmb_product"):
            return
        self.customers = self.session.query(Customer)\
            .order_by(Customer.razon_social.asc()).all()
        self.cmb_customer["values"] = [self._display_customer(c) for c in self.customers]
        if self.customers and not self.cmb_customer.get():
            self.cmb_customer.current(0)

        self.products = self.session.query(Product).order_by(Product.nombre.asc()).all()

        def _disp(p: Product) -> str:
            sku = getattr(p, "sku", "") or ""
            return f"{p.id} - {p.nombre}" + (f" [{sku}]" if sku else "")

        def _keys(p: Product):
            return [
                str(getattr(p, "id", "")),
                str(getattr(p, "nombre", "") or getattr(p, "name", "")),
                str(getattr(p, "sku", "") or getattr(p, "codigo", "") or getattr(p, "code", "")),
            ]

        self.cmb_product.set_dataset(self.products, keyfunc=_disp, searchkeys=_keys)

        if hasattr(self, "flt_customer"):
            def _c_disp(c: Customer) -> str:
                rut = getattr(c, "rut", "") or ""
                rs = getattr(c, "razon_social", "") or getattr(c, "nombre", "") or ""
                head = rs or rut or f"Cliente {getattr(c, 'id', '')}"
                return f"{head}" + (f" [{rut}]" if rut and rut not in head else "")

            def _c_keys(c: Customer):
                return [
                    str(getattr(c, "id", "")),
                    str(getattr(c, "razon_social", "") or getattr(c, "nombre", "")),
                    str(getattr(c, "rut", "")),
                    str(getattr(c, "email", "")),
                    str(getattr(c, "telefono", "")),
                ]
            self.flt_customer.set_dataset(self.customers, keyfunc=_c_disp, searchkeys=_c_keys)

        if hasattr(self, "flt_product"):
            self.flt_product.set_dataset(self.products, keyfunc=_disp, searchkeys=_keys)

        self._fill_price_from_selected_product()

    def _display_customer(self, c: Customer) -> str:
        rut = getattr(c, "rut", "") or ""
        rs = getattr(c, "razon_social", "") or ""
        if rut and rs:
            return f"{rs} — {rut}"
        return rs or rut or f"Cliente {getattr(c, 'id', '')}"

    def _get_selected_customer(self) -> Optional[Customer]:
        idx = self.cmb_customer.current()
        if idx is None or idx < 0:
            return None
        return self.customers[idx]

    # -------------------- Selección de producto --------------------
    def _selected_product(self) -> Optional[Product]:
        it = self.cmb_product.get_selected_item()
        if it is not None:
            return it
        try:
            idx = self.cmb_product.current()
        except Exception:
            idx = -1
        if idx is not None and 0 <= idx < len(self.products):
            return self.products[idx]
        return None

    # -------------------- UI helpers --------------------
    def _on_product_change(self, _evt=None):
        self._fill_price_from_selected_product()
        # Completar campos de detalle ampliado
        try:
            p = self._selected_product()
            if p:
                self.var_prod_code.set(getattr(p, 'sku', '') or '')
                self.var_prod_desc.set(getattr(p, 'nombre', '') or '')
                unidad = getattr(p, 'unidad_medida', None) or 'Unidades'
                self.var_unidad.set(unidad)
                # Recalcular neto con el nuevo precio seleccionado
                self._recalc_net()
        except Exception:
            pass

    def _fill_price_from_selected_product(self):
        p = self._selected_product()
        if not p:
            return
        try:
            pv = D(getattr(p, "precio_venta", 0) or 0)
            if pv > 0:
                self.ent_price.delete(0, "end")
                self.ent_price.insert(0, fmt_2(pv))
        except Exception:
            pass

    # -------------------- Ãtems --------------------
    def _on_add_item(self):
        """Agrega un ítem validando duplicados y valores."""
        try:
            p = self._selected_product()
            if not p:
                self._warn("Seleccione un producto.")
                return

            # Cantidad (entera para stock)
            try:
                qty = int(float(self.ent_qty.get()))
            except Exception:
                self._warn("Cantidad inválida.")
                return
            if qty <= 0:
                self._warn("La cantidad debe ser > 0.")
                return

            # Precio: si no se indicó, usar precio_venta del producto
            try:
                price = D(self.ent_price.get())
            except Exception:
                price = D(0)
            if price <= 0:
                price = D(getattr(p, "precio_venta", 0) or 0)
            if price <= 0:
                self._warn("Ingrese un precio válido (> 0).")
                return

            # Descuento: por monto o porcentaje
            try:
                desc_val = float(self.var_desc_val.get() or 0)
            except Exception:
                desc_val = 0.0
            desc_tipo = (self.var_desc_tipo.get() or 'Monto').strip()
            disc = 0.0  # porcentaje equivalente para la columna
            eff_price = D(price)
            if desc_tipo == 'Monto':
                eff_price = q2(D(price) - D(desc_val))
                if D(price) > 0:
                    disc = max(0.0, float((D(desc_val) / D(price)) * 100))
            else:
                disc = max(0.0, min(100.0, float(desc_val)))
                eff_price = q2(D(price) * D(1 - disc/100))

            # Evita duplicados
            for iid in self.tree.get_children():
                if str(p.id) == str(self.tree.item(iid, "values")[0]):
                    self._warn("Este producto ya está en la tabla.")
                    return

            subtotal = q2(D(qty) * eff_price)
            self.tree.insert("", "end",
                             values=(p.id, p.nombre, qty, fmt_2(price), f"{disc:.1f}", fmt_2(subtotal)))
            self._update_total()

            self.ent_qty.delete(0, "end"); self.ent_qty.insert(0, "1")
            self._fill_price_from_selected_product()
            # limpiar descuento avanzado
            try:
                self.var_desc_val.set(0.0)
            except Exception:
                pass
            self.cmb_product.set("")
            self.cmb_product.focus_set()

            # Actualizar número de detalle sugerido
            try:
                self.var_det_nro.set(str(len(self.tree.get_children()) + 1))
            except Exception:
                pass

        except Exception as e:
            self._error(f"No se pudo agregar el ítem:\n{e}")

    def _on_delete_item(self):
        for item in self.tree.selection():
            self.tree.delete(item)
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

    # ---- Calcular neto unitario desde precio + tipo de descuento ----
    def _recalc_net(self):
        try:
            price = float(self.ent_price.get() or 0)
            desc_tipo = (self.var_desc_tipo.get() or 'Monto').strip()
            desc_val = float(self.var_desc_val.get() or 0)
            neto = price
            pct = 0.0
            if desc_tipo == 'Monto':
                neto = max(0.0, price - desc_val)
                if price > 0:
                    pct = max(0.0, min(100.0, (desc_val / price) * 100.0))
            else:
                pct = max(0.0, min(100.0, desc_val))
                neto = max(0.0, price * (1 - pct/100.0))
            self.var_monto_neto.set(float(q2(D(neto))))
            # La columna Dcto % en la tabla se calcula al agregar el ítem.
        except Exception:
            pass

    # -------------------- Scroll wheel --------------------
    def _on_mousewheel(self, event):
        try:
            if event.delta:
                # Windows / macOS
                self.tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                # Linux (Button-4/5)
                if event.num == 4:
                    self.tree.yview_scroll(-1, "units")
                elif event.num == 5:
                    self.tree.yview_scroll(1, "units")
        except Exception:
            pass
        return "break"

    def _collect_items(self) -> List[dict]:
        items: List[dict] = []
        for iid in self.tree.get_children():
            prod_id, name, qty, price, disc, sub = self.tree.item(iid, "values")
            items.append({
                "id": int(prod_id),
                "nombre": str(name),
                "cantidad": int(float(qty)),
                # precio efectivo con descuento
                "precio": q2(D(price)),
                "descuento_porcentaje": float(disc or 0),
                "subtotal": D(sub),
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
        for name in ("create_sale", "create", "register_sale", "add_sale"):
            if hasattr(self.sm, name):
                return getattr(self.sm, name)
        raise AttributeError("SalesManager no expone un método para crear ventas (create_sale/create/...)")

    def _on_confirm_sale(self):
        try:
            items = self._collect_items()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return
            cust = self._get_selected_customer()
            if not cust:
                self._warn("Seleccione un cliente.")
                return

            sm_items = [
                SaleItem(product_id=it["id"], cantidad=it["cantidad"], precio_unitario=it["precio"])
                for it in items
            ]

            estado = (self.cmb_estado.get() or "Confirmada").strip()
            # Descontar stock solo si está Confirmada o Pagada (compatibilidad)
            apply_to_stock = self.var_apply.get() and (estado in ("Confirmada", "Pagada"))

            create_fn = self._resolve_create_sale()
            create_fn(
                customer_id=cust.id,
                items=sm_items,
                estado=estado,
                apply_to_stock=apply_to_stock,
            )

            self._on_clear_table()
            self._info(f"Venta registrada ({estado}).")
        except Exception as e:
            self._error(f"No se pudo confirmar la venta:\n{e}")

    def _on_generate_so_downloads(self):
        try:
            items = self._collect_items()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return
            cust = self._get_selected_customer_dict()
            try:
                cust["pago"] = self.cmb_pago.get()
            except Exception:
                pass
            so_number = f"OV-{cust['id']}-{self._stamp()}"
            out = generate_so_to_downloads(
                so_number=so_number,
                customer=cust,
                items=items,
                currency="CLP",
                notes=None,
                auto_open=True,
            )
            self._info(f"Orden de Venta creada en Descargas:\n{out}")
        except Exception as e:
            self._error(f"No se pudo generar la OV:\n{e}")

    def _on_generate_sales_quote(self):
        try:
            items = self._collect_items()
            if not items:
                self._warn("Agregue al menos un ítem.")
                return
            cust = self._get_selected_customer_dict()
            cust.setdefault("nombre", cust.get("razon_social") or "")
            try:
                cust["pago"] = self.cmb_pago.get()
            except Exception:
                pass
            quote_number = f"COTV-{cust.get('id','')}-{self._stamp()}"
            out = generate_quote_to_downloads(
                quote_number=quote_number,
                supplier=cust,
                items=items,
                currency="CLP",
                notes=None,
                auto_open=True,
            )
            self._info(f"Cotización de venta creada en Descargas:\n{out}")
        except Exception as e:
            self._error(f"No se pudo generar la cotización:\n{e}")

    def _on_cancel_sale(self):
        try:
            sid = int(self.ent_sale_id.get())
            self.sm.cancel_sale(sid, revert_stock=True)
            self._info(f"Venta {sid} cancelada.")
        except Exception as e:
            self._error(f"No se pudo cancelar:\n{e}")

    def _on_delete_sale(self):
        try:
            sid = int(self.ent_sale_id.get())
            if not messagebox.askyesno("Confirmar", f"¿Marcar venta {sid} como Eliminada? Se revertirá stock si corresponde."):
                return
            self.sm.delete_sale(sid, revert_stock=True)
            self._info(f"Venta {sid} marcada como Eliminada.")
        except Exception as e:
            self._error(f"No se pudo eliminar:\n{e}")

    # ==================== Informe de Ventas (Lógica) ====================
    @staticmethod
    def _parse_ddmmyyyy(s: str):
        from datetime import datetime as _dt
        s = (s or "").strip()
        return _dt.strptime(s, "%d/%m/%Y").date()

    @staticmethod
    def _downloads_dir():
        from pathlib import Path
        home = Path.home()
        for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
            p = home / cand
            if p.exists():
                return p
        return home

    def _selected_filter_customer(self) -> Optional[Customer]:
        return getattr(self.flt_customer, "get_selected_item", lambda: None)()

    def _selected_filter_product(self) -> Optional[Product]:
        return getattr(self.flt_product, "get_selected_item", lambda: None)()

    def _query_sales_between(self, d_from, d_to,
                             customer_id: Optional[int],
                             product_id: Optional[int],
                             estado: Optional[str],
                             total_min: Optional[float],
                             total_max: Optional[float]):
        import sqlalchemy
        from datetime import datetime
        from sqlalchemy import and_
        from src.data.models import Sale, SaleDetail

        start_dt = datetime.combine(d_from, datetime.min.time())
        end_dt = datetime.combine(d_to, datetime.max.time())

        q = self.session.query(Sale).filter(
            and_(getattr(Sale, "fecha_venta") >= start_dt,
                 getattr(Sale, "fecha_venta") <= end_dt)
        )

        if estado:
            q = q.filter(getattr(Sale, "estado") == estado)

        if total_min is not None:
            q = q.filter(getattr(Sale, "total_venta") >= float(total_min))
        if total_max is not None:
            q = q.filter(getattr(Sale, "total_venta") <= float(total_max))

        if customer_id:
            if hasattr(Sale, "id_cliente"):
                q = q.filter(getattr(Sale, "id_cliente") == int(customer_id))
            elif hasattr(Sale, "customer_id"):
                q = q.filter(getattr(Sale, "customer_id") == int(customer_id))

        if product_id:
            q = q.join(SaleDetail, getattr(SaleDetail, "id_venta") == getattr(Sale, "id")) \
                 .filter(getattr(SaleDetail, "id_producto") == int(product_id))

        q = q.order_by(getattr(Sale, "fecha_venta").asc())

        rows = []
        for s in q.all():
            fecha = getattr(s, "fecha_venta", None)
            total = getattr(s, "total_venta", None)
            est = getattr(s, "estado", None) or ""
            cliente = ""
            cust_obj = getattr(s, "customer", None)
            if cust_obj is not None:
                cliente = getattr(cust_obj, "razon_social", None) or getattr(cust_obj, "nombre", None) or f"Cliente {getattr(cust_obj, 'id', '')}"
            else:
                cliente = getattr(s, "cliente_nombre", None) or ""
            rows.append({
                "id": getattr(s, "id", None),
                "fecha": fecha,
                "cliente": cliente,
                "estado": est,
                "total": float(total or 0.0),
            })
        return rows

    def _open_sales_report_window(self, rows):
        win = tk.Toplevel(self)
        win.title("Informe de ventas")
        win.geometry("860x480")

        cols = ("id", "fecha", "cliente", "estado", "total")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=16)
        for cid, text, w, anchor in [
            ("id", "ID", 70, "center"),
            ("fecha", "Fecha", 160, "center"),
            ("cliente", "Cliente", 350, "w"),
            ("estado", "Estado", 120, "center"),
            ("total", "Total", 120, "e"),
        ]:
            tree.heading(cid, text=text)
            tree.column(cid, width=w, anchor=anchor)

        vsb = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
        tree.configure(yscroll=vsb.set)
        tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        vsb.pack(side="left", fill="y", pady=8)

        # Habilitar ordenamiento por encabezado
        try:
            from src.gui.treeview_utils import enable_treeview_sort
            enable_treeview_sort(tree)
        except Exception:
            pass

        total_general = 0.0
        for r in rows:
            if str(r.get("estado", "")).strip().lower() == "eliminada":
                continue
            f = r.get("fecha")
            if hasattr(f, "strftime"):
                fecha_txt = f.strftime("%d/%m/%Y %H:%M") if hasattr(f, "hour") else f.strftime("%d/%m/%Y")
            else:
                fecha_txt = str(f or "")
            total_general += float(r.get("total", 0.0))
            tree.insert("", "end", values=(
                r.get("id", ""),
                fecha_txt,
                r.get("cliente", "") or "",
                r.get("estado", "") or "",
                self._fmt_clp(r.get('total', 0.0)),
            ))

        bottom = ttk.Frame(win); bottom.pack(fill="x", padx=8, pady=(0, 8))
        lbl = ttk.Label(bottom, text=f"Total general: {self._fmt_clp(total_general)}", font=("", 11, "bold"))
        lbl.pack(side="left")

        def _export_csv():
            import csv
            from datetime import datetime as _dt
            out_dir = self._downloads_dir()
            out_dir.mkdir(parents=True, exist_ok=True)
            fname = f"informe_ventas_{_dt.now().strftime('%Y%m%d-%H%M%S')}.csv"
            out_path = out_dir / fname
            with open(out_path, "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f, delimiter=";")
                w.writerow(["ID", "Fecha", "Cliente", "Estado", "Total"])
                for r in rows:
                    if str(r.get("estado", "")).strip().lower() == "eliminada":
                        continue
                    fval = r["fecha"]
                    ftxt = fval.strftime("%d/%m/%Y %H:%M") if hasattr(fval, "strftime") else str(fval or "")
                    # Para CSV, dejamos valor entero en pesos (sin separadores)
                    try:
                        tot_i = int(round(float(r['total'] or 0)))
                    except Exception:
                        tot_i = 0
                    w.writerow([r["id"], ftxt, r["cliente"], r["estado"], str(tot_i)])
            self._info(f"CSV guardado en Descargas:\n{out_path}")

        def _export_pdf():
            filtro_cliente = ""
            sel_c = getattr(self.flt_customer, "get_selected_item", lambda: None)()
            if sel_c:
                filtro_cliente = getattr(sel_c, "razon_social", None) or getattr(sel_c, "nombre", None) or f"Cliente {getattr(sel_c, 'id', '')}"

            filtro_producto = ""
            sel_p = getattr(self.flt_product, "get_selected_item", lambda: None)()
            if sel_p:
                filtro_producto = getattr(sel_p, "nombre", None) or f"Producto {getattr(sel_p, 'id', '')}"

            filters = {
                "Cliente": filtro_cliente or "Todos",
                "Producto": filtro_producto or "Todos",
                "Estado": (self.flt_estado.get() or "").strip() or "Todos",
                "Total ≥": self.flt_total_min.get() or "-",
                "Total ≤": self.flt_total_max.get() or "-",
            }

            date_from = self.ent_from.get().strip()
            date_to = self.ent_to.get().strip()

            filtered_rows = [r for r in rows if str(r.get("estado", "")).strip().lower() != "eliminada"]

            out = generate_sales_report_to_downloads(
                rows=filtered_rows,
                date_from=date_from,
                date_to=date_to,
                filters=filters,
                auto_open=True,
            )
            self._info(f"Informe PDF guardado en Descargas:\n{out}")

        ttk.Button(bottom, text="Exportar CSV (Descargas)", command=_export_csv).pack(side="right")
        ttk.Button(bottom, text="Exportar PDF (Descargas)", command=_export_pdf).pack(side="right", padx=6)

    def _on_generate_sales_report(self):
        try:
            if not self.ent_from.get().strip() or not self.ent_to.get().strip():
                self._warn("Ingrese ambas fechas en formato dd/mm/aaaa.")
                return
            d_from = self._parse_ddmmyyyy(self.ent_from.get())
            d_to = self._parse_ddmmyyyy(self.ent_to.get())
            if d_from > d_to:
                self._warn("La fecha 'Desde' no puede ser mayor que 'Hasta'.")
                return

            cust = self._selected_filter_customer()
            prod = self._selected_filter_product()
            estado = (self.flt_estado.get() or "").strip() or None

            def _float_or_none(s: str):
                s = (s or "").strip().replace(".", "").replace(",", ".")
                if not s:
                    return None
                try:
                    return float(s)
                except Exception:
                    return None

            tmin = _float_or_none(self.flt_total_min.get())
            tmax = _float_or_none(self.flt_total_max.get())

            rows = self._query_sales_between(
                d_from, d_to,
                customer_id=(cust.id if cust else None),
                product_id=(prod.id if prod else None),
                estado=estado,
                total_min=tmin,
                total_max=tmax,
            )

            if not rows:
                self._info("No hay ventas con los filtros indicados.")
                return

            self._open_sales_report_window(rows)

        except ValueError:
            self._error("Use el formato dd/mm/aaaa (ej: 07/09/2025).")
        except Exception as e:
            self._error(f"No se pudo generar el informe:\n{e}")

    # -------------------- Mensajes --------------------
    def _warn(self, msg: str):
        messagebox.showwarning("Validación", msg)

    def _error(self, msg: str):
        messagebox.showerror("Error", msg)

    def _info(self, msg: str):
        messagebox.showinfo("OK", msg)

    @staticmethod
    def _stamp() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d-%H%M%S")


# src/gui/orders_admin_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Callable

from src.data.database import get_session
from src.data.models import (
    Supplier, Customer, Product,
    Purchase, PurchaseDetail,
    Sale, SaleDetail,
    Reception,
)
from src.core.inventory_manager import InventoryManager
from src.core.purchase_manager import PurchaseManager
from src.core.sales_manager import SalesManager
from src.utils.po_generator import generate_po_to_downloads
from src.utils.so_generator import generate_so_to_downloads

# Grilla tipo hoja (tksheet si estÃ¡ instalado; si no, Treeview)
from src.gui.widgets.grid_table import GridTable


class OrdersAdminView(ttk.Frame):
    """
    Administra Ã“rdenes de Compra y Ã“rdenes de Venta:
    - Listado de OC/OV con estado
    - Ver detalle (Ã­tems)
    - Marcar Confirmada/Completada (ajusta stock)
    - Cancelar / Eliminar (revierte stock si corresponde)
    """

    # ----- Columnas (titulos + anchos) -----
    PUR_COLS = ["ID", "N° OC", "Fecha", "Proveedor", "Estado", "Total", "Docs"]
    PUR_W    = [70, 110, 130, 260, 120, 120, 220]

    PUR_DET_COLS = ["ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]
    PUR_DET_W    = [80, 320, 80, 110, 130]

    SALE_COLS = ["ID", "Fecha", "Cliente", "Estado", "Total"]
    SALE_W    = [70, 130, 280, 120, 120]

    SALE_DET_COLS = ["ID Prod", "Producto", "Cant.", "Precio", "Subtotal"]
    SALE_DET_W    = [80, 320, 80, 110, 130]

    # Recepciones (vinculaciones OC ← documento de proveedor)
    RECV_COLS = ["ID", "N° OC", "Proveedor", "Tipo", "N° doc", "Fecha", "Estado OC", "Total OC"]
    RECV_W    = [70, 110, 260, 90, 130, 140, 120, 120]
    RECV_DET_COLS = ["ID Prod", "Producto", "Recibido", "Ubicación", "Lote/Serie", "Vence"]
    RECV_DET_W    = [80, 300, 90, 150, 150, 110]

    @staticmethod
    def _fmt_clp(value) -> str:
        """Formatea moneda CLP con miles y sin decimales (p.ej., $6.854.400)."""
        try:
            n = float(value or 0)
            s = f"${n:,.0f}"
            return s.replace(",", ".")
        except Exception:
            return f"$ {value}"

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.session = get_session()
        self.inventory = InventoryManager(self.session)
        self.pm = PurchaseManager(self.session)
        self.sm = SalesManager(self.session)

        # Mapeos fila -> id (para selecciÃ³n)
        self._pur_ids: List[int] = []
        self._sale_ids: List[int] = []

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self._nb = nb

        # --- TAB TODAS (Resumen de todas las órdenes) ---
        self.tab_all = ttk.Frame(nb, padding=8)
        nb.add(self.tab_all, text="Todas")
        self._init_all_tab(self.tab_all)

        # --- TAB COMPRAS ---
        self.tab_compra = ttk.Frame(nb, padding=8)
        nb.add(self.tab_compra, text="Compras")
        self._init_purchase_tab(self.tab_compra)

        # --- TAB VENTAS ---
        self.tab_venta = ttk.Frame(nb, padding=8)
        nb.add(self.tab_venta, text="Ventas")
        self._init_sales_tab(self.tab_venta)

        # --- TAB RECEPCIONES ---
        self.tab_recv = ttk.Frame(nb, padding=8)
        nb.add(self.tab_recv, text="Recepciones")
        self._init_receptions_tab(self.tab_recv)

        # carga inicial
        self._refresh_filter_lookups()
        self._load_purchases()
        self._load_sales()
        self._load_receptions()
        self._load_all()

    # =================== Inicialización pestaña TODAS ================== #
    ALL_COLS = ["Tipo", "ID", "Fecha", "Tercero", "Estado", "Total", "Ref"]
    ALL_W    = [90, 70, 130, 280, 120, 120, 200]

    def _init_all_tab(self, parent):
        top = ttk.Frame(parent); top.pack(fill="x")
        ttk.Button(top, text="Actualizar", command=self._load_all).pack(side="left", padx=4)

        self.tbl_all = GridTable(parent, height=12)
        self.tbl_all.pack(fill="both", expand=True, pady=(6, 4))
        if hasattr(self.tbl_all, "sheet"):
            try:
                self.tbl_all.sheet.extra_bindings([("double_click", lambda e: self._on_all_open())])
            except Exception:
                pass
        tv = getattr(self.tbl_all, "_fallback", None)
        if tv is not None:
            tv.bind("<Double-1>", lambda _e: self._on_all_open())

        self._all_rows_meta: List[tuple[str, int]] = []  # (tipo, id)
        self._set_table_data(self.tbl_all, self.ALL_COLS, self.ALL_W, [])

    def _load_all(self):
        rows: List[List] = []
        self._all_rows_meta = []
        # Compras
        q_p = (
            self.session.query(Purchase, Supplier)
            .join(Supplier, Supplier.id == Purchase.id_proveedor)
            .order_by(Purchase.id.desc())
        )
        for pur, sup in q_p:
            rows.append([
                "Compra",
                pur.id,
                pur.fecha_compra.strftime("%Y-%m-%d %H:%M") if getattr(pur, 'fecha_compra', None) else "",
                getattr(sup, 'razon_social', '') or '',
                getattr(pur, 'estado', '') or '',
                self._fmt_clp(getattr(pur,'total_compra',0) or 0),
                getattr(pur, 'referencia', '') or '',
            ])
            self._all_rows_meta.append(("compra", int(pur.id)))
        # Ventas
        q_s = (
            self.session.query(Sale, Customer)
            .join(Customer, Customer.id == Sale.id_cliente, isouter=True)
            .order_by(Sale.id.desc())
        )
        for sale, cust in q_s:
            rows.append([
                "Venta",
                sale.id,
                sale.fecha_venta.strftime("%Y-%m-%d %H:%M") if getattr(sale, 'fecha_venta', None) else "",
                getattr(cust, 'razon_social', '') or getattr(cust, 'rut', '') or '',
                getattr(sale, 'estado', '') or '',
                self._fmt_clp(getattr(sale,'total_venta',0) or 0),
                "",
            ])
            self._all_rows_meta.append(("venta", int(sale.id)))
        # Recepciones (se muestran como vínculos de OC)
        q_r = (
            self.session.query(Reception, Purchase, Supplier)
            .join(Purchase, Purchase.id == Reception.id_compra)
            .join(Supplier, Supplier.id == Purchase.id_proveedor)
            .order_by(Reception.id.desc())
        )
        for rec, pur, sup in q_r:
            ref = f"{getattr(rec,'tipo_doc','') or ''} {getattr(rec,'numero_documento','') or ''}".strip()
            rows.append([
                "Recepción",
                rec.id,
                rec.fecha.strftime("%Y-%m-%d %H:%M") if getattr(rec, 'fecha', None) else "",
                getattr(sup, 'razon_social', '') or '',
                getattr(pur, 'estado', '') or '',
                self._fmt_clp(getattr(pur,'total_compra',0) or 0),
                f"OC-{pur.id} {ref}".strip(),
            ])
            self._all_rows_meta.append(("recepcion", int(rec.id)))

        # Opcional: ordenar por fecha descendente (requiere parse)
        try:
            rows.sort(key=lambda r: r[2], reverse=True)
        except Exception:
            pass
        self._set_table_data(self.tbl_all, self.ALL_COLS, self.ALL_W, rows)

    def _on_all_open(self):
        idx = self._selected_row_index(self.tbl_all)
        if idx is None or idx < 0 or idx >= len(self._all_rows_meta):
            return
        tipo, idv = self._all_rows_meta[idx]
        # Navega a la pestaña correspondiente y selecciona
        # Simpler approach: switch tab by calling MainWindow controls is not accessible here.
        # We just switch within this Notebook to the specific tab and load details.
        try:
            nb = getattr(self, '_nb', None)
            if nb is None:
                return
            if tipo == "compra":
                nb.select(self.tab_compra)
                # Select row matching purchase id
                self._select_row_by_id(self.tbl_pur, self._pur_ids, idv)
                self._load_purchase_details(idv)
            elif tipo == "venta":
                nb.select(self.tab_venta)
                self._select_row_by_id(self.tbl_sale, self._sale_ids, idv)
                self._on_sale_selected()
            elif tipo == "recepcion":
                nb.select(self.tab_recv)
                # Select row by reception id
                self._select_reception_row(idv)
                self._on_reception_selected()
        except Exception:
            pass

    def _select_row_by_id(self, table: GridTable, ids: List[int], target_id: int) -> None:
        tv = getattr(table, "_fallback", None)
        if tv is None:
            return
        for iid in tv.get_children(""):
            try:
                vals = list(tv.item(iid, "values"))
                if vals and int(vals[0]) == int(target_id):
                    tv.selection_set(iid)
                    tv.see(iid)
                    break
            except Exception:
                continue

    def _select_reception_row(self, rid: int) -> None:
        tv = getattr(self.tbl_recv, "_fallback", None)
        if tv is None:
            return
        for iid in tv.get_children(""):
            try:
                vals = list(tv.item(iid, "values"))
                if vals and int(vals[0]) == int(rid):
                    tv.selection_set(iid)
                    tv.see(iid)
                    break
            except Exception:
                continue

    # ----------------- Utilidades de grilla -----------------
    def _apply_col_widths(self, table: GridTable, widths: List[int]) -> None:
        """Ajusta anchos en tksheet y en fallback Treeview."""
        if hasattr(table, "sheet"):
            try:
                for i, w in enumerate(widths):
                    table.sheet.column_width(i, width=w)
            except Exception:
                pass
        tv = getattr(table, "_fallback", None)
        if tv is not None:
            cols = list(tv["columns"]) if tv["columns"] else []
            for i, c in enumerate(cols):
                tv.heading(c, text=str(c), anchor="center")
                tv.column(c, width=widths[i] if i < len(widths) else 120, anchor="center")
            try:
                from src.gui.treeview_utils import enable_treeview_sort
                enable_treeview_sort(tv)
            except Exception:
                pass

    def _set_table_data(self, table: GridTable, cols: List[str], widths: List[int], rows: List[List]) -> None:
        table.set_data(cols, rows)
        self._apply_col_widths(table, widths)

    def _selected_row_index(self, table: GridTable) -> Optional[int]:
        """Ãndice de fila seleccionada (o None)."""
        if hasattr(table, "sheet"):
            try:
                rows = list(table.sheet.get_selected_rows())
                if rows:
                    return sorted(rows)[0]
                cells = table.sheet.get_selected_cells()
                if cells:
                    return sorted({r for r, _ in cells})[0]
            except Exception:
                return None
            return None
        tv = getattr(table, "_fallback", None)
        if tv is None:
            return None
        sel = tv.selection()
        if not sel:
            return None
        try:
            return tv.index(sel[0])
        except Exception:
            return None

    # ----------- Utilidades DB + feedback ----------- #
    def _handle_db_action(self, action: Callable, success_msg: str, reload_func: Callable):
        try:
            action()
            self.session.commit()
            reload_func()
            messagebox.showinfo("Ã‰xito", success_msg)
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"OcurriÃ³ un error:\n{e}")

    # ================== InicializaciÃ³n pestaÃ±a COMPRAS ================== #
    def _init_purchase_tab(self, parent):
        top_c = ttk.Frame(parent); top_c.pack(fill="x")
        ttk.Button(top_c, text="Actualizar", command=self._load_purchases).pack(side="left", padx=4)
        ttk.Button(top_c, text="Marcar COMPLETADA (sumar stock)", command=self._purchase_mark_completed).pack(side="left", padx=4)
        ttk.Button(top_c, text="Cancelar (reversa si completada)", command=self._purchase_cancel).pack(side="left", padx=4)
        ttk.Button(top_c, text="Eliminar (reversa si completada)", command=self._purchase_delete).pack(side="left", padx=4)
        ttk.Button(top_c, text="Reimprimir OC (PDF)", command=self._purchase_print_pdf).pack(side="left", padx=4)
        ttk.Button(top_c, text="Vincular recepción…", command=self._purchase_link_reception).pack(side="left", padx=4)

        # Editor de estado (mÃ¡s directo)
        editor = ttk.Frame(parent); editor.pack(fill="x", pady=(6, 0))
        ttk.Label(editor, text="Estado:").pack(side="left")
        self.PUR_STATES = ("Pendiente", "Incompleta", "Por pagar", "Completada", "Cancelada", "Eliminada")
        self.pur_state_cb = ttk.Combobox(editor, state="readonly", width=14, values=self.PUR_STATES)
        self.pur_state_cb.pack(side="left", padx=4)
        ttk.Button(editor, text="Aplicar estado", command=self._purchase_apply_state).pack(side="left", padx=4)

        # Filtros: Proveedor + Estado
        fil_p = ttk.Frame(parent); fil_p.pack(fill="x", pady=(6, 0))
        ttk.Label(fil_p, text="Proveedor:").pack(side="left")
        self.pur_filter_supplier = ttk.Combobox(fil_p, state="readonly", width=40)
        self.pur_filter_supplier.pack(side="left", padx=4)
        ttk.Label(fil_p, text="Estado:").pack(side="left")
        self.pur_filter_state = ttk.Combobox(fil_p, state="readonly", width=14, values=("Todos", "Pendiente", "Incompleta", "Por pagar", "Completada", "Cancelada"))
        try:
            self.pur_filter_state.current(0)
        except Exception:
            pass
        self.pur_filter_state.pack(side="left", padx=4)
        ttk.Button(fil_p, text="Aplicar filtro", command=self._apply_purchase_filter).pack(side="left", padx=4)
        ttk.Button(fil_p, text="Limpiar", command=self._clear_purchase_filter).pack(side="left", padx=4)

        # Listado de compras
        self.tbl_pur = GridTable(parent, height=10)
        self.tbl_pur.pack(fill="both", expand=True, pady=(6, 4))
        # SelecciÃ³n (tksheet)
        if hasattr(self.tbl_pur, "sheet"):
            try:
                self.tbl_pur.sheet.extra_bindings([("cell_select", lambda e: self._on_purchase_selected())])
            except Exception:
                pass
        # SelecciÃ³n (fallback Treeview)
        tv = getattr(self.tbl_pur, "_fallback", None)
        if tv is not None:
            tv.bind("<<TreeviewSelect>>", lambda _e: self._on_purchase_selected())
            tv.bind("<Double-1>", lambda _e: self._on_purchase_selected())
            tv.bind("<ButtonRelease-1>", lambda _e: self._on_purchase_selected())

        # Detalle de compra
        self.tbl_pur_det = GridTable(parent, height=8)
        self.tbl_pur_det.pack(fill="both", expand=False)

        # Inicializa headers vacÃ­os
        self._set_table_data(self.tbl_pur, self.PUR_COLS, self.PUR_W, [])
        self._set_table_data(self.tbl_pur_det, self.PUR_DET_COLS, self.PUR_DET_W, [])

    # =================== InicializaciÃ³n pestaÃ±a VENTAS ================== #
    def _init_sales_tab(self, parent):
        top_v = ttk.Frame(parent); top_v.pack(fill="x")
        ttk.Button(top_v, text="Actualizar", command=self._load_sales).pack(side="left", padx=4)
        ttk.Button(top_v, text="Marcar CONFIRMADA (descontar stock)", command=self._sale_mark_confirmed).pack(side="left", padx=4)
        ttk.Button(top_v, text="Cancelar (reversa si confirmada)", command=self._sale_cancel).pack(side="left", padx=4)
        ttk.Button(top_v, text="Eliminar (reversa si confirmada)", command=self._sale_delete).pack(side="left", padx=4)
        ttk.Button(top_v, text="Reimprimir OV (PDF)", command=self._sale_print_pdf).pack(side="left", padx=4)

        # Editor de estado
        editor = ttk.Frame(parent); editor.pack(fill="x", pady=(6, 0))
        ttk.Label(editor, text="Estado:").pack(side="left")
        self.SALE_STATES = ("Reservada", "Confirmada", "Cancelada", "Eliminada")
        self.sale_state_cb = ttk.Combobox(editor, state="readonly", width=14, values=self.SALE_STATES)
        self.sale_state_cb.pack(side="left", padx=4)
        ttk.Button(editor, text="Aplicar estado", command=self._sale_apply_state).pack(side="left", padx=4)

        # Filtros: Cliente + Estado
        fil_s = ttk.Frame(parent); fil_s.pack(fill="x", pady=(6, 0))
        ttk.Label(fil_s, text="Cliente:").pack(side="left")
        self.sale_filter_customer = ttk.Combobox(fil_s, state="readonly", width=40)
        self.sale_filter_customer.pack(side="left", padx=4)
        ttk.Label(fil_s, text="Estado:").pack(side="left")
        self.sale_filter_state = ttk.Combobox(fil_s, state="readonly", width=14, values=("Todos", "Reservada", "Confirmada", "Cancelada", "Eliminada"))
        try:
            self.sale_filter_state.current(0)
        except Exception:
            pass
        self.sale_filter_state.pack(side="left", padx=4)
        ttk.Button(fil_s, text="Aplicar filtro", command=self._apply_sale_filter).pack(side="left", padx=4)
        ttk.Button(fil_s, text="Limpiar", command=self._clear_sale_filter).pack(side="left", padx=4)

        # Listado de ventas
        self.tbl_sale = GridTable(parent, height=10)
        self.tbl_sale.pack(fill="both", expand=True, pady=(6, 4))
        if hasattr(self.tbl_sale, "sheet"):
            try:
                self.tbl_sale.sheet.extra_bindings([("cell_select", lambda e: self._on_sale_selected())])
            except Exception:
                pass
        tv = getattr(self.tbl_sale, "_fallback", None)
        if tv is not None:
            tv.bind("<<TreeviewSelect>>", lambda _e: self._on_sale_selected())
            tv.bind("<Double-1>", lambda _e: self._on_sale_selected())
            tv.bind("<ButtonRelease-1>", lambda _e: self._on_sale_selected())

        # Detalle de venta
        self.tbl_sale_det = GridTable(parent, height=8)
        self.tbl_sale_det.pack(fill="both", expand=False)

        # Inicializa headers vacÃ­os
        self._set_table_data(self.tbl_sale, self.SALE_COLS, self.SALE_W, [])
        self._set_table_data(self.tbl_sale_det, self.SALE_DET_COLS, self.SALE_DET_W, [])

    # =================== Inicialización pestaña RECEPCIONES ================== #
    def _init_receptions_tab(self, parent):
        top = ttk.Frame(parent); top.pack(fill="x")
        ttk.Button(top, text="Actualizar", command=self._load_receptions).pack(side="left", padx=4)
        ttk.Button(top, text="Abrir en Compras", command=self._reception_open_in_purchases).pack(side="left", padx=4)
        ttk.Button(top, text="Reimprimir OC (PDF)", command=self._reception_print_po).pack(side="left", padx=4)
        ttk.Button(top, text="Informe de recepción (PDF)", command=self._reception_report_pdf).pack(side="left", padx=4)

        self.tbl_recv = GridTable(parent, height=10)
        self.tbl_recv.pack(fill="both", expand=True, pady=(6, 4))
        if hasattr(self.tbl_recv, "sheet"):
            try:
                self.tbl_recv.sheet.extra_bindings([("cell_select", lambda e: self._on_reception_selected())])
            except Exception:
                pass
        tv = getattr(self.tbl_recv, "_fallback", None)
        if tv is not None:
            tv.bind("<<TreeviewSelect>>", lambda _e: self._on_reception_selected())
            tv.bind("<Double-1>", lambda _e: self._on_reception_selected())
            tv.bind("<ButtonRelease-1>", lambda _e: self._on_reception_selected())

        self.tbl_recv_det = GridTable(parent, height=8)
        self.tbl_recv_det.pack(fill="both", expand=False)

        # Inicializa headers
        self._recv_ids: List[int] = []
        self._recv_to_purchase: dict[int, int] = {}
        self._set_table_data(self.tbl_recv, self.RECV_COLS, self.RECV_W, [])
        self._set_table_data(self.tbl_recv_det, self.RECV_DET_COLS, self.RECV_DET_W, [])

    # ============================= Compras ============================= #
    def _load_purchases(self):
        rows: List[List] = []
        self._pur_ids = []

        q = (
            self.session.query(Purchase, Supplier)
            .join(Supplier, Supplier.id == Purchase.id_proveedor)
            .order_by(Purchase.id.desc())
        )
        # Filtros activos
        try:
            idx = self.pur_filter_supplier.current()
            if idx is not None and idx > 0:
                sup = self._suppliers_cache[idx - 1]
                q = q.filter(Purchase.id_proveedor == sup.id)
        except Exception:
            pass
        try:
            st = (self.pur_filter_state.get() or "").strip()
            if st and st != "Todos":
                q = q.filter(Purchase.estado == st)
        except Exception:
            pass
        # Opcional: adjuntar números de documentos vinculados (Recepciones) por OC
        try:
            from src.data.models import Reception
        except Exception:
            Reception = None  # type: ignore

        for pur, sup in q:
            fecha = pur.fecha_compra.strftime("%Y-%m-%d %H:%M")
            proveedor = getattr(sup, "razon_social", "") or "-"
            docs = ""
            try:
                if Reception is not None:
                    doc_rows = (
                        self.session.query(Reception)
                        .filter(getattr(Reception, "id_compra") == pur.id)
                        .order_by(getattr(Reception, "id").desc())
                        .all()
                    )
                    parts = []
                    for r in doc_rows:
                        tipo = (getattr(r, "tipo_doc", "") or "").strip()
                        nro = (getattr(r, "numero_documento", "") or "").strip()
                        if tipo or nro:
                            parts.append(f"{tipo}:{nro}" if (tipo and nro) else (tipo or nro))
                    docs = ", ".join(parts)
            except Exception:
                docs = ""
            rows.append([pur.id, f"OC-{pur.id}", fecha, proveedor, pur.estado, self._fmt_clp(pur.total_compra), docs])
            self._pur_ids.append(int(pur.id))

        self._set_table_data(self.tbl_pur, self.PUR_COLS, self.PUR_W, rows)
        # Limpia detalle
        self._set_table_data(self.tbl_pur_det, self.PUR_DET_COLS, self.PUR_DET_W, [])

    # ============================= Recepciones ============================= #
    def _load_receptions(self):
        rows: List[List] = []
        self._recv_ids = []
        self._recv_to_purchase = {}

        q = (
            self.session.query(Reception, Purchase, Supplier)
            .join(Purchase, Purchase.id == Reception.id_compra)
            .join(Supplier, Supplier.id == Purchase.id_proveedor)
            .order_by(Reception.id.desc())
        )
        for r, pur, sup in q:
            oc = f"OC-{pur.id}"
            proveedor = getattr(sup, "razon_social", "") or "-"
            tipo = (getattr(r, "tipo_doc", "") or "").strip()
            numero = (getattr(r, "numero_documento", "") or "").strip()
            try:
                fecha = getattr(r, "fecha", None)
                fecha_s = fecha.strftime("%Y-%m-%d %H:%M") if fecha else ""
            except Exception:
                fecha_s = ""
            rows.append([r.id, oc, proveedor, tipo, numero, fecha_s, pur.estado, self._fmt_clp(pur.total_compra)])
            self._recv_ids.append(int(r.id))
            self._recv_to_purchase[int(r.id)] = int(pur.id)

        self._set_table_data(self.tbl_recv, self.RECV_COLS, self.RECV_W, rows)
        # Limpia detalle
        self._set_table_data(self.tbl_recv_det, self.RECV_DET_COLS, self.RECV_DET_W, [])

    def _get_selected_reception_id(self) -> Optional[int]:
        tv = getattr(self.tbl_recv, "_fallback", None)
        if tv is not None:
            try:
                sel = tv.selection()
                if not sel:
                    return None
                vals = list(tv.item(sel[0], "values"))
                return int(vals[0]) if vals and vals[0] != '' else None
            except Exception:
                return None
        idx = self._selected_row_index(self.tbl_recv)
        if idx is None or idx < 0:
            return None
        try:
            return int(self.tbl_recv.sheet.get_row_data(idx)[0])  # type: ignore[attr-defined]
        except Exception:
            return None

    def _on_reception_selected(self, _evt: object | None = None):
        rid = self._get_selected_reception_id()
        if rid is None:
            return
        pid = self._recv_to_purchase.get(int(rid))
        if not pid:
            return
        # Preview de la recepción seleccionada: líneas recibidas (stock_entries)
        rows: List[List] = []
        try:
            from src.data.models import StockEntry, Location
            q = (
                self.session.query(StockEntry, Product)
                .join(Product, Product.id == StockEntry.id_producto)
                .filter(StockEntry.id_recepcion == rid)
                .order_by(StockEntry.id.asc())
            )
            for se, prod in q:
                loc_name = ""
                try:
                    if getattr(se, 'id_ubicacion', None):
                        loc = self.session.get(Location, int(getattr(se, 'id_ubicacion', 0) or 0))
                        loc_name = getattr(loc, 'nombre', '') or ''
                except Exception:
                    loc_name = ""
                lote_serie = (se.lote or se.serie or "")
                fv = getattr(se, 'fecha_vencimiento', None)
                fv_s = fv.strftime("%Y-%m-%d") if fv else ""
                rows.append([prod.id, prod.nombre, int(se.cantidad or 0), loc_name, lote_serie, fv_s])
        except Exception:
            rows = []
        # Fallback (datos antiguos sin id_recepcion): mostrar recibidos totales por ítem de la OC
        if not rows:
            try:
                from src.data.models import PurchaseDetail
                q2 = (
                    self.session.query(PurchaseDetail, Product)
                    .join(Product, Product.id == PurchaseDetail.id_producto)
                    .filter(PurchaseDetail.id_compra == int(pid))
                )
                for det, prod in q2:
                    rec_total = int(getattr(det, 'received_qty', 0) or 0)
                    rows.append([prod.id, prod.nombre, rec_total, "", ""])  # sin lote/serie/vence disponibles
            except Exception:
                pass
        self._set_table_data(self.tbl_recv_det, self.RECV_DET_COLS, self.RECV_DET_W, rows)

    def _reception_open_in_purchases(self):
        rid = self._get_selected_reception_id()
        if rid is None:
            messagebox.showwarning("Recepciones", "Seleccione una recepción.")
            return
        pid = self._recv_to_purchase.get(int(rid))
        if not pid:
            return
        # Abrir pestaña Compras y abrir la recepción para edición
        try:
            mw = self.master.master
            if hasattr(mw, 'show_purchases'):
                mw.show_purchases()
            pv = getattr(mw, 'purchases_tab', None)
            if pv and hasattr(pv, 'load_reception_for_edit'):
                pv.load_reception_for_edit(int(rid))
        except Exception:
            pass

    def _reception_print_po(self):
        rid = self._get_selected_reception_id()
        if rid is None:
            messagebox.showwarning("Recepciones", "Seleccione una recepción.")
            return
        pid = self._recv_to_purchase.get(int(rid))
        if not pid:
            return
        # Reutiliza rutina de reimpresión de OC para el purchase_id asociado
        pur = self.session.get(Purchase, pid)
        if pur is None:
            return
        # Código compartido con _purchase_print_pdf, duplicado mínimo para no reestructurar
        try:
            sup = self.session.get(Supplier, pur.id_proveedor)
            supplier_dict = {
                "id": str(getattr(sup, "id", "")),
                "nombre": getattr(sup, "razon_social", "") or "",
                "contacto": getattr(sup, "contacto", "") or "",
                "telefono": getattr(sup, "telefono", "") or "",
                "email": getattr(sup, "email", "") or "",
                "direccion": getattr(sup, "direccion", "") or "",
                "pago": "",
            }
            # Items actuales de la OC
            items = []
            for det in pur.details:
                prod = self.session.get(Product, det.id_producto)
                if not prod:
                    continue
                items.append({
                    "id": int(prod.id),
                    "nombre": str(prod.nombre),
                    "cantidad": int(det.cantidad),
                    "precio": float(det.precio_unitario),
                    "subtotal": float(det.subtotal),
                    "dcto_pct": 0,
                    "unidad": getattr(prod, "unidad_medida", None) or "U",
                })
            po_number = f"OC-{pur.id}"
            out = generate_po_to_downloads(
                po_number=po_number,
                supplier=supplier_dict,
                items=items,
                currency=str(pur.moneda or "CLP"),
                notes=None,
                auto_open=True,
            )
            messagebox.showinfo("Recepciones", f"OC generada nuevamente:\n{out}")
        except Exception as ex:
            messagebox.showerror("Recepciones", f"No se pudo generar el PDF:\n{ex}")

    def _reception_report_pdf(self):
        rid = self._get_selected_reception_id()
        if rid is None:
            messagebox.showwarning("Recepciones", "Seleccione una recepción.")
            return
        pid = self._recv_to_purchase.get(int(rid))
        if not pid:
            return
        try:
            from src.data.models import Reception
            rec = self.session.get(Reception, int(rid))
            pur = self.session.get(Purchase, int(pid))
            sup = self.session.get(Supplier, pur.id_proveedor) if pur else None
            if not rec or not pur or not sup:
                messagebox.showerror("Recepciones", "Faltan datos para generar el informe.")
                return
            # Header supplier
            supplier_dict = {
                "id": str(getattr(sup, "id", "")),
                "nombre": getattr(sup, "razon_social", "") or "",
                "contacto": getattr(sup, "contacto", "") or "",
                "telefono": getattr(sup, "telefono", "") or "",
                "email": getattr(sup, "email", "") or "",
                "direccion": getattr(sup, "direccion", "") or "",
            }
            reception_dict = {
                "id": int(getattr(rec, 'id', 0) or 0),
                "fecha": getattr(rec, 'fecha', None),
                "tipo_doc": getattr(rec, 'tipo_doc', '') or '',
                "numero_documento": getattr(rec, 'numero_documento', '') or '',
            }
            purchase_hdr = {
                "moneda": getattr(pur, 'moneda', None),
                "tasa_cambio": getattr(pur, 'tasa_cambio', None),
                "fecha_documento": getattr(pur, 'fecha_documento', None),
                "fecha_contable": getattr(pur, 'fecha_contable', None),
                "fecha_vencimiento": getattr(pur, 'fecha_vencimiento', None),
                "unidad_negocio": getattr(pur, 'unidad_negocio', None),
                "proporcionalidad": getattr(pur, 'proporcionalidad', None),
                "stock_policy": getattr(pur, 'stock_policy', None),
            }
            # Lines from stock_entries (preferido)
            from src.data.models import StockEntry, Product, PurchaseDetail, Location
            q = (
                self.session.query(StockEntry, Product)
                .join(Product, Product.id == StockEntry.id_producto)
                .filter(StockEntry.id_recepcion == int(rid))
                .order_by(StockEntry.id.asc())
            )
            lines = []
            for se, prod in q:
                loc_name = ''
                try:
                    if getattr(se, 'id_ubicacion', None):
                        loc = self.session.get(Location, int(getattr(se, 'id_ubicacion', 0) or 0))
                        loc_name = getattr(loc, 'nombre', '') or ''
                except Exception:
                    loc_name = ''
                lines.append({
                    'id': int(getattr(prod, 'id', 0) or 0),
                    'nombre': getattr(prod, 'nombre', '') or '',
                    'unidad': getattr(prod, 'unidad_medida', None) or 'U',
                    'cantidad': int(getattr(se, 'cantidad', 0) or 0),
                    'ubicacion': loc_name,
                    'lote_serie': (getattr(se, 'lote', None) or getattr(se, 'serie', None) or ''),
                    'vence': getattr(se, 'fecha_vencimiento', None),
                })
            # Fallback: si no hay registros por id_recepcion (recepciones antiguas), usar totales recibidos por ítem
            if not lines:
                q2 = (
                    self.session.query(PurchaseDetail, Product)
                    .join(Product, Product.id == PurchaseDetail.id_producto)
                    .filter(PurchaseDetail.id_compra == int(pid))
                )
                for det, prod in q2:
                    qty = int(getattr(det, 'received_qty', 0) or 0)
                    if qty <= 0:
                        continue
                    lines.append({
                        'id': int(getattr(prod, 'id', 0) or 0),
                        'nombre': getattr(prod, 'nombre', '') or '',
                        'unidad': getattr(prod, 'unidad_medida', None) or 'U',
                        'cantidad': qty,
                        'lote_serie': '',
                        'vence': None,
                    })
            from src.reports.reception_report_pdf import generate_reception_report_to_downloads
            out = generate_reception_report_to_downloads(
                oc_number=f"OC-{pur.id}",
                supplier=supplier_dict,
                reception=reception_dict,
                purchase_header=purchase_hdr,
                lines=lines,
                auto_open=True,
            )
            messagebox.showinfo("Recepciones", f"Informe generado:\n{out}")
        except Exception as ex:
            messagebox.showerror("Recepciones", f"No se pudo generar el informe:\n{ex}")

    def _on_purchase_selected(self, _evt: object | None = None):
        pid = self._get_selected_purchase_id()
        if pid is not None:
            self._load_purchase_details(pid)
            # Sincroniza editor de estado
            pur = self.session.get(Purchase, pid)
            if pur is not None:
                try:
                    self.pur_state_cb.set(str(pur.estado))
                except Exception:
                    pass

    def _get_selected_purchase_id(self) -> Optional[int]:
        tv = getattr(self.tbl_pur, "_fallback", None)
        if tv is not None:
            try:
                sel = tv.selection()
                if not sel:
                    return None
                vals = list(tv.item(sel[0], "values"))
                return int(vals[0]) if vals and vals[0] != '' else None
            except Exception:
                return None
        idx = self._selected_row_index(self.tbl_pur)
        if idx is None or idx < 0:
            return None
        try:
            return int(self.tbl_pur.sheet.get_row_data(idx)[0])  # type: ignore[attr-defined]
        except Exception:
            return None

    def _load_purchase_details(self, purchase_id: int):
        rows: List[List] = []
        q = (
            self.session.query(PurchaseDetail, Product)
            .join(Product, Product.id == PurchaseDetail.id_producto)
            .filter(PurchaseDetail.id_compra == purchase_id)
        )
        for det, prod in q:
            rows.append([prod.id, prod.nombre, det.cantidad, self._fmt_clp(det.precio_unitario), self._fmt_clp(det.subtotal)])

        self._set_table_data(self.tbl_pur_det, self.PUR_DET_COLS, self.PUR_DET_W, rows)

    def _get_selected_purchase(self) -> Optional[Purchase]:
        pid = self._get_selected_purchase_id()
        return self.session.get(Purchase, pid) if pid else None

    def _purchase_link_reception(self) -> None:
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        try:
            from src.gui.reception_link_dialog import ReceptionLinkDialog
        except Exception:
            messagebox.showerror("Compras", "No se pudo abrir el diálogo de vinculación.")
            return
        dlg = ReceptionLinkDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return
        data = dlg.result
        try:
            from src.data.models import Reception
            r = Reception(
                id_compra=int(pur.id),
                tipo_doc=str(data.get("tipo_doc") or ""),
                numero_documento=str(data.get("numero_documento") or ""),
            )
            self.session.add(r)
            self.session.commit()
            messagebox.showinfo("Compras", f"Recepción vinculada a OC {pur.id}.")
            try:
                mw = self.master.master
                if hasattr(mw, 'show_purchases'):
                    mw.show_purchases()
                pv = getattr(mw, 'purchases_tab', None)
                if pv and hasattr(pv, 'load_purchase_for_reception'):
                    pv.load_purchase_for_reception(
                        int(pur.id),
                        rec_id=int(r.id),
                        tipo_doc=data.get('tipo_doc'),
                        numero_doc=data.get('numero_documento'),
                    )
            except Exception:
                pass
        except Exception as ex:
            self.session.rollback()
            messagebox.showerror("Compras", f"No se pudo vincular la recepción:\n{ex}")

    def _purchase_print_pdf(self):
        """Genera nuevamente el PDF de la OC para la compra seleccionada."""
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        try:
            # Supplier dict para el generador
            sup = self.session.get(Supplier, pur.id_proveedor)
            supplier_dict = {
                "id": str(getattr(sup, "id", "")),
                "nombre": getattr(sup, "razon_social", "") or "",
                "contacto": getattr(sup, "contacto", "") or "",
                "telefono": getattr(sup, "telefono", "") or "",
                "email": getattr(sup, "email", "") or "",
                "direccion": getattr(sup, "direccion", "") or "",
                "pago": getattr(pur, "forma_pago", None) or "",
            }

            # Items
            items: List[dict] = []
            for det in getattr(pur, "details", []) or []:
                try:
                    prod = self.session.get(Product, det.id_producto)
                    unidad = getattr(prod, "unidad_medida", None) or "U"
                    items.append({
                        "id": int(det.id_producto),
                        "nombre": getattr(prod, "nombre", "") or "",
                        "cantidad": int(det.cantidad),
                        # precio en bruto (con IVA) si el generador lo espera; usamos subtotal para seguridad
                        "precio": float(det.precio_unitario),
                        "subtotal": float(det.subtotal),
                        "dcto_pct": 0,
                        "unidad": unidad,
                    })
                except Exception:
                    continue

            # Notas (con fechas del registro)
            def _fmt(d):
                try:
                    return d.strftime("%d/%m/%Y") if d else ""
                except Exception:
                    return ""
            notes_parts = []
            if pur.numero_documento: notes_parts.append(f"NÂº Doc: {pur.numero_documento}")
            if pur.fecha_documento: notes_parts.append(f"F. Documento: {_fmt(pur.fecha_documento)}")
            if pur.fecha_contable: notes_parts.append(f"F. Contable: {_fmt(pur.fecha_contable)}")
            if pur.fecha_vencimiento: notes_parts.append(f"F. Venc.: {_fmt(pur.fecha_vencimiento)}")
            if pur.moneda: notes_parts.append(f"Moneda: {pur.moneda}")
            if pur.tasa_cambio: notes_parts.append(f"Tasa cambio: {pur.tasa_cambio}")
            if pur.unidad_negocio: notes_parts.append(f"U. negocio: {pur.unidad_negocio}")
            if pur.proporcionalidad: notes_parts.append(f"Proporcionalidad: {pur.proporcionalidad}")
            if pur.referencia: notes_parts.append(f"Referencia: {pur.referencia}")
            if pur.ajuste_iva: notes_parts.append(f"Ajuste IVA: {pur.ajuste_iva}")
            if pur.ajuste_impuesto: notes_parts.append(f"Ajuste impuesto: {pur.ajuste_impuesto}")
            notes = " | ".join(notes_parts) if notes_parts else None

            po_number = f"OC-{pur.id}"
            out = generate_po_to_downloads(
                po_number=po_number,
                supplier=supplier_dict,
                items=items,
                currency=str(pur.moneda or "CLP"),
                notes=notes,
                auto_open=True,
            )
            messagebox.showinfo("Compras", f"OC generada nuevamente:\n{out}")
        except Exception as ex:
            messagebox.showerror("Compras", f"No se pudo generar el PDF:\n{ex}")

    def _purchase_mark_completed(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        if str(pur.estado).strip().lower() == "completada":
            messagebox.showinfo("Compras", "Esta compra ya estÃ¡ COMPLETADA.")
            return

        def action():
            for det in pur.details:
                self.inventory.register_entry(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Compra {pur.id}",
                )
            pur.estado = "Completada"

        self._handle_db_action(
            action,
            f"Compra {pur.id} marcada como COMPLETADA y stock actualizado.",
            self._load_purchases
        )

    def _purchase_cancel(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return

        def action():
            self.pm.cancel_purchase(pur.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Compra {pur.id} cancelada.",
            self._load_purchases
        )

    def _purchase_delete(self):
        pur = self._get_selected_purchase()
        if not pur:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        if not messagebox.askyesno("Confirmar", f"Â¿Eliminar compra {pur.id}?"):
            return

        def action():
            self.pm.delete_purchase(pur.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Compra {pur.id} eliminada.",
            self._load_purchases
        )

    # ============================== Ventas ============================= #
    def _load_sales(self):
        rows: List[List] = []
        self._sale_ids = []

        q = (
            self.session.query(Sale, Customer)
            .join(Customer, Customer.id == Sale.id_cliente)
            .order_by(Sale.id.desc())
        )
        # Filtros activos
        try:
            idx = self.sale_filter_customer.current()
            if idx is not None and idx > 0:
                cust = self._customers_cache[idx - 1]
                q = q.filter(Sale.id_cliente == cust.id)
        except Exception:
            pass
        try:
            st = (self.sale_filter_state.get() or "").strip()
            if st and st != "Todos":
                q = q.filter(Sale.estado == st)
        except Exception:
            pass
        for sale, cust in q:
            if str(sale.estado).strip().lower() == "eliminada":
                continue
            fecha = sale.fecha_venta.strftime("%Y-%m-%d %H:%M")
            cliente = getattr(cust, "razon_social", "") or "-"
            rows.append([sale.id, fecha, cliente, sale.estado, self._fmt_clp(sale.total_venta)])
            self._sale_ids.append(int(sale.id))

        self._set_table_data(self.tbl_sale, self.SALE_COLS, self.SALE_W, rows)
        # Limpia detalle
        self._set_table_data(self.tbl_sale_det, self.SALE_DET_COLS, self.SALE_DET_W, [])

    def _on_sale_selected(self, _evt: object | None = None):
        sid = self._get_selected_sale_id()
        if sid is not None:
            self._load_sale_details(sid)
            sale = self.session.get(Sale, sid)
            if sale is not None:
                try:
                    self.sale_state_cb.set(str(sale.estado))
                except Exception:
                    pass

    # ======================= Aplicar estado (editores) ======================= #
    def _purchase_apply_state(self):
        pid = self._get_selected_purchase_id()
        if pid is None:
            messagebox.showwarning("Compras", "Seleccione una compra.")
            return
        target = (self.pur_state_cb.get() or "").strip() or None
        if not target:
            return
        pur = self.session.get(Purchase, pid)
        if not pur:
            return
        cur_state = str(pur.estado).strip()
        if target.lower() == cur_state.lower():
            return

        if target == "Completada":
            self._purchase_mark_completed()
        elif target == "Por pagar":
            p = self._get_selected_purchase()
            if not p:
                return
            def action_pp():
                for det in p.details:
                    self.inventory.register_entry(product_id=det.id_producto, cantidad=det.cantidad, motivo=f"Compra {p.id}")
                p.estado = "Por pagar"
            self._handle_db_action(action_pp, f"Compra {p.id} marcada como POR PAGAR y stock actualizado.", self._load_purchases)
        elif target == "Cancelada":
            self._purchase_cancel()
        elif target == "Pendiente":
            # Si estaba completada, revertimos stock
            if cur_state.lower() in ("completada", "por pagar"):
                def action():
                    for det in pur.details:
                        self.inventory.register_exit(product_id=det.id_producto, cantidad=det.cantidad, motivo=f"Reversa compra {pur.id}")
                    pur.estado = "Pendiente"
                self._handle_db_action(action, f"Compra {pur.id} marcada como PENDIENTE y stock revertido.", self._load_purchases)
            else:
                def action2():
                    pur.estado = "Pendiente"
                self._handle_db_action(action2, f"Compra {pur.id} marcada como PENDIENTE.", self._load_purchases)

    def _sale_apply_state(self):
        sid = self._get_selected_sale_id()
        if sid is None:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        target = (self.sale_state_cb.get() or "").strip() or None
        if not target:
            return
        sale = self.session.get(Sale, sid)
        if not sale:
            return
        cur_state = str(sale.estado).strip()
        if target.lower() == cur_state.lower():
            return

        if target == "Confirmada":
            self._sale_mark_confirmed()
        elif target == "Cancelada":
            self._sale_cancel()
        elif target == "Eliminada":
            self._sale_delete()
        elif target == "Reservada":
            # Si estaba confirmada, devolver stock
            if cur_state.lower() == "confirmada":
                def action():
                    for det in sale.details:
                        self.inventory.register_entry(product_id=det.id_producto, cantidad=det.cantidad, motivo=f"Reversa venta {sale.id}")
                    sale.estado = "Reservada"
                self._handle_db_action(action, f"Venta {sale.id} marcada como RESERVADA y stock revertido.", self._load_sales)
            else:
                def action2():
                    sale.estado = "Reservada"
                self._handle_db_action(action2, f"Venta {sale.id} marcada como RESERVADA.", self._load_sales)

    def _get_selected_sale_id(self) -> Optional[int]:
        tv = getattr(self.tbl_sale, "_fallback", None)
        if tv is not None:
            try:
                sel = tv.selection()
                if not sel:
                    return None
                vals = list(tv.item(sel[0], "values"))
                return int(vals[0]) if vals and vals[0] != '' else None
            except Exception:
                return None
        idx = self._selected_row_index(self.tbl_sale)
        if idx is None or idx < 0:
            return None
        try:
            return int(self.tbl_sale.sheet.get_row_data(idx)[0])  # type: ignore[attr-defined]
        except Exception:
            return None

    def _load_sale_details(self, sale_id: int):
        rows: List[List] = []
        q = (
            self.session.query(SaleDetail, Product)
            .join(Product, Product.id == SaleDetail.id_producto)
            .filter(SaleDetail.id_venta == sale_id)
        )
        for det, prod in q:
            rows.append([
                prod.id,
                prod.nombre,
                det.cantidad,
                self._fmt_clp(det.precio_unitario),
                self._fmt_clp(det.subtotal),
            ])

        self._set_table_data(self.tbl_sale_det, self.SALE_DET_COLS, self.SALE_DET_W, rows)

    # ------------------ Filtros: lookups y acciones ------------------ #
    def _refresh_filter_lookups(self) -> None:
        try:
            self._suppliers_cache = self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all()
            vals = ["Todos"] + [getattr(s, "razon_social", "") or f"Proveedor {s.id}" for s in self._suppliers_cache]
            self.pur_filter_supplier["values"] = vals
            self.pur_filter_supplier.current(0)
        except Exception:
            pass
        try:
            self._customers_cache = self.session.query(Customer).order_by(Customer.razon_social.asc()).all()
            vals = ["Todos"] + [getattr(c, "razon_social", "") or f"Cliente {c.id}" for c in self._customers_cache]
            self.sale_filter_customer["values"] = vals
            self.sale_filter_customer.current(0)
        except Exception:
            pass

    def _apply_purchase_filter(self):
        self._load_purchases()

    def _clear_purchase_filter(self):
        try:
            self.pur_filter_supplier.current(0)
            self.pur_filter_state.current(0)
        except Exception:
            pass
        self._load_purchases()

    def _apply_sale_filter(self):
        self._load_sales()

    def _clear_sale_filter(self):
        try:
            self.sale_filter_customer.current(0)
            self.sale_filter_state.current(0)
        except Exception:
            pass
        self._load_sales()

    def _get_selected_sale(self) -> Optional[Sale]:
        sid = self._get_selected_sale_id()
        return self.session.get(Sale, sid) if sid else None

    def _sale_mark_confirmed(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        if str(sale.estado).strip().lower() == "confirmada":
            messagebox.showinfo("Ventas", "Esta venta ya estÃ¡ CONFIRMADA.")
            return

        def action():
            for det in sale.details:
                self.inventory.register_exit(
                    product_id=det.id_producto,
                    cantidad=det.cantidad,
                    motivo=f"Venta {sale.id}",
                )
            sale.estado = "Confirmada"

        self._handle_db_action(
            action,
            f"Venta {sale.id} marcada como CONFIRMADA y stock actualizado.",
            self._load_sales
        )

    def _sale_print_pdf(self):
        """Genera nuevamente el PDF de la OV para la venta seleccionada."""
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        try:
            cust = self.session.get(Customer, sale.id_cliente)
            customer = {
                "id": str(getattr(cust, "id", "")),
                "nombre": getattr(cust, "razon_social", "") or "",
                "contacto": getattr(cust, "contacto", "") or "",
                "telefono": getattr(cust, "telefono", "") or "",
                "email": getattr(cust, "email", "") or "",
                "direccion": getattr(cust, "direccion", "") or "",
                "rut": getattr(cust, "rut", "") or "-",
                "pago": getattr(sale, "forma_pago", "") or "",
            }
            items: List[dict] = []
            for det in getattr(sale, "details", []) or []:
                try:
                    prod = self.session.get(Product, det.id_producto)
                    unidad = getattr(prod, "unidad_medida", None) or "U"
                    items.append({
                        "id": int(det.id_producto),
                        "nombre": getattr(prod, "nombre", "") or "",
                        "cantidad": int(det.cantidad),
                        "precio": float(det.precio_unitario),
                        "subtotal": float(det.subtotal),
                        "descuento_porcentaje": 0,
                        "unidad": unidad,
                    })
                except Exception:
                    continue
            so_number = f"OV-{sale.id}"
            out = generate_so_to_downloads(
                so_number=so_number,
                customer=customer,
                items=items,
                currency="CLP",
                notes=None,
                auto_open=True,
            )
            messagebox.showinfo("Ventas", f"OV generada nuevamente:\n{out}")
        except Exception as ex:
            messagebox.showerror("Ventas", f"No se pudo generar el PDF:\n{ex}")

    def _sale_cancel(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return

        def action():
            self.sm.cancel_sale(sale.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Venta {sale.id} cancelada.",
            self._load_sales
        )

    def _sale_delete(self):
        sale = self._get_selected_sale()
        if not sale:
            messagebox.showwarning("Ventas", "Seleccione una venta.")
            return
        if not messagebox.askyesno("Confirmar", f"Â¿Eliminar venta {sale.id}?"):
            return

        def action():
            self.sm.delete_sale(sale.id, revert_stock=True)

        self._handle_db_action(
            action,
            f"Venta {sale.id} eliminada.",
            self._load_sales
        )



# src/gui/inventory_view.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional
import webbrowser

from src.data.database import get_session
from src.data.models import Product
from src.data.repository import ProductRepository
from src.utils.helpers import (
    get_inventory_limits,
    get_inventory_refresh_ms,
)

# ==== Reportes / filtros ====
from src.reports.inventory_reports import (
    InventoryFilter,
    InventoryReportService,
    generate_inventory_xlsx,
    print_inventory_report,
)
from src.gui.inventory_filters_dialog import InventoryFiltersDialog
from src.utils.inventory_thresholds import get_thresholds as _get_prod_limits, set_thresholds as _set_prod_limits
from src.gui.printer_select_dialog import PrinterSelectDialog

# Rejilla real (tksheet) o fallback Treeview
from src.gui.widgets.grid_table import GridTable


class InventoryView(ttk.Frame):
    """
    Vista de Inventario con grid real (tksheet) o fallback Treeview:
    - Resaltado por min/max (colores críticos persistentes).
    - Auto-refresco configurable.
    - Filtros + Exportar XLSX + Imprimir.
    - Columnas por 'venta' / 'compra' / 'completo'.
    - Footer con totales: Î£ P. Compra y Î£ P. Venta (de los productos mostrados).
    """

    # ============================ init / estado ============================ #
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        # --- Estado / repos ---
        self.session = get_session()
        self.repo = ProductRepository(self.session)

        self._auto_job: Optional[str] = None
        self._auto_enabled = tk.BooleanVar(value=True)

        # Configuración inicial
        min_v, max_v = get_inventory_limits()
        self._crit_min = tk.IntVar(value=min_v)
        self._crit_max = tk.IntVar(value=max_v)
        self._refresh_ms = tk.IntVar(value=get_inventory_refresh_ms())

        # Filtro activo
        self._current_filter = InventoryFilter()

        # Mapeo de filas mostradas â†’ IDs (para selección/imprimir/exportar)
        self._last_row_ids: List[int] = []

        # --- Encabezado ---
        header = ttk.Frame(self)
        header.pack(fill="x", expand=False)
        ttk.Label(
            header,
            text="Inventario (refresco automático)",
            font=("", 11, "bold"),
        ).pack(side="left")

        # Bloque derecho: acciones
        actions = ttk.Frame(header)
        actions.pack(side="right")
        ttk.Button(actions, text="Imprimir", command=self._on_print).pack(side="right", padx=4)
        ttk.Button(actions, text="Exportar XLSX", command=self._on_export_xlsx).pack(side="right", padx=4)
        ttk.Button(actions, text="Filtros…", command=self._on_filters).pack(side="right", padx=4)
        ttk.Button(actions, text="Refrescar ahora", command=self.refresh_table).pack(side="right", padx=4)
        ttk.Checkbutton(actions, text="Auto", variable=self._auto_enabled, command=self._on_toggle_auto).pack(side="right")

        # Manager de Código de Barras (top-right)
        bar = ttk.Labelframe(header, text="Código de barras", padding=6)
        bar.pack(side="right", padx=(8,0))
        # Canvas fijo para evitar deformaciones con SKUs de distintas longitudes
        self._BAR_W, self._BAR_H = 300,80
        self._bar_canvas = tk.Canvas(
            bar,
            width=self._BAR_W,
            height=self._BAR_H,
            background="white",
            highlightthickness=1,
            relief="sunken",
            bd=0,
        )
        self._bar_canvas.grid(row=0, column=0, columnspan=2, pady=(2, 4))
        self._bar_img = None
        self._bar_show_text = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            bar,
            text="Texto (nombre)",
            variable=self._bar_show_text,
            command=lambda: self._update_bar_preview(),
        ).grid(row=1, column=0, columnspan=2, sticky="w")
        ttk.Label(bar, text="Copias:").grid(row=2, column=0, sticky="e")
        self._bar_copies = tk.IntVar(value=1)
        ttk.Spinbox(bar, from_=1, to=999, textvariable=self._bar_copies, width=6).grid(row=2, column=1, sticky="w")
        btns_bar = ttk.Frame(bar)
        btns_bar.grid(row=3, column=0, columnspan=2, pady=(4,0))
        ttk.Button(btns_bar, text="Actualizar", command=self._update_bar_preview).pack(side="left", padx=3)
        ttk.Button(btns_bar, text="Imprimir", command=self._print_bar_label).pack(side="left", padx=3)

        # --- Tabla (GridTable) ---
        self.table = GridTable(self)
        self.table.pack(fill="both", expand=True, pady=(8, 6))
        # Enlazar selección para actualizar preview de código de barras y movimientos
        tv = getattr(self.table, '_fallback', None)
        if tv is not None:
            tv.bind('<<TreeviewSelect>>', lambda _e: (self._update_bar_preview(), self._load_movements_for_selection()))
            tv.bind('<ButtonRelease-1>', lambda _e: (self._update_bar_preview(), self._load_movements_for_selection()))
        
        # --- Movimientos recientes del producto seleccionado ---
        mov_frame = ttk.Labelframe(self, text="Movimientos recientes", padding=6)
        mov_frame.pack(fill="both", expand=False, pady=(0, 8))
        self.mov_table = GridTable(mov_frame, height=6)
        self.mov_table.pack(fill="both", expand=True)
        self._set_mov_data([])

        # (Se removió panel de "Stock por lote/serie" a pedido)

        # --- Footer de totales ---
        # Muestra Î£ P. Compra y Î£ P. Venta de lo actualmente listado
        footer = ttk.Frame(self)
        footer.pack(fill="x", expand=False, pady=(0, 10))

        ttk.Separator(self, orient="horizontal").pack(fill="x", pady=(0, 6))

        # Etiquetas alineadas a la derecha
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=0)
        footer.grid_columnconfigure(2, weight=0)
        footer.grid_columnconfigure(3, weight=0)

        ttk.Label(footer, text="Totales mostrados:", font=("", 10, "bold")).grid(row=0, column=0, sticky="e", padx=6)

        ttk.Label(footer, text="Î£ P. Compra:").grid(row=0, column=1, sticky="e", padx=(6, 2))
        self._lbl_total_compra = ttk.Label(footer, text="$ 0.00", font=("", 10, "bold"))
        self._lbl_total_compra.grid(row=0, column=2, sticky="w", padx=(0, 12))

        ttk.Label(footer, text="Î£ P. Venta:").grid(row=0, column=3, sticky="e", padx=(6, 2))
        self._lbl_total_venta = ttk.Label(footer, text="$ 0.00", font=("", 10, "bold"))
        self._lbl_total_venta.grid(row=0, column=4, sticky="w")

        # Leyenda (colorímetro) en la esquina inferior derecha
        self._legend = ttk.Frame(footer)
        self._legend.grid(row=0, column=5, sticky="e", padx=6)
        self._build_legend()

        # --- Límites por producto seleccionado ---
        prod_cfg = ttk.Labelframe(self, text="Límites críticos del producto seleccionado", padding=10)
        prod_cfg.pack(fill="x", expand=False, pady=(6, 10))
        self._sel_min = tk.IntVar(value=0)
        self._sel_max = tk.IntVar(value=0)
        ttk.Label(prod_cfg, text="Mínimo:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(prod_cfg, from_=0, to=999999, textvariable=self._sel_min, width=10).grid(row=0, column=1, sticky="w", padx=4, pady=4)
        ttk.Label(prod_cfg, text="Máximo:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Spinbox(prod_cfg, from_=0, to=999999, textvariable=self._sel_max, width=10).grid(row=0, column=3, sticky="w", padx=4, pady=4)
        ttk.Button(prod_cfg, text="Guardar límites del producto", command=self._on_save_selected_limits).grid(row=0, column=4, padx=8)

        # Primera carga + auto
        self.refresh_table()
        self._schedule_auto()

    # ====================== columnas y filas ====================== #
    def _columns_for(self, report_type: str) -> List[str]:
        """Define columnas del Treeview. Incluye todos los datos relevantes del producto."""
        comunes = ["ID", "Producto", "SKU", "Unidad", "Stock", "Lote/Serie"]
        if report_type == "venta":
            return comunes + ["P. Venta", "Proveedor", "Ubicación"]
        if report_type == "compra":
            return comunes + ["P. Compra", "Proveedor", "Ubicación"]
        return comunes + ["P. Compra", "P. Venta", "Proveedor", "Ubicación"]

    def _rows_from_products(self, products: List[Product], report_type: str):
        """
        Devuelve (rows, colors, ids)
          rows  : lista de listas con valores para la tabla
          colors: color de fondo por fila (None / rango por color)
          ids   : IDs de producto para mapear selección
        """
        rows, colors, ids = [], [], []
        min_def = int(self._crit_min.get())
        max_def = int(self._crit_max.get())

        for p in products:
            stock = int(p.stock_actual or 0)
            # lee límites por producto si existen; si no, usa defaults
            min_v, max_v = _get_prod_limits(int(p.id), min_def, max_def)
            # Colores por rango respecto a límites
            very_low_thr = max(0, int(min_v * 0.5))
            very_high_thr = int(max_v * 1.25)
            color = None
            if stock <= very_low_thr:
                color = "#ffb3b3"    # muy bajo (rojo fuerte)
            elif stock < min_v:
                color = "#ffdddd"    # bajo (rojo claro)
            elif stock > very_high_thr:
                color = "#ffe08a"    # muy alto (amarillo/naranja)
            elif stock > max_v:
                color = "#fff6cc"    # alto (amarillo claro)

            # Construir fila base con Lote/Serie más reciente (si existe)
            # Busca la última entrada con trazabilidad
            loteser = ""
            try:
                from src.data.models import StockEntry
                se = (
                    self.session.query(StockEntry)
                    .filter(StockEntry.id_producto == int(p.id))
                    .filter((StockEntry.lote.isnot(None)) | (StockEntry.serie.isnot(None)))
                    .order_by(StockEntry.fecha.desc())
                    .first()
                )
                if se is not None:
                    loteser = (se.lote or se.serie or "")
            except Exception:
                loteser = ""

            # Fila base
            row = [
                int(p.id),
                (p.nombre or ""),
                (p.sku or ""),
                (p.unidad_medida or ""),
                stock,
                loteser,
            ]

            # Agregar columnas de precio según tipo de reporte (sin barcode)
            if report_type == "venta":
                row += [f"{float(p.precio_venta or 0):.0f}"]
            elif report_type == "compra":
                row += [f"{float(p.precio_compra or 0):.0f}"]
            else:
                row += [f"{float(p.precio_compra or 0):.0f}", f"{float(p.precio_venta or 0):.0f}"]

            # Proveedor y Ubicación
            try:
                prov = getattr(getattr(p, "supplier", None), "razon_social", "") or ""
            except Exception:
                prov = ""
            try:
                ubic = getattr(getattr(p, "location", None), "nombre", "") or ""
            except Exception:
                ubic = ""
            # Anexar proveedor/ubicación al final según columnas
            cols_for_type = self._columns_for(report_type)
            if "Proveedor" in cols_for_type and "Ubicación" in cols_for_type:
                row = row + [prov, ubic]

            rows.append(row)
            colors.append(color)
            ids.append(int(p.id))
        return rows, colors, ids

    # ======================= helpers de totales / formato ======================= #
    @staticmethod
    def _fmt_money(value) -> str:
        """Formatea CLP con miles y sin decimales: $1.234.567."""
        try:
            n = float(value or 0)
            s = f"${n:,.0f}"
            return s.replace(",", ".")
        except Exception:
            return "$ 0"

    @staticmethod
    def _compute_totals(products: List[Product]) -> tuple[float, float]:
        """
        Suma precios unitarios sobre la lista mostrada.
        Retorna: (total_compra, total_venta)
        """
        total_compra = 0.0
        total_venta = 0.0
        for p in products:
            total_compra += float(p.precio_compra or 0)
            total_venta += float(p.precio_venta or 0)
        return total_compra, total_venta

    def _update_footer_totals(self, products: List[Product]) -> None:
        """Actualiza las etiquetas del footer con los totales actuales."""
        total_compra, total_venta = self._compute_totals(products)
        self._lbl_total_compra.config(text=self._fmt_money(total_compra))
        self._lbl_total_venta.config(text=self._fmt_money(total_venta))

    # ================================ acciones UI ================================ #
    def refresh_table(self):
        """Carga productos sin filtros y pinta por min/max (grid real si hay tksheet)."""
        try:
            products: List[Product] = (
                self.session.query(Product)
                .order_by(Product.nombre.asc())
                .all()
            )
            self._populate_table(products)
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo refrescar el inventario:\n{e}")

    def _populate_table(self, products: List[Product]) -> None:
        """
        Pinta la tabla con productos y aplica colores críticos.
        También actualiza el footer de totales con base en 'products'.
        """
        cols = self._columns_for(self._current_filter.report_type)
        rows, colors, ids = self._rows_from_products(products, self._current_filter.report_type)
        self._last_row_ids = ids

        # 1) Cargar datos en la grilla (tksheet o fallback Treeview)
        self.table.set_data(cols, rows)

        # 2) Refrescar tema (si cambió) y luego aplicar colores críticos por fila
        try:
            self.table.theme_refresh()
        except Exception:
            pass
        try:
            self.table.set_row_backgrounds(colors)
        except Exception:
            pass
        # Refrescar movimientos para la selección actual
        self._load_movements_for_selection()

    # ------------------ Movimientos por producto ------------------ #
    def _set_mov_data(self, rows: list[list]):
        cols = ["Fecha", "Tipo", "Cant.", "Proveedor", "Ubicación", "Lote/Serie", "Vence", "Motivo"]
        widths = [140, 70, 70, 220, 160, 150, 110, 260]
        self.mov_table.set_data(cols, rows)
        tv = getattr(self.mov_table, '_fallback', None)
        if tv is not None:
            try:
                for i, c in enumerate(cols):
                    tv.heading(c, text=c, anchor='center')
                    tv.column(c, width=widths[i], anchor='center')
            except Exception:
                pass


    def _load_movements_for_selection(self) -> None:
        try:
            prod = self._current_selected_product()
            if not prod:
                self._set_mov_data([])
                return
            pid = int(getattr(prod, 'id', 0) or 0)
            if pid <= 0:
                self._set_mov_data([])
                return
            from src.data.models import StockEntry, StockExit, Reception, Purchase, Supplier, Location
            rows: list[list] = []
            q_e = (
                self.session.query(StockEntry, Reception, Purchase, Supplier, Location)
                .outerjoin(Reception, StockEntry.id_recepcion == Reception.id)
                .outerjoin(Purchase, Reception.id_compra == Purchase.id)
                .outerjoin(Supplier, Purchase.id_proveedor == Supplier.id)
                .outerjoin(Location, StockEntry.id_ubicacion == Location.id)
                .filter(StockEntry.id_producto == pid)
                .order_by(StockEntry.id.desc())
                .limit(50)
            )
            for se, rec, pur, sup, loc in q_e:
                fecha = getattr(se, 'fecha', None)
                try:
                    fecha_s = fecha.strftime('%Y-%m-%d %H:%M') if fecha else ''
                except Exception:
                    fecha_s = ''
                prov = getattr(sup, 'razon_social', '') if sup else ''
                ubic = getattr(loc, 'nombre', '') if loc else ''
                if not ubic:
                    # Fallback: mostrar ubicación por defecto del producto
                    try:
                        p = self.session.get(Product, int(getattr(se, 'id_producto', 0) or 0))
                        ubic = getattr(getattr(p, 'location', None), 'nombre', '') or ''
                    except Exception:
                        pass
                loteser = (getattr(se, 'lote', None) or getattr(se, 'serie', None) or '')
                vence = getattr(se, 'fecha_vencimiento', None)
                try:
                    vence_s = vence.strftime('%Y-%m-%d') if vence else ''
                except Exception:
                    vence_s = ''
                rows.append([fecha_s, 'Entrada', int(getattr(se, 'cantidad', 0) or 0), prov, ubic, loteser, vence_s, getattr(se, 'motivo', '') or ''])
            q_x = (
                self.session.query(StockExit)
                .filter(StockExit.id_producto == pid)
                .order_by(StockExit.id.desc())
                .limit(50)
            )
            for sx in q_x:
                fecha = getattr(sx, 'fecha', None)
                try:
                    fecha_s = fecha.strftime('%Y-%m-%d %H:%M') if fecha else ''
                except Exception:
                    fecha_s = ''
                rows.append([fecha_s, 'Salida', int(getattr(sx, 'cantidad', 0) or 0), '', '', '', '', getattr(sx, 'motivo', '') or ''])
            try:
                rows.sort(key=lambda r: r[0], reverse=True)
            except Exception:
                pass
            self._set_mov_data(rows)
        except Exception:
            self._set_mov_data([])


    # ------------------ Barcode helpers ------------------ #
    def _current_selected_product(self) -> Optional[Product]:
        tv = getattr(self.table, '_fallback', None)
        if tv is not None:
            sel = tv.selection()
            if sel:
                try:
                    idx = tv.index(sel[0])
                    if 0 <= idx < len(self._last_row_ids):
                        return self.session.get(Product, int(self._last_row_ids[idx]))
                except Exception:
                    return None
            return None
        if hasattr(self.table, 'sheet'):
            try:
                rows = list(self.table.sheet.get_selected_rows())
                if rows:
                    i = sorted(rows)[0]
                    if 0 <= i < len(self._last_row_ids):
                        return self.session.get(Product, int(self._last_row_ids[i]))
            except Exception:
                return None
        return None

    def _update_bar_preview(self):
        # Limpiar área
        try:
            self._bar_canvas.delete("all")
        except Exception:
            pass

        p = self._current_selected_product()
        if not p:
            self._bar_canvas.create_text(
                self._BAR_W // 2,
                self._BAR_H // 2,
                text="(sin selección)",
                fill="#666",
                font=("TkDefaultFont", 10),
            )
            return

        code = (p.sku or "").strip()
        if not code:
            self._bar_canvas.create_text(
                self._BAR_W // 2,
                self._BAR_H // 2,
                text="(sin código)",
                fill="#666",
                font=("TkDefaultFont", 10),
            )
            return

        try:
            from src.reports.barcode_label import generate_barcode_png

            text = (p.nombre or "") if self._bar_show_text.get() else None
            png = generate_barcode_png(
                code,
                text=text,
                symbology="code128",
                width_mm=50,
                height_mm=15,
            )

            # Prefer PIL para escalar al canvas
            try:
                import PIL.Image  # type: ignore
                import PIL.ImageTk  # type: ignore

                im = PIL.Image.open(png)
                im = im.convert("RGBA")
                # Escalar proporcionalmente para caber en el canvas
                max_w, max_h = self._BAR_W, self._BAR_H
                im.thumbnail((max_w, max_h), resample=getattr(PIL.Image, "LANCZOS", 1))
                self._bar_img = PIL.ImageTk.PhotoImage(im)
                self._bar_canvas.create_image(
                    self._BAR_W // 2,
                    self._BAR_H // 2,
                    image=self._bar_img,
                )
            except Exception:
                # Fallback: sin escalado si PIL no está disponible
                self._bar_img = tk.PhotoImage(file=str(png))
                self._bar_canvas.create_image(
                    self._BAR_W // 2,
                    self._BAR_H // 2,
                    image=self._bar_img,
                )
        except Exception:
            self._bar_canvas.create_text(
                self._BAR_W // 2,
                self._BAR_H // 2,
                text="(error)",
                fill="#a00",
                font=("TkDefaultFont", 10),
            )

    def _print_bar_label(self):
        p = self._current_selected_product()
        if not p:
            messagebox.showwarning('Etiquetas', 'Seleccione un producto en la tabla.')
            return
        # El código de barras se genera SIEMPRE desde el SKU
        code = (p.sku or '').strip()
        if not code:
            messagebox.showwarning('Etiquetas', 'El producto no tiene código/SKU.')
            return
        copies = max(1, int(self._bar_copies.get() or 1))
        try:
            from src.reports.barcode_label import generate_label_pdf
            text = (p.nombre or '') if self._bar_show_text.get() else None
            out = generate_label_pdf(code, text=text, symbology='code128', label_w_mm=50, label_h_mm=30, copies=copies, auto_open=True)
            messagebox.showinfo('Etiquetas', f'PDF generado:\n{out}')
        except Exception as ex:
            messagebox.showerror('Etiquetas', f'No se pudo generar etiquetas:\n{ex}')
            return

        # 4) Actualizar totales del footer
        # self._update_footer_totals(products)  # removed: handled elsewhere
        # 5) Enlazar selección → actualizar panel límites
        try:
            if hasattr(self.table, "sheet"):
                self.table.sheet.extra_bindings([("cell_select", lambda e: self._update_selected_limits_panel())])
            tv = getattr(self.table, "_fallback", None)
            if tv is not None:
                tv.bind("<<TreeviewSelect>>", lambda _e: self._update_selected_limits_panel())
        except Exception:
            pass

    # ----------------------- Leyenda de colores ----------------------- #
    def _build_legend(self):
        """Leyenda robusta al cambio de tema: usa Canvas para los parches de color."""
        for c in self._legend.winfo_children():
            c.destroy()

        canvas = tk.Canvas(self._legend, height=16, highlightthickness=0, bd=0)
        canvas.pack(side="left")

        items = [
            ("#ffb3b3", "Muy bajo"),
            ("#ffdddd", "Bajo"),
            ("#fff6cc", "Alto"),
            ("#ffe08a", "Muy alto"),
        ]
        x = 0
        for color, label in items:
            canvas.create_rectangle(x, 2, x + 18, 14, fill=color, outline="#808080")
            x += 22
            t = ttk.Label(self._legend, text=label)
            t.pack(side="left", padx=(2, 8))
        # Ajustar ancho del canvas a los parches dibujados
        canvas.config(width=x)

    # ---------------- Límites por producto (panel) ---------------- #
    def _update_selected_limits_panel(self) -> None:
        ids = self._selected_ids()
        if not ids:
            return
        pid = int(ids[0])
        mn_def = int(self._crit_min.get()); mx_def = int(self._crit_max.get())
        mn, mx = _get_prod_limits(pid, mn_def, mx_def)
        try:
            self._sel_min.set(int(mn)); self._sel_max.set(int(mx))
        except Exception:
            pass

    def _on_save_selected_limits(self) -> None:
        ids = self._selected_ids()
        if not ids:
            messagebox.showwarning("Inventario", "Seleccione un producto en la tabla.")
            return
        pid = int(ids[0])
        try:
            mn = int(self._sel_min.get()); mx = int(self._sel_max.get())
        except Exception:
            messagebox.showwarning("Inventario", "Valores inválidos para mínimo/máximo.")
            return
        if mn < 0 or mx < 0:
            messagebox.showwarning("Inventario", "Los límites deben ser ≥ 0.")
            return
        if mx and mn and mx < mn:
            messagebox.showwarning("Inventario", "Máximo no puede ser menor que Mínimo.")
            return
        _set_prod_limits(pid, mn, mx)
        self.refresh_table()

    # (El bloque de configuración por defecto se eliminó por solicitud)

    def _on_toggle_auto(self):
        if self._auto_enabled.get():
            self._schedule_auto()
        else:
            self._cancel_auto()

    # ----------------------------- Auto-refresh ----------------------------- #
    def _tick(self):
        self.refresh_table()
        if self._auto_enabled.get():
            self._auto_job = self.after(self._refresh_ms.get(), self._tick)

    def _schedule_auto(self):
        if self._auto_enabled.get():
            self._auto_job = self.after(self._refresh_ms.get(), self._tick)

    def _cancel_auto(self):
        if self._auto_job:
            try:
                self.after_cancel(self._auto_job)
            except Exception:
                pass
            self._auto_job = None

    # ---------------------- Filtros, exportación, impresión ---------------------- #
    def _selected_ids(self) -> List[int]:
        """IDs de filas seleccionadas (tksheet o fallback Treeview)."""
        # tksheet backend
        if hasattr(self.table, "sheet"):
            try:
                sel_rows = sorted(set(self.table.sheet.get_selected_rows()))
            except Exception:
                try:
                    cells = self.table.sheet.get_selected_cells()
                    sel_rows = sorted({r for r, _c in cells})
                except Exception:
                    sel_rows = []
            return [self._last_row_ids[i] for i in sel_rows if 0 <= i < len(self._last_row_ids)]

        # Treeview fallback
        tv = getattr(self.table, "_fallback", None)
        ids: List[int] = []
        if tv is not None:
            for iid in tv.selection():
                try:
                    idx = tv.index(iid)
                    ids.append(self._last_row_ids[idx])
                except Exception:
                    pass
        return ids

    def _on_filters(self):
        """Abre diálogo de filtros, aplica y actualiza tabla + totales."""
        dlg = InventoryFiltersDialog(self, initial=self._current_filter)
        self.wait_window(dlg)
        if dlg.result:
            self._current_filter = dlg.result
            try:
                svc = InventoryReportService(self.session)
                products = svc.fetch(self._current_filter)
                self._populate_table(products)
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo aplicar filtros:\n{e}")

    def _on_export_xlsx(self):
        """Exporta XLSX con filtro actual (o con selección de IDs si la hay)."""
        ids = self._selected_ids()
        flt = self._current_filter
        if ids:
            flt = InventoryFilter(**{**flt.__dict__, "ids_in": ids})
        try:
            path = generate_inventory_xlsx(self.session, flt, "Listado de Inventario")
            webbrowser.open(str(path))
            messagebox.showinfo("OK", f"Exportado a:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo exportar:\n{e}")

    def _on_print(self):
        """Imprime con filtro actual (o con selección de IDs si la hay)."""
        ids = self._selected_ids()
        flt = self._current_filter
        if ids:
            flt = InventoryFilter(**{**flt.__dict__, "ids_in": ids})

        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if not dlg.result:
            return

        printer_name = dlg.result
        try:
            path = print_inventory_report(self.session, flt, "Listado de Inventario", printer_name=printer_name)
            messagebox.showinfo("Impresión", f"Enviado a '{printer_name}'.\nArchivo: {path}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo imprimir:\n{e}")

    # --------- Interfaz homogénea con MainWindow --------- #
    def print_current(self):
        self._on_print()

    def refresh_lookups(self):
        self.refresh_table()

    def destroy(self):
        self._cancel_auto()
        super().destroy()


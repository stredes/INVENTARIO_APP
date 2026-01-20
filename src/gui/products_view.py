# src/gui/products_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter import simpledialog
from typing import List, Optional
from pathlib import Path

from src.data.database import get_session
from src.data.models import Product, Supplier, Location
from src.data.repository import ProductRepository, SupplierRepository, LocationRepository
from src.gui.widgets.product_image_box import ProductImageBox  # <-- recuadro imagen

# Grilla tipo hoja (tksheet si está, o fallback Treeview)
from src.gui.widgets.grid_table import GridTable
from sqlalchemy import func  # para filtros (like case-insensitive)
from src.utils.printers import get_label_printer, print_file_windows


def calcular_precios(pc: float, iva: float, margen: float) -> tuple[float, float, float]:
    """Calcula monto IVA, precio + IVA y precio venta sugerido."""
    monto_iva = pc * (iva / 100.0)
    p_mas_iva = pc + monto_iva
    pventa = p_mas_iva * (1.0 + margen / 100.0)
    return round(monto_iva), round(p_mas_iva), round(pventa)


class ProductsView(ttk.Frame):
    """
    CRUD de Productos con grilla tipo hoja:
    - Recuadro de imagen (Cargar/Ver/Quitar)
    - Código (SKU)
    - Precio Compra (neto), IVA %, %Ganancia -> calcula (IVA, P+IVA)
    - Precio Venta (editable)
    - Proveedor (obligatorio) vía Combobox
    """

    COLS = ["ID", "Nombre", "Código", "P. Compra", "IVA %", "Monto IVA", "P. + IVA", "P. Neto", "Margen %", "P. Venta", "Unidad", "Etiqueta"]
    COL_WIDTHS = [50, 220, 120, 90, 70, 90, 90, 90, 90, 90, 90, 80]

    @staticmethod
    def _num(val) -> float:
        """Convierte un valor de celda a float de forma tolerante.
        Acepta números o strings con separadores/moneda ("$ 1.234,56").
        """
        try:
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            if not s:
                return 0.0
            import re
            s = re.sub(r"[^0-9,\.\-]", "", s)
            if "," in s and "." in s:
                if s.rfind(",") > s.rfind("."):
                    s = s.replace(".", "").replace(",", ".")
                else:
                    s = s.replace(",", "")
            elif "," in s:
                s = s.replace(",", ".")
            return float(s or 0)
        except Exception:
            return 0.0

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

        # caché tabla (para doble click en tksheet / tree)
        self._rows_cache: List[List[str]] = []
        self._id_by_index: List[int] = []
        # filtros rápidos de la grilla
        self.var_q_id = tk.StringVar()
        self.var_q_code = tk.StringVar()
        self.var_q_name = tk.StringVar()

        # ---------- estado (variables UI) ----------
        self.var_nombre = tk.StringVar()
        self.var_codigo = tk.StringVar()
        self.var_unidad = tk.StringVar(value="unidad")
        self.var_pc = tk.DoubleVar(value=0.0)
        self.var_iva = tk.DoubleVar(value=19.0)
        self.var_margen = tk.DoubleVar(value=30.0)
        self.var_iva_monto = tk.DoubleVar(value=0.0)
        self.var_p_mas_iva = tk.DoubleVar(value=0.0)
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

        # Panel extremo derecho: Manager de Código de Barras
        bar = ttk.Labelframe(frm, text="Código de Barras", padding=4)
        bar.grid(row=0, column=2, sticky="nw", padx=(10,0))
        # Contenedor externo para botones (queda por fuera del labelframe)
        bar_actions = ttk.Frame(bar)
        bar_actions.grid(row=5, column=0, columnspan=2, sticky="w", pady=(6, 0))
        try:
            bar.grid_columnconfigure(0, weight=1)
            bar.grid_columnconfigure(1, weight=1)
        except Exception:
            pass
        # Guarda referencia para sincronizar Tamaño con el recuadro de imagen
        self._bar_container = bar
        # Panel vertical a la derecha para acciones masivas
        bar_side = ttk.Frame(frm)
        bar_side.grid(row=0, column=3, sticky="nw", padx=(8,0))
        side_btn_opts = dict(fill="x", pady=4)
        ttk.Button(bar_side, text="Aplicar margen selección", command=self._apply_margin_to_selection).pack(**side_btn_opts)
        ttk.Button(bar_side, text="Aplicar Ubicación selección", command=self._apply_location_to_selection).pack(**side_btn_opts)
        ttk.Button(bar_side, text="Aplicar unidad selección", command=self._apply_unit_to_selection).pack(**side_btn_opts)
        ttk.Button(bar_side, text="Aplicar proveedor selección", command=self._apply_supplier_to_selection).pack(**side_btn_opts)
        ttk.Button(bar_side, text="Aplicar familia selección", command=self._apply_family_to_selection).pack(**side_btn_opts)
        # Toggle: si este producto tendrá etiqueta de Código de Barras (basado en SKU)
        self.var_has_barcode = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Generar etiqueta (usar SKU)", variable=self.var_has_barcode,
                        command=lambda: self._on_toggle_has_barcode()).grid(row=0, column=0, columnspan=2, sticky="w")
        # Opción: Mostrar texto legible con el nombre debajo
        self.var_bar_text = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Mostrar texto (nombre)", variable=self.var_bar_text,
                        command=lambda: self._refresh_barcode_preview()).grid(row=1, column=0, columnspan=2, sticky="w")
        # Preview
        self._bar_img_obj = None
        self._bar_preview = ttk.Label(bar, text="(sin código)")
        self._bar_preview.grid(row=2, column=0, columnspan=2, pady=(2,2))
        # Canvas de preview para limitar Tamaño (oculta label)
        try:
            # mismo aspecto que el recuadro de imagen, pero más compacto (ej. 70%)
            _box_w = int(getattr(self.img_box, "_box_w", 200))
            _box_h = int(getattr(self.img_box, "_box_h", 200))
            _scale = 0.7
            self._BAR_CANVAS_W = max(120, int(_box_w * _scale))
            self._BAR_CANVAS_H = max(100, int(_box_h * _scale))
            self._bar_canvas = tk.Canvas(
                bar,
                width=self._BAR_CANVAS_W,
                height=self._BAR_CANVAS_H,
                background="#f4f4f4",
                highlightthickness=1,
                relief="sunken",
                bd=0,
            )
            self._bar_canvas.grid(row=2, column=0, columnspan=2, pady=(2,2), sticky="nwe")
            # Mantener el label oculto, pero permitir que el frame calcule su Tamaño normalmente
            self._bar_preview.grid_remove()
            # Reservar espacio mínimo para el canvas dentro del frame
            try:
                bar.grid_columnconfigure(0, minsize=self._BAR_CANVAS_W, weight=1)
                bar.grid_columnconfigure(1, weight=1)
                bar.grid_rowconfigure(2, minsize=self._BAR_CANVAS_H)
            except Exception:
                pass
            # No desactivar grid_propagate para evitar que el frame colapse
        except Exception:
            pass
        # Tamaño + copias
        ttk.Label(bar, text="Tamaño:").grid(row=3, column=0, sticky="e", padx=2, pady=(2,0))
        self.var_bar_size = tk.StringVar(value="50x30 mm")
        ttk.Combobox(bar, textvariable=self.var_bar_size, values=["30x20 mm", "50x30 mm", "70x40 mm"], width=12, state="readonly").grid(row=3, column=1, sticky="w")
        ttk.Label(bar, text="Copias:").grid(row=4, column=0, sticky="e", padx=2, pady=(2,0))
        self.var_bar_copies = tk.IntVar(value=1)
        ttk.Spinbox(bar, from_=1, to=999, textvariable=self.var_bar_copies, width=8, justify="center").grid(row=4, column=1, sticky="w", pady=(2,0))
        btns_bar = ttk.Frame(bar_actions)
        btns_bar.grid(row=0, column=0, sticky="w")
        # Botones
        # (btns en contenedor externo)
        # (btns en contenedor externo)
        ttk.Button(btns_bar, text="Actualizar", command=self._refresh_barcode_preview).grid(row=0, column=0, sticky="w", padx=3)
        ttk.Button(btns_bar, text="Imprimir", command=self._print_barcode_label).grid(row=0, column=1, sticky="w", padx=3)
        bulk = ttk.Frame(bar_actions)
        bulk.grid(row=1, column=0, sticky="w", pady=(4,0))
        ttk.Button(bulk, text="Marcar selección", command=lambda: self._apply_label_to_selection(True)).grid(row=0, column=0, sticky="w", padx=3)
        ttk.Button(bulk, text="Quitar selección", command=lambda: self._apply_label_to_selection(False)).grid(row=0, column=1, sticky="w", padx=3)




        ttk.Label(right, text="Nombre:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ent_nombre = ttk.Entry(right, textvariable=self.var_nombre, width=35)
        ent_nombre.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.ent_nombre = ent_nombre  # para foco

        ttk.Label(right, text="Código:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        ttk.Entry(right, textvariable=self.var_codigo, width=20).grid(row=0, column=3, sticky="w", padx=4, pady=4)
        # Preview en vivo al cambiar Código o nombre
        try:
            self.var_codigo.trace_add('write', lambda *_: self._refresh_barcode_preview())
            self.var_nombre.trace_add('write', lambda *_: self._refresh_barcode_preview())
        except Exception:
            pass

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
            values=["unidad", "caja", "bolsa", "kg", "lt", "ml"],
            width=15, state="readonly"
        )
        self.cmb_unidad.grid(row=2, column=3, sticky="w", padx=4, pady=4)
        try:
            self.cmb_unidad.bind('<<ComboboxSelected>>', self._on_unidad_change)
        except Exception:
            pass

        # Fila 3: Monto IVA / Precio + IVA
        ttk.Label(right, text="Monto IVA:").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ent_iva_monto = ttk.Entry(right, textvariable=self.var_iva_monto, width=12, state="readonly")
        ent_iva_monto.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(right, text="Precio + IVA:").grid(row=3, column=2, sticky="e", padx=4, pady=4)
        ent_p_mas_iva = ttk.Entry(right, textvariable=self.var_p_mas_iva, width=12, state="readonly")
        ent_p_mas_iva.grid(row=3, column=3, sticky="w", padx=4, pady=4)

        # Fila 4: Precio Venta
        ttk.Label(right, text="Precio Venta:").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ent_pventa = ttk.Entry(right, textvariable=self.var_pventa, width=12)
        ent_pventa.grid(row=4, column=1, sticky="w", padx=4, pady=4)

        # Fila 4 (derecha): Familia (combobox + admin)
        ttk.Label(right, text="Familia:").grid(row=4, column=2, sticky="e", padx=4, pady=4)
        self.var_familia = tk.StringVar()
        self.cmb_familia = ttk.Combobox(right, textvariable=self.var_familia, width=20)
        self.cmb_familia.grid(row=4, column=3, sticky="w", padx=4, pady=4)
        try:
            self.cmb_familia.bind('<<ComboboxSelected>>', lambda *_: None)
        except Exception:
            pass
        ttk.Button(right, text="Admin. familias...", command=self._open_families_manager).grid(row=4, column=4, sticky="w", padx=(4, 0))

        # Fila 5: Proveedor
        ttk.Label(right, text="Proveedor:").grid(row=5, column=0, sticky="e", padx=4, pady=4)
        self.cmb_supplier = ttk.Combobox(right, state="readonly", width=35)
        self.cmb_supplier.grid(row=5, column=1, columnspan=3, sticky="we", padx=4, pady=4)

        # Fila 6: Ubicación
        ttk.Label(right, text="Ubicación:").grid(row=6, column=0, sticky="e", padx=4, pady=4)
        self.cmb_location = ttk.Combobox(right, state="readonly", width=28)
        self.cmb_location.grid(row=6, column=1, sticky="w", padx=4, pady=4)
        ttk.Button(right, text="Admin. Ubicaciones...", command=self._open_locations_manager).grid(row=6, column=2, columnspan=2, sticky="w", padx=4, pady=4)

        # Botones
        btns = ttk.Frame(right)
        btns.grid(row=7, column=0, columnspan=4, pady=8, sticky="w")

        self.btn_save = ttk.Button(btns, text="Agregar", command=self._on_add)
        self.btn_update = ttk.Button(btns, text="Guardar cambios", style="Success.TButton", command=self._on_update, state="disabled")
        self.btn_delete = ttk.Button(btns, text="Eliminar", style="Danger.TButton", command=self._on_delete, state="disabled")
        self.btn_clear = ttk.Button(btns, text="Limpiar", command=self._clear_form)

        self.btn_save.pack(side="left", padx=4)
        self.btn_update.pack(side="left", padx=4)
        self.btn_delete.pack(side="left", padx=4)
        self.btn_clear.pack(side="left", padx=4)

        # ---------- Filtros rápidos (ID / Código / Nombre) ----------
        self._filter_frame = ttk.Frame(self)
        self._filter_frame.pack(fill="x", expand=False, pady=(8, 0))
        ttk.Label(self._filter_frame, text="ID:").grid(row=0, column=0, padx=(0,4), sticky="w")
        ttk.Entry(self._filter_frame, textvariable=self.var_q_id, width=8).grid(row=0, column=1, padx=(0,12), sticky="w")
        ttk.Label(self._filter_frame, text="Código:").grid(row=0, column=2, padx=(0,4), sticky="w")
        ttk.Entry(self._filter_frame, textvariable=self.var_q_code, width=16).grid(row=0, column=3, padx=(0,12), sticky="w")
        ttk.Label(self._filter_frame, text="Nombre:").grid(row=0, column=4, padx=(0,4), sticky="w")
        ttk.Entry(self._filter_frame, textvariable=self.var_q_name, width=28).grid(row=0, column=5, padx=(0,12), sticky="w")
        ttk.Button(self._filter_frame, text="Aplicar filtro", command=self._apply_table_filter).grid(row=0, column=6, padx=(4,0))

        # ---------- Tabla (GridTable) ----------
        self.table = GridTable(self, height=14)
        self.table.pack(fill="both", expand=True, pady=(6, 0))

        # Doble click para editar (tksheet + fallback)
        if hasattr(self.table, "sheet"):
            try:
                self.table.sheet.extra_bindings([("double_click", lambda e: self._on_row_dblclick())])
            except Exception:
                pass
        tv = getattr(self.table, "_fallback", None)
        if tv is not None:
            tv.bind("<Double-1>", lambda e: self._on_row_dblclick())
            tv.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select())
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
        # Ajustar Tamaño del panel de Código de Barras para igualarlo al recuadro de imagen
        try:
            self._setup_bar_same_size_as_image()
        except Exception:
            pass

    # --------- Barcode manager logic --------- #
    def _refresh_barcode_preview(self):
        try:
            # Render sobre Canvas si existe (evita deformar la UI)
            if hasattr(self, "_bar_canvas"):
                try:
                    self._bar_canvas.delete("all")
                except Exception:
                    pass
                # Medidas reales del canvas (si ya está mapeado); fallback a valores base
                try:
                    self._bar_canvas.update_idletasks()
                except Exception:
                    pass
                cw = max(getattr(self, "_BAR_CANVAS_W", 260), int(self._bar_canvas.winfo_width() or 0))
                ch = max(getattr(self, "_BAR_CANVAS_H", 220), int(self._bar_canvas.winfo_height() or 0))
                if not bool(self.var_has_barcode.get()):
                    self._bar_canvas.create_text(cw//2, ch//2, text="(etiqueta desactivada)", fill="#666", font=("TkDefaultFont", 10))
                    return
                code = (self.var_codigo.get() or "").strip()
                if not code:
                    self._bar_canvas.create_text(cw//2, ch//2, text="(sin Código)", fill="#666", font=("TkDefaultFont", 10))
                    return
                from src.reports.barcode_label import generate_barcode_png
                text = (self.var_nombre.get().strip() if self.var_bar_text.get() else None) or None
                png = generate_barcode_png(code, text=text, symbology="code128", width_mm=50, height_mm=15)
                try:
                    import PIL.Image, PIL.ImageTk  # type: ignore
                    im = PIL.Image.open(png)
                    max_w, max_h = cw - 16, ch - 16
                    # Escalar para cubrir todo el ancho del canvas
                    scale_w = float(max_w) / float(im.width) if im.width else 1.0
                    new_w = int(im.width * scale_w)
                    new_h = int(im.height * scale_w)
                    if new_w > 0 and new_h > 0 and (new_w != im.width or new_h != im.height):
                        try:
                            im = im.resize((new_w, new_h))
                        except Exception:
                            im = im.resize((new_w, new_h))
                    # Si la altura supera el alto disponible, recortar verticalmente centrado
                    if new_h > max_h:
                        top = max(0, (new_h - max_h) // 2)
                        im = im.crop((0, top, max_w, top + max_h))
                    self._bar_img_obj = PIL.ImageTk.PhotoImage(im)
                    self._bar_canvas.create_image(cw//2, ch//2, image=self._bar_img_obj)
                except Exception:
                    try:
                        self._bar_img_obj = tk.PhotoImage(file=str(png))
                        self._bar_canvas.create_image(cw//2, ch//2, image=self._bar_img_obj)
                    except Exception:
                        self._bar_canvas.create_text(cw//2, ch//2, text=str(png), fill="#666", font=("TkDefaultFont", 9))
                return
            # Si no está habilitada la etiqueta para este producto, mostrar desactivado
            if not bool(self.var_has_barcode.get()):
                self._bar_preview.configure(text="(etiqueta desactivada)", image="")
                return
            code = (self.var_codigo.get() or "").strip()
            if not code:
                self._bar_preview.configure(text="(sin Código)", image="")
                return
            from src.reports.barcode_label import generate_barcode_png
            text = (self.var_nombre.get().strip() if self.var_bar_text.get() else None) or None
            # Ajustar Tamaño de preview según selección de etiqueta
            try:
                size = (self.var_bar_size.get() or "50x30 mm").replace("mm"," ").strip().split("x")
                w_mm = float(size[0]); h_mm = float(size[1])
            except Exception:
                w_mm, h_mm = 50.0, 30.0
            img_w = max(20.0, w_mm - 10.0)
            img_h = max(10.0, h_mm - 12.0)
            png = generate_barcode_png(code, text=text, symbology="code128", width_mm=img_w, height_mm=img_h)
            # Prefer PIL para mejor escalado; si no está, usa PhotoImage nativo
            try:
                import PIL.Image, PIL.ImageTk  # type: ignore
                im = PIL.Image.open(png)
                max_w = 280
                if im.width > max_w:
                    im = im.resize((max_w, int(im.height * (max_w / im.width))))
                self._bar_img_obj = PIL.ImageTk.PhotoImage(im)
                self._bar_preview.configure(image=self._bar_img_obj, text="")
            except Exception:
                try:
                    self._bar_img_obj = tk.PhotoImage(file=str(png))
                    self._bar_preview.configure(image=self._bar_img_obj, text="")
                except Exception:
                    self._bar_preview.configure(text=str(png), image="")
        except Exception:
            pass

    def _print_barcode_label(self):
        try:
            code = (self.var_codigo.get() or "").strip()
            if not code:
                messagebox.showwarning("Código", "Ingrese el Código del producto.")
                return
            size = (self.var_bar_size.get() or "50x30 mm").replace("mm"," ").strip().split("x")
            try:
                w_mm = float(size[0])
                h_mm = float(size[1])
            except Exception:
                w_mm, h_mm = 50, 30
            copies = max(1, int(self.var_bar_copies.get() or 1))
            from src.reports.barcode_label import generate_label_pdf
            text = (self.var_nombre.get().strip() if self.var_bar_text.get() else None) or None
            out = generate_label_pdf(code, text=text, symbology="code128", label_w_mm=w_mm, label_h_mm=h_mm, copies=copies, auto_open=False)
            prn = get_label_printer()
            try:
                print_file_windows(out, printer_name=prn)
                messagebox.showinfo("Etiquetas", f"Enviado a '{prn or 'predeterminada'}'.\nArchivo: {out}")
            except Exception:
                import webbrowser
                webbrowser.open(str(out))
                messagebox.showinfo("Etiquetas", f"PDF generado (abra el visor para imprimir):\n{out}")
        except Exception as ex:
            messagebox.showerror("Etiquetas", f"No se pudo generar etiquetas:\n{ex}")

    def _choose_printer(self):
        try:
            from src.gui.printer_select_dialog import PrinterSelectDialog
        except Exception:
            messagebox.showwarning("Impresoras", "Selector de impresoras no disponible.")
            return
        dlg = PrinterSelectDialog(self)
        self.wait_window(dlg)
        if getattr(dlg, 'result', None):
            messagebox.showinfo("Impresoras", f"seleccionada: {dlg.result}")

    def _on_toggle_has_barcode(self) -> None:
        """Activa/desactiva la etiqueta para el producto actual.
        - Si se activa: guarda Product.barcode = SKU
        - Si se desactiva: guarda Product.barcode = None
        También actualiza la preview y la tabla.
        """
        try:
            p = getattr(self, "_current_product", None)
            if p is None:
                # No hay producto cargado: solo refrescar preview
                self._refresh_barcode_preview()
                return
            code = (self.var_codigo.get() or "").strip()
            if bool(self.var_has_barcode.get()) and code:
                p.barcode = code
            else:
                p.barcode = None
            self.session.commit()
            # actualizar vista y preview
            self._refresh_barcode_preview()
            self._load_table()
        except Exception:
            try:
                self.session.rollback()
            except Exception:
                pass
            # Aun así refrescar preview por si quedó en estado intermedio
            self._refresh_barcode_preview()

    # --------- selección múltiple: aplicar/quitar etiqueta --------- #
    def _get_selected_product_ids(self) -> list[int]:
        """Obtiene IDs de producto de las filas seleccionadas (independiente del orden/ordenamiento)."""
        tv = getattr(self.table, "_fallback", None)
        ids: list[int] = []
        if tv is not None:
            try:
                for iid in tv.selection():
                    vals = list(tv.item(iid, "values"))
                    if not vals:
                        continue
                    try:
                        ids.append(int(vals[0]))
                    except Exception:
                        pass
            except Exception:
                pass
            return sorted(set(ids))
        # tksheet (si en el futuro se activa)
        if hasattr(self.table, "sheet"):
            try:
                rows = list(self.table.sheet.get_selected_rows())
                out: list[int] = []
                for r in rows:
                    if 0 <= r < len(self._rows_cache):
                        try:
                            out.append(int(self._rows_cache[r][0]))
                        except Exception:
                            pass
                return sorted(set(out))
            except Exception:
                return []
        return []

    def _apply_label_to_selection(self, enable: bool) -> None:
        try:
            ids = self._get_selected_product_ids()
            if not ids:
                messagebox.showwarning("Etiquetas", "Seleccione uno o más productos en la tabla.")
                return
            ok = 0
            for pid in ids:
                p = self.session.get(Product, int(pid))
                if p is None:
                    continue
                if enable:
                    code = (getattr(p, 'sku', '') or '').strip()
                    if not code:
                        continue
                    p.barcode = code
                else:
                    p.barcode = None
                ok += 1
            self.session.commit()
            self._load_table()
            # refrescar preview si el producto actual es parte de la selección
            try:
                if self._current_product and self._current_product.id in ids:
                    self.var_has_barcode.set(bool(self._current_product.barcode))
                    self._refresh_barcode_preview()
            except Exception:
                pass
            messagebox.showinfo("Etiquetas", f"{('Marcados' if enable else 'Quitados')} {ok} productos.")
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            messagebox.showerror("Etiquetas", f"No se pudo aplicar a la selección:\n{ex}")

    def _apply_margin_to_selection(self) -> None:
        """Aplica el % de ganancia actual a los productos seleccionados recalculando Precio Venta.
        Usa IVA% de la UI como referencia para calcular P + IVA y luego aplica margen.
        """
        try:
            ids = self._get_selected_product_ids()
            if not ids:
                messagebox.showwarning("Margen", "Seleccione uno o más productos en la tabla.")
                return
            iva = float(self.var_iva.get() or 19.0)
            margen = float(self.var_margen.get() or 0.0)
            updated = 0
            for pid in ids:
                p = self.session.get(Product, int(pid))
                if p is None:
                    continue
                try:
                    pc = float(getattr(p, 'precio_compra', 0) or 0)
                except Exception:
                    pc = 0.0
                if pc <= 0:
                    continue
                monto_iva = pc * (iva / 100.0)
                p_mas_iva = pc + monto_iva
                pventa = (p_mas_iva * (1.0 + margen / 100.0))
                # Redondeo a 2 decimales para compatibilidad con Numeric(12,2)
                try:
                    p.precio_venta = round(float(pventa), 2)
                except Exception:
                    p.precio_venta = float(pventa)
                updated += 1
            self.session.commit()
            self._load_table()
            try:
                if self._current_product and self._current_product.id in ids:
                    # refrescar campo Precio Venta del formulario con el nuevo cálculo
                    pv = self.session.get(Product, int(self._current_product.id)).precio_venta
                    try:
                        self.var_pventa.set(float(pv or 0))
                    except Exception:
                        pass
            except Exception:
                pass
            messagebox.showinfo("Margen", f"Precio de venta recalculado en {updated} productos.")
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            messagebox.showerror("Margen", f"No se pudo aplicar el margen:\n{ex}")

    def _apply_unit_to_selection(self) -> None:
        try:
            ids = self._get_selected_product_ids()
            if not ids:
                messagebox.showwarning("Unidad", "Seleccione uno o más productos en la tabla.")
                return
            unit = (self.var_unidad.get() or "").strip()
            if not unit:
                messagebox.showwarning("Unidad", "Seleccione una unidad en el formulario antes de aplicar.")
                return
            updated = 0
            for pid in ids:
                p = self.session.get(Product, int(pid))
                if p is None:
                    continue
                p.unidad_medida = unit
                updated += 1
            self.session.commit()
            self._load_table()
            messagebox.showinfo("Unidad", f"Unidad aplicada en {updated} productos.")
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            messagebox.showerror("Unidad", f"No se pudo aplicar a la selección:\n{ex}")

    def _apply_supplier_to_selection(self) -> None:
        try:
            ids = self._get_selected_product_ids()
            if not ids:
                messagebox.showwarning("Proveedor", "Seleccione uno o más productos en la tabla.")
                return
            idx = self.cmb_supplier.current()
            if idx is None or idx < 0 or idx >= len(self._suppliers):
                messagebox.showwarning("Proveedor", "Seleccione un proveedor en el formulario antes de aplicar.")
                return
            prov_id = int(self._suppliers[idx].id)
            updated = 0
            for pid in ids:
                p = self.session.get(Product, int(pid))
                if p is None:
                    continue
                p.id_proveedor = prov_id
                updated += 1
            self.session.commit()
            self._load_table()
            self._select_supplier_for_current_product()
            messagebox.showinfo("Proveedor", f"Proveedor aplicado en {updated} productos.")
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            messagebox.showerror("Proveedor", f"No se pudo aplicar a la selección:\n{ex}")

    def _apply_family_to_selection(self) -> None:
        try:
            ids = self._get_selected_product_ids()
            if not ids:
                messagebox.showwarning("Familia", "Seleccione uno o más productos en la tabla.")
                return
            fam = (self.var_familia.get().strip() if hasattr(self, 'var_familia') else '')
            fam_val = fam or None
            updated = 0
            for pid in ids:
                p = self.session.get(Product, int(pid))
                if p is None:
                    continue
                try:
                    p.familia = fam_val
                    updated += 1
                except Exception:
                    pass
            self.session.commit()
            self._load_table()
            messagebox.showinfo("Familia", f"Familia aplicada en {updated} productos.")
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            messagebox.showerror("Familia", f"No se pudo aplicar a la selección:\n{ex}")

    # ----------------- Unidad/Empaque prompts ----------------- #
    def _on_unidad_change(self, _evt=None):
        """Solicita detalle según la unidad elegida.

        - caja  -> "caja x N" (N entero > 0)
        - bolsa -> "bolsa x N" (N entero > 0)
        - kg    -> "kg N"     (N decimal > 0)
        - lt    -> "lt N"     (N decimal > 0)
        - ml    -> "N ml"     (N entero > 0)
        - unidad -> sin prompt
        """
        try:
            base = (self.var_unidad.get() or "unidad").strip().lower()
            if base == "unidad":
                self.var_unidad.set("unidad")
                return
            if base == "caja":
                n = simpledialog.askinteger("Caja", "¿Cajas de cuántas unidades?", minvalue=1, parent=self)
                if n and int(n) > 0:
                    value = f"caja x {int(n)}"
                    self._ensure_unidad_value(value)
                    self.var_unidad.set(value)
                else:
                    self.var_unidad.set("caja")
                return
            if base == "bolsa":
                n = simpledialog.askinteger("Bolsa", "¿Bolsas de cuántas unidades?", minvalue=1, parent=self)
                if n and int(n) > 0:
                    value = f"bolsa x {int(n)}"
                    self._ensure_unidad_value(value)
                    self.var_unidad.set(value)
                else:
                    self.var_unidad.set("bolsa")
                return
            if base == "kg":
                val = simpledialog.askfloat("Kilogramos", "¿De cuántos kg?", minvalue=0.001, parent=self)
                if val and float(val) > 0:
                    value = f"kg {float(val):g}"
                    self._ensure_unidad_value(value)
                    self.var_unidad.set(value)
                else:
                    self.var_unidad.set("kg")
                return
            if base == "lt":
                val = simpledialog.askfloat("Litros", "¿De cuántos litros?", minvalue=0.001, parent=self)
                if val and float(val) > 0:
                    value = f"lt {float(val):g}"
                    self._ensure_unidad_value(value)
                    self.var_unidad.set(value)
                else:
                    self.var_unidad.set("lt")
                return
            if base == "ml":
                nml = simpledialog.askinteger("Mililitros", "¿Cuántos ml tiene el producto?", minvalue=1, parent=self)
                if nml and int(nml) > 0:
                    value = f"{int(nml)} ml"
                    self._ensure_unidad_value(value)
                    self.var_unidad.set(value)
                else:
                    self.var_unidad.set("ml")
                return
        except Exception:
            # No bloquear flujo si hay algún error con el diálogo
            pass

    def _ensure_unidad_value(self, value: str) -> None:
        """Si el valor no está en el combobox (state=readonly), lo agrega temporalmente."""
        try:
            vals = list(self.cmb_unidad["values"] or [])
            if value not in vals:
                self.cmb_unidad["values"] = vals + [value]
        except Exception:
            pass

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

    def _with_pneto(self, rows, iva_ref):
        new_rows = []
        for r in rows:
            try:
                try:
                    pv = float(str(r[8]).replace('.', '').replace(',', '.'))
                except Exception:
                    pv = float(r[8])
            except Exception:
                pv = 0.0
            pneto = round(pv / (1.0 + (float(iva_ref) / 100.0))) if pv else 0
            rr = list(r)
            try:
                rr.insert(7, f"{pneto:.0f}")
            except Exception:
                rr.append(f"{pneto:.0f}")
            new_rows.append(rr)
        return new_rows

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
            monto_iva, p_mas_iva, pventa = calcular_precios(pc, iva, mg)
            self.var_iva_monto.set(monto_iva)
            self.var_p_mas_iva.set(p_mas_iva)
            self.var_pventa.set(pventa)
        except Exception:
            pass

    def _on_auto_calc(self, _evt=None):
        self._recalc_prices()

    # (def _on_unidad_change duplicado eliminado; lógica consolidada arriba)

    # ---------- CRUD ----------
    def _on_add(self):
        try:
            data = self._read_form()
            if not data:
                return
            # Validar unicidad de SKU
            try:
                if self.repo.get_by_sku(str(data.get("sku", ""))):
                    messagebox.showwarning("Duplicado", "Ya existe un producto con ese Código/SKU.")
                    return
            except Exception:
                pass
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
            # Validar unicidad de SKU si cambió
            try:
                new_sku = str(data.get("sku", ""))
                if new_sku and new_sku != getattr(p, "sku", None):
                    other = self.repo.get_by_sku(new_sku)
                    if other and getattr(other, "id", None) != p.id:
                        messagebox.showwarning("Duplicado", "Ya existe un producto con ese Código/SKU.")
                        return
            except Exception:
                pass
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
        """Carga la fila seleccionada al formulario (doble clic)."""
        tv = getattr(self.table, "_fallback", None)
        if tv is not None:
            try:
                sel = tv.selection()
                if sel:
                    vals = list(tv.item(sel[0], "values"))
                    if vals:
                        self._load_form_from_row_values(vals)
                        return
            except Exception:
                pass
        # Fallback a caché (tksheet)
        idx = self._selected_row_index()
        if idx is None or idx < 0 or idx >= len(self._rows_cache):
            return
        vals = self._rows_cache[idx]
        self._load_form_from_row_values(vals)

    def _on_tree_select(self, _event=None):
        """Carga al formulario el primer elemento seleccionado (un clic)."""
        tv = getattr(self.table, "_fallback", None)
        if tv is None:
            return
        try:
            sel = tv.selection()
            if not sel:
                return
            vals = list(tv.item(sel[0], "values"))
            if not vals:
                return
            self._load_form_from_row_values(vals)
        except Exception:
            pass

    def _load_form_from_row_values(self, vals: list[str]) -> None:
        """Rellena el formulario desde una fila de la tabla (lista de valores).
        Evita desincronización con _rows_cache tras ordenar columnas.
        """
        # 0 id, 1 nombre, 2 Código, 3 pcompra, 4 iva, 5 iva_monto, 6 p_mas_iva, 7 margen, 8 pventa, 9 unidad
        try:
            self._editing_id = int(vals[0])
        except Exception:
            return
        try:
            self._current_product = self.repo.get(self._editing_id)
        except Exception:
            self._current_product = None
        # Preferir valores reales desde la BD para evitar errores de formateo (miles/decimales)
        if self._current_product is not None:
            p = self._current_product
            self.var_nombre.set(getattr(p, 'nombre', '') or '')
            self.var_codigo.set(getattr(p, 'sku', '') or '')
            pc = 0.0
            pv = 0.0
            try:
                pc = float(getattr(p, 'precio_compra', 0) or 0)
            except Exception:
                pc = 0.0
            try:
                pv = float(getattr(p, 'precio_venta', 0) or 0)
            except Exception:
                pv = 0.0
            self.var_pc.set(pc)
            # Mantener IVA actual (usuario puede ajustar). Si quieres guardar por-producto, habría que extender el modelo.
            iva = 0.0
            try:
                iva = float(self.var_iva.get() or 19.0)
            except Exception:
                iva = 19.0
            # Derivados
            try:
                monto_iva = pc * (iva / 100.0)
                p_mas_iva = pc + monto_iva
                self.var_iva_monto.set(round(monto_iva))
                self.var_p_mas_iva.set(round(p_mas_iva))
                try:
                    margen = max(0.0, (pv / max(1.0, p_mas_iva) - 1.0) * 100.0)
                except Exception:
                    margen = 0.0
                self.var_margen.set(round(margen))
            except Exception:
                self.var_iva_monto.set(0.0)
                self.var_p_mas_iva.set(0.0)
                self.var_margen.set(30.0)
            self.var_pventa.set(pv)
            # Unidad
            try:
                unidad_val = getattr(p, 'unidad_medida', None) or 'unidad'
                self._ensure_unidad_value(unidad_val)
                self.var_unidad.set(unidad_val)
            except Exception:
                self.var_unidad.set('unidad')
        else:
            # Fallback a los valores del row si algo falló
            self.var_nombre.set(vals[1])
            self.var_codigo.set(vals[2])
            try: self.var_pc.set(self._num(vals[3]))
            except Exception: self.var_pc.set(0.0)
            try: self.var_iva.set(self._num(vals[4]) or 19.0)
            except Exception: self.var_iva.set(19.0)
            try: self.var_iva_monto.set(self._num(vals[5]))
            except Exception: self.var_iva_monto.set(0.0)
            try: self.var_p_mas_iva.set(self._num(vals[6]))
            except Exception: self.var_p_mas_iva.set(0.0)
            try: self.var_margen.set(self._num(vals[7]) or 30.0)
            except Exception: self.var_margen.set(30.0)
            try: self.var_pventa.set(self._num(vals[8]))
            except Exception: self.var_pventa.set(0.0)
            try:
                unidad_val = vals[9] or "unidad"
                self._ensure_unidad_value(unidad_val)
                self.var_unidad.set(unidad_val)
            except Exception: self.var_unidad.set("unidad")

        if self._current_product and self._current_product.id:
            self.img_box.set_product(self._current_product.id, on_image_changed=self._on_image_changed)
        else:
            self.img_box.set_product(None)

        self._select_supplier_for_current_product()

        self.btn_save.config(state="disabled")
        self.btn_update.config(state="normal")
        self.btn_delete.config(state="normal")

        # Refrescar preview de Código de Barras (SKU)
        try:
            # Si el producto tiene 'barcode' almacenado, el toggle queda activado. En esta app usamos el SKU como valor.
            try:
                self.var_has_barcode.set(bool(getattr(self._current_product, 'barcode', None)))
            except Exception:
                self.var_has_barcode.set(False)
            self._refresh_barcode_preview()
        except Exception:
            pass
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
            familia = (self.var_familia.get().strip() if hasattr(self, 'var_familia') else '')
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
            # Valor de 'barcode': si el producto tiene etiqueta, usamos el SKU; de lo contrario, None.
            barcode_val = (codigo if bool(self.var_has_barcode.get()) else None)
            return dict(
                nombre=nombre,
                sku=codigo,
                precio_compra=pc,
                precio_venta=pventa,
                unidad_medida=unidad,
                familia=(familia or None),
                id_proveedor=proveedor.id,
                id_ubicacion=location_id,
                barcode=barcode_val,
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
        self.var_p_mas_iva.set(0.0)
        self.var_pventa.set(0.0)
        self.img_box.set_product(None)
        self.btn_save.config(state="normal")
        self.btn_update.config(state="disabled")
        self.btn_delete.config(state="disabled")
        # Reset preview de Código de Barras
        try:
            self.var_has_barcode.set(False)
            self._bar_preview.configure(text="(sin Código)", image="")
            self._bar_img_obj = None
        except Exception:
            pass
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

    # ---- Utilidad: igualar Tamaño del panel de Código de Barras al recuadro de imagen ----
    def _setup_bar_same_size_as_image(self) -> None:
        def _sync(_evt=None) -> None:
            try:
                # Calcular Tamaño real del panel izquierdo (imagen + botones)
                self.update_idletasks()
                lw = self.img_box.winfo_toplevel()  # ensure mapped
            except Exception:
                pass
            try:
                left_parent = self.img_box.master  # el frame 'left'
                left_parent.update_idletasks()
                w = left_parent.winfo_width() or left_parent.winfo_reqwidth()
                h = left_parent.winfo_height() or left_parent.winfo_reqheight()
                # Aplicar dimensiones al Labelframe de Código de Barras
                self._bar_container.configure(width=w, height=h)
                try:
                    self._bar_container.grid_propagate(False)
                except Exception:
                    pass
            except Exception:
                pass

        # Ejecutar una vez y al reconfigurar el panel izquierdo
        _sync()
        try:
            self.img_box.master.bind('<Configure>', _sync, add='+')
        except Exception:
            pass

    def _load_table(self):
        """Carga los productos y calcula columnas derivadas para mostrar."""
        prods: List[Product] = self.session.query(Product).order_by(Product.id.desc()).all()
        iva_ref = float(self.var_iva.get() or 19.0)

        self._rows_cache = []
        self._id_by_index = []

        for p in prods:
            pc = float(p.precio_compra or 0)
            iva_monto, p_mas_iva, _ = calcular_precios(pc, iva_ref, 0)
            try:
                pv = float(p.precio_venta or 0)
                margen = max(0.0, (pv / max(1.0, p_mas_iva) - 1.0) * 100.0)
            except Exception:
                pv = float(p.precio_venta or 0)
                margen = 0.0
            etiqueta = "X" if getattr(p, 'barcode', None) else ""
            row = [
                p.id,
                p.nombre or "",
                p.sku or "",
                f"{pc:.0f}",
                f"{iva_ref:.1f}",
                f"{iva_monto:.0f}",
                f"{p_mas_iva:.0f}",
                f"{round(margen):.0f}",
                f"{pv:.0f}",
                p.unidad_medida or "",
                etiqueta,
            ]
            self._rows_cache.append(row)
            self._id_by_index.append(int(p.id))
        # Insertar columna ' + "'P. Neto'" + ' basada en Precio Venta y el IVA de referencia
        try:
            for _row in []:
                pv = 0.0
                try:
                    pv = float(str(_row[8]).replace('.', '').replace(',', '.'))
                except Exception:
                    try:
                        pv = float(_row[8])
                    except Exception:
                        pv = 0.0
                pneto = round(pv / (1.0 + (iva_ref / 100.0))) if pv else 0
                _row.insert(7, f"{pneto:.0f}")
        except Exception:
            pass

        self._set_table_data(self._with_pneto(self._rows_cache, iva_ref))

    def _apply_table_filter(self) -> None:
        """Aplica filtro por ID, Código (SKU) y Nombre (aproximación)."""
        id_q = (self.var_q_id.get() or "").strip()
        code_q = (self.var_q_code.get() or "").strip().lower()
        name_q = (self.var_q_name.get() or "").strip().lower()

        q = self.session.query(Product)
        # ID exacto si es numérico
        if id_q:
            try:
                q = q.filter(Product.id == int(id_q))
            except Exception:
                # si no es número, ignorar ID para evitar errores
                pass
        if code_q:
            q = q.filter(func.lower(Product.sku).like(f"%{code_q}%"))
        if name_q:
            q = q.filter(func.lower(Product.nombre).like(f"%{name_q}%"))

        prods: List[Product] = q.order_by(Product.id.desc()).all()

        # Reutiliza el mismo formato de filas
        iva_ref = float(self.var_iva.get() or 19.0)
        self._rows_cache = []
        self._id_by_index = []
        for p in prods:
            pc = float(p.precio_compra or 0)
            iva_monto, p_mas_iva, _ = calcular_precios(pc, iva_ref, 0)
            try:
                pv = float(p.precio_venta or 0)
                margen = max(0.0, (pv / max(1.0, p_mas_iva) - 1.0) * 100.0)
            except Exception:
                pv = float(p.precio_venta or 0)
                margen = 0.0
            etiqueta = "X" if getattr(p, 'barcode', None) else ""
            row = [
                p.id,
                p.nombre or "",
                p.sku or "",
                f"{pc:.0f}",
                f"{iva_ref:.1f}",
                f"{iva_monto:.0f}",
                f"{p_mas_iva:.0f}",
                f"{round(margen):.0f}",
                f"{pv:.0f}",
                p.unidad_medida or "",
                etiqueta,
            ]
            self._rows_cache.append(row)
            self._id_by_index.append(int(p.id))        # Insertar columna ' + "'P. Neto'" + ' basada en Precio Venta y el IVA de referencia
        try:
            for _row in []:
                pv = 0.0
                try:
                    pv = float(str(_row[8]).replace('.', '').replace(',', '.'))
                except Exception:
                    try:
                        pv = float(_row[8])
                    except Exception:
                        pv = 0.0
                pneto = round(pv / (1.0 + (iva_ref / 100.0))) if pv else 0
                _row.insert(7, f"{pneto:.0f}")
        except Exception:
            pass
        self._set_table_data(self._with_pneto(self._rows_cache, iva_ref))

    def refresh_lookups(self):
        """Carga proveedores y Ubicaciones a los combobox."""
        self._suppliers = self.session.query(Supplier).order_by(Supplier.razon_social.asc()).all()
        self._locations = self.session.query(Location).order_by(Location.nombre.asc()).all()
        # Familias: desde tabla families (si existe) + valores distintos en productos
        try:
            from src.data.models import Family
            fams = [ (f.nombre or '').strip() for f in self.session.query(Family).order_by(Family.nombre.asc()).all() ]
        except Exception:
            fams = []
        try:
            from sqlalchemy import func as _f
            extra = [ (s or '').strip() for (s,) in self.session.query(_f.distinct(Product.familia)).filter(Product.familia.isnot(None)).all() ]
        except Exception:
            extra = []
        fam_set = sorted([x for x in set([*fams, *extra]) if x])
        try:
            self.cmb_familia["values"] = fam_set
        except Exception:
            pass

        def _disp(s: Supplier) -> str:
            rut = (s.rut or "").strip()
            rs = (s.razon_social or "").strip()
            return f"{rs} - {rut}" if rut else rs

        self.cmb_supplier["values"] = [_disp(s) for s in self._suppliers]
        # selecciona automáticamente si solo hay un proveedor
        if len(self._suppliers) == 1:
            self.cmb_supplier.current(0)
        # Ubicaciones
        if hasattr(self, 'cmb_location'):
            try:
                self.cmb_location["values"] = [(l.nombre or "").strip() for l in self._locations]
            except Exception:
                pass

    def _select_supplier_for_current_product(self):
        """selecciona en los combos proveedor y Ubicación del producto cargado (si existe)."""
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
            messagebox.showerror("Ubicaciones", "No se pudo cargar el administrador de Ubicaciones.")
            return
        dlg = LocationsManager(self.session, parent=self)
        self.wait_window(dlg)
        # Refrescar lista tras cerrar
        self.refresh_lookups()
        self._select_supplier_for_current_product()

    def _open_families_manager(self):
        try:
            from src.gui.families_manager import FamiliesManager
        except Exception:
            messagebox.showerror("Familias", "No se pudo cargar el administrador de familias.")
            return
        dlg = FamiliesManager(self.session, parent=self)
        self.wait_window(dlg)
        # Refrescar lista tras cerrar
        self.refresh_lookups()

    # ---------- Solo fallback: limpiar selección al click de encabezado ----------
    def _on_tree_click(self, event):
        tv = getattr(self.table, "_fallback", None)
        if tv is None:
            return
        region = tv.identify("region", event.x, event.y)
        if region == "heading":
            tv.selection_remove(tv.selection())
            self._clear_form()









    def _apply_location_to_selection(self) -> None:
        """Aplica la Ubicación seleccionada en el combo a los productos marcados."""
        try:
            ids = self._get_selected_product_ids()
            if not ids:
                messagebox.showwarning("Ubicación", "Seleccione uno o más productos en la tabla.")
                return
            # Obtener nombre seleccionado en el combo
            try:
                sel_name = (self.cmb_location.get() or "").strip()
            except Exception:
                sel_name = ""
            if not sel_name:
                messagebox.showwarning("Ubicación", "Seleccione una Ubicación en el formulario antes de aplicar.")
                return
            # Resolver id de Ubicación a partir del nombre
            loc_id = None
            try:
                for l in self._locations:
                    if (l.nombre or "").strip() == sel_name:
                        loc_id = int(l.id)
                        break
            except Exception:
                pass
            if loc_id is None:
                messagebox.showwarning("Ubicación", "No se pudo determinar la Ubicación seleccionada.")
                return
            # Aplicar a cada producto
            updated = 0
            for pid in ids:
                p = self.session.get(Product, int(pid))
                if p is None:
                    continue
                try:
                    p.id_ubicacion = loc_id
                    updated += 1
                except Exception:
                    pass
            self.session.commit()
            self._load_table()
            try:
                if self._current_product and self._current_product.id in ids:
                    # Refrescar selección del combo para el producto actual
                    self._select_supplier_for_current_product()
            except Exception:
                pass
            messagebox.showinfo("Ubicación", f"Ubicación aplicada en {updated} productos.")
        except Exception as ex:
            try:
                self.session.rollback()
            except Exception:
                pass
            messagebox.showerror("Ubicación", f"No se pudo aplicar a la selección:\n{ex}")





































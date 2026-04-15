from __future__ import annotations

import configparser
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from typing import Callable

from PIL import Image, ImageTk
from sqlalchemy import func
from sqlalchemy.orm import Session
from tkinter import ttk

from src.app_meta import get_current_version
from src.data.models import Customer, Product, Purchase, Sale, Supplier


CONFIG_PATH = Path("config/settings.ini")


class HomeView(ttk.Frame):
    def __init__(
        self,
        master: tk.Misc,
        *,
        session: Session,
        callbacks: dict[str, Callable[[], None]],
        show_sidebar: bool = True,
    ) -> None:
        super().__init__(master, padding=0)
        self.session = session
        self.callbacks = callbacks
        self.show_sidebar = show_sidebar
        self._logo_img = None
        self._company_name = "Inventario App"
        self._version = get_current_version()
        self._db_label = "SQLite"

        self.var_active = tk.StringVar(value="Inicio")
        self.var_products = tk.StringVar(value="0")
        self.var_stock = tk.StringVar(value="0")
        self.var_pending = tk.StringVar(value="0")
        self.var_suppliers = tk.StringVar(value="0")
        self.var_customers = tk.StringVar(value="0")
        self.var_sales = tk.StringVar(value="0")
        self.var_health = tk.StringVar(value="Listo para operar")
        self.var_db = tk.StringVar(value="Sin conexión")
        self.var_company = tk.StringVar(value=self._company_name)
        self.var_version = tk.StringVar(value=f"Versión instalada: {self._version}")
        self.var_operation_copy = tk.StringVar(value="Panel central para compras, ventas e inventario.")
        self._responsive_job = None
        self._content_parent = None
        self._hero_copy_label = None
        self._main_description_label = None
        self._side_panel = None
        self._side_info_labels: list[ttk.Label] = []
        self._step_text_labels: list[ttk.Label] = []
        self._metric_body_labels: list[ttk.Label] = []
        self._mode_buttons: list[ttk.Button] = []
        self._cards_left = None
        self._main_panel = None

        self._load_company_info()
        self._configure_styles()
        self._build_ui()
        self.bind("<Configure>", self._on_resize, add="+")
        self.refresh_all()

    def _load_company_info(self) -> None:
        cfg = configparser.ConfigParser()
        try:
            if CONFIG_PATH.exists():
                cfg.read(CONFIG_PATH, encoding="utf-8")
        except Exception:
            return

        self._company_name = cfg.get("company", "name", fallback=self._company_name)
        self.var_company.set(self._company_name)
        self.var_operation_copy.set(
            f"Centro operativo para {self._company_name.lower()} con acceso rápido a compras, ventas e inventario."
        )
        logo_path = cfg.get("company", "logo", fallback="").strip()
        self._load_logo(logo_path)

    def _load_logo(self, logo_path: str) -> None:
        if not logo_path:
            return
        try:
            path = Path(logo_path)
            if not path.is_absolute():
                path = Path.cwd() / path
            img = Image.open(path).convert("RGBA")
            img.thumbnail((220, 220))
            self._logo_img = ImageTk.PhotoImage(img)
        except Exception:
            self._logo_img = None

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        base_font = tkfont.nametofont("TkDefaultFont")
        family = base_font.actual("family")

        style.configure("HomeRoot.TFrame", background="#E6EDF5")
        style.configure("HomeSidebar.TFrame", background="#0D1B2A")
        style.configure("HomeSidebarCard.TFrame", background="#16283D", relief="solid", borderwidth=1)
        style.configure("HomeSidebarPanel.TFrame", background="#102337", relief="solid", borderwidth=1)
        style.configure("HomeContent.TFrame", background="#E6EDF5")
        style.configure("HomeHero.TFrame", background="#FBFDFF", relief="solid", borderwidth=1)
        style.configure("HomeCard.TFrame", background="#FFFFFF", relief="solid", borderwidth=1)
        style.configure("HomeInfoCard.TFrame", background="#F5F9FD", relief="solid", borderwidth=1)
        style.configure("HomeSidebar.TLabel", background="#0D1B2A", foreground="#D5E4F4", font=(family, 10))
        style.configure("HomeBrand.TLabel", background="#16283D", foreground="#FFFFFF", font=(family, 24, "bold"))
        style.configure("HomeSmall.TLabel", background="#16283D", foreground="#D5E4F4", font=(family, 10))
        style.configure("HomeSection.TLabel", background="#102337", foreground="#93B4D5", font=(family, 10, "bold"))
        style.configure("HomeHeroTitle.TLabel", background="#FBFDFF", foreground="#0A2B4F", font=(family, 30, "bold"))
        style.configure("HomeHeroText.TLabel", background="#FBFDFF", foreground="#556C86", font=(family, 11))
        style.configure("HomeMode.TButton", background="#DCE7F4", foreground="#123457", padding=(20, 13), font=(family, 10, "bold"))
        style.map("HomeMode.TButton", background=[("active", "#C9D9EE")])
        style.configure("HomeModeAccent.TButton", background="#2457A6", foreground="#FFFFFF", padding=(20, 13), font=(family, 10, "bold"))
        style.map("HomeModeAccent.TButton", background=[("active", "#2E67C0")], foreground=[("active", "#FFFFFF")])
        style.configure("HomeTitle.TLabel", background="#FFFFFF", foreground="#667C96", font=(family, 10))
        style.configure("HomeValue.TLabel", background="#FFFFFF", foreground="#05284D", font=(family, 17, "bold"))
        style.configure("HomeBody.TLabel", background="#FFFFFF", foreground="#5B718A", font=(family, 10))
        style.configure("HomePanelTitle.TLabel", background="#FFFFFF", foreground="#0C2B4F", font=(family, 15, "bold"))
        style.configure("HomePanelText.TLabel", background="#FFFFFF", foreground="#556C86", font=(family, 10))
        style.configure("HomeImage.TLabel", background="#FFFFFF")
        style.configure("HomeInfoTitle.TLabel", background="#F5F9FD", foreground="#153A60", font=(family, 10, "bold"))
        style.configure("HomeInfoText.TLabel", background="#F5F9FD", foreground="#59708A", font=(family, 10))
        style.configure("HomeNav.TButton", background="#18324C", foreground="#FFFFFF", padding=(14, 12), font=(family, 10, "bold"))
        style.map("HomeNav.TButton", background=[("active", "#234565")], foreground=[("active", "#FFFFFF")])
        style.configure("HomeUpdate.TButton", background="#C8841A", foreground="#FFFFFF", padding=(14, 12), font=(family, 10, "bold"))
        style.map("HomeUpdate.TButton", background=[("active", "#D5942D")], foreground=[("active", "#FFFFFF")])
        style.configure("HomeExit.TButton", background="#A62C3E", foreground="#FFFFFF", padding=(14, 12), font=(family, 10, "bold"))
        style.map("HomeExit.TButton", background=[("active", "#BC3750")], foreground=[("active", "#FFFFFF")])
        style.configure("HomeStepNum.TLabel", background="#14314D", foreground="#FFFFFF", font=(family, 12, "bold"), anchor="center")
        style.configure("HomeStepTitle.TLabel", background="#FFFFFF", foreground="#0A2E53", font=(family, 11, "bold"))
        style.configure("HomeStepText.TLabel", background="#FFFFFF", foreground="#5B708B", font=(family, 10))

    def _build_ui(self) -> None:
        self.configure(style="HomeRoot.TFrame")
        self.rowconfigure(0, weight=1)
        if self.show_sidebar:
            self.columnconfigure(0, weight=0)
            self.columnconfigure(1, weight=1)
            sidebar = ttk.Frame(self, style="HomeSidebar.TFrame", width=285, padding=14)
            sidebar.grid(row=0, column=0, sticky="nsw")
            sidebar.grid_propagate(False)
            sidebar.columnconfigure(0, weight=1)
            self._build_sidebar(sidebar)
            content_column = 1
            content_padding = (18, 18, 18, 8)
        else:
            self.columnconfigure(0, weight=1)
            content_column = 0
            content_padding = (0, 0, 0, 0)

        content = ttk.Frame(self, style="HomeContent.TFrame", padding=content_padding)
        content.grid(row=0, column=content_column, sticky="nsew")
        content.columnconfigure(0, weight=3)
        content.columnconfigure(1, weight=2)
        self._content_parent = content
        self._build_content(content)

    def _build_sidebar(self, parent: ttk.Frame) -> None:
        brand = ttk.Frame(parent, style="HomeSidebarCard.TFrame", padding=20)
        brand.grid(row=0, column=0, sticky="ew")
        brand.columnconfigure(0, weight=1)

        ttk.Label(brand, textvariable=self.var_company, style="HomeBrand.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(brand, textvariable=self.var_version, style="HomeSmall.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(brand, text="Interfaz lista para trabajar", style="HomeSmall.TLabel").grid(row=2, column=0, sticky="w", pady=(10, 0))
        ttk.Separator(parent).grid(row=1, column=0, sticky="ew", pady=(18, 12))
        action_card = ttk.Frame(parent, style="HomeSidebarPanel.TFrame", padding=14)
        action_card.grid(row=2, column=0, sticky="ew")
        action_card.columnconfigure(0, weight=1)
        ttk.Label(action_card, text="Acciones disponibles", style="HomeSection.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 8))

        nav_items = [
            ("Inicio", "home"),
            ("Productos", "products"),
            ("Proveedores", "suppliers"),
            ("Clientes", "customers"),
            ("Compras", "purchases"),
            ("Ventas", "sales"),
            ("Inventario", "inventory"),
            ("Órdenes", "orders"),
            ("Informes", "reports"),
            ("Catálogo", "catalog"),
            ("Manuel", "facturion"),
            ("Tutoriales", "tutorials"),
        ]
        row = 1
        for label, key in nav_items:
            cb = self.callbacks.get(key)
            if cb is None:
                continue
            ttk.Button(action_card, text=label, style="HomeNav.TButton", command=cb).grid(row=row, column=0, sticky="ew", pady=5)
            row += 1

        if self.callbacks.get("refresh"):
            ttk.Button(action_card, text="Actualizar panel", style="HomeUpdate.TButton", command=self._refresh_action).grid(
                row=row, column=0, sticky="ew", pady=(14, 6)
            )
            row += 1

        parent.rowconfigure(3, weight=1)
        if self.callbacks.get("exit"):
            ttk.Button(action_card, text="Salir", style="HomeExit.TButton", command=self.callbacks["exit"]).grid(
                row=row + 1, column=0, sticky="ew", pady=(10, 0)
            )

    def _build_content(self, parent: ttk.Frame) -> None:
        hero = ttk.Frame(parent, style="HomeHero.TFrame", padding=26)
        hero.grid(row=0, column=0, columnspan=2, sticky="ew")
        hero.columnconfigure(0, weight=1)
        hero.columnconfigure(1, weight=1)

        hero_text = ttk.Frame(hero, style="HomeHero.TFrame")
        hero_text.grid(row=0, column=0, sticky="nsew")
        ttk.Label(hero_text, text=self._company_name, style="HomeHeroTitle.TLabel").pack(anchor="center", pady=(8, 6))
        self._hero_copy_label = ttk.Label(
            hero_text,
            textvariable=self.var_operation_copy,
            style="HomeHeroText.TLabel",
            wraplength=620,
            justify="center",
        )
        self._hero_copy_label.pack(anchor="center")

        mode_box = ttk.Frame(hero, style="HomeHero.TFrame", padding=(0, 22, 0, 0))
        mode_box.grid(row=1, column=0, columnspan=2, sticky="ew")
        for idx in range(5):
            mode_box.columnconfigure(idx, weight=1)

        mode_items = [
            ("Productos", "products", "HomeModeAccent.TButton"),
            ("Compras", "purchases", "HomeMode.TButton"),
            ("Ventas", "sales", "HomeMode.TButton"),
            ("Inventario", "inventory", "HomeMode.TButton"),
            ("Manuel", "facturion", "HomeMode.TButton"),
        ]
        for idx, (label, key, style_name) in enumerate(mode_items):
            cb = self.callbacks.get(key)
            if cb is None:
                continue
            btn = ttk.Button(mode_box, text=label, style=style_name, command=cb)
            btn.grid(row=0, column=idx, sticky="ew", padx=(0 if idx == 0 else 10, 0), pady=4)
            self._mode_buttons.append(btn)

        cards_left = ttk.Frame(parent, style="HomeContent.TFrame")
        cards_left.grid(row=1, column=0, sticky="nsew", pady=(14, 0), padx=(0, 10))
        for idx in range(3):
            cards_left.columnconfigure(idx, weight=1)
        self._cards_left = cards_left

        self._metric_card(cards_left, 0, "Operación activa", self.var_active, "Módulo listo para continuar.", "#173A5E")
        self._metric_card(cards_left, 1, "Productos registrados", self.var_products, "Catálogo base disponible.", "#2E6D68")
        self._metric_card(cards_left, 2, "Pulso del sistema", self.var_health, "Sincronización y acceso operativo.", "#9B6A2B")

        main_panel = ttk.Frame(parent, style="HomeCard.TFrame", padding=24)
        main_panel.grid(row=2, column=0, sticky="nsew", pady=(12, 0), padx=(0, 10))
        main_panel.columnconfigure(0, weight=1)
        self._main_panel = main_panel

        ttk.Label(main_panel, text="Recorrido recomendado", style="HomePanelTitle.TLabel").grid(row=0, column=0, sticky="w")
        self._main_description_label = ttk.Label(
            main_panel,
            text="Un flujo corto para entrar, cargar datos y validar antes de emitir documentos o ajustar stock.",
            style="HomePanelText.TLabel",
            wraplength=640,
            justify="left",
        )
        self._main_description_label.grid(row=1, column=0, sticky="w", pady=(6, 14))

        if self._logo_img is not None:
            ttk.Label(main_panel, image=self._logo_img, style="HomeImage.TLabel").grid(row=2, column=0, pady=(0, 16))

        steps = [
            ("01", "Revisa el catálogo", "Valida productos, proveedores y clientes antes de empezar la operación del día."),
            ("02", "Carga compras o ventas", "Ingresa los movimientos principales y confirma que los totales queden correctos."),
            ("03", "Controla inventario", "Ajusta stock, exporta informes y deja lista la impresión o el respaldo."),
        ]
        for idx, (num, title, text) in enumerate(steps, start=3):
            self._step_row(main_panel, idx, num, title, text)

        side_panel = ttk.Frame(parent, style="HomeCard.TFrame", padding=20)
        side_panel.grid(row=1, column=1, rowspan=2, sticky="nsew", pady=(14, 0))
        side_panel.columnconfigure(0, weight=1)
        self._side_panel = side_panel

        ttk.Label(side_panel, text="Salud operativa", style="HomePanelTitle.TLabel").grid(row=0, column=0, sticky="w", pady=(2, 12))
        info_items = [
            ("Base de datos", self.var_db),
            ("Stock total", self.var_stock),
            ("Proveedores", self.var_suppliers),
            ("Clientes", self.var_customers),
            ("Ventas confirmadas", self.var_sales),
            ("Compras pendientes", self.var_pending),
        ]
        for row, (title, variable) in enumerate(info_items, start=1):
            box = ttk.Frame(side_panel, style="HomeInfoCard.TFrame", padding=16)
            box.grid(row=row, column=0, sticky="ew", pady=6)
            box.columnconfigure(0, weight=1)
            ttk.Label(box, text=title, style="HomeInfoTitle.TLabel").grid(row=0, column=0, sticky="w")
            info_label = ttk.Label(box, textvariable=variable, style="HomeInfoText.TLabel", wraplength=280, justify="left")
            info_label.grid(row=1, column=0, sticky="w", pady=(6, 0))
            self._side_info_labels.append(info_label)

        parent.rowconfigure(2, weight=1)

    def _metric_card(
        self,
        parent: ttk.Frame,
        column: int,
        title: str,
        value_var: tk.StringVar,
        body: str,
        stripe: str,
    ) -> None:
        style_name = f"HomeStripe{column}.TFrame"
        ttk.Style(self).configure(style_name, background=stripe)

        card = ttk.Frame(parent, style="HomeCard.TFrame")
        card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))
        card.columnconfigure(0, weight=1)
        ttk.Frame(card, style=style_name, height=6).grid(row=0, column=0, sticky="ew")
        body_frame = ttk.Frame(card, style="HomeCard.TFrame", padding=18)
        body_frame.grid(row=1, column=0, sticky="nsew")
        body_frame.columnconfigure(0, weight=1)
        ttk.Label(body_frame, text=title, style="HomeTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(body_frame, textvariable=value_var, style="HomeValue.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 8))
        body_label = ttk.Label(body_frame, text=body, style="HomeBody.TLabel", wraplength=240, justify="left")
        body_label.grid(row=2, column=0, sticky="w")
        self._metric_body_labels.append(body_label)

    def _step_row(self, parent: ttk.Frame, row: int, num: str, title: str, text: str) -> None:
        box = ttk.Frame(parent, style="HomeInfoCard.TFrame", padding=12)
        box.grid(row=row, column=0, sticky="ew", pady=6)
        box.columnconfigure(1, weight=1)

        num_box = ttk.Label(box, text=num, style="HomeStepNum.TLabel", width=4)
        num_box.grid(row=0, column=0, rowspan=2, sticky="nsw", padx=(0, 12))
        ttk.Label(box, text=title, style="HomeStepTitle.TLabel").grid(row=0, column=1, sticky="w")
        step_label = ttk.Label(box, text=text, style="HomeStepText.TLabel", wraplength=560, justify="left")
        step_label.grid(row=1, column=1, sticky="w", pady=(6, 0))
        self._step_text_labels.append(step_label)

    def _on_resize(self, _event=None) -> None:
        try:
            if self._responsive_job is not None:
                self.after_cancel(self._responsive_job)
        except Exception:
            pass
        self._responsive_job = self.after(60, self._apply_responsive_layout)

    def _apply_responsive_layout(self) -> None:
        self._responsive_job = None
        parent = self._content_parent
        if parent is None or not parent.winfo_exists():
            return

        width = max(parent.winfo_width(), self.winfo_width(), 900)
        compact = width < 1450

        if self._hero_copy_label is not None:
            self._hero_copy_label.configure(wraplength=max(420, width - 240))
        if self._main_description_label is not None:
            self._main_description_label.configure(wraplength=max(420, int(width * 0.42)))

        for label in self._metric_body_labels:
            label.configure(wraplength=max(180, int(width * 0.12)))
        for label in self._step_text_labels:
            label.configure(wraplength=max(360, int(width * 0.38)))
        for label in self._side_info_labels:
            label.configure(wraplength=max(220, int(width * 0.18)))

        if self._cards_left is not None:
            if compact:
                for idx in range(3):
                    self._cards_left.columnconfigure(idx, weight=0)
                self._cards_left.columnconfigure(0, weight=1)
            else:
                for idx in range(3):
                    self._cards_left.columnconfigure(idx, weight=1)

        if compact:
            parent.columnconfigure(0, weight=1)
            parent.columnconfigure(1, weight=1)
            if self._cards_left is not None:
                self._cards_left.grid_configure(row=1, column=0, columnspan=2, sticky="nsew", pady=(14, 0), padx=(0, 0))
            if self._main_panel is not None:
                self._main_panel.grid_configure(row=2, column=0, columnspan=2, sticky="nsew", pady=(12, 0), padx=(0, 0))
            if self._side_panel is not None:
                self._side_panel.grid_configure(row=3, column=0, columnspan=2, rowspan=1, sticky="nsew", pady=(12, 0))
        else:
            parent.columnconfigure(0, weight=3)
            parent.columnconfigure(1, weight=2)
            if self._cards_left is not None:
                self._cards_left.grid_configure(row=1, column=0, columnspan=1, sticky="nsew", pady=(14, 0), padx=(0, 10))
            if self._main_panel is not None:
                self._main_panel.grid_configure(row=2, column=0, columnspan=1, sticky="nsew", pady=(12, 0), padx=(0, 10))
            if self._side_panel is not None:
                self._side_panel.grid_configure(row=1, column=1, columnspan=1, rowspan=2, sticky="nsew", pady=(14, 0))

    def _refresh_action(self) -> None:
        self.refresh_all()
        cb = self.callbacks.get("refresh")
        if cb is not None:
            cb()

    def set_active_view(self, name: str) -> None:
        if not name:
            return
        self.var_active.set(name)
        if name == "Inicio":
            self.var_health.set("Listo para operar")
        else:
            self.var_health.set(f"{name} disponible y sincronizado")

    def refresh_all(self) -> None:
        try:
            products = self.session.query(func.count(Product.id)).scalar() or 0
            stock = self.session.query(func.coalesce(func.sum(Product.stock_actual), 0)).scalar() or 0
            suppliers = self.session.query(func.count(Supplier.id)).scalar() or 0
            customers = self.session.query(func.count(Customer.id)).scalar() or 0
            sales = (
                self.session.query(func.count(Sale.id))
                .filter(Sale.estado == "Confirmada")
                .scalar()
                or 0
            )
            pending = (
                self.session.query(func.count(Purchase.id))
                .filter(Purchase.estado == "Pendiente")
                .scalar()
                or 0
            )
            bind = self.session.get_bind()
            backend = bind.url.get_backend_name().upper() if bind is not None else "DB"
            self._db_label = backend

            self.var_products.set(f"{products}")
            self.var_stock.set(f"{stock} unidades")
            self.var_suppliers.set(f"{suppliers} registros")
            self.var_customers.set(f"{customers} registros")
            self.var_sales.set(f"{sales} ventas confirmadas")
            self.var_pending.set(f"{pending} órdenes pendientes")
            self.var_db.set(f"{backend} conectada correctamente")
            if pending > 0:
                self.var_health.set(f"{pending} compras pendientes por revisar")
            elif products == 0:
                self.var_health.set("Carga inicial pendiente")
            else:
                self.var_health.set("Listo para operar")
        except Exception as ex:
            self.var_db.set("No se pudieron leer métricas")
            self.var_health.set(f"Revisión requerida: {ex}")

    def refresh(self) -> None:
        self.refresh_all()

    def refresh_lookups(self) -> None:
        self.refresh_all()

# src/gui/main_window.py
from __future__ import annotations
import sys
import configparser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, Menu

from src.gui.products_view import ProductsView
from src.gui.suppliers_view import SuppliersView
from src.gui.customers_view import CustomersView
from src.gui.purchases_view import PurchasesView
from src.gui.sales_view import SalesView
from src.gui.inventory_view import InventoryView
from src.gui.orders_admin_view import OrdersAdminView
from src.reports.report_center import ReportCenter  # ← NUEVO
from src.gui.catalog_view import CatalogView

from src.gui.theme_manager import ThemeManager
from src.gui.widgets.status_bar import StatusBar
from src.gui.widgets.toast import Toast
from src.gui.widgets.command_palette import CommandPalette, CommandAction

UI_STATE_PATH = Path("config/ui_state.ini")


class MainWindow(ttk.Frame):
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        # ⬇️ NO USAR self._root (colisiona con tk._root())
        self.app_root: tk.Tk = self.winfo_toplevel()

        # Tema y menú
        ThemeManager.attach(self.app_root)
        self._build_menu()

        # Notebook + tabs
        self.notebook = ttk.Notebook(self)
        self.products_tab = ProductsView(self.notebook)
        self.suppliers_tab = SuppliersView(self.notebook)
        self.customers_tab = CustomersView(self.notebook)
        self.purchases_tab = PurchasesView(self.notebook)
        self.sales_tab = SalesView(self.notebook)
        self.inventory_tab = InventoryView(self.notebook)
        self.orders_admin_tab = OrdersAdminView(self.notebook)
        self.report_center_tab = ReportCenter(self.notebook)  # ← NUEVO
        self.catalog_tab = CatalogView(self.notebook)

        self.notebook.add(self.products_tab, text="Productos")
        self.notebook.add(self.suppliers_tab, text="Proveedores")
        self.notebook.add(self.customers_tab, text="Clientes")
        self.notebook.add(self.purchases_tab, text="Compras")
        self.notebook.add(self.sales_tab, text="Ventas")
        self.notebook.add(self.inventory_tab, text="Inventario")
        self.notebook.add(self.orders_admin_tab, text="Órdenes")
        self.notebook.add(self.report_center_tab, text="Informes")  # ← NUEVO
        self.notebook.add(self.catalog_tab, text="Catálogo")

        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

        # Status bar
        self.status = StatusBar(self)
        self.status.pack(side="bottom", fill="x")
        self.status.set_message("Listo")
        self.status.set_info(user="admin", env="dev")
        self.status.set_db_status("OK")

        # Atajos
        self._setup_shortcuts()

        # Persistencia
        self._restore_ui_state()
        self.app_root.bind("<Destroy>", self._on_root_destroy, add="+")

        # Toast de ayuda
        Toast.show(self.app_root, "Ctrl+K: Paleta de comandos", kind="info", ms=1800)

    def _generate_catalog(self) -> None:
        """Genera catálogo PDF de productos (imagen, stock y precio sin IVA)."""
        try:
            from src.reports.catalog_generator import generate_products_catalog
            out = generate_products_catalog(self.products_tab.session, auto_open=True)
            Toast.show(self.app_root, f"Catálogo generado: {out}", kind="success")
        except Exception as ex:
            Toast.show(self.app_root, f"Error al generar catálogo: {ex}", kind="danger", position="tr")

    def _open_db_connection_dialog(self) -> None:
        try:
            from src.gui.db_connection_dialog import DBConnectionDialog
        except Exception as ex:
            Toast.show(self.app_root, f"No se pudo cargar el diálogo de DB: {ex}", kind="danger")
            return
        DBConnectionDialog(self)

    def _build_menu(self) -> None:
        menubar = Menu(self.app_root)
        self.app_root.config(menu=menubar)

        m_file = Menu(menubar, tearoff=False)
        m_file.add_command(label="Paleta de comandos…    Ctrl+K", command=self._open_palette)
        m_file.add_separator()
        m_file.add_command(label="Salir", command=self.app_root.quit)
        menubar.add_cascade(label="Archivo", menu=m_file)

        ThemeManager.build_menu(menubar)

        m_tools = Menu(menubar, tearoff=False)
        m_tools.add_command(label="Nuevo (Ctrl+N)", command=self._new_current)
        m_tools.add_command(label="Guardar (Ctrl+S)", command=self._save_current)
        m_tools.add_command(label="Imprimir (Ctrl+P)", command=self._print_current)
        m_tools.add_command(label="Refrescar aplicacion (F5)", command=self._refresh_all)
        m_tools.add_separator()
        m_tools.add_command(label="Generador de catálogos", command=self._generate_catalog)
        m_tools.add_separator()
        m_tools.add_command(label="Conexión a BD…", command=self._open_db_connection_dialog)
        # Importacion SQL masiva
        m_tools.add_separator()
        m_tools.add_command(label="Importacion SQL masiva...", command=self._open_sql_importer)
        # Limpiador de base de datos (BORRA TODO)
        m_tools.add_separator()
        m_tools.add_command(label="Limpiar base de datos...", command=self._wipe_databases)
        menubar.add_cascade(label="Herramientas", menu=m_tools)

        m_view = Menu(menubar, tearoff=False)
        m_view.add_command(label="Paleta de comandos…", command=self._open_palette)
        m_view.add_command(label="Ir a Informes", command=self.show_report_center)  # ← NUEVO
        menubar.add_cascade(label="Ver", menu=m_view)

    def _setup_shortcuts(self) -> None:
        self.bind_all("<Control-k>", lambda e: self._open_palette())
        self.bind_all("<Control-n>", lambda e: self._new_current())
        self.bind_all("<Control-s>", lambda e: self._save_current())
        self.bind_all("<Control-p>", lambda e: self._print_current())
        # F5 refresca toda la aplicacion
        try:
            self.bind_all("<F5>", lambda e: self._refresh_all())
        except Exception:
            pass

    def _open_palette(self) -> None:
        actions = self._build_actions()
        CommandPalette.open(self.app_root, actions=actions)

    def _build_actions(self) -> list[CommandAction]:
        view = self._current_view()
        actions: list[CommandAction] = [
            CommandAction("go_products", "Ir a Productos", callback=self.show_products, keywords=["inventario", "stock"]),
            CommandAction("go_suppliers", "Ir a Proveedores", callback=self.show_suppliers, keywords=["proveedores"]),
            CommandAction("go_customers", "Ir a Clientes", callback=self.show_customers, keywords=["clientes"]),
            CommandAction("go_purchases", "Ir a Compras", callback=self.show_purchases, keywords=["oc", "orden de compra"]),
            CommandAction("go_sales", "Ir a Ventas", callback=self.show_sales, keywords=["ov", "boletas", "ventas"]),
            CommandAction("go_inventory", "Ir a Inventario", callback=self.show_inventory, keywords=["kardex", "bodega"]),
            CommandAction("go_orders", "Ir a Órdenes", callback=self.show_orders_admin, keywords=["admin", "oc", "ov"]),
            CommandAction("go_reports", "Ir a Informes", callback=self.show_report_center, keywords=["reportes", "informes"]),  # ← NUEVO
            CommandAction("go_catalog", "Ir a Catálogo", callback=self.show_catalog, keywords=["catalogo", "pdf"]),
            CommandAction("act_new", "Nuevo registro", callback=self._new_current, category="Acción", shortcut="Ctrl+N"),
            CommandAction("act_save", "Guardar cambios", callback=self._save_current, category="Acción", shortcut="Ctrl+S"),
            CommandAction("act_print", "Imprimir vista", callback=self._print_current, category="Acción", shortcut="Ctrl+P"),
        ]
        if hasattr(view, "actions") and callable(getattr(view, "actions")):
            try:
                for label, func in view.actions():
                    actions.append(CommandAction(f"view_{label}", label, callback=func, category="Vista"))
            except Exception:
                pass
        return actions

    def _current_view(self) -> ttk.Frame:
        sel = self.notebook.select()
        return self.notebook.nametowidget(sel)

    def _select_tab_by_widget(self, widget: ttk.Frame) -> None:
        self.notebook.select(widget)

    def show_products(self) -> None: self._select_tab_by_widget(self.products_tab)
    def show_suppliers(self) -> None: self._select_tab_by_widget(self.suppliers_tab)
    def show_customers(self) -> None: self._select_tab_by_widget(self.customers_tab)
    def show_purchases(self) -> None: self._select_tab_by_widget(self.purchases_tab)
    def show_sales(self) -> None: self._select_tab_by_widget(self.sales_tab)
    def show_inventory(self) -> None: self._select_tab_by_widget(self.inventory_tab)
    def show_orders_admin(self) -> None: self._select_tab_by_widget(self.orders_admin_tab)
    def show_report_center(self) -> None: self._select_tab_by_widget(self.report_center_tab)  # ← NUEVO
    def show_catalog(self) -> None: self._select_tab_by_widget(self.catalog_tab)

    def _new_current(self) -> None:
        view = self._current_view()
        for name in ("new", "create_new", "new_record"):
            if hasattr(view, name) and callable(getattr(view, name)):
                getattr(view, name)()
                self.status.flash("Nuevo registro", kind="info", ms=1200)
                return
        Toast.show(self.app_root, "La vista actual no soporta 'Nuevo'", kind="warning")

    def _save_current(self) -> None:
        view = self._current_view()
        for name in ("save", "save_changes", "commit"):
            if hasattr(view, name) and callable(getattr(view, name)):
                try:
                    getattr(view, name)()
                    self.status.flash("Guardado con éxito", kind="success", ms=1400)
                except Exception as ex:
                    Toast.show(self.app_root, f"Error al guardar: {ex}", kind="danger", position="tr")
                    self.status.flash("Error al guardar", kind="danger", ms=1400)
                return
        Toast.show(self.app_root, "La vista actual no soporta 'Guardar'", kind="warning")

    def _print_current(self) -> None:
        view = self._current_view()
        for name in ("print_current", "print_inventory", "print", "export_pdf"):  # ← incluye print_inventory
            if hasattr(view, name) and callable(getattr(view, name)):
                try:
                    self.status.progress_start(indeterminate=True)
                    getattr(view, name)()
                    self.status.progress_hide()
                    self.status.flash("Impresión enviada", kind="success", ms=1400)
                except Exception as ex:
                    self.status.progress_hide()
                    Toast.show(self.app_root, f"Error al imprimir: {ex}", kind="danger", position="tr")
                    self.status.flash("Error al imprimir", kind="danger", ms=1400)
                return
        Toast.show(self.app_root, "La vista actual no soporta 'Imprimir'", kind="warning")

    def _on_tab_change(self, _event=None):
        w = self._current_view()
        if hasattr(w, "refresh_lookups"):
            try:
                w.refresh_lookups()
            except Exception as ex:
                print(f"Error al refrescar lookups: {ex}", file=sys.stderr)
        tab_text = self.notebook.tab(self.notebook.select(), "text")
        self.status.set_message(f"Vista: {tab_text} — Ctrl+K para comandos")
        self._save_last_tab_index()

    def _restore_ui_state(self) -> None:
        cfg = configparser.ConfigParser()
        if UI_STATE_PATH.exists():
            cfg.read(UI_STATE_PATH, encoding="utf-8")
        geom = cfg.get("mainwindow", "geometry", fallback="")
        if geom:
            # Restaura la geometría, pero asegúrate de que quede visible
            try:
                self.app_root.geometry(geom)
            except Exception:
                pass
            self._ensure_on_screen()
        else:
            # Si no hay geometría guardada, centra dentro de la pantalla actual
            self._center_on_screen()
        last_idx = cfg.getint("mainwindow", "last_tab_index", fallback=0)
        try:
            self.notebook.select(last_idx)
        except Exception:
            pass

    def _ensure_on_screen(self) -> None:
        """Garantiza que la ventana esté dentro de los límites visibles.
        Si la geometría previa estaba en un monitor secundario ausente,
        reubica/clampa la ventana para que sea visible.
        """
        root = self.app_root
        try:
            root.update_idletasks()
            # Tamaños actuales (si aún no se calculan, usa requeridos)
            w = root.winfo_width() or root.winfo_reqwidth()
            h = root.winfo_height() or root.winfo_reqheight()
            # Posición actual
            x = root.winfo_x()
            y = root.winfo_y()
            # Tamaño de escritorio virtual (múltiples monitores)
            v_w = max(getattr(root, 'winfo_vrootwidth', lambda: 0)() or 0, root.winfo_screenwidth())
            v_h = max(getattr(root, 'winfo_vrootheight', lambda: 0)() or 0, root.winfo_screenheight())

            # Clamps seguros
            w = min(w, v_w)
            h = min(h, v_h)
            new_x = min(max(x, 0), max(v_w - w, 0))
            new_y = min(max(y, 0), max(v_h - h, 0))

            if new_x != x or new_y != y:
                root.geometry(f"{w}x{h}+{new_x}+{new_y}")
        except Exception:
            # Ante cualquier error, como último recurso centra
            self._center_on_screen()

    def _center_on_screen(self) -> None:
        """Centra la ventana en la pantalla principal actual."""
        root = self.app_root
        try:
            root.update_idletasks()
            w = root.winfo_width() or root.winfo_reqwidth()
            h = root.winfo_height() or root.winfo_reqheight()
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            x = max(0, int((sw - w) / 2))
            y = max(0, int((sh - h) / 2))
            root.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            pass

    def _save_last_tab_index(self) -> None:
        idx = self._safe_current_index()
        cfg = configparser.ConfigParser()
        if UI_STATE_PATH.exists():
            cfg.read(UI_STATE_PATH, encoding="utf-8")
        cfg.setdefault("mainwindow", {})
        cfg["mainwindow"]["last_tab_index"] = str(idx)
        UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with UI_STATE_PATH.open("w", encoding="utf-8") as f:
            cfg.write(f)

    def _on_root_destroy(self, event) -> None:
        if event.widget is not self.app_root:
            return
        try:
            geom = self.app_root.winfo_geometry()
            cfg = configparser.ConfigParser()
            if UI_STATE_PATH.exists():
                cfg.read(UI_STATE_PATH, encoding="utf-8")
            cfg.setdefault("mainwindow", {})
            cfg["mainwindow"]["geometry"] = geom
            cfg["mainwindow"]["last_tab_index"] = str(self._safe_current_index())
            UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with UI_STATE_PATH.open("w", encoding="utf-8") as f:
                cfg.write(f)
        except Exception:
            pass

    def _safe_current_index(self) -> int:
        try:
            return self.notebook.index(self.notebook.select())
        except Exception:
            return 0

    def _wipe_databases(self) -> None:
        """Elimina TODOS los datos de la BD ORM y del ERP simple. IRREVERSIBLE."""
        try:
            from tkinter import messagebox
        except Exception:
            return
        if not messagebox.askyesno(
            "Limpiar base de datos",
            "Esto eliminará TODOS los registros (productos, proveedores, clientes,\n"
            "ventas, compras, inventario y documentos ERP).\n\n¿Desea continuar?",
            parent=self.app_root,
        ):
            return

        # 1) Limpiar ORM (SQLAlchemy)
        try:
            from sqlalchemy.orm import Session as _S
            from src.data.models import (
                SaleDetail, Sale, PurchaseDetail, Purchase,
                StockEntry, StockExit, Product, Supplier, Customer, Location,
            )
            sess: _S = self.products_tab.session
            # Orden seguro respetando FKs
            sess.query(SaleDetail).delete()
            sess.query(Sale).delete()
            sess.query(PurchaseDetail).delete()
            sess.query(Purchase).delete()
            sess.query(StockEntry).delete()
            sess.query(StockExit).delete()
            sess.query(Product).delete()
            sess.query(Supplier).delete()
            sess.query(Customer).delete()
            sess.query(Location).delete()
            sess.commit()
        except Exception as ex:
            try:
                Toast.show(self.app_root, f"Error limpiando ORM: {ex}", kind="danger", position="tr")
            except Exception:
                pass
            return

        # 2) Limpiar ERP (sqlite simple) si existe
        try:
            from src.erp.core.database import get_connection, DEFAULT_DB_PATH
            conn = get_connection(DEFAULT_DB_PATH)
            try:
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("DELETE FROM detalles;")
                conn.execute("DELETE FROM documentos;")
                conn.execute("DELETE FROM log_auditoria;")
                conn.commit()
            finally:
                conn.close()
        except Exception:
            # Si no existe o falla, lo omitimos silenciosamente
            pass

        # 3) Notificar
        try:
            Toast.show(self.app_root, "Base de datos limpiada", kind="success")
        except Exception:
            messagebox.showinfo("BD", "Base de datos limpiada")

    def _seed_surt_fake(self) -> None:
        """Seed SURT VENTAS (fake): proveedor + productos, opcional compra/stock."""
        try:
            from tkinter import messagebox
            from scripts import seed_surt_ventas as seed
        except Exception as ex:
            try:
                Toast.show(self.app_root, f"No se pudo cargar seed: {ex}", kind="danger")
            except Exception:
                pass
            return

        if not messagebox.askyesno(
            "Sembrar SURT",
            "Se insertaran/actualizaran proveedor y productos basicos.\n\n¿Continuar?",
            parent=self.app_root,
        ):
            return

        try:
            create_purchase = messagebox.askyesno(
                "Sembrar SURT",
                "¿Crear tambien una Orden de Compra (Pendiente)?",
                parent=self.app_root,
            )
            sum_stock = messagebox.askyesno(
                "Sembrar SURT",
                "¿Sumar stock segun cantidades de la orden?",
                parent=self.app_root,
            )

            session = self.products_tab.session
            supplier = seed.ensure_supplier(session, **seed.SUPPLIER)
            seed.upsert_products(session, supplier, seed.ITEMS, margen_pct=30.0)
            if create_purchase:
                seed.create_purchase(session, supplier, seed.ITEMS, estado="Pendiente")
            if sum_stock:
                seed.sum_stock(session, seed.ITEMS)

            Toast.show(self.app_root, "Seed SURT completado", kind="success")
        except Exception as ex:
            Toast.show(self.app_root, f"Fallo seed SURT: {ex}", kind="danger", position="tr")
    
    def _open_sql_importer(self) -> None:
        try:
            from src.gui.sql_importer_dialog import SqlMassImporter
            SqlMassImporter(self)
        except Exception as ex:
            try:
                Toast.show(self.app_root, f"No se pudo abrir importador SQL: {ex}", kind="danger")
            except Exception:
                pass

    def _refresh_all(self) -> None:
        """Refresca todas las pestañas de la aplicacion de forma segura."""
        views = [
            getattr(self, "products_tab", None),
            getattr(self, "suppliers_tab", None),
            getattr(self, "customers_tab", None),
            getattr(self, "purchases_tab", None),
            getattr(self, "sales_tab", None),
            getattr(self, "inventory_tab", None),
            getattr(self, "orders_admin_tab", None),
            getattr(self, "report_center_tab", None),
            getattr(self, "catalog_tab", None),
        ]
        for v in views:
            if v is None:
                continue
            for name in ("refresh_all", "refresh", "refresh_table", "refresh_lookups"):
                try:
                    fn = getattr(v, name, None)
                    if callable(fn):
                        fn()
                        break
                except Exception:
                    pass
        try:
            self.status.flash("Aplicacion refrescada", kind="info", ms=1200)
        except Exception:
            pass

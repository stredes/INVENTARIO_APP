from __future__ import annotations
import tkinter as tk
from tkinter import ttk

from src.gui.products_view import ProductsView
from src.gui.suppliers_view import SuppliersView
from src.gui.customers_view import CustomersView
from src.gui.purchases_view import PurchasesView
from src.gui.sales_view import SalesView
from src.gui.inventory_view import InventoryView


class MainWindow(ttk.Frame):
    """
    Ventana principal con Notebook (pestañas):
    - Productos
    - Proveedores
    - Clientes
    - Compras
    - Ventas
    - Inventario
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        self.notebook = ttk.Notebook(self)

        self.products_tab = ProductsView(self.notebook)
        self.suppliers_tab = SuppliersView(self.notebook)
        self.customers_tab = CustomersView(self.notebook)
        self.purchases_tab = PurchasesView(self.notebook)
        self.sales_tab = SalesView(self.notebook)
        self.inventory_tab = InventoryView(self.notebook)

        # 👉 usar keyword text=...
        self.notebook.add(self.products_tab, text="Productos")
        self.notebook.add(self.suppliers_tab, text="Proveedores")
        self.notebook.add(self.customers_tab, text="Clientes")
        self.notebook.add(self.purchases_tab, text="ocmpra")
        self.notebook.add(self.sales_tab, text="ocventa")
        self.notebook.add(self.inventory_tab, text="Inventario")

        self.notebook.pack(fill="both", expand=True)
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_change)

    def _on_tab_change(self, _event=None):
        w = self.notebook.nametowidget(self.notebook.select())
        if hasattr(w, "refresh_lookups"):
            try:
                w.refresh_lookups()
            except Exception:
                pass

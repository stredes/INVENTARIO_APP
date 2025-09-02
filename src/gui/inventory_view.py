from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox

from typing import List, Optional

from src.data.database import get_session
from src.data.models import Product
from src.data.repository import ProductRepository
from src.utils.helpers import (
    get_inventory_limits,
    set_inventory_limits,
    get_inventory_refresh_ms,
    set_inventory_refresh_ms,
)


class InventoryView(ttk.Frame):
    """
    Vista de Inventario con:
    - Tabla de productos y stock actual
    - Resaltado por límites críticos (min / max)
    - Auto-refresco configurable (ms)
    - Panel de configuración para límites y refresco
    """
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)

        # --- Estado / repos ---
        self.session = get_session()
        self.repo = ProductRepository(self.session)

        self._auto_job: Optional[str] = None
        self._auto_enabled = tk.BooleanVar(value=True)

        # Lee configuración inicial
        min_v, max_v = get_inventory_limits()
        self._crit_min = tk.IntVar(value=min_v)
        self._crit_max = tk.IntVar(value=max_v)
        self._refresh_ms = tk.IntVar(value=get_inventory_refresh_ms())

        # --- Encabezado ---
        header = ttk.Frame(self)
        header.pack(fill="x", expand=False)
        ttk.Label(header, text="Inventario (refresco automático)", font=("", 11, "bold")).pack(side="left")

        ttk.Button(header, text="Refrescar ahora", command=self.refresh_table).pack(side="right", padx=4)
        ttk.Checkbutton(header, text="Auto", variable=self._auto_enabled, command=self._on_toggle_auto).pack(side="right")

        # --- Tabla ---
        self.tree = ttk.Treeview(
            self,
            columns=("id", "nombre", "sku", "unidad", "stock", "p_compra", "p_venta"),
            show="headings",
            height=16,
        )
        for col, text, w, anchor in [
            ("id", "ID", 60, "center"),
            ("nombre", "Producto", 260, "w"),
            ("sku", "SKU", 140, "w"),
            ("unidad", "Unidad", 80, "center"),
            ("stock", "Stock", 90, "e"),
            ("p_compra", "P. Compra", 100, "e"),
            ("p_venta", "P. Venta", 100, "e"),
        ]:
            self.tree.heading(col, text=text)
            self.tree.column(col, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, pady=(8, 10))

        # Tags (colores)
        # Nota: ttk.Treeview no admite color por defecto de forma global con theme.
        # Usamos 'tags' por fila; el estilo depende del tema, pero suele funcionar.
        self.tree.tag_configure("low", background="#ffdddd")      # rojo claro (stock < min)
        self.tree.tag_configure("high", background="#fff6cc")     # amarillo claro (stock > max)
        self.tree.tag_configure("ok", background="")              # normal

        # --- Panel Configuración ---
        cfg = ttk.Labelframe(self, text="Configuración de límites críticos y refresco", padding=10)
        cfg.pack(fill="x", expand=False)

        ttk.Label(cfg, text="Mínimo crítico:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        sp_min = ttk.Spinbox(cfg, from_=0, to=999999, textvariable=self._crit_min, width=10)
        sp_min.grid(row=0, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(cfg, text="Máximo crítico:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        sp_max = ttk.Spinbox(cfg, from_=0, to=999999, textvariable=self._crit_max, width=10)
        sp_max.grid(row=0, column=3, sticky="w", padx=4, pady=4)

        ttk.Label(cfg, text="Refresco (ms):").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        sp_ms = ttk.Spinbox(cfg, from_=500, to=60000, increment=500, textvariable=self._refresh_ms, width=10)
        sp_ms.grid(row=0, column=5, sticky="w", padx=4, pady=4)

        ttk.Button(cfg, text="Guardar", command=self._on_save_config).grid(row=0, column=6, padx=8)

        for i in range(7):
            cfg.columnconfigure(i, weight=1)

        # Primera carga + programar auto
        self.refresh_table()
        self._schedule_auto()

    # ----------------------------------
    # UI actions
    # ----------------------------------
    def refresh_table(self):
        """
        Carga los productos, borra la grilla y la repuebla con tags de estado
        según los límites críticos configurados.
        """
        min_v = self._crit_min.get()
        max_v = self._crit_max.get()
        # Seguridad en runtime
        if min_v < 0:
            min_v = 0
            self._crit_min.set(0)
        if max_v < min_v:
            max_v = min_v
            self._crit_max.set(min_v)

        try:
            # Vaciar
            for iid in self.tree.get_children():
                self.tree.delete(iid)

            rows: List[Product] = (
                self.session.query(Product)
                .order_by(Product.nombre.asc())
                .all()
            )
            for p in rows:
                stock = int(p.stock_actual or 0)
                tag = "ok"
                if stock < min_v:
                    tag = "low"
                elif stock > max_v:
                    tag = "high"

                self.tree.insert(
                    "",
                    "end",
                    values=(
                        p.id,
                        p.nombre,
                        p.sku,
                        p.unidad_medida or "",
                        stock,
                        f"{float(p.precio_compra):.2f}",
                        f"{float(p.precio_venta):.2f}",
                    ),
                    tags=(tag,),
                )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo refrescar el inventario:\n{e}")

    def _on_save_config(self):
        """
        Persiste límites y ms de refresco, reprograma el auto y refresca la tabla.
        """
        try:
            min_v = int(self._crit_min.get())
            max_v = int(self._crit_max.get())
            ms = int(self._refresh_ms.get())
            set_inventory_limits(min_v, max_v)
            set_inventory_refresh_ms(ms)
            # Reprogramar
            self._cancel_auto()
            self._schedule_auto()
            # Refrescar ya
            self.refresh_table()
            messagebox.showinfo("OK", "Configuración guardada.")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar configuración:\n{e}")

    def _on_toggle_auto(self):
        """
        Activa/desactiva el refresco automático.
        """
        if self._auto_enabled.get():
            self._schedule_auto()
        else:
            self._cancel_auto()

    # ----------------------------------
    # Auto-refresh (after)
    # ----------------------------------
    def _tick(self):
        # Refresca y agenda siguiente si auto ON.
        self.refresh_table()
        if self._auto_enabled.get():
            self._auto_job = self.after(self._refresh_ms.get(), self._tick)

    def _schedule_auto(self):
        if self._auto_enabled.get():
            # Inicia/reinicia ciclo
            self._auto_job = self.after(self._refresh_ms.get(), self._tick)

    def _cancel_auto(self):
        if self._auto_job:
            try:
                self.after_cancel(self._auto_job)
            except Exception:
                pass
            self._auto_job = None

    # ----------------------------------
    # Interfaz homogénea con MainWindow
    # ----------------------------------
    def refresh_lookups(self):
        # Cuando entras a la pestaña, refresca también
        self.refresh_table()

    def destroy(self):
        # Cancela timers al cerrar
        self._cancel_auto()
        super().destroy()

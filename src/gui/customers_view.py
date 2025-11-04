# src/gui/customers_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional

from src.data.database import get_session
from src.data.models import Customer
from src.data.repository import CustomerRepository
from src.gui.widgets.grid_table import GridTable
from src.utils.validators import is_valid_rut_chile, normalize_rut, is_valid_email


class CustomersView(ttk.Frame):
    """CRUD de Clientes (Razón social + RUT + datos de contacto) con grilla tipo hoja."""

    COLS = ["ID", "Razón social", "RUT", "Contacto", "Teléfono", "Email", "Dirección"]
    COL_WIDTHS = [60, 220, 140, 160, 120, 220, 260]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = CustomerRepository(self.session)

        self._editing_id: Optional[int] = None
        self._rows_cache: List[List[str]] = []  # copia de lo mostrado en la tabla (por índice)
        self._id_by_index: List[int] = []       # mapea fila -> id

        # ---------- Formulario ----------
        frm = ttk.Labelframe(self, text="Cliente", padding=10)
        frm.pack(fill="x", expand=False)

        self.var_razon = tk.StringVar()
        self.var_rut = tk.StringVar()
        self.var_contacto = tk.StringVar()
        self.var_telefono = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_direccion = tk.StringVar()

        def row(lbl: str, var: tk.StringVar, r: int, width: int = 40):
            ttk.Label(frm, text=f"{lbl}:").grid(row=r, column=0, sticky="e", padx=4, pady=4)
            ttk.Entry(frm, textvariable=var, width=width).grid(row=r, column=1, sticky="w", padx=4, pady=4)

        row("Razón social", self.var_razon, 0)
        row("RUT", self.var_rut, 1, width=20)
        row("Contacto", self.var_contacto, 2)
        row("Teléfono", self.var_telefono, 3)
        row("Email", self.var_email, 4)
        row("Dirección", self.var_direccion, 5)

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, pady=8)
        self.btn_save = ttk.Button(btns, text="Agregar", command=self._on_add)
        self.btn_update = ttk.Button(btns, text="Guardar cambios", command=self._on_update, state="disabled")
        self.btn_delete = ttk.Button(btns, text="Eliminar", command=self._on_delete, state="disabled")
        self.btn_clear = ttk.Button(btns, text="Limpiar", command=self._clear_form)
        for b in (self.btn_save, self.btn_update, self.btn_delete, self.btn_clear):
            b.pack(side="left", padx=4)

        # ---------- Tabla (GridTable) ----------
        self.table = GridTable(self, height=14)
        self.table.pack(fill="both", expand=True, pady=(10, 0))

        # Doble click para editar (tksheet + fallback)
        if hasattr(self.table, "sheet"):
            try:
                self.table.sheet.extra_bindings([("double_click", lambda e: self._on_row_dblclick())])
            except Exception:
                pass
        tv = getattr(self.table, "_fallback", None)
        if tv is not None:
            tv.bind("<Double-1>", lambda e: self._on_row_dblclick())
            # Click en encabezado: limpiar selección y formulario
            tv.bind("<Button-1>", self._on_tree_click)

        # Carga inicial
        self._load_table()

    # ---------- Utilidades ----------
    def _normalize_rut(self, rut: str) -> str:
        """Normaliza formato básico del RUT."""
        return normalize_rut(rut)

    def _apply_column_widths(self) -> None:
        """Ajusta anchos de columnas tanto en tksheet como en Treeview."""
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

    def _read_form(self) -> dict | None:
        razon = self.var_razon.get().strip()
        rut = self._normalize_rut(self.var_rut.get())
        if not razon:
            messagebox.showwarning("Validación", "La Razón social es obligatoria.")
            return None
        if not rut:
            messagebox.showwarning("Validación", "El RUT es obligatorio.")
            return None
        # Validación de RUT (con dígito verificador)
        if not is_valid_rut_chile(rut):
            messagebox.showwarning("Validación", "El RUT no es válido (revise dígito verificador).")
            return None

        # Email opcional: solo validar si está presente
        email = self.var_email.get().strip()
        if email and not is_valid_email(email):
            messagebox.showwarning("Validación", "El email no parece válido.")
            return None

        return {
            "razon_social": razon,
            "rut": rut,
            "contacto": self.var_contacto.get().strip() or None,
            "telefono": self.var_telefono.get().strip() or None,
            "email": (email or None),
            "direccion": self.var_direccion.get().strip() or None,
        }

    def _selected_row_index(self) -> Optional[int]:
        """Índice de fila seleccionada en la grilla (o None)."""
        # tksheet
        if hasattr(self.table, "sheet"):
            try:
                rows = list(self.table.sheet.get_selected_rows())
                if rows:
                    return sorted(rows)[0]
                # alternativa: desde celdas seleccionadas
                cells = self.table.sheet.get_selected_cells()
                if cells:
                    return sorted({r for r, _ in cells})[0]
            except Exception:
                pass
            return None
        # fallback Treeview
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

    # ---------- CRUD ----------
    def _on_add(self):
        try:
            data = self._read_form()
            if not data:
                return
            # Validar unicidad de RUT
            if self.session.query(Customer).filter_by(rut=data["rut"]).first():
                messagebox.showwarning("Duplicado", "Ya existe un cliente con ese RUT.")
                return
            c = Customer(**data)
            self.session.add(c)
            self.session.commit()
            self._clear_form()
            self._load_table()
            messagebox.showinfo("OK", f"Cliente '{data['razon_social']}' creado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo crear el cliente:\n{e}")

    def _on_update(self):
        if self._editing_id is None:
            return
        try:
            data = self._read_form()
            if not data:
                return
            c = self.repo.get(self._editing_id)
            if not c:
                messagebox.showwarning("Aviso", "Registro no encontrado.")
                return
            # Validar unicidad de RUT si cambió
            if c.rut != data["rut"]:
                if self.session.query(Customer).filter_by(rut=data["rut"]).first():
                    messagebox.showwarning("Duplicado", "Ya existe un cliente con ese RUT.")
                    return
            c.razon_social = data["razon_social"]
            c.rut = data["rut"]
            c.contacto = data["contacto"]
            c.telefono = data["telefono"]
            c.email = data["email"]
            c.direccion = data["direccion"]
            self.session.commit()
            self._clear_form()
            self._load_table()
            messagebox.showinfo("OK", "Cliente actualizado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo actualizar:\n{e}")

    def _on_delete(self):
        if self._editing_id is None:
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este cliente?"):
            return
        try:
            self.repo.delete(self._editing_id)
            self.session.commit()
            self._clear_form()
            self._load_table()
            messagebox.showinfo("OK", "Cliente eliminado.")
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

    def _on_row_dblclick(self, _=None):
        """Carga la fila seleccionada a los controles para edición."""
        idx = self._selected_row_index()
        if idx is None or idx < 0 or idx >= len(self._rows_cache):
            return
        vals = self._rows_cache[idx]
        # 0 id, 1 razon, 2 rut, 3 contacto, 4 tel, 5 email, 6 dir
        self._editing_id = int(vals[0])
        self.var_razon.set(vals[1] or "")
        self.var_rut.set(vals[2] or "")
        self.var_contacto.set(vals[3] or "")
        self.var_telefono.set(vals[4] or "")
        self.var_email.set(vals[5] or "")
        self.var_direccion.set(vals[6] or "")

        self.btn_save.config(state="disabled")
        self.btn_update.config(state="normal")
        self.btn_delete.config(state="normal")

    def _on_tree_click(self, event):
        """(Solo fallback) Click en encabezado: limpiar selección y formulario."""
        tv = getattr(self.table, "_fallback", None)
        if tv is None:
            return
        region = tv.identify("region", event.x, event.y)
        if region == "heading":
            tv.selection_remove(tv.selection())
            self._clear_form()

    def _clear_form(self):
        self._editing_id = None
        for v in (self.var_razon, self.var_rut, self.var_contacto, self.var_telefono, self.var_email, self.var_direccion):
            v.set("")
        self.btn_save.config(state="normal")
        self.btn_update.config(state="disabled")
        self.btn_delete.config(state="disabled")
        # Limpia selección en la grilla
        try:
            if hasattr(self.table, "sheet"):
                self.table.sheet.deselect("all")
            else:
                tv = getattr(self.table, "_fallback", None)
                if tv is not None:
                    tv.selection_remove(tv.selection())
        except Exception:
            pass

    def _load_table(self):
        """Consulta y vuelca datos en la grilla (sin colores)."""
        rows_db: List[Customer] = self.session.query(Customer).order_by(Customer.razon_social.asc()).all()

        self._rows_cache = []
        self._id_by_index = []

        for r in rows_db:
            row = [
                r.id,
                getattr(r, "razon_social", None) or "",
                getattr(r, "rut", None) or "",
                r.contacto or "",
                r.telefono or "",
                r.email or "",
                r.direccion or "",
            ]
            self._rows_cache.append(row)
            self._id_by_index.append(int(r.id))

        # Set data a la grilla y ajustar anchos
        self.table.set_data(self.COLS, self._rows_cache)
        self._apply_column_widths()

    # ---------- Interfaz homogénea con MainWindow ----------
    def refresh_lookups(self):
        self._load_table()


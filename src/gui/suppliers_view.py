# src/gui/suppliers_view.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional

from src.data.database import get_session
from src.data.models import Supplier
from src.data.repository import SupplierRepository

# Grilla tipo hoja (tksheet si está instalado; si no, Treeview)
from src.gui.widgets.grid_table import GridTable


def validar_rut_chileno(rut: str) -> bool:
    """Valida formato básico de RUT chileno (sin puntos, con guion y dígito verificador)."""
    rut = rut.replace(" ", "").replace(".", "").upper()
    if "-" not in rut or len(rut) < 3:
        return False
    num, dv = rut.split("-")
    return num.isdigit() and (dv.isdigit() or dv == "K")


class SuppliersView(ttk.Frame):
    """CRUD de Proveedores (Razón social + RUT + datos de contacto) con grilla tipo hoja."""

    COLS = ["ID", "Razón social", "RUT", "Contacto", "Teléfono", "Email", "Dirección"]
    COL_WIDTHS = [50, 220, 120, 160, 120, 200, 260]

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = SupplierRepository(self.session)
        self._editing_id: Optional[int] = None

        # Cache de filas mostradas (para facilitar doble click y edición)
        self._rows_cache: List[List[str]] = []
        self._id_by_index: List[int] = []

        # ---------- Formulario ----------
        frm = ttk.Labelframe(self, text="Proveedor", padding=10)
        frm.pack(fill="x", expand=False)

        self.var_razon = tk.StringVar()
        self.var_rut = tk.StringVar()
        self.var_contacto = tk.StringVar()
        self.var_telefono = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_direccion = tk.StringVar()

        def row(lbl: str, var: tk.StringVar, r: int, width: int = 40):
            ttk.Label(frm, text=f"{lbl}:").grid(row=r, column=0, sticky="e", padx=4, pady=4)
            ent = ttk.Entry(frm, textvariable=var, width=width)
            ent.grid(row=r, column=1, sticky="w", padx=4, pady=4)
            return ent

        self.ent_razon = row("Razón social", self.var_razon, 0)
        self.ent_rut = row("RUT", self.var_rut, 1, width=20)
        row("Contacto (vendedor)", self.var_contacto, 2)
        row("Teléfono", self.var_telefono, 3)
        row("Email", self.var_email, 4)
        row("Dirección", self.var_direccion, 5)

        # Botones
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
            # Click en encabezado → limpiar selección y formulario
            tv.bind("<Button-1>", self._on_tree_click)

        # Carga inicial
        self._load_table()
        # Foco inicial
        self.after(100, lambda: self.ent_razon.focus_set())

    # ---------- Utilidades ----------
    def _apply_column_widths(self) -> None:
        """Ajusta anchos de columnas tanto en tksheet como en Treeview."""
        if hasattr(self.table, "sheet"):
            try:
                for i, w in enumerate(self.COLS and self.COL_WIDTHS):
                    self.table.sheet.column_width(i, width=self.COL_WIDTHS[i])
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

    def _normalize_rut(self, rut: str) -> str:
        """Normaliza espacios y mayúsculas."""
        return rut.replace(" ", "").strip().upper()

    def _selected_row_index(self) -> Optional[int]:
        """Índice de fila seleccionada en la grilla (None si no hay)."""
        # tksheet
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

    def _read_form(self) -> dict | None:
        razon = self.var_razon.get().strip()
        rut = self._normalize_rut(self.var_rut.get())
        if not razon:
            self._warn("La Razón social es obligatoria.")
            return None
        if not rut:
            self._warn("El RUT es obligatorio.")
            return None
        if not validar_rut_chileno(rut):
            self._warn("El RUT no tiene un formato válido (ej: 12345678-9).")
            return None
        # Validación mínima de email
        email = self.var_email.get().strip() or None
        if email and "@" not in email:
            self._warn("El email no parece válido.")
            return None

        # Evita RUT duplicados (excepto si es edición del mismo)
        exists = self.session.query(Supplier).filter(Supplier.rut == rut).first()
        if exists and (self._editing_id is None or exists.id != self._editing_id):
            self._warn("Ya existe un proveedor con ese RUT.")
            return None

        return {
            "razon_social": razon,
            "rut": rut,
            "contacto": self.var_contacto.get().strip() or None,
            "telefono": self.var_telefono.get().strip() or None,
            "email": email,
            "direccion": self.var_direccion.get().strip() or None,
        }

    # ---------- CRUD ----------
    def _on_add(self):
        try:
            data = self._read_form()
            if not data:
                return
            s = Supplier(**data)
            self.session.add(s)
            self.session.commit()
            self._clear_form()
            self._load_table()
            self._info(f"Proveedor '{data['razon_social']}' creado.")
        except Exception as e:
            self.session.rollback()
            self._error(f"No se pudo crear el proveedor:\n{e}")

    def _on_update(self):
        if self._editing_id is None:
            return
        try:
            data = self._read_form()
            if not data:
                return
            s = self.repo.get(self._editing_id)
            if not s:
                self._warn("Registro no encontrado.")
                return
            # Actualizar campos
            s.razon_social = data["razon_social"]
            s.rut = data["rut"]
            s.contacto = data["contacto"]
            s.telefono = data["telefono"]
            s.email = data["email"]
            s.direccion = data["direccion"]

            self.session.commit()
            self._clear_form()
            self._load_table()
            self._info("Proveedor actualizado.")
        except Exception as e:
            self.session.rollback()
            self._error(f"No se pudo actualizar:\n{e}")

    def _on_delete(self):
        if self._editing_id is None:
            return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este proveedor?"):
            return
        try:
            self.repo.delete(self._editing_id)
            self.session.commit()
            self._clear_form()
            self._load_table()
        except Exception as e:
            self.session.rollback()
            self._error(f"No se pudo eliminar:\n{e}")

    def _on_row_dblclick(self, _=None):
        """Carga la fila seleccionada a los controles para edición."""
        idx = self._selected_row_index()
        if idx is None or idx < 0 or idx >= len(self._rows_cache):
            return
        vals = self._rows_cache[idx]
        # 0 id, 1 razon, 2 rut, 3 contacto, 4 telefono, 5 email, 6 direccion
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

        # Selecciona texto en el primer campo para edición rápida
        self.after(100, lambda: self.ent_razon.focus_set())
        self.after(120, lambda: self.ent_razon.select_range(0, "end"))

    def _on_tree_click(self, event):
        """(Solo fallback) Click en encabezado → limpiar selección y formulario."""
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
        # Foco en el primer campo
        self.after(100, lambda: self.ent_razon.focus_set())

    def _load_table(self):
        """Consulta y vuelca datos en la grilla (sin colores)."""
        rows_db: List[Supplier] = self.session.query(Supplier).order_by(Supplier.id.desc()).all()

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

    def refresh_lookups(self):
        """Recarga la tabla de proveedores."""
        self._load_table()

    # ---------- Mensajes ----------
    def _warn(self, msg: str):
        messagebox.showwarning("Validación", msg)

    def _error(self, msg: str):
        messagebox.showerror("Error", msg)

    def _info(self, msg: str):
        messagebox.showinfo("OK", msg)

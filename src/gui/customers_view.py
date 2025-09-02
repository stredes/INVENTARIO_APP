from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional

from src.data.database import get_session
from src.data.models import Customer
from src.data.repository import CustomerRepository


class CustomersView(ttk.Frame):
    """CRUD de Clientes."""
    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = CustomerRepository(self.session)
        self._editing_id: Optional[int] = None

        frm = ttk.Labelframe(self, text="Cliente", padding=10)
        frm.pack(fill="x", expand=False)

        self.var_nombre = tk.StringVar()
        self.var_contacto = tk.StringVar()
        self.var_telefono = tk.StringVar()
        self.var_email = tk.StringVar()
        self.var_direccion = tk.StringVar()

        def row(lbl, var, r, width=40):
            ttk.Label(frm, text=f"{lbl}:").grid(row=r, column=0, sticky="e", padx=4, pady=4)
            ttk.Entry(frm, textvariable=var, width=width).grid(row=r, column=1, sticky="w", padx=4, pady=4)

        row("Nombre", self.var_nombre, 0)
        row("Contacto", self.var_contacto, 1)
        row("Teléfono", self.var_telefono, 2)
        row("Email", self.var_email, 3)
        row("Dirección", self.var_direccion, 4)

        btns = ttk.Frame(frm); btns.grid(row=5, column=0, columnspan=2, pady=8)
        self.btn_save = ttk.Button(btns, text="Agregar", command=self._on_add)
        self.btn_update = ttk.Button(btns, text="Guardar cambios", command=self._on_update, state="disabled")
        self.btn_delete = ttk.Button(btns, text="Eliminar", command=self._on_delete, state="disabled")
        self.btn_clear = ttk.Button(btns, text="Limpiar", command=self._clear_form)
        for b in (self.btn_save, self.btn_update, self.btn_delete, self.btn_clear):
            b.pack(side="left", padx=4)

        self.tree = ttk.Treeview(self, columns=("id","nombre","contacto","telefono","email","direccion"), show="headings", height=14)
        for cid, text, w in [
            ("id","ID",60), ("nombre","Nombre",220), ("contacto","Contacto",160),
            ("telefono","Teléfono",120), ("email","Email",200), ("direccion","Dirección",260),
        ]:
            self.tree.heading(cid, text=text); self.tree.column(cid, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True, pady=(10,0))
        self.tree.bind("<Double-1>", self._on_row_dblclick)

        self._load_table()

    def _read_form(self) -> dict | None:
        nombre = self.var_nombre.get().strip()
        if not nombre:
            messagebox.showwarning("Validación", "El nombre es obligatorio."); return None
        return {
            "nombre": nombre,
            "contacto": self.var_contacto.get().strip() or None,
            "telefono": self.var_telefono.get().strip() or None,
            "email": self.var_email.get().strip() or None,
            "direccion": self.var_direccion.get().strip() or None,
        }

    def _on_add(self):
        try:
            data = self._read_form()
            if not data: return
            c = Customer(**data); self.session.add(c); self.session.commit()
            self._clear_form(); self._load_table()
            messagebox.showinfo("OK", f"Cliente '{data['nombre']}' creado.")
        except Exception as e:
            self.session.rollback(); messagebox.showerror("Error", f"No se pudo crear:\n{e}")

    def _on_update(self):
        if self._editing_id is None: return
        try:
            data = self._read_form()
            if not data: return
            c = self.repo.get(self._editing_id)
            if not c:
                messagebox.showwarning("Aviso", "Registro no encontrado."); return
            for k, v in data.items(): setattr(c, k, v)
            self.session.commit()
            self._clear_form(); self._load_table()
            messagebox.showinfo("OK", "Cliente actualizado.")
        except Exception as e:
            self.session.rollback(); messagebox.showerror("Error", f"No se pudo actualizar:\n{e}")

    def _on_delete(self):
        if self._editing_id is None: return
        if not messagebox.askyesno("Confirmar", "¿Eliminar este cliente?"): return
        try:
            self.repo.delete(self._editing_id); self.session.commit()
            self._clear_form(); self._load_table()
        except Exception as e:
            self.session.rollback(); messagebox.showerror("Error", f"No se pudo eliminar:\n{e}")

    def _on_row_dblclick(self, _=None):
        sel = self.tree.selection()
        if not sel: return
        vals = self.tree.item(sel[0], "values")
        self._editing_id = int(vals[0])
        self.var_nombre.set(vals[1]); self.var_contacto.set(vals[2] or "")
        self.var_telefono.set(vals[3] or ""); self.var_email.set(vals[4] or ""); self.var_direccion.set(vals[5] or "")
        self.btn_save.config(state="disabled"); self.btn_update.config(state="normal"); self.btn_delete.config(state="normal")

    def _clear_form(self):
        self._editing_id = None
        for v in (self.var_nombre, self.var_contacto, self.var_telefono, self.var_email, self.var_direccion):
            v.set("")
        self.btn_save.config(state="normal"); self.btn_update.config(state="disabled"); self.btn_delete.config(state="disabled")

    def _load_table(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        rows: List[Customer] = self.session.query(Customer).order_by(Customer.id.desc()).all()
        for r in rows:
            self.tree.insert("", "end", values=(r.id, r.nombre, r.contacto or "", r.telefono or "", r.email or "", r.direccion or ""))

    def refresh_lookups(self):
        pass

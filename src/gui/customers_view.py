from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional

from src.data.database import get_session
from src.data.models import Customer
from src.data.repository import CustomerRepository


class CustomersView(ttk.Frame):
    """CRUD de Clientes (Razón social + RUT + datos de contacto)."""

    def __init__(self, master: tk.Misc):
        super().__init__(master, padding=10)
        self.session = get_session()
        self.repo = CustomerRepository(self.session)
        self._editing_id: Optional[int] = None

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

        # ---------- Tabla ----------
        self.tree = ttk.Treeview(
            self,
            columns=("id", "razon", "rut", "contacto", "telefono", "email", "direccion"),
            show="headings",
            height=14,
        )
        for cid, text, w, anchor in [
            ("id", "ID", 60, "center"),
            ("razon", "Razón social", 220, "w"),
            ("rut", "RUT", 140, "w"),
            ("contacto", "Contacto", 160, "w"),
            ("telefono", "Teléfono", 120, "w"),
            ("email", "Email", 220, "w"),
            ("direccion", "Dirección", 260, "w"),
        ]:
            self.tree.heading(cid, text=text)
            self.tree.column(cid, width=w, anchor=anchor)
        self.tree.pack(fill="both", expand=True, pady=(10, 0))
        self.tree.bind("<Double-1>", self._on_row_dblclick)
        self.tree.bind("<Button-1>", self._on_tree_click)

        self._load_table()

    # ---------- Utilidades ----------
    def _normalize_rut(self, rut: str) -> str:
        """Normaliza formato básico del RUT."""
        return rut.replace(" ", "").strip().upper()

    def _read_form(self) -> dict | None:
        razon = self.var_razon.get().strip()
        rut = self._normalize_rut(self.var_rut.get())
        if not razon:
            messagebox.showwarning("Validación", "La Razón social es obligatoria.")
            return None
        if not rut:
            messagebox.showwarning("Validación", "El RUT es obligatorio.")
            return None

        email = self.var_email.get().strip() or None
        if email and "@" not in email:
            messagebox.showwarning("Validación", "El email no parece válido.")
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
        sel = self.tree.selection()
        if not sel:
            return
        vals = self.tree.item(sel[0], "values")
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
        # Des-selecciona fila si se hace click fuera de una celda
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            self.tree.selection_remove(self.tree.selection())
            self._clear_form()

    def _clear_form(self):
        self._editing_id = None
        for v in (self.var_razon, self.var_rut, self.var_contacto, self.var_telefono, self.var_email, self.var_direccion):
            v.set("")
        self.btn_save.config(state="normal")
        self.btn_update.config(state="disabled")
        self.btn_delete.config(state="disabled")

    def _load_table(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        rows: List[Customer] = self.session.query(Customer).order_by(Customer.razon_social.asc()).all()
        for r in rows:
            self.tree.insert(
                "",
                "end",
                values=(
                    r.id,
                    getattr(r, "razon_social", None) or "",
                    getattr(r, "rut", None) or "",
                    r.contacto or "",
                    r.telefono or "",
                    r.email or "",
                    r.direccion or "",
                ),
            )

    def refresh_lookups(self):
       self._load_table()
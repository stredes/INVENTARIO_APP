from __future__ import annotations
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from sqlalchemy.orm import Session

from src.data.models import Location


class LocationsManager(tk.Toplevel):
    """Diálogo simple para administrar ubicaciones (bodegas/estanterías)."""

    def __init__(self, session: Session, parent: Optional[tk.Misc] = None):
        super().__init__(parent)
        self.title("Ubicaciones")
        self.geometry("520x360")
        self.transient(parent)
        self.grab_set()

        self.session = session

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # Listado
        self.tree = ttk.Treeview(frm, columns=("id", "nombre", "descripcion"), show="headings", height=10)
        self.tree.heading("id", text="ID")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("descripcion", text="Descripción")
        self.tree.column("id", width=60, anchor="center")
        self.tree.column("nombre", width=180, anchor="w")
        self.tree.column("descripcion", width=240, anchor="w")
        self.tree.pack(fill="both", expand=True)

        # Formulario simple
        form = ttk.Frame(frm)
        form.pack(fill="x", pady=(8, 4))
        ttk.Label(form, text="Nombre:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        ttk.Label(form, text="Descripción:").grid(row=1, column=0, sticky="e", padx=4, pady=2)
        self.var_nombre = tk.StringVar()
        self.var_desc = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_nombre, width=28).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Entry(form, textvariable=self.var_desc, width=42).grid(row=1, column=1, sticky="w", padx=4, pady=2)

        # Botones
        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="Nuevo", command=self._on_new).pack(side="left", padx=4)
        ttk.Button(btns, text="Guardar", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(btns, text="Eliminar", command=self._on_delete).pack(side="left", padx=4)
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side="right", padx=4)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self._load()

    # --- Data ---
    def _load(self):
        self.tree.delete(*self.tree.get_children(""))
        for loc in self.session.query(Location).order_by(Location.nombre.asc()).all():
            self.tree.insert("", "end", iid=str(loc.id), values=(loc.id, loc.nombre or "", loc.descripcion or ""))

    def _on_new(self):
        self.var_nombre.set("")
        self.var_desc.set("")
        self.tree.selection_remove(self.tree.selection())

    def _on_select(self, _evt=None):
        sel = self.tree.selection()
        if not sel:
            return
        iid = sel[0]
        loc = self.session.get(Location, int(iid))
        if not loc:
            return
        self.var_nombre.set(loc.nombre or "")
        self.var_desc.set(loc.descripcion or "")

    def _on_save(self):
        nombre = (self.var_nombre.get() or "").strip()
        if not nombre:
            messagebox.showwarning("Ubicaciones", "Ingrese un nombre de ubicación.")
            return
        sel = self.tree.selection()
        try:
            if sel:
                # update
                iid = sel[0]
                loc = self.session.get(Location, int(iid))
                if not loc:
                    messagebox.showwarning("Ubicaciones", "Registro no encontrado.")
                    return
                loc.nombre = nombre
                loc.descripcion = (self.var_desc.get() or "").strip()
            else:
                # new
                loc = Location(nombre=nombre, descripcion=(self.var_desc.get() or "").strip())
                self.session.add(loc)
            self.session.commit()
            self._load()
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Ubicaciones", f"No se pudo guardar:\n{e}")

    def _on_delete(self):
        sel = self.tree.selection()
        if not sel:
            return
        if not messagebox.askyesno("Ubicaciones", "¿Eliminar la ubicación seleccionada?"):
            return
        try:
            iid = sel[0]
            loc = self.session.get(Location, int(iid))
            if loc:
                self.session.delete(loc)
                self.session.commit()
            self._load()
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Ubicaciones", f"No se pudo eliminar:\n{e}")


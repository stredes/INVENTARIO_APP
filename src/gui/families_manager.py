from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Set

from sqlalchemy.orm import Session

from src.data.models import Family, Product


class FamiliesManager(tk.Toplevel):
    """Administrador simple de familias (categorías).

    - Sincroniza nombres existentes en productos -> tabla families.
    - Permite crear, renombrar y eliminar familias.
    - Al renombrar, actualiza también los productos que tenían ese nombre.
    """

    def __init__(self, session: Session, parent: Optional[tk.Misc] = None):
        super().__init__(parent)
        self.title("Familias")
        self.geometry("620x420")
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.session = session

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)
        frm.rowconfigure(0, weight=1)
        frm.columnconfigure(0, weight=1)

        # Tabla
        tree_frame = ttk.Frame(frm)
        tree_frame.grid(row=0, column=0, sticky="nsew")
        self.tree = ttk.Treeview(tree_frame, columns=("id", "nombre"), show="headings", height=14)
        self.tree.heading("id", text="ID")
        self.tree.heading("nombre", text="Nombre")
        self.tree.column("id", width=80, anchor="center")
        self.tree.column("nombre", width=360, anchor="w")
        vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        tree_frame.rowconfigure(0, weight=1)
        tree_frame.columnconfigure(0, weight=1)

        # Formulario
        form = ttk.Frame(frm)
        form.grid(row=1, column=0, sticky="we", pady=(8, 4))
        ttk.Label(form, text="Nombre:").grid(row=0, column=0, sticky="e", padx=4, pady=2)
        self.var_nombre = tk.StringVar()
        ttk.Entry(form, textvariable=self.var_nombre, width=36).grid(row=0, column=1, sticky="w", padx=4, pady=2)

        # Botones
        btns = ttk.Frame(frm)
        btns.grid(row=2, column=0, sticky="we", pady=(6, 0))
        ttk.Button(btns, text="Importar desde productos", command=self._on_import_from_products).pack(side="left", padx=4)
        ttk.Button(btns, text="Nuevo", command=self._on_new).pack(side="left", padx=4)
        ttk.Button(btns, text="Guardar", command=self._on_save).pack(side="left", padx=4)
        ttk.Button(btns, text="Eliminar", command=self._on_delete).pack(side="left", padx=4)
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side="right", padx=4)

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self._load()

    # ---- Data helpers ----
    def _current_selection(self) -> Optional[int]:
        try:
            sel = self.tree.selection()
            if not sel:
                return None
            return int(sel[0])
        except Exception:
            return None

    def _load(self) -> None:
        # Auto-import desde productos para que estén todas disponibles
        try:
            names_in_products: Set[str] = set(
                (n or "").strip() for (n,) in self.session.query(Product.familia).filter(Product.familia.isnot(None)).distinct().all()
            )
            names_in_products.discard("")
            known: Set[str] = set((f.nombre or "").strip() for f in self.session.query(Family).all())
            to_add = [Family(nombre=n) for n in names_in_products if n not in known]
            if to_add:
                self.session.add_all(to_add)
                self.session.commit()
        except Exception:
            self.session.rollback()

        # Cargar a la tabla
        for iid in self.tree.get_children(""):
            self.tree.delete(iid)
        for fam in self.session.query(Family).order_by(Family.nombre.asc()).all():
            self.tree.insert("", "end", iid=str(int(fam.id)), values=(fam.id, fam.nombre or ""))

    # ---- UI actions ----
    def _on_new(self) -> None:
        self.var_nombre.set("")
        self.tree.selection_remove(self.tree.selection())

    def _on_select(self, _evt=None) -> None:
        fid = self._current_selection()
        if fid is None:
            return
        fam = self.session.get(Family, fid)
        if not fam:
            return
        self.var_nombre.set(fam.nombre or "")

    def _on_save(self) -> None:
        name = (self.var_nombre.get() or "").strip()
        if not name:
            messagebox.showwarning("Familias", "Ingrese un nombre de familia.")
            return
        sel_id = self._current_selection()
        try:
            if sel_id is None:
                # nuevo
                fam = Family(nombre=name)
                self.session.add(fam)
                self.session.commit()
            else:
                fam = self.session.get(Family, int(sel_id))
                if not fam:
                    messagebox.showwarning("Familias", "Registro no encontrado.")
                    return
                old = fam.nombre or ""
                fam.nombre = name
                self.session.commit()
                # Renombrar también en productos
                if old and old != name:
                    self.session.query(Product).filter(Product.familia == old).update({Product.familia: name})
                    self.session.commit()
            self._load()
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Familias", f"No se pudo guardar/renombrar:\n{e}")

    def _on_delete(self) -> None:
        fid = self._current_selection()
        if fid is None:
            return
        if not messagebox.askyesno("Familias", "¿Eliminar la familia seleccionada? Esto no cambia los productos."):
            return
        try:
            fam = self.session.get(Family, int(fid))
            if fam:
                self.session.delete(fam)
                self.session.commit()
            self._load()
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Familias", f"No se pudo eliminar:\n{e}")

    def _on_import_from_products(self) -> None:
        """Crea entradas de familia para todos los nombres presentes en productos."""
        try:
            names_in_products: Set[str] = set(
                (n or "").strip() for (n,) in self.session.query(Product.familia).filter(Product.familia.isnot(None)).distinct().all()
            )
            names_in_products.discard("")
            known: Set[str] = set((f.nombre or "").strip() for f in self.session.query(Family).all())
            to_add = [Family(nombre=n) for n in names_in_products if n not in known]
            if to_add:
                self.session.add_all(to_add)
                self.session.commit()
                messagebox.showinfo("Familias", f"Importadas {len(to_add)} familias desde productos.")
            self._load()
        except Exception as e:
            self.session.rollback()
            messagebox.showerror("Familias", f"No se pudo importar:\n{e}")


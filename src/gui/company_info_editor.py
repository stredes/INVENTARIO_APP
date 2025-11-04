from __future__ import annotations
import configparser
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox


CONFIG_PATH = Path("config/settings.ini")


class CompanyInfoEditor(tk.Toplevel):
    """Editor simple para la sección [company] de config/settings.ini.

    Campos: name, rut, address, phone, email, logo
    """

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.title("Editor de información (Empresa)")
        self.resizable(False, False)
        self.transient(master)
        self.grab_set()

        self.vars = {
            "name": tk.StringVar(),
            "rut": tk.StringVar(),
            "address": tk.StringVar(),
            "phone": tk.StringVar(),
            "email": tk.StringVar(),
            "logo": tk.StringVar(),
        }

        self._load()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        pad = {"padx": 6, "pady": 6}
        row = 0
        for key, label in (
            ("name", "Nombre"),
            ("rut", "RUT"),
            ("address", "Dirección"),
            ("phone", "Teléfono"),
            ("email", "Email"),
        ):
            ttk.Label(frm, text=f"{label}:").grid(row=row, column=0, sticky="e", **pad)
            ttk.Entry(frm, textvariable=self.vars[key], width=42).grid(row=row, column=1, sticky="w", **pad)
            row += 1

        ttk.Label(frm, text="Logo:").grid(row=row, column=0, sticky="e", **pad)
        ttk.Entry(frm, textvariable=self.vars["logo"], width=36).grid(row=row, column=1, sticky="w", **pad)
        ttk.Button(frm, text="Examinar…", command=self._browse_logo).grid(row=row, column=2, sticky="w", padx=4)
        row += 1

        btns = ttk.Frame(frm)
        btns.grid(row=row, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Guardar", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side="left", padx=4)

    # ----- helpers -----
    def _load(self) -> None:
        cfg = configparser.ConfigParser()
        if CONFIG_PATH.exists():
            cfg.read(CONFIG_PATH, encoding="utf-8")
        sec = cfg["company"] if cfg.has_section("company") else {}
        self.vars["name"].set(sec.get("name", ""))
        self.vars["rut"].set(sec.get("rut", ""))
        self.vars["address"].set(sec.get("address", ""))
        self.vars["phone"].set(sec.get("phone", ""))
        self.vars["email"].set(sec.get("email", ""))
        self.vars["logo"].set(sec.get("logo", ""))

    def _browse_logo(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Seleccionar logo",
            filetypes=[("Imagen", "*.png;*.jpg;*.jpeg"), ("Todos", "*.*")],
        )
        if path:
            self.vars["logo"].set(path)

    def _save(self) -> None:
        try:
            cfg = configparser.ConfigParser()
            if CONFIG_PATH.exists():
                cfg.read(CONFIG_PATH, encoding="utf-8")
            if not cfg.has_section("company"):
                cfg.add_section("company")
            sec = cfg["company"]
            for k, v in self.vars.items():
                sec[k] = v.get().strip()
            with CONFIG_PATH.open("w", encoding="utf-8") as f:
                cfg.write(f)
            messagebox.showinfo("Información", "Datos de empresa guardados.", parent=self)
            self.destroy()
        except Exception as ex:
            messagebox.showerror("Error", f"No se pudo guardar:\n{ex}", parent=self)


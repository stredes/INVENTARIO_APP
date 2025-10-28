from __future__ import annotations
import configparser
import os
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from sqlalchemy import create_engine, text

# Reutilizamos la misma ruta de settings que usa src.data.database
CONFIG_PATH = Path("config/settings.ini")


class DBConnectionDialog(tk.Toplevel):
    """
    Diálogo de configuración de conexión a Base de Datos.

    Permite:
    - Ver y editar la URL SQLAlchemy actual (SQLite/PostgreSQL/MySQL).
    - Construir la URL con campos guiados por motor.
    - Probar la conexión.
    - Guardar en config/settings.ini ([database] url=...).
    - Al guardar, puedes reiniciar el engine desde la app para reabrir conexión.
    """

    def __init__(self, master: tk.Misc):
        super().__init__(master)
        self.title("Conexión a Base de Datos")
        self.resizable(False, False)
        self.grab_set()
        self.transient(master)

        self.var_engine = tk.StringVar(value="sqlite")
        self.var_host = tk.StringVar(value="localhost")
        self.var_port = tk.StringVar(value="5432")
        self.var_db = tk.StringVar(value="inventario")
        self.var_user = tk.StringVar(value="")
        self.var_pass = tk.StringVar(value="")
        self.var_sqlite_file = tk.StringVar(value="inventario.db")
        self.var_url = tk.StringVar(value="")

        # Cargar configuración inicial
        self._load_config()

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        # Selector de motor
        ttk.Label(frm, text="Motor:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        cmb = ttk.Combobox(frm, textvariable=self.var_engine, values=["sqlite", "postgresql", "mysql"], width=14, state="readonly")
        cmb.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        cmb.bind('<<ComboboxSelected>>', lambda e: self._update_url_from_fields())

        # Campos según motor
        # SQLite
        self._sqlite_row = ttk.Frame(frm)
        self._sqlite_row.grid(row=1, column=0, columnspan=3, sticky="we")
        ttk.Label(self._sqlite_row, text="Archivo:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        ent_sqlite = ttk.Entry(self._sqlite_row, textvariable=self.var_sqlite_file, width=36)
        ent_sqlite.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        ttk.Button(self._sqlite_row, text="Examinar…", command=self._browse_sqlite).grid(row=0, column=2, sticky="w", padx=5, pady=5)

        # Servidor (PostgreSQL/MySQL)
        self._server_rows = ttk.Frame(frm)
        self._server_rows.grid(row=2, column=0, columnspan=3, sticky="we")
        pad = dict(padx=5, pady=5)
        ttk.Label(self._server_rows, text="Host:").grid(row=0, column=0, sticky="e", **pad)
        ttk.Entry(self._server_rows, textvariable=self.var_host, width=18).grid(row=0, column=1, sticky="w", **pad)
        ttk.Label(self._server_rows, text="Puerto:").grid(row=0, column=2, sticky="e", **pad)
        ttk.Entry(self._server_rows, textvariable=self.var_port, width=8).grid(row=0, column=3, sticky="w", **pad)
        ttk.Label(self._server_rows, text="Base de datos:").grid(row=1, column=0, sticky="e", **pad)
        ttk.Entry(self._server_rows, textvariable=self.var_db, width=18).grid(row=1, column=1, sticky="w", **pad)
        ttk.Label(self._server_rows, text="Usuario:").grid(row=1, column=2, sticky="e", **pad)
        ttk.Entry(self._server_rows, textvariable=self.var_user, width=16).grid(row=1, column=3, sticky="w", **pad)
        ttk.Label(self._server_rows, text="Contraseña:").grid(row=2, column=0, sticky="e", **pad)
        ttk.Entry(self._server_rows, textvariable=self.var_pass, show="*", width=18).grid(row=2, column=1, sticky="w", **pad)

        # URL directa
        ttk.Label(frm, text="URL (avanzado):").grid(row=3, column=0, sticky="e", padx=5, pady=(10, 5))
        ent_url = ttk.Entry(frm, textvariable=self.var_url, width=52)
        ent_url.grid(row=3, column=1, columnspan=2, sticky="we", padx=5, pady=(10, 5))

        # Botones
        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, columnspan=3, sticky="e", pady=(8, 0))
        ttk.Button(btns, text="Probar conexión", command=self._test_connection).pack(side="left", padx=4)
        ttk.Button(btns, text="Guardar", command=self._save).pack(side="left", padx=4)
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side="left", padx=4)

        # Acomodar visibilidad por motor y establecer URL
        self._toggle_rows()
        self._update_url_from_fields()

    # ---------------- Internos ----------------
    def _browse_sqlite(self):
        path = filedialog.asksaveasfilename(
            title="Seleccionar/crear archivo SQLite",
            initialfile=self.var_sqlite_file.get() or "inventario.db",
            defaultextension=".db",
            filetypes=[("SQLite (*.db)", "*.db"), ("Todos", "*.*")],
        )
        if path:
            self.var_sqlite_file.set(path)
            self._update_url_from_fields()

    def _toggle_rows(self):
        eng = (self.var_engine.get() or "sqlite").lower()
        if eng == "sqlite":
            self._sqlite_row.grid()
            self._server_rows.grid_remove()
        else:
            self._sqlite_row.grid_remove()
            self._server_rows.grid()

    def _compose_url(self) -> str:
        eng = (self.var_engine.get() or "sqlite").lower()
        if eng == "sqlite":
            p = self.var_sqlite_file.get().strip() or "inventario.db"
            # Normalizamos a ruta absoluta para evitar confusiones
            pth = Path(os.path.expanduser(os.path.expandvars(p)))
            if not pth.is_absolute():
                pth = Path.cwd() / pth
            return f"sqlite:///{pth}"
        host = self.var_host.get().strip() or "localhost"
        port = self.var_port.get().strip()
        db = self.var_db.get().strip() or "inventario"
        user = self.var_user.get().strip()
        pwd = self.var_pass.get().strip()
        auth = f"{user}:{pwd}@" if user else ""
        if eng == "postgresql":
            port = port or "5432"
            return f"postgresql+psycopg2://{auth}{host}:{port}/{db}"
        if eng == "mysql":
            port = port or "3306"
            return f"mysql+pymysql://{auth}{host}:{port}/{db}"
        return self.var_url.get().strip() or "sqlite:///inventario.db"

    def _update_url_from_fields(self):
        self._toggle_rows()
        # Si el usuario está editando manualmente la URL, no la pisamos si ya contiene otro motor
        try:
            url = self._compose_url()
            self.var_url.set(url)
        except Exception:
            pass

    def _load_config(self) -> None:
        cfg = configparser.ConfigParser()
        if CONFIG_PATH.exists():
            cfg.read(CONFIG_PATH, encoding="utf-8")
        url = cfg.get("database", "url", fallback="sqlite:///inventario.db").strip()
        self.var_url.set(url)
        # Intentamos parsear para precargar campos
        try:
            if url.startswith("sqlite"):
                self.var_engine.set("sqlite")
                path = url.split("sqlite:///")[-1]
                self.var_sqlite_file.set(path)
            elif url.startswith("postgresql"):
                self.var_engine.set("postgresql")
                # Parseo simple
                self._parse_server_url(url)
            elif url.startswith("mysql"):
                self.var_engine.set("mysql")
                self._parse_server_url(url)
        except Exception:
            pass

    def _parse_server_url(self, url: str) -> None:
        try:
            # postgresql+psycopg2://user:pass@host:port/db
            rest = url.split("//", 1)[1]
            auth_host, db = rest.split("/", 1)
            db = db.split("?")[0]
            if "@" in auth_host:
                auth, hostport = auth_host.split("@", 1)
                if ":" in auth:
                    user, pwd = auth.split(":", 1)
                else:
                    user, pwd = auth, ""
            else:
                user, pwd, hostport = "", "", auth_host
            host, port = (hostport.split(":", 1) + [""])[:2]
            self.var_host.set(host or "localhost")
            self.var_port.set(port or ("5432" if url.startswith("postgresql") else "3306"))
            self.var_db.set(db)
            self.var_user.set(user)
            self.var_pass.set(pwd)
        except Exception:
            pass

    def _test_connection(self):
        url = (self.var_url.get() or "").strip()
        if not url:
            messagebox.showwarning("Conexión", "URL vacía.")
            return
        try:
            eng = create_engine(url, future=True, pool_pre_ping=True)
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
            messagebox.showinfo("Conexión", "Conexión exitosa.")
        except Exception as ex:
            messagebox.showerror("Conexión", f"No se pudo conectar:\n{ex}")

    def _save(self):
        url = (self.var_url.get() or "").strip()
        if not url:
            messagebox.showwarning("Guardar", "La URL no puede estar vacía.")
            return
        cfg = configparser.ConfigParser()
        if CONFIG_PATH.exists():
            cfg.read(CONFIG_PATH, encoding="utf-8")
        if "database" not in cfg:
            cfg["database"] = {}
        cfg["database"]["url"] = url

        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as f:
            cfg.write(f)

        # Intento de reiniciar engine para que la app tome el nuevo DSN
        try:
            from src.data.database import dispose_engine  # type: ignore
            dispose_engine()
        except Exception:
            pass

        messagebox.showinfo("Guardar", "Conexión guardada. Reinicia la vista o la aplicación si es necesario.")


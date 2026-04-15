from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import ttk

from src.utils.app_logging import get_known_log_files, get_log_dir


class LogViewerDialog(tk.Toplevel):
    def __init__(self, parent: tk.Misc):
        super().__init__(parent)
        self.title("Visor de logs")
        self.transient(parent.winfo_toplevel())
        self.geometry("1080x680")
        self.minsize(860, 520)

        self._refresh_job = None
        self._log_files = [p for p in get_known_log_files() if p.exists()]
        if not self._log_files:
            self._log_files = get_known_log_files()

        self.var_file = tk.StringVar(value=str(self._log_files[0]))
        self.var_autorefresh = tk.BooleanVar(value=True)
        self.var_status = tk.StringVar(value=f"Carpeta de logs: {get_log_dir()}")

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_toolbar()
        self._build_text()
        self._configure_tags()

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._load_selected_log()
        self._schedule_refresh()

    def _build_toolbar(self) -> None:
        top = ttk.Frame(self, padding=10)
        top.grid(row=0, column=0, sticky="ew")
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Archivo:").grid(row=0, column=0, sticky="w")
        self.cmb_file = ttk.Combobox(
            top,
            state="readonly",
            textvariable=self.var_file,
            values=[str(p) for p in self._log_files],
        )
        self.cmb_file.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.cmb_file.bind("<<ComboboxSelected>>", lambda _e: self._load_selected_log())

        ttk.Button(top, text="Refrescar", command=self._load_selected_log).grid(row=0, column=2, padx=(0, 8))
        ttk.Button(top, text="Abrir carpeta", command=self._open_log_dir).grid(row=0, column=3, padx=(0, 8))
        ttk.Checkbutton(top, text="Auto", variable=self.var_autorefresh, command=self._toggle_refresh).grid(row=0, column=4)
        ttk.Label(top, textvariable=self.var_status, style="HomeSmall.TLabel").grid(row=1, column=0, columnspan=5, sticky="w", pady=(8, 0))

    def _build_text(self) -> None:
        body = ttk.Frame(self, padding=(10, 0, 10, 10))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(0, weight=1)
        body.rowconfigure(0, weight=1)

        self.text = tk.Text(
            body,
            wrap="none",
            bg="#0f172a",
            fg="#dbeafe",
            insertbackground="#dbeafe",
            selectbackground="#1d4ed8",
            relief="flat",
            font=("Consolas", 10),
        )
        self.text.grid(row=0, column=0, sticky="nsew")

        ybar = ttk.Scrollbar(body, orient="vertical", command=self.text.yview)
        xbar = ttk.Scrollbar(body, orient="horizontal", command=self.text.xview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)

    def _configure_tags(self) -> None:
        self.text.tag_configure("default", foreground="#dbeafe")
        self.text.tag_configure("debug", foreground="#94a3b8")
        self.text.tag_configure("info", foreground="#93c5fd")
        self.text.tag_configure("warning", foreground="#facc15")
        self.text.tag_configure("error", foreground="#f87171")
        self.text.tag_configure("critical", foreground="#ffffff", background="#991b1b")
        self.text.tag_configure("startup", foreground="#86efac")
        self.text.tag_configure("db_ok", foreground="#22c55e")
        self.text.tag_configure("update", foreground="#c084fc")
        self.text.tag_configure("trace", foreground="#7dd3fc")

    def _classify_tags(self, line: str) -> tuple[str, ...]:
        text = line.lower()
        tags: list[str] = ["default"]

        if " critical " in text or "[critical]" in text:
            tags.append("critical")
        elif " error " in text or "[error]" in text or "exception" in text:
            tags.append("error")
        elif " warning " in text or "[warning]" in text:
            tags.append("warning")
        elif " debug " in text or "[debug]" in text:
            tags.append("debug")
        elif " info " in text or "[info]" in text:
            tags.append("info")

        if any(key in text for key in ("iniciando", "logging inicializado", "ventana principal construida", "mainloop", "arranque", "base de datos inicializada")):
            tags.append("startup")
        if any(key in text for key in ("conexion", "conexión", "db", "base de datos inicializada", "ok", "estable")):
            tags.append("db_ok")
        if any(key in text for key in ("actualizacion", "actualización", "release", "update")):
            tags.append("update")
        if any(key in text for key in (" call ", " return ", " loop ", "inventario.trace")):
            tags.append("trace")

        return tuple(dict.fromkeys(tags))

    def _selected_path(self) -> Path:
        return Path(self.var_file.get())

    def _load_selected_log(self) -> None:
        path = self._selected_path()
        try:
            if not path.exists():
                self.text.configure(state="normal")
                self.text.delete("1.0", "end")
                self.text.insert("1.0", f"Aun no existe el archivo:\n{path}\n", ("warning",))
                self.text.configure(state="disabled")
                self.var_status.set(f"Esperando generación de {path.name}")
                return

            raw = path.read_text(encoding="utf-8", errors="replace").splitlines()
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            for line in raw[-2500:]:
                tags = self._classify_tags(line)
                self.text.insert("end", line + "\n", tags)
            self.text.see("end")
            self.text.configure(state="disabled")
            self.var_status.set(f"{path.name} | {len(raw)} líneas | {path}")
        except Exception as ex:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", f"No se pudo leer el log:\n{ex}\n", ("error",))
            self.text.configure(state="disabled")
            self.var_status.set("Error leyendo log")

    def _open_log_dir(self) -> None:
        import os
        import subprocess
        import sys

        log_dir = get_log_dir()
        try:
            if os.name == "nt":
                os.startfile(str(log_dir))  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.run(["open", str(log_dir)], check=False)
            else:
                subprocess.run(["xdg-open", str(log_dir)], check=False)
        except Exception:
            self.var_status.set(f"No se pudo abrir {log_dir}")

    def _schedule_refresh(self) -> None:
        self._refresh_job = self.after(2000, self._auto_refresh_tick)

    def _auto_refresh_tick(self) -> None:
        self._refresh_job = None
        if self.var_autorefresh.get():
            self._load_selected_log()
        self._schedule_refresh()

    def _toggle_refresh(self) -> None:
        if self.var_autorefresh.get():
            self._load_selected_log()

    def _on_close(self) -> None:
        try:
            if self._refresh_job is not None:
                self.after_cancel(self._refresh_job)
        except Exception:
            pass
        self.destroy()

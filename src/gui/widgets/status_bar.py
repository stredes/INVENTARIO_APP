# src/gui/widgets/status_bar.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional


class StatusBar(ttk.Frame):
    """
    Barra de estado flexible para Tkinter/ttk.

    Zonas:
      - Izquierda: mensaje principal (+ flash).
      - Centro   : badges dinámicos (Info/Success/Warning/Danger).
      - Derecha  : texto compacto (USR | ENV | DB | *).

    Extras:
      - ProgressBar integrada (determinate/indeterminate).
      - Métodos para setear usuario/ambiente/DB/unsaved.
      - 'Flash message' temporal que vuelve al mensaje anterior.
      - Funciones add_badge/update_badge/remove_badge.

    Estilos esperados (si usas ThemeManager):
      InfoBadge.TLabel, SuccessBadge.TLabel, WarningBadge.TLabel, DangerBadge.TLabel

    Uso mínimo:
        sb = StatusBar(parent); sb.pack(side="bottom", fill="x")
        sb.set_message("Listo")
        sb.set_info(user="admin", env="prod")
        sb.set_db_status("OK")
        sb.flash("Guardado con éxito", kind="success", ms=2000)
        sb.progress_start(indeterminate=True)  # o progress_set(42)
    """

    def __init__(self, master: tk.Misc, **kwargs) -> None:
        super().__init__(master, **kwargs)

        # Vars de estado
        self._msg_var = tk.StringVar(value="Listo")
        self._right_var = tk.StringVar(value="")
        self._user: Optional[str] = None
        self._env: Optional[str] = None
        self._db: Optional[str] = None
        self._unsaved: bool = False
        self._flash_after: Optional[str] = None

        # Layout base (3 columnas)
        self.columnconfigure(0, weight=1)   # mensaje crece
        self.columnconfigure(1, weight=0)   # badges auto
        self.columnconfigure(2, weight=0)   # info derecha

        # IZQUIERDA: mensaje + progress
        left = ttk.Frame(self)
        left.grid(row=0, column=0, sticky="we")
        left.columnconfigure(0, weight=1)

        self._lbl_msg = ttk.Label(left, textvariable=self._msg_var, anchor="w")
        self._lbl_msg.grid(row=0, column=0, sticky="we", padx=(8, 6), pady=4)

        self._pbar = ttk.Progressbar(left, mode="determinate", length=120)
        self._pbar.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._pbar.grid_remove()  # oculto por defecto

        # CENTRO: badges dinámicos
        self._badges_frame = ttk.Frame(self)
        self._badges_frame.grid(row=0, column=1, sticky="w")
        self._badges: Dict[str, ttk.Label] = {}

        # DERECHA: info compacta
        self._lbl_right = ttk.Label(self, textvariable=self._right_var, anchor="e", style="InfoBadge.TLabel")
        self._lbl_right.grid(row=0, column=2, sticky="e", padx=8, pady=4)

        # Fallback de estilos si ThemeManager no fue cargado aún
        self._ensure_min_styles()

        # Primer render del panel derecho
        self._render_right()

    # ------------------------------------------------------------------ #
    # Mensaje principal
    # ------------------------------------------------------------------ #
    def set_message(self, text: str) -> None:
        """Mensaje persistente (izquierda)."""
        self._msg_var.set(text)

    def flash(self, text: str, *, kind: str = "info", ms: int = 2000) -> None:
        """
        Muestra un mensaje temporal con badge a la izquierda y vuelve al anterior.
        kind: info | success | warning | danger
        """
        prev = self._msg_var.get()
        self._msg_var.set(text)
        # Pintamos badge temporal antes del texto
        self._lbl_msg.configure(style=self._kind_to_style(kind))

        # Cancelar flash previo si corresponde
        if self._flash_after is not None:
            try:
                self.after_cancel(self._flash_after)
            except Exception:
                pass

        def _restore():
            self._msg_var.set(prev)
            self._lbl_msg.configure(style="TLabel")
            self._flash_after = None

        self._flash_after = self.after(ms, _restore)

    # ------------------------------------------------------------------ #
    # Panel derecho: USR | ENV | DB | *
    # ------------------------------------------------------------------ #
    def set_info(self, *, user: Optional[str] = None, env: Optional[str] = None) -> None:
        if user is not None:
            self._user = user
        if env is not None:
            self._env = env
        self._render_right()

    def set_db_status(self, status: Optional[str]) -> None:
        """Ej: 'OK', 'RO', 'OFF', 'ERROR'."""
        self._db = status
        self._render_right()

    def set_unsaved(self, flag: bool) -> None:
        """Marca '*' cuando hay cambios sin guardar."""
        self._unsaved = bool(flag)
        self._render_right()

    def _render_right(self) -> None:
        parts = []
        if self._user:
            parts.append(f"USR: {self._user}")
        if self._env:
            parts.append(f"ENV: {self._env}")
        if self._db:
            parts.append(f"DB: {self._db}")
        if self._unsaved:
            parts.append("*")
        self._right_var.set(" | ".join(parts))

    # ------------------------------------------------------------------ #
    # ProgressBar integrada
    # ------------------------------------------------------------------ #
    def progress_show(self) -> None:
        self._pbar.grid()
        self._pbar.lift()

    def progress_hide(self) -> None:
        self._pbar.stop()
        self._pbar.grid_remove()

    def progress_start(self, *, indeterminate: bool = True) -> None:
        """Inicia progressbar. indeterminate=True para 'marquee'."""
        self.progress_show()
        if indeterminate:
            self._pbar.configure(mode="indeterminate")
            self._pbar.start(10)  # más pequeño = más rápido
        else:
            self._pbar.configure(mode="determinate")
            self._pbar["value"] = 0

    def progress_set(self, value: float) -> None:
        """Mueve progress determinate (0..100). Hace visible si estaba oculta."""
        self._pbar.configure(mode="determinate")
        self.progress_show()
        self._pbar["value"] = max(0, min(100, value))
        if value >= 100:
            self.progress_hide()

    # ------------------------------------------------------------------ #
    # Badges (centro)
    # ------------------------------------------------------------------ #
    def add_badge(self, key: str, text: str, *, kind: str = "info") -> None:
        """
        Agrega un badge identificado por 'key'. Si ya existe, lo actualiza.
        kind: info | success | warning | danger
        """
        if key in self._badges:
            self.update_badge(key, text=text, kind=kind)
            return

        lbl = ttk.Label(self._badges_frame, text=text, style=self._kind_to_style(kind))
        # Coloca los badges en fila
        col = len(self._badges)
        lbl.grid(row=0, column=col, padx=(0, 6))
        self._badges[key] = lbl

    def update_badge(self, key: str, *, text: Optional[str] = None, kind: Optional[str] = None) -> None:
        lbl = self._badges.get(key)
        if not lbl:
            return
        if text is not None:
            lbl.configure(text=text)
        if kind is not None:
            lbl.configure(style=self._kind_to_style(kind))

    def remove_badge(self, key: str) -> None:
        lbl = self._badges.pop(key, None)
        if lbl:
            lbl.destroy()
            # Re-compactar columnas
            for i, (k, w) in enumerate(self._badges.items()):
                w.grid_configure(column=i)

    def clear_badges(self) -> None:
        for lbl in self._badges.values():
            lbl.destroy()
        self._badges.clear()

    # ------------------------------------------------------------------ #
    # Utilidades
    # ------------------------------------------------------------------ #
    @staticmethod
    def _kind_to_style(kind: str) -> str:
        """Mapea 'kind' → estilo de badge."""
        kind = (kind or "info").lower()
        return {
            "info": "InfoBadge.TLabel",
            "success": "SuccessBadge.TLabel",
            "warning": "WarningBadge.TLabel",
            "danger": "DangerBadge.TLabel",
        }.get(kind, "InfoBadge.TLabel")

    def _ensure_min_styles(self) -> None:
        """
        Si el ThemeManager no estableció estilos de badges,
        define unos básicos para evitar errores visuales.
        """
        st = ttk.Style(self)
        # Si el estilo ya existe, no lo tocamos
        def ensure(style_name: str, bg: str, fg: str) -> None:
            try:
                st.configure(style_name)
                # si existe, style.lookup devuelve algo
                if st.lookup(style_name, "background"):
                    return
            except Exception:
                pass
            st.configure(style_name, background=bg, foreground=fg, padding=3)

        ensure("InfoBadge.TLabel",    "#E6F0FF", "#0B3C7A")
        ensure("SuccessBadge.TLabel", "#E8F7EE", "#146C43")
        ensure("WarningBadge.TLabel", "#FFF4E5", "#7A3D00")
        ensure("DangerBadge.TLabel",  "#FDEBEC", "#8A1C1C")


# ------------------------- DEMO manual (opcional) ------------------------- #
if __name__ == "__main__":
    root = tk.Tk()
    root.title("StatusBar Demo")
    root.geometry("720x200")
    sb = StatusBar(root)
    sb.pack(side="bottom", fill="x")

    # Ejemplos
    sb.set_message("Conectado a SQLite")
    sb.set_info(user="admin", env="dev")
    sb.set_db_status("OK")
    sb.add_badge("qc", "QC: dentro de rango", kind="success")
    sb.add_badge("urgent", "2 urgentes", kind="warning")

    def _simulate_long_task():
        sb.set_unsaved(True)
        sb.flash("Procesando impresión…", kind="info", ms=1000)
        sb.progress_start(indeterminate=True)
        root.after(2500, lambda: (sb.progress_set(100),
                                  sb.flash("Impresión lista", kind="success", ms=1500),
                                  sb.set_unsaved(False)))

    ttk.Button(root, text="Simular tarea", command=_simulate_long_task).pack(pady=16)
    root.mainloop()

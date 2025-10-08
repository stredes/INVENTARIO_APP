# src/gui/widgets/toast.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# API de alto nivel:
#   Toast.show(root, "Guardado con éxito", kind="success", ms=2500)
#   Toast.show(root, "Error al imprimir", kind="danger", position="tr")
#   Toast.show(root, "Pedido creado", kind="info", action=("Deshacer", on_undo))
#
# Posiciones: "br" (bottom-right), "tr" (top-right), "bl", "tl"
# ---------------------------------------------------------------------------


@dataclass
class ToastOptions:
    text: str
    kind: str = "info"          # info | success | warning | danger
    ms: int = 2500              # tiempo de vida
    position: str = "br"        # esquina: br/tr/bl/tl
    margin: int = 16            # margen a bordes
    gap: int = 8                # separación entre toasts
    max_width: int = 360        # ancho máx del texto (wrap)
    fade: bool = True           # fade-in/out
    action: Optional[Tuple[str, Callable[[], None]]] = None  # (texto, callback)
    dismiss_on_click: bool = True
    pause_on_hover: bool = True


class ToastManager:
    """Administra apilamiento y reposicionamiento por 'root' y 'position'."""
    _instances: Dict[int, "ToastManager"] = {}

    def __init__(self, root: tk.Tk | tk.Toplevel):
        self.root = root
        # Diccionario por esquina → lista de ventanas ToastWindow activas
        self.stacks: Dict[str, List["ToastWindow"]] = {"br": [], "tr": [], "bl": [], "tl": []}

    @classmethod
    def for_root(cls, root: tk.Tk | tk.Toplevel) -> "ToastManager":
        key = int(root.winfo_id())
        inst = cls._instances.get(key)
        if inst is None:
            inst = cls._instances[key] = ToastManager(root)
        return inst

    def add(self, win: "ToastWindow", position: str) -> None:
        stack = self.stacks[position]
        stack.append(win)
        self.reflow(position)

    def remove(self, win: "ToastWindow", position: str) -> None:
        stack = self.stacks[position]
        if win in stack:
            stack.remove(win)
            self.reflow(position)

    def reflow(self, position: str) -> None:
        """Re-posiciona toasts en la esquina indicada, respetando margin/gap."""
        stack = self.stacks[position]
        if not stack:
            return
        root = self.root
        root.update_idletasks()  # asegurar dimensiones reales

        margin = stack[0].opts.margin
        gap = stack[0].opts.gap

        rx, ry = root.winfo_rootx(), root.winfo_rooty()
        rw, rh = root.winfo_width(), root.winfo_height()

        # Coordenadas base por esquina
        if position == "br":
            base_x = rx + rw - margin
            base_y = ry + rh - margin
            # de abajo hacia arriba
            cur_y = base_y
            for win in reversed(stack):
                w, h = win.size()
                x = base_x - w
                y = cur_y - h
                win.move(x, y)
                cur_y = y - gap

        elif position == "tr":
            base_x = rx + rw - margin
            base_y = ry + margin
            cur_y = base_y
            for win in stack:
                w, h = win.size()
                x = base_x - w
                y = cur_y
                win.move(x, y)
                cur_y = y + h + gap

        elif position == "bl":
            base_x = rx + margin
            base_y = ry + rh - margin
            cur_y = base_y
            for win in reversed(stack):
                w, h = win.size()
                x = base_x
                y = cur_y - h
                win.move(x, y)
                cur_y = y - gap

        else:  # "tl"
            base_x = rx + margin
            base_y = ry + margin
            cur_y = base_y
            for win in stack:
                w, h = win.size()
                x = base_x
                y = cur_y
                win.move(x, y)
                cur_y = y + h + gap


class ToastWindow(tk.Toplevel):
    """Ventana de toast individual."""
    ICONS = {
        "info": "ℹ",
        "success": "✓",
        "warning": "⚠",
        "danger": "✖",
    }

    def __init__(self, manager: ToastManager, opts: ToastOptions):
        super().__init__(manager.root)
        self.manager = manager
        self.opts = opts
        self.position = opts.position
        self._alpha_target = 1.0
        self._hover = False
        self._auto_id: Optional[str] = None

        # Ventana flotante sin decoraciones
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Contenido
        bg, fg = self._resolve_colors(opts.kind)
        # Contenedor como tk.Frame para setear bg exacto
        self.container = tk.Frame(self, bg=bg, highlightthickness=0)
        self.container.pack(fill="both", expand=True)

        # Cuerpo (grid)
        self.container.grid_columnconfigure(1, weight=1)

        # Icono
        self.lbl_icon = tk.Label(self.container, text=self.ICONS.get(opts.kind, "ℹ"),
                                 bg=bg, fg=fg, font=("TkDefaultFont", 12, "bold"))
        self.lbl_icon.grid(row=0, column=0, sticky="n", padx=(10, 6), pady=10)

        # Mensaje
        self.lbl_text = tk.Label(self.container, text=opts.text, justify="left",
                                 wraplength=opts.max_width, bg=bg, fg=fg)
        self.lbl_text.grid(row=0, column=1, sticky="w", padx=0, pady=10)

        # Botones (acción + cerrar)
        btns = tk.Frame(self.container, bg=bg)
        btns.grid(row=0, column=2, sticky="ne", padx=(8, 10), pady=8)

        if opts.action:
            txt, cb = opts.action
            # Botón ttk con estilo semántico si existe
            btn = ttk.Button(btns, text=txt, style=_kind_to_button_style(opts.kind), command=lambda: self._run_action(cb))
            btn.pack(side="left", padx=(0, 6))

        close = tk.Button(btns, text="×", relief="flat", bd=0, bg=bg, fg=fg,
                          activebackground=bg, activeforeground=fg, command=self.close)
        close.pack(side="left")

        # Interacciones
        if opts.dismiss_on_click:
            self.container.bind("<Button-1>", lambda e: self.close())
            self.lbl_text.bind("<Button-1>", lambda e: self.close())
            self.lbl_icon.bind("<Button-1>", lambda e: self.close())

        if opts.pause_on_hover:
            # Pausa el autocierre si el mouse está encima
            self.container.bind("<Enter>", lambda e: self._set_hover(True))
            self.container.bind("<Leave>", lambda e: self._set_hover(False))

        # Apariencia inicial (fade-in)
        if opts.fade:
            try:
                self.attributes("-alpha", 0.0)
                self._fade_to(1.0, step=0.15, delay=12)
            except tk.TclError:
                pass  # en algunos entornos -alpha no está disponible

        # Agregar a la pila y programar autocierre
        self.manager.add(self, self.position)
        self._schedule_autoclose()

    # ---------------------------- Estilo & colores ------------------------ #

    @staticmethod
    def _ensure_min_styles():
        st = ttk.Style()
        def ensure(style_name: str, bg: str, fg: str):
            try:
                if st.lookup(style_name, "background"):
                    return
            except Exception:
                pass
            st.configure(style_name, background=bg, foreground=fg, padding=3)

        ensure("InfoBadge.TLabel",    "#E6F0FF", "#0B3C7A")
        ensure("SuccessBadge.TLabel", "#E8F7EE", "#146C43")
        ensure("WarningBadge.TLabel", "#FFF4E5", "#7A3D00")
        ensure("DangerBadge.TLabel",  "#FDEBEC", "#8A1C1C")

        # Botones semánticos (por si ThemeManager no está)
        ensure("Accent.TButton",      "#0B3C7A", "#FFFFFF")

    def _resolve_colors(self, kind: str) -> Tuple[str, str]:
        """Lee colores de estilos de ThemeManager si existen; si no, usa fallback."""
        self._ensure_min_styles()
        st = ttk.Style()
        map_badge = {
            "info": "InfoBadge.TLabel",
            "success": "SuccessBadge.TLabel",
            "warning": "WarningBadge.TLabel",
            "danger": "DangerBadge.TLabel",
        }
        sty = map_badge.get(kind, "InfoBadge.TLabel")
        bg = st.lookup(sty, "background") or "#E6F0FF"
        fg = st.lookup(sty, "foreground") or "#0B3C7A"
        return bg, fg

    # ------------------------------ Medición ------------------------------ #

    def size(self) -> Tuple[int, int]:
        self.update_idletasks()
        return self.winfo_width(), self.winfo_height()

    def move(self, x: int, y: int) -> None:
        self.geometry(f"+{int(x)}+{int(y)}")

    # ------------------------------ Vida útil ----------------------------- #

    def _schedule_autoclose(self):
        if self.opts.ms <= 0:
            return
        self._auto_id = self.after(self.opts.ms, self.close)

    def _set_hover(self, state: bool):
        self._hover = state
        # Si entra hover y hay autocierre programado, lo pausamos
        if state and self._auto_id is not None:
            try:
                self.after_cancel(self._auto_id)
            except Exception:
                pass
            self._auto_id = None
        # Si sale hover, reprogramamos
        elif not state and self._auto_id is None and self.opts.ms > 0:
            self._auto_id = self.after(self.opts.ms, self.close)

    def _fade_to(self, target: float, *, step: float = 0.1, delay: int = 10):
        try:
            cur = float(self.attributes("-alpha"))
        except tk.TclError:
            return  # no soportado
        if abs(cur - target) < 0.02:
            self.attributes("-alpha", target)
            return
        nxt = cur + (step if target > cur else -step)
        self.attributes("-alpha", max(0.0, min(1.0, nxt)))
        self.after(delay, lambda: self._fade_to(target, step=step, delay=delay))

    def _run_action(self, cb: Callable[[], None]):
        try:
            cb()
        finally:
            self.close()

    def close(self):
        # Remueve del stack y opcionalmente fade-out
        def _destroy():
            try:
                self.manager.remove(self, self.position)
            finally:
                self.destroy()

        if self.opts.fade:
            try:
                self._fade_to(0.0, step=0.2, delay=12)
                self.after(150, _destroy)
            except tk.TclError:
                _destroy()
        else:
            _destroy()


def _kind_to_button_style(kind: str) -> str:
    """Selecciona un estilo de botón acorde al tipo de toast."""
    k = (kind or "info").lower()
    return {
        "success": "Success.TButton",
        "warning": "Warning.TButton",
        "danger":  "Danger.TButton",
        "info":    "Accent.TButton",
    }.get(k, "Accent.TButton")


class Toast:
    """Fachada estática amigable."""
    @staticmethod
    def show(root: tk.Tk | tk.Toplevel, text: str, **kwargs) -> ToastWindow:
        opts = ToastOptions(text=text, **kwargs)
        mgr = ToastManager.for_root(root)
        win = ToastWindow(mgr, opts)
        return win


# ------------------------- DEMO manual (opcional) ------------------------- #
if __name__ == "__main__":
    # Pequeña demo
    root = tk.Tk()
    root.geometry("720x420")
    ttk.Button(root, text="Info",
               command=lambda: Toast.show(root, "Operación informativa")).pack(pady=6)
    ttk.Button(root, text="Éxito",
               command=lambda: Toast.show(root, "Guardado con éxito", kind="success")).pack(pady=6)
    ttk.Button(root, text="Warning (TR)",
               command=lambda: Toast.show(root, "Stock bajo en bodega", kind="warning", position="tr")).pack(pady=6)
    ttk.Button(root, text="Error con acción",
               command=lambda: Toast.show(
                   root,
                   "Impresión falló en la cola 'HP-Lab-01'",
                   kind="danger",
                   action=("Reintentar", lambda: print("retry")),
               )).pack(pady=6)

    root.mainloop()

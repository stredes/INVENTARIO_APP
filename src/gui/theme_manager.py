# src/gui/theme_manager.py
from __future__ import annotations
import configparser
from pathlib import Path
import sys
from tkinter import Tk, Menu, Text, Canvas
from tkinter import ttk
import tkinter.font as tkfont
from typing import Dict, Any

CONFIG_PATH = Path("config/settings.ini")
UI_STATE_PATH = Path("config/ui_state.ini")


def _frozen_dir() -> Path | None:
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
    except Exception:
        pass
    return None


def _meipass_dir() -> Path | None:
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base)
    except Exception:
        pass
    return None


def _external_ui_state_path() -> Path:
    """Devuelve la ruta preferida para persistir estado de UI (ui_state.ini)."""
    exedir = _frozen_dir()
    if exedir is not None:
        return exedir / UI_STATE_PATH
    return UI_STATE_PATH


class ThemeManager:
    """
    Gestor avanzado de temas para Tkinter + ttk (base 'clam').

    - +20 temas listos (Solarized, Nord, Dracula, Monokai, Ocean, Forest, etc.).
    - Estilos semánticos para botones/labels: Accent, Success, Warning, Danger, Info.
    - Ajustes de densidad (comfortable/compact) y de tamaño de fuente (sm/md/lg/xl).
    - Escalado DPI (tk scaling) persistente.
    - Colorea widgets Tk “puros” (Text/Canvas) y ttk (Button/Label/Entry/Treeview/...).
    - Persistencia en config/settings.ini -> [ui] theme, density, font_size, scaling.

    Uso:
        ThemeManager.attach(root)
        ThemeManager.apply("Nord Dark")
        ThemeManager.build_menu(menubar)  # agrega submenús: Tema / Densidad / Fuente / Escala
    """

    # --- Paletas ------------------------------------------------------------
    # Claves soportadas por cada tema:
    #   bg, fg, panel, accent, accent_fg, border, tab_bg, tab_sel_bg, entry_bg
    # Opcionales:
    #   select_bg, select_fg, success, warning, danger, info
    THEMES: Dict[str, Dict[str, str]] = {
        # Base del usuario (conservadas)
        "Light": {
            "bg": "#F5F5F7", "fg": "#111111", "panel": "#FFFFFF",
            "accent": "#2D7D46", "accent_fg": "#FFFFFF",
            "border": "#DADADA", "tab_bg": "#EDEDED",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Dark": {
            "bg": "#1F1F1F", "fg": "#EAEAEA", "panel": "#262626",
            "accent": "#3AA675", "accent_fg": "#0F0F0F",
            "border": "#3A3A3A", "tab_bg": "#2B2B2B",
            "tab_sel_bg": "#262626", "entry_bg": "#2C2C2C",
        },
        "Sepia": {
            "bg": "#F3E9D2", "fg": "#3B2F2F", "panel": "#FFF7E6",
            "accent": "#A67C52", "accent_fg": "#FFFFFF",
            "border": "#D9C7A5", "tab_bg": "#EADFC7",
            "tab_sel_bg": "#FFF7E6", "entry_bg": "#FFF7E6",
        },
        "Grayscale": {
            "bg": "#F0F0F0", "fg": "#222222", "panel": "#FFFFFF",
            "accent": "#5A5A5A", "accent_fg": "#FFFFFF",
            "border": "#C8C8C8", "tab_bg": "#E6E6E6",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "High Contrast": {
            "bg": "#000000", "fg": "#FFFFFF", "panel": "#000000",
            "accent": "#FFD400", "accent_fg": "#000000",
            "border": "#FFFFFF", "tab_bg": "#1A1A1A",
            "tab_sel_bg": "#000000", "entry_bg": "#0D0D0D",
        },

        # --- Extras modernos ---
        "Solarized Light": {
            "bg": "#FDF6E3", "fg": "#657B83", "panel": "#FFFDF5",
            "accent": "#268BD2", "accent_fg": "#FDF6E3",
            "border": "#E5DFC5", "tab_bg": "#EEE8D5",
            "tab_sel_bg": "#FFFDF5", "entry_bg": "#FFFDF5",
            "select_bg": "#268BD2", "select_fg": "#FDF6E3",
        },
        "Solarized Dark": {
            "bg": "#002B36", "fg": "#EEE8D5", "panel": "#073642",
            "accent": "#B58900", "accent_fg": "#002B36",
            "border": "#094048", "tab_bg": "#0A3A46",
            "tab_sel_bg": "#073642", "entry_bg": "#0A3A46",
            "select_bg": "#B58900", "select_fg": "#002B36",
        },
        "Nord Light": {
            "bg": "#ECEFF4", "fg": "#2E3440", "panel": "#FFFFFF",
            "accent": "#5E81AC", "accent_fg": "#ECEFF4",
            "border": "#D8DEE9", "tab_bg": "#E5E9F0",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Nord Dark": {
            "bg": "#2E3440", "fg": "#D8DEE9", "panel": "#3B4252",
            "accent": "#88C0D0", "accent_fg": "#2E3440",
            "border": "#4C566A", "tab_bg": "#434C5E",
            "tab_sel_bg": "#3B4252", "entry_bg": "#434C5E",
        },
        "Dracula": {
            "bg": "#282A36", "fg": "#F8F8F2", "panel": "#303241",
            "accent": "#BD93F9", "accent_fg": "#282A36",
            "border": "#44475A", "tab_bg": "#3B3E52",
            "tab_sel_bg": "#303241", "entry_bg": "#35384A",
        },
        "Monokai": {
            "bg": "#272822", "fg": "#F8F8F2", "panel": "#33342E",
            "accent": "#A6E22E", "accent_fg": "#272822",
            "border": "#49483E", "tab_bg": "#3A3B34",
            "tab_sel_bg": "#33342E", "entry_bg": "#3A3B34",
        },
        "Ocean": {
            "bg": "#E6F2F8", "fg": "#0B2E3B", "panel": "#FFFFFF",
            "accent": "#0077B6", "accent_fg": "#FFFFFF",
            "border": "#B9DFF5", "tab_bg": "#D8EDF7",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Forest": {
            "bg": "#F1F8F4", "fg": "#173A2F", "panel": "#FFFFFF",
            "accent": "#2D6A4F", "accent_fg": "#FFFFFF",
            "border": "#CFE8DA", "tab_bg": "#E4F2EA",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Rose Pine (Dawn)": {
            "bg": "#FAF4ED", "fg": "#575279", "panel": "#FFFFFF",
            "accent": "#D7827E", "accent_fg": "#FAF4ED",
            "border": "#F2E9E1", "tab_bg": "#F2E9E1",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Rose Pine (Moon)": {
            "bg": "#232136", "fg": "#E0DEF4", "panel": "#2A273F",
            "accent": "#C4A7E7", "accent_fg": "#232136",
            "border": "#393552", "tab_bg": "#2E2A4A",
            "tab_sel_bg": "#2A273F", "entry_bg": "#2E2A4A",
        },
        "Amber Light": {
            "bg": "#FFF8E1", "fg": "#3D2F00", "panel": "#FFFFFF",
            "accent": "#FFA000", "accent_fg": "#3D2F00",
            "border": "#FFE0B2", "tab_bg": "#FFECB3",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Slate": {
            "bg": "#F8FAFC", "fg": "#0F172A", "panel": "#FFFFFF",
            "accent": "#334155", "accent_fg": "#F8FAFC",
            "border": "#E2E8F0", "tab_bg": "#F1F5F9",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
        "Midnight Blue": {
            "bg": "#0F172A", "fg": "#E2E8F0", "panel": "#111827",
            "accent": "#60A5FA", "accent_fg": "#0F172A",
            "border": "#1F2937", "tab_bg": "#1E293B",
            "tab_sel_bg": "#111827", "entry_bg": "#1E293B",
        },
        "Terminal Green": {
            "bg": "#101010", "fg": "#00FF80", "panel": "#101010",
            "accent": "#00FF80", "accent_fg": "#0B0B0B",
            "border": "#00CC66", "tab_bg": "#141414",
            "tab_sel_bg": "#101010", "entry_bg": "#141414",
        },
        "Lavender": {
            "bg": "#F5F3FF", "fg": "#3B0764", "panel": "#FFFFFF",
            "accent": "#7C3AED", "accent_fg": "#F5F3FF",
            "border": "#E9D5FF", "tab_bg": "#F3E8FF",
            "tab_sel_bg": "#FFFFFF", "entry_bg": "#FFFFFF",
        },
    }

    # Valores semánticos por defecto (si el tema no define los suyos)
    DEFAULT_SEMANTIC = {
        "success": "#22C55E",  # verde
        "warning": "#F59E0B",  # ámbar
        "danger":  "#EF4444",  # rojo
        "info":    "#3B82F6",  # azul
        # selección genérica (texto/tablas/text)
        "select_bg": "#3B82F6",
        "select_fg": "#FFFFFF",
    }

    _root: Tk | None = None
    _style: ttk.Style | None = None

    # Estado persistente
    _current: str = "Light"
    _density: str = "comfortable"  # comfortable | compact
    _font_size: str = "md"         # sm | md | lg | xl
    _scaling: float = 1.0           # tk scaling (DPI)

    # Métricas por densidad
    DENSITY = {
        "comfortable": {
            "padding_x": 12, "padding_y": 8, "entry_ipady": 4, "row_height": 26
        },
        "compact": {
            "padding_x": 8, "padding_y": 4, "entry_ipady": 1, "row_height": 20
        }
    }

    # Tamaños de fuente base (afectan TkDefaultFont y derivados)
    FONT_SIZES = {
        "sm": 9,
        "md": 10,
        "lg": 11,
        "xl": 12,
    }

    # --------------------------------------------------------------------- #
    # Inicialización y menú
    # --------------------------------------------------------------------- #
    @classmethod
    def attach(cls, root: Tk) -> None:
        """
        Debe llamarse una vez al iniciar la app.
        """
        cls._root = root
        cls._style = ttk.Style(root)
        try:
            cls._style.theme_use("clam")  # base consistente cross-platform
        except Exception:
            pass

        # Cargar configuración previa
        # Usa strict=False para tolerar claves duplicadas en ui_state.ini y normalizar en _persist
        cfg = configparser.ConfigParser(strict=False)
        # 1) ui_state.ini (preferido)
        ui_path = _external_ui_state_path()
        if ui_path.exists():
            cfg.read(ui_path, encoding="utf-8")
        else:
            # 2) fallback legacy: settings.ini (solo lectura de [ui])
            ex_cfg = CONFIG_PATH if _frozen_dir() is None else (_frozen_dir() / CONFIG_PATH)
            try:
                if ex_cfg and Path(ex_cfg).exists():
                    cfg.read(ex_cfg, encoding="utf-8")
            except Exception:
                pass
        # Aplicar valores cargados (si existen)
        cls._current = cfg.get("ui", "theme", fallback=cls._current)
        cls._density = cfg.get("ui", "density", fallback=cls._density)
        cls._font_size = cfg.get("ui", "font_size", fallback=cls._font_size)
        cls._scaling = cfg.getfloat("ui", "scaling", fallback=cls._scaling)

        if cls._current not in cls.THEMES:
            cls._current = "Light"
        if cls._density not in cls.DENSITY:
            cls._density = "comfortable"
        if cls._font_size not in cls.FONT_SIZES:
            cls._font_size = "md"

        # Aplicar escala DPI ANTES de derivar fuentes
        try:
            root.tk.call("tk", "scaling", cls._scaling)
        except Exception:
            pass

        # Aplicar todo
        cls.apply(cls._current, persist=False)
        cls._apply_font_size(cls._font_size, persist=False)
        cls._apply_density(cls._density, persist=False)

        cls._persist()  # normaliza archivo con claves nuevas

    @classmethod
    def build_menu(cls, menubar: Menu) -> None:
        """
        Agrega submenús a la barra superior:
        - Tema (radio buttons)
        - Densidad (comfortable/compact)
        - Fuente (sm/md/lg/xl)
        - Escala (0.75/1.0/1.25/1.5)
        """
        # Menú de temas
        m_theme = Menu(menubar, tearoff=False)
        for name in sorted(cls.THEMES.keys()):
            m_theme.add_radiobutton(label=name, command=lambda n=name: cls.apply(n))
        menubar.add_cascade(label="Tema", menu=m_theme)

        # Menú densidad
        m_density = Menu(menubar, tearoff=False)
        for name in ("comfortable", "compact"):
            m_density.add_radiobutton(
                label=name.title(),
                command=lambda n=name: cls._apply_density(n)
            )
        menubar.add_cascade(label="Densidad", menu=m_density)

        # Menú fuente
        m_font = Menu(menubar, tearoff=False)
        for name in ("sm", "md", "lg", "xl"):
            m_font.add_radiobutton(
                label=name.upper(),
                command=lambda n=name: cls._apply_font_size(n)
            )
        menubar.add_cascade(label="Fuente", menu=m_font)

        # Menú escala
        m_scale = Menu(menubar, tearoff=False)
        for val in (0.75, 1.0, 1.25, 1.5, 1.75, 2.0):
            m_scale.add_radiobutton(
                label=f"{val:.2f}x",
                command=lambda v=val: cls._apply_scaling(v)
            )
        menubar.add_cascade(label="Escala", menu=m_scale)

    # --------------------------------------------------------------------- #
    # Aplicación de tema
    # --------------------------------------------------------------------- #
    @classmethod
    def apply(cls, name: str, persist: bool = True) -> None:
        if not cls._root or not cls._style:
            raise RuntimeError("ThemeManager.attach(root) no fue llamado")

        pal = cls._merged_palette(cls.THEMES[name])
        s = cls._style

        # Fondo raíz y color base
        cls._root.configure(bg=pal["bg"])
        s.configure(".", background=pal["panel"], foreground=pal["fg"])

        # --- Botones -------------------------------------------------------
        base_padx = cls.DENSITY[cls._density]["padding_x"]
        base_pady = cls.DENSITY[cls._density]["padding_y"]

        s.configure(
            "TButton",
            background=pal["panel"], foreground=pal["fg"],
            bordercolor=pal["border"], focusthickness=1, focuscolor=pal["accent"],
            padding=(base_padx, base_pady)
        )
        # Asegura contraste adecuado en estado "pressed"
        pressed_fg = pal.get("accent_fg")
        if cls._contrast_ratio(pal["accent"], pressed_fg or "#000000") < 4.5:
            pressed_fg = cls._best_text_color(pal["accent"])
        s.map(
            "TButton",
            background=[("active", pal["tab_bg"]), ("pressed", pal["accent"])],
            foreground=[("pressed", pressed_fg)],
            bordercolor=[("focus", pal["accent"]), ("active", pal["border"])]
        )

        # Botones semánticos (rellenos)
        cls._configure_filled_button("Accent.TButton", pal["accent"], pal["accent_fg"])
        cls._configure_filled_button("Success.TButton", pal["success"], pal["panel_fg_on_success"] if "panel_fg_on_success" in pal else "#FFFFFF")
        cls._configure_filled_button("Warning.TButton", pal["warning"], pal.get("warning_fg", "#1A1A1A"))
        cls._configure_filled_button("Danger.TButton",  pal["danger"],  pal.get("danger_fg", "#FFFFFF"))
        cls._configure_filled_button("Info.TButton",    pal["info"],    pal.get("info_fg", "#FFFFFF"))

        # Botones contorno
        cls._configure_outline_button("Outline.TButton", pal["accent"], pal["accent_fg"])
        cls._configure_outline_button("OutlineDanger.TButton", pal["danger"], pal.get("danger_fg", "#FFFFFF"))

        # Labels / Frames
        s.configure("TLabel", background=pal["panel"], foreground=pal["fg"])
        s.configure("TFrame", background=pal["panel"])
        s.configure("TLabelframe", background=pal["panel"], bordercolor=pal["border"])
        s.configure("TLabelframe.Label", background=pal["panel"], foreground=pal["fg"])

        # Badges (labels con fondo)
        s.configure("Badge.TLabel", background=cls._tint(pal["accent"], 0.9), foreground=pal["accent"])
        s.configure("SuccessBadge.TLabel", background=cls._tint(pal["success"], 0.85), foreground=pal["success"])
        s.configure("WarningBadge.TLabel", background=cls._tint(pal["warning"], 0.85), foreground=pal["warning"])
        s.configure("DangerBadge.TLabel",  background=cls._tint(pal["danger"],  0.85), foreground=pal["danger"])
        s.configure("InfoBadge.TLabel",    background=cls._tint(pal["info"],    0.85), foreground=pal["info"])

        # Entradas / Spinbox / Combobox
        entry_ipady = cls.DENSITY[cls._density]["entry_ipady"]
        s.configure("TEntry", fieldbackground=pal["entry_bg"], foreground=pal["fg"],
                    bordercolor=pal["border"], padding=(6, entry_ipady))
        s.configure("TSpinbox", fieldbackground=pal["entry_bg"], foreground=pal["fg"],
                    bordercolor=pal["border"], padding=(6, entry_ipady))
        s.configure("TCombobox", fieldbackground=pal["entry_bg"], foreground=pal["fg"],
                    bordercolor=pal["border"], arrowsize=18)

        # Notebook (tabs)
        s.configure("TNotebook", background=pal["bg"], bordercolor=pal["border"])
        s.configure("TNotebook.Tab", background=pal["tab_bg"], foreground=pal["fg"],
                    lightcolor=pal["border"], bordercolor=pal["border"], padding=(10, 6))
        sel_fg = pal["fg"]
        if cls._contrast_ratio(pal["tab_sel_bg"], sel_fg) < 4.5:
            sel_fg = cls._best_text_color(pal["tab_sel_bg"])
        s.map("TNotebook.Tab",
              background=[("selected", pal["tab_sel_bg"]), ("active", pal["tab_bg"])],
              foreground=[("selected", sel_fg)])

        # Treeview
        row_height = cls.DENSITY[cls._density]["row_height"]
        s.configure("Treeview",
                    background=pal["panel"], fieldbackground=pal["panel"],
                    foreground=pal["fg"], bordercolor=pal["border"],
                    rowheight=row_height)
        # Selección de Treeview con alto contraste
        t_sel_fg = pal["select_fg"]
        if cls._contrast_ratio(pal["select_bg"], t_sel_fg) < 4.5:
            t_sel_fg = cls._best_text_color(pal["select_bg"])
        s.map("Treeview",
              background=[("selected", pal["select_bg"])],
              foreground=[("selected", t_sel_fg)])

        # Encabezados de Treeview
        s.configure("Treeview.Heading",
                    background=pal["tab_bg"], foreground=pal["fg"],
                    bordercolor=pal["border"], relief="flat", padding=(6, 4))
        s.map("Treeview.Heading",
              background=[("active", cls._tint(pal["tab_bg"], 0.95))],
              foreground=[("active", pal["fg"])])

        # Scrollbar, Progressbar, Scale, Separator
        s.configure("TScrollbar", troughcolor=pal["panel"], bordercolor=pal["border"])
        s.configure("Horizontal.TProgressbar", troughcolor=pal["panel"], background=pal["accent"])
        s.configure("Vertical.TProgressbar", troughcolor=pal["panel"], background=pal["accent"])
        s.configure("TScale", background=pal["panel"], troughcolor=pal["tab_bg"])
        s.configure("TSeparator", background=pal["border"])

        # Checkbutton / Radiobutton
        s.configure("TCheckbutton",
                    background=pal["panel"], foreground=pal["fg"],
                    focuscolor=pal["accent"])
        s.configure("TRadiobutton",
                    background=pal["panel"], foreground=pal["fg"],
                    focuscolor=pal["accent"])

        # Menú nativo
        cls._configure_native_menu(pal)

        # Widgets Tk “puros” (no-ttk)
        cls._repaint_tk_widgets(pal)

        cls._current = name
        if persist:
            cls._persist()

    # --------------------------------------------------------------------- #
    # API pública adicional
    # --------------------------------------------------------------------- #
    @classmethod
    def apply_treeview_stripes(cls, tree: ttk.Treeview, *, odd: str | None = None, even: str | None = None) -> None:
        """
        Aplica un “zebra striping” simple al Treeview usando tags.
        Llama esto después de insertar filas o cuando refresques datos.
        """
        if not cls._style:
            return
        pal = cls._merged_palette(cls.THEMES[cls._current])
        odd = odd or cls._tint(pal["panel"], 0.97)
        even = even or cls._tint(pal["panel"], 0.99)
        # Define tags
        tree.tag_configure("oddrow", background=odd)
        tree.tag_configure("evenrow", background=even)
        # Asigna alternadamente
        for i, iid in enumerate(tree.get_children("")):
            tree.item(iid, tags=("evenrow" if i % 2 == 0 else "oddrow",))

    @classmethod
    def list_themes(cls) -> list[str]:
        return sorted(cls.THEMES.keys())

    # --------------------------------------------------------------------- #
    # Configuración secundaria
    # --------------------------------------------------------------------- #
    @classmethod
    def _apply_density(cls, density: str, persist: bool = True) -> None:
        cls._density = density
        # Reaplicamos el tema actual para observar cambios de padding/rowheight
        cls.apply(cls._current, persist=False)
        if persist:
            cls._persist()

    @classmethod
    def _apply_font_size(cls, size_key: str, persist: bool = True) -> None:
        if not cls._root:
            return
        cls._font_size = size_key
        base_size = cls.FONT_SIZES.get(size_key, 10)

        # Ajustamos fuentes Tk por nombre (afecta ttk)
        for fam in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont", "TkTooltipFont"):
            try:
                f = tkfont.nametofont(fam)
                f.configure(size=base_size)
            except Exception:
                pass

        # Reaplicamos tema para recalcular paddings en función del nuevo tamaño
        cls.apply(cls._current, persist=False)
        if persist:
            cls._persist()

    @classmethod
    def _apply_scaling(cls, value: float, persist: bool = True) -> None:
        if not cls._root:
            return
        cls._scaling = float(value)
        try:
            cls._root.tk.call("tk", "scaling", cls._scaling)
        except Exception:
            pass
        # Reaplicar tema y fuentes para que todo escale consistentemente
        cls._apply_font_size(cls._font_size, persist=False)
        cls.apply(cls._current, persist=False)
        if persist:
            cls._persist()

    # --------------------------------------------------------------------- #
    # Utilitarios internos
    # --------------------------------------------------------------------- #
    @classmethod
    def _merged_palette(cls, pal: Dict[str, str]) -> Dict[str, Any]:
        """
        Mergear paleta del tema con valores semánticos por defecto.
        """
        out = {**pal}
        for k, v in cls.DEFAULT_SEMANTIC.items():
            out.setdefault(k, v)
        # Derivados útiles + corrección de contraste
        out.setdefault("panel_fg_on_success", "#FFFFFF")
        # Asegura colores de selección razonables
        if "select_bg" not in out or not out.get("select_bg"):
            out["select_bg"] = out.get("accent", "#3B82F6")
        if cls._contrast_ratio(out["select_bg"], out.get("select_fg", "#FFFFFF")) < 4.5:
            out["select_fg"] = cls._best_text_color(out["select_bg"])
        # Asegura que accent_fg tenga contraste suficiente
        if cls._contrast_ratio(out.get("accent", "#3B82F6"), out.get("accent_fg", "#FFFFFF")) < 4.5:
            out["accent_fg"] = cls._best_text_color(out.get("accent", "#3B82F6"))
        return out

    @classmethod
    def _configure_filled_button(cls, stylename: str, bg: str, fg: str) -> None:
        if not cls._style:
            return
        pad = (cls.DENSITY[cls._density]["padding_x"], cls.DENSITY[cls._density]["padding_y"])
        cls._style.configure(stylename,
                             background=bg, foreground=fg,
                             bordercolor=bg, focusthickness=1, focuscolor=bg,
                             padding=pad)
        cls._style.map(stylename,
                       background=[("active", cls._tint(bg, 0.9)),
                                   ("pressed", cls._tint(bg, 0.8))],
                       bordercolor=[("focus", cls._tint(bg, 0.7))])

    @classmethod
    def _configure_outline_button(cls, stylename: str, border: str, fg: str) -> None:
        if not cls._style:
            return
        pad = (cls.DENSITY[cls._density]["padding_x"], cls.DENSITY[cls._density]["padding_y"])
        cls._style.configure(stylename,
                             background="",
                             foreground=border,
                             bordercolor=border,
                             focusthickness=1, focuscolor=border,
                             padding=pad)
        cls._style.map(stylename,
                       background=[("active", cls._tint(border, 0.95))],
                       foreground=[("active", fg)])

    @classmethod
    def _configure_native_menu(cls, pal: Dict[str, str]) -> None:
        try:
            mb = cls._root.nametowidget(cls._root["menu"]) if cls._root else None
            if isinstance(mb, Menu):
                active_fg = pal.get("accent_fg")
                if cls._contrast_ratio(pal["accent"], active_fg or "#000000") < 4.5:
                    active_fg = cls._best_text_color(pal["accent"])
                mb.configure(bg=pal["panel"], fg=pal["fg"],
                             activebackground=pal["accent"], activeforeground=active_fg,
                             bd=0)
        except Exception:
            pass

    @classmethod
    def _repaint_tk_widgets(cls, pal: Dict[str, str]) -> None:
        """
        Recorre el árbol de widgets y pinta widgets Tk “puros”.
        """
        def _recurse(widget):
            for w in widget.winfo_children():
                if isinstance(w, Canvas):
                    try:
                        w.configure(bg=pal["panel"], highlightbackground=pal["border"])
                    except Exception:
                        pass
                elif isinstance(w, Text):
                    try:
                        w.configure(bg=pal["entry_bg"], fg=pal["fg"],
                                    insertbackground=pal["fg"], highlightbackground=pal["border"],
                                    selectbackground=pal["select_bg"], selectforeground=pal["select_fg"])
                    except Exception:
                        pass
                else:
                    # Mínimo: dar fondo de panel
                    try:
                        w.configure(bg=pal["panel"])
                    except Exception:
                        pass
                    # Si el widget expone una API de refresco de tema, invócala
                    try:
                        refresh = getattr(w, "theme_refresh", None)
                        if callable(refresh):
                            refresh()
                    except Exception:
                        pass
                _recurse(w)
        if cls._root:
            _recurse(cls._root)

    @staticmethod
    def _tint(hex_color: str, factor: float) -> str:
        """
        Aclara/oscurece un color hex (#RRGGBB).
        factor < 1 => oscurece; factor > 1 => aclara (0.8, 0.9, 1.1, 1.2, ...)
        """
        hex_color = hex_color.lstrip("#")
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        r = max(0, min(255, int(r * factor)))
        g = max(0, min(255, int(g * factor)))
        b = max(0, min(255, int(b * factor)))
        return f"#{r:02X}{g:02X}{b:02X}"

    @classmethod
    def _persist(cls) -> None:
        cfg = configparser.ConfigParser(strict=False)
        cfg_path = _external_ui_state_path()
        if cfg_path.exists():
            cfg.read(cfg_path, encoding="utf-8")
        if "ui" not in cfg:
            cfg["ui"] = {}
        cfg["ui"]["theme"] = cls._current
        cfg["ui"]["density"] = cls._density
        cfg["ui"]["font_size"] = cls._font_size
        cfg["ui"]["scaling"] = str(cls._scaling)
        cfg_path.parent.mkdir(parents=True, exist_ok=True)
        with cfg_path.open("w", encoding="utf-8") as f:
            cfg.write(f)

    # --------------------------------------------------------------------- #
    # Contraste y utilitarios de color
    # --------------------------------------------------------------------- #
    @staticmethod
    def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
        hc = (hex_color or "#000000").lstrip("#")
        return int(hc[0:2], 16), int(hc[2:4], 16), int(hc[4:6], 16)

    @classmethod
    def _relative_luminance(cls, hex_color: str) -> float:
        r, g, b = cls._hex_to_rgb(hex_color)
        def _lin(c: float) -> float:
            c = c / 255.0
            return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
        R, G, B = _lin(r), _lin(g), _lin(b)
        return 0.2126 * R + 0.7152 * G + 0.0722 * B

    @classmethod
    def _contrast_ratio(cls, bg: str, fg: str) -> float:
        if not fg:
            return 0.0
        L1 = cls._relative_luminance(bg)
        L2 = cls._relative_luminance(fg)
        lighter, darker = (L1, L2) if L1 >= L2 else (L2, L1)
        return (lighter + 0.05) / (darker + 0.05)

    @classmethod
    def _best_text_color(cls, bg: str) -> str:
        # Elige negro o blanco según mejor contraste con el fondo
        return "#000000" if cls._contrast_ratio(bg, "#000000") >= cls._contrast_ratio(bg, "#FFFFFF") else "#FFFFFF"

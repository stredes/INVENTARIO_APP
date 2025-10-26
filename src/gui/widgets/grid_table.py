# src/gui/widgets/grid_table.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Iterable, Sequence, TYPE_CHECKING, Optional, List

# Tipado opcional para Pylance sin requerir que tksheet esté instalado
if TYPE_CHECKING:
    from tksheet import Sheet  # type: ignore[import-not-found]

# Forzar Treeview: desactivar tksheet siempre
_HAS_TKSHEET = False

# ThemeManager es opcional; no dependemos de APIs privadas
try:
    from src.gui.theme_manager import ThemeManager
except Exception:
    ThemeManager = None  # type: ignore

# Estilo/centrado global para Treeviews
try:
    from src.gui.treeview_utils import (
        apply_default_treeview_styles,
        enable_auto_center_for_new_treeviews,
        center_treeview,
        enable_treeview_sort,
    )
except Exception:
    def center_treeview(*_a, **_k):  # type: ignore
        pass


class GridTable(ttk.Frame):
    """
    Tabla basada únicamente en Treeview (sin tksheet).
    API:
        set_data(columns, rows)                 # rows: lista de dicts o secuencias
        set_row_backgrounds(bg_colors)         # lista del mismo largo que rows con str|None
        theme_refresh()                        # re-aplica colores al cambiar tema
    """

    def __init__(self, master, height: int = 12):
        super().__init__(master)
        self._fallback: Optional[ttk.Treeview] = None
        self._columns: list[str] = []

        if _HAS_TKSHEET:
            # Import local para no gatillar warnings de Pylance
            from tksheet import Sheet  # type: ignore
            self.sheet: Sheet = Sheet(
                self,
                show_x_scrollbar=True,
                show_y_scrollbar=True,
                show_top_left=False,
                height=300,
            )
            self.sheet.enable_bindings((
                "single_select", "row_select", "column_select", "drag_select",
                "copy", "paste", "ctrl_c", "ctrl_v",
                "edit_cell", "select_all",
            ))
            self.sheet.grid(row=0, column=0, sticky="nsew")
            self.rowconfigure(0, weight=1)
            self.columnconfigure(0, weight=1)
            self._apply_theme_to_sheet()
        else:
            # Fallback: Treeview + scrollbars + zebrado
            # Asegura estilos ya con root creado (evita crear root implícito)
            try:
                apply_default_treeview_styles()
                enable_auto_center_for_new_treeviews()
            except Exception:
                pass

            tv = self._fallback = ttk.Treeview(self, show="headings", height=height)
            vs = ttk.Scrollbar(self, orient="vertical", command=tv.yview)
            hs = ttk.Scrollbar(self, orient="horizontal", command=tv.xview)
            tv.configure(yscrollcommand=vs.set, xscrollcommand=hs.set)
            tv.grid(row=0, column=0, sticky="nsew")
            vs.grid(row=0, column=1, sticky="ns")
            hs.grid(row=1, column=0, sticky="we")
            self.rowconfigure(0, weight=1)
            self.columnconfigure(0, weight=1)
            try:
                center_treeview(tv)
            except Exception:
                pass

            # Tags para zebrado (nunca pisarán filas "state_*")
            base_bg = self._pal("panel", "#FFFFFF")
            tv.tag_configure("grid_odd", background=self._tint(base_bg, 1.00))
            tv.tag_configure("grid_even", background=self._tint(base_bg, 0.97))
            # Tags de estado (críticos)
            tv.tag_configure("state_low", background="#ffdddd")
            tv.tag_configure("state_high", background="#fff6cc")

    # ------------------------------ THEME ------------------------------- #
    def theme_refresh(self) -> None:
        """Reaplica colores al widget activo (sheet/tree) tras cambiar de tema."""
        if _HAS_TKSHEET:
            self._apply_theme_to_sheet()
        else:
            if self._fallback is None:
                return
            base_bg = self._pal("panel", "#FFFFFF")
            self._fallback.tag_configure("grid_odd", background=self._tint(base_bg, 1.00))
            self._fallback.tag_configure("grid_even", background=self._tint(base_bg, 0.97))
            self._retag_zebra()

    def _apply_theme_to_sheet(self) -> None:
        """Aplica la paleta al tksheet (seguro ante claves faltantes)."""
        if not _HAS_TKSHEET:
            return
        pal = {
            "panel": "#FFFFFF", "fg": "#111111", "border": "#DADADA",
            "tab_bg": "#EDEDED", "accent": "#2D7D46", "accent_fg": "#FFFFFF"
        }
        if ThemeManager is not None:
            try:
                current = getattr(ThemeManager, "_current", "Light")
                pal.update(getattr(ThemeManager, "THEMES", {}).get(current, {}))
            except Exception:
                pass
        select_bg = pal.get("select_bg", pal.get("accent", "#2D7D46"))
        select_fg = pal.get("select_fg", pal.get("accent_fg", "#FFFFFF"))
        try:
            self.sheet.configure(
                header_bg=pal.get("tab_bg"),
                header_fg=pal.get("fg"),
                top_left_corner_bg=pal.get("panel"),
                table_bg=pal.get("panel"),
                table_fg=pal.get("fg"),
                grid_color=pal.get("border"),
                selected_rows_bg=select_bg, selected_rows_fg=select_fg,
                selected_columns_bg=select_bg, selected_columns_fg=select_fg,
                selected_cells_bg=select_bg, selected_cells_fg=select_fg,
            )
        except Exception:
            pass

    # ------------------------------ DATA ------------------------------- #
    def set_data(self, columns: Sequence[str], rows: Iterable):
        """Carga datos en la tabla. `rows` puede ser lista de dicts o secuencias."""
        self._columns = list(columns)
        if _HAS_TKSHEET:
            self._set_data_sheet(columns, rows)
        else:
            self._set_data_tree(columns, rows)

    def _set_data_sheet(self, columns: Sequence[str], rows: Iterable) -> None:
        rows_list = list(rows) if not isinstance(rows, list) else rows
        if rows_list and isinstance(rows_list[0], dict):
            data = [[r.get(c, "") for c in columns] for r in rows_list]
        else:
            data = [[*r] for r in rows_list]
        try:
            self.sheet.headers(columns)
            self.sheet.set_sheet_data(data)
            self.sheet.refresh()
        except Exception:
            pass

    def _set_data_tree(self, columns: Sequence[str], rows: Iterable) -> None:
        tv = self._fallback
        if tv is None:
            return
        tv["columns"] = list(columns)
        for c in columns:
            tv.heading(c, text=str(c), anchor="center")
            tv.column(c, width=120, stretch=True, anchor="center")
        for iid in tv.get_children(""):
            tv.delete(iid)
        rows_list = list(rows) if not isinstance(rows, list) else rows
        if rows_list and isinstance(rows_list[0], dict):
            for r in rows_list:
                tv.insert("", "end", values=[r.get(c, "") for c in columns])
        else:
            for r in rows_list:
                tv.insert("", "end", values=list(r))
        self._retag_zebra()
        try:
            enable_treeview_sort(tv)
        except Exception:
            pass

    # ----------------------- ROW BACKGROUNDS (NEW) ---------------------- #
    def set_row_backgrounds(self, bg_colors: List[Optional[str]]) -> None:
        """
        Aplica colores por fila. bg_colors[i] puede ser None o un #RRGGBB.
        En Treeview: usa tags 'state_low'/'state_high' y NO pisa el zebrado.
        En tksheet: usa highlight de filas.
        """
        if _HAS_TKSHEET:
            try:
                self.sheet.clear_highlights()
            except Exception:
                pass
            try:
                for i, c in enumerate(bg_colors):
                    if c:
                        self.sheet.highlight_rows(rows=[i], bg=c)
                self.sheet.refresh()
            except Exception:
                pass
            return

        tv = self._fallback
        if tv is None:
            return
        children = tv.get_children("")
        for i, iid in enumerate(children):
            tags = set(tv.item(iid, "tags") or [])
            # Limpia tags previas de estado/bg
            tags = {t for t in tags if not (t.startswith("bg_") or t.startswith("state_"))}
            c = bg_colors[i] if i < len(bg_colors) else None
            if c:
                # Tag dinámico por color para soportar múltiples rangos
                tag = f"bg_{str(c).lstrip('#').lower()}"
                try:
                    tv.tag_configure(tag, background=str(c))
                except Exception:
                    pass
                tags.add(tag)
            tv.item(iid, tags=tuple(tags))
        # Reaplica zebra solo en filas SIN estado
        self._retag_zebra()

    # ------------------------------ ZEBRA ------------------------------- #
    def _retag_zebra(self) -> None:
        tv = self._fallback
        if tv is None:
            return
        children = tv.get_children("")
        for i, iid in enumerate(children):
            tags = set(tv.item(iid, "tags") or [])
            # Si ya tiene un color de estado/bg, no aplicamos zebra para no tapar color
            has_state = any(t.startswith("state_") or t.startswith("bg_") for t in tags)
            tags.discard("grid_even"); tags.discard("grid_odd")
            if not has_state:
                tags.add("grid_even" if i % 2 == 0 else "grid_odd")
            tv.item(iid, tags=tuple(tags))

    # ---------------------------- UTILIDADES ---------------------------- #
    @staticmethod
    def _tint(hex_color: str, factor: float) -> str:
        """Aclara/oscurece #RRGGBB; factor<1 oscurece, >1 aclara."""
        try:
            h = hex_color.lstrip("#")
            r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
            r = max(0, min(255, int(r * factor)))
            g = max(0, min(255, int(g * factor)))
            b = max(0, min(255, int(b * factor)))
            return f"#{r:02X}{g:02X}{b:02X}"
        except Exception:
            return hex_color

    def _pal(self, key: str, default: str) -> str:
        """Lee un color del ThemeManager si existe; si no, retorna default."""
        if ThemeManager is None:
            return default
        try:
            current = getattr(ThemeManager, "_current", "Light")
            themes = getattr(ThemeManager, "THEMES", {})
            return themes.get(current, {}).get(key, default)
        except Exception:
            return default

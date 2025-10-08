# src/gui/widgets/autocomplete_combobox.py
# -*- coding: utf-8 -*-
from __future__ import annotations
import unicodedata
import tkinter as tk
from tkinter import ttk
from typing import Callable, Iterable, List, Any, Dict, Optional

def _norm(s: str) -> str:
    """Normaliza a minúsculas y sin tildes para búsqueda aproximada."""
    if s is None:
        return ""
    s = str(s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.lower()

class AutoCompleteCombobox(ttk.Combobox):
    """
    ttk.Combobox con autocompletado por aproximación (substring)
    ignorando mayúsculas/tildes, sobre múltiples claves de búsqueda.

    Uso:
        cmb = AutoCompleteCombobox(parent, width=45, state="normal")
        cmb.set_dataset(
            items,
            keyfunc=lambda p: f"{p.id} - {p.nombre} [{p.sku}]",
            searchkeys=lambda p: [p.id, p.nombre, p.sku]
        )
        item = cmb.get_selected_item()
    """
    def __init__(self, master: tk.Misc, **kwargs):
        kwargs.setdefault("state", "normal")  # permitir escritura
        super().__init__(master, **kwargs)
        self._items: List[Any] = []
        self._keyfunc: Callable[[Any], str] = lambda x: str(x)
        self._searchkeys: Callable[[Any], Iterable[str]] = lambda x: [str(x)]
        self._display_to_item: Dict[str, Any] = {}
        self._popup_open: bool = False

        # Eventos (sin binding a "<Down>" para evitar recursión)
        self.bind("<KeyRelease>", self._on_keyrelease, add="+")
        self.bind("<<ComboboxSelected>>", self._on_selected, add="+")
        self.bind("<FocusOut>", self._on_focus_out, add="+")

    # -------- API pública --------
    def set_dataset(
        self,
        items: List[Any],
        keyfunc: Callable[[Any], str],
        searchkeys: Callable[[Any], Iterable[str]],
    ) -> None:
        self._items = list(items) if items else []
        self._keyfunc = keyfunc or (lambda x: str(x))
        self._searchkeys = searchkeys or (lambda x: [str(x)])
        self._rebuild_index()
        self._apply_values(self._display_to_item.keys())

    def get_selected_item(self) -> Optional[Any]:
        txt = self.get().strip()
        return self._display_to_item.get(txt)

    def clear(self) -> None:
        self.set("")

    # -------- internos --------
    def _rebuild_index(self) -> None:
        self._display_to_item.clear()
        for it in self._items:
            disp = self._keyfunc(it)
            self._display_to_item[str(disp)] = it

    def _apply_values(self, displays_iterable) -> None:
        self["values"] = list(displays_iterable)

    def _filter(self, typed: str) -> List[str]:
        if not typed:
            return list(self._display_to_item.keys())
        ntyped = _norm(typed)
        out: List[str] = []
        for it in self._items:
            try:
                keys = list(self._searchkeys(it))
            except Exception:
                keys = [self._keyfunc(it)]
            if any(ntyped in _norm(k) for k in keys if k is not None):
                out.append(self._keyfunc(it))
        return out

    def _post_dropdown(self) -> None:
        """Abre el desplegable sin disparar nuestros propios handlers."""
        try:
            self.tk.call('ttk::combobox::Post', self._w)
        except Exception:
            # Fallback: Alt-Down suele postear sin nuestros binds
            self.event_generate('<Alt-Down>')
        self._popup_open = True

    def _unpost_dropdown(self) -> None:
        """Cierra el desplegable."""
        try:
            self.tk.call('ttk::combobox::Unpost', self._w)
        except Exception:
            self.event_generate('<Escape>')
        self._popup_open = False

    # -------- eventos --------
    def _on_keyrelease(self, evt=None):
        # ignorar navegación/teclas de control
        if evt and evt.keysym in ("Up", "Down", "Return", "Escape", "Tab", "Alt_L", "Alt_R"):
            return

        typed = self.get()
        matches = self._filter(typed)
        self._apply_values(matches)
        self.icursor(tk.END)

        if matches:
            if not self._popup_open:
                self._post_dropdown()
        else:
            if self._popup_open:
                self._unpost_dropdown()

    def _on_selected(self, evt=None):
        # Asegura que el texto final corresponde a una opción válida
        txt = self.get().strip()
        if txt not in self._display_to_item:
            values = list(self["values"])
            if values:
                self.set(values[0])
        self._popup_open = False

    def _on_focus_out(self, evt=None):
        # Cierra el popup si queda abierto al perder foco
        if self._popup_open:
            self._unpost_dropdown()

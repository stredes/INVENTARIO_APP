"""Shared helpers for order-related GUI modules (compras/ventas/ordenes)."""

from __future__ import annotations

from typing import Sequence

from tkinter import ttk

from src.gui.treeview_utils import (
    apply_default_treeview_styles,
    enable_auto_center_for_new_treeviews,
)


def ensure_treeview_styling() -> None:
    """Apply default Treeview styling only once, ignoring Tk init errors."""
    try:
        apply_default_treeview_styles()
        enable_auto_center_for_new_treeviews()
    except Exception:
        pass


def safe_set_combobox_values(widget: ttk.Combobox, values: Sequence[str]) -> None:
    """Assign values to a Combobox, ignoring ttk backend quirks."""
    try:
        widget["values"] = tuple(values)
    except Exception:
        pass


def format_currency(value) -> str:
    """Format CLP currency with thousands separator, fallback to raw string."""
    try:
        amount = float(value or 0)
        formatted = f"${amount:,.0f}"
        return formatted.replace(",", ".")
    except Exception:
        return f"$ {value}"

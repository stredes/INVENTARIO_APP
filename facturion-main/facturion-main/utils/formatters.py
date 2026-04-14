from __future__ import annotations


def format_currency(value: float) -> str:
    formatted = f"{value:,.2f}"
    return f"$ {formatted}".replace(",", "X").replace(".", ",").replace("X", ".")


def month_label(month_key: str) -> str:
    year, month = month_key.split("-")
    return f"{month}/{year}"

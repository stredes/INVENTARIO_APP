from __future__ import annotations


def format_currency(value: float) -> str:
    formatted = f"{round(value or 0):,.0f}"
    return f"$ {formatted}".replace(",", "X").replace(".", ",").replace("X", ".")


def month_label(month_key: str) -> str:
    year, month = month_key.split("-")
    return f"{month}/{year}"

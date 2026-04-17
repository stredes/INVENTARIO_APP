from __future__ import annotations

from datetime import datetime


def validate_positive_number(value: str, field_name: str, allow_zero: bool = True, decimals: int = 0) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise ValueError(f"El campo '{field_name}' debe ser numérico.") from error
    if allow_zero and parsed < 0:
        raise ValueError(f"El campo '{field_name}' no puede ser negativo.")
    if not allow_zero and parsed <= 0:
        raise ValueError(f"El campo '{field_name}' debe ser mayor que cero.")
    return round(parsed, decimals)


def validate_required(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError(f"El campo '{field_name}' es obligatorio.")
    return cleaned


def validate_invoice_date(value: str) -> str:
    try:
        parsed = datetime.strptime(value.strip(), "%d/%m/%Y")
    except ValueError as error:
        raise ValueError("La fecha debe tener formato DD/MM/AAAA.") from error
    return parsed.strftime("%Y-%m-%d")


def format_invoice_date(value: str) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.strftime("%d/%m/%Y")
        except ValueError:
            continue
    return cleaned


def validate_month(month: str, year: str) -> str:
    if not month or not year:
        raise ValueError("Debe seleccionar mes y año.")
    month_number = int(month)
    year_number = int(year)
    if month_number < 1 or month_number > 12:
        raise ValueError("El mes seleccionado no es válido.")
    if year_number < 2000 or year_number > 2100:
        raise ValueError("El año seleccionado no es válido.")
    return f"{year_number}-{month_number:02d}"

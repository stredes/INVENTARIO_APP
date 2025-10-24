from __future__ import annotations

from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Iterable, Union, List, Dict, Any


# Set a sane, high precision to avoid intermediate rounding errors
ctx = getcontext()
ctx.prec = 28
ctx.rounding = ROUND_HALF_UP


NumberLike = Union[str, int, float, Decimal]


def D(value: NumberLike) -> Decimal:
    """
    Convert common numeric inputs to Decimal safely.
    - str: used as-is
    - float: convert via repr to avoid binary artifacts
    - int/Decimal: direct conversion
    """
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        # Use repr to capture full precision then Decimal for exact value
        return Decimal(repr(value))
    return Decimal(str(value))


def q2(value: NumberLike) -> Decimal:
    """
    Quantize to 2 decimal places using ROUND_HALF_UP.
    """
    return D(value).quantize(Decimal("0.01"))


def q0(value: NumberLike) -> Decimal:
    """
    Quantize to 0 decimal places (integer pesos display, etc.).
    """
    return D(value).quantize(Decimal("1"))


def money_sum(values: Iterable[NumberLike]) -> Decimal:
    total = Decimal(0)
    for v in values:
        total += D(v)
    return total


def mul(a: NumberLike, b: NumberLike, *, quantize_2: bool = True) -> Decimal:
    """Multiply two numbers exactly; by default quantize to 2 decimals."""
    res = D(a) * D(b)
    return q2(res) if quantize_2 else res


def fmt_2(value: NumberLike) -> str:
    """Format with 2 decimals as string."""
    return f"{q2(value):.2f}"


def vat_breakdown(items: List[Dict[str, Any]], *, currency: str = "CLP", iva_rate: NumberLike = "0.19") -> tuple[Decimal, Decimal, Decimal]:
    """
    Compute Neto, IVA and Total from a list of items.
    - Each item dict may have 'subtotal' or ('cantidad' and 'precio').
    - For CLP, applies 0-decimal rounding per line (common Chile practice):
        net_line = round(subtotal_line / (1+iva), 0)
        iva_line = subtotal_line - net_line
      Then sums lines to get totals, avoiding discrepancies.
    - For other currencies, uses 2-decimal rounding.
    Returns (neto, iva, total) as Decimals.
    """
    rate = D(iva_rate)
    total = Decimal(0)
    neto_sum = Decimal(0)
    iva_sum = Decimal(0)
    for it in items:
        sub = D(it.get("subtotal", D(it.get("cantidad", 0)) * D(it.get("precio", 0))))
        if currency.upper() == "CLP":
            sub = q0(sub)
            net_line = q0(sub / (Decimal(1) + rate))
            iva_line = sub - net_line
        else:
            sub = q2(sub)
            net_line = q2(sub / (Decimal(1) + rate))
            iva_line = q2(sub - net_line)
        total += sub
        neto_sum += net_line
        iva_sum += iva_line
    return neto_sum, iva_sum, total

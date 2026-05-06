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


def parse_money(value: NumberLike) -> Decimal:
    """
    Parse common money input formats into Decimal.

    Accepts plain numbers and Chilean-style values such as
    "1.325.365,90", "$1.325.365" or "CLP 1325365.90".
    """
    if isinstance(value, (int, float, Decimal)):
        return D(value)
    raw = str(value or "").replace("$", "").replace("CLP", "").strip()
    raw = raw.replace(" ", "")
    if not raw:
        return D(0)
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".")
    elif raw.count(".") > 1:
        raw = raw.replace(".", "")
    return D(raw)


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


def fmt_0(value: NumberLike, *, thousands: bool = False) -> str:
    """Format rounded integer pesos."""
    amount = q0(value)
    if thousands:
        return f"{amount:,.0f}".replace(",", ".")
    return f"{amount:.0f}"


def vat_breakdown(items: List[Dict[str, Any]], *, currency: str = "CLP", iva_rate: NumberLike = "0.19") -> tuple[Decimal, Decimal, Decimal]:
    """
    Compute Neto, IVA and Total from a list of items.
    - Each item dict may have 'subtotal' or ('cantidad' and 'precio').
    - Sums line subtotals first, then derives neto/iva from the GRAND TOTAL.
      This matches the common expectation that: neto = round(total/(1+iva)),
      iva = total - neto; with 0 decimals for CLP and 2 decimals otherwise.
    Returns (neto, iva, total) as Decimals.
    """
    rate = D(iva_rate)
    total = Decimal(0)
    for it in items:
        sub = D(it.get("subtotal", D(it.get("cantidad", 0)) * D(it.get("precio", 0))))
        if currency.upper() == "CLP":
            sub = q0(sub)
        else:
            sub = q2(sub)
        total += sub

    if currency.upper() == "CLP":
        neto = q0(total / (Decimal(1) + rate))
        iva = total - neto
    else:
        neto = q2(total / (Decimal(1) + rate))
        iva = q2(total - neto)

    return neto, iva, total

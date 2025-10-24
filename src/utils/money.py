from __future__ import annotations

from decimal import Decimal, getcontext, ROUND_HALF_UP
from typing import Iterable, Union


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


from __future__ import annotations

import re
from typing import Optional


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def normalize_rut(rut: str) -> str:
    """Normaliza RUT chileno: elimina espacios y puntos, mayúsculas.

    Ejemplos:
    - "12.345.678-k" -> "12345678-K"
    - "12345678-9"   -> "12345678-9"
    """
    s = (rut or "").replace(" ", "").replace(".", "").strip().upper()
    return s


def _rut_check_digit(num: str) -> str:
    """Calcula dígito verificador (módulo 11)."""
    seq = [2, 3, 4, 5, 6, 7]
    acc = 0
    for i, ch in enumerate(reversed(num)):
        acc += int(ch) * seq[i % len(seq)]
    dv = 11 - (acc % 11)
    if dv == 11:
        return "0"
    if dv == 10:
        return "K"
    return str(dv)


def is_valid_rut_chile(rut: str) -> bool:
    """Valida RUT chileno con dígito verificador.

    - Formato: NNNNNNNN-DV (sin puntos)
    - DV puede ser 0-9 o K
    """
    s = normalize_rut(rut)
    if "-" not in s or len(s) < 3:
        return False
    num, dv = s.split("-", 1)
    if not num.isdigit():
        return False
    expected = _rut_check_digit(num)
    return dv == expected


def is_valid_email(email: Optional[str]) -> bool:
    if not email:
        return True
    return bool(_EMAIL_RE.match(email.strip()))


def is_positive_int(value: int) -> bool:
    try:
        return int(value) > 0
    except Exception:
        return False


def is_non_negative_number(value) -> bool:
    try:
        return float(value) >= 0
    except Exception:
        return False


def is_non_empty(text: Optional[str]) -> bool:
    return bool((text or "").strip())


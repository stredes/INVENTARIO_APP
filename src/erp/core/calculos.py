from __future__ import annotations

"""
Funciones de cálculo contable (Neto, IVA, Total) y utilidades comunes.

- Maneja líneas con descuentos por ítem.
- Permite IVA configurable y documentos exentos.
- Expone `calcular_totales(conn, id_documento)` que recalcula a partir
  de la tabla `detalles` y persiste en `documentos`.
"""

from decimal import Decimal, ROUND_HALF_UP, getcontext
from typing import Iterable, Dict, Any
import sqlite3
from datetime import datetime


ctx = getcontext()
ctx.prec = 28
ctx.rounding = ROUND_HALF_UP


def D(x) -> Decimal:
    if isinstance(x, Decimal):
        return x
    return Decimal(str(x or 0))


def q2(x) -> Decimal:
    return D(x).quantize(Decimal("0.01"))


def q0(x) -> Decimal:
    return D(x).quantize(Decimal("1"))


def calcular_totales(conn: sqlite3.Connection, id_documento: int) -> Dict[str, float]:
    """
    Recalcula `monto_neto`, `monto_iva` y `monto_total` del documento y los guarda.

    Reglas:
    - `subtotal` = cantidad * precio_unitario (si viene nulo, se recalcula).
    - `subtotal_final` = subtotal - (subtotal * descuento_porcentaje / 100).
    - neto = SUM(subtotal_final)
    - iva = (exento ? 0 : neto * tasa_iva)
    - total = neto + iva
    """
    cur = conn.cursor()
    # Lee flags de cabecera
    row = cur.execute(
        "SELECT exento, tasa_iva FROM documentos WHERE id = ?", (id_documento,)
    ).fetchone()
    if not row:
        raise ValueError(f"Documento id={id_documento} no existe")
    exento = bool(row[0])
    tasa = D(row[1])

    # Recalcula líneas y acumula neto
    neto = D(0)
    for det in cur.execute(
        "SELECT id, cantidad, precio_unitario, descuento_porcentaje FROM detalles WHERE id_documento = ?",
        (id_documento,),
    ).fetchall():
        did, cant, precio, dcto = det
        cant = D(cant); precio = D(precio); dcto = D(dcto or 0)
        sub = q2(cant * precio)
        sub_final = q2(sub - (sub * dcto / D(100)))
        neto += sub_final
        cur.execute(
            "UPDATE detalles SET subtotal = ?, subtotal_final = ? WHERE id = ?",
            (float(sub), float(sub_final), did),
        )

    iva = D(0) if exento else q2(neto * tasa)
    total = neto + iva
    # Persistir en cabecera
    cur.execute(
        "UPDATE documentos SET monto_neto=?, monto_iva=?, monto_total=? WHERE id=?",
        (float(q2(neto)), float(q2(iva)), float(q2(total)), id_documento),
    )
    conn.commit()
    return {
        "monto_neto": float(q2(neto)),
        "monto_iva": float(q2(iva)),
        "monto_total": float(q2(total)),
    }


def log_event(conn: sqlite3.Connection, usuario: str, accion: str, documento_id: int,
              prev: str = "", new: str = "") -> None:
    """Inserta una entrada en `log_auditoria`."""
    conn.execute(
        "INSERT INTO log_auditoria(usuario, fecha_hora, accion, documento_afectado, valores_previos, valores_nuevos)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (usuario, datetime.now().isoformat(timespec="seconds"), accion, documento_id, prev, new),
    )
    conn.commit()


__all__ = ["calcular_totales", "log_event", "D", "q2", "q0"]


from __future__ import annotations

"""Módulo de Cotizaciones (COT).

Expone funciones de alto nivel para crear/actualizar documentos,
recalcular totales y generar PDF usando el generador existente.
"""

from typing import Dict, Any, List, Optional
import sqlite3

from src.erp.documentos._base import guardar_documento as _save_base, actualizar_estado as _estado_base
from src.erp.core.calculos import calcular_totales

# Reutilizamos el generador de Cotizaciones del proyecto
from src.utils.quote_generator import generate_quote_to_downloads as _gen_quote


def guardar_documento(conn: sqlite3.Connection, header: Dict[str, Any], items: List[Dict[str, Any]], *, usuario: str = "system") -> int:
    """Guarda una COT (insert o update) con sus ítems y totales.

    Retorna `id_documento`.
    """
    return _save_base(conn, "COT", header, items, usuario=usuario)


def calcular_totales_doc(conn: sqlite3.Connection, id_documento: int) -> Dict[str, float]:
    """Recalcula totales del documento id."""
    return calcular_totales(conn, id_documento)


def actualizar_estado(conn: sqlite3.Connection, id_documento: int, nuevo_estado: str, *, usuario: str = "system") -> None:
    """Actualiza estado de la cotización (ver reglas en _base.actualizar_estado)."""
    _estado_base(conn, id_documento, nuevo_estado, usuario=usuario)


def generar_pdf(conn: sqlite3.Connection, id_documento: int, *, auto_open: bool = True) -> str:
    """Genera el PDF de la COT usando el generador existente.

    Convierte cabecera y detalle a la estructura esperada por `generate_quote_to_downloads`.
    """
    cur = conn.cursor()
    doc = cur.execute("SELECT * FROM documentos WHERE id=?", (id_documento,)).fetchone()
    if not doc:
        raise ValueError("Documento no encontrado")
    rows = cur.execute("SELECT * FROM detalles WHERE id_documento=?", (id_documento,)).fetchall()

    supplier = {
        "id": str(doc["id"]),
        "nombre": doc["proveedor_cliente"],
        "contacto": None,
        "telefono": None,
        "email": None,
        "direccion": None,
    }
    items = [
        {
            # Mantener 'id' para compatibilidad (no usado para mostrar código)
            "id": r["codigo_item"] or "",
            "codigo": r["codigo_item"] or "",
            "nombre": r["descripcion"] or "",
            "cantidad": r["cantidad"],
            "precio": r["precio_unitario"],
            "subtotal": r["subtotal_final"] or r["subtotal"],
        }
        for r in rows
    ]
    return _gen_quote(
        quote_number=str(doc["folio"] or f"COT-{doc['id']}"),
        supplier=supplier,
        items=items,
        currency=doc["moneda"] or "CLP",
        notes=doc["observaciones"],
        auto_open=auto_open,
    )


__all__ = [
    "guardar_documento",
    "calcular_totales_doc",
    "actualizar_estado",
    "generar_pdf",
]


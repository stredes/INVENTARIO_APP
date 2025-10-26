from __future__ import annotations

"""Módulo de Órdenes de Venta (OV)."""

from typing import Dict, Any, List
import sqlite3

from src.erp.documentos._base import guardar_documento as _save_base, actualizar_estado as _estado_base
from src.erp.core.calculos import calcular_totales
from src.utils.so_generator import generate_so_to_downloads as _gen_so


def guardar_documento(conn: sqlite3.Connection, header: Dict[str, Any], items: List[Dict[str, Any]], *, usuario: str = "system") -> int:
    return _save_base(conn, "OV", header, items, usuario=usuario)


def calcular_totales_doc(conn: sqlite3.Connection, id_documento: int):
    return calcular_totales(conn, id_documento)


def actualizar_estado(conn: sqlite3.Connection, id_documento: int, nuevo_estado: str, *, usuario: str = "system") -> None:
    _estado_base(conn, id_documento, nuevo_estado, usuario=usuario)


def generar_pdf(conn: sqlite3.Connection, id_documento: int, *, auto_open: bool = True) -> str:
    cur = conn.cursor()
    doc = cur.execute("SELECT * FROM documentos WHERE id=?", (id_documento,)).fetchone()
    if not doc:
        raise ValueError("Documento no encontrado")
    rows = cur.execute("SELECT * FROM detalles WHERE id_documento=?", (id_documento,)).fetchall()

    company = {
        "name": doc["proveedor_cliente"],
        "rut": doc["rut_receptor"],
        "address": None,
    }
    items = [
        {
            "id": r["codigo_item"] or "",
            "nombre": r["descripcion"] or "",
            "cantidad": r["cantidad"],
            "precio": r["precio_unitario"],
            "subtotal": r["subtotal_final"] or r["subtotal"],
        }
        for r in rows
    ]
    return _gen_so(
        so_number=str(doc["folio"] or f"OV-{doc['id']}"),
        company=company,
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


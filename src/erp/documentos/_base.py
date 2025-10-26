from __future__ import annotations

"""
Base común para los módulos de documentos (COT/OC/OV).

Incluye utilidades para insertar/actualizar cabecera y detalles y para
generar folios. Mantiene una interfaz mínima que comparten los módulos
específicos.
"""

import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.erp.core.calculos import calcular_totales, log_event


def _ensure_header(conn: sqlite3.Connection, tipo: str, header: Dict[str, Any]) -> int:
    """Inserta o actualiza la cabecera y retorna `id`.

    Si `header` trae `id`, hace UPDATE (si el estado no está bloqueado).
    Si no, hace INSERT. Genera `folio` si falta.
    """
    cur = conn.cursor()
    doc_id = int(header.get("id") or 0)
    estado = str(header.get("estado", "pendiente")).strip().lower() or "pendiente"
    folio = header.get("folio") or f"{tipo}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    data = {
        "tipo": tipo,
        "folio": folio,
        "fecha_emision": header.get("fecha_emision") or datetime.now().strftime("%Y-%m-%d"),
        "fecha_vencimiento": header.get("fecha_vencimiento"),
        "proveedor_cliente": header.get("proveedor_cliente"),
        "rut_receptor": header.get("rut_receptor"),
        "nombre_receptor": header.get("nombre_receptor"),
        "moneda": header.get("moneda", "CLP"),
        "estado": estado,
        "observaciones": header.get("observaciones"),
        "referencia_id": header.get("referencia_id"),
        "exento": 1 if header.get("exento") else 0,
        "tasa_iva": float(header.get("tasa_iva", 0.19) or 0.19),
    }

    if doc_id:
        # Verifica estado bloqueado
        row = cur.execute("SELECT estado FROM documentos WHERE id=?", (doc_id,)).fetchone()
        if not row:
            raise ValueError(f"Documento id={doc_id} no existe")
        cur_estado = str(row[0]).strip().lower()
        if cur_estado in ("aprobado", "cerrado", "anulado"):
            raise ValueError("El documento no es editable en su estado actual")
        # Update
        cur.execute(
            (
                "UPDATE documentos SET tipo=:tipo, folio=:folio, fecha_emision=:fecha_emision, "
                "fecha_vencimiento=:fecha_vencimiento, proveedor_cliente=:proveedor_cliente, "
                "rut_receptor=:rut_receptor, nombre_receptor=:nombre_receptor, moneda=:moneda, "
                "estado=:estado, observaciones=:observaciones, referencia_id=:referencia_id, "
                "exento=:exento, tasa_iva=:tasa_iva WHERE id=:id"
            ),
            {**data, "id": doc_id},
        )
    else:
        cur.execute(
            (
                "INSERT INTO documentos(tipo, folio, fecha_emision, fecha_vencimiento, proveedor_cliente, "
                "rut_receptor, nombre_receptor, moneda, estado, observaciones, referencia_id, exento, tasa_iva)"
                " VALUES (:tipo, :folio, :fecha_emision, :fecha_vencimiento, :proveedor_cliente, :rut_receptor, "
                ":nombre_receptor, :moneda, :estado, :observaciones, :referencia_id, :exento, :tasa_iva)"
            ),
            data,
        )
        doc_id = int(cur.lastrowid)

    conn.commit()
    return doc_id


def _replace_details(conn: sqlite3.Connection, doc_id: int, items: List[Dict[str, Any]]) -> None:
    """Borra los detalles actuales e inserta los entregados."""
    cur = conn.cursor()
    cur.execute("DELETE FROM detalles WHERE id_documento = ?", (doc_id,))
    for it in items:
        cur.execute(
            (
                "INSERT INTO detalles(id_documento, codigo_item, descripcion, unidad, cantidad, precio_unitario, "
                "descuento_porcentaje, subtotal, subtotal_final) VALUES (?,?,?,?,?,?,?,?,?)"
            ),
            (
                doc_id,
                it.get("codigo_item"),
                it.get("descripcion"),
                it.get("unidad"),
                float(it.get("cantidad", 0) or 0),
                float(it.get("precio_unitario", 0) or 0),
                float(it.get("descuento_porcentaje", 0) or 0),
                0.0,
                0.0,
            ),
        )
    conn.commit()


def guardar_documento(conn: sqlite3.Connection, tipo: str, header: Dict[str, Any], items: List[Dict[str, Any]], *, usuario: str = "system") -> int:
    """Crea o actualiza un documento con sus detalles y recalcula totales.

    - `tipo`: 'COT' | 'OC' | 'OV'
    - `header`: dict con los campos de cabecera (ver _ensure_header)
    - `items`: lista de dicts con claves: codigo_item, descripcion, unidad, cantidad, precio_unitario, descuento_porcentaje
    """
    doc_id = _ensure_header(conn, tipo, header)
    _replace_details(conn, doc_id, items)
    res = calcular_totales(conn, doc_id)
    log_event(conn, usuario, f"guardar_{tipo}", doc_id, new=str({"header": header, "n_items": len(items)}))
    return doc_id


def actualizar_estado(conn: sqlite3.Connection, id_documento: int, nuevo_estado: str, *, usuario: str = "system") -> None:
    """Actualiza el estado y aplica reglas automáticas.

    - aprobado → bloquea edición (sin tocar totales)
    - cerrado  → bloquea edición
    - anulado  → totales a 0 (manteniendo el detalle histórico)
    """
    estado = str(nuevo_estado or "").strip().lower()
    cur = conn.cursor()
    prev = cur.execute("SELECT estado, monto_neto, monto_iva, monto_total FROM documentos WHERE id=?", (id_documento,)).fetchone()
    if not prev:
        raise ValueError("Documento no existe")

    if estado == "anulado":
        cur.execute(
            "UPDATE documentos SET estado=?, monto_neto=0, monto_iva=0, monto_total=0 WHERE id=?",
            (estado, id_documento),
        )
    else:
        cur.execute("UPDATE documentos SET estado=? WHERE id=?", (estado, id_documento))
    conn.commit()
    log_event(conn, usuario, f"estado_{estado}", id_documento, prev=str(dict(prev)))


__all__ = [
    "guardar_documento",
    "actualizar_estado",
]


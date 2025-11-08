# src/reports/pos_receipt.py
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional
import webbrowser
from datetime import datetime

from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home


def _fmt_clp0(value: float | int) -> str:
    try:
        n = int(round(float(value)))
    except Exception:
        n = 0
    return f"{n:,}".replace(",", ".")


def _text_fit(c: canvas.Canvas, text: str, max_w: float, font: str = "Helvetica", size: int = 8) -> str:
    """Trunca texto para que quepa en max_w (puntos) agregando 'â€¦' si es necesario."""
    c.setFont(font, size)
    if c.stringWidth(text, font, size) <= max_w:
        return text
    ell = "â€¦"
    for i in range(len(text), 0, -1):
        s = text[:i] + ell
        if c.stringWidth(s, font, size) <= max_w:
            return s
    return ell


def generate_pos_ticket_to_downloads(
    *,
    folio: str,
    fecha: datetime,
    customer: Optional[Dict[str, Any]],
    items: List[Dict[str, Any]],  # {codigo, descripcion, cantidad, precio, subtotal}
    payment: Optional[str] = None,
    width_mm: float = 80.0,  # tÃ­pico rollo 80mm (tambiÃ©n 58mm)
    iva_percent: float = 19.0,
    auto_open: bool = True,
) -> Path:
    """
    Genera un ticket tipo POS (boleta) compacto en la carpeta Descargas.
    - width_mm: ancho del papel
    - alto se calcula segÃºn cantidad de Ã­tems
    """
    # Totales
    total = sum(float(it.get("subtotal", 0) or 0) for it in items)
    if iva_percent and iva_percent > 0:
        neto = int(round(total / (1.0 + (iva_percent / 100.0))))
        iva = int(round(total - neto))
    else:
        neto = int(round(total))
        iva = 0

    # Medidas y salida
    w_pt = width_mm * mm
    # Alto base + por Ã­tem
    base_h_mm = 100.0
    per_item_mm = 6.0
    totals_mm = 28.0
    h_pt = max(140 * mm, (base_h_mm + per_item_mm * max(1, len(items)) + totals_mm) * mm)

    out_dir = _downloads_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"boleta_{folio}_{fecha.strftime('%Y%m%d-%H%M%S')}.pdf"
    out_path = out_dir / fname

    c = canvas.Canvas(str(out_path), pagesize=(w_pt, h_pt))

    # MÃ¡rgenes y cursor
    m = 4 * mm
    y = h_pt - m

    # Header
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(w_pt / 2, y, "BOLETA DE VENTA")
    y -= 12
    c.setFont("Helvetica", 8)
    c.drawCentredString(w_pt / 2, y, f"NÂº {folio}")
    y -= 12
    c.drawCentredString(w_pt / 2, y, fecha.strftime("%d/%m/%Y %H:%M"))
    y -= 16

    # Cliente (opcional y compacto)
    if customer:
        nom = str(customer.get("razon_social") or customer.get("nombre") or "")
        rut = str(customer.get("rut") or "")
        if nom:
            c.drawString(m, y, _text_fit(c, f"Cliente: {nom}", w_pt - 2 * m))
            y -= 10
        if rut:
            c.drawString(m, y, _text_fit(c, f"RUT: {rut}", w_pt - 2 * m))
            y -= 10

    # Separador
    y -= 2
    c.line(m, y, w_pt - m, y)
    y -= 10

    # Cabeceras
    c.setFont("Helvetica-Bold", 8)
    c.drawString(m, y, "DescripciÃ³n")
    c.drawRightString(w_pt - m, y, "Cant  Precio  Subtotal")
    y -= 10
    c.setFont("Helvetica", 8)

    # Ãtems
    for it in items:
        if y < 30 * mm:  # Evitar desbordes (muy conservador)
            break
        desc = str(it.get("descripcion") or "")
        qty = int(round(float(it.get("cantidad", 0) or 0)))
        precio = float(it.get("precio", 0) or 0)
        sub = float(it.get("subtotal", 0) or 0)

        # LÃ­nea descripciÃ³n (ajustar ancho)
        desc_fit = _text_fit(c, desc, w_pt - 2 * m)
        c.drawString(m, y, desc_fit)
        y -= 10

        # LÃ­nea cantidades/precios
        right = f"{qty}  {_fmt_clp0(precio)}  {_fmt_clp0(sub)}"
        c.drawRightString(w_pt - m, y, right)
        y -= 12

    # Separador y totales
    y -= 2
    c.line(m, y, w_pt - m, y)
    y -= 12

    c.setFont("Helvetica-Bold", 9)
    c.drawRightString(w_pt - m, y, f"Neto: {_fmt_clp0(neto)}")
    y -= 12
    c.drawRightString(w_pt - m, y, f"IVA {int(iva_percent)}%: {_fmt_clp0(iva)}")
    y -= 12
    c.setFont("Helvetica-Bold", 10)
    c.drawRightString(w_pt - m, y, f"TOTAL: {_fmt_clp0(total)}")
    y -= 16

    if payment:
        c.setFont("Helvetica", 8)
        c.drawString(m, y, _text_fit(c, f"Pago: {payment}", w_pt - 2 * m))
        y -= 12

    c.setFont("Helvetica", 8)
    c.drawCentredString(w_pt / 2, max(8 * mm, y), "Gracias por su compra")

    c.showPage()
    c.save()

    if auto_open:
        try:
            __try_open(str(out_path))
        except Exception:
            pass

    return out_path



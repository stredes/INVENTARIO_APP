# src/utils/quote_generator.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import webbrowser

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet

def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home

def _fmt_moneda(n: float, currency: str = "CLP") -> str:
    try:
        x = float(n)
    except Exception:
        return str(n)
    if currency.upper() == "CLP":
        return f"${int(round(x)):,.0f}".replace(",", ".")
    return f"${x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def _label(s: Optional[str]) -> str:
    return s or ""

def _styles():
    return getSampleStyleSheet()

def _header_story(st, quote_number: str, supplier: Dict[str, str]):
    story = []
    story.append(Paragraph("<b><font size=16>COTIZACIÓN</font></b>", st["Title"]))
    story.append(Spacer(1, 6))
    meta = f"<b>N°:</b> {quote_number} &nbsp;&nbsp;&nbsp; <b>Fecha:</b> {datetime.now().strftime('%d-%m-%Y %H:%M')}"
    story.append(Paragraph(meta, st["Normal"]))
    story.append(Spacer(1, 8))
    sup_html = (
        f"<b>Proveedor:</b> {_label(supplier.get('nombre'))}<br/>"
        f"<b>Contacto:</b> {_label(supplier.get('contacto'))} &nbsp;&nbsp; "
        f"<b>Tel:</b> {_label(supplier.get('telefono'))}<br/>"
        f"<b>Email:</b> {_label(supplier.get('email'))}<br/>"
        f"<b>Dirección:</b> {_label(supplier.get('direccion'))}"
    )
    story.append(Paragraph(sup_html, st["Normal"]))
    story.append(Spacer(1, 10))
    return story

def _items_table(items: List[Dict[str, object]], currency: str) -> Table:
    data = [["Código", "Producto", "Unidad", "Cantidad", "Precio Unit.", "Subtotal"]]
    for it in items:
        cant = int(float(it.get("cantidad", 0)))
        precio = float(it.get("precio", 0.0))
        sub = float(it.get("subtotal", cant * precio))
        data.append([
            str(it.get("id", "")),
            str(it.get("nombre", "")),
            str(it.get("unidad", "")),  # si no manejas unidad, queda vacío
            f"{cant:d}",
            _fmt_moneda(precio, currency),
            _fmt_moneda(sub, currency),
        ])
    tbl = Table(data, colWidths=[25*mm, 60*mm, 18*mm, 22*mm, 30*mm, 30*mm])
    tbl.setStyle(TableStyle([
        ("GRID", (0,0), (-1,-1), 0.4, colors.black),
        ("BACKGROUND", (0,0), (-1,0), colors.lightgrey),
        ("ALIGN", (3,1), (5,-1), "RIGHT"),
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("FONTSIZE", (0,0), (-1,-1), 9),
        ("LEADING", (0,0), (-1,-1), 11),
    ]))
    return tbl

def _totals_story(st, items: List[Dict[str, object]], currency: str):
    total = 0.0
    for it in items:
        try:
            total += float(it.get("subtotal", 0.0))
        except Exception:
            pass
    story = [Spacer(1, 6)]
    story.append(Paragraph(f"<b>Total:</b> {_fmt_moneda(total, currency)}", st["Heading3"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Esta cotización no constituye una orden de compra. "
        "Precios sujetos a cambio sin previo aviso y válidos por 7 días.",
        st["Italic"]
    ))
    return story

def generate_quote_to_downloads(
    *,
    quote_number: str,
    supplier: Dict[str, str],
    items: List[Dict[str, object]],
    currency: str = "CLP",
    notes: Optional[str] = None,
    auto_open: bool = True,
) -> str:
    """
    Genera un PDF 'COTIZACIÓN' en Descargas y retorna la ruta absoluta.
    No persiste compras ni modifica stock.
    """
    out_dir = _downloads_dir(); out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{quote_number}.pdf"

    st = _styles()
    story = []
    story += _header_story(st, quote_number, supplier)
    if notes:
        story.append(Paragraph(notes, st["Normal"]))
        story.append(Spacer(1, 8))
    story.append(_items_table(items, currency))
    story += _totals_story(st, items, currency)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm,
        topMargin=12*mm, bottomMargin=14*mm,
        title="Cotización", author="Inventario App",
    )
    doc.build(story)

    if auto_open:
        try:
            webbrowser.open(out_path.as_uri())
        except Exception:
            pass
    return str(out_path)

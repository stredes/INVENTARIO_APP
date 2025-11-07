from __future__ import annotations
"""
Generador de Cotizacion (PDF) con etiquetas en ASCII para evitar caracteres extraños.

API principal:
    generate_quote_to_downloads(quote_number, supplier, items, currency="CLP", notes=None, auto_open=True)

Estructuras esperadas:
    supplier: { nombre, contacto, telefono, direccion, pago }
    items: [ { id, codigo, nombre, cantidad, precio, descuento_porcentaje?, subtotal? } ]
        - precio: precio de venta (neto) mostrado en la UI
        - subtotal (opcional): si viene, se usa tal cual; si no, se calcula
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
import webbrowser

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import ParagraphStyle

from src.utils.helpers import get_company_info, get_downloads_dir, get_po_payment_method
from src.utils.money import D, q2, q0


def _fmt_moneda(n, currency: str = "CLP") -> str:
    try:
        x = D(n)
    except Exception:
        return str(n)
    cur = (currency or "CLP").strip().upper()
    if cur in ("CLP", "PESO CHILENO", "PESOS CHILENOS", "CHILEAN PESO", "CHILEAN PESOS"):
        return f"${x:,.0f}".replace(",", ".")
    return f"${x:,.2f}"


def _band(title: str):
    style = ParagraphStyle(name="band", fontName="Helvetica-Bold", fontSize=11, textColor=colors.white, alignment=1)
    tbl = Table([[Paragraph(title, style)]], colWidths=[180 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#1E6AA8")),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _header(company: Dict[str, Any], quote_number: str):
    h1 = ParagraphStyle(name="h1", fontName="Helvetica-Bold", fontSize=14, leading=16)
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)

    # Logo / Empresa
    logo_cell: Any
    logo_path = (company.get("logo") or "").strip()
    if logo_path and Path(logo_path).exists():
        try:
            img = Image(logo_path)
            img._restrictSize(60 * mm, 25 * mm)
            logo_cell = img
        except Exception:
            logo_cell = Paragraph(company.get("name", ""), h1)
    else:
        logo_cell = Paragraph(company.get("name", ""), h1)

    comp_lines = [
        f"<b>{company.get('name','')}</b>",
        f"RUT: {company.get('rut','')}" if company.get('rut') else "",
        company.get('address',''),
        " | ".join([x for x in [f"Tel: {company.get('phone','')}" if company.get('phone') else '', company.get('email','')] if x]),
    ]
    comp_html = "<br/>".join([x for x in comp_lines if x])
    right = Paragraph(f"<b>COTIZACION</b><br/>No. {quote_number}", h1)
    header_tbl = Table([[logo_cell, Paragraph(comp_html, p), right]], colWidths=[45 * mm, 90 * mm, 45 * mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    return header_tbl


def _items_table(items: List[Dict[str, object]], currency: str) -> Table:
    hdr = ParagraphStyle(name="hdr", fontName="Helvetica-Bold", fontSize=8, leading=9, alignment=1)
    cell = ParagraphStyle(name="cell", fontName="Helvetica", fontSize=9, leading=11)
    col_widths = [8, 16, 70, 12, 16, 28, 10, 22]
    assert sum(col_widths) == 182
    headers = [
        Paragraph("Item", hdr), Paragraph("Codigo", hdr), Paragraph("Descripcion", hdr), Paragraph("Unidad", hdr),
        Paragraph("Cantidad", hdr), Paragraph("Precio Venta", hdr), Paragraph("Dcto", hdr), Paragraph("Total", hdr)
    ]
    data = [headers]
    for idx, it in enumerate(items, start=1):
        cant = D(it.get("cantidad", 0) or 0)
        precio = D(it.get("precio", 0) or 0)
        dcto = D(it.get("descuento_porcentaje", it.get("dcto", 0)) or 0)
        if it.get("subtotal") is not None:
            sub_line = D(it.get("subtotal") or 0)
        else:
            sub_line = cant * precio * (D(1) - dcto / D(100))
        precio_mostrar = q0(precio) if currency.upper() == "CLP" else q2(precio)
        sub_line = q0(sub_line) if currency.upper() == "CLP" else q2(sub_line)
        data.append([
            str(idx),
            str(it.get("codigo") or it.get("id", "")),
            Paragraph(str(it.get("nombre", "")), cell),
            str(it.get("unidad", "U") or "U"),
            f"{int(cant) if cant == cant.to_integral_value() else cant}",
            _fmt_moneda(precio_mostrar, currency),
            Paragraph(f"{dcto} %", cell),
            _fmt_moneda(sub_line, currency),
        ])
    tbl = Table(data, colWidths=[w * mm for w in col_widths], repeatRows=1)
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EFF7")),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 11),
    ]))
    return tbl


def _totals_block(company: Dict[str, Any], items: List[Dict[str, object]], currency: str):
    iva_rate = D("0.19")
    net_total = D(0)
    for it in items:
        cant = D(it.get("cantidad", 0) or 0)
        precio = D(it.get("precio", 0) or 0)
        dcto = D(it.get("descuento_porcentaje", it.get("dcto", 0)) or 0)
        if it.get("subtotal") is not None:
            sub = D(it.get("subtotal") or 0)
        else:
            sub = cant * precio * (D(1) - dcto / D(100))
        sub = q0(sub) if currency.upper() == "CLP" else q2(sub)
        net_total += sub
    neto = net_total
    iva = q0(neto * iva_rate) if currency.upper() == "CLP" else q2(neto * iva_rate)
    total = neto + iva

    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    tot_tbl = Table([
        [Paragraph("<b>Neto :</b>", p), Paragraph(_fmt_moneda(neto, currency), p)],
        [Paragraph("<b>IVA :</b>", p), Paragraph(_fmt_moneda(iva, currency), p)],
        [Paragraph("<b>Total :</b>", p), Paragraph(_fmt_moneda(total, currency), p)],
    ], colWidths=[28 * mm, 32 * mm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))

    # Mostrar totales pegados a la derecha: envolver en tabla de 2 columnas
    wrap = Table([["", tot_tbl]], colWidths=[110 * mm, 70 * mm])
    wrap.setStyle(TableStyle([["VALIGN", (0, 0), (-1, -1), "TOP"]]))
    return [wrap]


def generate_quote_to_downloads(
    *,
    quote_number: str,
    supplier: Dict[str, str],
    items: List[Dict[str, object]],
    currency: str = "CLP",
    notes: Optional[str] = None,
    auto_open: bool = True,
) -> str:
    out_dir = get_downloads_dir(); Path(out_dir).mkdir(parents=True, exist_ok=True)
    out_path = Path(out_dir) / f"{quote_number}.pdf"

    company = get_company_info()
    story: List = []
    story.append(_header(company, quote_number))
    story.append(Spacer(1, 6))

    # Detalles generales
    story.append(_band("Detalles generales"))
    story.append(Spacer(1, 2))
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    left_lines = [
        ("Senor(es):", supplier.get('nombre') or "-"),
        ("Atencion:", supplier.get('contacto') or "-"),
        ("Telefono:", supplier.get('telefono') or "-"),
        ("Direccion:", supplier.get('direccion') or "-"),
    ]
    right_lines = [
        ("Fecha Documento:", datetime.now().strftime("%d/%m/%Y")),
        ("Forma de Pago:", supplier.get('pago') or get_po_payment_method()),
    ]
    def _two_col(rows, w_label_mm: float, w_val_mm: float):
        data = []
        for a, b in rows:
            data.append([Paragraph(f"<b>{a}</b>", p), Paragraph(str(b), p)])
        return Table(data, colWidths=[w_label_mm * mm, w_val_mm * mm])
    details = Table([[ _two_col(left_lines, 34, 78), _two_col(right_lines, 28, 40) ]], colWidths=[112 * mm, 68 * mm])
    details.setStyle(TableStyle([["VALIGN", (0, 0), (-1, -1), "TOP"]]))
    story.append(details)
    story.append(Spacer(1, 4))

    # Items + totales
    story.append(_items_table(items, currency))
    story.append(Spacer(1, 4))
    story += _totals_block(company, items, currency)

    # Observaciones
    story.append(Spacer(1, 3))
    story.append(_band("Observaciones:"))
    if notes:
        story.append(Spacer(1, 2))
        story.append(Paragraph(notes, p))

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=14 * mm, rightMargin=14 * mm,
        topMargin=14 * mm, bottomMargin=14 * mm,
        title="Cotizacion", author="Inventario App",
    )
    doc.build(story)

    if auto_open:
        try:
            webbrowser.open(out_path.as_uri())
        except Exception:
            pass
    return str(out_path)

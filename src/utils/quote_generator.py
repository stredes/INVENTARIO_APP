"""
Generador de Cotización con estilo unificado:
- Encabezado con logo y datos de empresa desde config/settings.ini
- Aviso "Documento sujeto a modificación (Provisorio)"
- Banda "Detalles generales" (datos del destinatario)
- Tabla de ítems
- Bloque de Facturación (Neto/IVA/Total) con datos de la empresa
"""

from __future__ import annotations
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
from src.utils.money import D, q2, vat_breakdown


def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home


def _fmt_moneda(n, currency: str = "CLP") -> str:
    try:
        x = D(n)
    except Exception:
        return str(n)
    if currency.upper() == "CLP":
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
            img._restrictSize(35 * mm, 20 * mm)
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
    right = Paragraph(f"<b>COTIZACIÓN</b><br/>Nº {quote_number}", h1)
    header_tbl = Table([[logo_cell, Paragraph(comp_html, p), right]], colWidths=[45 * mm, 90 * mm, 45 * mm])
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    return header_tbl


def _items_table(items: List[Dict[str, object]], currency: str) -> Table:
    data = [["Item", "Código", "Descripción", "Unidad", "Cantidad", "Precio Unit.", "Dcto", "Total"]]
    for idx, it in enumerate(items, start=1):
        cant = D(it.get("cantidad", 0) or 0)
        precio = D(it.get("precio", 0) or 0)
        sub = q2(it.get("subtotal", cant * precio) or 0)
        data.append([
            str(idx),
            str(it.get("id", "")),
            str(it.get("nombre", "")),
            str(it.get("unidad", "U") or "U"),
            f"{int(cant) if cant == cant.to_integral_value() else cant}",
            _fmt_moneda(precio, currency),
            _fmt_moneda(0, currency),
            _fmt_moneda(sub, currency),
        ])
    tbl = Table(
        data,
        colWidths=[8 * mm, 16 * mm, 72 * mm, 12 * mm, 16 * mm, 24 * mm, 10 * mm, 24 * mm],
        repeatRows=1,
    )
    tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.4, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EFF7")),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("LEADING", (0, 0), (-1, -1), 11),
    ]))
    return tbl


def _totals_block(company: Dict[str, Any], items: List[Dict[str, object]], currency: str):
    # Unificar cálculo con OC/OV para evitar discrepancias
    neto, iva, total = vat_breakdown(items, currency=currency, iva_rate=D("0.19"))
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

    left_lines = [
        f"<b>Facturar a:</b> {company.get('name','')}",
        f"RUT: {company.get('rut','-')}",
        "Presentar factura en:",
        company.get('address',''),
    ]
    left = Paragraph("<br/>".join([x for x in left_lines if x]), p)
    tbl = Table([[left, tot_tbl]], colWidths=[110 * mm, 70 * mm])
    tbl.setStyle(TableStyle([["VALIGN", (0, 0), (-1, -1), "TOP"]]))
    return [tbl]


def generate_quote_to_downloads(
    *,
    quote_number: str,
    supplier: Dict[str, str],
    items: List[Dict[str, object]],
    currency: str = "CLP",
    notes: Optional[str] = None,
    auto_open: bool = True,
) -> str:
    out_dir = _downloads_dir(); out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{quote_number}.pdf"

    company = get_company_info()
    story: List = []
    # Encabezado + aviso
    story.append(_header(company, quote_number))
    story.append(Spacer(1, 4))
    warn = ParagraphStyle(name="warn", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1E6AA8"), alignment=1)
    story.append(Paragraph("*Documento sujeto a modificación (Provisorio)*", warn))
    story.append(Spacer(1, 4))

    # Detalles generales
    story.append(_band("Detalles generales"))
    story.append(Spacer(1, 2))
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    left_lines = [
        ("Señor(es):", supplier.get('nombre') or "-"),
        ("Atención:", supplier.get('contacto') or "-"),
        ("Teléfono:", supplier.get('telefono') or "-"),
        ("Dirección:", supplier.get('direccion') or "-"),
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
    details = Table(
        [[ _two_col(left_lines, 34, 78), _two_col(right_lines, 28, 40) ]],
        colWidths=[112 * mm, 68 * mm]
    )
    details.setStyle(TableStyle([["VALIGN", (0, 0), (-1, -1), "TOP"]]))
    story.append(details)
    story.append(Spacer(1, 4))

    # Ítems + totales
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
        title="Cotización", author="Inventario App",
    )
    doc.build(story)

    if auto_open:
        try:
            webbrowser.open(out_path.as_uri())
        except Exception:
            pass
    return str(out_path)

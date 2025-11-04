from __future__ import annotations
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image

from src.utils.helpers import get_company_info, get_po_terms, get_downloads_dir, unique_path
from src.utils.po_generator import open_file  # reutilizamos open_file
from src.utils.money import D, q2


def _fmt_money(value, currency: str) -> str:
    try:
        cur = (currency or "CLP").strip().upper()
        if cur in ("CLP", "PESO CHILENO", "PESOS CHILENOS", "CHILEAN PESO", "CHILEAN PESOS"):
            return f"{D(value):,.0f}".replace(",", ".")
        return f"{D(value):,.2f}"
    except Exception:
        return str(value)


def _band(title: str, *, color=colors.HexColor("#1E6AA8")):
    style = ParagraphStyle(name="band", fontName="Helvetica-Bold", fontSize=11, textColor=colors.white, alignment=1)
    tbl = Table([[Paragraph(title, style)]], colWidths=[180 * mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TEXTCOLOR", (0, 0), (-1, -1), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def _header(company: Dict[str, Any], so_number: str):
    h1 = ParagraphStyle(name="h1", fontName="Helvetica-Bold", fontSize=14, leading=16)
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    logo_cell: Any
    logo_path = (company.get("logo") or "").strip()
    if logo_path and Path(logo_path).exists():
        try:
            img = Image(logo_path)
            img._restrictSize(35 * mm, 20 * mm)
            logo_cell = img
        except Exception:
            logo_cell = Paragraph(f"<b>{company.get('name','')}</b>", h1)
    else:
        logo_cell = Paragraph(f"<b>{company.get('name','')}</b>", h1)

    comp_lines = [
        f"<b>{company.get('name','')}</b>",
        f"RUT: {company.get('rut','')}" if company.get('rut') else "",
        company.get('address',''),
        " | ".join([x for x in [f"Tel: {company.get('phone','')}" if company.get('phone') else '', company.get('email','')] if x]),
    ]
    comp_html = "<br/>".join([x for x in comp_lines if x])
    right = Paragraph(f"<b>ORDEN DE VENTA</b><br/>Nº {so_number}", h1)
    header_table = Table([[logo_cell, Paragraph(comp_html, p), right]], colWidths=[45 * mm, 90 * mm, 45 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    return header_table


def generate_so_to_downloads(
    *,
    so_number: str,
    customer: Dict[str, Optional[str]],
    items: List[Dict[str, Any]],
    currency: str = "CLP",
    notes: Optional[str] = None,
    auto_open: bool = True,
) -> str:
    """Guarda la OV en Descargas con nombre único y la abre si se pide."""
    safe_customer = (customer.get("nombre") or "Cliente").strip().replace("/", "-").replace("\\", "-")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{so_number}_{safe_customer}_{ts}.pdf"
    out_dir = get_downloads_dir()
    out_path = unique_path(out_dir, filename)

    generate_so_pdf(
        output_path=str(out_path),
        so_number=so_number,
        customer=customer,
        items=items,
        currency=currency,
        notes=notes,
    )
    if auto_open:
        open_file(str(out_path))
    return str(out_path)




def generate_so_pdf(
    output_path: str,
    *,
    so_number: str,
    customer: Dict[str, Optional[str]],
    items: List[Dict[str, Any]],
    currency: str = "CLP",
    notes: Optional[str] = None,
) -> str:
    comp = get_company_info()
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
    )
    story: List[Any] = []

    # Encabezado
    story.append(_header(comp, so_number))
    story.append(Spacer(1, 4 * mm))

    # Detalles generales
    story.append(_band("Detalles generales"))
    story.append(Spacer(1, 2 * mm))
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    left_lines = [
        ("Cliente:", customer.get('nombre') or customer.get('razon_social') or "-"),
        ("Contacto:", customer.get('contacto') or "-"),
        ("Teléfono:", customer.get('telefono') or "-"),
        ("Email:", customer.get('email') or "-"),
        ("Dirección:", customer.get('direccion') or "-"),
    ]
    right_lines = [
        ("Fecha Documento:", datetime.now().strftime("%d/%m/%Y")),
        ("Rut:", customer.get('rut', '-') or "-"),
        ("Forma de Pago:", customer.get('pago') or "-"),
    ]

    def _two_col(rows, w_label_mm: float, w_val_mm: float):
        data = []
        for a, b in rows:
            data.append([Paragraph(f"<b>{a}</b>", p), Paragraph(str(b), p)])
        return Table(data, colWidths=[w_label_mm * mm, w_val_mm * mm])

    details = Table([[ _two_col(left_lines, 28, 84), _two_col(right_lines, 28, 40) ]], colWidths=[112 * mm, 68 * mm])
    details.setStyle(TableStyle([["VALIGN", (0, 0), (-1, -1), "TOP"]]))
    story.append(details)
    story.append(Spacer(1, 4 * mm))

    # Ítems: precio unitario sin IVA + descuento + total sin IVA
    hdr = ParagraphStyle(name="hdr", fontName="Helvetica-Bold", fontSize=8, leading=9, alignment=1)
    cell = ParagraphStyle(name="cell", fontName="Helvetica", fontSize=9, leading=11)
    headers = [
        Paragraph("Ítem", hdr), Paragraph("Código", hdr), Paragraph("Descripción", hdr), Paragraph("Unidad", hdr),
        Paragraph("Cantidad", hdr), Paragraph("Precio Unit.<br/>(sin IVA)", hdr), Paragraph("Dcto (%)", hdr), Paragraph("Total<br/>(sin IVA)", hdr)
    ]
    data = [headers]
    suma_neto = D(0)
    iva_rate = D("0.19")
    for idx, it in enumerate(items, start=1):
        cantidad = D(it.get("cantidad", 0) or 0)
        precio_bruto = D(it.get("precio", 0) or 0)
        dcto = D(it.get("descuento_porcentaje", 0) or 0)
        precio_neto = precio_bruto / (D(1) + iva_rate)
        total_linea_neto = cantidad * precio_neto * (D(1) - dcto / D(100))
        suma_neto += q2(total_linea_neto)
        data.append([
            str(idx), str(it.get("id", "") or ""), Paragraph(it.get("nombre", "") or "", cell), it.get("unidad", "U") or "U",
            f"{int(cantidad) if cantidad == cantidad.to_integral_value() else cantidad}",
            _fmt_money(precio_neto, currency), f"{dcto} %", _fmt_money(total_linea_neto, currency),
        ])

    items_table = Table(
        data,
        colWidths=[8 * mm, 16 * mm, 70 * mm, 12 * mm, 16 * mm, 28 * mm, 12 * mm, 20 * mm],
        repeatRows=1,
    )
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EFF7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
    ]))
    story.append(items_table)
    story.append(Spacer(1, 4 * mm))

    # Totales: Neto / IVA / Total
    story.append(_band("Facturación"))
    story.append(Spacer(1, 2 * mm))
    neto = q2(suma_neto)
    iva = q2(neto * iva_rate)
    total_v = q2(neto + iva)
    p2 = ParagraphStyle(name="p2", fontName="Helvetica", fontSize=10, leading=13)
    tot_tbl = Table([
        [Paragraph("<b>Neto :</b>", p2), Paragraph(_fmt_money(neto, currency), p2)],
        [Paragraph("<b>IVA :</b>", p2), Paragraph(_fmt_money(iva, currency), p2)],
        [Paragraph("<b>Total :</b>", p2), Paragraph(_fmt_money(total_v, currency), p2)],
    ], colWidths=[28 * mm, 32 * mm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))

    fact_left_lines = [
        f"<b>Cliente:</b> {customer.get('nombre','')}",
        f"RUT: {customer.get('rut','-')}",
        customer.get('direccion','') or '',
    ]
    fact_left = Paragraph("<br/>".join([x for x in fact_left_lines if x]), p)
    fact_tbl = Table([[fact_left, tot_tbl]], colWidths=[110 * mm, 70 * mm])
    fact_tbl.setStyle(TableStyle([["VALIGN", (0, 0), (-1, -1), "TOP"]]))
    story.append(fact_tbl)

    # Observaciones / Términos
    story.append(Spacer(1, 3 * mm))
    story.append(_band("Observaciones:"))
    if notes:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(str(notes), p))
    terms = get_po_terms()
    if terms:
        story.append(Spacer(1, 3 * mm))
        small2 = ParagraphStyle(name="small2", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.grey)
        story.append(Paragraph(terms, small2))

    doc.build(story)
    return str(output_path)



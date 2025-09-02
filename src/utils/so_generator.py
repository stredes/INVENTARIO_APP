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
    terms = get_po_terms()

    doc = SimpleDocTemplate(output_path, pagesize=A4, topMargin=18*mm, bottomMargin=15*mm, leftMargin=15*mm, rightMargin=15*mm)
    story = []

    h1 = ParagraphStyle(name="h1", fontName="Helvetica-Bold", fontSize=14, leading=16, spaceAfter=6)
    h2 = ParagraphStyle(name="h2", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceAfter=4)
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    small = ParagraphStyle(name="small", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.grey)

    # Encabezado
    logo_path = (comp.get("logo") or "").strip()
    if logo_path and Path(logo_path).exists():
        img = Image(logo_path); img._restrictSize(35*mm, 20*mm); logo_cell = img
    else:
        logo_cell = Paragraph(comp.get("name","Mi Empresa"), h2)

    comp_lines = [
        f"<b>{comp.get('name','')}</b>",
        f"RUT: {comp.get('rut','')}" if comp.get("rut") else "",
        comp.get("address",""),
        " · ".join([x for x in [f"Tel: {comp.get('phone','')}" if comp.get("phone") else "", comp.get("email","")] if x]),
    ]
    comp_html = "<br/>".join([x for x in comp_lines if x])

    header = Table([[logo_cell, Paragraph(comp_html, p), Paragraph(f"<b>ORDEN DE VENTA</b><br/>N° {so_number}", h1)]],
                   colWidths=[45*mm, 90*mm, 45*mm])
    header.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP"), ("ALIGN",(2,0),(2,0),"RIGHT")]))
    story.append(header); story.append(Spacer(1, 6*mm))

    # Cliente + fecha
    cust_lines = [
        f"<b>Cliente:</b> {customer.get('nombre','')}",
        f"<b>Contacto:</b> {customer.get('contacto','') or '-'}",
        f"<b>Tel:</b> {customer.get('telefono','') or '-'}",
        f"<b>Email:</b> {customer.get('email','') or '-'}",
        f"<b>Dirección:</b> {customer.get('direccion','') or '-'}",
    ]
    sup_table = Table([[Paragraph("<b>Fecha:</b> " + datetime.now().strftime("%d-%m-%Y"), p),
                        Paragraph("<br/>".join(cust_lines), p)]],
                      colWidths=[45*mm, 135*mm])
    sup_table.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"TOP")]))
    story.append(sup_table); story.append(Spacer(1, 4*mm))

    # Detalle
    data = [["ID", "Producto", "Cantidad", f"Precio ({currency})", f"Subtotal ({currency})"]]
    total = 0.0
    for it in items:
        cantidad = it.get("cantidad", 0)
        precio = float(it.get("precio", 0))
        subtotal = float(it.get("subtotal", cantidad * precio))
        data.append([str(it.get("id","")), it.get("nombre",""), f"{cantidad}", f"{precio:.2f}", f"{subtotal:.2f}"])
        total += subtotal

    table = Table(data, colWidths=[18*mm, 90*mm, 20*mm, 30*mm, 30*mm])
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0), colors.lightgrey),
        ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("ALIGN",(2,1),(4,-1),"RIGHT"),
        ("GRID",(0,0),(-1,-1), 0.3, colors.grey),
    ]))
    story.append(table); story.append(Spacer(1, 4*mm))

    total_table = Table([["", Paragraph("<b>Total:</b>", p), Paragraph(f"<b>{total:.2f} {currency}</b>", p)]],
                        colWidths=[128*mm, 32*mm, 28*mm])
    total_table.setStyle(TableStyle([("ALIGN",(-1,0),(-1,0),"RIGHT")]))
    story.append(total_table)

    if notes:
        story.append(Spacer(1, 3*mm)); story.append(Paragraph(f"<b>Notas:</b> {notes}", p))

    story.append(Spacer(1, 6*mm)); story.append(Paragraph(get_po_terms(), small))

    doc.build(story)
    return str(output_path)


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

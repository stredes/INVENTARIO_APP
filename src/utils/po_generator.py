from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import subprocess
import sys
from typing import List, Dict, Any, Optional
import os
import json

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image

from src.utils.helpers import (
    get_company_info,
    get_po_terms,
    get_po_payment_method,
    get_downloads_dir,
    unique_path,
)
from src.utils.money import D, q2, q0


def _fmt_money(value, currency: str) -> str:
    try:
        if currency.upper() == "CLP":
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


def _header(company: Dict[str, Any], po_number: str):
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
    right = Paragraph(f"<b>ORDEN DE COMPRA</b><br/>Nº {po_number}", h1)
    header_table = Table([[logo_cell, Paragraph(comp_html, p), right]], colWidths=[45 * mm, 90 * mm, 45 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, -1), "RIGHT"),
    ]))
    return header_table


def _dump_po_json(path_without_ext: Path, *, po_number: str,
                  supplier: Dict[str, Optional[str]],
                  items: List[Dict[str, Any]],
                  currency: str, notes: Optional[str]) -> str:
    payload = {
        "schema": "po.v1",
        "po_number": po_number,
        "supplier": supplier,
        "items": items,
        "currency": currency,
        "notes": notes,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }

    def _default(o):
        if isinstance(o, Decimal):
            try:
                return float(o)
            except Exception:
                return str(o)
        return str(o)

    json_path = path_without_ext.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=_default), encoding="utf-8")
    return str(json_path)


def generate_po_pdf(
    output_path: str,
    *,
    po_number: str,
    supplier: Dict[str, Optional[str]],
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

    story.append(_header(comp, po_number))
    story.append(Spacer(1, 4 * mm))
    warn = ParagraphStyle(name="warn", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1E6AA8"), alignment=1)
    story.append(Paragraph("*Documento sujeto a modificación (Provisorio)*", warn))
    story.append(Spacer(1, 4 * mm))

    # Detalles generales
    story.append(_band("Detalles generales"))
    story.append(Spacer(1, 2 * mm))
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    left_lines = [
        ("Señor(es):", supplier.get('nombre') or supplier.get('razon_social') or "-"),
        ("Atención:", supplier.get('contacto') or "-"),
        ("Teléfono:", supplier.get('telefono') or "-"),
        ("Giro:", supplier.get('giro', '-') or "-"),
        ("Dirección:", supplier.get('direccion') or "-"),
        ("Despachar a:", supplier.get('direccion') or "-"),
    ]
    right_lines = [
        ("Fecha Documento:", datetime.now().strftime("%d/%m/%Y")),
        ("Rut:", supplier.get('rut', '-') or "-"),
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
    story.append(Spacer(1, 4 * mm))

    # Ítems (precio y total sin IVA)
    hdr = ParagraphStyle(name="hdr", fontName="Helvetica-Bold", fontSize=8, leading=9, alignment=1)
    cell = ParagraphStyle(name="cell", fontName="Helvetica", fontSize=9, leading=11)
    headers = [
        Paragraph("Ítem", hdr), Paragraph("Código", hdr), Paragraph("Descripción", hdr), Paragraph("Unidad", hdr),
        Paragraph("Cantidad", hdr), Paragraph("Precio Unit.<br/>(sin IVA)", hdr), Paragraph("Dcto", hdr), Paragraph("Total<br/>(sin IVA)", hdr)
    ]
    data = [headers]
    net_total = D(0)
    gross_total = D(0)
    for idx, it in enumerate(items, start=1):
        cantidad = D(it.get("cantidad", 0) or 0)
        precio_bruto = D(it.get("precio", 0) or 0)
        precio_neto_raw = precio_bruto / (D(1) + D("0.19"))
        precio_neto = q0(precio_neto_raw) if currency.upper() == "CLP" else q2(precio_neto_raw)
        dcto_pct = D(it.get("dcto_pct", 0) or 0)
        dcto_rate = dcto_pct / D(100)
        dcto_monto_raw = cantidad * precio_neto * dcto_rate
        subtotal_neto_raw = cantidad * precio_neto - dcto_monto_raw
        dcto_monto = q0(dcto_monto_raw) if currency.upper() == "CLP" else q2(dcto_monto_raw)
        subtotal_neto = q0(subtotal_neto_raw) if currency.upper() == "CLP" else q2(subtotal_neto_raw)
        data.append([
            str(idx), str(it.get("id", "") or ""), Paragraph(it.get("nombre", "") or "", cell), it.get("unidad", "U") or "U",
            f"{int(cantidad) if cantidad == cantidad.to_integral_value() else cantidad}",
            _fmt_money(precio_neto, currency), _fmt_money(dcto_monto, currency), _fmt_money(subtotal_neto, currency),
        ])
        net_total += D(subtotal_neto)
        sub_bruto = D(it.get("subtotal", (cantidad * precio_bruto)))
        sub_bruto = q0(sub_bruto) if currency.upper() == "CLP" else q2(sub_bruto)
        gross_total += sub_bruto

    items_table = Table(
        data,
        colWidths=[8 * mm, 16 * mm, 70 * mm, 12 * mm, 16 * mm, 28 * mm, 10 * mm, 22 * mm],
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

    # Facturación
    story.append(_band("Facturación"))
    story.append(Spacer(1, 2 * mm))
    p2 = ParagraphStyle(name="p2", fontName="Helvetica", fontSize=10, leading=13)
    neto = net_total
    total = gross_total
    iva = (total - neto) if currency.upper() != "CLP" else q0(total - neto)
    tot_tbl = Table([
        [Paragraph("<b>Neto :</b>", p2), Paragraph(_fmt_money(neto, currency), p2)],
        [Paragraph("<b>IVA :</b>", p2), Paragraph(_fmt_money(iva, currency), p2)],
        [Paragraph("<b>Total :</b>", p2), Paragraph(_fmt_money(total, currency), p2)],
    ], colWidths=[28 * mm, 32 * mm])
    tot_tbl.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("BOX", (0, 0), (-1, -1), 0.25, colors.grey),
    ]))

    fact_left_lines = [
        f"<b>Facturar a:</b> {comp.get('name','')}",
        f"RUT: {comp.get('rut','-')}",
        "Presentar factura en:",
        comp.get('address',''),
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


def open_file(path: str) -> None:
    """Abre un archivo con el visor del sistema de forma segura."""
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", path], check=False)
        else:
            subprocess.run(["xdg-open", path], check=False)
    except Exception:
        pass


def generate_po_to_downloads(
    *,
    po_number: str,
    supplier: Dict[str, Optional[str]],
    items: List[Dict[str, Any]],
    currency: str = "CLP",
    notes: Optional[str] = None,
    auto_open: bool = True,
    save_json: bool = True,
) -> str:
    safe_supplier = (supplier.get("nombre") or supplier.get("razon_social") or "Proveedor").strip().replace("/", "-").replace("\\", "-")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"{po_number}_{safe_supplier}_{ts}"

    downloads = get_downloads_dir()
    out_pdf = unique_path(downloads, base_name + ".pdf")

    generate_po_pdf(
        output_path=str(out_pdf),
        po_number=po_number,
        supplier=supplier,
        items=items,
        currency=currency,
        notes=notes,
    )

    if save_json:
        _dump_po_json(
            out_pdf.with_suffix(""),
            po_number=po_number,
            supplier=supplier,
            items=items,
            currency=currency,
            notes=notes,
        )

    if auto_open:
        open_file(str(out_pdf))

    return str(out_pdf)


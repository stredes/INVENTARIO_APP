from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any, Optional
import os
import json  # <-- nuevo

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image,
)

from src.utils.helpers import (
    get_company_info,
    get_po_terms,
    get_po_payment_method,
    get_downloads_dir,
    unique_path,
)
from src.utils.money import D, q2


# -----------------------------
# Utilidades internas
# -----------------------------
def _fmt_money(value, currency: str) -> str:
    """
    Formatea el valor segÃºn moneda.
    - CLP: miles con punto, sin decimales (e.g., 1.234.567)
    - Otras: miles con coma, 2 decimales (e.g., 1,234,567.89)
    """
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

    # Logo
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
        f"RUT: {company.get('rut','')}" if company.get("rut") else "",
        company.get("address", ""),
        " | ".join([x for x in [f"Tel: {company.get('phone','')}" if company.get('phone') else '', company.get('email','')] if x]),
    ]
    comp_html = "<br/>".join([x for x in comp_lines if x])

    right = Paragraph(f"<b>ORDEN DE COMPRA</b><br/>NÂº {po_number}", h1)
    header_table = Table([[logo_cell, Paragraph(comp_html, p), right]], colWidths=[45*mm, 90*mm, 45*mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    return header_table


def _dump_po_json(path_without_ext: Path, *, po_number: str,
                  supplier: Dict[str, Optional[str]],
                  items: List[Dict[str, Any]],
                  currency: str, notes: Optional[str]) -> str:
    """
    Guarda un archivo JSON con los datos de la OC junto al PDF.
    """
    payload = {
        "schema": "po.v1",
        "po_number": po_number,
        "supplier": supplier,
        "items": items,
        "currency": currency,
        "notes": notes,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    # JSON seguro con Decimal: convertir a float (o str) automÃ¡ticamente
    def _default(o):
        if isinstance(o, Decimal):
            try:
                return float(o)
            except Exception:
                return str(o)
        return str(o)

    json_path = path_without_ext.with_suffix(".json")
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=_default),
        encoding="utf-8",
    )
    return str(json_path)


# -----------------------------
# API pÃºblica
# -----------------------------
def generate_po_pdf(
    output_path: str,
    *,
    po_number: str,
    supplier: Dict[str, Optional[str]],
    items: List[Dict[str, Any]],
    currency: str = "CLP",
    notes: Optional[str] = None,
) -> str:
    """
    Genera un PDF de Orden de Compra en 'output_path'.
    - supplier: dict con claves: id, nombre/razon social, rut, contacto, telefono, email, direccion
    - items: lista de dicts con claves: id, nombre, cantidad, precio, subtotal
    Retorna la ruta del archivo creado.
    """
    comp = get_company_info()
    terms = get_po_terms()

    # Documento
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        topMargin=16 * mm,
        bottomMargin=15 * mm,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
    )
    story = []

    # Estilos
    h1 = ParagraphStyle(name="h1", fontName="Helvetica-Bold", fontSize=14, leading=16, spaceAfter=6)
    h2 = ParagraphStyle(name="h2", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceAfter=4)
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    small = ParagraphStyle(name="small", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.grey)

    # Encabezado (logo + empresa + OC)
    header_table_data = []

    # Col 1: Logo (si existe) o nombre empresa en negrita
    logo_cell: Any
    logo_path = (comp.get("logo") or "").strip()
    if logo_path and Path(logo_path).exists():
        try:
            img = Image(logo_path)
            img._restrictSize(35 * mm, 20 * mm)
            logo_cell = img
        except Exception:
            logo_cell = Paragraph(f"<b>{comp.get('name','Mi Empresa')}</b>", h2)
    else:
        logo_cell = Paragraph(f"<b>{comp.get('name','Mi Empresa')}</b>", h2)

    # Col 2: datos de la empresa
    comp_lines = [
        f"<b>{comp.get('name','')}</b>",
        f"RUT: {comp.get('rut','')}" if comp.get("rut") else "",
        comp.get("address", ""),
        " Â· ".join(
            [x for x in [
                f"Tel: {comp.get('phone','')}" if comp.get("phone") else "",
                comp.get("email","") or "",
            ] if x]
        ),
    ]
    comp_html = "<br/>".join([x for x in comp_lines if x])

    # Col 3: tÃ­tulo + folio
    header_table_data.append([
        logo_cell,
        Paragraph(comp_html, p),
        Paragraph(f"<b>ORDEN DE COMPRA</b><br/>NÂ° {po_number}", h1),
    ])
    header_table = Table(header_table_data, colWidths=[45 * mm, 90 * mm, 45 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 4 * mm))

    # Estilo solicitado: banda 'Detalles generales' y tabla de dos columnas
    story.append(_band("Detalles generales"))
    story.append(Spacer(1, 2 * mm))
    p = ParagraphStyle(name="p", fontName="Helvetica", fontSize=10, leading=13)
    left_lines = [
        ("SeÃ±or(es):", supplier.get('nombre') or supplier.get('razon_social') or "-"),
        ("AtenciÃ³n:", supplier.get('contacto') or "-"),
        ("TelÃ©fono:", supplier.get('telefono') or "-"),
        ("Giro:", supplier.get('giro', '-') or "-"),
        ("DirecciÃ³n:", supplier.get('direccion') or "-"),
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
    details = Table([[ _two_col(left_lines, 34, 78), _two_col(right_lines, 28, 40) ]], colWidths=[112*mm, 68*mm])
    details.setStyle(TableStyle([["VALIGN", (0,0), (-1,-1), "TOP"]]))
    story.append(details)
    story.append(Spacer(1, 4 * mm))
    warn = ParagraphStyle(name="warn", fontName="Helvetica-Bold", fontSize=12, textColor=colors.HexColor("#1E6AA8"), alignment=1)
    story.append(Paragraph("*Documento sujeto a modificaciÃ³n (Provisorio)*", warn))
    story.append(Spacer(1, 4 * mm))

    # Detalle (tabla)
    data = [["Item", "CÃ³digo", "DescripciÃ³n", "Unidad", "Cantidad", "Precio Unit.", "Dcto", "Total"]]
    total = D(0)
    for idx, it in enumerate(items, start=1):
        cantidad = D(it.get("cantidad", 0) or 0)
        precio = D(it.get("precio", 0) or 0)
        subtotal = q2(it.get("subtotal", cantidad * precio) or 0)
        data.append([
            str(idx),
            str(it.get("id", "") or ""),
            it.get("nombre", "") or "",
            it.get("unidad", "U") or "U",
            f"{int(cantidad) if cantidad == cantidad.to_integral_value() else cantidad}",
            _fmt_money(precio, currency),
            _fmt_money(0, currency),
            _fmt_money(subtotal, currency),
        ])
        total += D(subtotal)

    table = Table(
        data,
        colWidths=[8*mm, 16*mm, 72*mm, 12*mm, 16*mm, 24*mm, 10*mm, 24*mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EFF7")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))

    # FacturaciÃ³n (neto / IVA / total)
    story.append(_band("FacturaciÃ³n"))
    story.append(Spacer(1, 2 * mm))
    iva_rate = D("0.19")
    neto = q2(D(total) / (D(1) + iva_rate))
    iva = q2(total - neto)
    tot_tbl = Table([
        [Paragraph("<b>Neto :</b>", p), Paragraph(_fmt_money(neto, currency), p)],
        [Paragraph("<b>IVA :</b>", p), Paragraph(_fmt_money(iva, currency), p)],
        [Paragraph("<b>Total :</b>", p), Paragraph(_fmt_money(total, currency), p)],
    ], colWidths=[28*mm, 32*mm])
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
    fact_tbl = Table([[fact_left, tot_tbl]], colWidths=[110*mm, 70*mm])
    fact_tbl.setStyle(TableStyle([["VALIGN", (0,0), (-1,-1), "TOP"]]))
    story.append(fact_tbl)

    # Observaciones / TÃ©rminos
    story.append(Spacer(1, 3 * mm))
    story.append(_band("Observaciones:"))
    if notes:
        story.append(Spacer(1, 2 * mm))
        story.append(Paragraph(str(notes), p))
    if terms:
        story.append(Spacer(1, 3 * mm))
        small2 = ParagraphStyle(name="small2", fontName="Helvetica", fontSize=9, leading=12, textColor=colors.grey)
        story.append(Paragraph(terms, small2))

    # Construir PDF
    doc.build(story)
    return str(output_path)


def open_file(path: str) -> None:
    """Abre el archivo con la app por defecto del SO."""
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif hasattr(os, "uname") and os.uname().sysname == "Darwin":
            os.system(f"open '{path}'")
        else:
            os.system(f"xdg-open '{path}'")
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
    save_json: bool = True,  # <-- nuevo
) -> str:
    """
    Genera la OC en la carpeta Descargas con nombre Ãºnico y la abre si se pide.
    AdemÃ¡s guarda un JSON con los datos (save_json=True).
    Retorna la ruta del PDF creado.
    """
    safe_supplier = (supplier.get("nombre") or supplier.get("razon_social") or "Proveedor").strip().replace("/", "-").replace("\\", "-")
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = f"{po_number}_{safe_supplier}_{ts}"

    downloads = get_downloads_dir()
    out_pdf = unique_path(downloads, base_name + ".pdf")

    # PDF
    generate_po_pdf(
        output_path=str(out_pdf),
        po_number=po_number,
        supplier=supplier,
        items=items,
        currency=currency,
        notes=notes,
    )

    # JSON (mismo nombre)
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


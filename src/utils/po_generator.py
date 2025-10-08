from __future__ import annotations
from datetime import datetime
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
    get_downloads_dir,
    unique_path,
)


# -----------------------------
# Utilidades internas
# -----------------------------
def _fmt_money(value: float, currency: str) -> str:
    """
    Formatea el valor según moneda.
    - CLP: miles con punto, sin decimales (e.g., 1.234.567)
    - Otras: miles con coma, 2 decimales (e.g., 1,234,567.89)
    """
    try:
        if currency.upper() == "CLP":
            return f"{value:,.0f}".replace(",", ".")
        return f"{value:,.2f}"
    except Exception:
        return str(value)


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
    json_path = path_without_ext.with_suffix(".json")
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(json_path)


# -----------------------------
# API pública
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
        topMargin=18 * mm,
        bottomMargin=15 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
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
        " · ".join(
            [x for x in [
                f"Tel: {comp.get('phone','')}" if comp.get("phone") else "",
                comp.get("email","") or "",
            ] if x]
        ),
    ]
    comp_html = "<br/>".join([x for x in comp_lines if x])

    # Col 3: título + folio
    header_table_data.append([
        logo_cell,
        Paragraph(comp_html, p),
        Paragraph(f"<b>ORDEN DE COMPRA</b><br/>N° {po_number}", h1),
    ])
    header_table = Table(header_table_data, colWidths=[45 * mm, 90 * mm, 45 * mm])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    story.append(header_table)
    story.append(Spacer(1, 6 * mm))

    # Datos proveedor y fecha actual
    sup_lines = [
        f"<b>Proveedor:</b> {supplier.get('nombre') or supplier.get('razon_social') or ''}",
        f"<b>RUT:</b> {supplier.get('rut','') or '-'}",
        f"<b>Vendedor:</b> {supplier.get('contacto','') or '-'}",
        f"<b>Tel:</b> {supplier.get('telefono','') or '-'}",
        f"<b>Email:</b> {supplier.get('email','') or '-'}",
        f"<b>Dirección:</b> {supplier.get('direccion','') or '-'}",
    ]
    sup_table = Table([[
        Paragraph("<b>Fecha:</b> " + datetime.now().strftime("%d-%m-%Y"), p),
        Paragraph("<br/>".join(sup_lines), p),
    ]], colWidths=[45 * mm, 135 * mm])
    sup_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(sup_table)
    story.append(Spacer(1, 4 * mm))

    # Detalle (tabla)
    data = [["ID", "Producto", "Cantidad", f"Precio ({currency})", f"Subtotal ({currency})"]]
    total = 0.0
    for it in items:
        cantidad = float(it.get("cantidad", 0) or 0)
        precio = float(it.get("precio", 0) or 0)
        subtotal = float(it.get("subtotal", cantidad * precio) or 0)
        data.append([
            str(it.get("id", "") or ""),
            it.get("nombre", "") or "",
            f"{int(cantidad) if cantidad.is_integer() else cantidad}",
            _fmt_money(precio, currency),
            _fmt_money(subtotal, currency),
        ])
        total += subtotal

    table = Table(data, colWidths=[18 * mm, 90 * mm, 20 * mm, 30 * mm, 30 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(table)
    story.append(Spacer(1, 4 * mm))

    # Total
    total_table = Table([[
        "", Paragraph("<b>Total:</b>", p),
        Paragraph(f"<b>{_fmt_money(total, currency)} {currency}</b>", p)
    ]], colWidths=[128 * mm, 32 * mm, 28 * mm])
    total_table.setStyle(TableStyle([
        ("ALIGN", (-1, 0), (-1, 0), "RIGHT"),
        ("LINEABOVE", (1, 0), (-1, 0), 0.25, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(total_table)

    # Notas
    if notes:
        story.append(Spacer(1, 3 * mm))
        story.append(Paragraph("<b>Notas:</b>", p))
        for line in str(notes).splitlines():
            if line.strip():
                story.append(Paragraph(line.strip(), p))

    # Términos
    if terms:
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(terms, small))

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
    Genera la OC en la carpeta Descargas con nombre único y la abre si se pide.
    Además guarda un JSON con los datos (save_json=True).
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

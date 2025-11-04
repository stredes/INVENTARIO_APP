from __future__ import annotations
from pathlib import Path
from typing import List, Dict, Any, Optional
import webbrowser
from datetime import datetime as _dt

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm

from src.utils.helpers import get_downloads_dir, unique_path


def _fmt_date(dt) -> str:
    try:
        if hasattr(dt, "strftime"):
            return dt.strftime("%d/%m/%Y")
        return str(dt)
    except Exception:
        return ""


def generate_reception_report_to_downloads(
    *,
    oc_number: str,
    supplier: Dict[str, Any],
    reception: Dict[str, Any],  # {id, fecha, tipo_doc, numero_documento}
    purchase_header: Dict[str, Any] | None,
    lines: List[Dict[str, Any]],  # [{id, nombre, unidad, cantidad, lote_serie, vence}]
    auto_open: bool = True,
) -> Path:
    out_dir = get_downloads_dir()
    fname = f"recepcion_{oc_number.replace(' ', '_')}_{_dt.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    out_path = unique_path(out_dir, fname)

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=12*mm,
        title="Informe de RecepciÃ³n",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10))

    story: list = []
    story.append(Paragraph("RecepciÃ³n de MercaderÃ­as", styles["Title"]))
    story.append(Spacer(1, 6))

    # Encabezado
    prov = supplier or {}
    rec = reception or {}
    ph = purchase_header or {}

    hdr_lines = [
        f"<b>OC:</b> {oc_number}",
        f"<b>RecepciÃ³n ID:</b> {rec.get('id','')}",
        f"<b>Fecha recepciÃ³n:</b> { _fmt_date(rec.get('fecha')) }",
        f"<b>Tipo doc:</b> {rec.get('tipo_doc','')}",
        f"<b>NÂ° doc:</b> {rec.get('numero_documento','')}",
    ]
    story.append(Paragraph(" ".join(hdr_lines), styles["BodyText"]))
    story.append(Spacer(1, 6))

    prov_lines = [
        f"<b>Proveedor:</b> {prov.get('nombre','')}",
        f"<b>Contacto:</b> {prov.get('contacto','')}",
        f"<b>Tel:</b> {prov.get('telefono','')}",
        f"<b>Email:</b> {prov.get('email','')}",
        f"<b>DirecciÃ³n:</b> {prov.get('direccion','')}",
    ]
    story.append(Paragraph(" ".join(prov_lines), styles["BodyText"]))

    # Datos del encabezado de compra (si existen)
    if ph:
        story.append(Spacer(1, 6))
        extra = []
        if ph.get('moneda'): extra.append(f"<b>Moneda:</b> {ph.get('moneda')}")
        if ph.get('tasa_cambio'): extra.append(f"<b>Tasa cambio:</b> {ph.get('tasa_cambio')}")
        if ph.get('fecha_documento'): extra.append(f"<b>F. doc:</b> {_fmt_date(ph.get('fecha_documento'))}")
        if ph.get('fecha_contable'): extra.append(f"<b>F. contable:</b> {_fmt_date(ph.get('fecha_contable'))}")
        if ph.get('fecha_vencimiento'): extra.append(f"<b>F. venc.:</b> {_fmt_date(ph.get('fecha_vencimiento'))}")
        if ph.get('unidad_negocio'): extra.append(f"<b>U. negocio:</b> {ph.get('unidad_negocio')}")
        if ph.get('proporcionalidad'): extra.append(f"<b>Proporcionalidad:</b> {ph.get('proporcionalidad')}")
        if ph.get('stock_policy'): extra.append(f"<b>Stock:</b> {ph.get('stock_policy')}")
        if extra:
            story.append(Paragraph(" ".join(extra), styles["BodyText"]))

    story.append(Spacer(1, 10))

    headers = ["ID", "Producto", "Unidad", "Cant.", "UbicaciÃ³n", "Lote/Serie", "Vence"]
    data = [headers]
    for ln in lines:
        data.append([
            str(ln.get('id','')),
            ln.get('nombre',''),
            ln.get('unidad','') or "",
            str(ln.get('cantidad','')),
            ln.get('ubicacion','') or "",
            ln.get('lote_serie','') or "",
            _fmt_date(ln.get('vence')) if ln.get('vence') else "",
        ])

    table = Table(data, colWidths=[35, None, 55, 40, 80, 100, 55])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 9),
        ("ALIGN",      (0, 0), (0, -1), "CENTER"),
        ("ALIGN",      (2, 1), (3, -1), "CENTER"),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFBFB")]),
    ]))
    story.append(table)

    doc.build(story)
    if auto_open:
        try:
            webbrowser.open(str(out_path))
        except Exception:
            pass
    return out_path

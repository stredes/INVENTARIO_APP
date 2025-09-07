# src/reports/sales_report_pdf.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any, Optional
import webbrowser
from datetime import datetime as _dt

# ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------
def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home

def _fmt_money_clp(value: float) -> str:
    """
    Formatea 1234567.89 -> '1.234.567,89' (estilo es-CL).
    """
    try:
        s = f"{float(value):,.2f}"         # 1,234,567.89
        s = s.replace(",", "_").replace(".", ",").replace("_", ".")
        return s
    except Exception:
        return str(value)

def _fmt_date_ddmmyyyy(dt) -> str:
    try:
        if hasattr(dt, "strftime"):
            # si tiene hora, la incluimos hh:mm
            if getattr(dt, "hour", None) is not None:
                return dt.strftime("%d/%m/%Y %H:%M")
            return dt.strftime("%d/%m/%Y")
        return str(dt)
    except Exception:
        return str(dt)

# ---------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------
def generate_sales_report_to_downloads(
    *,
    rows: Iterable[Dict[str, Any]],
    date_from: str,
    date_to: str,
    filters: Optional[Dict[str, Any]] = None,
    auto_open: bool = True,
) -> Path:
    """
    Genera PDF 'informe_ventas_YYYYMMDD-HHMMSS.pdf' en Descargas.

    rows: iterable de dicts {id, fecha, cliente, estado, total}
    date_from/date_to: strings dd/mm/aaaa para mostrar en encabezado
    filters: dict opcional para imprimir filtros aplicados
    """
    out_dir = _downloads_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"informe_ventas_{_dt.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    out_path = out_dir / fname

    # Documento
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36,
        title="Informe de Ventas",
    )
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal = styles["BodyText"]
    small = ParagraphStyle("small", parent=normal, fontSize=9, leading=11)
    h2 = styles["Heading2"]

    story = []

    # Encabezado
    story.append(Paragraph("Informe de Ventas", title_style))
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Rango: <b>{date_from}</b> a <b>{date_to}</b>", normal))

    # Filtros aplicados
    if filters:
        lines = []
        for k, v in filters.items():
            if v not in (None, "", []):
                lines.append(f"<b>{k}:</b> {v}")
        if lines:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Filtros aplicados:", h2))
            for ln in lines:
                story.append(Paragraph(ln, small))

    story.append(Spacer(1, 10))

    # Tabla
    headers = ["ID", "Fecha", "Cliente", "Estado", "Total (CLP)"]
    data = [headers]
    total_general = 0.0

    # Ordenamos por fecha
    def _key(r):
        f = r.get("fecha")
        # si no es comparable, lo convertimos a string
        return f if hasattr(f, "timestamp") else str(f)
    rows_sorted = sorted(list(rows), key=_key)

    for r in rows_sorted:
        fid = r.get("id", "")
        ffecha = _fmt_date_ddmmyyyy(r.get("fecha"))
        fcli = r.get("cliente", "") or ""
        fest = r.get("estado", "") or ""
        ftotal = float(r.get("total", 0.0))
        total_general += ftotal
        data.append([str(fid), ffecha, fcli, fest, _fmt_money_clp(ftotal)])

    table = Table(data, colWidths=[50, 110, None, 80, 90])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F0F0")),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.black),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, 0), 10),
        ("ALIGN",      (0, 0), (0, -1), "CENTER"),
        ("ALIGN",      (1, 0), (1, -1), "CENTER"),
        ("ALIGN",      (3, 0), (3, -1), "CENTER"),
        ("ALIGN",      (4, 0), (4, -1), "RIGHT"),
        ("GRID",       (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FBFBFB")]),
    ]))
    story.append(table)

    story.append(Spacer(1, 10))
    story.append(Paragraph(f"Total general: <b>CLP { _fmt_money_clp(total_general) }</b>", styles["Heading3"]))

    # Render
    doc.build(story)

    if auto_open:
        try:
            webbrowser.open(str(out_path))
        except Exception:
            pass

    return out_path

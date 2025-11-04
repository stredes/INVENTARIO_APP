from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any, Optional, List
import webbrowser
from datetime import datetime as _dt

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import mm


def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home


def _fmt_money2(value: float) -> str:
    try:
        s = f"{float(value):,.2f}"
        return s.replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return str(value)


def _fmt_date_ddmmyyyy(dt) -> str:
    try:
        if hasattr(dt, "strftime"):
            if getattr(dt, "hour", None) is not None:
                return dt.strftime("%d/%m/%Y %H:%M")
            return dt.strftime("%d/%m/%Y")
        return str(dt)
    except Exception:
        return str(dt)


def generate_purchases_report_to_downloads(
    *,
    rows: Iterable[Dict[str, Any]],
    date_from: str,
    date_to: str,
    filters: Optional[Dict[str, Any]] = None,
    auto_open: bool = True,
) -> Path:
    out_dir = _downloads_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"informe_compras_{_dt.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    out_path = out_dir / fname

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=12*mm,
        title="Informe / Ã“rdenes de Compra",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10))

    story: List = []
    title = Paragraph("Informe de Compras", styles["Title"])
    story.append(title)
    story.append(Spacer(1, 6))
    story.append(Paragraph(f"Rango: <b>{date_from}</b> a <b>{date_to}</b>", styles["BodyText"]))

    if filters:
        lines = []
        for k, v in filters.items():
            if v not in (None, "", []):
                lines.append(f"<b>{k}:</b> {v}")
        if lines:
            story.append(Spacer(1, 6))
            story.append(Paragraph("Filtros aplicados:", styles["Heading2"]))
            for ln in lines:
                story.append(Paragraph(ln, styles["BodyText"]))

    story.append(Spacer(1, 10))
    headers = ["ID", "Fecha", "Proveedor", "Estado", "Total (CLP)"]
    data = [headers]
    total_general = 0.0

    def _key(r):
        f = r.get("fecha")
        return f if hasattr(f, "timestamp") else str(f)

    rows_sorted = sorted(list(rows), key=_key)
    for r in rows_sorted:
        fid = r.get("id", "")
        ffecha = _fmt_date_ddmmyyyy(r.get("fecha"))
        fprov = r.get("proveedor", "") or ""
        fest = r.get("estado", "") or ""
        ftotal = float(r.get("total", 0.0))
        total_general += ftotal
        data.append([str(fid), ffecha, fprov, fest, _fmt_money2(ftotal)])

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
    story.append(Paragraph(f"Total general: <b>{_fmt_money2(total_general)}</b>", styles["Heading3"]))

    doc.build(story)

    if auto_open:
        try:
            webbrowser.open(str(out_path))
        except Exception:
            pass

    return out_path


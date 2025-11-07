# src/reports/sales_report_pdf.py
# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Iterable, Dict, Any, Optional, List, Tuple
import webbrowser
from datetime import datetime as _dt
import configparser

# ReportLab
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Image, PageBreak
)
from reportlab.lib.units import mm

# ---------------------------------------------------------------------
# Helpers: rutas, formato y empresa
# ---------------------------------------------------------------------
def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home

def _fmt_money2(value: float) -> str:
    """1234567.89 -> '1.234.567,89' (CLP estilo es-CL)."""
    try:
        s = f"{float(value):,.2f}"
        return s.replace(",", "_").replace(".", ",").replace("_", ".")
    except Exception:
        return str(value)

def _fmt_clp0(value: float | int) -> str:
    """CLP sin decimales: 1234567 -> '1.234.567'."""
    try:
        n = int(round(float(value)))
    except Exception:
        n = 0
    return f"{n:,}".replace(",", ".")

def _fmt_date_ddmmyyyy(dt) -> str:
    try:
        if hasattr(dt, "strftime"):
            if getattr(dt, "hour", None) is not None:
                return dt.strftime("%d/%m/%Y %H:%M")
            return dt.strftime("%d/%m/%Y")
        return str(dt)
    except Exception:
        return str(dt)

def _read_company_cfg() -> dict:
    """
    Lee datos de empresa desde config/company.ini.
    Claves: name, rut, giro, direccion, comuna, ciudad, telefono, email, logo_path
    """
    defaults = {
        "name": "Tu Empresa Spa",
        "rut": "76.123.456-7",
        "giro": "ComercializaciÃ³n de artÃ­culos",
        "direccion": "Calle Falsa 123",
        "comuna": "Santiago",
        "ciudad": "Santiago",
        "telefono": "+56 9 1234 5678",
        "email": "ventas@tuempresa.cl",
        "logo_path": "",
    }
    cfg_path = Path("config/company.ini")
    if cfg_path.exists():
        cfg = configparser.ConfigParser()
        cfg.read(cfg_path, encoding="utf-8")
        sec = cfg["company"] if "company" in cfg else cfg["DEFAULT"]
        for k in list(defaults.keys()):
            defaults[k] = sec.get(k, defaults[k])
    return defaults

def _try_logo_img(path: str | Path, max_w_mm: float, max_h_mm: float) -> Optional[Image]:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        img = Image(str(p))
        img._restrictSize(max_w_mm * mm, max_h_mm * mm)
        return img
    except Exception:
        return None

# ---------------------------------------------------------------------
# ConstrucciÃ³n de una pÃ¡gina â€œtipo facturaâ€ (una venta)
# ---------------------------------------------------------------------
def _venta_page_story(row: Dict[str, Any], styles, company: dict) -> List:
    """
    Construye la historia (flowables) de una venta con layout tipo Factura ElectrÃ³nica.
    Espera en `row`:
      - id / folio / numero (opcional)
      - fecha
      - cliente datos: cliente / cliente_rut / cliente_direccion / cliente_telefono / cliente_email / cliente_contacto
      - items: lista de dicts {codigo, descripcion, cantidad, precio, subtotal}
      - iva_percent (float, opcional; default 19)
      - neto / iva / total (opcionales, si no se entregan se calculan)
      - observaciones (opcional)
    """
    story: List = []

    # --- Encabezado: logo + empresa (izq) / caja rut-doc-folio-fecha (der)
    logo = _try_logo_img(company.get("logo_path", ""), 28, 28)
    if logo is None:
        # caja de logo vacÃ­a
        logo = Table([[Paragraph("LOGO", styles["small"])]],
                     colWidths=[28*mm], rowHeights=[28*mm])
        logo.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))

    emp_lines = [
        f"<b>{company['name']}</b>",
        company["giro"],
        company["direccion"],
        f"{company['comuna']} â€“ {company['ciudad']}",
        f"Tel: {company['telefono']}",
        company["email"],
    ]
    emp_block = Paragraph("<br/>".join(emp_lines), styles["small"])

    left = Table([[logo, emp_block]], colWidths=[30*mm, 70*mm])
    left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    rut = company.get("rut", "")
    folio = row.get("folio") or row.get("numero") or row.get("id") or "-"
    fecha = _fmt_date_ddmmyyyy(row.get("fecha"))
    right = Table([
        [Paragraph(f"R.U.T.: <b>{rut}</b>", styles["h_med"])],
        [Paragraph("<b>ORDEN DE VENTA</b>", styles["h_doc"])],
        [Paragraph(f"NÂº <b>{folio}</b>", styles["h_med"])],
        [Paragraph(f"Fecha EmisiÃ³n: <b>{fecha}</b>", styles["small"])],
    ], colWidths=[60*mm])
    right.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.8, colors.black),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    header = Table([[left, right]], colWidths=[100*mm, 70*mm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(header)
    story.append(Spacer(1, 6))

    # --- Bloque Cliente
    cli = {
        "razon": row.get("cliente") or row.get("cliente_razon") or "-",
        "rut": row.get("cliente_rut") or "-",
        "dir": row.get("cliente_direccion") or "-",
        "tel": row.get("cliente_telefono") or "-",
        "mail": row.get("cliente_email") or "-",
        "cont": row.get("cliente_contacto") or "-",
    }
    cliente_tbl = Table([
        [Paragraph("<b>SeÃ±or(es):</b>", styles["lbl"]), Paragraph(cli["razon"], styles["cell"]),
         Paragraph("<b>RUT:</b>", styles["lbl"]), Paragraph(cli["rut"], styles["cell"])],
        [Paragraph("<b>DirecciÃ³n:</b>", styles["lbl"]), Paragraph(cli["dir"], styles["cell"]),
         Paragraph("<b>TelÃ©fono:</b>", styles["lbl"]), Paragraph(cli["tel"], styles["cell"])],
        [Paragraph("<b>Contacto:</b>", styles["lbl"]), Paragraph(cli["cont"], styles["cell"]),
         Paragraph("<b>Email:</b>", styles["lbl"]), Paragraph(cli["mail"], styles["cell"])],
    ], colWidths=[22*mm, 78*mm, 18*mm, 52*mm])
    cliente_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.black),
        ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
        ("BACKGROUND", (2, 0), (2, -1), colors.whitesmoke),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(cliente_tbl)
    story.append(Spacer(1, 6))

    # --- Ãtems
    items: List[Dict[str, Any]] = list(row.get("items") or [])
    data = [["CÃ³digo", "DescripciÃ³n", "Cantidad", "Precio (CLP)", "Subtotal (CLP)"]]
    total_calc = 0.0
    for it in items:
        cod = it.get("codigo") or ""
        desc = it.get("descripcion") or ""
        cant = float(it.get("cantidad") or 0)
        precio = float(it.get("precio") or 0)
        subtotal = float(it.get("subtotal") or cant * precio)
        total_calc += subtotal
        data.append([
            Paragraph(str(cod), styles["cell"]),
            Paragraph(desc, styles["cell"]),
            Paragraph(_fmt_money2(cant), styles["cell"]),
            Paragraph(_fmt_money2(precio), styles["cell"]),
            Paragraph(_fmt_money2(subtotal), styles["cell"]),
        ])

    items_tbl = Table(data, colWidths=[25*mm, 80*mm, 22*mm, 28*mm, 28*mm], repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.black),
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("FONT", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (2, 1), (4, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 6))

    # --- Totales
    iva_percent = float(row.get("iva_percent", 19.0))
    total = float(row.get("total", total_calc))
    neto = float(row.get("neto", round(total / (1.0 + iva_percent / 100.0))))
    iva = float(row.get("iva", round(total - neto)))

    tot_tbl = Table([
        ["MONTO NETO $", _fmt_clp0(neto)],
        [f"IVA {int(iva_percent)} %  $", _fmt_clp0(iva)],
        ["TOTAL $", _fmt_clp0(total)],
    ], colWidths=[40*mm, 40*mm])
    tot_tbl.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
        ("INNERGRID", (0, 0), (-1, -1), 0.3, colors.black),
        ("BACKGROUND", (0, 2), (-1, 2), colors.whitesmoke),
        ("ALIGN", (0, 0), (0, -1), "RIGHT"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONT", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))

    # Observaciones (opcional)
    obs = (row.get("observaciones") or "").strip()
    if obs:
        obs_tbl = Table([[Paragraph("<b>Observaciones:</b>", styles["lbl"]),
                          Paragraph(obs, styles["small"])]],
                        colWidths=[28*mm, 112*mm])
        obs_tbl.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.3, colors.gray),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]))
        # totales a la derecha, observaciones a la izquierda
        bottom = Table([[obs_tbl, tot_tbl]], colWidths=[120*mm, 50*mm])
    else:
        bottom = Table([[Spacer(1, 1), tot_tbl]], colWidths=[120*mm, 50*mm])

    bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(bottom)

    story.append(Spacer(1, 6))
    # Pie de pÃ¡gina simple (opcional)
    story.append(Paragraph("* RecepciÃ³n sujeta a revisiÃ³n de calidad. Plazo de pago 30 dÃ­as salvo acuerdo.", styles["small"]))

    return story

# ---------------------------------------------------------------------
# API pÃºblica
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
    Genera PDF en Descargas. Si los `rows` traen `items`, se genera
    **una pÃ¡gina tipo â€œFactura ElectrÃ³nicaâ€ por venta**. Si no traen `items`,
    se produce un **resumen tabular**.

    Estructura esperada por venta (cuando se desea pÃ¡gina tipo factura):
    {
      "id": 101, "folio": "OV-20250901", "fecha": datetime,
      "cliente": "ACME SPA", "cliente_rut": "76.777.777-7",
      "cliente_direccion": "...", "cliente_telefono": "...",
      "cliente_email": "...", "cliente_contacto": "...",
      "items": [
         {"codigo": "SKU-100", "descripcion": "Producto X", "cantidad": 2, "precio": 15390, "subtotal": 30780},
         ...
      ],
      "iva_percent": 19.0,              # opcional (default 19)
      "neto": 30780, "iva": 5848, "total": 36628,  # opcionales (se calculan si faltan)
      "observaciones": "Entregar con guÃ­a."
    }
    """
    out_dir = _downloads_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"informe_ventas_{_dt.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    out_path = out_dir / fname

    # Documento
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=14*mm, rightMargin=14*mm, topMargin=14*mm, bottomMargin=12*mm,
        title="Informe / Ã“rdenes de Venta",
    )
    styles = getSampleStyleSheet()
    # estilos extra
    styles.add(ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10))
    styles.add(ParagraphStyle("lbl", fontName="Helvetica-Bold", fontSize=8, leading=10))
    styles.add(ParagraphStyle("h_doc", fontName="Helvetica-Bold", fontSize=14, alignment=2))   # derecha
    styles.add(ParagraphStyle("h_med", fontName="Helvetica-Bold", fontSize=11))
    styles.add(ParagraphStyle("cell", fontName="Helvetica", fontSize=8, leading=10))

    story: List = []
    company = _read_company_cfg()

    rows_list = list(rows)
    any_items = any(bool(r.get("items")) for r in rows_list)

    if any_items:
        # Una pÃ¡gina por venta con layout factura
        for idx, r in enumerate(rows_list):
            story += _venta_page_story(r, styles, company)
            if idx < len(rows_list) - 1:
                story.append(PageBreak())
    else:
        # --------- Resumen tabular (fallback como el original) ---------
        title = Paragraph("Informe de Ventas", styles["Title"])
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
        headers = ["ID", "Fecha", "Cliente", "Estado", "Total (CLP)"]
        data = [headers]
        total_general = 0.0

        def _key(r):
            f = r.get("fecha")
            return f if hasattr(f, "timestamp") else str(f)

        rows_sorted = sorted(rows_list, key=_key)
        for r in rows_sorted:
            fid = r.get("id", "")
            ffecha = _fmt_date_ddmmyyyy(r.get("fecha"))
            fcli = r.get("cliente", "") or ""
            fest = r.get("estado", "") or ""
            ftotal = float(r.get("total", 0.0))
            total_general += ftotal
            data.append([str(fid), ffecha, fcli, fest, _fmt_money2(ftotal)])

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
        story.append(Paragraph(f"Total general: <b>CLP {_fmt_clp0(total_general)}</b>", styles["Heading3"]))

    # Render
    doc.build(story)

    if auto_open:
        try:
            webbrowser.open(str(out_path))
        except Exception:
            pass

    return out_path


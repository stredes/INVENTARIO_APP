# -*- coding: utf-8 -*-
from __future__ import annotations
from pathlib import Path
from typing import Optional, List
import webbrowser

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepInFrame
from reportlab.pdfbase import pdfmetrics
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from sqlalchemy.orm import Session

from src.data.database import get_session
from src.data.models import Product
from src.utils.image_store import get_latest_image_paths
import configparser
from datetime import datetime


def _downloads_dir() -> Path:
    home = Path.home()
    for cand in ("Downloads", "Descargas", "downloads", "DESCARGAS"):
        p = home / cand
        if p.exists():
            return p
    return home


def _price_without_vat(price_with_vat: float, iva: float = 0.19) -> float:
    try:
        return round(float(price_with_vat) / (1.0 + float(iva)), 0)
    except Exception:
        return float(price_with_vat or 0)


def _read_company_cfg() -> dict:
    """Lee datos de empresa desde config/settings.ini [company].
    Acepta claves: name, rut, address, phone, email, logo.
    Mantiene compatibilidad con company.ini si existe.
    """
    data = {
        "name": "Tu Empresa Spa",
        "rut": "76.123.456-7",
        "address": "Calle Falsa 123",
        "phone": "+56 9 1234 5678",
        "email": "ventas@tuempresa.cl",
        "logo": "",
    }
    # Preferir settings.ini
    ini = Path("config/settings.ini")
    if ini.exists():
        cfg = configparser.ConfigParser()
        cfg.read(ini, encoding="utf-8")
        if cfg.has_section("company"):
            sec = cfg["company"]
            data["name"] = sec.get("name", data["name"]) or data["name"]
            data["rut"] = sec.get("rut", data["rut"]) or data["rut"]
            data["address"] = sec.get("address", data["address"]) or data["address"]
            data["phone"] = sec.get("phone", data["phone"]) or data["phone"]
            data["email"] = sec.get("email", data["email"]) or data["email"]
            data["logo"] = sec.get("logo", data["logo"]) or data["logo"]
            return data
    # Compatibilidad: company.ini
    legacy = Path("config/company.ini")
    if legacy.exists():
        cfg = configparser.ConfigParser()
        cfg.read(legacy, encoding="utf-8")
        sec = cfg["company"] if "company" in cfg else cfg["DEFAULT"]
        data["name"] = sec.get("name", data["name"]) or data["name"]
        data["rut"] = sec.get("rut", data["rut"]) or data["rut"]
        data["address"] = sec.get("direccion", data["address"]) or data["address"]
        data["phone"] = sec.get("telefono", data["phone"]) or data["phone"]
        data["email"] = sec.get("email", data["email"]) or data["email"]
        data["logo"] = sec.get("logo_path", data["logo"]) or data["logo"]
    return data


def generate_products_catalog(
    session: Optional[Session] = None,
    *,
    out_path: Optional[Path] = None,
    iva: float = 0.19,
    copies: int = 1,
    title: str = "CatÃ¡logo de Productos",
    cols: int = 3,
    rows: int = 4,
    show_company: bool = True,
    show_sku: bool = True,
    show_stock: bool = True,
    show_price_net: bool = True,
    show_price_gross: bool = False,
    auto_open: bool = True,
) -> Path:
    """
    Genera un catÃ¡logo PDF de todos los productos con:
      - Imagen (si existe, usando thumbnail),
      - Nombre + SKU,
      - Stock actual,
      - Precio de venta sin IVA.

    Layout: tarjetas en grilla (3 columnas x 4 filas) por pÃ¡gina.
    """
    session = session or get_session()
    products: List[Product] = session.query(Product).order_by(Product.nombre.asc()).all()

    out_path = out_path or (_downloads_dir() / "catalogo_productos.pdf")
    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=14 * mm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="tiny", fontSize=7, leading=9))
    styles.add(ParagraphStyle(name="card_title", fontSize=9, leading=11, spaceAfter=2, alignment=0, wordWrap="CJK"))
    styles.add(ParagraphStyle(name="hdr", fontSize=12, leading=14))
    styles.add(ParagraphStyle(name="hdr_b", fontSize=16, leading=18, alignment=1))

    W, H = A4
    col_w = (W - doc.leftMargin - doc.rightMargin) / cols
    row_h = (H - doc.topMargin - doc.bottomMargin) / rows

    story = []

    # Encabezado de empresa
    if show_company:
        comp = _read_company_cfg()
        left = []
        logo_path = comp.get("logo") or ""
        if logo_path and Path(logo_path).exists():
            try:
                logo = Image(str(logo_path))
                logo._restrictSize(28*mm, 28*mm)
                left = [logo]
            except Exception:
                left = [Paragraph("LOGO", styles["tiny"])]
        else:
            left = [Paragraph("LOGO", styles["tiny"])]
        emp_lines = [
            f"<b>{comp['name']}</b>",
            comp.get("address", ""),
            comp.get("phone", ""),
            comp.get("email", ""),
        ]
        emp_block = Paragraph("<br/>".join(emp_lines), styles["tiny"])
        hdr = Table([[left[0], emp_block, Paragraph(title, styles["hdr_b"]) ]], colWidths=[30*mm, 80*mm, 60*mm])
        hdr.setStyle(TableStyle([
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("ALIGN", (2,0), (2,0), "CENTER"),
        ]))
        story.append(hdr)
        story.append(Spacer(1, 6))
    cards: List[List] = []
    row_buf: List = []
    def _wrap_title(text: str, max_width: float, max_lines: int = 2, *, font_name: str = "Helvetica-Bold", font_size: int = 9) -> str:
        """Ajusta el nombre del producto al ancho y limita lineas, agregando '...' si es necesario."""
        if not text:
            return ""
        words = (text.replace("\n", " ").strip()).split()
        lines_acc = []
        line = ""
        i = 0
        while i < len(words):
            w = words[i]
            cand = (line + (" " if line else "") + w).strip()
            if pdfmetrics.stringWidth(cand, font_name, font_size) <= max_width:
                line = cand
                i += 1
            else:
                if line:
                    lines_acc.append(line)
                    line = ""
                else:
                    cut = w
                    while cut and pdfmetrics.stringWidth(cut, font_name, font_size) > max_width:
                        cut = cut[:-1]
                    if cut:
                        lines_acc.append(cut)
                        rest = w[len(cut):]
                        if rest:
                            words[i] = rest
                            continue
                        i += 1
                    else:
                        i += 1
                if len(lines_acc) >= max_lines:
                    break
        if len(lines_acc) < max_lines and line:
            lines_acc.append(line)
        if i < len(words):
            last = lines_acc[-1] if lines_acc else ""
            ell = "..."
            while last and pdfmetrics.stringWidth(last + ell, font_name, font_size) > max_width:
                last = last[:-1]
            if lines_acc:
                lines_acc[-1] = (last + ell) if last else ell
            else:
                lines_acc = [ell]
        return "<br/>".join(lines_acc)

    for p in products:
        img_path, thumb_path = get_latest_image_paths(int(p.id))
        # Imagen contenida en un contenedor fijo (aspect-ratio friendly)
        img_box_w = col_w - 8 * mm
        img_box_h = row_h * 0.5
        img_cell: Table
        use_path: Optional[Path] = None
        if thumb_path and thumb_path.exists():
            use_path = thumb_path
        elif img_path and img_path.exists():
            use_path = img_path
        if use_path is not None:
            try:
                im = Image(str(use_path))
                # Escalar manteniendo proporciÃ³n sin exceder el box
                iw, ih = float(getattr(im, 'imageWidth', 1)), float(getattr(im, 'imageHeight', 1))
                r = min(img_box_w / max(iw, 1.0), img_box_h / max(ih, 1.0), 1.0)
                im.drawWidth = iw * r
                im.drawHeight = ih * r
                img_cell = Table([[im]], colWidths=[img_box_w], rowHeights=[img_box_h])
            except Exception:
                img_cell = Table([[Paragraph("Sin imagen", styles["tiny"])]], colWidths=[img_box_w], rowHeights=[img_box_h])
        else:
            img_cell = Table([[Paragraph("Sin imagen", styles["tiny"])]], colWidths=[img_box_w], rowHeights=[img_box_h])
        img_cell.setStyle(TableStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("BOX", (0,0), (-1,-1), 0.3, colors.lightgrey),
        ]))

        raw_title = (p.nombre or '').strip()
        title = f"<b>{_wrap_title(raw_title, col_w - 8*mm, 2)}</b>"
        sku = (p.sku or "").strip()
        sku_txt = f"SKU: {sku}" if sku else ""
        stock = int(getattr(p, "stock_actual", 0) or 0)
        price_raw = float(getattr(p, "precio_venta", 0.0) or 0.0)
        price_net = _price_without_vat(price_raw, iva)

        lines = [Paragraph(title, styles["card_title"])]
        if show_sku and sku:
            lines.append(Paragraph(sku_txt, styles["tiny"]))
        if show_stock:
            lines.append(Paragraph(f"Stock: <b>{stock}</b>", styles["tiny"]))
        if show_price_net:
            lines.append(Paragraph(f"Precio (sin IVA): <b>{int(price_net):,}</b>".replace(",", "."), styles["tiny"]))
        if show_price_gross:
            lines.append(Paragraph(f"Precio (con IVA): <b>{int(price_raw):,}</b>".replace(",", "."), styles["tiny"]))

        text_block = KeepInFrame(col_w-8*mm, row_h*0.4, content=lines, mode='truncate', mergeSpace=True)
        card_tbl = Table([
            [img_cell],
            [text_block]
        ], colWidths=[col_w-8*mm], rowHeights=[row_h*0.6, row_h*0.4])
        card_tbl.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), 0.3, colors.black),
            ("TOPPADDING", (0,0), (-1,-1), 3),
            ("LEFTPADDING", (0,0), (-1,-1), 3),
            ("RIGHTPADDING", (0,0), (-1,-1), 3),
        ]))

        row_buf.append(card_tbl)
        if len(row_buf) == cols:
            cards.append(row_buf)
            row_buf = []
        if len(cards) == rows:
            story.append(Table(cards, colWidths=[col_w]*cols, rowHeights=[row_h]*rows, hAlign='CENTER'))
            story.append(Spacer(1, 6))
            cards = []

    if row_buf:
        while len(row_buf) < cols:
            row_buf.append(Spacer(1, row_h))
        cards.append(row_buf)
    if cards:
        story.append(Table(cards, colWidths=[col_w]*cols, rowHeights=[row_h]*len(cards), hAlign='CENTER'))

    # Repetir pÃ¡ginas segÃºn 'copies'
    if copies and copies > 1:
        story = story * int(copies)

    def _footer(canvas, _doc):
        pg = canvas.getPageNumber()
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(W - 15*mm, 10*mm, "Pagina {0} - ".format(pg) + __import__("datetime").datetime.now().strftime("%d/%m/%Y"))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    if auto_open:
        try:
            webbrowser.open(str(out_path))
        except Exception:
            pass
    return out_path







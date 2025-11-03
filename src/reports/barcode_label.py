from __future__ import annotations
"""
Generador simple de códigos de barras para preview/etiquetas.

Intenta usar:
- python-barcode (+ Pillow) si está instalado → PNG estándar.
- Fallback con Pillow (rayas simples, no estándar) → solo preview.
- Último recurso: PNG con texto plano.

También genera un PDF de etiqueta con ReportLab si está disponible.
"""

from pathlib import Path
from typing import Optional, Literal
import tempfile
import webbrowser

Symbology = Literal["code128", "ean13"]


def _write_text_png(text: str) -> Path:
    """Genera un PNG básico con solo el texto (fallback final)."""
    try:
        from PIL import Image, ImageDraw  # type: ignore
        img = Image.new("RGB", (380, 80), "white")
        d = ImageDraw.Draw(img)
        d.text((10, 30), text, fill="black")
        out = Path(tempfile.gettempdir()) / f"barcode_txt_{abs(hash(text))}.png"
        img.save(out)
        return out
    except Exception:
        # Si incluso PIL falta, crea un archivo vacío para no romper
        out = Path(tempfile.gettempdir()) / f"barcode_txt_{abs(hash(text))}.png"
        try:
            out.write_bytes(b"")
        except Exception:
            pass
        return out


def _fallback_stripes_png(code: str, width_mm: float, height_mm: float) -> Path:
    """Crea un PNG simple de 'rayas' en base a los bytes del código (solo visual)."""
    try:
        from PIL import Image, ImageDraw  # type: ignore
        width_px = max(260, int(width_mm * 8))
        height_px = max(90, int(height_mm * 4))
        img = Image.new("RGB", (width_px, height_px), "white")
        draw = ImageDraw.Draw(img)
        x = 12
        bar_w = 2
        for b in code.encode("utf-8", "ignore"):
            for i in range(8):
                if (b >> (7 - i)) & 1:
                    draw.rectangle([x, 10, x + bar_w, height_px - 22], fill="black")
                x += bar_w
            x += bar_w
            if x > width_px - 12:
                break
        out = Path(tempfile.gettempdir()) / f"barcode_fb_{abs(hash((code, width_mm, height_mm)))}.png"
        img.save(out)
        return out
    except Exception:
        return _write_text_png(code)


def generate_barcode_png(
    code: str,
    *,
    text: Optional[str] = None,
    symbology: Symbology = "code128",
    width_mm: float = 50,
    height_mm: float = 15,
) -> Path:
    """
    Devuelve la ruta a un PNG de código de barras.
    - Prefiere python-barcode (si disponible).
    - Fallback a stripes con Pillow.
    - Fallback final: PNG con texto.
    """
    # 1) python-barcode
    try:
        from barcode import get_barcode_class  # type: ignore
        from barcode.writer import ImageWriter  # type: ignore

        s = str(code)
        if symbology == "ean13":
            cls_name = "ean13"
            payload = s[:12] if len(s) >= 12 and s.isdigit() else ("0" * 12)
        else:
            cls_name = "code128"
            payload = s

        BC = get_barcode_class(cls_name)
        writer = ImageWriter()
        options = {
            "module_width": 0.22,
            # px/mm ≈ 72/25.4
            "module_height": max(8.0, float(height_mm)),
            "font_size": 9,
            "text_distance": 1.0,
            "write_text": True,
            "quiet_zone": 1.5,
        }
        out = Path(tempfile.gettempdir()) / f"barcode_{abs(hash((code, symbology, width_mm, height_mm)))}.png"
        BC(payload, writer=writer).write(out.open("wb"), options=options)
        return out
    except Exception:
        pass

    # 2) Fallback con Pillow: rayas (no estándar)
    try:
        return _fallback_stripes_png(code, width_mm, height_mm)
    except Exception:
        pass

    # 3) Solo texto
    return _write_text_png(code)


def generate_label_pdf(
    code: str,
    *,
    text: Optional[str] = None,
    symbology: Symbology = "code128",
    label_w_mm: float = 50,
    label_h_mm: float = 30,
    copies: int = 1,
    out_path: Optional[Path] = None,
    auto_open: bool = True,
) -> Path:
    """Genera un PDF de etiqueta (una por página) usando el PNG generado."""
    try:
        from reportlab.pdfgen import canvas  # type: ignore
        from reportlab.lib.units import mm  # type: ignore
    except Exception:
        # Sin reportlab: devolver PNG como “resultado” (UX mínima)
        return generate_barcode_png(code, text=text, symbology=symbology, width_mm=label_w_mm - 10, height_mm=label_h_mm - 18)

    label_w = label_w_mm * mm
    label_h = label_h_mm * mm
    if out_path is None:
        out_path = Path(tempfile.gettempdir()) / f"label_{abs(hash((code, text, symbology, label_w_mm, label_h_mm)))}.pdf"

    c = canvas.Canvas(str(out_path), pagesize=(label_w, label_h))
    for _ in range(max(1, int(copies))):
        # Genera PNG ajustado y colócalo en el centro con márgenes
        tmp_png = generate_barcode_png(code, text=text, symbology=symbology, width_mm=label_w_mm - 10, height_mm=max(12, label_h_mm - 18))
        try:
            c.drawImage(str(tmp_png), 5 * mm, 8 * mm, width=label_w - 10 * mm, height=label_h - 18 * mm, preserveAspectRatio=True, mask='auto')
        except Exception:
            # últimos recursos: escribir texto
            c.setFont("Helvetica", 10)
            c.drawCentredString(label_w / 2, label_h / 2, code)
        if text:
            c.setFont("Helvetica", 8)
            c.drawCentredString(label_w / 2, 3 * mm, str(text))
        c.showPage()
    c.save()

    if auto_open:
        try:
            webbrowser.open(str(out_path))
        except Exception:
            pass
    return out_path

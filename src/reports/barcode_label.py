from __future__ import annotations
from pathlib import Path
from typing import Optional, Literal
import tempfile
import webbrowser

from reportlab.graphics.shapes import Drawing
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.graphics.barcode import createBarcodeDrawing

Symbology = Literal["code128", "ean13"]


def _barcode_drawing(code: str, *, symbology: Symbology = "code128", width_mm: float = 40, height_mm: float = 15) -> Drawing:
    target_w = max(10.0, width_mm) * mm
    target_h = max(8.0, height_mm) * mm
    name = "EAN13" if symbology == "ean13" else "Code128"
    # Create drawing with human readable text
    drawing = createBarcodeDrawing(name, value=code, barHeight=target_h, humanReadable=True)
    # Scale to requested width, keeping aspect ratio
    try:
        scale = target_w / float(getattr(drawing, "width", 1) or 1)
        drawing.scale(scale, scale)
    except Exception:
        pass
    return drawing


def generate_barcode_png(code: str, *, text: Optional[str] = None, symbology: Symbology = "code128", width_mm: float = 40, height_mm: float = 15) -> Path:
    """
    Generate PNG for barcode. If code is numeric with 12/13 digits -> EAN13; else Code128.
    Uses python-barcode (Pillow). Falls back to Pillow simple render if missing.
    """
    tmp = Path(tempfile.gettempdir()) / f"barcode_{abs(hash((code, 'auto', width_mm, height_mm)))}.png"
    # Try python-barcode first
    try:
        from barcode import get_barcode_class  # type: ignore
        from barcode.writer import ImageWriter  # type: ignore
        s = str(code)
        use_ean13 = (s.isdigit() and (len(s) in (12, 13)))
        if use_ean13:
            cls_name = "ean13"
            payload = s[:12]  # library computes check digit
        else:
            cls_name = "code128"
            payload = s
        BC = get_barcode_class(cls_name)
        writer = ImageWriter()
        options = {
            "module_height": max(8.0, float(height_mm)) * (72.0 / 25.4),
            "font_size": 10,
            "text_distance": 1,
            "write_text": True,
            "quiet_zone": 3.0,
        }
        BC(payload, writer=writer).write(tmp.open("wb"), options=options)
        return tmp
    except Exception:
        pass
    # Fallback rough image with Pillow (not standards compliant, for preview only)
    try:
        from PIL import Image, ImageDraw  # type: ignore
        width_px = max(220, int(width_mm * 8))
        height_px = max(80, int(height_mm * 4))
        img = Image.new("RGB", (width_px, height_px), "white")
        draw = ImageDraw.Draw(img)
        x = 10
        bar_w = 2
        for b in str(code).encode("utf-8", "ignore"):
            for i in range(8):
                if (b >> (7 - i)) & 1:
                    draw.rectangle([x, 10, x + bar_w, height_px - 20], fill="black")
                x += bar_w
            x += bar_w
            if x > width_px - 10:
                break
        img.save(tmp)
        return tmp
    except Exception:
        pass
    # Last resort: draw text only
    try:
        from PIL import Image, ImageDraw  # type: ignore
        img = Image.new("RGB", (300, 80), "white")
        d = ImageDraw.Draw(img)
        d.text((10, 30), str(code), fill="black")
        img.save(tmp)
        return tmp
    except Exception:
        raise RuntimeError("Failed to generate barcode image.")

def generate_label_pdf(code: str, *, text: Optional[str] = None, symbology: Symbology = "code128",
                        label_w_mm: float = 50, label_h_mm: float = 30, copies: int = 1,
                        out_path: Optional[Path] = None, auto_open: bool = True) -> Path:
    # small label; place multiple copies on pages if needed (1 per page for simplicity)
    label_w = label_w_mm * mm
    label_h = label_h_mm * mm
    if out_path is None:
        out_path = Path(tempfile.gettempdir()) / f"label_{abs(hash((code, text, symbology)))}.pdf"

    c = canvas.Canvas(str(out_path), pagesize=(label_w, label_h))
    for i in range(max(1, int(copies))):
        # render barcode into PDF by converting to bitmap
        tmp_png = generate_barcode_png(code, symbology=symbology, width_mm=label_w_mm - 10, height_mm=max(12, label_h_mm - 18))
        # center
        x = (label_w - (label_w - 10 * mm)) / 2
        y = (label_h - (label_h - 18 * mm)) / 2
        c.drawImage(str(tmp_png), 5 * mm, 8 * mm, width=label_w - 10 * mm, height=label_h - 18 * mm, preserveAspectRatio=True, mask='auto')
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


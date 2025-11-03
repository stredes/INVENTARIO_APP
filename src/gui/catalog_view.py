from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from sqlalchemy.orm import Session
from PIL import Image, ImageDraw, ImageFont, ImageTk  # type: ignore
import configparser
from pathlib import Path

from src.data.database import get_session
from src.reports.catalog_generator import generate_products_catalog


class CatalogView(ttk.Frame):
    """Vista para generar el catálogo de productos en PDF (con preview)."""

    def __init__(self, master: tk.Misc, session: Optional[Session] = None):
        super().__init__(master, padding=10)
        self.session: Session = session or get_session()

        ttk.Label(self, text="Generador de Catálogo de Productos", font=("", 12, "bold")).pack(anchor="w")

        actions = ttk.LabelFrame(self, text="Acciones de catálogo", padding=8)
        actions.pack(fill="x", pady=(6, 8))

        ttk.Label(actions, text="Copias:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.var_copies = tk.IntVar(value=1)
        ttk.Spinbox(actions, from_=1, to=50, textvariable=self.var_copies, width=5).grid(row=0, column=1, sticky="w")

        ttk.Label(actions, text="IVA % (para neto):").grid(row=0, column=2, sticky="e", padx=8)
        self.var_iva = tk.DoubleVar(value=19.0)
        ttk.Spinbox(actions, from_=0, to=100, increment=0.5, textvariable=self.var_iva, width=6).grid(row=0, column=3, sticky="w")

        ttk.Label(actions, text="Diseño:").grid(row=0, column=4, sticky="e", padx=8)
        self.var_layout = tk.StringVar(value="3 x 4")
        ttk.Combobox(actions, textvariable=self.var_layout, values=["3 x 4", "2 x 3", "4 x 5"], state="readonly", width=8).grid(row=0, column=5, sticky="w")

        ttk.Label(actions, text="Título:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.var_title = tk.StringVar(value="Catálogo de Productos")
        ttk.Entry(actions, textvariable=self.var_title, width=36).grid(row=1, column=1, columnspan=3, sticky="we")

        # Filtro por familia (opcional)
        ttk.Label(actions, text="Familia:").grid(row=1, column=4, sticky="e", padx=8)
        self.var_family = tk.StringVar(value="(todas)")
        self.cmb_family = ttk.Combobox(actions, textvariable=self.var_family, values=["(todas)"], width=18)
        self.cmb_family.grid(row=1, column=5, sticky="w")
        try:
            from src.data.models import Product
            fams = sorted(set(((getattr(p, "familia", "") or "").strip() for p in self.session.query(Product).all() if (getattr(p, "familia", None) or "").strip())))
            if fams:
                self.cmb_family["values"] = ["(todas)"] + list(fams)
        except Exception:
            pass

        # Toggles de contenido
        self.var_show_company = tk.BooleanVar(value=True)
        self.var_show_sku = tk.BooleanVar(value=True)
        self.var_show_stock = tk.BooleanVar(value=True)
        self.var_show_net = tk.BooleanVar(value=True)
        self.var_show_gross = tk.BooleanVar(value=False)
        ttk.Checkbutton(actions, text="Mostrar empresa", variable=self.var_show_company).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(actions, text="SKU", variable=self.var_show_sku).grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(actions, text="Stock", variable=self.var_show_stock).grid(row=2, column=2, sticky="w")
        ttk.Checkbutton(actions, text="Precio sin IVA", variable=self.var_show_net).grid(row=2, column=3, sticky="w")
        ttk.Checkbutton(actions, text="Precio con IVA", variable=self.var_show_gross).grid(row=2, column=4, sticky="w")

        ttk.Button(actions, text="Vista previa", command=self._on_preview).grid(row=2, column=5, padx=(12, 4))
        ttk.Button(actions, text="Imprimir (PDF)", command=self._on_generate).grid(row=2, column=6, padx=4)

        # Área de vista previa con scroll
        host = ttk.Frame(self)
        host.pack(fill="both", expand=True)
        self.canvas = tk.Canvas(host, highlightthickness=0, bg="#f2f2f2")
        vsb = ttk.Scrollbar(host, orient="vertical", command=self.canvas.yview)
        hsb = ttk.Scrollbar(host, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="we")
        host.rowconfigure(0, weight=1)
        host.columnconfigure(0, weight=1)

        self.preview = ttk.Label(self.canvas)
        self._canvas_item = self.canvas.create_window(0, 0, anchor="nw", window=self.preview)
        self._preview_img = None
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Shift-MouseWheel>", self._on_shift_mousewheel)

    def _on_generate(self) -> None:
        try:
            cols, rows = self._layout()
            fam = (self.var_family.get() or "").strip()
            if fam and fam != "(todas)":
                os.environ["CATALOG_FAMILY"] = fam
            else:
                os.environ.pop("CATALOG_FAMILY", None)
            out = generate_products_catalog(
                self.session,
                auto_open=True,
                iva=float(self.var_iva.get() or 19.0),
                copies=max(1, int(self.var_copies.get() or 1)),
                title=self.var_title.get().strip() or "Catálogo de Productos",
                cols=cols, rows=rows,
                show_company=self.var_show_company.get(),
                show_sku=self.var_show_sku.get(),
                show_stock=self.var_show_stock.get(),
                show_price_net=self.var_show_net.get(),
                show_price_gross=self.var_show_gross.get(),
            )
            messagebox.showinfo("Catálogo", f"Catálogo generado:\n{out}")
        except Exception as e:
            messagebox.showerror("Catálogo", f"No se pudo generar el catálogo:\n{e}")

    def _on_preview(self) -> None:
        try:
            img = self._render_preview_image()
            self._preview_img = ImageTk.PhotoImage(img)
            self.preview.configure(image=self._preview_img)
            self.canvas.itemconfigure(self._canvas_item, width=img.width, height=img.height)
            self.canvas.configure(scrollregion=(0, 0, img.width, img.height))
        except Exception as e:
            messagebox.showerror("Vista previa", f"No se pudo generar la preview:\n{e}")

    def _render_preview_image(self) -> Image.Image:
        from src.data.models import Product
        from src.utils.image_store import get_latest_image_paths

        W, H = 900, 1200
        bg = (250, 250, 250)
        im = Image.new("RGB", (W, H), bg)
        draw = ImageDraw.Draw(im)
        cols, rows = self._layout()
        margin = 16
        col_w = (W - margin * 2) // cols
        row_h = (H - margin * 2) // rows

        iva = float(self.var_iva.get() or 19.0) / 100.0
        fam = (self.var_family.get() or "").strip()
        q = self.session.query(Product)
        if fam and fam != "(todas)":
            try:
                from sqlalchemy import func as _f
                q = q.filter((_f.lower(Product.familia) == fam.lower()) | (_f.lower(Product.familia).like(f"%{fam.lower()}%")))
            except Exception:
                q = q.filter(Product.familia == fam)
        prods = q.order_by(Product.nombre.asc()).limit(cols * rows).all()

        try:
            font_t = ImageFont.truetype("arial.ttf", 16)
            font_s = ImageFont.truetype("arial.ttf", 12)
        except Exception:
            font_t = ImageFont.load_default()
            font_s = ImageFont.load_default()

        if self.var_show_company.get():
            comp = self._read_company_cfg()
            title = self.var_title.get().strip() or "Catálogo de Productos"
            draw.text((margin, 4), f"{comp.get('name', '')}", fill=(0, 0, 0), font=font_t)
            draw.text((W//2 - 120, 4), title, fill=(0, 0, 0), font=font_t)

        def _wrap(text: str, *, font: ImageFont.ImageFont, max_w: int, max_lines: int = 2) -> list[str]:
            if not text:
                return []
            tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
            def _w(s: str) -> int:
                try:
                    return int(tmp.textlength(s, font=font))
                except Exception:
                    try:
                        box = font.getbbox(s)
                        return int((box[2] - box[0]) if box else 0)
                    except Exception:
                        return len(s) * max(1, font.size // 2)
            words = (text or "").replace("\n", " ").strip().split()
            lines: list[str] = []
            line = ""
            i = 0
            while i < len(words):
                cand = (line + (" " if line else "") + words[i]).strip()
                if _w(cand) <= max_w:
                    line = cand; i += 1
                else:
                    if line:
                        lines.append(line); line = ""
                    else:
                        cut = words[i]
                        while cut and _w(cut) > max_w:
                            cut = cut[:-1]
                        if cut:
                            lines.append(cut)
                            rest = words[i][len(cut):]
                            if rest:
                                words[i] = rest; continue
                            i += 1
                        else:
                            i += 1
                    if len(lines) >= max_lines:
                        break
            if len(lines) < max_lines and line:
                lines.append(line)
            if i < len(words) and lines:
                last, ell = lines[-1], "..."
                while last and _w(last + ell) > max_w:
                    last = last[:-1]
                lines[-1] = (last + ell) if last else ell
            return lines

        for idx, p in enumerate(prods):
            r = idx // cols
            c = idx % cols
            x0 = margin + c * col_w
            y0 = margin + r * row_h + (30 if self.var_show_company.get() else 0)
            x1 = x0 + col_w - 8
            y1 = y0 + row_h - 8
            draw.rectangle([x0, y0, x1, y1], outline=(180, 180, 180), width=1)

            from src.utils.image_store import get_latest_image_paths as _glp
            main_img, thumb = _glp(int(p.id))
            use = thumb if (thumb and thumb.exists()) else main_img
            box_w = col_w - 24
            box_h = int(row_h * 0.5) - 24
            draw.rectangle([x0 + 12, y0 + 12, x0 + 12 + box_w, y0 + 12 + box_h], outline=(200, 200, 200), width=1)
            if use and use.exists():
                try:
                    im_p = Image.open(use).convert("RGB")
                    iw, ih = im_p.size
                    rsc = min(box_w / max(iw, 1), box_h / max(ih, 1))
                    new_w, new_h = int(iw * rsc), int(ih * rsc)
                    im_p = im_p.resize((new_w, new_h))
                    px = x0 + 12 + (box_w - new_w) // 2
                    py = y0 + 12 + (box_h - new_h) // 2
                    im.paste(im_p, (px, py))
                except Exception:
                    pass
            else:
                draw.text((x0 + 20, y0 + 20), "Sin imagen", fill=(90, 90, 90), font=font_s)

            name = (p.nombre or "").strip()
            sku = (p.sku or "").strip()
            stock = int(getattr(p, "stock_actual", 0) or 0)
            price = float(getattr(p, "precio_venta", 0.0) or 0.0)
            neto = int(round(price / (1.0 + iva), 0)) if price > 0 else 0
            tx = x0 + 12
            ty = y0 + int(row_h * 0.55)
            for ln in _wrap(name, font=font_t, max_w=col_w - 24, max_lines=2):
                draw.text((tx, ty), ln, fill=(0, 0, 0), font=font_t)
                ty += 18
            if self.var_show_sku.get() and sku:
                draw.text((tx, ty), f"SKU: {sku}", fill=(20, 20, 20), font=font_s); ty += 18
            if self.var_show_stock.get():
                draw.text((tx, ty), f"Stock: {stock}", fill=(20, 20, 20), font=font_s); ty += 18
            if self.var_show_net.get():
                draw.text((tx, ty), f"Precio (sin IVA): {format(neto,',').replace(',', '.')}", fill=(0, 0, 0), font=font_s); ty += 18
            if self.var_show_gross.get():
                draw.text((tx, ty), f"Precio (con IVA): {format(int(price),',').replace(',', '.')}", fill=(0, 0, 0), font=font_s)

        return im

    def _layout(self) -> tuple[int, int]:
        val = (self.var_layout.get() or "3 x 4").strip().lower()
        if "2 x 3" in val:
            return 2, 3
        if "4 x 5" in val:
            return 4, 5
        return 3, 4

    @staticmethod
    def _read_company_cfg() -> dict:
        data = {"name": "Tu Empresa Spa", "address": "Calle Falsa 123", "phone": "+56 9 1234 5678"}
        cfg_path = Path("config/settings.ini")
        if cfg_path.exists():
            cfg = configparser.ConfigParser(); cfg.read(cfg_path, encoding="utf-8")
            if cfg.has_section("company"):
                sec = cfg["company"]
                data["name"] = sec.get("name", data["name"]) or data["name"]
                data["address"] = sec.get("address", data["address"]) or data["address"]
                data["phone"] = sec.get("phone", data["phone"]) or data["phone"]
        else:
            legacy = Path("config/company.ini")
            if legacy.exists():
                cfg = configparser.ConfigParser(); cfg.read(legacy, encoding="utf-8")
                sec = cfg["company"] if "company" in cfg else cfg["DEFAULT"]
                data["name"] = sec.get("name", data["name"]) or data["name"]
                data["address"] = sec.get("direccion", data["address"]) or data["address"]
                data["phone"] = sec.get("telefono", data["phone"]) or data["phone"]
        return data

    # Scroll helpers
    def _on_mousewheel(self, event):
        try:
            delta = int(-1 * (event.delta / 120)); self.canvas.yview_scroll(delta, "units")
        except Exception:
            pass
        return "break"

    def _on_shift_mousewheel(self, event):
        try:
            delta = int(-1 * (event.delta / 120)); self.canvas.xview_scroll(delta, "units")
        except Exception:
            pass
        return "break"


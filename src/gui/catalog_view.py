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

        self._actions_frame = ttk.LabelFrame(self, text="Acciones de catálogo", padding=8)
        self._actions_frame.pack(fill="x", pady=(6, 8))

        ttk.Label(self._actions_frame, text="Copias:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.var_copies = tk.IntVar(value=1)
        ttk.Spinbox(self._actions_frame, from_=1, to=50, textvariable=self.var_copies, width=5).grid(row=0, column=1, sticky="w")

        ttk.Label(self._actions_frame, text="IVA % (para neto):").grid(row=0, column=2, sticky="e", padx=8)
        self.var_iva = tk.DoubleVar(value=19.0)
        ttk.Spinbox(self._actions_frame, from_=0, to=100, increment=0.5, textvariable=self.var_iva, width=6).grid(row=0, column=3, sticky="w")

        ttk.Label(self._actions_frame, text="Diseño:").grid(row=0, column=4, sticky="e", padx=8)
        self.var_layout = tk.StringVar(value="3 x 4")
        ttk.Combobox(self._actions_frame, textvariable=self.var_layout, values=["3 x 4", "2 x 3", "4 x 5"], state="readonly", width=8).grid(row=0, column=5, sticky="w")

        ttk.Label(self._actions_frame, text="Título:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        self.var_title = tk.StringVar(value="Catálogo de Productos")
        ttk.Entry(self._actions_frame, textvariable=self.var_title, width=36).grid(row=1, column=1, columnspan=3, sticky="we")

        ttk.Button(self._actions_frame, text="Admin. familias...", command=self._open_families_manager).grid(row=1, column=4, sticky="w", padx=(8,0))
        self.var_family_summary = tk.StringVar(value="Familias: todas")
        self.family_menu_button = ttk.Menubutton(self._actions_frame, textvariable=self.var_family_summary, direction="below")
        self.family_menu_button.grid(row=1, column=5, columnspan=2, sticky="we", padx=(6, 0))
        self._family_menu = tk.Menu(self.family_menu_button, tearoff=False)
        self.family_menu_button["menu"] = self._family_menu
        ttk.Button(self._actions_frame, text="Marcar todo", command=self._mark_all_families).grid(row=3, column=5, sticky="we", padx=(6,0), pady=(6,0))
        ttk.Button(self._actions_frame, text="Desmarcar todo", command=self._unmark_all_families).grid(row=3, column=6, sticky="we", padx=(6,0), pady=(6,0))
        self.family_vars: dict[str, tk.BooleanVar] = {}
        try:
            self._refresh_family_list()
        except Exception:
            pass

        # Toggles de contenido
        self.var_show_company = tk.BooleanVar(value=True)
        self.var_show_sku = tk.BooleanVar(value=True)
        self.var_show_stock = tk.BooleanVar(value=False)
        self.var_show_net = tk.BooleanVar(value=False)
        self.var_show_gross = tk.BooleanVar(value=True)
        ttk.Checkbutton(self._actions_frame, text="Mostrar empresa", variable=self.var_show_company).grid(row=2, column=0, sticky="w")
        ttk.Checkbutton(self._actions_frame, text="SKU", variable=self.var_show_sku).grid(row=2, column=1, sticky="w")
        ttk.Checkbutton(self._actions_frame, text="Precio sin IVA", variable=self.var_show_net).grid(row=2, column=2, sticky="w")
        ttk.Checkbutton(self._actions_frame, text="Precio con IVA", variable=self.var_show_gross).grid(row=2, column=3, sticky="w")

        ttk.Button(self._actions_frame, text="Vista previa", command=self._on_preview).grid(row=2, column=5, padx=(12, 4))
        ttk.Button(self._actions_frame, text="Imprimir (PDF)", command=self._on_generate).grid(row=2, column=6, padx=4)

        # Ãrea de vista previa con scroll
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
            families, include_no_family = self._selected_family_filter()
            os.environ.pop("CATALOG_FAMILY", None)
            out = generate_products_catalog(
                self.session,
                auto_open=True,
                iva=float(self.var_iva.get() or 19.0) / 100.0,
                copies=max(1, int(self.var_copies.get() or 1)),
                title=self.var_title.get().strip() or "Catálogo de Productos",
                cols=cols, rows=rows,
                show_company=self.var_show_company.get(),
                show_sku=self.var_show_sku.get(),
                show_stock=False,
                show_price_net=self.var_show_net.get(),
                show_price_gross=self.var_show_gross.get(),
                families=families,
                include_no_family=include_no_family,
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
        q = self.session.query(Product)
        families, include_no_family = self._selected_family_filter()
        if families is not None:
            from sqlalchemy import or_, func as _f
            selected_lower = [item.lower() for item in families]
            clauses = []
            if selected_lower:
                clauses.append(_f.lower(Product.familia).in_(selected_lower))
            if include_no_family:
                clauses.append((Product.familia.is_(None)) | (_f.trim(Product.familia) == ""))
            if clauses:
                q = q.filter(or_(*clauses))
            else:
                q = q.filter(Product.id == -1)
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
            img_ratio = 0.52 if rows >= 5 else 0.6
            box_w = col_w - 24
            box_h = int(row_h * img_ratio) - 24
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
            price = float(getattr(p, "precio_venta", 0.0) or 0.0)
            neto = int(round(price / (1.0 + iva), 0)) if price > 0 else 0
            # Text layout under the image area
            tx = x0 + 12
            line_h = 16 if rows >= 5 else 18
            ty = y0 + int(row_h * img_ratio) + 6
            max_text_h = row_h - int(row_h * img_ratio) - 10
            max_lines = max(1, int(max_text_h // line_h))

            # Compose lines: title (wrapped), optional sku/stock, and price(s)
            name_lines = _wrap(name, font=font_t, max_w=col_w - 24, max_lines=(1 if rows >= 5 else 2))
            content_lines = [(ln, font_t) for ln in name_lines]
            if self.var_show_sku.get() and sku:
                content_lines.append((f"SKU: {sku}", font_s))
            price_lines = []
            if self.var_show_net.get():
                price_lines.append((f"Precio (sin IVA): {format(neto,',').replace(',', '.')}", font_s))
            if self.var_show_gross.get():
                price_lines.append((f"Precio: {format(int(price),',').replace(',', '.')}", font_s))
            content_lines.extend(price_lines)
            # Ensure price lines are not dropped: trim head if needed
            if len(content_lines) > max_lines:
                keep_tail = min(len(price_lines), max_lines - 1) if price_lines else 0
                # number of lines to show from start segment
                head_allow = max_lines - keep_tail
                if head_allow < len(content_lines) - keep_tail:
                    # take first head_allow and last keep_tail
                    content_lines = content_lines[:head_allow] + content_lines[-keep_tail:]
                else:
                    content_lines = content_lines[:max_lines]
            # Draw
            for text, font in content_lines[:max_lines]:
                draw.text((tx, ty), text, fill=(0, 0, 0), font=font)
                ty += line_h

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

    # ---- Familias ----
    def _refresh_family_list(self) -> None:
        old_values = {name: var.get() for name, var in getattr(self, "family_vars", {}).items()}
        try:
            from src.data.models import Product, Family
            fams_tbl = [ (f.nombre or '').strip() for f in self.session.query(Family).order_by(Family.nombre.asc()).all() ]
        except Exception:
            fams_tbl = []
        has_no_family = False
        try:
            from src.data.models import Product
            from sqlalchemy import func as _f
            fams_prod = [ (s or '').strip() for (s,) in self.session.query(_f.distinct(Product.familia)).filter(Product.familia.isnot(None)).all() ]
            has_no_family = bool(
                self.session.query(Product.id)
                .filter((Product.familia.is_(None)) | (_f.trim(Product.familia) == ""))
                .first()
            )
        except Exception:
            fams_prod = []
        names = [x for x in sorted({*(x for x in fams_tbl if x), *(x for x in fams_prod if x)})]
        if has_no_family:
            names.append("(sin familia)")
        self._render_family_checks(names, old_values)

    def _render_family_checks(self, names: list[str], previous: dict[str, bool]) -> None:
        self._family_menu.delete(0, "end")
        self.family_vars = {}
        if not names:
            self.var_family_summary.set("Familias: todas")
            self._family_menu.add_command(label="Sin familias cargadas")
            return

        for name in names:
            var = tk.BooleanVar(value=previous.get(name, True))
            self.family_vars[name] = var
            self._family_menu.add_checkbutton(
                label=name,
                variable=var,
                command=self._update_family_summary,
            )
        self._update_family_summary()

    def _mark_all_families(self) -> None:
        for var in self.family_vars.values():
            var.set(True)
        self._update_family_summary()

    def _unmark_all_families(self) -> None:
        for var in self.family_vars.values():
            var.set(False)
        self._update_family_summary()

    def _update_family_summary(self) -> None:
        if not self.family_vars:
            self.var_family_summary.set("Familias: todas")
            return
        selected = [name for name, var in self.family_vars.items() if var.get()]
        total = len(self.family_vars)
        if len(selected) == total:
            text = "Familias: todas"
        elif not selected:
            text = "Familias: ninguna"
        elif len(selected) == 1:
            text = f"Familia: {selected[0]}"
        else:
            text = f"Familias: {len(selected)} seleccionadas"
        if len(text) > 32:
            text = text[:29].rstrip() + "..."
        self.var_family_summary.set(text)

    def _selected_family_filter(self) -> tuple[list[str] | None, bool]:
        if not self.family_vars:
            return None, True
        selected = [name for name, var in self.family_vars.items() if var.get()]
        if len(selected) == len(self.family_vars):
            return None, True
        include_no_family = "(sin familia)" in selected
        families = [name for name in selected if name != "(sin familia)"]
        return families, include_no_family

    def _open_families_manager(self) -> None:
        try:
            from src.gui.families_manager import FamiliesManager
        except Exception:
            messagebox.showerror("Familias", "No se pudo abrir el administrador de familias.")
            return
        dlg = FamiliesManager(self.session, parent=self)
        self.wait_window(dlg)
        try:
            self._refresh_family_list()
        except Exception:
            pass

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


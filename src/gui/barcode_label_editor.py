from __future__ import annotations
import tkinter as tk
from tkinter import ttk
from typing import Optional

from src.reports.barcode_label import generate_barcode_png, generate_label_pdf


class BarcodeLabelEditor(tk.Toplevel):
    def __init__(self, master, *, initial_code: str = "", initial_text: str = "", symbology: str = "code128"):
        super().__init__(master)
        self.title("Etiqueta de código de barras")
        self.resizable(False, False)
        self.grab_set()

        self.var_code = tk.StringVar(value=initial_code)
        self.var_text = tk.StringVar(value=initial_text)
        self.var_symb = tk.StringVar(value=symbology)
        self.var_copies = tk.IntVar(value=1)
        # Presets de tamaño (mm): pensados para mejor lectura en pistola
        self.SIZES = {
            "50 x 30 mm (retail)": (50, 30),
            "60 x 35 mm (alto)": (60, 35),
            "80 x 50 mm (grande)": (80, 50),
        }
        self.var_size = tk.StringVar(value="50 x 30 mm (retail)")

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(frm, text="Código:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        ent_code = ttk.Entry(frm, textvariable=self.var_code, width=32)
        ent_code.grid(row=0, column=1, sticky="w")

        ttk.Label(frm, text="Texto (opcional):").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        ttk.Entry(frm, textvariable=self.var_text, width=32).grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="Simbolo:").grid(row=2, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(frm, textvariable=self.var_symb, values=["code128", "ean13"], state="readonly", width=10)\
            .grid(row=2, column=1, sticky="w")

        ttk.Label(frm, text="Tamaño etiqueta:").grid(row=3, column=0, sticky="e", padx=4, pady=4)
        ttk.Combobox(frm, textvariable=self.var_size, values=list(self.SIZES.keys()), state="readonly", width=20)\
            .grid(row=3, column=1, sticky="w")

        ttk.Label(frm, text="Copias:").grid(row=4, column=0, sticky="e", padx=4, pady=4)
        ttk.Spinbox(frm, from_=1, to=999, textvariable=self.var_copies, width=6).grid(row=4, column=1, sticky="w")

        # Preview
        self.lbl_preview = ttk.Label(frm)
        self.lbl_preview.grid(row=5, column=0, columnspan=2, pady=(8, 4))

        btns = ttk.Frame(frm)
        btns.grid(row=6, column=0, columnspan=2, pady=(6, 0))
        ttk.Button(btns, text="Actualizar", command=self._refresh_preview).pack(side="left", padx=4)
        ttk.Button(btns, text="Imprimir", command=self._print).pack(side="left", padx=4)
        ttk.Button(btns, text="Cerrar", command=self.destroy).pack(side="left", padx=4)

        self._img = None
        self.after(100, self._refresh_preview)

    def _refresh_preview(self):
        try:
            code = self.var_code.get().strip()
            if not code:
                self.lbl_preview.configure(text="(Ingrese código)")
                return
            png = generate_barcode_png(code, text=self.var_text.get().strip() or None, symbology=self.var_symb.get())
            try:
                import PIL.Image, PIL.ImageTk  # type: ignore
                im = PIL.Image.open(png)
                im = im.resize((int(im.width*0.8), int(im.height*0.8))) if im.width > 400 else im
                self._img = PIL.ImageTk.PhotoImage(im)
                self.lbl_preview.configure(image=self._img)
            except Exception:
                # Fallback simple: muestra ruta
                self.lbl_preview.configure(text=str(png))
        except Exception as e:
            self.lbl_preview.configure(text=f"Error: {e}")

    def _print(self):
        code = self.var_code.get().strip()
        if not code:
            return
        w_mm, h_mm = self.SIZES.get(self.var_size.get(), (50, 30))
        generate_label_pdf(
            code,
            text=self.var_text.get().strip() or None,
            symbology=self.var_symb.get(),
            label_w_mm=w_mm,
            label_h_mm=h_mm,
            copies=max(1, int(self.var_copies.get() or 1)),
            auto_open=True,
        )

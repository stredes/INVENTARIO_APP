# src/gui/widgets/product_image_box.py
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable
from pathlib import Path
from PIL import Image, ImageTk

from src.utils.image_store import save_image_for_product, get_latest_image_paths

class ProductImageBox(ttk.Frame):
    """Recuadro para imagen de producto (cargar/ver/quitar)."""

    def __init__(self, master: tk.Misc, width: int = 220, height: int = 220, **kw):
        super().__init__(master, padding=6, **kw)
        self.configure(borderwidth=1, relief="groove")
        self._pid: Optional[int] = None
        self._on_changed: Optional[Callable[[Optional[Path]], None]] = None
        self._w, self._h = width, height
        self._imgtk: Optional[ImageTk.PhotoImage] = None

        self.canvas = tk.Canvas(self, width=width, height=height, bg="#f4f4f4", highlightthickness=0)
        self.canvas.grid(row=0, column=0, columnspan=3, pady=(0,6))
        ttk.Button(self, text="Cargar…", command=self._load).grid(row=1, column=0, sticky="ew", padx=2)
        ttk.Button(self, text="Ver", command=self._open).grid(row=1, column=1, sticky="ew", padx=2)
        ttk.Button(self, text="Quitar", command=self._clear).grid(row=1, column=2, sticky="ew", padx=2)
        for i in range(3): self.columnconfigure(i, weight=1)
        self._draw_empty()

    def set_product(self, product_id: Optional[int], on_image_changed: Optional[Callable[[Optional[Path]], None]] = None):
        self._pid = product_id
        self._on_changed = on_image_changed
        self.refresh()

    def refresh(self):
        if not self._pid:
            self._draw_empty(); return
        main, thumb = get_latest_image_paths(self._pid)
        img = thumb or main
        if img: self._draw(img)
        else: self._draw_empty()

    # --- acciones ---
    def _load(self):
        if not self._pid:
            messagebox.showwarning("Imagen", "Guarda el producto antes de subir una imagen.")
            return
        path = filedialog.askopenfilename(
            title="Seleccionar imagen",
            filetypes=[("Imágenes", "*.png;*.jpg;*.jpeg;*.webp;*.bmp"), ("Todos", "*.*")]
        )
        if not path: return
        try:
            main, thumb = save_image_for_product(self._pid, Path(path))
            if self._on_changed: self._on_changed(main)
            self._draw(thumb or main)
        except Exception as e:
            messagebox.showerror("Imagen", f"No se pudo guardar la imagen:\n{e}")

    def _open(self):
        if not self._pid: return
        main, _ = get_latest_image_paths(self._pid)
        if main: 
            import webbrowser
            try: webbrowser.open(main.as_uri())
            except Exception: webbrowser.open(str(main))

    def _clear(self):
        # Solo limpia el preview (no borra archivos); tu callback decide si limpia DB
        self._draw_empty()
        if self._on_changed: self._on_changed(None)

    # --- dibujo ---
    def _draw_empty(self):
        self.canvas.delete("all")
        self.canvas.create_text(self._w//2, self._h//2, text="Sin imagen", fill="#888")

    def _draw(self, path: Path):
        try:
            im = Image.open(path).convert("RGB")
            im.thumbnail((self._w, self._h))
            self._imgtk = ImageTk.PhotoImage(im)
            self.canvas.delete("all")
            self.canvas.create_image(self._w//2, self._h//2, image=self._imgtk)
        except Exception:
            self._draw_empty()

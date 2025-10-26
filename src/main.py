from __future__ import annotations
import tkinter as tk
from tkinter import ttk, Menu  # ← añadimos Menu

from src.data.database import init_db, dispose_engine
from src.gui.main_window import MainWindow
from src.gui.theme_manager import ThemeManager  # ← import del gestor de temas


def on_close(root: tk.Tk):
    """Cierre ordenado: liberar engine SQLAlchemy antes de salir."""
    try:
        dispose_engine()
    finally:
        root.destroy()


def _setup_windows_dpi_awareness() -> None:
    """Mejora visual en Windows con monitores múltiples/HiDPI.
    Intenta activar 'Per-Monitor DPI Awareness' para evitar que la UI
    se vea comprimida al mover la ventana entre pantallas con distinto
    escalado (125%, 150%, etc.).
    """
    try:  # Windows 8.1+
        import ctypes  # noqa: WPS433
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PMv2
    except Exception:
        try:  # Fallback Vista+
            import ctypes  # noqa: WPS433
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _apply_tk_scaling(root: tk.Tk) -> None:
    """Ajusta el 'tk scaling' según los DPI efectivos del monitor actual.
    Esto reduce problemas de "colapso"/corte al mover la app entre
    monitores con diferente escala.
    """
    try:
        px_per_in = root.winfo_fpixels('1i')  # pixels por pulgada
        scaling = max(0.8, min(3.0, px_per_in / 72.0))  # 72 pt = 1 in
        root.tk.call('tk', 'scaling', scaling)
    except Exception:
        pass


def main():
    # Inicializa DB (aplica schema.sql si está configurado; crea tablas ORM)
    init_db()

    # Tk App
    _setup_windows_dpi_awareness()
    root = tk.Tk()
    root.title("Inventario App - Tkinter")
    root.geometry("1100x720")
    _apply_tk_scaling(root)

    # Menú principal de la ventana
    menubar = Menu(root)
    root.config(menu=menubar)

    # Tema: adjunta el gestor y construye el menú "Tema"
    ThemeManager.attach(root)          # aplica el tema guardado (por defecto "Light")
    ThemeManager.build_menu(menubar)   # añade el submenú "Tema" al menubar

    # Ventana principal (Notebook con pestañas)
    app = MainWindow(root)
    app.pack(fill="both", expand=True)

    # Recalcula scaling al cambiar de monitor/tamaño
    def _on_cfg(_evt=None):
        _apply_tk_scaling(root)
    root.bind('<Configure>', _on_cfg, add='+')

    # Cierre ordenado
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))
    root.mainloop()


if __name__ == "__main__":
    main()

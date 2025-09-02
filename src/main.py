from __future__ import annotations
import tkinter as tk
from tkinter import ttk

from src.data.database import init_db, dispose_engine
from src.gui.main_window import MainWindow


def on_close(root: tk.Tk):
    """Cierre ordenado: liberar engine SQLAlchemy antes de salir."""
    try:
        dispose_engine()
    finally:
        root.destroy()


def main():
    # Inicializa DB (aplica schema.sql si está configurado; crea tablas ORM)
    init_db()

    # Tk App
    root = tk.Tk()
    root.title("Inventario App - Tkinter")
    root.geometry("1100x720")

    # Estilo ttk básico
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass

    app = MainWindow(root)
    app.pack(fill="both", expand=True)

    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))
    root.mainloop()


if __name__ == "__main__":
    main()

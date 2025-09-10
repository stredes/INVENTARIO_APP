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


def main():
    # Inicializa DB (aplica schema.sql si está configurado; crea tablas ORM)
    init_db()

    # Tk App
    root = tk.Tk()
    root.title("Inventario App - Tkinter")
    root.geometry("1100x720")

    # Menú principal de la ventana
    menubar = Menu(root)
    root.config(menu=menubar)

    # Tema: adjunta el gestor y construye el menú "Tema"
    ThemeManager.attach(root)          # aplica el tema guardado (por defecto "Light")
    ThemeManager.build_menu(menubar)   # añade el submenú "Tema" al menubar

    # Ventana principal (Notebook con pestañas)
    app = MainWindow(root)
    app.pack(fill="both", expand=True)

    # Cierre ordenado
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))
    root.mainloop()


if __name__ == "__main__":
    main()

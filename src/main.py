from __future__ import annotations

import sys
import tkinter as tk
from tkinter import Menu

from src.app_meta import get_app_meta
from src.data.database import dispose_engine, init_db
from src.gui.main_window import MainWindow
from src.gui.theme_manager import ThemeManager
from src.utils.github_updater import check_for_updates_async


def on_close(root: tk.Tk) -> None:
    """Cierre ordenado: liberar engine SQLAlchemy antes de salir."""
    try:
        dispose_engine()
    finally:
        root.destroy()


def _setup_windows_dpi_awareness() -> None:
    """Mejora visual en Windows con monitores múltiples/HiDPI."""
    try:
        import ctypes  # noqa: WPS433

        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            import ctypes  # noqa: WPS433

            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def _apply_tk_scaling(root: tk.Tk) -> None:
    """Auto-ajusta el escalado en función de la pantalla actual."""
    try:
        ThemeManager.apply_auto_scaling()
        return
    except Exception:
        pass
    try:
        px_per_in = root.winfo_fpixels("1i")
        scaling = max(0.8, min(3.0, px_per_in / 72.0))
        root.tk.call("tk", "scaling", scaling)
    except Exception:
        pass


def _configure_window_for_screen(root: tk.Tk) -> None:
    """Ajusta tamaño inicial y mínimos según la pantalla actual."""
    try:
        root.update_idletasks()
        screen_w = max(root.winfo_screenwidth(), 1024)
        screen_h = max(root.winfo_screenheight(), 768)

        width = min(max(int(screen_w * 0.90), 980), screen_w)
        height = min(max(int(screen_h * 0.88), 700), screen_h)
        min_w = min(max(int(screen_w * 0.64), 900), width)
        min_h = min(max(int(screen_h * 0.62), 620), height)

        root.minsize(min_w, min_h)
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        root.geometry(f"{width}x{height}+{x}+{y}")

        if sys.platform.startswith("win") and screen_w >= 1800 and screen_h >= 980:
            try:
                root.state("zoomed")
            except Exception:
                pass
    except Exception:
        root.geometry("1100x720")


def main() -> None:
    meta = get_app_meta()
    init_db()

    _setup_windows_dpi_awareness()
    root = tk.Tk()
    root.title(f"{meta.app_name} {meta.version}")
    _configure_window_for_screen(root)

    menubar = Menu(root)
    root.config(menu=menubar)

    ThemeManager.attach(root)
    ThemeManager.build_menu(menubar)
    _apply_tk_scaling(root)

    app = MainWindow(root)
    app.pack(fill="both", expand=True)

    def _on_cfg(_evt=None) -> None:
        _apply_tk_scaling(root)

    root.bind("<Configure>", _on_cfg, add="+")
    root.protocol("WM_DELETE_WINDOW", lambda: on_close(root))
    try:
        root.after(
            1200,
            lambda: check_for_updates_async(
                root,
                on_update_ready=app.set_update_release,
                auto_apply=False,
            ),
        )
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    main()

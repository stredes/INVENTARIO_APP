from __future__ import annotations
"""
Utilidades de impresoras:

- Listado de impresoras instaladas (Windows via win32print si está disponible).
- Lectura/escritura de impresoras predeterminadas en config/settings.ini -> [printers]
  - document_name: impresora para documentos (listados, informes)
  - label_name: impresora para etiquetas
- Envío de archivos a imprimir en Windows (PDF u otros) usando ShellExecute
  con las acciones 'print' (predeterminada) y 'printto' (dirigida a una impresora).

Nota sobre Bluetooth:
  Las impresoras bluetooth emparejadas y agregadas como impresoras de Windows
  aparecerán en el listado y funcionarán igual que las USB/red.
  Para dispositivos sin controlador de impresión instalado en Windows
  no se garantiza la impresión directa desde PDF.
"""

from pathlib import Path
from typing import List, Optional
import sys
import os

from src.utils.helpers import read_config, write_config

try:
    import win32print  # type: ignore
except Exception:  # pragma: no cover - entorno no Windows/pywin32
    win32print = None  # type: ignore

try:
    import win32api  # type: ignore
except Exception:  # pragma: no cover
    win32api = None  # type: ignore


# --------------------- Listado de impresoras --------------------- #
def list_windows_printers() -> List[str]:
    if sys.platform.startswith("win") and win32print is not None:
        try:
            return [p[2] for p in win32print.EnumPrinters(2)]
        except Exception:
            return []
    return []


# --------------------- Configuración predeterminadas --------------------- #
SECTION = "printers"


def get_document_printer() -> Optional[str]:
    cfg = read_config()
    return cfg.get(SECTION, "document_name", fallback=None)


def set_document_printer(name: Optional[str]) -> None:
    cfg = read_config()
    if SECTION not in cfg:
        cfg[SECTION] = {}
    if name:
        cfg[SECTION]["document_name"] = str(name)
    else:
        cfg[SECTION].pop("document_name", None)
    write_config(cfg)


def get_label_printer() -> Optional[str]:
    cfg = read_config()
    return cfg.get(SECTION, "label_name", fallback=None)


def set_label_printer(name: Optional[str]) -> None:
    cfg = read_config()
    if SECTION not in cfg:
        cfg[SECTION] = {}
    if name:
        cfg[SECTION]["label_name"] = str(name)
    else:
        cfg[SECTION].pop("label_name", None)
    write_config(cfg)


# --------------------- Impresión de archivos (Windows) --------------------- #
def print_file_windows(path: Path, printer_name: Optional[str] = None) -> None:
    """
    Solicita al sistema imprimir el archivo usando la aplicación asociada.

    - Si `printer_name` está definido e instalados pywin32 y asociación
      de "printto" para la extensión (p.ej., PDF), usa ShellExecute 'printto'.
    - En caso contrario, intenta 'print' (usará la impresora predeterminada
      de la aplicación asociada o del sistema).
    - Como último recurso, abre el archivo para que el usuario imprima manualmente.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(str(path))

    if not sys.platform.startswith("win"):
        # En otros SO abre el archivo; el flujo de impresión depende del visor
        _open_file_default(path)
        return

    # Intento con pywin32 -> 'printto' (dirigido a impresora)
    if printer_name and win32api is not None:
        try:
            # Algunos visores (p.ej., Adobe Reader / Sumatra) soportan 'printto'.
            win32api.ShellExecute(0, "printto", str(path), f'"{printer_name}"', str(path.parent), 0)
            return
        except Exception:
            pass

    # Intento genérico: 'print' (predeterminada)
    if win32api is not None:
        try:
            win32api.ShellExecute(0, "print", str(path), None, str(path.parent), 0)
            return
        except Exception:
            pass

    # Fallback: abrir el archivo para impresión manual
    _open_file_default(path)


def _open_file_default(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        os.system(f"open '{str(path)}'")
    else:
        os.system(f"xdg-open '{str(path)}'")


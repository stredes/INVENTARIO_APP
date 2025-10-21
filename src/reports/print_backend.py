from __future__ import annotations
import os, sys, subprocess
from pathlib import Path
from typing import Optional

def _find_soffice() -> Optional[Path]:
    r"""
    Devuelve la ruta a soffice.exe si la encuentra.
    En Windows prueba:
      - ENV LIBREOFFICE_PATH
      - C:\Program Files\LibreOffice\program\soffice.exe
      - C:\Program Files (x86)\LibreOffice\program\soffice.exe
    En otros SO devuelve 'soffice' (se usará vía PATH).
    """
    if sys.platform.startswith("win"):
        # 1) variable de entorno opcional
        p = os.getenv("LIBREOFFICE_PATH", "").strip('"').strip()
        if p:
            exe = Path(p)
            if exe.is_file():
                return exe

        # 2) rutas típicas
        candidates = [
            Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
            Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
        ]
        for c in candidates:
            if c.is_file():
                return c
        return None
    else:
        return Path("soffice")  # se espera en PATH

def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)

def _convert_to_pdf(soffice: Path, xlsx_path: Path) -> Path:
    """Convierte XLSX a PDF en el mismo directorio y devuelve la ruta del PDF."""
    outdir = xlsx_path.parent
    _run([str(soffice), "--headless", "--convert-to", "pdf", "--outdir", str(outdir), str(xlsx_path)])
    pdf = xlsx_path.with_suffix(".pdf")
    if not pdf.exists():
        # LibreOffice nombra a veces con .pdf (igual base)
        # si no existe, hacer un barrido simple
        for f in outdir.glob(f"{xlsx_path.stem}*.pdf"):
            return f
        raise RuntimeError("Conversión a PDF falló (no se encontró el archivo).")
    return pdf

def _open_file_default(path: Path) -> None:
    """Abre el archivo con la app predeterminada del SO (para impresión manual)."""
    if sys.platform.startswith("win"):
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        _run(["open", str(path)])
    else:
        _run(["xdg-open", str(path)])

def print_xlsx(xlsx_path: Path, printer_name: str | None = None) -> None:
    """
    Imprime un .xlsx:
      - Windows: Excel/COM (pywin32). Fallback a LibreOffice (soffice).
      - Linux/macOS: LibreOffice (soffice) headless.
    Si no hay backend de impresión, exporta a PDF y lo abre.
    Usa EXCELCIOR_PRINTER si no se especifica printer_name.
    """
    printer = printer_name or os.getenv("EXCELCIOR_PRINTER", "")

    # 1) Windows: Excel COM
    if sys.platform.startswith("win"):
        try:
            import win32com.client  # pywin32
            excel = win32com.client.DispatchEx("Excel.Application")
            excel.Visible = False
            wb = excel.Workbooks.Open(str(xlsx_path))
            try:
                if printer:
                    excel.ActivePrinter = printer
                wb.PrintOut()  # imprime
            finally:
                wb.Close(SaveChanges=False)
                excel.Quit()
            return
        except Exception:
            # Continúa a LibreOffice
            pass

    # 2) LibreOffice
    soffice = _find_soffice()
    if soffice is not None or not sys.platform.startswith("win"):
        soffice = soffice or Path("soffice")  # no-Windows: desde PATH
        try:
            args = [str(soffice), "--headless", "--pt", printer or "", str(xlsx_path)]
            _run(args)
            return
        except FileNotFoundError:
            # sin soffice → intentamos PDF si Windows; si no, re-raise
            if not sys.platform.startswith("win"):
                raise RuntimeError("LibreOffice (soffice) no está instalado o no está en PATH")
        except Exception:
            # seguimos a fallback PDF
            pass

        # 3) Fallback: convertir a PDF y abrir
        try:
            pdf = _convert_to_pdf(soffice, xlsx_path)
            _open_file_default(pdf)
            raise RuntimeError(
                "No se pudo imprimir directamente. Se generó un PDF y se abrió para impresión manual:\n"
                f"{pdf}"
            )
        except Exception as e:
            raise RuntimeError(f"No se pudo imprimir con LibreOffice ni generar PDF: {e}")

    # 4) Sin Excel COM y sin LibreOffice detectado
    raise RuntimeError(
        "No hay backend de impresión disponible. Instala Microsoft Excel o LibreOffice.\n"
        "O define LIBREOFFICE_PATH con la ruta a soffice.exe."
    )

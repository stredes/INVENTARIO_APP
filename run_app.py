"""
Launcher de Inventario App desde la raíz del proyecto.
Ejecuta:  python run_app.py
"""
import sys
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from src.main import main  # noqa: E402
if __name__ == "__main__":
    main()

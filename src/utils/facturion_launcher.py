from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FACTURION_ROOT = PROJECT_ROOT / "facturion-main" / "facturion-main"
FACTURION_ENTRYPOINT = FACTURION_ROOT / "main.py"


def facturion_available() -> bool:
    return FACTURION_ENTRYPOINT.exists()


def get_facturion_entrypoint() -> Path:
    if not facturion_available():
        raise FileNotFoundError(
            f"No se encontró Facturion en: {FACTURION_ENTRYPOINT}"
        )
    return FACTURION_ENTRYPOINT


def launch_facturion() -> subprocess.Popen[bytes]:
    entrypoint = get_facturion_entrypoint()
    return subprocess.Popen(
        [sys.executable, str(entrypoint)],
        cwd=str(FACTURION_ROOT),
    )

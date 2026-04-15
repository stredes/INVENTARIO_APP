from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEV_FACTURION_ROOT = PROJECT_ROOT / "facturion-main" / "facturion-main"
DEV_FACTURION_ENTRYPOINT = DEV_FACTURION_ROOT / "main.py"
PACKAGED_FACTURION_EXE = Path(sys.executable).resolve().parent / "facturion" / "Facturion.exe"


def facturion_available() -> bool:
    if getattr(sys, "frozen", False):
        return PACKAGED_FACTURION_EXE.exists()
    return DEV_FACTURION_ENTRYPOINT.exists()


def get_facturion_target() -> Path:
    if not facturion_available():
        missing_path = PACKAGED_FACTURION_EXE if getattr(sys, "frozen", False) else DEV_FACTURION_ENTRYPOINT
        raise FileNotFoundError(f"No se encontró Facturion en: {missing_path}")
    return PACKAGED_FACTURION_EXE if getattr(sys, "frozen", False) else DEV_FACTURION_ENTRYPOINT


def launch_facturion() -> subprocess.Popen[bytes]:
    target = get_facturion_target()
    if getattr(sys, "frozen", False):
        return subprocess.Popen(
            [str(target)],
            cwd=str(target.parent),
        )
    return subprocess.Popen(
        [sys.executable, str(target)],
        cwd=str(DEV_FACTURION_ROOT),
    )

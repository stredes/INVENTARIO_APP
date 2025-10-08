"""
Fixtures de prueba:
- Crea una BD SQLite temporal en un directorio tmp.
- Reescribe config/settings.ini para apuntar a esa BD.
- Inicializa/limpia el engine entre tests.
"""

from __future__ import annotations
import os
from pathlib import Path
import shutil
import pytest

from src.data import database as db


@pytest.fixture(scope="session")
def tmp_project_dir(tmp_path_factory):
    # Carpeta temporal estilo proyecto
    p = tmp_path_factory.mktemp("inventario_app_tests")
    (p / "config").mkdir(exist_ok=True)
    return p


@pytest.fixture(autouse=True)
def isolated_db(tmp_project_dir, monkeypatch):
    """
    BD aislada por test:
    - Escribe un settings.ini apuntando a inventario_test.db en tmp.
    - Monkeypatch a database.CONFIG_PATH.
    - Reinicia engine/sesión antes y después.
    """
    cfg_path = tmp_project_dir / "config" / "settings.ini"
    dbfile = tmp_project_dir / "inventario_test.db"
    cfg_path.write_text(
        f"[database]\nurl = sqlite:///{dbfile.as_posix()}\n",
        encoding="utf-8",
    )

    # Apuntar el módulo database a este settings.ini
    monkeypatch.setattr(db, "CONFIG_PATH", cfg_path, raising=False)

    # Asegurar estado limpio
    db.dispose_engine()
    db.init_db(create_with_orm=True)

    yield

    # Limpieza
    db.dispose_engine()
    try:
        if dbfile.exists():
            dbfile.unlink()
    except Exception:
        pass


@pytest.fixture()
def session():
    """Entrega la sesión SQLAlchemy (scoped_session proxied)."""
    return db.get_session()

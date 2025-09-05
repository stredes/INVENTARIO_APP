"""
Gestión de la base de datos (SQLAlchemy):
- Crea engine + scoped_session.
- Activa PRAGMA foreign_keys en SQLite.
- init_db(): crea tablas con ORM o aplica schema.sql si se indica en config.
- MIGRACIÓN LIGERA: asegura columnas nuevas (p.ej. products.image_path).
"""

from __future__ import annotations
import configparser
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker

CONFIG_PATH = Path("config/settings.ini")

_engine: Optional[Engine] = None
SessionLocal: Optional[scoped_session] = None


def _read_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        cfg.read(CONFIG_PATH, encoding="utf-8")
    else:
        # Valor por defecto si no existe settings.ini
        cfg["database"] = {"url": "sqlite:///./src/data/inventory.db"}
    return cfg


def get_engine() -> Engine:
    """
    Crea (o retorna) un Engine global. Para SQLite, fuerza foreign_keys=ON
    y aplica migraciones ligeras (ALTER TABLE si faltan columnas conocidas).
    """
    global _engine
    if _engine is not None:
        return _engine

    cfg = _read_config()
    db_url = cfg.get("database", "url", fallback="sqlite:///./src/data/inventory.db")

    _engine = create_engine(db_url, future=True)

    # PRAGMA foreign_keys=ON para SQLite
    @event.listens_for(_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        try:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()
        except Exception:
            # Si no es SQLite o falla, ignoramos silenciosamente
            pass

    # MIGRACIÓN LIGERA (idempotente)
    _ensure_schema(_engine)

    return _engine


def get_session() -> scoped_session:
    """Retorna un scoped_session global para uso en repos/servicios."""
    global SessionLocal
    if SessionLocal is None:
        engine = get_engine()
        SessionLocal = scoped_session(
            sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        )
    return SessionLocal


def init_db(apply_schema_sql_path: Optional[str] = None, create_with_orm: bool = True) -> None:
    """
    Inicializa la base:
    - Si apply_schema_sql_path está definido (o en settings.ini: database.apply_schema_sql),
      aplica ese SQL (p.ej., schema.sql).
    - Si create_with_orm=True, hace Base.metadata.create_all() con los modelos ORM.
    """
    engine = get_engine()
    _ = get_session()  # asegura la sesión creada

    # Carga diferida para evitar import circular
    from .models import Base  # noqa: WPS433

    cfg = _read_config()
    if apply_schema_sql_path is None:
        apply_schema_sql_path = cfg.get("database", "apply_schema_sql", fallback=None)

    # 1) Aplicar schema.sql si se indicó
    if apply_schema_sql_path:
        sql_path = Path(apply_schema_sql_path)
        if not sql_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo SQL: {sql_path}")
        sql_text = sql_path.read_text(encoding="utf-8")
        # Ejecutamos dentro de una transacción
        with engine.begin() as conn:
            # Desactivar restricciones si lo necesitas (SQLite)
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF;")
            conn.execute(text(sql_text))
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")

    # 2) Crear tablas definidas en los modelos (no falla si ya existen)
    if create_with_orm:
        Base.metadata.create_all(bind=engine)

    # 3) Asegurar columnas nuevas (por si create_all no las puede añadir)
    _ensure_schema(engine)


def dispose_engine() -> None:
    """Cierra el engine y limpia el scoped_session (útil para tests)."""
    global _engine, SessionLocal
    if SessionLocal is not None:
        SessionLocal.remove()
        SessionLocal = None
    if _engine is not None:
        _engine.dispose()
        _engine = None


# =========================
# MIGRACIONES LIGERAS
# =========================
def _is_sqlite(engine: Engine) -> bool:
    try:
        return engine.url.get_backend_name() == "sqlite"
    except Exception:
        return False


def _table_has_column(engine: Engine, table: str, column: str) -> bool:
    """Devuelve True si la columna existe (solo SQLite; para otros motores devuelve True y no hace nada)."""
    if not _is_sqlite(engine):
        return True  # no gestionamos introspección aquí para otros motores
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f'PRAGMA table_info("{table}")').fetchall()
        cols = {r[1] for r in rows}  # (cid, name, type, notnull, dflt_value, pk)
        return column in cols


def _add_column_if_missing(engine: Engine, table: str, column: str, type_sql: str) -> None:
    """
    ALTER TABLE seguro en SQLite: agrega la columna si no existe.
    type_sql debe ser SQL nativo (ej: "TEXT", "INTEGER NOT NULL DEFAULT 0", etc.)
    """
    if not _is_sqlite(engine):
        return
    if _table_has_column(engine, table, column):
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {type_sql}')


def _ensure_schema(engine: Engine) -> None:
    """
    Aplica pequeñas migraciones idempotentes necesarias para la app.
    - products.image_path TEXT
    (agrega aquí otras columnas futuras si se requieren)
    """
    try:
        # products.image_path fue agregado al modelo; lo aseguramos en SQLite existentes
        _add_column_if_missing(engine, table="products", column="image_path", type_sql="TEXT")
    except Exception:
        # Evitar que un fallo de migración bloquee el arranque;
        # si necesitas depurar, eleva la excepción.
        pass

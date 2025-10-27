"""
Gestión de la base de datos (SQLAlchemy):
- Crea engine + scoped_session.
- Activa PRAGMA foreign_keys en SQLite.
- init_db(): crea tablas con ORM o aplica schema.sql si se indica en config.
- MIGRACIÓN LIGERA: asegura columnas nuevas (p.ej. products.image_path, products.id_proveedor).
"""

from __future__ import annotations
import configparser
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker
import os
import sys

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


def _resolve_portable_db_path(raw: str) -> Path:
    """
    Resuelve una ruta de archivo de base de datos (posiblemente relativa) para modo portable.
    - Expande variables de entorno y ~.
    - Si es relativa:
        * En ejecutable PyInstaller (sys.frozen): junto al .exe.
        * En desarrollo: relativa a la raíz del proyecto (dos niveles arriba de este archivo).
    - Crea la carpeta padre si falta.
    """
    p = Path(os.path.expandvars(os.path.expanduser(raw)))
    if not p.is_absolute():
        if getattr(sys, "frozen", False):  # running from .exe
            base = Path(sys.executable).resolve().parent
        else:
            base = Path(__file__).resolve().parents[2]
        p = base / p
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return p


def _safe_sqlite_url(db_url: str, cfg: configparser.ConfigParser) -> str:
    """
    Si es SQLite, garantiza que el directorio del archivo exista y que la ruta
    sea escribible en entornos empaquetados (PyInstaller).
    - Rutas absolutas: crea el directorio padre si falta.
    - Rutas relativas: coloca el archivo en %LOCALAPPDATA%/InventarioApp/<nombre>.
      (Evita fallos al ejecutar el .exe donde no existe ./src/data/).
    Precedencia para ruta de archivo:
    1) ENV INVENTARIO_DB_PATH (ruta al archivo .db)
    2) settings.ini [database] file o path (ruta al archivo .db)
    3) URL original (si es relativa): %LOCALAPPDATA%/InventarioApp/<nombre>
       (evita fallos en ejecución del .exe)
    """
    # 1) ENV explícito a archivo
    env_path = os.getenv("INVENTARIO_DB_PATH", "").strip()
    if env_path:
        file_path = _resolve_portable_db_path(env_path)
        return f"sqlite:///{file_path}"

    # 2) settings.ini con 'file' o 'path'
    for key in ("file", "path"):
        val = cfg.get("database", key, fallback="").strip()
        if val:
            file_path = _resolve_portable_db_path(val)
            return f"sqlite:///{file_path}"

    # 3) Derivado desde la URL existente
    prefix = "sqlite:///"
    if not db_url.startswith(prefix):
        return db_url
    raw_path = db_url[len(prefix):]
    path = Path(raw_path)
    if not path.is_absolute():
        # Carpeta de datos del usuario para fallback portable
        base = os.getenv("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        app_dir = Path(base) / "InventarioApp"
        fname = path.name if path.name else "inventory.db"
        path = app_dir / fname
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return f"sqlite:///{path}"


def get_engine() -> Engine:
    """
    Crea (o retorna) un Engine global. Para SQLite, fuerza foreign_keys=ON
    y aplica migraciones ligeras (ALTER TABLE si faltan columnas conocidas).
    """
    global _engine
    if _engine is not None:
        return _engine

    # 1) Prioridad a env var (multiusuario en servidor) y fallback a settings.ini/SQLite local
    env_url = os.getenv("DATABASE_URL", "").strip()
    if env_url:
        db_url = env_url
    else:
        cfg = _read_config()
        db_url = cfg.get("database", "url", fallback="sqlite:///./src/data/inventory.db")
    # Ajuste seguro para SQLite (considerando archivo en settings/env)
    cfg = _read_config()
    db_url = _safe_sqlite_url(db_url, cfg)

    # 2) Engine con pool razonable si es servidor (PostgreSQL)
    kw = {"future": True, "pool_pre_ping": True}
    try:
        if db_url.startswith("postgresql"):
            kw.update({"pool_size": 5, "max_overflow": 5})
    except Exception:
        pass
    _engine = create_engine(db_url, **kw)

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


def _table_exists(engine: Engine, table: str) -> bool:
    """True si la tabla existe (solo SQLite; para otros motores asumimos True)."""
    if not _is_sqlite(engine):
        return True
    with engine.connect() as conn:
        row = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
            (table,),
        ).fetchone()
        return bool(row)


def _table_has_column(engine: Engine, table: str, column: str) -> bool:
    """Devuelve True si la columna existe (solo SQLite; para otros motores devuelve True y no hace nada)."""
    if not _is_sqlite(engine):
        return True  # no gestionamos introspección aquí para otros motores
    if not _table_exists(engine, table):
        return False
    with engine.connect() as conn:
        rows = conn.exec_driver_sql(f'PRAGMA table_info("{table}")').fetchall()
        cols = {r[1] for r in rows}  # (cid, name, type, notnull, dflt_value, pk)
        return column in cols


def _add_column_if_missing(engine: Engine, table: str, column: str, type_sql: str) -> None:
    """
    ALTER TABLE seguro en SQLite: agrega la columna si no existe y la tabla existe.
    type_sql debe ser SQL nativo (ej: "TEXT", "INTEGER NOT NULL DEFAULT 0", etc.)
    NOTA: para columnas nuevas con FK, en SQLite se puede usar 'INTEGER REFERENCES x(y)'.
          Evita NOT NULL si ya hay datos; se recomienda validar NOT NULL desde la app
          o hacer un rebuild posterior.
    """
    if not _is_sqlite(engine):
        return
    if not _table_exists(engine, table):
        return
    if _table_has_column(engine, table, column):
        return
    with engine.begin() as conn:
        conn.exec_driver_sql(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {type_sql}')


def _create_index_if_missing(engine: Engine, index_sql: str, index_name: str) -> None:
    """
    Crea un índice si no existe (solo SQLite).
    index_sql: sentencia completa 'CREATE INDEX IF NOT EXISTS ...'
    index_name: nombre del índice para chequeo rápido.
    """
    if not _is_sqlite(engine):
        return
    with engine.connect() as conn:
        # Si el índice ya existe, no hacemos nada
        row = conn.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='index' AND name=?;",
            (index_name,),
        ).fetchone()
        if row:
            return
    with engine.begin() as conn:
        conn.exec_driver_sql(index_sql)


def _ensure_schema(engine: Engine) -> None:
    """
    Aplica pequeñas migraciones idempotentes necesarias para la app.
    - products.image_path TEXT
    - products.id_proveedor INTEGER REFERENCES suppliers(id)
      (queda NULL-permitido para no romper BD con datos previos; validar en capa de app)
    - products.barcode TEXT (y UNIQUE INDEX)
      - Índice en products(id_proveedor) para acelerar filtros por proveedor.
    """
    try:
        # Asegurar columna de imagen en productos
        _add_column_if_missing(engine, table="products", column="image_path", type_sql="TEXT")

        # Asegurar columna de proveedor en productos (FK suave)
        _add_column_if_missing(
            engine,
            table="products",
            column="id_proveedor",
            type_sql='INTEGER REFERENCES suppliers(id)'
        )

        # Índice para consultas por proveedor (opcional pero útil)
        _create_index_if_missing(
            engine,
            index_sql='CREATE INDEX IF NOT EXISTS idx_products_id_proveedor ON products(id_proveedor);',
            index_name='idx_products_id_proveedor',
        )

        # Asegurar columna de código de barras y UNIQUE INDEX (nullable)
        _add_column_if_missing(engine, table="products", column="barcode", type_sql="TEXT")
        _create_index_if_missing(
            engine,
            index_sql='CREATE UNIQUE INDEX IF NOT EXISTS uq_products_barcode ON products(barcode) WHERE barcode IS NOT NULL;',
            index_name='uq_products_barcode',
        )

    except Exception:
        # Evitar que un fallo de migración bloquee el arranque;
        # si necesitas depurar, eleva la excepción.
        pass

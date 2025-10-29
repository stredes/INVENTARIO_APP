"""
GestiÃ³n de la base de datos (SQLAlchemy):
- Crea engine + scoped_session.
- Activa PRAGMA foreign_keys en SQLite.
- init_db(): crea tablas con ORM o aplica schema.sql si se indica en config.
- MIGRACIÃ“N LIGERA: asegura columnas nuevas (p.ej. products.image_path, products.id_proveedor).
"""

from __future__ import annotations
import configparser
from pathlib import Path
import sys
from typing import Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import scoped_session, sessionmaker
import os

CONFIG_PATH = Path("config/settings.ini")

_engine: Optional[Engine] = None
SessionLocal: Optional[scoped_session] = None


def _frozen_dir() -> Path | None:
    try:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
    except Exception:
        pass
    return None


def _meipass_dir() -> Path | None:
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            return Path(base)
    except Exception:
        pass
    return None


def _read_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    # Prioridad de lectura:
    # 1) config/settings.ini junto al ejecutable (dist/..)
    # 2) config/settings.ini relativo al cwd (modo dev)
    # 3) config/settings.ini embebido (PyInstaller, _MEIPASS)
    # 4) valores por defecto
    tried = False
    try:
        exedir = _frozen_dir()
        if exedir is not None:
            p = exedir / CONFIG_PATH
            if p.exists():
                cfg.read(p, encoding="utf-8")
                tried = True
    except Exception:
        pass
    if not tried and CONFIG_PATH.exists():
        cfg.read(CONFIG_PATH, encoding="utf-8")
        tried = True
    if not tried:
        mdir = _meipass_dir()
        if mdir is not None:
            p = mdir / CONFIG_PATH
            if p.exists():
                cfg.read(p, encoding="utf-8")
                tried = True
    if not tried:
        # Valor por defecto si no existe settings.ini
        cfg["database"] = {"url": "sqlite:///app_data/inventario.db"}
    return cfg


def _safe_sqlite_url(db_url: str) -> str:
    """
    Si es SQLite, garantiza que el directorio del archivo exista y que la ruta
    sea escribible en entornos empaquetados (PyInstaller).

    - Rutas absolutas: crea el directorio padre si falta.
    - Rutas relativas: coloca el archivo en %LOCALAPPDATA%/InventarioApp/<nombre>.
      (Evita fallos al ejecutar el .exe donde no existe ./src/data/).
    """
    prefix = "sqlite:///"
    if not db_url.startswith(prefix):
        return db_url
    raw_path = db_url[len(prefix):]
    path = Path(raw_path)
    if not path.is_absolute():
        exedir = _frozen_dir()
        base = exedir if exedir is not None else Path.cwd()
        path = base / path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass
    try:
        resolved = Path(path).resolve()
    except Exception:
        resolved = path
    # Usar formato POSIX para evitar problemas de barras invertidas en URI
    return f"sqlite:///{resolved.as_posix()}"


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
        db_url = cfg.get("database", "url", fallback="sqlite:///app_data/inventario.db")
    db_url = _safe_sqlite_url(db_url)

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

    # MIGRACIÃ“N LIGERA (idempotente)
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
    - Si apply_schema_sql_path estÃ¡ definido (o en settings.ini: database.apply_schema_sql),
      aplica ese SQL (p.ej., schema.sql).
    - Si create_with_orm=True, hace Base.metadata.create_all() con los modelos ORM.
    """
    engine = get_engine()
    _ = get_session()  # asegura la sesiÃ³n creada

    # Carga diferida para evitar import circular
    from .models import Base  # noqa: WPS433

    cfg = _read_config()
    if apply_schema_sql_path is None:
        apply_schema_sql_path = cfg.get("database", "apply_schema_sql", fallback=None)

    # 1) Aplicar schema.sql si se indicÃ³
    if apply_schema_sql_path:
        sql_path = Path(apply_schema_sql_path)
        if not sql_path.exists():
            raise FileNotFoundError(f"No se encontrÃ³ el archivo SQL: {sql_path}")
        sql_text = sql_path.read_text(encoding="utf-8")
        # Ejecutamos dentro de una transacciÃ³n
        with engine.begin() as conn:
            # Desactivar restricciones si lo necesitas (SQLite)
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF;")
            conn.execute(text(sql_text))
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")

    # 2) Crear tablas definidas en los modelos (no falla si ya existen)
    if create_with_orm:
        Base.metadata.create_all(bind=engine)

    # 3) Asegurar columnas nuevas (por si create_all no las puede aÃ±adir)
    _ensure_schema(engine)


def dispose_engine() -> None:
    """Cierra el engine y limpia el scoped_session (Ãºtil para tests)."""
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
        return True  # no gestionamos introspecciÃ³n aquÃ­ para otros motores
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
    Crea un Ã­ndice si no existe (solo SQLite).
    index_sql: sentencia completa 'CREATE INDEX IF NOT EXISTS ...'
    index_name: nombre del Ã­ndice para chequeo rÃ¡pido.
    """
    if not _is_sqlite(engine):
        return
    with engine.connect() as conn:
        # Si el Ã­ndice ya existe, no hacemos nada
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
    Aplica pequeÃ±as migraciones idempotentes necesarias para la app.
    - products.image_path TEXT
    - products.id_proveedor INTEGER REFERENCES suppliers(id)
      (queda NULL-permitido para no romper BD con datos previos; validar en capa de app)
    - Ãndice en products(id_proveedor) para acelerar filtros por proveedor.
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

        # Asegurar columna de ubicaciÃ³n en productos (FK a locations)
        _add_column_if_missing(
            engine,
            table="products",
            column="id_ubicacion",
            type_sql='INTEGER REFERENCES locations(id)'
        )

        # Ãndice para consultas por proveedor (opcional pero Ãºtil)
        _create_index_if_missing(
            engine,
            index_sql='CREATE INDEX IF NOT EXISTS idx_products_id_proveedor ON products(id_proveedor);',
            index_name='idx_products_id_proveedor',
        )

        # Ãndice para ubicaciÃ³n (opcional)
        _create_index_if_missing(
            engine,
            index_sql='CREATE INDEX IF NOT EXISTS idx_products_id_ubicacion ON products(id_ubicacion);',
            index_name='idx_products_id_ubicacion',
        )

        # --------- Compras: campos adicionales opcionales ---------
        _add_column_if_missing(engine, table="purchases", column="numero_documento", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="fecha_documento", type_sql="DATETIME")
        _add_column_if_missing(engine, table="purchases", column="fecha_contable", type_sql="DATETIME")
        _add_column_if_missing(engine, table="purchases", column="fecha_vencimiento", type_sql="DATETIME")
        _add_column_if_missing(engine, table="purchases", column="moneda", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="tasa_cambio", type_sql="NUMERIC")
        _add_column_if_missing(engine, table="purchases", column="unidad_negocio", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="proporcionalidad", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="atencion", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="tipo_descuento", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="descuento", type_sql="NUMERIC")
        _add_column_if_missing(engine, table="purchases", column="ajuste_iva", type_sql="NUMERIC")
        _add_column_if_missing(engine, table="purchases", column="stock_policy", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="referencia", type_sql="TEXT")
        _add_column_if_missing(engine, table="purchases", column="ajuste_impuesto", type_sql="NUMERIC")

    except Exception:
        # Evitar que un fallo de migraciÃ³n bloquee el arranque;
        # si necesitas depurar, eleva la excepciÃ³n.
        pass



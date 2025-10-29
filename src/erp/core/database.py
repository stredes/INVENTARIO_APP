from __future__ import annotations

"""
Infra mínima de base de datos para documentos ERP (COT/OC/OV).

- Usa SQLite nativo (sin requerir SQLAlchemy) para ser auto‑contenible.
- Crea automáticamente las tablas si no existen.
- Entrega helpers para abrir conexión con `PRAGMA foreign_keys = ON`.

Este módulo es deliberadamente simple para integrarse fácil con Tkinter.
Si tu app ya usa SQLAlchemy, puedes reemplazar internamente estas funciones
por sesiones de ORM manteniendo la misma interfaz pública.
"""

from pathlib import Path
import sqlite3
from typing import Optional
import configparser


DEFAULT_DB_PATH = Path("app_data/erp.sqlite3")  # legacy default (no longer used by default)


def _config_erp_path() -> Optional[Path]:
    """Lee config/settings.ini:[erp] para resolver la ruta del ERP.

    Claves soportadas:
      - enabled = true/false (si es false -> usa memoria y no crea archivo)
      - path = ruta al archivo sqlite donde persistir
    Precedencia: env ERP_DB_PATH > ini path > memoria.
    """
    # ENV tiene prioridad
    import os
    env = os.getenv("ERP_DB_PATH", "").strip()
    if env:
        return Path(env)

    ini = Path("config/settings.ini")
    if ini.exists():
        cfg = configparser.ConfigParser()
        try:
            cfg.read(ini, encoding="utf-8")
            sec = cfg["erp"] if cfg.has_section("erp") else None
        except Exception:
            sec = None
        if sec is not None:
            enabled = sec.get("enabled", "true").strip().lower()
            if enabled in {"0", "false", "no"}:
                return None
            p = sec.get("path", "").strip()
            if p:
                return Path(p)
    # Si no hay configuración explícita, por defecto NO crear archivo
    return None


def get_connection(db_path: Optional[str | Path] = None) -> sqlite3.Connection:
    """Retorna una conexión SQLite con FK activas.

    Si `db_path` es None, y no hay config, usa una BD en memoria (no genera archivo).
    Para persistir en archivo, configure `ERP_DB_PATH` o [erp] path en config/settings.ini.
    """
    # Resolver ruta de destino
    path: Optional[Path]
    if db_path is not None:
        path = Path(db_path)
    else:
        path = _config_erp_path()

    if path is None:
        conn = sqlite3.connect(":memory:")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Crea las tablas necesarias si no existen.

    Tablas:
      - documentos (cabecera)
      - detalles (líneas)
      - log_auditoria (auditoría de acciones)
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,                         -- COT / OC / OV
            folio TEXT UNIQUE,
            fecha_emision TEXT,
            fecha_vencimiento TEXT,
            proveedor_cliente TEXT,                     -- nombre o FK externa
            rut_receptor TEXT,
            nombre_receptor TEXT,
            moneda TEXT DEFAULT 'CLP',
            estado TEXT DEFAULT 'pendiente',
            observaciones TEXT,
            referencia_id INTEGER,                      -- id de documento origen
            exento INTEGER DEFAULT 0,                   -- 1 = exento IVA
            tasa_iva REAL DEFAULT 0.19,
            monto_neto REAL DEFAULT 0,
            monto_iva REAL DEFAULT 0,
            monto_total REAL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS detalles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_documento INTEGER NOT NULL,
            codigo_item TEXT,
            descripcion TEXT,
            unidad TEXT,
            cantidad REAL DEFAULT 0,
            precio_unitario REAL DEFAULT 0,
            descuento_porcentaje REAL DEFAULT 0,
            subtotal REAL DEFAULT 0,
            subtotal_final REAL DEFAULT 0,
            FOREIGN KEY(id_documento) REFERENCES documentos(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS log_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            fecha_hora TEXT,
            accion TEXT,
            documento_afectado INTEGER,
            valores_previos TEXT,
            valores_nuevos TEXT
        );
        """
    )
    conn.commit()


__all__ = ["get_connection", "init_db", "DEFAULT_DB_PATH"]


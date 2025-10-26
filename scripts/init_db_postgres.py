from __future__ import annotations

"""
Inicializa la base en PostgreSQL leyendo DATABASE_URL.

Uso:
  - Defina la variable de entorno DATABASE_URL, por ejemplo:
      postgresql+psycopg2://usuario:clave@192.168.1.10:5432/inventario?sslmode=prefer
  - Ejecute:  python -m scripts.init_db_postgres

El script valida conexión y crea las tablas ORM necesarias.
"""

import os
import sys


def main() -> int:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        print("[ERROR] La variable de entorno DATABASE_URL no está definida.")
        print("Ejemplo: postgresql+psycopg2://usuario:clave@host:5432/inventario?sslmode=prefer")
        return 2

    try:
        from src.data.database import get_engine, init_db

        eng = get_engine()
        # Fuerza prueba de conexión
        with eng.connect() as conn:
            _ = conn.exec_driver_sql("SELECT 1").scalar_one()
        init_db()
        print("[OK] Conexión verificada y tablas creadas si faltaban.")
        return 0
    except Exception as e:  # pragma: no cover
        print(f"[ERROR] No se pudo inicializar la BD: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


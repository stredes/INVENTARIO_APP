# API Web (FastAPI)

API en FastAPI que reutiliza el ORM y lógica de negocio de la app de escritorio (SQLAlchemy, managers en `src/core/*`).

## Requisitos
- Python 3.11+
- Variables de entorno (opcional): `DATABASE_URL` para usar PostgreSQL. Si no, usa SQLite local (ver `src/data/database.py`).

## Levantar en local
```bash
python -m venv .venv
. .venv/Scripts/activate  # Windows PowerShell: .\\.venv\\Scripts\\Activate.ps1
pip install -r api/requirements.txt

# Ejecutar
uvicorn api.main:app --reload
# Abre http://127.0.0.1:8000/docs
```

## Endpoints iniciales
- Salud: `GET /health`
- Productos: `GET /products`, `POST /products`, `GET /products/{id}`, `PUT /products/{id}`, `DELETE /products/{id}`
- Proveedores: `GET /suppliers`, `POST /suppliers`, `GET /suppliers/{id}`, `PUT /suppliers/{id}`, `DELETE /suppliers/{id}`
- Clientes: `GET /customers`, `POST /customers`, `GET /customers/{id}`, `PUT /customers/{id}`, `DELETE /customers/{id}`
- Inventario: `POST /inventory/entries`, `POST /inventory/exits`
- Compras: `POST /purchases`
- Ventas: `POST /sales`

## Notas
- La sesión de DB se obtiene de `src.data.database.get_session()` y se cierra por request.
- Los managers (`src/core/*`) realizan `commit()` en operaciones de negocio.
- Para producción, usa PostgreSQL gestionado (Neon/Supabase) y define `DATABASE_URL`.


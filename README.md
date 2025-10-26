# 📦 Inventario App

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy-green.svg)](https://www.sqlalchemy.org/)
[![Tkinter](https://img.shields.io/badge/GUI-Tkinter-orange.svg)](https://docs.python.org/3/library/tkinter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Inventario App** es un sistema de escritorio para gestionar **productos**, **compras**, **ventas** e **inventario** con base de datos local **SQLite**. Mantiene el stock actualizado y permite generar documentos PDF (OC/OV/Cotización) directamente en la carpeta de **Descargas** del usuario.

---

## ✨ Características

- **Productos**: altas, búsqueda por ID/Nombre/SKU, precios de compra/venta, stock actual.
- **Proveedores** y **Clientes** con datos de contacto y RUT.
- **Compras**:
  - Carrito con múltiples ítems.
  - Confirmación con opción de **sumar stock**.
  - **Orden de Compra (PDF)** a *Descargas*.
  - **Cotización (PDF)** a *Descargas* **sin afectar stock**.
- **Ventas**:
  - Carrito con múltiples ítems.
  - **Orden de Venta (PDF)** a *Descargas*.
  - **Autocompletado** de productos (ID/Nombre/SKU) por aproximación.
  - **Informe de ventas** por **rango de fechas** (`dd/mm/aaaa`) con **filtros** por cliente, producto, estado y totales; **Exportar a CSV**.
- **Movimientos de Inventario** automáticos en compras/ventas confirmadas.
- **Seed de datos** para desarrollo (incluye compras **y ventas** con detalles).

> Probado en Python **3.11/3.12**.

---

## 🧱 Arquitectura por capas

- **GUI (Tkinter/ttk)**: `src/gui/*`
- **Core (lógica de negocio)**: `src/core/*`
- **Data (ORM/Repos/DB)**: `src/data/*`
- **Utils/Reports**: `src/utils/*`, `src/reports/*`
- **Config**: `src/config/settings.ini`

---

## 📂 Estructura del Proyecto

inventario_app/
├─ src/
│ ├─ main.py # Punto de entrada (o usa run_app.py si existe)
│ ├─ gui/ # Interfaces (Tkinter/ttk)
│ │ └─ widgets/
│ │ └─ autocomplete_combobox.py
│ ├─ core/ # Inventory/Sales/Purchase Manager
│ ├─ data/ # models.py, repository.py, database.py
│ ├─ reports/ # generadores PDF (OC/OV/Cotización/Informe)
│ └─ utils/ # helpers, image_store, paths, etc.
├─ scripts/
│ └─ seed_fake_data.py # Datos falsos: proveedores, clientes, productos, compras y ventas
├─ config/ # settings.ini
├─ docs/ # arquitectura, esquema DB
├─ tests/ # pytest
├─ requirements.txt
├─ README.md
└─ run_app.py # (opcional) alternativa de entrada

---

## 🚀 Puesta en marcha

### 1) Entorno virtual

```bash
python -m venv .venv

# Linux/macOS
source .venv/bin/activate

# Windows (PowerShell/CMD)
.\.venv\Scripts\activate
```

### 2) Dependencias

```bash
pip install -r requirements.txt
```

### 3) Base de datos (opcional con datos falsos)

```bash
python scripts/seed_fake_data.py
```
Crea proveedores, clientes, productos, compras y ventas con detalles.
Si no usas seed, la app crea la DB vacía al primer arranque.

### 4) Ejecutar

```bash
# Si tu entrada es src/main.py
python -m src.main

# Si usas run_app.py
python run_app.py
```

## 🌐 Modo multiusuario (PostgreSQL)

Para que varios empleados usen la app simultáneamente, configura un servidor PostgreSQL y define la URL en cada cliente.

1) Levanta PostgreSQL (por ejemplo con Docker Compose):

```
version: "3.9"
services:
  db:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: inventario
      POSTGRES_USER: inventario_app
      POSTGRES_PASSWORD: CambiaEstaClaveFuerte
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

2) En cada PC cliente, define `DATABASE_URL`:

- Windows (PowerShell):
```
setx DATABASE_URL "postgresql+psycopg2://inventario_app:CambiaEstaClaveFuerte@IP_SERVIDOR:5432/inventario?sslmode=prefer"
```

- Linux/macOS:
```
export DATABASE_URL='postgresql+psycopg2://inventario_app:CambiaEstaClaveFuerte@IP_SERVIDOR:5432/inventario?sslmode=prefer'
```

3) Instala el driver en cada cliente:
```
pip install psycopg2-binary
```

4) Inicializa la base (una sola vez):
```
python -m scripts.init_db_postgres
```

Si `DATABASE_URL` no está definida, la app usará SQLite local en `app_data/` como modo standalone.

🧭 Uso rápido por módulo
Compras
Selecciona Proveedor → agrega productos (cantidad; precio unitario con IVA calculado desde el precio de compra).

Confirmar compra: si “Sumar stock (Completada)” está activo, impacta inventario.

Generar OC (PDF) → Descargas.

Generar Cotización (PDF) → Descargas (no modifica stock).

Ventas
Selecciona Cliente.

Autocompletado de productos: escribe en la barra (ID/Nombre/SKU) y elige por aproximación.

Confirmar venta: si “Descontar stock (Confirmada)” está activo, impacta inventario.

Generar OV (PDF) → Descargas.

Informe de Ventas
Rango Desde/Hasta en dd/mm/aaaa.

Filtros: Cliente (autocomplete), Producto (autocomplete), Estado (Confirmada/Borrador/Cancelada), Total ≥ / ≤.

Generar Informe: tabla con ID, fecha, cliente, estado y total; muestra total general.

Exportar CSV: guarda el informe en Descargas.

⚙️ Configuración
Archivo: src/config/settings.ini

Parámetros típicos:

Ruta/nombre de DB SQLite.

Opciones de impresión/plantillas PDF.

Si empaquetas, incluye src/config/, src/reports/, src/gui/ y src/app_data/.

🧪 Tests
```bash
pytest -q
```
🗂️ Generadores de documentos (PDF)
Orden de Compra: src/utils/po_generator.py

Cotización: src/utils/quote_generator.py

Orden de Venta: src/utils/so_generator.py

(Opcional) Informe ventas PDF: src/reports/sales_report_pdf.py

Guardan en Descargas e intentan abrir el archivo (auto_open=True).

🧰 Empaquetado (Windows nativo)
PyInstaller (resumen):

```bat
REM Activar venv e instalar PyInstaller
pip install pyinstaller

REM Empaquetar (ajusta el entrypoint que uses)
pyinstaller run_app.py ^
  --name InventarioApp ^
  --noconsole ^
  --onefile ^
  --clean ^
  --hidden-import=sqlite3 ^
  --hidden-import=sqlalchemy.dialects.sqlite ^
  --add-data "src/config;src/config" ^
  --add-data "src/app_data;src/app_data" ^
  --add-data "src/reports;src/reports" ^
  --add-data "src/gui;src/gui"
```
El ejecutable queda en dist/InventarioApp.exe.

Si cargas recursos por rutas relativas, usa un helper tipo utils/paths.py que resuelva rutas en desarrollo y dentro del .exe (_MEIPASS).

❓ Problemas comunes
Autocomplete no filtra → verifica AutoCompleteCombobox.set_dataset(...) y que haya productos cargados.

Fecha inválida en informe → usa dd/mm/aaaa (ej.: 07/09/2025).

PDF no abre → revisa permisos del SO o desactiva auto_open.

Recursos ausentes en .exe → asegúrate de los --add-data y de resolver rutas correctamente.

📜 Licencia
Este proyecto está bajo la licencia MIT.

Desarrollado por Gian Lucas San Martín ✨



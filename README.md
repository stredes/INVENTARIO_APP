# 📦 Inventario App

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![SQLAlchemy](https://img.shields.io/badge/ORM-SQLAlchemy-green.svg)](https://www.sqlalchemy.org/)
[![Tkinter](https://img.shields.io/badge/GUI-Tkinter-orange.svg)](https://docs.python.org/3/library/tkinter.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Sistema de gestión de inventario de escritorio desarrollado en **Python**, con:

- **Tkinter (ttk)** para la interfaz gráfica.
- **SQLAlchemy** para la persistencia de datos.
- **SQLite** como base de datos local (portable).
- Arquitectura modular (GUI, Core, Data).

---

## ✨ Características

- Gestión de **Productos** (altas, listados, stock inicial).
- Gestión de **Proveedores**.
- Registro de **Compras** con múltiples ítems (impacto en stock opcional).
- Registro de **Movimientos de Inventario** (entradas y salidas manuales).
- Control de **stock actual** actualizado automáticamente.

---

## 📂 Estructura del Proyecto
inventario_app/
├── src/
│ ├── main.py # Punto de entrada (Tkinter)
│ ├── gui/ # Interfaces gráficas (Tkinter)
│ ├── core/ # Lógica de negocio
│ ├── data/ # Modelos y persistencia
│ └── utils/ # Helpers
├── tests/ # Tests (pytest)
├── config/ # Configuración (settings.ini)
├── docs/ # Documentación (arquitectura, DB)
├── requirements.txt
├── setup.py
└── README.md


---

Crear entorno virtual:

python -m venv .venv
source .venv/bin/activate   # Linux/macOS
.venv\Scripts\activate      # Windows


Instalar dependencias:

pip install -r requirements.txt

▶️ Ejecución

Inicia la aplicación con:

python -m src.main


La primera vez se creará automáticamente la base de datos inventory.db en src/data/.

🧪 Tests

Ejecutar los tests con pytest:

pytest -q

📸 Capturas (Ejemplo)

(Aquí puedes pegar screenshots de tus vistas de Tkinter: Productos, Proveedores, Compras, Inventario).

📜 Licencia

Este proyecto está bajo la licencia MIT
.
Desarrollado por Gian Lucas San Martin ✨
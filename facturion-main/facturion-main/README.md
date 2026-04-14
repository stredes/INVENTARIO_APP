# Facturion

Aplicación de escritorio en Python para llevar el control mensual de facturas, IVA acumulado, conciliación con SII y saldo tributario final.

## Funcionalidades

- Registro manual de facturas con cálculo automático de IVA y total final
- Acumulados mensuales de neto, IVA, TAG, contador y total facturado
- Conciliación mensual con IVA informado en SII
- Estado de saldo mensual: a favor, en contra o sin diferencia
- Dashboard inicial con métricas del mes actual
- CRUD completo de facturas
- Búsqueda por cliente, fecha o número de factura
- Filtros por mes y año
- Exportación a Excel y CSV
- Historial mensual y gráfico comparativo
- Configuración editable de porcentaje de IVA
- Respaldo local de base de datos SQLite

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Base de datos

La base SQLite se crea automáticamente en `data/facturion.db`.

Cuando la app se ejecuta instalada como `.exe`, la base se guarda en:

`%LOCALAPPDATA%\Facturion\data\facturion.db`

## Releases y autoactualización

- La app incluye botón `Actualizar app`
- El actualizador busca el último release en GitHub
- Descarga `Facturion-Setup.exe`
- Cierra la app actual
- Instala la nueva versión
- Reemplaza el acceso directo del escritorio

### Configuración del repositorio

Antes de usar la actualización automática, configura el repositorio GitHub en:

`utils/app_metadata.py`

Edita:

```python
GITHUB_REPOSITORY = "tu-usuario/tu-repo"
```

También puedes usar la variable de entorno:

```powershell
$env:FACTURION_GITHUB_REPOSITORY="tu-usuario/tu-repo"
```

### Generar release local

Necesitas:

- `PyInstaller`
- `Inno Setup 6`

Luego ejecuta:

```powershell
.\build_release.ps1
```

Eso genera:

- `dist\Facturion.exe`
- `dist\release\Facturion-Setup.exe`
- `dist\release\version.json`

### Publicación automática en GitHub

El workflow está en:

`.github/workflows/release.yml`

Se ejecuta al publicar un tag como:

```powershell
git tag v0.2.0
git push origin v0.2.0
```

<#
build.ps1
Empaqueta la app con PyInstaller en Windows.

Uso:
  powershell -ExecutionPolicy Bypass -File .\build.ps1 [-Name "InventarioApp"] [-Console]

Opciones por defecto:
  - onefile, noconsole, clean
  - hidden-import: sqlite3, sqlalchemy.dialects.sqlite, win32com.client, reportlab, scripts.seed_surt_ventas
  - add-data: config;config (y copia post-build)
  - copia post-build opcional de app_data/ a dist/app_data
#>

param(
  [string]$Name = "InventarioApp",
  [switch]$Console,
  [string]$Icon,
  [switch]$OneDir,
  [switch]$NoClean,
  [switch]$InstallMissing
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }

# Ir a la carpeta del script
Set-Location -Path $PSScriptRoot

# Resolver el intérprete de Python a usar para el build
# 1) Prioriza venv local del proyecto (./.venv)
# 2) Luego 'python' del PATH
# 3) Luego 'py' launcher
$py = $null
$venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (Test-Path $venvPy) { $py = $venvPy }
if (-not $py) { $py = (Get-Command python -ErrorAction SilentlyContinue) }
if (-not $py) { $py = (Get-Command py -ErrorAction SilentlyContinue) }
if (-not $py) {
  Write-Err "No se encontró 'python'. Activa tu entorno virtual (.venv) o instala Python."
  exit 1
}

# Instalacion opcional de herramientas/dep si se solicita (-InstallMissing)
if ($InstallMissing) {
  Write-Info "Comprobando e instalando herramientas requeridas (-InstallMissing)..."
  # PyInstaller
  & $py "-c" "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Info "Instalando PyInstaller..."
    & $py -m pip install -U pyinstaller pyinstaller-hooks-contrib
    if ($LASTEXITCODE -ne 0) { Write-Err "No se pudo instalar PyInstaller"; exit 1 }
  }
  # Dependencias runtime
  & $py "-c" "import importlib.util,sys;mods=['sqlalchemy','reportlab','PIL','openpyxl','barcode','win32com.client','win32api','win32print'];missing=[m for m in mods if importlib.util.find_spec(m) is None];sys.exit(0 if not missing else 1)" | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Info "Instalando dependencias (sqlalchemy, reportlab, pillow, openpyxl, python-barcode, pywin32)..."
    & $py -m pip install -U sqlalchemy reportlab pillow openpyxl python-barcode pywin32
    if ($LASTEXITCODE -ne 0) { Write-Err "No se pudieron instalar dependencias"; exit 1 }
  }
}
# Verificar PyInstaller en ese mismo Python
Write-Info "Verificando PyInstaller en el mismo intérprete..."
& $py "-c" "import sys; import importlib.util as i; sys.exit(0 if i.find_spec('PyInstaller') else 1)" | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Err "PyInstaller no está instalado en este entorno. Instala con: $py -m pip install -U pyinstaller pyinstaller-hooks-contrib"
  exit 1
}

# Verificar dependencias Python requeridas en el mismo entorno del build
Write-Info "Verificando dependencias de Python (sqlalchemy, reportlab, pillow, openpyxl, python-barcode, pywin32)..."

$mods = "'sqlalchemy','reportlab','PIL','openpyxl','barcode','win32com.client','win32api','win32print'"
& $py "-c" "import importlib.util,sys;mods=[$mods];missing=[m for m in mods if importlib.util.find_spec(m) is None];
print('Faltan:', missing) if missing else print('OK deps');sys.exit(1 if missing else 0)" | Out-Null
if ($LASTEXITCODE -ne 0) {
  Write-Err "Faltan paquetes de Python en el entorno actual. Instala: pip install sqlalchemy reportlab pillow openpyxl python-barcode pywin32"
  exit 1
}

# Limpiar build previo

Write-Info "Limpiando carpetas build/dist previas..."
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue | Out-Null

$entry = Join-Path $PSScriptRoot "run_app.py"
if (-not (Test-Path $entry)) {
  Write-Err "No se encuentra run_app.py en $PSScriptRoot"
  exit 1
}

# Argumentos de PyInstaller
$argsList = @()
$argsList += @($entry)
$argsList += @("--name", $Name)
if (-not $OneDir) { $argsList += @("--onefile") }
if (-not $NoClean) { $argsList += @("--clean") }
$argsList += @("--noconfirm")
if ($Console) { $argsList += @("--console") } else { $argsList += @("--noconsole") }
if ($Icon -and (Test-Path $Icon)) { $argsList += @("--icon", $Icon) }

# Hidden imports necesarios en runtime
$argsList += @("--hidden-import=sqlite3")
$argsList += @("--hidden-import=sqlalchemy.dialects.sqlite")
$argsList += @("--hidden-import=sqlalchemy")
$argsList += @("--hidden-import=win32com.client")
$argsList += @("--hidden-import=reportlab")
$argsList += @("--hidden-import=openpyxl")
$argsList += @("--hidden-import=barcode")
$argsList += @("--hidden-import=win32api")
$argsList += @("--hidden-import=win32print")
$argsList += @("--hidden-import=scripts.seed_surt_ventas")
 $argsList += @("--hidden-import=src.gui.sql_importer_dialog")
 $argsList += @("--hidden-import=src.gui.bluetooth_scan_dialog")

# Recolectar paquetes (si PyInstaller moderno)
$argsList += @("--collect-all", "reportlab")
$argsList += @("--collect-all", "PIL")
$argsList += @("--collect-all", "openpyxl")
$argsList += @("--collect-all", "barcode")
$argsList += @("--collect-all", "sqlalchemy")

# Datos adicionales: settings.ini y otros dentro de config/
if (Test-Path (Join-Path $PSScriptRoot "config")) {
  $argsList += @("--add-data", "config;config")
}
if (Test-Path (Join-Path $PSScriptRoot "app_data")) {
  $argsList += @("--add-data", "app_data;app_data")
}

Write-Info "Ejecutando PyInstaller con el intérprete seleccionado..."
Write-Host (("" + $py + " -m PyInstaller ") + ($argsList -join ' '))

& $py -m PyInstaller @argsList
if ($LASTEXITCODE -ne 0) {
  Write-Err "Fallo el empaquetado (exit code $LASTEXITCODE)"
  exit $LASTEXITCODE
}

# Detectar destino (onefile u onedir)
$exeOneFile = Join-Path $PSScriptRoot "dist\$Name.exe"
$exeOneDir  = Join-Path $PSScriptRoot "dist\$Name\$Name.exe"
if (Test-Path $exeOneFile) {
  $distRoot = Join-Path $PSScriptRoot "dist"
  Write-Ok "Build OK (onefile): $exeOneFile"
} elseif (Test-Path $exeOneDir) {
  $distRoot = Join-Path $PSScriptRoot "dist\$Name"
  Write-Ok "Build OK (onedir): $exeOneDir"
} else {
  Write-Err "No se encontro el ejecutable en dist/"
  exit 1
}

# Copiar config editable
if (Test-Path (Join-Path $PSScriptRoot "config")) {
  $dst = Join-Path $distRoot "config"
  New-Item -ItemType Directory -Path $dst -Force | Out-Null
  Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "config\*") $dst
  Write-Ok "Config copiado a $dst"
}

# Copiar app_data si existe
$srcAppData = Join-Path $PSScriptRoot "app_data"
if (Test-Path $srcAppData) {
  $dstAppData = Join-Path $distRoot "app_data"
  New-Item -ItemType Directory -Path $dstAppData -Force | Out-Null
  Copy-Item -Recurse -Force (Join-Path $srcAppData "*") $dstAppData
  Write-Ok "app_data copiado a $dstAppData"
}

# Copiar inventario.db si existe en el proyecto (DB inicial editable en dist)
$projDb = Join-Path $PSScriptRoot "inventario.db"
if (Test-Path $projDb) {
  New-Item -ItemType Directory -Path (Join-Path $distRoot "app_data") -Force | Out-Null; Copy-Item -Force $projDb (Join-Path $distRoot "app_data\inventario.db")
  Write-Ok "inventario.db copiado a $distRoot"
}

Write-Ok "Listo"



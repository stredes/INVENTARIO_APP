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
  [switch]$NoClean
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }

# Ir a la carpeta del script
Set-Location -Path $PSScriptRoot

# Verificar PyInstaller
Write-Info "Verificando PyInstaller..."
$pyi = (Get-Command pyinstaller -ErrorAction SilentlyContinue)
if (-not $pyi) {
  Write-Err "PyInstaller no esta instalado. Instala con: pip install pyinstaller"
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
$argsList += @("--hidden-import=win32com.client")
$argsList += @("--hidden-import=reportlab")
$argsList += @("--hidden-import=scripts.seed_surt_ventas")
 $argsList += @("--hidden-import=src.gui.sql_importer_dialog")

# Recolectar paquetes (si PyInstaller moderno)
$argsList += @("--collect-all", "reportlab")
$argsList += @("--collect-all", "PIL")

# Datos adicionales: settings.ini y otros dentro de config/
if (Test-Path (Join-Path $PSScriptRoot "config")) {
  $argsList += @("--add-data", "config;config")
}
if (Test-Path (Join-Path $PSScriptRoot "app_data")) {
  $argsList += @("--add-data", "app_data;app_data")
}

Write-Info "Ejecutando PyInstaller..."
Write-Host ("pyinstaller " + ($argsList -join ' '))

pyinstaller @argsList
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



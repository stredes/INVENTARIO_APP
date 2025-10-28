<#
build.ps1
Empaqueta la app con PyInstaller en Windows.

Uso:
  powershell -ExecutionPolicy Bypass -File .\build.ps1 [-Name "InventarioApp"] [-Console]

Opciones por defecto:
  - onefile, noconsole, clean
  - hidden-import: sqlite3, sqlalchemy.dialects.sqlite, win32com.client, reportlab
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
  Write-Err "PyInstaller no estÃ¡ instalado. InstÃ¡lalo con: pip install pyinstaller"
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

# Recolectar paquetes (si PyInstaller moderno)
$argsList += @("--collect-all", "reportlab")

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

$exePath = Join-Path $PSScriptRoot "dist\$Name.exe"
if (Test-Path $exePath) {
  Write-Ok "Build OK: $exePath"
  # Copiar config como carpeta externa editable en dist
  $distConfig = Join-Path $PSScriptRoot "dist\config"
  if (Test-Path (Join-Path $PSScriptRoot "config")) {
    New-Item -ItemType Directory -Path $distConfig -Force | Out-Null
    Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "config\*") $distConfig
    Write-Ok "Config copiado a dist/config (editable)"
  }
  # Copiar app_data (si existe) para recursos adicionales
  $srcAppData = Join-Path $PSScriptRoot "app_data"
  if (Test-Path $srcAppData) {
    $dstAppData = Join-Path $PSScriptRoot "dist\app_data"
    New-Item -ItemType Directory -Path $dstAppData -Force | Out-Null
    Copy-Item -Recurse -Force (Join-Path $srcAppData "*") $dstAppData
    Write-Ok "app_data copiado a dist/app_data"
  }
} else {
  Write-Err "No se encontrÃ³ el ejecutable en dist/"
  exit 1
}


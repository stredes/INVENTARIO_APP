<#
build.ps1
Empaqueta la app con PyInstaller en Windows.

Uso:
  powershell -ExecutionPolicy Bypass -File .\build.ps1 [-Name "InventarioApp"] [-Console]

Opciones por defecto:
  - onefile, noconsole, clean
  - hidden-import: sqlite3, sqlalchemy.dialects.sqlite, win32com.client
  - add-data: config;config
#>

param(
  [string]$Name = "InventarioApp",
  [switch]$Console
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
  Write-Err "PyInstaller no está instalado. Instálalo con: pip install pyinstaller"
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
$argsList += @("--onefile")
$argsList += @("--clean")
if ($Console) { $argsList += @("--console") } else { $argsList += @("--noconsole") }

# Hidden imports necesarios en runtime
$argsList += @("--hidden-import=sqlite3")
$argsList += @("--hidden-import=sqlalchemy.dialects.sqlite")
$argsList += @("--hidden-import=win32com.client")

# Datos adicionales: settings.ini y otros dentro de config/
if (Test-Path (Join-Path $PSScriptRoot "config")) {
  $argsList += @("--add-data", "config;config")
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
} else {
  Write-Err "No se encontró el ejecutable en dist/"
  exit 1
}

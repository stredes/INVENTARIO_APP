<#
restore_env.ps1
- Crea/restaura el ambiente virtual .venv
- Instala dependencias (requirements.txt si existe)
- Configura VS Code para usar el venv
Soporta múltiples versiones de Python instaladas. Intenta 3.12, 3.11, 3.10, 3.9
o la instalación por defecto del sistema.
#>

param(
  [string]$VenvDir = ".venv",
  [string]$ReqFile = "requirements.txt",
  [string]$PreferredPython = "3.12"
)

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }

function Resolve-PythonExe {
  param([string]$Preferred)
  $candidates = @()
  if ($Preferred) { $candidates += $Preferred }
  $candidates += @("3.12","3.11","3.10","3.9","3")

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    foreach ($v in $candidates) {
      try {
        $p = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() }
      } catch {}
    }
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) { return $python.Source }
  return $null
}

# --- 1) Borrar venv antiguo ---
if (Test-Path $VenvDir) {
  Write-Warn "Eliminando ambiente virtual anterior: $VenvDir"
  Remove-Item -Recurse -Force $VenvDir
}

# --- 2) Crear venv nuevo con el mejor Python disponible ---
Write-Info "Buscando intérprete de Python disponible (preferido: $PreferredPython)..."
$pyExe = Resolve-PythonExe -Preferred $PreferredPython
if (-not $pyExe) {
  Write-Err "No se encontró Python 3.x en el sistema. Instala Python 3.12/3.11."
  exit 1
}
Write-Info "Usando: $pyExe"

Write-Info "Creando nuevo ambiente virtual..."
& $pyExe -m venv $VenvDir
if ($LASTEXITCODE -ne 0 -or -not (Test-Path "$VenvDir\Scripts\Activate.ps1")) {
  Write-Err "No se pudo crear el venv con: $pyExe"
  exit 1
}

# --- 3) Activar e instalar dependencias ---
Write-Info "Activando el ambiente virtual..."
& "$VenvDir\Scripts\Activate.ps1"

Write-Info "Actualizando pip/setuptools/wheel..."
python -m pip install -U pip setuptools wheel

if (Test-Path $ReqFile) {
  Write-Info "Instalando dependencias desde $ReqFile..."
  pip install -r $ReqFile
} else {
  Write-Warn "No existe requirements.txt, instalando paquetes básicos..."
  pip install sqlalchemy reportlab pillow openpyxl python-barcode
}

# --- 4) Crear settings.json para VS Code ---
$vsDir = ".vscode"
$settingsFile = "$vsDir\settings.json"
if (-not (Test-Path $vsDir)) { New-Item -ItemType Directory -Path $vsDir | Out-Null }

$settings = @{
  "python.defaultInterpreterPath" = "${PWD}\$VenvDir\Scripts\python.exe"
  "python.analysis.extraPaths"    = @("${PWD}\src")
}
$settings | ConvertTo-Json -Depth 3 | Out-File -Encoding UTF8 $settingsFile

Write-Ok "Ambiente virtual restaurado en $VenvDir"
Write-Ok "Si usas VS Code: Ctrl+Shift+P → Python: Select Interpreter y elige .venv"

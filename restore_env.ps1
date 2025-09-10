<#
restore_env.ps1
- Restaura el ambiente virtual .venv
- Instala dependencias (requirements.txt si existe)
- Configura VS Code para usar el venv
#>

# --- CONFIG ---
$venvDir = ".venv"
$reqFile = "requirements.txt"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[OK]   $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[ERR]  $msg" -ForegroundColor Red }

# --- 1) Borrar venv antiguo ---
if (Test-Path $venvDir) {
    Write-Warn "Eliminando ambiente virtual anterior: $venvDir"
    Remove-Item -Recurse -Force $venvDir
}

# --- 2) Crear venv nuevo con Python 3.12 ---
Write-Info "Creando nuevo ambiente virtual..."
py -3.12 -m venv $venvDir

if (-not (Test-Path "$venvDir\Scripts\Activate.ps1")) {
    Write-Err "No se pudo crear el venv. ¿Está instalado Python 3.12?"
    exit 1
}

# --- 3) Activar e instalar dependencias ---
Write-Info "Activando el ambiente virtual..."
& "$venvDir\Scripts\Activate.ps1"

Write-Info "Actualizando pip/setuptools/wheel..."
python -m pip install -U pip setuptools wheel

if (Test-Path $reqFile) {
    Write-Info "Instalando dependencias desde $reqFile..."
    pip install -r $reqFile
} else {
    Write-Warn "No existe requirements.txt, instalando paquetes básicos..."
    pip install sqlalchemy alembic pandas openpyxl reportlab
}

# --- 4) Crear settings.json para VS Code ---
$vsDir = ".vscode"
$settingsFile = "$vsDir\settings.json"
if (-not (Test-Path $vsDir)) { New-Item -ItemType Directory -Path $vsDir | Out-Null }

$settings = @{
    "python.defaultInterpreterPath" = "${PWD}\$venvDir\Scripts\python.exe"
    "python.analysis.extraPaths"    = @("${PWD}\src")
}
$settings | ConvertTo-Json -Depth 3 | Out-File -Encoding UTF8 $settingsFile

Write-Ok "Ambiente virtual restaurado en $venvDir"
Write-Ok "Ahora en VS Code: Ctrl+Shift+P → 'Python: Select Interpreter' y selecciona .venv"

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

$AppName = "Facturion"
$MainScript = Join-Path $ProjectRoot "main.py"
$BuildDir = Join-Path $ProjectRoot "build"
$DistDir = Join-Path $ProjectRoot "dist"
$SpecFile = Join-Path $ProjectRoot "$AppName.spec"

if (-not (Test-Path $MainScript)) {
    throw "No se encontró main.py en $ProjectRoot"
}

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Ensure-Command {
    param([string]$CommandName)
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontró el comando '$CommandName'. Instala Python y asegúrate de que esté en PATH."
    }
}

Ensure-Command "python"

Write-Step "Verificando PyInstaller"
$pyInstallerInstalled = $false
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)" > $null 2>&1
if ($LASTEXITCODE -eq 0) {
    $pyInstallerInstalled = $true
}

if (-not $pyInstallerInstalled) {
    Write-Step "Instalando PyInstaller"
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar PyInstaller."
    }
}

Write-Step "Limpiando compilaciones anteriores"
if (Test-Path $BuildDir) {
    Remove-Item -LiteralPath $BuildDir -Recurse -Force
}
if (Test-Path $DistDir) {
    Remove-Item -LiteralPath $DistDir -Recurse -Force
}
if (Test-Path $SpecFile) {
    Remove-Item -LiteralPath $SpecFile -Force
}

Write-Step "Generando ejecutable"
python -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name $AppName `
    --collect-all customtkinter `
    --hidden-import matplotlib.backends.backend_tkagg `
    --hidden-import tkinter `
    $MainScript

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller no pudo generar el ejecutable."
}

$ExePathFolder = Join-Path $DistDir "$AppName\$AppName.exe"
$ExePathOneDir = Join-Path $DistDir "$AppName.exe"

Write-Step "Proceso finalizado"
if (Test-Path $ExePathFolder) {
    Write-Host "EXE generado en: $ExePathFolder" -ForegroundColor Green
} elseif (Test-Path $ExePathOneDir) {
    Write-Host "EXE generado en: $ExePathOneDir" -ForegroundColor Green
} else {
    Write-Warning "No se encontró el ejecutable esperado en '$ExePathFolder' ni en '$ExePathOneDir'."
}

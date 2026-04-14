$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ProjectRoot

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Get-AppMeta {
    $json = python -c "import json; from utils.app_metadata import APP_NAME, APP_VERSION, APP_EXECUTABLE_NAME; print(json.dumps({'name': APP_NAME, 'version': APP_VERSION, 'exe': APP_EXECUTABLE_NAME}))"
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron leer los metadatos de la app."
    }
    return $json | ConvertFrom-Json
}

function Ensure-Command {
    param([string]$CommandName)
    if (-not (Get-Command $CommandName -ErrorAction SilentlyContinue)) {
        throw "No se encontró el comando '$CommandName'."
    }
}

Ensure-Command "python"

$meta = Get-AppMeta
$appName = $meta.name
$appVersion = $meta.version
$exeName = $meta.exe
$distDir = Join-Path $ProjectRoot "dist"
$buildDir = Join-Path $ProjectRoot "build"
$releaseDir = Join-Path $distDir "release"
$releaseAppDir = Join-Path $releaseDir "app"
$portableExe = Join-Path $distDir $exeName
$setupExe = Join-Path $releaseDir "Facturion-Setup.exe"
$versionJson = Join-Path $releaseDir "version.json"

Write-Step "Verificando dependencias de build"
python -c "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec('PyInstaller') else 1)" > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Step "Instalando PyInstaller"
    python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo instalar PyInstaller."
    }
}

$iscc = $null
$possibleIsccPaths = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles}\Inno Setup 6\ISCC.exe"
)
foreach ($candidate in $possibleIsccPaths) {
    if ($candidate -and (Test-Path $candidate)) {
        $iscc = $candidate
        break
    }
}
if (-not $iscc) {
    throw "No se encontró Inno Setup 6. Instálalo o ejecútalo desde el workflow de GitHub."
}

Write-Step "Limpiando artefactos anteriores"
if (Test-Path $buildDir) { Remove-Item -LiteralPath $buildDir -Recurse -Force }
if (Test-Path $distDir) { Remove-Item -LiteralPath $distDir -Recurse -Force }
New-Item -ItemType Directory -Path $releaseAppDir -Force | Out-Null

Write-Step "Generando ejecutable portable"
python -m PyInstaller `
    --noconfirm `
    --clean `
    --onefile `
    --windowed `
    --name $appName `
    --collect-all customtkinter `
    --hidden-import matplotlib.backends.backend_tkagg `
    --hidden-import tkinter `
    main.py
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller no pudo generar el ejecutable portable."
}

if (-not (Test-Path $portableExe)) {
    throw "No se encontró el ejecutable portable esperado en $portableExe"
}

Copy-Item -LiteralPath $portableExe -Destination (Join-Path $releaseAppDir $exeName) -Force

Write-Step "Generando Setup.exe"
& $iscc "/DMyAppVersion=$appVersion" "/DMyAppExeName=$exeName" "/DMySourceDir=$releaseAppDir" "/DMyOutputDir=$releaseDir" "installer\Facturion.iss"
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup no pudo generar el instalador."
}

$versionPayload = @{
    app_name = $appName
    version = $appVersion
    portable_exe = $exeName
    setup_asset = "Facturion-Setup.exe"
    generated_at = [DateTime]::UtcNow.ToString("o")
} | ConvertTo-Json -Depth 4
Set-Content -LiteralPath $versionJson -Value $versionPayload -Encoding UTF8

Write-Step "Build release listo"
Write-Host "Portable EXE: $portableExe" -ForegroundColor Green
Write-Host "Setup EXE: $setupExe" -ForegroundColor Green
Write-Host "Metadata: $versionJson" -ForegroundColor Green

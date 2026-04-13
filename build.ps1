param(
  [switch]$InstallMissing,
  [switch]$SkipSetup,
  [switch]$SkipPublish,
  [string]$ReleaseNotes = "Release generado automáticamente desde build.ps1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

Set-Location -Path $PSScriptRoot

function Get-PythonCommand {
  $venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $cmd = Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "No se encontró Python para ejecutar el build."
}

function Ensure-Tooling([string]$PythonExe) {
  if (-not $InstallMissing) { return }
  Write-Info "Instalando dependencias de build..."
  & $PythonExe -m pip install -U pyinstaller pyinstaller-hooks-contrib | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar PyInstaller." }
}

function Read-ReleaseConfig {
  $path = Join-Path $PSScriptRoot "config\release.json"
  if (-not (Test-Path $path)) { throw "Falta config\release.json" }
  return (Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-ReleaseConfig($cfg) {
  $path = Join-Path $PSScriptRoot "config\release.json"
  ($cfg | ConvertTo-Json -Depth 10) | Set-Content -Path $path -Encoding UTF8
}

function New-BuildVersion($cfg) {
  $counter = [int]$cfg.release_counter + 1
  $cfg.release_counter = $counter
  Write-ReleaseConfig $cfg
  $version = "{0}-build.{1}" -f $cfg.base_version, $counter
  $tag = "v$version"
  return @{
    Counter = $counter
    Version = $version
    Tag = $tag
  }
}

function Write-BuildInfo($cfg, $buildMeta) {
  $buildInfo = [ordered]@{
    app_name = [string]$cfg.app_name
    company_name = [string]$cfg.company_name
    version = [string]$buildMeta.Version
    release_tag = [string]$buildMeta.Tag
    channel = [string]$cfg.release_channel
    repo_owner = [string]$cfg.repo_owner
    repo_name = [string]$cfg.repo_name
    portable_asset_pattern = [string]$cfg.portable_asset_pattern
    setup_asset_pattern = [string]$cfg.setup_asset_pattern
    built_at_utc = [DateTime]::UtcNow.ToString("o")
  }
  $path = Join-Path $PSScriptRoot "config\build_info.json"
  ($buildInfo | ConvertTo-Json -Depth 10) | Set-Content -Path $path -Encoding UTF8
  Write-Ok "build_info.json actualizado: $($buildMeta.Version)"
}

function Require-Module([string]$PythonExe, [string]$module) {
  & $PythonExe -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('$module') else 1)" | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "Falta el módulo Python '$module'." }
}

function Find-ISCC {
  $candidates = @(
    ${env:ISCC_EXE},
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
  ) | Where-Object { $_ }
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) { return $candidate }
  }
  return $null
}

function New-InnoScript([string]$AppName, [string]$Version, [string]$SourceDir) {
  $issPath = Join-Path $PSScriptRoot "build\installer.iss"
  $outputDir = Join-Path $PSScriptRoot "dist\installer"
  New-Item -ItemType Directory -Force -Path (Split-Path $issPath), $outputDir | Out-Null
  $iss = @"
#define MyAppName "$AppName"
#define MyAppVersion "$Version"
#define MyAppExeName "$AppName.exe"
#define MySourceDir "$SourceDir"

[Setup]
AppId={{$AppName}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=$outputDir
OutputBaseFilename=$AppName-setup-$Version
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent
"@
  Set-Content -Path $issPath -Value $iss -Encoding UTF8
  return $issPath
}

function Compress-Folder([string]$Source, [string]$Destination) {
  if (Test-Path $Destination) { Remove-Item -Force $Destination }
  Compress-Archive -Path (Join-Path $Source "*") -DestinationPath $Destination -Force
  Write-Ok "ZIP generado: $Destination"
}

function Ensure-GitHubCli {
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if (-not $gh) { throw "No se encontró GitHub CLI ('gh'). Instálalo e inicia sesión con 'gh auth login'." }
  return $gh.Source
}

function Publish-Release([string]$RepoSlug, [string]$Tag, [string]$Title, [string[]]$Assets, [string]$Notes) {
  $gh = Ensure-GitHubCli
  & $gh release view $Tag --repo $RepoSlug | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Info "Creando release $Tag en $RepoSlug..."
    & $gh release create $Tag --repo $RepoSlug --title $Title --notes $Notes | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el release $Tag." }
  }
  Write-Info "Subiendo assets al release $Tag..."
  & $gh release upload $Tag @Assets --repo $RepoSlug --clobber | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "No se pudieron subir los assets al release $Tag." }
  Write-Ok "Release actualizado: $Tag"
}

$python = Get-PythonCommand
Write-Info "Python usado para build: $python"
Ensure-Tooling -PythonExe $python
Require-Module -PythonExe $python -module "PyInstaller"

$releaseCfg = Read-ReleaseConfig
$buildMeta = New-BuildVersion -cfg $releaseCfg
Write-BuildInfo -cfg $releaseCfg -buildMeta $buildMeta

$appName = [string]$releaseCfg.app_name
$repoSlug = "{0}/{1}" -f $releaseCfg.repo_owner, $releaseCfg.repo_name
$distRoot = Join-Path $PSScriptRoot "dist"
$buildRoot = Join-Path $PSScriptRoot "build"
$assetsRoot = Join-Path $PSScriptRoot "artifacts"
$portableDir = Join-Path $distRoot $appName

Write-Info "Limpiando build/dist..."
Remove-Item -Recurse -Force $buildRoot, $distRoot, $assetsRoot -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Force -Path $buildRoot, $distRoot, $assetsRoot | Out-Null

$entry = Join-Path $PSScriptRoot "run_app.py"
if (-not (Test-Path $entry)) { throw "No se encontró run_app.py" }

$pyArgs = @(
  "-m", "PyInstaller",
  $entry,
  "--name", $appName,
  "--noconfirm",
  "--clean",
  "--onedir",
  "--noconsole",
  "--hidden-import=sqlite3",
  "--hidden-import=sqlalchemy",
  "--hidden-import=sqlalchemy.dialects.sqlite",
  "--hidden-import=win32com.client",
  "--hidden-import=reportlab",
  "--hidden-import=openpyxl",
  "--hidden-import=barcode",
  "--hidden-import=win32api",
  "--hidden-import=win32print",
  "--collect-all", "reportlab",
  "--collect-all", "PIL",
  "--collect-all", "openpyxl",
  "--collect-all", "barcode",
  "--collect-all", "sqlalchemy"
)

if (Test-Path (Join-Path $PSScriptRoot "config")) {
  $pyArgs += @("--add-data", "config;config")
}
if (Test-Path (Join-Path $PSScriptRoot "app_data")) {
  $pyArgs += @("--add-data", "app_data;app_data")
}

Write-Info "Ejecutando PyInstaller..."
& $python @pyArgs | Out-Host
if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminó con código $LASTEXITCODE" }

if (-not (Test-Path (Join-Path $portableDir "$appName.exe"))) {
  throw "No se generó el ejecutable esperado en $portableDir"
}

$configDir = Join-Path $portableDir "config"
New-Item -ItemType Directory -Force -Path $configDir | Out-Null
Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "config\*") $configDir

if (Test-Path (Join-Path $PSScriptRoot "app_data")) {
  $dstAppData = Join-Path $portableDir "app_data"
  New-Item -ItemType Directory -Force -Path $dstAppData | Out-Null
  Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "app_data\*") $dstAppData
}

$portableZip = Join-Path $assetsRoot ("{0}-portable-{1}.zip" -f $appName, $buildMeta.Version)
Compress-Folder -Source $portableDir -Destination $portableZip

$buildZip = Join-Path $assetsRoot ("build-{0}.zip" -f $buildMeta.Version)
$distZip = Join-Path $assetsRoot ("dist-{0}.zip" -f $buildMeta.Version)
Compress-Folder -Source $buildRoot -Destination $buildZip
Compress-Folder -Source $distRoot -Destination $distZip

$setupExe = $null
if (-not $SkipSetup) {
  $iscc = Find-ISCC
  if (-not $iscc) {
    throw "No se encontró Inno Setup (ISCC.exe). Instálalo o ejecuta con -SkipSetup."
  }
  $iss = New-InnoScript -AppName $appName -Version $buildMeta.Version -SourceDir $portableDir
  Write-Info "Compilando instalador con Inno Setup..."
  & $iscc $iss | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el instalador." }
  $setupExe = Join-Path $distRoot "installer\${appName}-setup-$($buildMeta.Version).exe"
  if (-not (Test-Path $setupExe)) { throw "No se encontró el setup generado." }
  Write-Ok "Setup generado: $setupExe"
}

$manifest = [ordered]@{
  version = $buildMeta.Version
  release_tag = $buildMeta.Tag
  repo = $repoSlug
  assets = @(
    @{ kind = "portable"; path = (Split-Path $portableZip -Leaf) },
    @{ kind = "build"; path = (Split-Path $buildZip -Leaf) },
    @{ kind = "dist"; path = (Split-Path $distZip -Leaf) }
  )
  built_at_utc = [DateTime]::UtcNow.ToString("o")
}
if ($setupExe) {
  $manifest.assets += @{ kind = "setup"; path = (Split-Path $setupExe -Leaf) }
}
$manifestPath = Join-Path $assetsRoot "release-manifest.json"
($manifest | ConvertTo-Json -Depth 10) | Set-Content -Path $manifestPath -Encoding UTF8
Write-Ok "Manifest generado: $manifestPath"

$assets = @($portableZip, $buildZip, $distZip, $manifestPath)
if ($setupExe) { $assets += $setupExe }

if (-not $SkipPublish) {
  Publish-Release -RepoSlug $repoSlug -Tag $buildMeta.Tag -Title "$appName $($buildMeta.Version)" -Assets $assets -Notes $ReleaseNotes
}

Write-Ok "Build completo: $($buildMeta.Version)"

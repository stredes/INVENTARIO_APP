param(
  [switch]$InstallMissing,
  [switch]$SkipSetup,
  [switch]$SkipPublish,
  [switch]$SkipGitSync,
  [string]$ReleaseNotes = "Release generado automÃ¡ticamente desde build.ps1"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Err($msg)  { Write-Host "[ERR ] $msg" -ForegroundColor Red }

Set-Location -Path $PSScriptRoot

function Write-Utf8File([string]$Path, [string]$Content) {
  $dir = Split-Path -Parent $Path
  if ($dir) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }
  $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
  [System.IO.File]::WriteAllText($Path, $Content, $utf8NoBom)
}

function Get-PythonCommand {
  $venvPy = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
  if (Test-Path $venvPy) { return $venvPy }
  $cmd = Get-Command python -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  $cmd = Get-Command py -ErrorAction SilentlyContinue
  if ($cmd) { return $cmd.Source }
  throw "No se encontrÃ³ Python para ejecutar el build."
}

function Get-GitCommand {
  $git = Get-Command git -ErrorAction SilentlyContinue
  if (-not $git) { throw "No se encontro git para sincronizar el repositorio." }
  return $git.Source
}

function Get-GitBranchName([string]$GitExe) {
  & $GitExe rev-parse --abbrev-ref HEAD | Out-Null
  $branch = (& $GitExe rev-parse --abbrev-ref HEAD).Trim()
  if ($LASTEXITCODE -ne 0 -or -not $branch -or $branch -eq "HEAD") {
    throw "No se pudo determinar la rama actual de git."
  }
  return $branch
}

function Sync-GitReleaseState([string]$Version, [string]$Tag) {
  if ($SkipGitSync) {
    Write-Info "Se omitira la sincronizacion git por -SkipGitSync."
    return $null
  }
  $git = Get-GitCommand
  $branch = Get-GitBranchName -GitExe $git
  Write-Info "Sincronizando cambios con git en la rama $branch..."
  & $git add -A -- . | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "No se pudieron preparar cambios con git add." }
  & $git reset -q -- artifacts build dist | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "No se pudieron limpiar artifacts/build/dist del indice git." }
  & $git diff --cached --quiet
  if ($LASTEXITCODE -eq 1) {
    $commitMsg = "build: release $Version"
    & $git commit -m $commitMsg | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el commit automatico del release." }
  }
  & $git push origin $branch | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "No se pudo hacer push de la rama $branch." }
  return @{
    GitExe = $git
    Branch = $branch
  }
}

function Initialize-Tooling([string]$PythonExe) {
  if (-not $InstallMissing) { return }
  Install-BuildTooling -PythonExe $PythonExe -Upgrade
}

function Read-ReleaseConfig {
  $path = Join-Path $PSScriptRoot "config\release.json"
  if (-not (Test-Path $path)) { throw "Falta config\release.json" }
  return (Get-Content $path -Raw -Encoding UTF8 | ConvertFrom-Json)
}

function Write-ReleaseConfig($cfg) {
  $path = Join-Path $PSScriptRoot "config\release.json"
  Write-Utf8File -Path $path -Content ($cfg | ConvertTo-Json -Depth 10)
}

function Get-NextSemanticVersion([string]$Version) {
  $baseVersion = if ([string]::IsNullOrWhiteSpace($Version)) { "0.1.0" } else { $Version.Trim() }
  $parts = @(($baseVersion -split '\.'))
  if ($parts.Count -lt 3) {
    throw "base_version debe tener formato semántico mayor.menor.parche"
  }
  try {
    $major = [int]$parts[0]
    $minor = [int]$parts[1]
    $patch = [int]$parts[2]
  }
  catch {
    throw "base_version debe tener formato semántico mayor.menor.parche"
  }
  $patch += 1
  return "$major.$minor.$patch"
}

function New-BuildVersion($cfg) {
  $previousVersion = [string]$cfg.base_version
  $version = Get-NextSemanticVersion -Version $previousVersion
  $cfg.base_version = $version
  $cfg.release_counter = [int]($cfg.release_counter) + 1
  Write-ReleaseConfig $cfg
  $tag = "v$version"
  return @{
    PreviousVersion = $previousVersion
    Counter = [int]$cfg.release_counter
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
  Write-Utf8File -Path $path -Content ($buildInfo | ConvertTo-Json -Depth 10)
  Write-Ok "build_info.json actualizado: $($buildMeta.Version)"
}


function Test-PythonModule([string]$PythonExe, [string]$module) {
  & $PythonExe -c "import importlib.util,sys;sys.exit(0 if importlib.util.find_spec('$module') else 1)" | Out-Null
  return ($LASTEXITCODE -eq 0)
}

function Install-BuildTooling([string]$PythonExe, [switch]$Upgrade) {
  $pipArgs = @("-m", "pip", "install")
  if ($Upgrade) { $pipArgs += "-U" }
  $pipArgs += @("pyinstaller", "pyinstaller-hooks-contrib")
  Write-Info "Instalando dependencias de build..."
  & $PythonExe @pipArgs | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "No se pudo instalar PyInstaller." }
}

function Install-RequiredModule([string]$PythonExe, [string]$module) {
  if (Test-PythonModule -PythonExe $PythonExe -module $module) { return }
  Write-Info "Falta el modulo Python '$module'. Intentando instalar dependencias de build..."
  Install-BuildTooling -PythonExe $PythonExe
  if (-not (Test-PythonModule -PythonExe $PythonExe -module $module)) {
    throw "Falta el modulo Python '$module' incluso despues de intentar instalarlo."
  }
}

function Find-ISCC {
  $registryInstallLocation = $null
  $regPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
  )
  foreach ($regPath in $regPaths) {
    $match = Get-ItemProperty $regPath -ErrorAction SilentlyContinue |
      Where-Object {
        $_.PSObject.Properties.Match("DisplayName").Count -gt 0 -and
        [string]$_.DisplayName -like "*Inno Setup*"
      } |
      Select-Object -First 1
    if ($match -and $match.PSObject.Properties.Match("InstallLocation").Count -gt 0 -and $match.InstallLocation) {
      $registryInstallLocation = Join-Path $match.InstallLocation "ISCC.exe"
      break
    }
  }
  $candidates = @(
    ${env:ISCC_EXE},
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path ${env:LOCALAPPDATA} "Programs\Inno Setup 6\ISCC.exe"),
    $registryInstallLocation
  ) | Where-Object { $_ }
  foreach ($candidate in $candidates) {
    if (Test-Path $candidate) { return $candidate }
  }
  return $null
}

function Install-WingetPackage([string]$PackageId, [string]$DisplayName) {
  $winget = Get-Command winget -ErrorAction SilentlyContinue
  if (-not $winget) {
    Write-Info "No se encontro winget para instalar $DisplayName automaticamente."
    return $false
  }
  Write-Info "Instalando $DisplayName con winget..."
  & $winget.Source install --id $PackageId -e --accept-source-agreements --accept-package-agreements --disable-interactivity | Out-Host
  return ($LASTEXITCODE -eq 0)
}

function Get-ISCCPath {
  $iscc = Find-ISCC
  if ($iscc) { return $iscc }
  if (Install-WingetPackage -PackageId "JRSoftware.InnoSetup" -DisplayName "Inno Setup") {
    $iscc = Find-ISCC
    if ($iscc) { return $iscc }
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

function Build-FacturionExecutable([string]$PythonExe, [string]$PortableDir, [string]$BuildRoot) {
  $facturionRoot = Join-Path $PSScriptRoot "facturion-main\facturion-main"
  $facturionEntry = Join-Path $facturionRoot "main.py"
  if (-not (Test-Path $facturionEntry)) {
    Write-Info "No se encontro Facturion para empaquetar. Se omitira."
    return
  }

  Install-RequiredModule -PythonExe $PythonExe -module "customtkinter"
  Install-RequiredModule -PythonExe $PythonExe -module "matplotlib"

  $factBuild = Join-Path $BuildRoot "facturion-build"
  $factDist = Join-Path $BuildRoot "facturion-dist"
  $factSpec = Join-Path $BuildRoot "facturion-spec"
  New-Item -ItemType Directory -Force -Path $factBuild, $factDist, $factSpec | Out-Null

  $args = @(
    "-m", "PyInstaller",
    $facturionEntry,
    "--name", "Facturion",
    "--noconfirm",
    "--clean",
    "--onefile",
    "--windowed",
    "--distpath", $factDist,
    "--workpath", $factBuild,
    "--specpath", $factSpec,
    "--collect-all", "customtkinter",
    "--hidden-import", "matplotlib.backends.backend_tkagg",
    "--hidden-import", "tkinter"
  )

  Write-Info "Empaquetando Facturion..."
  Push-Location $facturionRoot
  try {
    & $PythonExe @args | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "No se pudo generar Facturion.exe" }
  }
  finally {
    Pop-Location
  }

  $factExe = Join-Path $factDist "Facturion.exe"
  if (-not (Test-Path $factExe)) {
    throw "No se encontro Facturion.exe despues del empaquetado."
  }

  $factTargetDir = Join-Path $PortableDir "facturion"
  New-Item -ItemType Directory -Force -Path $factTargetDir | Out-Null
  Copy-Item -LiteralPath $factExe -Destination (Join-Path $factTargetDir "Facturion.exe") -Force
  Write-Ok "Facturion incluido en el build portable."
}

function Compress-Folder([string]$Source, [string]$Destination) {
  if (Test-Path $Destination) { Remove-Item -Force $Destination }
  $maxAttempts = 5
  for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
    try {
      Compress-Archive -Path (Join-Path $Source "*") -DestinationPath $Destination -Force
      Write-Ok "ZIP generado: $Destination"
      return
    }
    catch {
      if ($attempt -eq $maxAttempts) { throw }
      Write-Info "No se pudo comprimir '$Source' en el intento $attempt/$maxAttempts. Reintentando..."
      Start-Sleep -Seconds 2
    }
  }
}

function Get-GitHubCliPath {
  $gh = Get-Command gh -ErrorAction SilentlyContinue
  if (-not $gh) {
    if (Install-WingetPackage -PackageId "GitHub.cli" -DisplayName "GitHub CLI") {
      $gh = Get-Command gh -ErrorAction SilentlyContinue
    }
  }
  if (-not $gh) { return $null }
  return $gh.Source
}

function Get-GitHubToken {
  if ($env:GH_TOKEN) { return $env:GH_TOKEN }
  if ($env:GITHUB_TOKEN) { return $env:GITHUB_TOKEN }
  return $null
}

function Invoke-GitHubJson([string]$Method, [string]$Url, [object]$Body = $null) {
  $token = Get-GitHubToken
  if (-not $token) { throw "No se encontro GH_TOKEN ni GITHUB_TOKEN para publicar por API." }
  $headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "User-Agent" = "inventario-app-build"
    "X-GitHub-Api-Version" = "2022-11-28"
  }
  $params = @{
    Method = $Method
    Uri = $Url
    Headers = $headers
    ErrorAction = "Stop"
  }
  if ($null -ne $Body) {
    $params.ContentType = "application/json"
    $params.Body = ($Body | ConvertTo-Json -Depth 10)
  }
  return Invoke-RestMethod @params
}

function Remove-GitHubReleaseAsset([string]$RepoSlug, [int]$AssetId) {
  $url = "https://api.github.com/repos/$RepoSlug/releases/assets/$AssetId"
  Invoke-GitHubJson -Method "DELETE" -Url $url | Out-Null
}

function Publish-ReleaseViaApi([string]$RepoSlug, [string]$Tag, [string]$Title, [string[]]$Assets, [string]$Notes, [string]$TargetBranch = $null) {
  try {
    $release = Invoke-GitHubJson -Method "GET" -Url "https://api.github.com/repos/$RepoSlug/releases/tags/$Tag"
  }
  catch {
    $release = $null
  }
  if (-not $release) {
    Write-Info "Creando release $Tag en $RepoSlug por API..."
    $body = @{
      tag_name = $Tag
      name = $Title
      body = $Notes
      draft = $false
      prerelease = $false
    }
    if ($TargetBranch) {
      $body.target_commitish = $TargetBranch
    }
    $release = Invoke-GitHubJson -Method "POST" -Url "https://api.github.com/repos/$RepoSlug/releases" -Body $body
  }

  $assetsUrl = [string]$release.assets_url
  $uploadUrl = ([string]$release.upload_url) -replace "\{\?name,label\}", ""
  $existingAssets = @()
  if ($assetsUrl) {
    $existingAssets = @(Invoke-GitHubJson -Method "GET" -Url $assetsUrl)
  }

  foreach ($asset in $Assets) {
    $name = Split-Path $asset -Leaf
    $existing = $existingAssets | Where-Object {
      $_.PSObject.Properties.Match("name").Count -gt 0 -and
      [string]$_.name -eq $name
    } | Select-Object -First 1
    if ($existing) {
      Write-Info "Reemplazando asset existente: $name"
      Remove-GitHubReleaseAsset -RepoSlug $RepoSlug -AssetId ([int]$existing.id)
    }

    $token = Get-GitHubToken
    $headers = @{
      Authorization = "Bearer $token"
      Accept = "application/vnd.github+json"
      "User-Agent" = "inventario-app-build"
      "X-GitHub-Api-Version" = "2022-11-28"
    }
    $uploadUri = "${uploadUrl}?name=$([System.Uri]::EscapeDataString($name))"
    Write-Info "Subiendo asset por API: $name"
    Invoke-WebRequest -Method Post -Uri $uploadUri -Headers $headers -InFile $asset -ContentType "application/octet-stream" -ErrorAction Stop | Out-Null
  }
  Write-Ok "Release actualizado por API: $Tag"
}

function Publish-Release([string]$RepoSlug, [string]$Tag, [string]$Title, [string[]]$Assets, [string]$Notes, [string]$TargetBranch = $null) {
  $gh = Get-GitHubCliPath
  if (-not $gh) {
    Write-Info "No se encontro GitHub CLI ('gh'). Intentando publicacion por API..."
    Publish-ReleaseViaApi -RepoSlug $RepoSlug -Tag $Tag -Title $Title -Assets $Assets -Notes $Notes -TargetBranch $TargetBranch
    return
  }
  if (-not $env:GH_TOKEN -and $env:GITHUB_TOKEN) {
    $env:GH_TOKEN = $env:GITHUB_TOKEN
  }
  & $gh release view $Tag --repo $RepoSlug | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Info "Creando release $Tag en $RepoSlug..."
    $createArgs = @("release", "create", $Tag, "--repo", $RepoSlug, "--title", $Title, "--notes", $Notes)
    if ($TargetBranch) {
      $createArgs += @("--target", $TargetBranch)
    }
    & $gh @createArgs | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el release $Tag." }
  }
  Write-Info "Subiendo assets al release $Tag..."
  & $gh release upload $Tag @Assets --repo $RepoSlug --clobber | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "No se pudieron subir los assets al release $Tag." }
  Write-Ok "Release actualizado: $Tag"
}

$python = Get-PythonCommand
Write-Info "Python usado para build: $python"
Initialize-Tooling -PythonExe $python
Install-RequiredModule -PythonExe $python -module "PyInstaller"

$releaseCfg = Read-ReleaseConfig
$buildMeta = New-BuildVersion -cfg $releaseCfg
Write-BuildInfo -cfg $releaseCfg -buildMeta $buildMeta
$gitSync = Sync-GitReleaseState -Version $buildMeta.Version -Tag $buildMeta.Tag

$appName = [string]$releaseCfg.app_name
$repoSlug = "{0}/{1}" -f $releaseCfg.repo_owner, $releaseCfg.repo_name
$targetBranch = if ($gitSync) { [string]$gitSync.Branch } else { $null }
$distRoot = Join-Path $PSScriptRoot "dist"
$buildRoot = Join-Path $PSScriptRoot "build"
$assetsRoot = Join-Path $PSScriptRoot "artifacts"
$portableDir = Join-Path $distRoot $appName

Write-Info "Limpiando build/dist..."
Remove-Item -Recurse -Force $buildRoot, $distRoot, $assetsRoot -ErrorAction SilentlyContinue | Out-Null
New-Item -ItemType Directory -Force -Path $buildRoot, $distRoot, $assetsRoot | Out-Null

$entry = Join-Path $PSScriptRoot "run_app.py"
if (-not (Test-Path $entry)) { throw "No se encontrÃ³ run_app.py" }

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
if ($LASTEXITCODE -ne 0) { throw "PyInstaller terminÃ³ con cÃ³digo $LASTEXITCODE" }

if (-not (Test-Path (Join-Path $portableDir "$appName.exe"))) {
  throw "No se generÃ³ el ejecutable esperado en $portableDir"
}

Build-FacturionExecutable -PythonExe $python -PortableDir $portableDir -BuildRoot $buildRoot

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
  $iscc = Get-ISCCPath
  if (-not $iscc) {
    Write-Info "No se encontro Inno Setup (ISCC.exe). Se omitira la generacion del instalador."
  }
  else {
    $iss = New-InnoScript -AppName $appName -Version $buildMeta.Version -SourceDir $portableDir
    Write-Info "Compilando instalador con Inno Setup..."
    & $iscc $iss | Out-Host
    if ($LASTEXITCODE -ne 0) { throw "No se pudo generar el instalador." }
    $setupExe = Join-Path $distRoot "installer\${appName}-setup-$($buildMeta.Version).exe"
    if (-not (Test-Path $setupExe)) { throw "No se encontrÃ³ el setup generado." }
    Write-Ok "Setup generado: $setupExe"
  }
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
Write-Utf8File -Path $manifestPath -Content ($manifest | ConvertTo-Json -Depth 10)
Write-Ok "Manifest generado: $manifestPath"

$assets = @($portableZip, $buildZip, $distZip, $manifestPath)
if ($setupExe) { $assets += $setupExe }

if (-not $SkipPublish) {
  Publish-Release -RepoSlug $repoSlug -Tag $buildMeta.Tag -Title "$appName $($buildMeta.Version)" -Assets $assets -Notes $ReleaseNotes -TargetBranch $targetBranch
}

Write-Ok "Build completo: $($buildMeta.Version)"


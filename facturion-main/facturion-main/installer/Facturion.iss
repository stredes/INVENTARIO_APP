#define MyAppName "Facturion"
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#ifndef MyAppExeName
  #define MyAppExeName "Facturion.exe"
#endif
#ifndef MySourceDir
  #define MySourceDir "..\dist\release\app"
#endif
#ifndef MyOutputDir
  #define MyOutputDir "..\dist\release"
#endif

[Setup]
AppId={{B96E6B88-CF4A-4E2E-8D36-9B6A40E0F721}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppName}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableDirPage=yes
DisableProgramGroupPage=yes
OutputDir={#MyOutputDir}
OutputBaseFilename=Facturion-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}

[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"; GroupDescription: "Accesos directos:"

[Files]
Source: "{#MySourceDir}\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{autodesktop}\Facturion*.lnk"

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Iniciar {#MyAppName}"; Flags: nowait postinstall skipifsilent

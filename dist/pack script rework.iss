; Mouse Slip Installer (Improved & Clean Version)

#define MyAppName "Mouse Slip beta 4.1"
#define MyAppVersion "2.4.1"
#define MyAppPublisher "Akshay Jain"
#define MyAppURL "mailto:4791akshayjain@gmail.com"
#define MyAppExeName "main.exe"

[Setup]
AppId={{B2087E7A-D182-4128-B2BC-155FBA93B9B7}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Install for current user only (no admin required)
PrivilegesRequired=lowest
DefaultDirName={localappdata}\{#MyAppName}

; 64-bit support
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#MyAppExeName}

OutputDir=F:\
OutputBaseFilename=MouseSlip_beta_4_1
SetupIconFile=F:\pygame\pg2\dist\icon.ico

Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Icon"; Flags: unchecked

[Files]
Source: "F:\pygame\pg2\dist\main.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\pygame\pg2\dist\hart.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\pygame\pg2\dist\icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\pygame\pg2\dist\mrunner.png"; DestDir: "{app}"; Flags: ignoreversion
Source: "F:\pygame\pg2\dist\spider.png"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}";
Description: "Launch {#MyAppName}";
Flags: nowait postinstall skipifsilent

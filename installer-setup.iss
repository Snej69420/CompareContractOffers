[Setup]
; NOTE: The value of AppId uniquely identifies this application. 
; Do not use the same AppId value in installers for other applications.
AppId={{CE86C04C-2512-4C8E-A9FD-1DDDCD926822}
AppName=Offerte Vergelijker
AppVersion=1.0.0
; This displays your name in the "Add/Remove Programs" list
AppPublisher=Jens Vissenberg
DefaultDirName={autopf}\Offerte Vergelijker
DefaultGroupName=Offerte Vergelijker
UninstallDisplayIcon={app}\Offertevergelijker.exe
Compression=lzma/max
SolidCompression=yes
; This is where the setup.exe will be saved
OutputDir=Output
OutputBaseFilename=Offerte-Vergelijker-Setup
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 1. The main executable
Source: "dist\Offertevergelijker\Offertevergelijker.exe"; DestDir: "{app}"; Flags: ignoreversion
; 2. CRITICAL: Include all other files in the folder (dependencies, dlls, etc)
Source: "dist\Offertevergelijker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
; Creates the shortcut in the Start Menu
Name: "{group}\Offerte Vergelijker"; Filename: "{app}\Offertevergelijker.exe"
; Creates the shortcut on the Desktop (if the user checked the box)
Name: "{autodesktop}\Offerte Vergelijker"; Filename: "{app}\Offertevergelijker.exe"; Tasks: desktopicon

[Run]
; Option to run the app immediately after installation finishes
Filename: "{app}\Offertevergelijker.exe"; Description: "{cm:LaunchProgram,Offerte Vergelijker}"; Flags: nowait postinstall skipifsilent

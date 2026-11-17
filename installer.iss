; Inno Setup 6 (https://jrsoftware.org/isinfo.php) — встановлення для поточного користувача, без прав адміністратора.
; Збірка:  iscc installer.iss   (build.bat робить це сам, якщо Inno Setup встановлено)

#define AppName "Attack Shark Battery"
#define AppExe  "AttackSharkBattery.exe"
#ifndef AppVer
  #define AppVer "1.1.0"
#endif

[Setup]
AppId={{6E1B7C2A-4F3D-4B8E-9A55-A7D0C1E5B2F1}
AppName={#AppName}
AppVersion={#AppVer}
AppPublisher=Attack Shark Battery
DefaultDirName={localappdata}\Programs\AttackSharkBattery
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=AttackSharkBattery-Setup
SetupIconFile=app.ico
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "autostart"; Description: "Запускати разом із Windows"; GroupDescription: "Додатково:"
Name: "desktopicon"; Description: "Ярлик на робочому столі"; GroupDescription: "Додатково:"; Flags: unchecked

[Files]
Source: "dist\AttackSharkBattery\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; шаблон конфігу (build.bat кладе його в dist\AttackSharkBattery\config.default.json);
; при першому запуску копіюється в %APPDATA%\AttackSharkBattery\config.json

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "AttackSharkBattery"; ValueData: """{app}\{#AppExe}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустити {#AppName}"; Flags: nowait postinstall skipifsilent
; після тихого оновлення (з самої програми) запускаємо нову версію автоматично
Filename: "{app}\{#AppExe}"; Flags: nowait; Check: WizardSilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM {#AppExe}"; Flags: runhidden; RunOnceId: "KillApp"

[UninstallDelete]
; дані користувача (%APPDATA%\AttackSharkBattery: конфіг, історія, лог) НЕ видаляються
Type: filesandordirs; Name: "{app}"

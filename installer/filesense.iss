; Instalador do FileSense (Inno Setup 6). Compile com: ISCC.exe installer\filesense.iss
; Gera installer\Output\FileSense-Setup.exe

[Setup]
AppName=FileSense
AppVersion=1.0.0
AppPublisher=FileSense
DefaultDirName={autopf}\FileSense
DefaultGroupName=FileSense
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=FileSense-Setup
SetupIconFile=..\icon.ico
UninstallDisplayIcon={app}\FileSense.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ShowLanguageDialog=no
LanguageDetectionMethod=none

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; Flags: unchecked
Name: "startup"; Description: "Abrir o FileSense ao ligar o computador"; Flags: unchecked

[Files]
Source: "..\dist\FileSense.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FileSense"; Filename: "{app}\FileSense.exe"
Name: "{group}\Desinstalar FileSense"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FileSense"; Filename: "{app}\FileSense.exe"; Tasks: desktopicon
Name: "{userstartup}\FileSense"; Filename: "{app}\FileSense.exe"; Tasks: startup

[Run]
Filename: "{app}\FileSense.exe"; Description: "Abrir o FileSense agora"; Flags: nowait postinstall skipifsilent

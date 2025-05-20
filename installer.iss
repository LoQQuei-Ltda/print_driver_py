; Script para o Inno Setup
#define MyAppName "Sistema de Gerenciamento de Impressão"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "LoQQuei"
#define MyAppURL "https://loqquei.com.br"
#define MyAppExeName "PrintManagementSystem.exe"

[Setup]
; Identificadores de aplicação
AppId={{95AFCE9F-6E8E-4B74-B736-CF95DF76D9C0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
OutputDir=Output
OutputBaseFilename=Instalador_Gerenciamento_LoQQuei_V{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
LZMAUseSeparateProcess=yes
LZMADictionarySize=1048576
LZMANumFastBytes=273
WizardStyle=modern
SetupLogging=yes

; Configurações para instalar sempre para todos os usuários
DefaultDirName={commonpf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AlwaysRestart=no

; Sempre requer privilégios de administrador (instalação para todos os usuários)
PrivilegesRequired=admin

; Configurações de UI
SetupIconFile=src\ui\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
; Removido a opção de iniciar automaticamente pois será obrigatório

[Files]
; Adicione o executável principal e outros arquivos
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\ui\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Cria atalhos no menu iniciar e área de trabalho
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{commonprograms}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"

[Run]
; Opção para iniciar o aplicativo após a instalação
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Adiciona chave de registro para garantir que o aplicativo inicie com o Windows
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue
; Script para o Inno Setup
#define MyAppName "Gerenciamento de Impressão - LoQQuei"
#define MyAppVersion "2.0.3"
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

; Instalação sem privilégios administrativos
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Diretório de instalação no perfil do usuário (não requer admin)
DefaultDirName={localappdata}\LoQQuei\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AlwaysRestart=no

; Configurações de UI
SetupIconFile=src\ui\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

; Versão mínima do Windows
MinVersion=6.1sp1

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1
Name: "startup"; Description: "Iniciar automaticamente com o Windows"; GroupDescription: "Configurações adicionais:"

[Files]
; SOLUÇÃO: Executável principal SEM verificação prévia - OBRIGATÓRIO
Source: "build\exe\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Recursos - INCLUÍDOS EXPLICITAMENTE
Source: "build\exe\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}"; Permissions: users-modify
Name: "{app}\logs"; Permissions: users-modify
Name: "{app}\config"; Permissions: users-modify
Name: "{app}\temp"; Permissions: users-modify
Name: "{app}\data"; Permissions: users-modify
Name: "{app}\cache"; Permissions: users-modify
Name: "{userappdata}\{#MyAppName}"; Permissions: users-modify
Name: "{userappdata}\{#MyAppName}\logs"; Permissions: users-modify
Name: "{userappdata}\{#MyAppName}\config"; Permissions: users-modify

[Icons]
; Atalhos do programa
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: quicklaunchicon
; Inicialização automática
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Registry]
; Registra configurações na área do usuário (não requer admin)
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
; Executa a aplicação após instalação SEM privilégios elevados
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
; Para o processo antes de desinstalar
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName}"; Flags: runhidden

[Code]
// Verifica se a aplicação está em execução
function IsAppRunning(): Boolean;
var
  ResultCode: Integer;
begin
  Exec('cmd.exe', '/C tasklist /FI "IMAGENAME eq {#MyAppExeName}" | find /I "{#MyAppExeName}"', 
       '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Result := (ResultCode = 0);
end;

// Para a aplicação se estiver em execução
procedure StopApplication();
var
  ResultCode: Integer;
begin
  if IsAppRunning() then
  begin
    Exec('cmd.exe', '/C taskkill /F /IM {#MyAppExeName}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1000); // Aguarda 1 segundo
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopApplication();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  Result := True;
  StopApplication();
end;
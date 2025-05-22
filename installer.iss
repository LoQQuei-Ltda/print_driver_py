; Script para o Inno Setup - VERSÃO CORRIGIDA (Apenas EXE)
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

; Configurações de instalação
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AlwaysRestart=no
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

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
; Executável principal (OBRIGATÓRIO - falha se não existir)
Source: "build\exe\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Recursos (ícones, etc) - apenas se existirem dentro do EXE
Source: "build\exe\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs skipifsourcedoesntexist

[Icons]
; Atalhos do programa
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon
; Inicialização automática
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Registry]
; Registro para inicialização automática (alternativa)
Root: HKCU; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
; Executa a aplicação após instalação
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Para o processo antes de desinstalar
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName}"; Flags: runhidden

[Code]
// Função para verificar se o executável foi criado corretamente
function InitializeSetup(): Boolean;
var
  ExePath: String;
begin
  Result := True;
  ExePath := ExpandConstant('{#SourcePath}\build\exe\{#MyAppExeName}');
  
  if not FileExists(ExePath) then
  begin
    MsgBox('ERRO: O executável não foi encontrado em:' + #13#10 + 
           ExePath + #13#10#13#10 +
           'Execute o script build_installer.py primeiro para criar o executável.', 
           mbError, MB_OK);
    Result := False;
  end;
end;

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

// Adiciona informações de versão no Painel de Controle
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Registra informações adicionais
    RegWriteStringValue(HKEY_LOCAL_MACHINE, 
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1',
      'DisplayVersion', '{#MyAppVersion}');
    RegWriteStringValue(HKEY_LOCAL_MACHINE, 
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1',
      'Publisher', '{#MyAppPublisher}');
    RegWriteStringValue(HKEY_LOCAL_MACHINE, 
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1',
      'URLInfoAbout', '{#MyAppURL}');
    RegWriteStringValue(HKEY_LOCAL_MACHINE, 
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1',
      'HelpLink', '{#MyAppURL}');
  end;
end;
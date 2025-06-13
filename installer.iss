; Script para o Inno Setup com Suporte Multi-usuário e Permissões de Impressora
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

DefaultDirName={autopf}\LoQQuei\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
AlwaysRestart=no
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

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
; Diretórios da aplicação com permissões completas para todos os usuários
Name: "{app}"; Permissions: everyone-modify users-modify
Name: "{app}\logs"; Permissions: everyone-modify users-modify
Name: "{app}\config"; Permissions: everyone-modify users-modify
Name: "{app}\temp"; Permissions: everyone-modify users-modify
Name: "{app}\data"; Permissions: everyone-modify users-modify
Name: "{app}\cache"; Permissions: everyone-modify users-modify

; Diretórios de usuário com permissões ampliaes
Name: "{userappdata}\{#MyAppName}"; Permissions: everyone-modify users-modify
Name: "{userappdata}\{#MyAppName}\logs"; Permissions: everyone-modify users-modify
Name: "{userappdata}\{#MyAppName}\config"; Permissions: everyone-modify users-modify

; Diretórios compartilhados para todos os usuários
Name: "{commonappdata}\{#MyAppName}"; Permissions: everyone-modify users-modify
Name: "{commonappdata}\{#MyAppName}\shared"; Permissions: everyone-modify users-modify
Name: "{commonappdata}\{#MyAppName}\printers"; Permissions: everyone-modify users-modify

[Icons]
; Atalhos do programa
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: quicklaunchicon
; Inicialização automática
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: startup

[Registry]
; === CONFIGURAÇÕES GLOBAIS PARA TODOS OS USUÁRIOS ===
; Registra configurações globais (HKEY_LOCAL_MACHINE)
Root: HKLM; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: dword; ValueName: "MultiUserSupport"; ValueData: 1; Flags: uninsdeletekey

; === PERMISSÕES ESPECIAIS PARA IMPRESSORAS ===
; Permite que todos os usuários gerenciem impressoras
Root: HKLM; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}\Permissions"; ValueType: dword; ValueName: "AllowPrinterManagement"; ValueData: 1; Flags: uninsdeletekey
Root: HKLM; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}\Permissions"; ValueType: dword; ValueName: "AllowAllUsers"; ValueData: 1; Flags: uninsdeletekey

; === CONFIGURAÇÕES DE SEGURANÇA PARA COMANDOS DE IMPRESSORA ===
; Registra o aplicativo como autorizado para operações de impressora
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System"; ValueType: string; ValueName: "EnableLUA"; ValueData: "0"; Flags: dontcreatekey
Root: HKLM; Subkey: "SOFTWARE\Policies\Microsoft\Windows\System"; ValueType: dword; ValueName: "EnableSmartScreen"; ValueData: 0; Flags: dontcreatekey

; === CONFIGURAÇÕES DO SPOOLER PARA MULTI-USUÁRIO ===
; Configurações do spooler para permitir operações de todos os usuários
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Print"; ValueType: dword; ValueName: "AllowPrintingToAllUsers"; ValueData: 1; Flags: dontcreatekey

; === CONFIGURAÇÕES DE USUÁRIO (aplicadas a todos) ===
; Configurações na área do usuário atual
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: dword; ValueName: "UserConfigured"; ValueData: 1; Flags: uninsdeletekey

; === CONFIGURAÇÕES PARA USUÁRIOS FUTUROS ===
; Configura para que novos usuários também tenham as permissões
Root: HKU; Subkey: ".DEFAULT\SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKU; Subkey: ".DEFAULT\SOFTWARE\{#MyAppPublisher}\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey

[Run]
; Executa a aplicação após instalação SEM privilégios elevados
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
; Para o processo antes de desinstalar
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM {#MyAppExeName}"; Flags: runhidden

; Remove impressoras virtuais antes de desinstalar
Filename: "powershell.exe"; Parameters: "-Command ""if (Get-Printer -Name 'Impressora LoQQuei' -ErrorAction SilentlyContinue) {{ Remove-Printer -Name 'Impressora LoQQuei' -ErrorAction SilentlyContinue }}"""; Flags: runhidden

[Code]
// ===== FUNÇÕES AUXILIARES =====

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

// Configura permissões avançadas de arquivo
procedure ConfigureAdvancedPermissions();
var
  ResultCode: Integer;
  AppDir: String;
begin
  AppDir := ExpandConstant('{app}');
  
  // Concede controle total para todos os usuários na pasta da aplicação
  Exec('icacls.exe', '"' + AppDir + '" /grant "Todos":(OI)(CI)F /T /Q', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('icacls.exe', '"' + AppDir + '" /grant "Everyone":(OI)(CI)F /T /Q', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('icacls.exe', '"' + AppDir + '" /grant "Users":(OI)(CI)F /T /Q', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('icacls.exe', '"' + AppDir + '" /grant "Usuários":(OI)(CI)F /T /Q', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  Log('Permissões avançadas configuradas para: ' + AppDir);
end;

// Configura permissões específicas para operações de impressora
procedure ConfigurePrinterPermissions();
var
  ResultCode: Integer;
begin
  // Adiciona o grupo de usuários aos operadores de impressão
  Exec('net.exe', 'localgroup "Print Operators" "Users" /add', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('net.exe', 'localgroup "Print Operators" "Todos" /add', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('net.exe', 'localgroup "Print Operators" "Everyone" /add', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Concede direitos de impressão para todos os usuários via política local
  Exec('powershell.exe', '-Command "& {try { $policy = Get-WmiObject -Class Win32_AccountSID | Where-Object {$_.SID -like ''*-513''}; if ($policy) { Write-Host ''Users group found'' } } catch { Write-Host ''Error configuring printer policies'' }}"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  Log('Permissões de impressora configuradas');
end;

// Remove impressoras virtuais existentes antes da instalação
procedure RemoveExistingVirtualPrinters();
var
  ResultCode: Integer;
begin
  Log('Removendo impressoras virtuais existentes...');
  
  // Remove via PowerShell
  Exec('powershell.exe', '-Command "Get-Printer | Where-Object {$_.Name -like ''*LoQQuei*''} | Remove-Printer -ErrorAction SilentlyContinue"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Remove via rundll32 (método alternativo)
  Exec('rundll32.exe', 'printui.dll,PrintUIEntry /dl /n "Impressora LoQQuei"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Remove portas TCP/IP relacionadas
  Exec('powershell.exe', '-Command "Get-PrinterPort | Where-Object {$_.Name -like ''*LoQQuei*'' -or $_.PrinterHostAddress -like ''127.0.0.1''} | Remove-PrinterPort -ErrorAction SilentlyContinue"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  Sleep(2000); // Aguarda para garantir que as operações foram concluídas
  Log('Limpeza de impressoras concluída');
end;

// Configura políticas de segurança para permitir operações de impressora
procedure ConfigureSecurityPolicies();
var
  ResultCode: Integer;
begin
  // Habilita a política "Permitir que usuários instalem drivers de impressora"
  Exec('reg.exe', 'add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v RestrictDriverInstallationToAdministrators /t REG_DWORD /d 0 /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Habilita Point and Print para todos os usuários
  Exec('reg.exe', 'add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v TrustedServers /t REG_DWORD /d 1 /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('reg.exe', 'add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v ServerList /t REG_SZ /d "127.0.0.1;localhost" /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  // Permite instalação de drivers sem elevação
  Exec('reg.exe', 'add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v NoWarningNoElevationOnInstall /t REG_DWORD /d 1 /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Exec('reg.exe', 'add "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Printers\PointAndPrint" /v NoWarningNoElevationOnUpdate /t REG_DWORD /d 1 /f', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  
  Log('Políticas de segurança de impressora configuradas');
end;

// Reinicia o serviço de spooler
procedure RestartSpoolerService();
var
  ResultCode: Integer;
begin
  Log('Reiniciando serviço de spooler...');
  
  Exec('net.exe', 'stop spooler', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(2000);
  Exec('net.exe', 'start spooler', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  Sleep(2000);
  
  Log('Serviço de spooler reiniciado');
end;

// Função chamada antes da instalação
function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  Log('=== INICIANDO PREPARAÇÃO PARA INSTALAÇÃO ===');
  
  // Para a aplicação se estiver rodando
  StopApplication();
  
  // Remove impressoras virtuais existentes para evitar duplicação
  RemoveExistingVirtualPrinters();
  
  Log('=== PREPARAÇÃO CONCLUÍDA ===');
end;

// Função chamada antes da desinstalação
function InitializeUninstall(): Boolean;
begin
  Result := True;
  Log('=== INICIANDO DESINSTALAÇÃO ===');
  
  // Para a aplicação
  StopApplication();
  
  // Remove impressoras virtuais
  RemoveExistingVirtualPrinters();
  
  Log('=== PREPARAÇÃO PARA DESINSTALAÇÃO CONCLUÍDA ===');
end;

// Função principal chamada durante a instalação
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    Log('=== INICIANDO CONFIGURAÇÕES PÓS-INSTALAÇÃO ===');
    
    // 1. Configurar permissões avançadas de arquivo
    ConfigureAdvancedPermissions();
    
    // 2. Configurar permissões específicas para operações de impressora
    ConfigurePrinterPermissions();
    
    // 3. Configurar políticas de segurança
    ConfigureSecurityPolicies();
    
    // 4. Registrar informações adicionais no sistema
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
    
    // 5. Adicionar informações sobre multi-usuário
    RegWriteStringValue(HKEY_LOCAL_MACHINE, 
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1',
      'Comments', 'Sistema de gerenciamento de impressão com suporte multi-usuário');
    RegWriteDWordValue(HKEY_LOCAL_MACHINE, 
      'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1',
      'NoModify', 1);
    
    // 6. Reiniciar o serviço de spooler para aplicar mudanças
    RestartSpoolerService();
    
    Log('=== CONFIGURAÇÕES PÓS-INSTALAÇÃO CONCLUÍDAS ===');
  end;
end;

// Função chamada ao finalizar a instalação
procedure DeinitializeSetup();
begin
  Log('=== INSTALAÇÃO CONCLUÍDA ===');
  Log('Sistema configurado para suporte multi-usuário');
  Log('Todos os usuários agora podem gerenciar impressoras virtuais');
end;
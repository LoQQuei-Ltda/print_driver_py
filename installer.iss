; Script para o Inno Setup - Com instalação automática do Python
#define MyAppName "Sistema de Gerenciamento de Impressão"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "LoQQuei"
#define MyAppURL "https://loqquei.com.br"
#define MyAppExeName "PrintManagementSystem.exe"
#define PythonVersion "3.11.9"
#define PythonInstallerURL "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
#define PythonInstallerFile "python-3.11.9-amd64.exe"

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

; Sempre requer privilégios de administrador
PrivilegesRequired=admin

; Configurações de UI
SetupIconFile=src\ui\resources\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Executável principal (se existir - PyInstaller standalone)
Source: "build\exe\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion; Check: FileExists('build\exe\{#MyAppExeName}')
; Arquivos Python originais (sempre incluir como fallback)
Source: "main.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "src\*"; DestDir: "{app}\src"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
; Recursos da aplicação
Source: "src\ui\resources\*"; DestDir: "{app}\resources"; Flags: ignoreversion recursesubdirs createallsubdirs
; Scripts auxiliares
Source: "scripts\install_dependencies_silent.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion
Source: "scripts\run_app.bat"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
; Atalhos (usa executável se existir, senão usa script)
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Check: FileExists(ExpandConstant('{app}\{#MyAppExeName}'))
Name: "{commonprograms}\{#MyAppName}"; Filename: "{app}\scripts\run_app.bat"; Check: not FileExists(ExpandConstant('{app}\{#MyAppExeName}'))
Name: "{commonprograms}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Check: FileExists(ExpandConstant('{app}\{#MyAppExeName}'))
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\scripts\run_app.bat"; Tasks: desktopicon; Check: not FileExists(ExpandConstant('{app}\{#MyAppExeName}'))
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Check: FileExists(ExpandConstant('{app}\{#MyAppExeName}'))
Name: "{commonstartup}\{#MyAppName}"; Filename: "{app}\scripts\run_app.bat"; Check: not FileExists(ExpandConstant('{app}\{#MyAppExeName}'))

[Code]
var
  PythonPath: string;
  DownloadPage: TDownloadWizardPage;

function IsPythonInstalled(): Boolean;
var
  ResultCode: Integer;
begin
  Result := False;
  
  // Tenta executar python diretamente
  if Exec('cmd.exe', '/c python --version', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) and (ResultCode = 0) then
  begin
    Result := True;
    Exit;
  end;
  
  // Verifica Python no registro
  if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.11\InstallPath', '', PythonPath) then
    Result := FileExists(PythonPath + 'python.exe')
  else if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.10\InstallPath', '', PythonPath) then
    Result := FileExists(PythonPath + 'python.exe')
  else if RegQueryStringValue(HKEY_LOCAL_MACHINE, 'SOFTWARE\Python\PythonCore\3.9\InstallPath', '', PythonPath) then
    Result := FileExists(PythonPath + 'python.exe')
  else if RegQueryStringValue(HKEY_CURRENT_USER, 'SOFTWARE\Python\PythonCore\3.11\InstallPath', '', PythonPath) then
    Result := FileExists(PythonPath + 'python.exe')
  else if RegQueryStringValue(HKEY_CURRENT_USER, 'SOFTWARE\Python\PythonCore\3.10\InstallPath', '', PythonPath) then
    Result := FileExists(PythonPath + 'python.exe')
  else if RegQueryStringValue(HKEY_CURRENT_USER, 'SOFTWARE\Python\PythonCore\3.9\InstallPath', '', PythonPath) then
    Result := FileExists(PythonPath + 'python.exe');
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(SetupMessage(msgWizardPreparing), SetupMessage(msgPreparingDesc), nil);
end;

function OnDownloadProgress(const Url, FileName: String; const Progress, ProgressMax: Int64): Boolean;
begin
  if ProgressMax <> 0 then
    Log(Format('Progresso: %d de %d bytes', [Progress, ProgressMax]));
  Result := True;
end;

function InstallPython(): Boolean;
var
  ResultCode: Integer;
  PythonInstaller: string;
begin
  Result := False;
  PythonInstaller := ExpandConstant('{tmp}\{#PythonInstallerFile}');
  
  // Download do Python usando a página de download integrada
  DownloadPage.Clear;
  DownloadPage.Add('{#PythonInstallerURL}', '{#PythonInstallerFile}', '');
  DownloadPage.Show;
  
  try
    DownloadPage.Download;
    Result := True;
  except
    Log('Erro no download do Python');
    Result := False;
  finally
    DownloadPage.Hide;
  end;
  
  if Result and FileExists(PythonInstaller) then
  begin
    // Instala o Python silenciosamente
    if Exec(PythonInstaller, '/quiet InstallAllUsers=1 PrependPath=1 Include_test=0', '', 
            SW_SHOW, ewWaitUntilTerminated, ResultCode) then
    begin
      Result := (ResultCode = 0);
      if not Result then
        Log(Format('Instalação do Python retornou código: %d', [ResultCode]));
    end
    else
    begin
      Log('Falha ao executar instalador do Python');
      Result := False;
    end;
  end;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  
  if CurPageID = wpReady then
  begin
    if not IsPythonInstalled() then
    begin
      if MsgBox('Python não foi encontrado no sistema. Deseja instalar o Python {#PythonVersion} automaticamente?', 
                mbConfirmation, MB_YESNO) = IDYES then
      begin
        Result := InstallPython();
        if not Result then
          MsgBox('Não foi possível instalar o Python. Por favor, instale manualmente e execute o instalador novamente.', mbError, MB_OK);
      end
      else
      begin
        MsgBox('A instalação será continuada, mas a aplicação pode não funcionar corretamente sem o Python.', mbInformation, MB_OK);
      end;
    end;
  end;
end;

procedure InstallDependencies();
var
  ResultCode: Integer;
  AppPath: string;
begin
  AppPath := ExpandConstant('{app}');
  
  // Atualiza o status na janela de progresso
  WizardForm.StatusLabel.Caption := 'Instalando dependências Python...';
  WizardForm.ProgressGauge.Style := npbstMarquee;
  
  try
    // Executa o script silencioso de instalação
    if Exec('cmd.exe', '/c "' + AppPath + '\scripts\install_dependencies_silent.bat"', 
            AppPath, SW_HIDE, ewWaitUntilTerminated, ResultCode) then
    begin
      if ResultCode <> 0 then
        Log(Format('Script de dependências retornou código: %d', [ResultCode]));
    end
    else
    begin
      Log('Falha ao executar script de dependências');
    end;
  finally
    WizardForm.ProgressGauge.Style := npbstNormal;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    if IsPythonInstalled() then
    begin
      InstallDependencies();
    end
    else
    begin
      Log('Python não encontrado, pulando instalação de dependências');
    end;
  end;
end;

[Run]
; Executa a aplicação após instalação (usa executável se existir, senão usa script)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent; Check: FileExists(ExpandConstant('{app}\{#MyAppExeName}'))

[Registry]
; Registro para inicialização automática (usa executável se existir, senão usa script)
Root: HKLM; Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Check: FileExists(ExpandConstant('{app}\{#MyAppExeName}'))
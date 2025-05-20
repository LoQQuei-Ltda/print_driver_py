import os
import sys
import subprocess
import time
import tempfile
import ctypes
import shutil
import urllib.request
import winreg
from pathlib import Path

def is_admin():
    """Verifica se o script está sendo executado como administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False

def ensure_output_dir():
    """Garante que o diretório de saída exista e tenha permissões."""
    pdf_dir = Path("C:/pdfs")
    if not pdf_dir.exists():
        pdf_dir.mkdir(parents=True)
    
    # Configura permissões totais na pasta
    try:
        subprocess.run(["icacls", str(pdf_dir), "/grant", "Everyone:(OI)(CI)F"], 
                     capture_output=True, check=False)
        subprocess.run(["icacls", str(pdf_dir), "/grant", "SYSTEM:(OI)(CI)F"], 
                     capture_output=True, check=False)
        subprocess.run(["icacls", str(pdf_dir), "/grant", "Administrators:(OI)(CI)F"], 
                     capture_output=True, check=False)
    except Exception as e:
        print(f"Aviso: Não foi possível configurar permissões: {str(e)}")
    
    return str(pdf_dir)

def restart_spooler():
    """Reinicia o serviço de spooler de impressão"""
    print("Reiniciando serviço de spooler de impressão...")
    try:
        subprocess.run(["net", "stop", "spooler"], capture_output=True, check=False)
        time.sleep(2)
        
        # Limpa arquivos temporários de impressão
        spool_path = os.path.join(os.environ["SystemRoot"], "System32", "spool", "PRINTERS")
        try:
            for file in os.listdir(spool_path):
                file_path = os.path.join(spool_path, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception:
                    pass
        except Exception:
            pass
            
        subprocess.run(["net", "start", "spooler"], capture_output=True, check=False)
        time.sleep(2)
    except Exception as e:
        print(f"Erro ao reiniciar o spooler: {str(e)}")

def download_file(url, destination):
    """Faz o download de um arquivo."""
    try:
        print(f"Baixando {url}...")
        # Tenta com urllib
        urllib.request.urlretrieve(url, destination)
        return True
    except Exception as e:
        print(f"Erro ao baixar arquivo com urllib: {e}")
        
        # Se falhar, tenta com PowerShell
        try:
            cmd = f'powershell -Command "& {{[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri \'{url}\' -OutFile \'{destination}\'}}"'
            subprocess.run(cmd, shell=True, check=True)
            return True
        except Exception as e2:
            print(f"Erro ao baixar arquivo com PowerShell: {e2}")
            return False

def install_bullzip():
    """Instala o Bullzip PDF Printer."""
    pdf_dir = ensure_output_dir()
    
    # URL para o instalador do Bullzip
    bullzip_url = "https://dl.bullzip.com/download/BullzipPdfPrinter_13_2_0_2924.exe"
    installer = os.path.join(tempfile.gettempdir(), "bullzip_installer.exe")
    
    # Baixa o instalador
    if not download_file(bullzip_url, installer):
        print("Erro ao baixar Bullzip PDF Printer. Tentar método alternativo.")
        return False
    
    # Prepara arquivo de configuração para instalação silenciosa
    ini_file = os.path.join(tempfile.gettempdir(), "bullzip_setup.ini")
    
    ini_content = f"""[Setup]
Bits=x64
TargetDirBits=%ProgramFiles%\\Bullzip\\PDF Printer
LicenseFile=
InstallType=typical
TARGETDIR=%ProgramFiles%\\Bullzip\\PDF Printer
INSTALLLEVEL=100
ShellIntegration=Yes
SetAsDefaultPrinter=No
Shortcuts=No
RUNPROGRAM=No
SILENT=Yes
PrinterName=PDF Printer Virtual
READMECHECK=No
PDFPATH={pdf_dir}
AUTOPRINT=No
AUTOPDF=Yes
AUTOSTARTPRINT=No
SHOWSETTINGS=No
SHOWPDF=No
"""
    
    with open(ini_file, 'w') as f:
        f.write(ini_content)
    
    # Instala o Bullzip PDF Printer
    print("Instalando Bullzip PDF Printer (isso pode levar alguns minutos)...")
    cmd = f'"{installer}" /LOADINF="{ini_file}" /SILENT /NORESTART'
    
    try:
        subprocess.run(cmd, shell=True, check=True)
        print("Bullzip PDF Printer instalado com sucesso.")
        return True
    except Exception as e:
        print(f"Erro ao instalar Bullzip PDF Printer: {e}")
        return False

def configure_bullzip_registry(pdf_dir):
    """Configura o Bullzip PDF Printer via registro do Windows para garantir que funcione corretamente."""
    print("Configurando o Bullzip PDF Printer via registro do Windows...")
    
    try:
        # Define as configurações no registro
        # 1. Configurações globais para todos os usuários
        reg_cmd = f'''
# Configura Bullzip para todos os usuários
$regkeys = @(
    "HKLM:\\SOFTWARE\\Wow6432Node\\Bullzip\\PDF Printer",
    "HKLM:\\SOFTWARE\\Bullzip\\PDF Printer"
)

foreach ($regkey in $regkeys) {{
    if (Test-Path $regkey) {{
        # Configurações principais
        New-ItemProperty -Path "$regkey" -Name "OutputFormat" -Value "PDF" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "OutputDirectory" -Value "{pdf_dir}" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "FilenameFormat" -Value "Impressao_%Y%m%d_%H%M%S.pdf" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "ConfirmOverwrite" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "OpenViewer" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "ShowSettings" -Value "Never" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "ShowProgress" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "ShowProgressFinish" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "RememberLastFolders" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "RememberLastFormat" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "SavePasswordsRegistry" -Value "No" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "PromptForFilename" -Value "Never" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "PromptForProperties" -Value "Never" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "AutoSaveEnabled" -Value "Yes" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "AutoSaveDirectory" -Value "{pdf_dir}" -PropertyType String -Force | Out-Null
        New-ItemProperty -Path "$regkey" -Name "AutoSaveFilename" -Value "Impressao_%Y%m%d_%H%M%S.pdf" -PropertyType String -Force | Out-Null
    }}
}}

# Configurações específicas para o usuário atual
$regkeys = @(
    "HKCU:\\Software\\Bullzip\\PDF Printer",
    "HKCU:\\Software\\Wow6432Node\\Bullzip\\PDF Printer"
)

foreach ($regkey in $regkeys) {{
    if (!(Test-Path $regkey)) {{
        New-Item -Path $regkey -Force | Out-Null
    }}
    
    # Configurações principais
    New-ItemProperty -Path "$regkey" -Name "OutputFormat" -Value "PDF" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "OutputDirectory" -Value "{pdf_dir}" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "FilenameFormat" -Value "Impressao_%Y%m%d_%H%M%S.pdf" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ConfirmOverwrite" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "OpenViewer" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ShowSettings" -Value "Never" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ShowProgress" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ShowProgressFinish" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "PromptForFilename" -Value "Never" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "PromptForProperties" -Value "Never" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "RunProgramAfterSaving" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "RunProgramBeforeSaving" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "AutoSaveEnabled" -Value "Yes" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "AutoSaveDirectory" -Value "{pdf_dir}" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "AutoSaveFilename" -Value "Impressao_%Y%m%d_%H%M%S.pdf" -PropertyType String -Force | Out-Null
}}

# Configurações específicas por impressora 
$regkeys = @(
    "HKCU:\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual",
    "HKLM:\\SOFTWARE\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual",
    "HKLM:\\SOFTWARE\\Wow6432Node\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual"
)

foreach ($regkey in $regkeys) {{
    if (!(Test-Path $regkey)) {{
        New-Item -Path $regkey -Force | Out-Null
    }}
    
    # Configurações específicas da impressora
    New-ItemProperty -Path "$regkey" -Name "OutputFormat" -Value "PDF" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "OutputDirectory" -Value "{pdf_dir}" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "FilenameFormat" -Value "Impressao_%Y%m%d_%H%M%S.pdf" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ConfirmOverwrite" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "OpenViewer" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ShowSettings" -Value "Never" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ShowProgress" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "ShowProgressFinish" -Value "No" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "PromptForFilename" -Value "Never" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "PromptForProperties" -Value "Never" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "AutoSaveEnabled" -Value "Yes" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "AutoSaveDirectory" -Value "{pdf_dir}" -PropertyType String -Force | Out-Null
    New-ItemProperty -Path "$regkey" -Name "AutoSaveFilename" -Value "Impressao_%Y%m%d_%H%M%S.pdf" -PropertyType String -Force | Out-Null
}}

# Configurações de preferências do usuário
$regkey = "HKCU:\\Software\\Bullzip\\PDF Printer\\UserPrefs"
if (!(Test-Path $regkey)) {{
    New-Item -Path $regkey -Force | Out-Null
}}
New-ItemProperty -Path "$regkey" -Name "PromptForFileName" -Value "Never" -PropertyType String -Force | Out-Null
New-ItemProperty -Path "$regkey" -Name "ShowProgress" -Value "No" -PropertyType String -Force | Out-Null
'''
        
        subprocess.run(["powershell", "-Command", reg_cmd], 
                      capture_output=True, check=False)
        
        # Cria arquivo de configuração global
        global_config_dir = os.path.expandvars("%ProgramFiles%\\Bullzip\\PDF Printer")
        os.makedirs(global_config_dir, exist_ok=True)
        
        global_config_file = os.path.join(global_config_dir, "settings.ini")
        
        global_config_content = f"""[PDF Settings]
OutputFormat=PDF
OutputDirectory={pdf_dir}
FilenameFormat=Impressao_%Y%m%d_%H%M%S.pdf
ConfirmOverwrite=No
OpenViewer=No
ShowSettings=Never
ShowProgress=No
ShowProgressFinish=No
PromptForFilename=Never
PromptForProperties=Never
AutoSaveEnabled=Yes
AutoSaveDirectory={pdf_dir}
AutoSaveFilename=Impressao_%Y%m%d_%H%M%S.pdf
"""
        
        with open(global_config_file, 'w') as f:
            f.write(global_config_content)
        
        # Cria arquivo de configuração de usuário
        user_config_dir = os.path.expandvars("%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer")
        os.makedirs(user_config_dir, exist_ok=True)
        
        user_config_file = os.path.join(user_config_dir, "pdfprinter.ini")
        
        user_config_content = f"""[PDF Printer Virtual]
OutputFormat=PDF
OutputDirectory={pdf_dir}
FilenameFormat=Impressao_%Y%m%d_%H%M%S.pdf
ConfirmOverwrite=No
OpenViewer=No
ShowSettings=Never
ShowProgress=No
ShowProgressFinish=No
PromptForFilename=Never
PromptForProperties=Never
AutoSaveEnabled=Yes
AutoSaveDirectory={pdf_dir}
AutoSaveFilename=Impressao_%Y%m%d_%H%M%S.pdf
"""
        
        with open(user_config_file, 'w') as f:
            f.write(user_config_content)
        
        # Configura o arquivo como padrão no registro
        conf_cmd = f'reg add "HKCU\\Software\\Bullzip\\PDF Printer\\UserPrefs" /v "UserConfig" /t REG_SZ /d "{user_config_file}" /f'
        subprocess.run(conf_cmd, shell=True, check=False)
        
        print("Configuração do Bullzip finalizada.")
        
        return True
    except Exception as e:
        print(f"Erro ao configurar Bullzip via registro: {e}")
        return False

def create_test_script():
    """Cria um script batch para testar a impressora."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    test_script = os.path.join(script_dir, "testar_impressora.bat")
    
    script_content = '''@echo off
echo Criando arquivo de teste...
echo Este é um teste da impressora virtual PDF. > "%TEMP%\\teste_impressao.txt"
echo Se este arquivo for impresso corretamente, você verá um PDF em C:\\pdfs >> "%TEMP%\\teste_impressao.txt"
echo Data/hora: %date% %time% >> "%TEMP%\\teste_impressao.txt"

echo Imprimindo arquivo de teste...
print /d:"PDF Printer Virtual" "%TEMP%\\teste_impressao.txt"

echo.
echo Arquivo de teste enviado para a impressora.
echo Verifique se o arquivo PDF foi criado em C:\\pdfs
echo.

pause
'''
    
    with open(test_script, 'w') as f:
        f.write(script_content)
    
    print(f"Script de teste criado em: {test_script}")
    return test_script

def create_direct_install_script():
    """Cria um script batch para instalação direta."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    install_script = os.path.join(script_dir, "instalar_impressora_direta.bat")
    
    script_content = '''@echo off
echo Instalando impressora virtual PDF...

REM Verifica se está executando como administrador
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Este script precisa ser executado como administrador.
    echo Por favor, clique com o botão direito e selecione "Executar como administrador".
    pause
    exit /b 1
)

REM Cria diretório de destino
if not exist "C:\\pdfs" mkdir "C:\\pdfs"
icacls "C:\\pdfs" /grant Everyone:(OI)(CI)F
icacls "C:\\pdfs" /grant SYSTEM:(OI)(CI)F
icacls "C:\\pdfs" /grant Administrators:(OI)(CI)F

REM Reinicia o spooler de impressão
net stop spooler
timeout /t 2 /nobreak > NUL
echo Limpando arquivos temporários de impressão...
del /q /f %systemroot%\\System32\\spool\\PRINTERS\\*.*
net start spooler
timeout /t 2 /nobreak > NUL

REM Verifica se o Bullzip já está instalado e remove
echo Verificando instalação existente...
wmic product where "name like 'Bullzip PDF Printer%%'" call uninstall /nointeractive

REM Baixa e instala o Bullzip PDF Printer
echo Baixando Bullzip PDF Printer...
powershell -Command "& {[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://dl.bullzip.com/download/BullzipPdfPrinter_13_2_0_2924.exe' -OutFile '%TEMP%\\bullzip_installer.exe'}"

REM Cria arquivo de configuração
echo Criando arquivo de configuração...
echo [Setup] > "%TEMP%\\bullzip_setup.ini"
echo Bits=x64 >> "%TEMP%\\bullzip_setup.ini"
echo TargetDirBits=%%ProgramFiles%%\\Bullzip\\PDF Printer >> "%TEMP%\\bullzip_setup.ini"
echo LicenseFile= >> "%TEMP%\\bullzip_setup.ini"
echo InstallType=typical >> "%TEMP%\\bullzip_setup.ini"
echo TARGETDIR=%%ProgramFiles%%\\Bullzip\\PDF Printer >> "%TEMP%\\bullzip_setup.ini"
echo INSTALLLEVEL=100 >> "%TEMP%\\bullzip_setup.ini"
echo ShellIntegration=Yes >> "%TEMP%\\bullzip_setup.ini"
echo SetAsDefaultPrinter=No >> "%TEMP%\\bullzip_setup.ini"
echo Shortcuts=No >> "%TEMP%\\bullzip_setup.ini"
echo RUNPROGRAM=No >> "%TEMP%\\bullzip_setup.ini"
echo SILENT=Yes >> "%TEMP%\\bullzip_setup.ini"
echo PrinterName=PDF Printer Virtual >> "%TEMP%\\bullzip_setup.ini"
echo READMECHECK=No >> "%TEMP%\\bullzip_setup.ini"
echo PDFPATH=C:\\pdfs >> "%TEMP%\\bullzip_setup.ini"
echo AUTOPRINT=No >> "%TEMP%\\bullzip_setup.ini"
echo AUTOPDF=Yes >> "%TEMP%\\bullzip_setup.ini"
echo AUTOSTARTPRINT=No >> "%TEMP%\\bullzip_setup.ini"
echo SHOWSETTINGS=No >> "%TEMP%\\bullzip_setup.ini"
echo SHOWPDF=No >> "%TEMP%\\bullzip_setup.ini"

REM Instala o Bullzip
echo Instalando Bullzip PDF Printer (isso pode levar alguns minutos)...
"%TEMP%\\bullzip_installer.exe" /LOADINF="%TEMP%\\bullzip_setup.ini" /SILENT /NORESTART

REM Aguarda a instalação
timeout /t 10 /nobreak > NUL

REM Configura o diretório global
if not exist "%ProgramFiles%\\Bullzip\\PDF Printer" mkdir "%ProgramFiles%\\Bullzip\\PDF Printer"

echo [PDF Settings] > "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo OutputFormat=PDF >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo OutputDirectory=C:\\pdfs >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo FilenameFormat=Impressao_%%Y%%m%%d_%%H%%M%%S.pdf >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo ConfirmOverwrite=No >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo OpenViewer=No >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo ShowSettings=Never >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo ShowProgress=No >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo ShowProgressFinish=No >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo PromptForFilename=Never >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo PromptForProperties=Never >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo AutoSaveEnabled=Yes >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo AutoSaveDirectory=C:\\pdfs >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"
echo AutoSaveFilename=Impressao_%%Y%%m%%d_%%H%%M%%S.pdf >> "%ProgramFiles%\\Bullzip\\PDF Printer\\settings.ini"

REM Configura o diretório de usuário
if not exist "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer" mkdir "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer"

echo [PDF Printer Virtual] > "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo OutputFormat=PDF >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo OutputDirectory=C:\\pdfs >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo FilenameFormat=Impressao_%%Y%%m%%d_%%H%%M%%S.pdf >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo ConfirmOverwrite=No >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo OpenViewer=No >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo ShowSettings=Never >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo ShowProgress=No >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo ShowProgressFinish=No >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo PromptForFilename=Never >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo PromptForProperties=Never >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo AutoSaveEnabled=Yes >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo AutoSaveDirectory=C:\\pdfs >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"
echo AutoSaveFilename=Impressao_%%Y%%m%%d_%%H%%M%%S.pdf >> "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini"

REM Configura o registro para todos os usuários
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "OutputFormat" /t REG_SZ /d "PDF" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "OutputDirectory" /t REG_SZ /d "C:\\pdfs" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "FilenameFormat" /t REG_SZ /d "Impressao_%%Y%%m%%d_%%H%%M%%S.pdf" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "ConfirmOverwrite" /t REG_SZ /d "No" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "OpenViewer" /t REG_SZ /d "No" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "ShowSettings" /t REG_SZ /d "Never" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "ShowProgress" /t REG_SZ /d "No" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "ShowProgressFinish" /t REG_SZ /d "No" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "PromptForFilename" /t REG_SZ /d "Never" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "PromptForProperties" /t REG_SZ /d "Never" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "AutoSaveEnabled" /t REG_SZ /d "Yes" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "AutoSaveDirectory" /t REG_SZ /d "C:\\pdfs" /f
reg add "HKLM\\SOFTWARE\\Bullzip\\PDF Printer" /v "AutoSaveFilename" /t REG_SZ /d "Impressao_%%Y%%m%%d_%%H%%M%%S.pdf" /f

REM Configura o registro para o usuário atual
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "OutputFormat" /t REG_SZ /d "PDF" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "OutputDirectory" /t REG_SZ /d "C:\\pdfs" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "FilenameFormat" /t REG_SZ /d "Impressao_%%Y%%m%%d_%%H%%M%%S.pdf" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "ConfirmOverwrite" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "OpenViewer" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "ShowSettings" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "ShowProgress" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "ShowProgressFinish" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "PromptForFilename" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "PromptForProperties" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "AutoSaveEnabled" /t REG_SZ /d "Yes" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "AutoSaveDirectory" /t REG_SZ /d "C:\\pdfs" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer" /v "AutoSaveFilename" /t REG_SZ /d "Impressao_%%Y%%m%%d_%%H%%M%%S.pdf" /f

REM Configura o registro para a impressora específica
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "OutputFormat" /t REG_SZ /d "PDF" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "OutputDirectory" /t REG_SZ /d "C:\\pdfs" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "FilenameFormat" /t REG_SZ /d "Impressao_%%Y%%m%%d_%%H%%M%%S.pdf" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "ConfirmOverwrite" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "OpenViewer" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "ShowSettings" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "ShowProgress" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "ShowProgressFinish" /t REG_SZ /d "No" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "PromptForFilename" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "PromptForProperties" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "AutoSaveEnabled" /t REG_SZ /d "Yes" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "AutoSaveDirectory" /t REG_SZ /d "C:\\pdfs" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\Printers\\PDF Printer Virtual" /v "AutoSaveFilename" /t REG_SZ /d "Impressao_%%Y%%m%%d_%%H%%M%%S.pdf" /f

REM Configura o arquivo como padrão no registro
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\UserPrefs" /v "UserConfig" /t REG_SZ /d "%USERPROFILE%\\AppData\\Roaming\\Bullzip\\PDF Printer\\pdfprinter.ini" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\UserPrefs" /v "PromptForFileName" /t REG_SZ /d "Never" /f
reg add "HKCU\\Software\\Bullzip\\PDF Printer\\UserPrefs" /v "ShowProgress" /t REG_SZ /d "No" /f

REM Cria um arquivo de teste
echo Este é um teste da impressora virtual PDF. > "C:\\pdfs\\teste_impressao.txt"

echo.
echo Instalação concluída! A impressora "PDF Printer Virtual" está instalada.
echo Os arquivos PDF serão salvos automaticamente em C:\\pdfs
echo Para testar, imprima o arquivo "C:\\pdfs\\teste_impressao.txt"
echo.

pause
'''
    
    with open(install_script, 'w') as f:
        f.write(script_content)
    
    print(f"Script de instalação direta criado em: {install_script}")
    return install_script

def remove_existing_bullzip():
    """Remove qualquer instalação existente do Bullzip para evitar problemas de configuração."""
    print("Removendo instalações existentes do Bullzip PDF Printer...")
    
    try:
        # Usa o WMI para remover o produto existente
        remove_cmd = '''
$products = Get-WmiObject -Class Win32_Product | Where-Object { $_.Name -like "Bullzip PDF Printer*" }
foreach ($product in $products) {
    Write-Host "Desinstalando: " $product.Name
    $product.Uninstall() | Out-Null
}
'''
        subprocess.run(["powershell", "-Command", remove_cmd], 
                      capture_output=True, check=False)
        
        # Aguarda a desinstalação
        time.sleep(5)
        
        return True
    except Exception as e:
        print(f"Aviso: Falha ao remover instalação existente: {e}")
        return False

def main():
    """Função principal."""
    print("Iniciando instalação da impressora virtual PDF...")
    
    # Verifica se está executando como administrador
    if not is_admin():
        print("Este script precisa ser executado como administrador.")
        print("Por favor, execute novamente com privilégios de administrador.")
        sys.exit(1)
    
    # Cria o diretório de saída
    pdf_dir = ensure_output_dir()
    
    # Reinicia o spooler para limpar qualquer impressora/porta problemática
    restart_spooler()
    
    # Cria o script de instalação direta (como backup)
    install_script = create_direct_install_script()
    
    # Remove instalações existentes
    remove_existing_bullzip()
    
    # Instala o Bullzip PDF Printer
    print("Instalando Bullzip PDF Printer...")
    if install_bullzip():
        # Configura o Bullzip PDF Printer via registro
        configure_bullzip_registry(pdf_dir)
        
        # Cria script de teste
        test_script = create_test_script()
        
        print("\n" + "="*80)
        print("Instalação concluída!")
        print("="*80)
        print("\nA impressora 'PDF Printer Virtual' foi instalada com sucesso.")
        print(f"Os arquivos PDF serão salvos automaticamente em {pdf_dir}")
        print("\nPara testar, execute o script:", test_script)
        print("\nSe ainda assim aparecer diálogos ou os arquivos não forem salvos,")
        print(f"execute o script de instalação direta: {install_script}")
    else:
        print("\nA instalação automática falhou.")
        print(f"Por favor, execute o script {install_script} manualmente.")
    
    print("\nDicas para resolução de problemas:")
    print("1. Se os diálogos continuarem aparecendo, reinicie o computador")
    print("2. Verifique se a pasta C:\\pdfs tem permissões de escrita")
    print("3. Para uma instalação limpa, execute:", install_script)

if __name__ == "__main__":
    main()
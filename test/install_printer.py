import os
import sys
import subprocess
import tempfile
import shutil
import winreg
import ctypes
import urllib.request
import zipfile
import platform
import time
from pathlib import Path

# Verificar se está rodando como administrador
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

# Função para baixar arquivos
def download_file(url, destination):
    try:
        # Criar objeto Request com User-Agent para evitar bloqueios
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        req = urllib.request.Request(url, headers=headers)
        
        # Baixar o arquivo
        with urllib.request.urlopen(req) as response, open(destination, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
        return True
    except Exception as e:
        print(f"Erro ao baixar arquivo: {e}")
        return False

# Função para instalar Ghostscript silenciosamente
def install_ghostscript():
    # Verificar arquitetura do sistema
    is_64bit = platform.machine().endswith('64')
    
    # URL para a versão mais recente do Ghostscript (10.02.0) - link oficial
    if is_64bit:
        gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10020/gs10020w64.exe"
    else:
        gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10020/gs10020w32.exe"
    
    # Baixar o instalador
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "ghostscript_installer.exe")
    
    print("Baixando Ghostscript...")
    if not download_file(gs_url, installer_path):
        print("Falha ao baixar Ghostscript. Abortando.")
        return False
    
    # Instalar silenciosamente
    print("Instalando Ghostscript...")
    try:
        subprocess.run([
            installer_path,
            "/S",  # Instalação silenciosa
            "/NCRC"  # Não verificar CRC
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Aguardar instalação concluir
        time.sleep(10)
        
        # Verificar se Ghostscript foi instalado corretamente
        try:
            # Verificar chave de registro para instalação
            reg_path = r"SOFTWARE\GPL Ghostscript"
                
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                return True
        except:
            # Tentar caminhos comuns de instalação
            potential_paths = [
                r"C:\Program Files\gs\gs10.02.0\bin\gswin64c.exe",
                r"C:\Program Files\gs\gs10.01.2\bin\gswin64c.exe",
                r"C:\Program Files\gs\gs10.00.0\bin\gswin64c.exe",
                r"C:\Program Files (x86)\gs\gs10.02.0\bin\gswin32c.exe",
                r"C:\Program Files (x86)\gs\gs10.01.2\bin\gswin32c.exe",
                r"C:\Program Files (x86)\gs\gs10.00.0\bin\gswin32c.exe"
            ]
            
            for path in potential_paths:
                if os.path.exists(path):
                    return True
            
            return False
            
    except Exception as e:
        print(f"Erro na instalação do Ghostscript: {e}")
        return False
    finally:
        # Limpar o instalador
        try:
            os.remove(installer_path)
        except:
            pass
    
    return True

# Encontrar o caminho do executável do Ghostscript
def find_ghostscript_path():
    gs_path = ""
    try:
        # Procurar nas chaves de registro do Ghostscript
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GPL Ghostscript") as key:
            # Obter a versão mais recente (último item na lista)
            versions = []
            i = 0
            while True:
                try:
                    version = winreg.EnumKey(key, i)
                    versions.append(version)
                    i += 1
                except WindowsError:
                    break
            
            if versions:
                # Ordenar versões e pegar a mais recente
                versions.sort(reverse=True)
                version = versions[0]
                
                with winreg.OpenKey(key, version) as verkey:
                    gs_install_dir = winreg.QueryValueEx(verkey, "GS_DLL")[0]
                    gs_install_dir = gs_install_dir.rsplit('\\', 1)[0]  # Remover o nome do arquivo .dll
                    
                    # Tentar encontrar o executável
                    if platform.machine().endswith('64'):
                        gs_path = os.path.join(gs_install_dir, "gswin64c.exe")
                    else:
                        gs_path = os.path.join(gs_install_dir, "gswin32c.exe")
    except:
        pass
    
    if not gs_path or not os.path.exists(gs_path):
        # Tentar caminhos padrão
        potential_paths = [
            r"C:\Program Files\gs\gs10.02.0\bin\gswin64c.exe",
            r"C:\Program Files\gs\gs10.01.2\bin\gswin64c.exe",
            r"C:\Program Files\gs\gs10.00.0\bin\gswin64c.exe",
            r"C:\Program Files (x86)\gs\gs10.02.0\bin\gswin32c.exe",
            r"C:\Program Files (x86)\gs\gs10.01.2\bin\gswin32c.exe",
            r"C:\Program Files (x86)\gs\gs10.00.0\bin\gswin32c.exe"
        ]
        
        for path in potential_paths:
            if os.path.exists(path):
                gs_path = path
                break
    
    return gs_path

# Criar um serviço Windows para monitorar a pasta de impressão
def create_print_monitor_service(install_dir, spool_folder, output_folder, gs_path):
    # Criar script de serviço para monitorar a pasta e converter PS para PDF
    monitor_script = f"""import os
import sys
import time
import shutil
import subprocess
import logging
import win32serviceutil
import win32service
import win32event
import servicemanager
import socket
from datetime import datetime

# Configuração do logger
def setup_logging():
    log_file = r'{install_dir}\\pdf_printer_service.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename=log_file,
        filemode='a'
    )
    return logging.getLogger('PDFPrinterService')

# Classe de serviço
class PDFPrinterService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PDFPrinterService"
    _svc_display_name_ = "PDF Printer Service"
    _svc_description_ = "Monitora arquivos de impressão e converte para PDF"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = False
        self.logger = setup_logging()

    def SvcStop(self):
        self.logger.info('Parando serviço...')
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)
        self.is_running = False

    def SvcDoRun(self):
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, '')
        )
        self.logger.info('Serviço iniciado')
        self.is_running = True
        self.main()

    def main(self):
        # Configurações
        spool_folder = r'{spool_folder}'
        output_folder = r'{output_folder}'
        gs_path = r'{gs_path}'
        
        # Criar pastas se não existirem
        os.makedirs(spool_folder, exist_ok=True)
        os.makedirs(output_folder, exist_ok=True)
        
        self.logger.info(f'Monitorando pasta: {{spool_folder}}')
        self.logger.info(f'Pasta de saída: {{output_folder}}')
        
        # Loop principal
        while self.is_running:
            try:
                # Verificar arquivos na pasta de spool
                files = [f for f in os.listdir(spool_folder) if f.endswith('.ps') or f.endswith('.prn')]
                
                for file in files:
                    try:
                        input_file = os.path.join(spool_folder, file)
                        
                        # Verificar se o arquivo está sendo usado
                        try:
                            with open(input_file, 'a'):
                                pass
                        except:
                            # Arquivo em uso, pular
                            continue
                        
                        # Gerar nome de saída com timestamp
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        output_file = os.path.join(output_folder, f'document_{{timestamp}}.pdf')
                        
                        # Converter para PDF usando Ghostscript
                        self.logger.info(f'Convertendo {{file}} para PDF...')
                        result = subprocess.run([
                            gs_path,
                            '-sDEVICE=pdfwrite',
                            '-dNOPAUSE',
                            '-dBATCH',
                            '-dSAFER',
                            '-sPAPERSIZE=a4',
                            '-dPDFSETTINGS=/prepress',
                            '-dCompatibilityLevel=1.7',
                            f'-sOutputFile={{output_file}}',
                            input_file
                        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                        
                        # Verificar resultado
                        if result.returncode == 0:
                            self.logger.info(f'Conversão concluída: {{output_file}}')
                            # Remover arquivo original
                            os.remove(input_file)
                        else:
                            error = result.stderr.decode('utf-8', errors='ignore')
                            self.logger.error(f'Erro na conversão: {{error}}')
                            
                    except Exception as e:
                        self.logger.error(f'Erro ao processar arquivo {{file}}: {{str(e)}}')
                
                # Aguardar antes de verificar novamente
                time.sleep(1)
                
                # Verificar se o serviço deve parar
                if win32event.WaitForSingleObject(self.hWaitStop, 1) == win32event.WAIT_OBJECT_0:
                    break
                    
            except Exception as e:
                self.logger.error(f'Erro no loop principal: {{str(e)}}')
                time.sleep(5)  # Aguardar mais tempo em caso de erro

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PDFPrinterService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PDFPrinterService)
"""
    
    # Salvar o script do serviço
    service_script_path = os.path.join(install_dir, "pdf_printer_service.py")
    with open(service_script_path, "w") as f:
        f.write(monitor_script)
    
    # Instalar dependências necessárias para o serviço
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pywin32", "--quiet"])
    except:
        print("Erro ao instalar pywin32. Tentando continuar...")
    
    # Instalar o serviço
    try:
        subprocess.run([
            sys.executable,
            service_script_path,
            "install"
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Iniciar o serviço
        subprocess.run([
            "net",
            "start",
            "PDFPrinterService"
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return True
    except Exception as e:
        print(f"Erro ao instalar serviço: {e}")
        
        # Criar script batch para iniciar o monitor na inicialização (alternativa ao serviço)
        batch_script = f"""@echo off
REM Script para monitorar a pasta de impressão e converter para PDF

:start
REM Verificar se há arquivos para converter
for %%f in ("{spool_folder}\\*.ps" "{spool_folder}\\*.prn") do (
    echo Convertendo %%f para PDF...
    REM Gerar timestamp
    for /f "tokens=1-6 delims=/ :," %%a in ("%date% %time%") do (
        set timestamp=%%c%%a%%b_%%d%%e%%f
    )
    
    REM Converter para PDF
    "{gs_path}" -sDEVICE=pdfwrite -dNOPAUSE -dBATCH -dSAFER -sPAPERSIZE=a4 -dPDFSETTINGS=/prepress -dCompatibilityLevel=1.7 -sOutputFile="{output_folder}\\document_%timestamp%.pdf" "%%f"
    
    REM Remover arquivo original
    del "%%f"
)

REM Aguardar antes de verificar novamente
timeout /t 1 /nobreak > nul
goto start
"""
        
        batch_path = os.path.join(install_dir, "monitor_printer.bat")
        with open(batch_path, "w") as f:
            f.write(batch_script)
        
        # Criar tarefa agendada
        task_name = "PDFPrinterMonitor"
        subprocess.run([
            "schtasks",
            "/create",
            "/tn", task_name,
            "/tr", f'cmd /c "{batch_path}"',
            "/sc", "onstart",
            "/ru", "SYSTEM",
            "/f"
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Iniciar a tarefa agora
        subprocess.run([
            "schtasks",
            "/run",
            "/tn", task_name
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Iniciar o batch agora
        subprocess.Popen(["cmd", "/c", batch_path], 
                        shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        return True

# Configurar a impressora virtual usando FILE: port
def setup_file_printer(printer_name, spool_folder):
    try:
        # Remover impressora anterior se existir
        subprocess.run([
            'powershell.exe',
            '-Command',
            f'Remove-Printer -Name "{printer_name}" -ErrorAction SilentlyContinue'
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Criar porta de arquivo
        port_name = f"FILE:{spool_folder}\\"
        
        # Adicionar a impressora usando um driver PostScript padrão
        ps_drivers = [
            "Microsoft PS Class Driver",
            "MS Publisher Color Printer",
            "Microsoft Publisher Color Printer",
            "Generic / Text Only"
        ]
        
        driver_installed = False
        for driver in ps_drivers:
            try:
                # Verificar se o driver existe
                result = subprocess.run([
                    'powershell.exe',
                    '-Command',
                    f'Get-PrinterDriver -Name "{driver}" -ErrorAction SilentlyContinue'
                ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                if driver in result.stdout.decode():
                    # Adicionar impressora com este driver
                    subprocess.run([
                        'powershell.exe',
                        '-Command',
                        f'Add-Printer -Name "{printer_name}" -DriverName "{driver}" -PortName "{port_name}"'
                    ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    
                    driver_installed = True
                    break
            except:
                continue
        
        if not driver_installed:
            # Tentar adicionar o driver Microsoft PS Class Driver (que normalmente vem com o Windows)
            try:
                subprocess.run([
                    'powershell.exe',
                    '-Command',
                    'Add-PrinterDriver -Name "Microsoft PS Class Driver"'
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                # Adicionar impressora
                subprocess.run([
                    'powershell.exe',
                    '-Command',
                    f'Add-Printer -Name "{printer_name}" -DriverName "Microsoft PS Class Driver" -PortName "{port_name}"'
                ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                
                driver_installed = True
            except:
                pass
        
        if not driver_installed:
            # Último recurso: usar o driver "Generic / Text Only" que está sempre presente
            subprocess.run([
                'RUNDLL32.EXE',
                'PRINTUI.DLL,PrintUIEntry',
                '/if',
                '/b', printer_name,
                '/f', os.path.join(os.environ["SystemRoot"], "inf", "ntprint.inf"),
                '/r', port_name,
                '/m', "Generic / Text Only"
            ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Definir como impressora padrão
        subprocess.run([
            'RUNDLL32.EXE',
            'PRINTUI.DLL,PrintUIEntry',
            '/y',
            f'/n"{printer_name}"'
        ], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Esconder janelas de diálogo de impressão alterando o registro
        try:
            reg_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_WRITE) as key:
                winreg.SetValueEx(key, "NoFileAssociate", 0, winreg.REG_DWORD, 1)
        except:
            pass
        
        return True
    except Exception as e:
        print(f"Erro na configuração da impressora: {e}")
        return False

# Função principal
def main():
    # Verificar se está rodando em Windows
    if platform.system() != "Windows":
        print("Este script funciona apenas no Windows.")
        return
    
    # Verificar privilégios de administrador
    if not is_admin():
        # Relançar o script com privilégios de administrador
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        return
    
    # Configurações
    install_dir = os.path.join(os.environ["ProgramFiles"], "SilentPDFPrinter")
    spool_folder = os.path.join(install_dir, "Spool")
    printer_name = "PDF Printer Silent"
    output_folder = os.path.join(os.path.expanduser("~"), "Documents", "PDFPrints")
    
    # Criar pastas necessárias
    os.makedirs(install_dir, exist_ok=True)
    os.makedirs(spool_folder, exist_ok=True)
    os.makedirs(output_folder, exist_ok=True)
    
    # 1. Instalar Ghostscript
    print("Instalando Ghostscript...")
    if not install_ghostscript():
        print("Falha na instalação do Ghostscript. Abortando.")
        return
    
    # 2. Encontrar o caminho do executável do Ghostscript
    gs_path = find_ghostscript_path()
    if not gs_path:
        print("Erro: Não foi possível encontrar o executável do Ghostscript.")
        print("Por favor, instale o Ghostscript manualmente.")
        return
    
    # 3. Configurar a impressora virtual usando porta FILE:
    print("Configurando impressora virtual...")
    if not setup_file_printer(printer_name, spool_folder):
        print("Falha na configuração da impressora. Abortando.")
        return
    
    # 4. Criar e iniciar o serviço/monitor
    print("Configurando monitor de impressão...")
    if not create_print_monitor_service(install_dir, spool_folder, output_folder, gs_path):
        print("Falha na configuração do monitor. Abortando.")
        return
    
    print(f"Instalação concluída com sucesso!")
    print(f"A impressora '{printer_name}' está configurada.")
    print(f"Os PDFs serão salvos em: {output_folder}")

if __name__ == "__main__":
    # Verificar se está em modo silencioso
    silent_mode = "--silent" in sys.argv
    if silent_mode:
        # Redirecionar saída para arquivo temporário
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
    
    main()
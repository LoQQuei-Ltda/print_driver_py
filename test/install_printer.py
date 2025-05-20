# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time
import tempfile
import urllib.request
import ctypes
import winreg
from pathlib import Path
import shutil
import locale
import traceback
import logging
import datetime

# Configuração de logging
log_dir = os.path.expanduser("~")
log_file = os.path.join(log_dir, "printer_install_log.txt")
logging.basicConfig(
    filename=log_file,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Função para log que escreve tanto no arquivo quanto na tela
def log_message(message, level="INFO"):
    print(message)
    if level == "INFO":
        logging.info(message)
    elif level == "ERROR":
        logging.error(message)
    elif level == "WARNING":
        logging.warning(message)
    elif level == "DEBUG":
        logging.debug(message)

# Constantes
PDF_DIR = "c:/pdfs"
TEMP_DIR = "c:/pdf_temp"
PRINTER_NAME = "Impressora LoQQuei"
GHOSTSCRIPT_URL = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10020/gs10020w64.exe"

# Variável global para armazenar o caminho do executável do Ghostscript
GHOSTSCRIPT_EXE = None

# Detecta o idioma do Windows para usar o nome correto do grupo "Everyone"
try:
    lang = locale.getpreferredencoding()
    if lang.lower() == 'cp1252':  # Português
        EVERYONE_GROUP = "Todos"
    else:
        EVERYONE_GROUP = "Everyone"
except:
    EVERYONE_GROUP = "Todos"  # Assumir português como padrão

def is_admin():
    """Verifica se o script está sendo executado como administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception as e:
        log_message(f"Erro ao verificar privilégios de administrador: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def install_required_packages():
    """Instala pacotes Python necessários."""
    required_packages = ['pywin32', 'psutil']
    
    for package in required_packages:
        try:
            log_message(f"Instalando pacote {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package], 
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            log_message(f"Pacote {package} instalado com sucesso.")
        except Exception as e:
            log_message(f"Erro ao instalar pacote {package}: {e}", "ERROR")
            log_message(traceback.format_exc(), "ERROR")
    
    # Verifica se os pacotes foram realmente instalados
    try:
        import win32print
        import psutil
        log_message("Pacotes verificados e disponíveis.")
        return True
    except ImportError as e:
        log_message(f"Falha ao importar pacotes necessários: {e}", "ERROR")
        return False

def download_file(url, destination):
    """Baixa arquivo da URL especificada."""
    try:
        log_message(f"Baixando {url} para {destination}...")
        
        # Cria o diretório de destino se não existir
        os.makedirs(os.path.dirname(os.path.abspath(destination)), exist_ok=True)
        
        # Baixa o arquivo
        urllib.request.urlretrieve(url, destination)
        
        # Verifica se o arquivo foi baixado corretamente
        if os.path.exists(destination):
            file_size = os.path.getsize(destination)
            log_message(f"Arquivo baixado com sucesso. Tamanho: {file_size} bytes")
            return True
        else:
            log_message(f"Falha ao baixar arquivo: arquivo não existe", "ERROR")
            return False
    except Exception as e:
        log_message(f"Erro ao baixar arquivo: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def setup_folders():
    """Cria e configura as pastas necessárias."""
    try:
        log_message(f"Criando pastas {PDF_DIR} e {TEMP_DIR}...")
        
        # Cria os diretórios, se não existirem
        for directory in [PDF_DIR, TEMP_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)
                log_message(f"Pasta {directory} criada.")
            else:
                log_message(f"Pasta {directory} já existe.")
            
            # Define permissões para "Todos" usando icacls
            try:
                subprocess.check_call(f'icacls "{directory}" /grant "{EVERYONE_GROUP}":(OI)(CI)F /T', shell=True)
                subprocess.check_call(f'icacls "{directory}" /grant SYSTEM:(OI)(CI)F /T', shell=True)
                log_message(f"Permissões para {directory} configuradas.")
            except subprocess.CalledProcessError as e:
                log_message(f"Erro ao definir permissões para {directory}: {e}", "ERROR")
        
        return True
    except Exception as e:
        log_message(f"Erro ao configurar pastas: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def find_ghostscript_executable():
    """Localiza o executável do Ghostscript na instalação."""
    global GHOSTSCRIPT_EXE
    
    try:
        gs_base_dir = "C:\\Program Files\\gs"
        
        # Caminhos possíveis para o executável do Ghostscript
        possible_paths = [
            "C:\\Program Files\\gs\\bin\\gswin64c.exe",
            "C:\\Program Files\\gs\\bin\\gswin64.exe",
            "C:\\Program Files\\gs\\gs10.02.0\\bin\\gswin64c.exe",
            "C:\\Program Files\\gs\\gs10.02.0\\bin\\gswin64.exe"
        ]
        
        # Procura em todos os subdiretórios
        if os.path.exists(gs_base_dir):
            for root, dirs, files in os.walk(gs_base_dir):
                for file in files:
                    if file.lower() in ["gswin64c.exe", "gswin64.exe"]:
                        gs_path = os.path.join(root, file)
                        log_message(f"Encontrado executável do Ghostscript: {gs_path}")
                        GHOSTSCRIPT_EXE = gs_path
                        return gs_path
        
        # Procura nos caminhos possíveis
        for path in possible_paths:
            if os.path.exists(path):
                log_message(f"Encontrado executável do Ghostscript: {path}")
                GHOSTSCRIPT_EXE = path
                return path
        
        # Procura no PATH do sistema
        result = subprocess.run('where gswin64c.exe', shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            gs_path = result.stdout.strip().split('\n')[0]
            log_message(f"Encontrado executável do Ghostscript no PATH: {gs_path}")
            GHOSTSCRIPT_EXE = gs_path
            return gs_path
        
        log_message("Executável do Ghostscript não encontrado.", "WARNING")
        return None
    except Exception as e:
        log_message(f"Erro ao procurar executável do Ghostscript: {e}", "ERROR")
        return None

def install_ghostscript():
    """Baixa e instala o Ghostscript silenciosamente."""
    global GHOSTSCRIPT_EXE
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "gs_setup.exe")
    
    try:
        # Procura o Ghostscript já instalado
        gs_exe = find_ghostscript_executable()
        if gs_exe:
            log_message(f"Ghostscript já está instalado em: {gs_exe}")
            GHOSTSCRIPT_EXE = gs_exe
            return True
            
        # Baixa o instalador
        log_message("Ghostscript não encontrado. Baixando instalador...")
        if not download_file(GHOSTSCRIPT_URL, installer_path):
            log_message("Falha ao baixar Ghostscript.", "ERROR")
            return False
        
        # Verifica se o arquivo foi baixado
        if not os.path.exists(installer_path):
            log_message(f"Arquivo de instalação não encontrado: {installer_path}", "ERROR")
            return False
            
        # Parâmetros para instalação silenciosa
        log_message("Instalando Ghostscript silenciosamente...")
        install_args = [
            installer_path,
            '/S',           # Instalação silenciosa
            '/NCRC',        # Não verifica CRC
            '/D=C:\\Program Files\\gs'  # Diretório de instalação
        ]
        
        # Executa o instalador
        process = subprocess.Popen(install_args, 
                                stdout=subprocess.PIPE, 
                                stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        log_message(f"Saída da instalação: {stdout.decode() if stdout else 'Nenhuma'}")
        
        if stderr:
            log_message(f"Erro na instalação: {stderr.decode()}", "ERROR")
        
        # Aguarda a instalação concluir
        log_message("Aguardando conclusão da instalação...")
        time.sleep(20)
        
        # Procura novamente pelo executável do Ghostscript
        gs_exe = find_ghostscript_executable()
        if gs_exe:
            log_message(f"Ghostscript instalado com sucesso em: {gs_exe}")
            GHOSTSCRIPT_EXE = gs_exe
            return True
        else:
            log_message("Ghostscript não foi encontrado após a instalação.", "ERROR")
            return False
    
    except Exception as e:
        log_message(f"Erro durante a instalação do Ghostscript: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False
    finally:
        # Limpa o arquivo temporário
        try:
            if os.path.exists(installer_path):
                os.remove(installer_path)
                log_message(f"Arquivo de instalação {installer_path} removido.")
        except Exception as e:
            log_message(f"Erro ao remover arquivo de instalação: {e}", "WARNING")

def create_postscript_printer_service():
    """Cria um serviço Python que monitora impressões e converte direto para PDF."""
    global GHOSTSCRIPT_EXE
    service_path = os.path.join(os.environ["SYSTEMROOT"], "ps_printer_service.py")
    
    log_message(f"Criando serviço de impressão em {service_path}...")
    
    # Garante que temos um caminho válido para o Ghostscript
    if not GHOSTSCRIPT_EXE:
        gs_exe = find_ghostscript_executable()
        if gs_exe:
            GHOSTSCRIPT_EXE = gs_exe
        else:
            # Caminho padrão para tentar
            GHOSTSCRIPT_EXE = "C:\\Program Files\\gs\\gs10.02.0\\bin\\gswin64c.exe"
            log_message(f"Usando caminho padrão para Ghostscript: {GHOSTSCRIPT_EXE}", "WARNING")
    
    # Código do serviço
    service_code = f"""# -*- coding: utf-8 -*-
import os
import sys
import time
import tempfile
import subprocess
import traceback
import logging
import threading
import socket
import win32serviceutil
import win32service
import win32event
import servicemanager
import win32print
import win32con
import pythoncom
import io
import glob

# Configurações
PDF_DIR = "{PDF_DIR}"
TEMP_DIR = "{TEMP_DIR}"
PRINTER_NAME = "{PRINTER_NAME}"
GS_PATH = "{GHOSTSCRIPT_EXE}"
LOG_FILE = os.path.expanduser("~/ps_printer_service.log")

# Configuração de logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_message(message, level="INFO"):
    if level == "INFO":
        logging.info(message)
    elif level == "ERROR":
        logging.error(message)
    elif level == "WARNING":
        logging.warning(message)
    elif level == "DEBUG":
        logging.debug(message)

def find_ghostscript():
    # Primeiro, verifica se o GS_PATH é válido
    if os.path.exists(GS_PATH):
        return GS_PATH
    
    # Procura em locais comuns
    for path in [
        "C:\\\\Program Files\\\\gs\\\\gs10.02.0\\\\bin\\\\gswin64c.exe",
        "C:\\\\Program Files\\\\gs\\\\gs10.02.0\\\\bin\\\\gswin64.exe",
        "C:\\\\Program Files\\\\gs\\\\bin\\\\gswin64c.exe",
        "C:\\\\Program Files\\\\gs\\\\bin\\\\gswin64.exe"
    ]:
        if os.path.exists(path):
            return path
    
    # Tenta encontrar via PATH
    try:
        result = subprocess.run("where gswin64c.exe", shell=True, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().split("\\n")[0]
    except:
        pass
    
    # Procura recursivamente no diretório do GS
    gs_dir = "C:\\\\Program Files\\\\gs"
    if os.path.exists(gs_dir):
        for root, dirs, files in os.walk(gs_dir):
            for file in files:
                if file.lower() in ["gswin64c.exe", "gswin64.exe"]:
                    return os.path.join(root, file)
    
    # Último recurso: tenta usar o comando gswin64c diretamente
    return "gswin64c.exe"

def convert_ps_to_pdf(ps_file, pdf_file):
    try:
        gs_exe = find_ghostscript()
        log_message(f"Usando Ghostscript: {{gs_exe}}")
        
        process = subprocess.Popen([
            gs_exe,
            '-dNOPAUSE',
            '-dBATCH',
            '-dSAFER',
            '-sDEVICE=pdfwrite',
            f'-sOutputFile={{pdf_file}}',
            ps_file
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            log_message(f"Erro do Ghostscript: {{stderr.decode()}}", "ERROR")
            return False
            
        return True
    except Exception as e:
        log_message(f"Erro ao converter {{ps_file}}: {{e}}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def printer_monitor_job():
    log_message("Iniciando monitoramento de impressões...")
    
    # Garante que os diretórios existam
    for dir_path in [PDF_DIR, TEMP_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            log_message(f"Criada pasta {{dir_path}}")
    
    # Configura a porta FILE: para salvar no TEMP_DIR automaticamente
    port_key_path = r"Software\\Microsoft\\Windows NT\\CurrentVersion\\Devices"
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Software\\Microsoft\\Windows NT\\CurrentVersion\\Devices", 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, PRINTER_NAME, 0, winreg.REG_SZ, f"{{TEMP_DIR}}\\output.prn,FILE:")
        winreg.CloseKey(key)
        log_message("Porta configurada para salvar automaticamente.")
    except Exception as e:
        log_message(f"Erro ao configurar porta: {{e}}", "ERROR")
    
    # Loop principal: monitora diretórios para novos arquivos
    while True:
        try:
            # Busca por arquivos de impressão no diretório TEMP
            search_paths = [
                os.path.join(TEMP_DIR, "*.prn"),
                os.path.join(TEMP_DIR, "*.ps"),
                os.path.join(TEMP_DIR, "*.PRN"),
                os.path.join(TEMP_DIR, "*.PS"),
                os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), "*.prn"),
                os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), "*.ps"),
                os.path.join(os.environ.get('USERPROFILE'), "*.prn"),
                os.path.join(os.environ.get('USERPROFILE'), "*.ps")
            ]
            
            found_files = []
            for path in search_paths:
                found_files.extend(glob.glob(path))
            
            # Processa cada arquivo encontrado
            for file_path in found_files:
                try:
                    # Verifica se o arquivo não está sendo usado
                    try:
                        with open(file_path, 'a'):
                            pass
                    except:
                        # Arquivo em uso, pula
                        continue
                    
                    log_message(f"Novo arquivo de impressão encontrado: {{file_path}}")
                    
                    # Nome do arquivo PDF de saída
                    filename = os.path.basename(file_path)
                    base_name = os.path.splitext(filename)[0]
                    
                    # Adiciona timestamp para evitar sobreposições
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    pdf_name = f"{{base_name}}_{{timestamp}}.pdf"
                    pdf_path = os.path.join(PDF_DIR, pdf_name)
                    
                    # Converte para PDF
                    log_message(f"Convertendo {{file_path}} para {{pdf_path}}...")
                    if convert_ps_to_pdf(file_path, pdf_path):
                        log_message(f"Arquivo convertido com sucesso para {{pdf_path}}")
                        
                        # Remove o arquivo original
                        try:
                            os.remove(file_path)
                        except Exception as e:
                            log_message(f"Erro ao remover arquivo original: {{e}}", "ERROR")
                    else:
                        log_message(f"Falha ao converter {{file_path}}", "ERROR")
                        
                except Exception as e:
                    log_message(f"Erro ao processar {{file_path}}: {{e}}", "ERROR")
                    log_message(traceback.format_exc(), "ERROR")
            
            # Aguarda antes da próxima verificação
            time.sleep(1)
            
        except Exception as e:
            log_message(f"Erro no loop de monitoramento: {{e}}", "ERROR")
            log_message(traceback.format_exc(), "ERROR")
            time.sleep(5)  # Espera um pouco mais em caso de erro

def create_direct_printing_batch():
    batch_path = os.path.join(TEMP_DIR, "direct_print.bat")
    
    # Agora usamos a variável GS_PATH que foi definida nas configurações
    batch_content = f'''@echo off
REM Script para imprimir diretamente para PDF usando Ghostscript
set INPUT_FILE=%1
set OUTPUT_NAME=%~n1
set OUTPUT_FILE="{PDF_DIR}\\%OUTPUT_NAME%_%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2%.pdf"
set OUTPUT_FILE=%OUTPUT_FILE: =0%

"{{GS_PATH}}" -dNOPAUSE -dBATCH -dSAFER -sDEVICE=pdfwrite -sOutputFile="%OUTPUT_FILE%" "%INPUT_FILE%"

if %ERRORLEVEL% EQU 0 (
    del "%INPUT_FILE%"
    echo Arquivo convertido com sucesso para %OUTPUT_FILE%
) else (
    echo Erro na conversão
)
'''
    
    # Salva o arquivo batch
    with open(batch_path, "w") as f:
        f.write(batch_content)
    
    log_message(f"Criado script de impressão direta em {{batch_path}}")
    return batch_path

class PrinterService(win32serviceutil.ServiceFramework):
    _svc_name_ = "PSPrinterService"
    _svc_display_name_ = "PostScript Printer Service"
    _svc_description_ = "Serviço de impressão e conversão automática para PDF"

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        socket.setdefaulttimeout(60)
        self.is_running = True
        self.thread = None

    def SvcStop(self):
        self.is_running = False
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE,
                              servicemanager.PID_INFO,
                              (self._svc_name_, ''))
        self.main()

    def main(self):
        # Inicia o monitoramento em uma thread separada
        self.thread = threading.Thread(target=printer_monitor_job)
        self.thread.daemon = True
        self.thread.start()
        
        # Cria o script de impressão direta
        create_direct_printing_batch()
        
        # Loop principal do serviço
        while self.is_running:
            # Verifica se o serviço deve parar
            rc = win32event.WaitForSingleObject(self.hWaitStop, 5000)
            if rc == win32event.WAIT_OBJECT_0:
                break

if __name__ == '__main__':
    if len(sys.argv) == 1:
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PrinterService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PrinterService)
"""
    
    # Salva o arquivo do serviço
    with open(service_path, 'w', encoding='utf-8') as f:
        f.write(service_code)
    
    log_message(f"Serviço criado em: {service_path}")
    
    # Cria o arquivo .bat para instalar e iniciar o serviço
    bat_path = os.path.join(os.environ["SYSTEMROOT"], "install_ps_service.bat")
    with open(bat_path, 'w', encoding='utf-8') as f:
        f.write(f'@echo off\n')
        f.write(f'echo Instalando serviço de impressão...\n')
        f.write(f'"{sys.executable}" "{service_path}" install\n')
        f.write(f'echo Iniciando serviço...\n')
        f.write(f'"{sys.executable}" "{service_path}" start\n')
        f.write(f'echo Serviço instalado e iniciado.\n')
        f.write(f'pause\n')
    
    log_message(f"Script de instalação do serviço criado em: {bat_path}")
    
    # Executa o script de instalação
    log_message("Instalando e iniciando o serviço...")
    subprocess.call(f'"{bat_path}"', shell=True)
    
    # Também cria um monitor de fallback como script Python normal
    monitor_path = os.path.join(os.environ["SYSTEMROOT"], "ps_print_monitor.py")
    
    # Código muito similar ao serviço, mas executado como script normal
    monitor_code = f"""# -*- coding: utf-8 -*-
import os
import sys
import time
import glob
import subprocess
import traceback
import logging

# Configurações
PDF_DIR = "{PDF_DIR}"
TEMP_DIR = "{TEMP_DIR}"
PRINTER_NAME = "{PRINTER_NAME}"
GS_PATH = "{GHOSTSCRIPT_EXE}"
LOG_FILE = os.path.expanduser("~/ps_print_monitor.log")

# Configuração de logging
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def log_message(message, level="INFO"):
    if level == "INFO":
        logging.info(message)
    elif level == "ERROR":
        logging.error(message)
    elif level == "WARNING":
        logging.warning(message)
    elif level == "DEBUG":
        logging.debug(message)

def find_ghostscript():
    # Primeiro, verifica se o GS_PATH é válido
    if os.path.exists(GS_PATH):
        return GS_PATH
    
    # Procura em locais comuns
    for path in [
        "C:\\\\Program Files\\\\gs\\\\gs10.02.0\\\\bin\\\\gswin64c.exe",
        "C:\\\\Program Files\\\\gs\\\\gs10.02.0\\\\bin\\\\gswin64.exe",
        "C:\\\\Program Files\\\\gs\\\\bin\\\\gswin64c.exe",
        "C:\\\\Program Files\\\\gs\\\\bin\\\\gswin64.exe"
    ]:
        if os.path.exists(path):
            return path
    
    # Procura recursivamente no diretório do GS
    gs_dir = "C:\\\\Program Files\\\\gs"
    if os.path.exists(gs_dir):
        for root, dirs, files in os.walk(gs_dir):
            for file in files:
                if file.lower() in ["gswin64c.exe", "gswin64.exe"]:
                    return os.path.join(root, file)
    
    # Último recurso: tenta usar o comando gswin64c diretamente
    return "gswin64c.exe"

def convert_ps_to_pdf(ps_file, pdf_file):
    try:
        gs_exe = find_ghostscript()
        log_message(f"Usando Ghostscript: {{gs_exe}}")
        
        process = subprocess.Popen([
            gs_exe,
            '-dNOPAUSE',
            '-dBATCH',
            '-dSAFER',
            '-sDEVICE=pdfwrite',
            f'-sOutputFile={{pdf_file}}',
            ps_file
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            log_message(f"Erro do Ghostscript: {{stderr.decode()}}", "ERROR")
            return False
            
        return True
    except Exception as e:
        log_message(f"Erro ao converter {{ps_file}}: {{e}}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def main():
    log_message("Iniciando monitor de arquivos de impressão...")
    
    # Garante que os diretórios existam
    for dir_path in [PDF_DIR, TEMP_DIR]:
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
            log_message(f"Criada pasta {{dir_path}}")
    
    # Loop principal de monitoramento
    while True:
        try:
            # Lista de diretórios onde arquivos de impressão podem ser salvos
            search_paths = [
                os.path.join(TEMP_DIR, "*.prn"),
                os.path.join(TEMP_DIR, "*.ps"),
                os.path.join(TEMP_DIR, "*.PRN"),
                os.path.join(TEMP_DIR, "*.PS"),
                os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), "*.prn"),
                os.path.join(os.environ.get('TEMP', 'C:\\Windows\\Temp'), "*.ps"),
                os.path.join(os.environ.get('USERPROFILE'), "*.prn"),
                os.path.join(os.environ.get('USERPROFILE'), "*.ps"),
                os.path.join(os.environ.get('USERPROFILE'), "Desktop", "*.prn"),
                os.path.join(os.environ.get('USERPROFILE'), "Desktop", "*.ps"),
                os.path.join(os.environ.get('USERPROFILE'), "Documents", "*.prn"),
                os.path.join(os.environ.get('USERPROFILE'), "Documents", "*.ps")
            ]
            
            found_files = []
            for path in search_paths:
                found_files.extend(glob.glob(path))
            
            # Se encontrou arquivos, processa cada um
            for file_path in found_files:
                try:
                    # Verifica se o arquivo não está sendo usado
                    try:
                        with open(file_path, 'a'):
                            pass
                    except:
                        # Arquivo em uso, pula
                        continue
                    
                    log_message(f"Arquivo encontrado: {{file_path}}")
                    
                    # Nome do arquivo PDF de saída
                    filename = os.path.basename(file_path)
                    base_name = os.path.splitext(filename)[0]
                    
                    # Adiciona timestamp para evitar sobreposições
                    timestamp = time.strftime("%Y%m%d_%H%M%S")
                    pdf_name = f"{{base_name}}_{{timestamp}}.pdf"
                    pdf_path = os.path.join(PDF_DIR, pdf_name)
                    
                    # Converte para PDF
                    if convert_ps_to_pdf(file_path, pdf_path):
                        log_message(f"Arquivo convertido para {{pdf_path}}")
                        
                        # Remove o arquivo original
                        try:
                            os.remove(file_path)
                            log_message(f"Arquivo original removido: {{file_path}}")
                        except Exception as e:
                            log_message(f"Erro ao remover arquivo original: {{e}}", "ERROR")
                    else:
                        log_message(f"Falha ao converter {{file_path}}", "ERROR")
                
                except Exception as e:
                    log_message(f"Erro ao processar {{file_path}}: {{e}}", "ERROR")
                    log_message(traceback.format_exc(), "ERROR")
            
            # Pausa breve antes da próxima verificação
            time.sleep(1)
            
        except Exception as e:
            log_message(f"Erro no loop principal: {{e}}", "ERROR")
            log_message(traceback.format_exc(), "ERROR")
            time.sleep(5)  # Espera um pouco mais em caso de erro

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Erro crítico: {{e}}")
        logging.error(traceback.format_exc())
"""
    
    # Salva o monitor de fallback
    with open(monitor_path, 'w', encoding='utf-8') as f:
        f.write(monitor_code)
    
    log_message(f"Monitor de fallback criado em: {monitor_path}")
    
    # Cria um arquivo .bat para iniciar o monitor
    monitor_bat_path = os.path.join(os.environ["SYSTEMROOT"], "start_ps_monitor.bat")
    with open(monitor_bat_path, 'w', encoding='utf-8') as f:
        f.write(f'@echo off\n')
        f.write(f'start /MIN pythonw "{monitor_path}"\n')
    
    log_message(f"Script para iniciar o monitor criado em: {monitor_bat_path}")
    
    # Adiciona ao startup do Windows
    startup_folder = os.path.join(os.environ['APPDATA'], r"Microsoft\Windows\Start Menu\Programs\Startup")
    startup_link = os.path.join(startup_folder, "PS to PDF Monitor.lnk")
    
    # Cria um atalho para o script no startup
    vbs_path = os.path.join(tempfile.gettempdir(), "create_shortcut.vbs")
    with open(vbs_path, 'w', encoding='utf-8') as f:
        f.write(f'Set oWS = WScript.CreateObject("WScript.Shell")\r\n')
        f.write(f'sLinkFile = "{startup_link}"\r\n')
        f.write(f'Set oLink = oWS.CreateShortcut(sLinkFile)\r\n')
        f.write(f'oLink.TargetPath = "{monitor_bat_path}"\r\n')
        f.write(f'oLink.WindowStyle = 7\r\n')  # 7 = Minimized
        f.write(f'oLink.Save\r\n')
    
    # Executa o script VBS para criar o atalho
    subprocess.call(f'cscript "{vbs_path}"', shell=True)
    
    log_message(f"Atalho criado em {startup_link}")
    
    # Inicia o monitor
    log_message("Iniciando monitor de arquivos...")
    subprocess.Popen(f'start /MIN pythonw "{monitor_path}"', shell=True)
    
    return True

def create_pure_ps_printer():
    """Cria uma impressora PostScript pura que não mostra diálogos."""
    try:
        log_message("Criando impressora PostScript pura...")
        
        # Verifica se a impressora já existe e a remove
        import win32print
        try:
            printers = [printer[2] for printer in win32print.EnumPrinters(2)]
            if PRINTER_NAME in printers:
                log_message(f"Removendo impressora {PRINTER_NAME} existente...")
                del_cmd = f'rundll32 printui.dll,PrintUIEntry /dl /n"{PRINTER_NAME}"'
                subprocess.call(del_cmd, shell=True)
                time.sleep(2)
        except Exception as e:
            log_message(f"Erro ao verificar impressoras: {e}", "WARNING")
        
        # Limpa serviço de spooler para garantir
        try:
            subprocess.run('net stop spooler', shell=True)
            time.sleep(2)
            
            # Remove arquivos de spool antigos
            spool_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'System32', 'spool', 'PRINTERS')
            if os.path.exists(spool_path):
                for file in os.listdir(spool_path):
                    try:
                        os.remove(os.path.join(spool_path, file))
                    except:
                        pass
            
            subprocess.run('net start spooler', shell=True)
            time.sleep(2)
            log_message("Serviço de spooler reiniciado e limpo.")
        except:
            log_message("Erro ao reiniciar serviço de spooler.", "WARNING")
        
        # Tenta usar o driver Microsoft XPS Document Writer ou PDF
        driver_names_to_try = [
            "Microsoft XPS Document Writer v4",
            "Microsoft XPS Document Writer",
            "Microsoft Print To PDF",
            "Generic / PS Printer",
            "MS Publisher Imagesetter",
            "Generic / Text Only"
        ]
        
        driver_name = driver_names_to_try[-1]  # Default to "Generic / Text Only"
        
        try:
            import win32print
            drivers = win32print.EnumPrinterDrivers(None, None, 2)
            # Verifica todos os drivers disponíveis pelo nome
            for preferred_driver in driver_names_to_try:
                for driver in drivers:
                    try:
                        if preferred_driver.lower() in driver["Name"].lower():
                            driver_name = driver["Name"]
                            log_message(f"Usando driver: {driver_name}")
                            break
                    except Exception as de:
                        continue
                if driver_name != driver_names_to_try[-1]:
                    break
        except Exception as e:
            log_message(f"Erro ao listar drivers de impressora: {e}", "WARNING")
        
        # Cria arquivo temporário para a porta de saída
        output_file = os.path.join(TEMP_DIR, "output.prn")
        if not os.path.exists(output_file):
            with open(output_file, 'w') as f:
                f.write("")
        
        # Define permissões
        subprocess.run(f'icacls "{output_file}" /grant Everyone:(F) /T', shell=True)
        log_message(f"Arquivo de saída padrão {output_file} preparado.")
        
        # Adiciona a impressora com a porta FILE: apontando para o arquivo fixo
        add_printer_cmd = f'rundll32 printui.dll,PrintUIEntry /if /b"{PRINTER_NAME}" /f%windir%\\inf\\ntprint.inf /r"FILE:" /m"{driver_name}"'
        subprocess.call(add_printer_cmd, shell=True)
        
        # Aguarda um momento para a impressora ser criada
        time.sleep(3)
        
        # Define como impressora padrão
        import win32print
        try:
            win32print.SetDefaultPrinter(PRINTER_NAME)
            log_message(f"Impressora {PRINTER_NAME} definida como padrão.")
        except Exception as e:
            log_message(f"Erro ao definir impressora padrão: {e}", "ERROR")
        
        # Configura a pasta de saída fixa no registro
        try:
            key_path = r"Software\Microsoft\Windows NT\CurrentVersion\Devices"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, key_path)
            winreg.SetValueEx(key, PRINTER_NAME, 0, winreg.REG_SZ, f"{output_file},FILE:")
            winreg.CloseKey(key)
            log_message("Registro configurado para salvar sem diálogo.")
        except Exception as e:
            log_message(f"Erro ao configurar registro: {e}", "ERROR")
        
        # Configura as portas no registro
        try:
            ports_path = r"Software\Microsoft\Windows NT\CurrentVersion\PrinterPorts"
            ports_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, ports_path)
            winreg.SetValueEx(ports_key, PRINTER_NAME, 0, winreg.REG_SZ, f"{output_file},FILE:,15,45")
            winreg.CloseKey(ports_key)
            log_message("Portas de impressora configuradas.")
        except Exception as e:
            log_message(f"Erro ao configurar portas: {e}", "ERROR")
            
        # Configura parâmetros da impressora usando PowerShell
        ps_script = os.path.join(tempfile.gettempdir(), "config_printer.ps1")
        with open(ps_script, 'w', encoding='utf-8') as f:
            f.write(f'''
$printerName = "{PRINTER_NAME}"
$outputFile = "{output_file.replace("\\", "\\\\")}"

# Configurar a impressora para salvar sempre no mesmo local
try {{
    $printer = Get-Printer -Name $printerName -ErrorAction SilentlyContinue
    if ($printer) {{
        # Tentar definir configurações avançadas
        Set-PrintConfiguration -PrinterName $printerName -PaperSize Letter -Color $false
        
        # Modificar diretamente no registro para garantir que não haja diálogos
        $regPath = "HKCU:\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Devices"
        Set-ItemProperty -Path $regPath -Name $printerName -Value "$outputFile,FILE:"
        
        # Configurar para salvar sem dialogos
        $regPathDlg = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced"
        Set-ItemProperty -Path $regPathDlg -Name "DontUseSaveDlg" -Value 1 -Type DWord
        
        Write-Host "Impressora configurada com sucesso."
    }} else {{
        Write-Host "Impressora $printerName não encontrada."
    }}
}} catch {{
    Write-Host "Erro ao configurar impressora: $_"
}}
''')
        
        # Executa o script PowerShell
        subprocess.call(f'powershell -ExecutionPolicy Bypass -File "{ps_script}"', shell=True)
        log_message("Configurações avançadas aplicadas via PowerShell.")
        
        # Cria o diretório temporário se não existir
        if not os.path.exists(TEMP_DIR):
            os.makedirs(TEMP_DIR)
        
        # Cria uma pasta de destino para o Salvar Como
        save_as_dir = os.path.join(TEMP_DIR, "SaveDialog")
        if not os.path.exists(save_as_dir):
            os.makedirs(save_as_dir)
        
        # Define esta pasta como destinação padrão para caixas de diálogo
        try:
            shell_folders_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_folders_path)
            winreg.SetValueEx(key, "Desktop", 0, winreg.REG_EXPAND_SZ, save_as_dir)
            winreg.SetValueEx(key, "Personal", 0, winreg.REG_EXPAND_SZ, save_as_dir)
            winreg.SetValueEx(key, "SavedGames", 0, winreg.REG_EXPAND_SZ, save_as_dir)
            winreg.CloseKey(key)
            
            # Também na outra chave de registro
            shell_folders = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_folders)
            winreg.SetValueEx(key, "Desktop", 0, winreg.REG_SZ, save_as_dir)
            winreg.SetValueEx(key, "Personal", 0, winreg.REG_SZ, save_as_dir)
            winreg.CloseKey(key)
            
            log_message(f"Pasta de destino de diálogos definida para {save_as_dir}")
        except Exception as e:
            log_message(f"Erro ao configurar pasta de destino: {e}", "WARNING")
        
        log_message("Impressora PostScript configurada com sucesso.")
        return True
    except Exception as e:
        log_message(f"Erro ao criar impressora PostScript: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def create_test_file():
    """Cria um arquivo de teste para verificar se a impressora funciona corretamente."""
    try:
        log_message("Criando arquivo de teste...")
        
        # Cria um arquivo de texto simples
        test_file = os.path.join(tempfile.gettempdir(), "printer_test.txt")
        with open(test_file, "w") as f:
            f.write("Este é um teste da impressora virtual.\n")
            f.write(f"Data e hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Se este teste for bem sucedido, um arquivo PDF será criado na pasta {PDF_DIR} sem mostrar janelas.")
        
        log_message(f"Arquivo de teste criado: {test_file}")
        
        # Imprime o arquivo usando a impressora configurada
        log_message(f"Imprimindo arquivo de teste na impressora {PRINTER_NAME}...")
        
        print_cmd = f'powershell -Command "Get-Content \'{test_file}\' | Out-Printer -Name \'{PRINTER_NAME}\'"'
        subprocess.call(print_cmd, shell=True)
        
        log_message(f"Arquivo de teste enviado para impressão. Verifique a pasta {PDF_DIR} em alguns instantes.")
        
        # Aguarda um pouco para permitir que a impressão seja processada
        log_message("Aguardando processamento da impressão...")
        time.sleep(5)
        
        # Verifica se o arquivo PDF foi criado
        import glob
        pdf_files = glob.glob(os.path.join(PDF_DIR, "*.pdf"))
        newest_pdfs = sorted(pdf_files, key=os.path.getctime, reverse=True)
        
        if newest_pdfs and (time.time() - os.path.getctime(newest_pdfs[0])) < 30:
            log_message(f"Sucesso! PDF criado: {newest_pdfs[0]}")
        else:
            log_message("Nenhum novo PDF detectado. Verifique a configuração.")
        
        return True
    except Exception as e:
        log_message(f"Erro ao criar teste de impressão: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def fix_auto_save_registry():
    """Aplica correções específicas no registro para salvar sem diálogos."""
    try:
        log_message("Aplicando correções finais no registro...")
        
        # Altera o caminho padrão para a área de trabalho (usado pela caixa de diálogo de salvar)
        try:
            shell_folders = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, shell_folders)
            
            # Backup do valor original
            try:
                original_desktop = winreg.QueryValueEx(key, "Desktop")[0]
                winreg.SetValueEx(key, "Desktop_Backup", 0, winreg.REG_SZ, original_desktop)
            except:
                pass
            
            # Define a pasta de destino como TEMP_DIR
            winreg.SetValueEx(key, "Desktop", 0, winreg.REG_SZ, TEMP_DIR)
            winreg.CloseKey(key)
            log_message("Caminho da área de trabalho redirecionado para TEMP_DIR.")
        except Exception as e:
            log_message(f"Erro ao configurar Shell Folders: {e}", "WARNING")
        
        # Configurações avançadas para desabilitar diálogos
        try:
            # Configurações para não usar diálogos de salvamento
            save_settings = r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, save_settings, 0, winreg.KEY_WRITE)
            winreg.SetValueEx(key, "DontUseSaveDlg", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(key)
            
            # Políticas para desabilitar caixas de diálogo
            policies_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer"
            policies_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, policies_path)
            winreg.SetValueEx(policies_key, "NoSaveAs", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(policies_key)
            
            # Políticas para diálogos comuns
            comdlg_path = r"Software\Microsoft\Windows\CurrentVersion\Policies\Comdlg32"
            comdlg_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, comdlg_path)
            winreg.SetValueEx(comdlg_key, "NoFileMru", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(comdlg_key, "NoBackupButton", 0, winreg.REG_DWORD, 1)
            winreg.CloseKey(comdlg_key)
            
            log_message("Configurações de políticas aplicadas para desabilitar diálogos.")
        except Exception as e:
            log_message(f"Erro ao configurar políticas de diálogo: {e}", "WARNING")
            
        # Configurações adicionais para PDF e impressoras
        try:
            # Configuração para salvar sempre no mesmo local
            print_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
            print_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, print_path)
            winreg.SetValueEx(print_key, "{374DE290-123F-4565-9164-39C4925E467B}", 0, winreg.REG_EXPAND_SZ, TEMP_DIR)
            winreg.CloseKey(print_key)
            
            # Cria arquivo .REG completo para importar todas as configurações
            reg_path = os.path.join(tempfile.gettempdir(), "printer_settings.reg")
            with open(reg_path, 'w', encoding='utf-8') as f:
                f.write('Windows Registry Editor Version 5.00\n\n')
                f.write(f'[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\Devices]\n')
                f.write(f'"{PRINTER_NAME}"="{TEMP_DIR}\\\\output.prn,nul:"\n\n')
                f.write(f'[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows NT\\CurrentVersion\\PrinterPorts]\n')
                f.write(f'"{PRINTER_NAME}"="{TEMP_DIR}\\\\output.prn,nul:,15,45"\n\n')
                f.write('[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Advanced]\n')
                f.write('"DontUseSaveDlg"=dword:00000001\n\n')
                f.write('[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Comdlg32]\n')
                f.write('"NoFileMru"=dword:00000001\n')
                f.write('"NoBackupButton"=dword:00000001\n\n')
                f.write('[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer]\n')
                f.write('"NoSaveAs"=dword:00000001\n\n')
                f.write(f'[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\Shell Folders]\n')
                f.write(f'"Desktop"="{TEMP_DIR}"\n\n')
                f.write(f'[HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Explorer\\User Shell Folders]\n')
                f.write(f'"{{374DE290-123F-4565-9164-39C4925E467B}}"="{TEMP_DIR}"\n\n')
            
            # Importa o registro completo
            subprocess.call(f'regedit /s "{reg_path}"', shell=True)
            log_message("Configurações completas de registro importadas com sucesso.")
        except Exception as e:
            log_message(f"Erro ao configurar configurações completas de registro: {e}", "WARNING")
        
        log_message("Correções no registro aplicadas.")
        return True
    except Exception as e:
        log_message(f"Erro ao aplicar correções no registro: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
        return False

def wait_for_key():
    """Aguarda o usuário pressionar uma tecla para continuar."""
    print("\n" + "=" * 80)
    print("Instalação concluída. Pressione qualquer tecla para fechar esta janela.")
    print("Os logs detalhados estão disponíveis em: " + log_file)
    print("=" * 80)
    
    try:
        input("\nPressione ENTER para continuar...")
    except:
        pass

def main():
    start_time = datetime.datetime.now()
    log_message(f"Iniciando script de instalação da impressora virtual {PRINTER_NAME} em {start_time}")
    
    try:
        # Verifica se está sendo executado como administrador
        if not is_admin():
            log_message("O script não está sendo executado como administrador. Tentando reexecutar com privilégios elevados...", "WARNING")
            try:
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
                return
            except Exception as e:
                log_message(f"Falha ao solicitar privilégios de administrador: {e}", "ERROR")
                log_message("O script continuará, mas pode encontrar erros por falta de privilégios.", "WARNING")
        
        log_message(f"Iniciando configuração da impressora virtual '{PRINTER_NAME}'...")
        
        # Passo 1: Instalar pacotes necessários
        log_message("\nInstalando pacotes Python necessários...")
        install_required_packages()
        
        # Passo 2: Configurar pastas necessárias
        log_message(f"\nConfigurando pastas necessárias...")
        setup_folders()
        
        # Passo 3: Instalar o Ghostscript
        log_message("\nInstalando Ghostscript (conversor PostScript para PDF)...")
        if not install_ghostscript():
            log_message("AVISO: Ghostscript instalado mas não encontrado no caminho esperado.", "WARNING")
            log_message("Tentando continuar com o caminho detectado...")
            GHOSTSCRIPT_EXE = "C:\\Program Files\\gs\\gs10.02.0\\bin\\gswin64c.exe"
            
            if not os.path.exists(GHOSTSCRIPT_EXE):
                log_message(f"O caminho {GHOSTSCRIPT_EXE} não existe. Tentando localizar...", "WARNING")
                gs_path = find_ghostscript_executable()
                if gs_path:
                    GHOSTSCRIPT_EXE = gs_path
                    log_message(f"Ghostscript encontrado em: {GHOSTSCRIPT_EXE}")
                else:
                    log_message("Ghostscript não encontrado. Continuando mesmo assim...", "WARNING")
        
        # Passo 4: Criar impressora PostScript pura
        log_message("\nCriando impressora PostScript...")
        create_pure_ps_printer()
        
        # Passo 5: Configurar correções no registro para salvamento automático
        log_message("\nConfigurando ajustes para salvamento automático...")
        fix_auto_save_registry()
        
        # Passo 6: Criar serviço de monitoramento
        log_message("\nConfigurando serviço de monitoramento e conversão...")
        create_postscript_printer_service()
        
        # Passo 7: Criar teste
        log_message("\nCriando teste de impressão...")
        create_test_file()
        
        # Finalização
        end_time = datetime.datetime.now()
        duration = end_time - start_time
        log_message(f"\nInstalação concluída em {duration.total_seconds():.2f} segundos!")
        log_message(f"A impressora '{PRINTER_NAME}' está configurada para salvar PDFs em {PDF_DIR}.")
        log_message("Esta solução usa Ghostscript (~30MB) em vez do PDF24 (700MB).")
        log_message("Os arquivos serão convertidos automaticamente para PDF sem mostrar diálogos.")
        log_message(f"Logs detalhados foram salvos em: {log_file}")
        
    except Exception as e:
        log_message(f"Erro crítico durante a instalação: {e}", "ERROR")
        log_message(traceback.format_exc(), "ERROR")
    
    # Aguarda o usuário pressionar uma tecla antes de fechar
    wait_for_key()

if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Instalador da impressora virtual
"""

import os
import sys
import platform
import logging
import subprocess
import tempfile
import shutil
import ctypes
from pathlib import Path

logger = logging.getLogger("PrintManagementSystem.VirtualPrinter.Installer")

class VirtualPrinterInstaller:
    """Instalador da impressora virtual"""
    
    PRINTER_NAME = "LoQQuei PDF Printer"
    
    def __init__(self, config):
        """
        Inicializa o instalador
        
        Args:
            config: Configuração da aplicação
        """
        self.config = config
        self.system = platform.system()
    
    def install(self):
        """
        Instala a impressora virtual
        
        Returns:
            bool: True se a instalação foi bem-sucedida
            
        Raises:
            RuntimeError: Se ocorrer um erro na instalação
        """
        logger.info(f"Instalando impressora virtual no {self.system}")
        
        if self.is_installed():
            logger.info("Impressora virtual já está instalada")
            return True
        
        try:
            if self.system == "Windows":
                return self._install_windows()
            elif self.system == "Darwin":  # macOS
                return self._install_macos()
            else:  # Linux ou outros
                return self._install_linux()
        except Exception as e:
            logger.error(f"Erro ao instalar impressora virtual: {str(e)}")
            raise RuntimeError(f"Erro ao instalar impressora virtual: {str(e)}")
    
    def uninstall(self):
        """
        Remove a impressora virtual
        
        Returns:
            bool: True se a remoção foi bem-sucedida
            
        Raises:
            RuntimeError: Se ocorrer um erro na remoção
        """
        logger.info(f"Removendo impressora virtual do {self.system}")
        
        if not self.is_installed():
            logger.info("Impressora virtual não está instalada")
            return True
        
        try:
            if self.system == "Windows":
                return self._uninstall_windows()
            elif self.system == "Darwin":  # macOS
                return self._uninstall_macos()
            else:  # Linux ou outros
                return self._uninstall_linux()
        except Exception as e:
            logger.error(f"Erro ao remover impressora virtual: {str(e)}")
            raise RuntimeError(f"Erro ao remover impressora virtual: {str(e)}")
    
    def is_installed(self):
        """
        Verifica se a impressora virtual está instalada
        
        Returns:
            bool: True se a impressora está instalada
        """
        try:
            if self.system == "Windows":
                return self._is_installed_windows()
            elif self.system == "Darwin":  # macOS
                return self._is_installed_macos()
            else:  # Linux ou outros
                return self._is_installed_linux()
        except Exception as e:
            logger.error(f"Erro ao verificar instalação da impressora virtual: {str(e)}")
            return False
    
    def _is_admin(self):
        """
        Verifica se o aplicativo está sendo executado como administrador/root
        
        Returns:
            bool: True se o aplicativo está sendo executado com privilégios elevados
        """
        try:
            if self.system == "Windows":
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception:
            return False
    
    def _request_admin(self, script_path, args=None):
        """
        Solicita privilégios de administrador
        
        Args:
            script_path (str): Caminho do script a ser executado com privilégios elevados
            args (list, optional): Argumentos adicionais para o script
            
        Returns:
            bool: True se o processo foi iniciado com sucesso
        """
        args = args or []
        
        try:
            if self.system == "Windows":
                # No Windows, usa ShellExecute com o verbo "runas"
                ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{script_path}" {" ".join(args)}', None, 1)
            elif self.system == "Darwin":  # macOS
                # No macOS, usa osascript para solicitar privilégios
                cmd = ["osascript", "-e", f'do shell script "\\"{sys.executable}\\" \\"{script_path}\\" {" ".join(args)}" with administrator privileges']
                subprocess.Popen(cmd)
            else:  # Linux ou outros
                # No Linux, usa sudo, gksudo, pkexec ou equivalente
                for sudo_cmd in ["pkexec", "gksudo", "kdesudo", "sudo"]:
                    if shutil.which(sudo_cmd):
                        subprocess.Popen([sudo_cmd, sys.executable, script_path] + args)
                        break
                else:
                    raise RuntimeError("Não foi possível encontrar um comando para solicitar privilégios de administrador")
            
            return True
        except Exception as e:
            logger.error(f"Erro ao solicitar privilégios de administrador: {str(e)}")
            return False
    
    # Implementações específicas para Windows
    
    def _is_installed_windows(self):
        """
        Verifica se a impressora virtual está instalada no Windows
        
        Returns:
            bool: True se a impressora está instalada
        """
        try:
            import win32print
            
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            for _, printer_name, _, _ in printers:
                if self.PRINTER_NAME in printer_name:
                    return True
            
            return False
            
        except ImportError:
            logger.error("Módulo win32print não encontrado")
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar instalação no Windows: {str(e)}")
            return False
    
    def _install_windows(self):
        """
        Instala a impressora virtual no Windows
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        if not self._is_admin():
            logger.info("Solicitando privilégios de administrador para instalar a impressora virtual")
            
            # Cria um script temporário para instalar a impressora
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "install_printer.py")
            
            with open(script_path, 'w') as f:
                f.write(f"""
import os
import sys
import subprocess
import time

# Adiciona o diretório do aplicativo ao caminho de importação
app_dir = {repr(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))}
sys.path.insert(0, app_dir)

from src.virtual_printer.installer import VirtualPrinterInstaller
from src.config import AppConfig

# Inicializa a configuração
config = AppConfig({repr(self.config.data_dir)})

# Instala a impressora
installer = VirtualPrinterInstaller(config)
result = installer._install_windows_impl()

if result:
    print("Impressora virtual instalada com sucesso!")
else:
    print("Falha ao instalar impressora virtual")

# Aguarda para o usuário ver a mensagem
time.sleep(3)
""")
            
            return self._request_admin(script_path)
        
        # Quando já temos privilégios de administrador
        return self._install_windows_impl()
    
    def _install_windows_impl(self):
        """
        Implementação real da instalação no Windows
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        try:
            import win32print
            import win32con
            
            # Verifica se já existe
            if self._is_installed_windows():
                return True
            
            # No Windows, usamos um driver de impressora PDF nativo ou instalamos um
            # Para simplicidade, vamos usar o Microsoft Print to PDF que está disponível no Windows 10 e posterior
            # Ou PDF-XChange se disponível
            
            drivers = [
                ("Microsoft Print to PDF", "PORTPROMPT:"),
                ("PDF-XChange Standard Printer Driver", "PORTPROMPT:"),
                ("PDF24", "PORTPROMPT:"),
                ("Foxit Reader PDF Printer", "PORTPROMPT:"),
            ]
            
            # Verifica se algum dos drivers está disponível
            available_drivers = win32print.EnumPrinterDrivers(None, None, 2)
            driver_found = False
            driver_name = ""
            
            for driver_info in available_drivers:
                for target_driver, _ in drivers:
                    if target_driver in driver_info["Name"]:
                        driver_name = driver_info["Name"]
                        driver_found = True
                        break
                
                if driver_found:
                    break
            
            if not driver_found:
                logger.error("Nenhum driver de impressora PDF encontrado no sistema")
                # TODO: Implementar instalação de um driver PDF
                return False
            
            # Cria um diretório para armazenar os PDFs (vai ser usado no monitor)
            pdf_dir = self.config.pdf_dir
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Cria uma porta de impressora que salva em arquivo
            port_name = f"FILE:{pdf_dir}\\$.pdf"
            
            # Adiciona impressora
            win32print.AddPrinter(
                None,  # servidor local
                2,  # nível de informação
                {
                    "Name": self.PRINTER_NAME,
                    "ShareName": "",
                    "PortName": port_name,
                    "DriverName": driver_name,
                    "Comment": "Impressora virtual para criação de PDFs",
                    "Location": "",
                    "DevMode": None,
                    "SepFile": "",
                    "PrintProcessor": "WinPrint",
                    "Datatype": "RAW",
                    "Parameters": "",
                    "Attributes": win32print.PRINTER_ATTRIBUTE_LOCAL | win32print.PRINTER_ATTRIBUTE_SHARED,
                    "Priority": 1,
                    "DefaultPriority": 1,
                    "StartTime": 0,
                    "UntilTime": 0,
                    "Status": 0,
                    "AveragePPM": 0
                }
            )
            
            return True
            
        except ImportError:
            logger.error("Módulo win32print não encontrado")
            return False
        except Exception as e:
            logger.error(f"Erro ao instalar impressora virtual no Windows: {str(e)}")
            return False
    
    def _uninstall_windows(self):
        """
        Remove a impressora virtual do Windows
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        if not self._is_admin():
            logger.info("Solicitando privilégios de administrador para remover a impressora virtual")
            
            # Cria um script temporário para remover a impressora
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "uninstall_printer.py")
            
            with open(script_path, 'w') as f:
                f.write(f"""
import os
import sys
import subprocess
import time

# Adiciona o diretório do aplicativo ao caminho de importação
app_dir = {repr(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))}
sys.path.insert(0, app_dir)

from src.virtual_printer.installer import VirtualPrinterInstaller
from src.config import AppConfig

# Inicializa a configuração
config = AppConfig({repr(self.config.data_dir)})

# Remove a impressora
installer = VirtualPrinterInstaller(config)
result = installer._uninstall_windows_impl()

if result:
    print("Impressora virtual removida com sucesso!")
else:
    print("Falha ao remover impressora virtual")

# Aguarda para o usuário ver a mensagem
time.sleep(3)
""")
            
            return self._request_admin(script_path)
        
        # Quando já temos privilégios de administrador
        return self._uninstall_windows_impl()
    
    def _uninstall_windows_impl(self):
        """
        Implementação real da remoção no Windows
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        try:
            import win32print
            
            # Procura a impressora
            printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS)
            for _, printer_name, _, _ in printers:
                if self.PRINTER_NAME in printer_name:
                    # Abre a impressora
                    handle = win32print.OpenPrinter(printer_name)
                    
                    try:
                        # Remove a impressora
                        win32print.DeletePrinter(handle)
                    finally:
                        win32print.ClosePrinter(handle)
                    
                    return True
            
            # Impressora não encontrada
            return True
            
        except ImportError:
            logger.error("Módulo win32print não encontrado")
            return False
        except Exception as e:
            logger.error(f"Erro ao remover impressora virtual do Windows: {str(e)}")
            return False
    
    # Implementações específicas para macOS
    
    def _is_installed_macos(self):
        """
        Verifica se a impressora virtual está instalada no macOS
        
        Returns:
            bool: True se a impressora está instalada
        """
        try:
            # Lista impressoras
            output = subprocess.check_output(["lpstat", "-p"], universal_newlines=True)
            
            # Procura pelo nome da impressora
            return self.PRINTER_NAME in output
            
        except subprocess.CalledProcessError:
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar instalação no macOS: {str(e)}")
            return False
    
    def _install_macos(self):
        """
        Instala a impressora virtual no macOS
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        if not self._is_admin():
            logger.info("Solicitando privilégios de administrador para instalar a impressora virtual")
            
            # Cria um script temporário para instalar a impressora
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "install_printer.py")
            
            with open(script_path, 'w') as f:
                f.write(f"""
import os
import sys
import subprocess
import time

# Adiciona o diretório do aplicativo ao caminho de importação
app_dir = {repr(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))}
sys.path.insert(0, app_dir)

from src.virtual_printer.installer import VirtualPrinterInstaller
from src.config import AppConfig

# Inicializa a configuração
config = AppConfig({repr(self.config.data_dir)})

# Instala a impressora
installer = VirtualPrinterInstaller(config)
result = installer._install_macos_impl()

if result:
    print("Impressora virtual instalada com sucesso!")
else:
    print("Falha ao instalar impressora virtual")

# Aguarda para o usuário ver a mensagem
time.sleep(3)
""")
            
            return self._request_admin(script_path)
        
        # Quando já temos privilégios de administrador
        return self._install_macos_impl()
    
    def _install_macos_impl(self):
        """
        Implementação real da instalação no macOS
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        try:
            # Verifica se já existe
            if self._is_installed_macos():
                return True
            
            # Cria um diretório para armazenar os PDFs
            pdf_dir = self.config.pdf_dir
            os.makedirs(pdf_dir, exist_ok=True)
            
            # No macOS, podemos usar o CUPS para criar uma impressora PDF
            # O backend 'lp' pode ser configurado para "imprimir para arquivo"
            
            # Cria o backend script
            backend_dir = "/usr/libexec/cups/backend"
            our_backend = os.path.join(backend_dir, "loqquei")
            
            with open(our_backend, 'w') as f:
                f.write(f"""#!/bin/bash
# CUPS backend for LoQQuei PDF Printer

# The backend receives these arguments:
# $1 = job ID
# $2 = user
# $3 = title
# $4 = copies
# $5 = options
# $6 = file name (for filter)

# Path to save PDFs
PDF_DIR="{pdf_dir}"

# Make sure the directory exists
mkdir -p "$PDF_DIR"

# Generate a unique filename
TIMESTAMP=$(date +%Y%m%d%H%M%S)
OUTPUT_FILE="$PDF_DIR/$3-$TIMESTAMP.pdf"

# Replace spaces and special characters in filename
OUTPUT_FILE=$(echo "$OUTPUT_FILE" | sed 's/[^a-zA-Z0-9_.-]/_/g')

# Copy stdin to the output file
cat > "$OUTPUT_FILE"

# Return success
exit 0
""")
            
            # Torna o script executável
            os.chmod(our_backend, 0o755)
            
            # Adiciona a impressora usando lpadmin
            subprocess.run([
                "lpadmin",
                "-p", self.PRINTER_NAME,
                "-E",
                "-v", f"loqquei:/",
                "-P", "/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/PrintCore.framework/Versions/A/Resources/Generic.ppd",
                "-o", "printer-is-shared=false"
            ], check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar lpadmin: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro ao instalar impressora virtual no macOS: {str(e)}")
            return False
    
    def _uninstall_macos(self):
        """
        Remove a impressora virtual do macOS
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        if not self._is_admin():
            logger.info("Solicitando privilégios de administrador para remover a impressora virtual")
            
            # Cria um script temporário para remover a impressora
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "uninstall_printer.py")
            
            with open(script_path, 'w') as f:
                f.write(f"""
import os
import sys
import subprocess
import time

# Adiciona o diretório do aplicativo ao caminho de importação
app_dir = {repr(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))}
sys.path.insert(0, app_dir)

from src.virtual_printer.installer import VirtualPrinterInstaller
from src.config import AppConfig

# Inicializa a configuração
config = AppConfig({repr(self.config.data_dir)})

# Remove a impressora
installer = VirtualPrinterInstaller(config)
result = installer._uninstall_macos_impl()

if result:
    print("Impressora virtual removida com sucesso!")
else:
    print("Falha ao remover impressora virtual")

# Aguarda para o usuário ver a mensagem
time.sleep(3)
""")
            
            return self._request_admin(script_path)
        
        # Quando já temos privilégios de administrador
        return self._uninstall_macos_impl()
    
    def _uninstall_macos_impl(self):
        """
        Implementação real da remoção no macOS
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        try:
            # Verifica se existe
            if not self._is_installed_macos():
                return True
            
            # Remove a impressora
            subprocess.run(["lpadmin", "-x", self.PRINTER_NAME], check=True)
            
            # Remove o backend
            backend_path = "/usr/libexec/cups/backend/loqquei"
            if os.path.exists(backend_path):
                os.remove(backend_path)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar lpadmin: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro ao remover impressora virtual do macOS: {str(e)}")
            return False
    
    # Implementações específicas para Linux
    
    def _is_installed_linux(self):
        """
        Verifica se a impressora virtual está instalada no Linux
        
        Returns:
            bool: True se a impressora está instalada
        """
        try:
            # Lista impressoras
            output = subprocess.check_output(["lpstat", "-p"], universal_newlines=True)
            
            # Procura pelo nome da impressora
            return self.PRINTER_NAME in output
            
        except subprocess.CalledProcessError:
            return False
        except Exception as e:
            logger.error(f"Erro ao verificar instalação no Linux: {str(e)}")
            return False
    
    def _install_linux(self):
        """
        Instala a impressora virtual no Linux
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        if not self._is_admin():
            logger.info("Solicitando privilégios de administrador para instalar a impressora virtual")
            
            # Cria um script temporário para instalar a impressora
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "install_printer.py")
            
            with open(script_path, 'w') as f:
                f.write(f"""
import os
import sys
import subprocess
import time

# Adiciona o diretório do aplicativo ao caminho de importação
app_dir = {repr(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))}
sys.path.insert(0, app_dir)

from src.virtual_printer.installer import VirtualPrinterInstaller
from src.config import AppConfig

# Inicializa a configuração
config = AppConfig({repr(self.config.data_dir)})

# Instala a impressora
installer = VirtualPrinterInstaller(config)
result = installer._install_linux_impl()

if result:
    print("Impressora virtual instalada com sucesso!")
else:
    print("Falha ao instalar impressora virtual")

# Aguarda para o usuário ver a mensagem
time.sleep(3)
""")
            
            return self._request_admin(script_path)
        
        # Quando já temos privilégios de administrador
        return self._install_linux_impl()
    
    def _install_linux_impl(self):
        """
        Implementação real da instalação no Linux
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        try:
            # Verifica se já existe
            if self._is_installed_linux():
                return True
            
            # Cria um diretório para armazenar os PDFs
            pdf_dir = self.config.pdf_dir
            os.makedirs(pdf_dir, exist_ok=True)
            
            # No Linux, podemos usar o CUPS para criar uma impressora PDF
            # O backend 'lp' pode ser configurado para "imprimir para arquivo"
            
            # Cria o backend script
            backend_dir = "/usr/lib/cups/backend"
            if not os.path.exists(backend_dir):
                backend_dir = "/usr/libexec/cups/backend"
            
            our_backend = os.path.join(backend_dir, "loqquei")
            
            with open(our_backend, 'w') as f:
                f.write(f"""#!/bin/bash
# CUPS backend for LoQQuei PDF Printer

# The backend receives these arguments:
# $1 = job ID
# $2 = user
# $3 = title
# $4 = copies
# $5 = options
# $6 = file name (for filter)

# Path to save PDFs
PDF_DIR="{pdf_dir}"

# Make sure the directory exists
mkdir -p "$PDF_DIR"

# Generate a unique filename
TIMESTAMP=$(date +%Y%m%d%H%M%S)
OUTPUT_FILE="$PDF_DIR/$3-$TIMESTAMP.pdf"

# Replace spaces and special characters in filename
OUTPUT_FILE=$(echo "$OUTPUT_FILE" | sed 's/[^a-zA-Z0-9_.-]/_/g')

# Copy stdin to the output file
cat > "$OUTPUT_FILE"

# Return success
exit 0
""")
            
            # Torna o script executável
            os.chmod(our_backend, 0o755)
            
            # Adiciona a impressora usando lpadmin
            subprocess.run([
                "lpadmin",
                "-p", self.PRINTER_NAME,
                "-E",
                "-v", f"loqquei:/",
                "-m", "raw",  # Driver raw para aceitar PDF diretamente
                "-o", "printer-is-shared=false"
            ], check=True)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar lpadmin: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro ao instalar impressora virtual no Linux: {str(e)}")
            return False
    
    def _uninstall_linux(self):
        """
        Remove a impressora virtual do Linux
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        if not self._is_admin():
            logger.info("Solicitando privilégios de administrador para remover a impressora virtual")
            
            # Cria um script temporário para remover a impressora
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "uninstall_printer.py")
            
            with open(script_path, 'w') as f:
                f.write(f"""
import os
import sys
import subprocess
import time

# Adiciona o diretório do aplicativo ao caminho de importação
app_dir = {repr(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))}
sys.path.insert(0, app_dir)

from src.virtual_printer.installer import VirtualPrinterInstaller
from src.config import AppConfig

# Inicializa a configuração
config = AppConfig({repr(self.config.data_dir)})

# Remove a impressora
installer = VirtualPrinterInstaller(config)
result = installer._uninstall_linux_impl()

if result:
    print("Impressora virtual removida com sucesso!")
else:
    print("Falha ao remover impressora virtual")

# Aguarda para o usuário ver a mensagem
time.sleep(3)
""")
            
            return self._request_admin(script_path)
        
        # Quando já temos privilégios de administrador
        return self._uninstall_linux_impl()
    
    def _uninstall_linux_impl(self):
        """
        Implementação real da remoção no Linux
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        try:
            # Verifica se existe
            if not self._is_installed_linux():
                return True
            
            # Remove a impressora
            subprocess.run(["lpadmin", "-x", self.PRINTER_NAME], check=True)
            
            # Remove o backend
            for backend_dir in ["/usr/lib/cups/backend", "/usr/libexec/cups/backend"]:
                backend_path = os.path.join(backend_dir, "loqquei")
                if os.path.exists(backend_path):
                    os.remove(backend_path)
            
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar lpadmin: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro ao remover impressora virtual do Linux: {str(e)}")
            return False
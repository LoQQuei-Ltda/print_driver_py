"""
Utilitários específicos para diferentes plataformas (Windows, macOS, Linux)
"""
import os
import sys
import logging
import platform
import subprocess
from pathlib import Path
import shutil
import tempfile
import json

logger = logging.getLogger("VirtualPrinter.PlatformUtils")

def get_platform():
    """Identifica a plataforma atual"""
    system = platform.system().lower()
    if system == "darwin":
        return "macos"
    return system  # windows ou linux

def get_user_documents_dir():
    """Retorna o diretório de documentos do usuário"""
    system = get_platform()
    
    if system == "windows":
        # No Windows, usar a variável de ambiente USERPROFILE
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
    elif system == "macos":
        # No macOS, o diretório de documentos é ~/Documents
        return Path.home() / "Documents"
    else:
        # No Linux, tentar XDG_DOCUMENTS_DIR ou usar ~/Documents
        xdg_config = Path.home() / ".config/user-dirs.dirs"
        if xdg_config.exists():
            try:
                with open(xdg_config, 'r') as f:
                    for line in f:
                        if line.startswith("XDG_DOCUMENTS_DIR="):
                            path = line.split("=")[1].strip().strip('"').replace("$HOME", str(Path.home()))
                            return Path(path)
            except Exception as e:
                logger.warning(f"Erro ao ler diretório XDG: {e}")
        
        # Fallback para ~/Documents
        documents_dir = Path.home() / "Documents"
        documents_dir.mkdir(exist_ok=True)
        return documents_dir

def setup_virtual_printer(output_dir):
    """Configura a impressora virtual específica para a plataforma"""
    system = get_platform()
    
    if system == "windows":
        return _setup_windows_printer(output_dir)
    elif system == "macos":
        return _setup_macos_printer(output_dir)
    else:  # linux
        return _setup_linux_printer(output_dir)

def _setup_windows_printer(output_dir):
    """Configura a impressora virtual no Windows usando PDFCreator ou similar"""
    try:
        # Verificar se o PDFCreator está instalado (em um cenário real)
        # Esta é uma simulação simplificada
        logger.info(f"Configurando impressora virtual no Windows para: {output_dir}")
        
        # Em um cenário real, usar um instalador silencioso ou APIs COM para configurar
        # Aqui apenas simulamos uma configuração bem-sucedida
        
        # Criar arquivo de configuração para a impressora virtual
        printer_config = {
            "Name": "VirtualPDF",
            "OutputDirectory": str(output_dir),
            "AutoSave": True,
            "ShowSaveDialog": False
        }
        
        config_path = Path.home() / ".virtual_printer" / "printer_config.json"
        with open(config_path, 'w') as f:
            json.dump(printer_config, f, indent=2)
        
        logger.info("Impressora virtual configurada com sucesso no Windows")
        return True
    except Exception as e:
        logger.error(f"Erro ao configurar impressora virtual no Windows: {e}")
        return False

def _setup_macos_printer(output_dir):
    """Configura a impressora virtual no macOS usando CUPS-PDF"""
    try:
        logger.info(f"Configurando impressora virtual no macOS para: {output_dir}")
        
        # Verificar se CUPS-PDF está instalado (em um cenário real)
        # E configurá-lo para usar o diretório de saída específico
        
        # Criar arquivo de configuração
        cups_config = f"""
        *PPD-Adobe: "4.3"
        *cupsFilter: "application/pdf 0 -"
        *Destination: "{output_dir}"
        *ShowSaveDialog: No
        *AutoSave: Yes
        """
        
        config_path = Path.home() / ".virtual_printer" / "cups-pdf.conf"
        with open(config_path, 'w') as f:
            f.write(cups_config)
        
        logger.info("Impressora virtual configurada com sucesso no macOS")
        return True
    except Exception as e:
        logger.error(f"Erro ao configurar impressora virtual no macOS: {e}")
        return False

def _setup_linux_printer(output_dir):
    """Configura a impressora virtual no Linux usando CUPS-PDF"""
    try:
        logger.info(f"Configurando impressora virtual no Linux para: {output_dir}")
        
        # Verificar se CUPS-PDF está instalado (em um cenário real)
        # E configurá-lo para usar o diretório de saída específico
        
        # Criar arquivo de configuração
        cups_config = f"""
        Out {output_dir}
        Label VirtualPDF
        DuplexNoTumble 0
        """
        
        config_path = Path.home() / ".virtual_printer" / "cups-pdf.conf"
        with open(config_path, 'w') as f:
            f.write(cups_config)
        
        logger.info("Impressora virtual configurada com sucesso no Linux")
        return True
    except Exception as e:
        logger.error(f"Erro ao configurar impressora virtual no Linux: {e}")
        return False

def send_to_printer(printer_name, file_path):
    """Envia um arquivo para impressão usando o sistema nativo"""
    system = get_platform()
    
    try:
        if system == "windows":
            # No Windows, usar SumatraPDF ou similar para impressão silenciosa
            # Em um cenário real, isso usaria APIs de impressão do Windows
            return True
        
        elif system == "macos":
            # No macOS, usar lpr para impressão
            cmd = ["lpr", "-P", printer_name, file_path]
            subprocess.run(cmd, check=True)
            return True
        
        else:  # linux
            # No Linux, usar lpr para impressão
            cmd = ["lpr", "-P", printer_name, file_path]
            subprocess.run(cmd, check=True)
            return True
    
    except Exception as e:
        logger.error(f"Erro ao enviar arquivo para impressora {printer_name}: {e}")
        return False

def get_system_printers():
    """Retorna a lista de impressoras instaladas no sistema"""
    system = get_platform()
    printers = []
    
    try:
        if system == "windows":
            # No Windows, usar APIs de impressão (simulado)
            printers = ["Printer1", "Printer2"]
        
        elif system == "macos":
            # No macOS, usar lpstat
            cmd = ["lpstat", "-p"]
            output = subprocess.check_output(cmd, text=True)
            for line in output.splitlines():
                if line.startswith("printer"):
                    parts = line.split()
                    if len(parts) > 1:
                        printers.append(parts[1])
        
        else:  # linux
            # No Linux, usar lpstat
            cmd = ["lpstat", "-p"]
            output = subprocess.check_output(cmd, text=True)
            for line in output.splitlines():
                if line.startswith("printer"):
                    parts = line.split()
                    if len(parts) > 1:
                        printers.append(parts[1])
    
    except Exception as e:
        logger.error(f"Erro ao listar impressoras do sistema: {e}")
    
    return printers
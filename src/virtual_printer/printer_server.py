#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servidor de impressora virtual cross-platform
Versão corrigida com melhor suporte para macOS, Windows 7+ e Linux
"""

import os
import sys
import socket
import select
import subprocess
import threading
import time
import platform
import logging
import tempfile
import re
import unicodedata
from pathlib import Path
import getpass
import ctypes
from src.utils.subprocess_utils import run_hidden, popen_hidden, check_output_hidden

logger = logging.getLogger("PrintManagementSystem.VirtualPrinter.Server")

class PrinterServer:
    """Servidor de impressora virtual que converte para PDF"""
    
    def __init__(self, config, on_new_document=None):
        """
        Inicializa o servidor de impressora virtual
        
        Args:
            config: Configuração da aplicação
            on_new_document: Callback chamado quando um novo documento é criado
        """
        self.config = config
        self.on_new_document = on_new_document
        self.printer_name = 'Impressora LoQQuei'
        self.ip = '127.0.0.1'
        self.port = 0  # Será definido automaticamente
        self.buffer_size = 4096  # Aumentado para melhor performance
        self.running = False
        self.keep_going = False
        self.server_thread = None
        self.socket = None
        self.system = platform.system()
        self.system_version = self._get_system_version()
        self.architecture = self._get_architecture()
        self.ghostscript_path = None
        
        # Diretório base para PDFs
        self.base_output_dir = config.pdf_dir
        
        # Criar diretório base
        Path(self.base_output_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Diretório base para PDFs: {self.base_output_dir}")
        
        # Log de informações do sistema
        self._log_system_info()
        
        # Verificar e instalar Ghostscript
        self._init_ghostscript()
    
    def _get_system_version(self):
        """Obtém versão específica do sistema"""
        try:
            if self.system == 'Darwin':  # macOS
                version = platform.mac_ver()[0]
                return version
            elif self.system == 'Windows':
                return platform.release()
            elif self.system == 'Linux':
                try:
                    with open('/etc/os-release', 'r') as f:
                        lines = f.readlines()
                        for line in lines:
                            if line.startswith('PRETTY_NAME='):
                                return line.split('=', 1)[1].strip().strip('"')
                except:
                    pass
                return platform.release()
            else:
                return platform.release()
        except:
            return "unknown"
    
    def _get_architecture(self):
        """Detecta a arquitetura do sistema de forma precisa"""
        machine = platform.machine().lower()
        
        if self.system == 'Darwin':  # macOS
            # Verificar se é Apple Silicon
            try:
                # Método 1: Verificar tradução Rosetta
                result = run_hidden(['sysctl', '-n', 'sysctl.proc_translated'], timeout=5)
                if result.returncode == 0 and result.stdout.strip() == '1':
                    # Rodando sob Rosetta, mas vamos verificar a arquitetura real
                    pass
            except:
                pass
            
            try:
                # Método 2: Verificar arquitetura do processador
                result = run_hidden(['uname', '-m'], timeout=5)
                if result.returncode == 0:
                    uname_machine = result.stdout.strip().lower()
                    if 'arm' in uname_machine or 'aarch64' in uname_machine:
                        return 'apple_silicon'
                    else:
                        return 'intel'
            except:
                pass
            
            # Método 3: Verificar via sysctl
            try:
                result = run_hidden(['sysctl', '-n', 'hw.optional.arm64'], timeout=5)
                if result.returncode == 0 and result.stdout.strip() == '1':
                    return 'apple_silicon'
            except:
                pass
            
            # Fallback baseado no platform.machine()
            if 'arm' in machine or 'aarch64' in machine:
                return 'apple_silicon'
            else:
                return 'intel'
                
        elif 'x86_64' in machine or 'amd64' in machine:
            return 'x86_64'
        elif 'i386' in machine or 'i686' in machine:
            return 'x86'
        elif 'arm' in machine or 'aarch64' in machine:
            return 'arm64'
        else:
            return machine
    
    def _log_system_info(self):
        """Log detalhado das informações do sistema"""
        logger.info("=== INFORMAÇÕES DO SISTEMA ===")
        logger.info(f"Sistema operacional: {self.system}")
        logger.info(f"Versão do sistema: {self.system_version}")
        logger.info(f"Arquitetura: {self.architecture}")
        logger.info(f"Máquina: {platform.machine()}")
        logger.info(f"Processador: {platform.processor()}")
        
        if self.system == 'Darwin':
            try:
                # Informações específicas do macOS
                result = run_hidden(['sw_vers'], timeout=5)
                if result.returncode == 0:
                    logger.info("Detalhes do macOS:")
                    for line in result.stdout.strip().split('\n'):
                        logger.info(f"  {line}")
            except:
                pass
        
        logger.info("===============================")
    
    def _init_ghostscript(self):
        """Inicializa o Ghostscript"""
        logger.info("Verificando instalação do Ghostscript...")
        self.ghostscript_path = self._find_ghostscript()
        if not self.ghostscript_path:
            logger.info("Ghostscript não encontrado. Iniciando instalação...")
            self.ghostscript_path = self._install_portable_ghostscript()
            if self.ghostscript_path:
                logger.info(f"Ghostscript instalado com sucesso em: {self.ghostscript_path}")
            else:
                logger.warning("AVISO: Não foi possível instalar o Ghostscript automaticamente.")
        else:
            logger.info(f"Ghostscript encontrado em: {self.ghostscript_path}")
    
    def _find_ghostscript(self):
        """Localiza o executável do Ghostscript cross-platform"""
        if self.system == 'Windows':
            return self._find_ghostscript_windows()
        elif self.system == 'Darwin':
            return self._find_ghostscript_macos()
        else:  # Linux
            return self._find_ghostscript_linux()
    
    def _find_ghostscript_windows(self):
        """Busca Ghostscript no Windows"""
        executable_names = [
            'gpcl6win64.exe', 'gpcl6win32.exe',
            'gspcl64c.exe', 'gspcl32c.exe',
            'gswin64c.exe', 'gswin32c.exe',
            'gswin.exe', 'gs.exe'
        ]
        
        # Verificar pasta portátil primeiro
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        gs_dir = os.path.join(current_dir, 'gs')
        
        if os.path.exists(gs_dir):
            for root, dirs, files in os.walk(gs_dir):
                for name in executable_names:
                    if name.lower() in [f.lower() for f in files]:
                        real_name = next(f for f in files if f.lower() == name.lower())
                        full_path = os.path.join(root, real_name)
                        if self._test_ghostscript_executable(full_path):
                            return full_path
        
        # Verificar instalações do sistema
        common_dirs = [
            os.environ.get('ProgramFiles', r'C:\Program Files') + r'\gs',
            os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)') + r'\gs',
        ]
        
        for gs_dir in common_dirs:
            if os.path.isdir(gs_dir):
                for root, dirs, files in os.walk(gs_dir):
                    for name in executable_names:
                        if name.lower() in [f.lower() for f in files]:
                            real_name = next(f for f in files if f.lower() == name.lower())
                            full_path = os.path.join(root, real_name)
                            if self._test_ghostscript_executable(full_path):
                                return full_path
        
        return None
    
    def _find_ghostscript_macos(self):
        """Busca Ghostscript no macOS"""
        # Verificar pasta portátil primeiro
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        gs_dir = os.path.join(current_dir, 'gs')
        
        if os.path.exists(gs_dir):
            for root, dirs, files in os.walk(gs_dir):
                if 'gs' in files:
                    gs_path = os.path.join(root, 'gs')
                    if os.access(gs_path, os.X_OK) and self._test_ghostscript_executable(gs_path):
                        return gs_path
        
        # Verificar instalações do Homebrew
        homebrew_paths = []
        if self.architecture == 'apple_silicon':
            homebrew_paths = [
                '/opt/homebrew/bin/gs',  # Homebrew Apple Silicon
                '/usr/local/bin/gs',     # Homebrew Intel no Apple Silicon
            ]
        else:
            homebrew_paths = [
                '/usr/local/bin/gs',     # Homebrew Intel
                '/opt/homebrew/bin/gs',  # Fallback
            ]
        
        for path in homebrew_paths:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                if self._test_ghostscript_executable(path):
                    return path
        
        # Verificar no PATH do sistema
        try:
            result = run_hidden(['which', 'gs'], timeout=5)
            if result.returncode == 0:
                gs_path = result.stdout.strip()
                if self._test_ghostscript_executable(gs_path):
                    return gs_path
        except:
            pass
        
        # Verificar locais comuns de instalação no macOS
        common_paths = [
            '/usr/bin/gs',
            '/usr/local/bin/gs',
            '/opt/local/bin/gs',  # MacPorts
            '/Applications/ghostscript*/bin/gs',
            '/Library/usr/bin/gs',
        ]
        
        import glob
        for path_pattern in common_paths:
            paths = glob.glob(path_pattern)
            for path in paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    if self._test_ghostscript_executable(path):
                        return path
        
        return None
    
    def _find_ghostscript_linux(self):
        """Busca Ghostscript no Linux"""
        # Verificar pasta portátil primeiro
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        gs_dir = os.path.join(current_dir, 'gs')
        
        if os.path.exists(gs_dir):
            for root, dirs, files in os.walk(gs_dir):
                if 'gs' in files:
                    gs_path = os.path.join(root, 'gs')
                    if os.access(gs_path, os.X_OK) and self._test_ghostscript_executable(gs_path):
                        return gs_path
        
        # Verificar no PATH do sistema
        try:
            result = run_hidden(['which', 'gs'], timeout=5)
            if result.returncode == 0:
                gs_path = result.stdout.strip()
                if self._test_ghostscript_executable(gs_path):
                    return gs_path
        except:
            pass
        
        # Verificar locais comuns de instalação
        common_paths = [
            '/usr/bin/gs',
            '/usr/local/bin/gs',
            '/opt/local/bin/gs',
            '/snap/bin/gs',  # Snap packages
            '/usr/local/Cellar/ghostscript/*/bin/gs'  # Se alguém instalou Homebrew no Linux
        ]
        
        import glob
        for path_pattern in common_paths:
            paths = glob.glob(path_pattern)
            for path in paths:
                if os.path.isfile(path) and os.access(path, os.X_OK):
                    if self._test_ghostscript_executable(path):
                        return path
        
        return None
    
    def _test_ghostscript_executable(self, path):
        """Testa se um executável Ghostscript funciona"""
        try:
            if self.system == 'Windows' and os.path.basename(path).lower().startswith('gpcl'):
                process = popen_hidden(
                    [path, '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                stdout, stderr = process.communicate(timeout=5)
                return "PCL" in stdout or "PCL" in stderr or "Ghostscript" in stdout
            else:
                result = run_hidden([path, '--version'], timeout=5)
                return result.returncode == 0
        except:
            return False
    
    def _install_portable_ghostscript(self):
        """Instala versão portátil do Ghostscript baseada no sistema"""
        if self.system == 'Windows':
            return self._install_ghostscript_windows()
        elif self.system == 'Darwin':
            return self._install_ghostscript_macos()
        elif self.system == 'Linux':
            return self._install_ghostscript_linux()
        return None
    
    def _install_ghostscript_windows(self):
        """Instala Ghostscript no Windows"""
        import urllib.request
        import zipfile
        import tempfile
        import shutil
        
        is_64bits = platform.architecture()[0] == '64bit'
        
        # URLs atualizadas para Ghostscript 10.02.1 (versão mais recente)
        if is_64bits:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostpcl-10.02.1-win64.zip"
            expected_exe = "gpcl6win64.exe"
        else:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostpcl-10.02.1-win32.zip"
            expected_exe = "gpcl6win32.exe"
        
        return self._download_and_install_ghostscript(gs_url, expected_exe)
    
    def _install_ghostscript_macos(self):
        """Instala Ghostscript no macOS"""
        # Primeiro, tentar Homebrew
        homebrew_success = self._install_ghostscript_homebrew()
        if homebrew_success:
            return homebrew_success
        
        # Se Homebrew falhou, tentar MacPorts
        macports_success = self._install_ghostscript_macports()
        if macports_success:
            return macports_success
        
        # Se ambos falharam, tentar download direto
        return self._install_ghostscript_macos_direct()
    
    def _install_ghostscript_homebrew(self):
        """Instala Ghostscript via Homebrew no macOS"""
        try:
            # Verificar se Homebrew está instalado
            homebrew_paths = ['/opt/homebrew/bin/brew', '/usr/local/bin/brew']
            brew_cmd = None
            
            for path in homebrew_paths:
                if os.path.exists(path):
                    brew_cmd = path
                    break
            
            if not brew_cmd:
                # Tentar encontrar brew no PATH
                try:
                    result = run_hidden(['which', 'brew'], timeout=5)
                    if result.returncode == 0:
                        brew_cmd = result.stdout.strip()
                except:
                    pass
            
            if brew_cmd:
                logger.info("Homebrew encontrado, tentando instalar Ghostscript...")
                
                # Atualizar Homebrew primeiro
                try:
                    run_hidden([brew_cmd, 'update'], timeout=120)
                except:
                    pass  # Não é crítico se a atualização falhar
                
                # Instalar Ghostscript
                result = run_hidden([brew_cmd, 'install', 'ghostscript'], timeout=300)
                if result.returncode == 0:
                    logger.info("Ghostscript instalado via Homebrew com sucesso")
                    
                    # Encontrar o executável instalado
                    time.sleep(2)
                    return self._find_ghostscript_macos()
                else:
                    logger.warning(f"Falha ao instalar Ghostscript via Homebrew: {result.stderr}")
            else:
                logger.info("Homebrew não encontrado")
                
        except Exception as e:
            logger.warning(f"Erro ao instalar via Homebrew: {e}")
        
        return None
    
    def _install_ghostscript_macports(self):
        """Instala Ghostscript via MacPorts no macOS"""
        try:
            # Verificar se MacPorts está instalado
            if os.path.exists('/opt/local/bin/port'):
                logger.info("MacPorts encontrado, tentando instalar Ghostscript...")
                
                result = run_hidden(['sudo', '/opt/local/bin/port', 'install', 'ghostscript'], timeout=300)
                if result.returncode == 0:
                    logger.info("Ghostscript instalado via MacPorts com sucesso")
                    
                    # Encontrar o executável instalado
                    time.sleep(2)
                    return self._find_ghostscript_macos()
                else:
                    logger.warning(f"Falha ao instalar Ghostscript via MacPorts: {result.stderr}")
            else:
                logger.info("MacPorts não encontrado")
                
        except Exception as e:
            logger.warning(f"Erro ao instalar via MacPorts: {e}")
        
        return None
    
    def _install_ghostscript_macos_direct(self):
        """Instala Ghostscript diretamente no macOS via download"""
        logger.info("Tentando instalação direta do Ghostscript para macOS...")
        
        # URLs corretas para macOS baseadas na arquitetura
        if self.architecture == 'apple_silicon':
            # Para Apple Silicon, usar builds universais ou ARM64
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostscript-10.02.1-darwin-x86_64.pkg"
            logger.info("Usando build para Apple Silicon/ARM64")
        else:
            # Para Intel Mac
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostscript-10.02.1-darwin-x86_64.pkg"
            logger.info("Usando build para Intel Mac")
        
        return self._download_and_install_ghostscript_macos_pkg(gs_url)
    
    def _download_and_install_ghostscript_macos_pkg(self, url):
        """Download e instalação de PKG do macOS"""
        import urllib.request
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp(prefix="gs_install_")
        
        try:
            pkg_path = os.path.join(temp_dir, "ghostscript.pkg")
            
            logger.info(f"Baixando Ghostscript de {url}...")
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; Python)'}
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(pkg_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            # Instalar o PKG
            logger.info("Instalando Ghostscript...")
            result = run_hidden(['sudo', 'installer', '-pkg', pkg_path, '-target', '/'], timeout=180)
            
            if result.returncode == 0:
                logger.info("Ghostscript instalado com sucesso")
                time.sleep(3)
                return self._find_ghostscript_macos()
            else:
                logger.error(f"Falha ao instalar PKG: {result.stderr}")
                return None
            
        except Exception as e:
            logger.error(f"Erro na instalação do PKG: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _install_ghostscript_linux(self):
        """Instala Ghostscript no Linux"""
        # Primeiro, tentar via gerenciador de pacotes
        package_success = self._install_ghostscript_linux_packages()
        if package_success:
            return package_success
        
        # Se falhou, tentar download direto
        return self._install_ghostscript_linux_direct()
    
    def _install_ghostscript_linux_packages(self):
        """Instala Ghostscript via gerenciador de pacotes"""
        logger.info("Tentando instalar Ghostscript via gerenciador de pacotes...")
        
        # Detectar distribuição e gerenciador de pacotes
        install_commands = []
        
        # Debian/Ubuntu (apt)
        if os.path.exists('/usr/bin/apt-get') or os.path.exists('/usr/bin/apt'):
            install_commands.extend([
                ['sudo', 'apt-get', 'update'],
                ['sudo', 'apt-get', 'install', '-y', 'ghostscript'],
            ])
        
        # Red Hat/CentOS/Fedora (yum/dnf)
        elif os.path.exists('/usr/bin/yum'):
            install_commands.append(['sudo', 'yum', 'install', '-y', 'ghostscript'])
        elif os.path.exists('/usr/bin/dnf'):
            install_commands.append(['sudo', 'dnf', 'install', '-y', 'ghostscript'])
        
        # Arch Linux (pacman)
        elif os.path.exists('/usr/bin/pacman'):
            install_commands.append(['sudo', 'pacman', '-S', '--noconfirm', 'ghostscript'])
        
        # openSUSE (zypper)
        elif os.path.exists('/usr/bin/zypper'):
            install_commands.append(['sudo', 'zypper', 'install', '-y', 'ghostscript'])
        
        # Alpine Linux (apk)
        elif os.path.exists('/sbin/apk'):
            install_commands.append(['sudo', 'apk', 'add', 'ghostscript'])
        
        for cmd in install_commands:
            try:
                logger.info(f"Executando: {' '.join(cmd)}")
                result = run_hidden(cmd, timeout=180)
                if result.returncode == 0:
                    logger.info("Ghostscript instalado via gerenciador de pacotes")
                    time.sleep(2)
                    return self._find_ghostscript_linux()
            except Exception as e:
                logger.warning(f"Erro ao executar comando: {e}")
        
        return None
    
    def _install_ghostscript_linux_direct(self):
        """Instala Ghostscript diretamente no Linux via download"""
        logger.info("Tentando instalação direta do Ghostscript para Linux...")
        
        # URLs baseadas na arquitetura
        if self.architecture == 'x86_64':
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostscript-10.02.1-linux-x86_64.tgz"
        elif self.architecture == 'x86':
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostscript-10.02.1-linux-x86.tgz"
        elif self.architecture == 'arm64':
            # Para ARM64, tentar compilar ou usar build genérico
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs10021/ghostscript-10.02.1-linux-x86_64.tgz"
            logger.warning("Usando build x86_64 para ARM64 - pode não funcionar otimamente")
        else:
            logger.warning(f"Arquitetura {self.architecture} não suportada para download direto")
            return None
        
        return self._download_and_install_ghostscript_unix(gs_url, 'gs')
    
    def _download_and_install_ghostscript(self, url, expected_exe):
        """Download e instalação para Windows (ZIP)"""
        import urllib.request
        import zipfile
        import tempfile
        import shutil
        
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        gs_dir = os.path.join(current_dir, 'gs')
        
        temp_dir = tempfile.mkdtemp(prefix="gs_install_")
        
        try:
            zip_path = os.path.join(temp_dir, "ghostscript.zip")
            
            logger.info(f"Baixando Ghostscript de {url}...")
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; Python)'}
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(zip_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            extract_dir = tempfile.mkdtemp(prefix="gs_extract_")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            os.makedirs(gs_dir, exist_ok=True)
            
            extracted_items = os.listdir(extract_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
                src_dir = os.path.join(extract_dir, extracted_items[0])
            else:
                src_dir = extract_dir
            
            for item in os.listdir(src_dir):
                src = os.path.join(src_dir, item)
                dst = os.path.join(gs_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            
            for root, dirs, files in os.walk(gs_dir):
                if expected_exe.lower() in [f.lower() for f in files]:
                    real_name = next(f for f in files if f.lower() == expected_exe.lower())
                    return os.path.join(root, real_name)
            
            return None
            
        except Exception as e:
            logger.error(f"Erro na instalação: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _download_and_install_ghostscript_unix(self, url, expected_exe):
        """Download e instalação para Unix (TAR.GZ)"""
        import urllib.request
        import tarfile
        import tempfile
        import shutil
        
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        gs_dir = os.path.join(current_dir, 'gs')
        
        temp_dir = tempfile.mkdtemp(prefix="gs_install_")
        
        try:
            tar_path = os.path.join(temp_dir, "ghostscript.tgz")
            
            logger.info(f"Baixando Ghostscript de {url}...")
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; Python)'}
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(tar_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            extract_dir = tempfile.mkdtemp(prefix="gs_extract_")
            
            with tarfile.open(tar_path, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
            
            os.makedirs(gs_dir, exist_ok=True)
            
            extracted_items = os.listdir(extract_dir)
            if len(extracted_items) == 1 and os.path.isdir(os.path.join(extract_dir, extracted_items[0])):
                src_dir = os.path.join(extract_dir, extracted_items[0])
            else:
                src_dir = extract_dir
            
            for item in os.listdir(src_dir):
                src = os.path.join(src_dir, item)
                dst = os.path.join(gs_dir, item)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
                    if os.path.basename(item) == expected_exe:
                        os.chmod(dst, 0o755)
            
            for root, dirs, files in os.walk(gs_dir):
                if expected_exe in files:
                    gs_path = os.path.join(root, expected_exe)
                    os.chmod(gs_path, 0o755)
                    return gs_path
            
            return None
            
        except Exception as e:
            logger.error(f"Erro na instalação: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _postscript_to_pdf(self, data):
        """Converte dados PostScript para PDF usando Ghostscript"""
        if not self.ghostscript_path:
            logger.error("Ghostscript não disponível.")
            return None
        
        cmd = [
            self.ghostscript_path,
            '-q', '-dNOPAUSE', '-dBATCH',
            '-sDEVICE=pdfwrite',
            '-sstdout=%stderr',
            '-sOutputFile=-',
            '-f', '-'
        ]
        
        try:
            process = popen_hidden(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            pdf_data, stderr = process.communicate(input=data, timeout=60)
            
            if pdf_data and pdf_data.startswith(b'%PDF-'):
                logger.info(f"Conversão bem-sucedida. Tamanho: {len(pdf_data)} bytes")
                return pdf_data
            else:
                logger.error("Erro: Saída não contém um PDF válido.")
                if stderr:
                    logger.error(f"Stderr do Ghostscript: {stderr.decode('utf-8', errors='ignore')}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao converter PostScript para PDF: {e}")
            return None
    
    def _extract_filename_from_data(self, data):
        """Extrai nome do arquivo dos dados de impressão"""
        try:
            # Detecta o encoding mais provável
            detected_text = self._decode_with_multiple_encodings(data[:2000])  # Aumentado para capturar mais dados
            file_start = detected_text[:20]
            is_pdf = file_start.startswith('%PDF-') or 'PDF-' in file_start
            
            if is_pdf:
                logger.info("Detectado arquivo PDF direto...")
                filename = self._extract_pdf_filename(data)
                if filename:
                    return self._clean_filename(filename)
            
            # Usa o texto decodificado corretamente para todo o arquivo
            ps_text = self._decode_with_multiple_encodings(data)
            filename = self._extract_from_header(ps_text)
            
            if filename:
                return self._clean_filename(filename)
            
            return filename
                
        except Exception as e:
            logger.error(f"Erro ao extrair metadados: {e}")
            return None
    
    def _extract_username_from_data(self, data):
        """Extrai o nome do usuário que enviou o trabalho dos dados de impressão"""
        try:
            # Decodifica o cabeçalho do trabalho
            ps_text = self._decode_with_multiple_encodings(data[:5000])
            
            # Padrões para extrair usuário
            user_patterns = [
                r'@PJL\s+SET\s+USERNAME\s*=\s*"([^"]+)"',
                r'@PJL\s+JOB\s+NAME\s*=\s*"([^"]+)@([^"]+)"',
                r'@PJL\s+COMMENT\s+USER\s*=\s*"([^"]+)"',
                r'%%For:\s*([^\r\n]+)',
                r'/For\s*\(([^)]+)\)',
                r'%%Creator:\s*([^\r\n]+)',
                r'user[=:\s]+([^\r\n\s"]+)',
                r'owner[=:\s]+([^\r\n\s"]+)',
                r'autor[=:\s]+([^\r\n\s"]+)',
                r'autor[=:\s]+"([^"]+)"',
                r'usu.rio[=:\s]+([^\r\n\s"]+)',
                r'usuario[=:\s]+([^\r\n\s"]+)',
            ]
            
            import re
            
            # Tentar cada padrão
            for pattern in user_patterns:
                matches = re.search(pattern, ps_text, re.IGNORECASE)
                if matches:
                    username = matches.group(1).strip()
                    
                    # Limpar nome de usuário - remover caracteres não permitidos
                    username = re.sub(r'[\\/*?:"<>|]', '', username)
                    username = username.strip()
                    
                    # Se for um email, extrair a parte do usuário
                    if '@' in username:
                        username = username.split('@')[0]
                    
                    # Verificar se o nome de usuário é válido (mais de 2 caracteres)
                    if username and len(username) > 2:
                        # Verificar se não é um nome de sistema
                        if username.lower() not in ['sistema', 'system', 'admin', 'administrador', 'administrator', 'documentos']:
                            logger.info(f"Nome de usuário extraído: {username}")
                            return username
            
            # Se não conseguiu extrair um usuário válido, retorna None para usar o diretório padrão
            logger.info("Não foi possível extrair um nome de usuário válido, usando diretório padrão")
            return None
        
        except Exception as e:
            logger.error(f"Erro ao extrair nome de usuário: {e}")
            return None
    
    def _get_current_system_user(self):
        """Obtém o nome do usuário atual do sistema"""
        try:
            return getpass.getuser()
        except:
            return "shared_user"
    
    def _get_user_output_dir(self, username=None):
        """
        Obtém o diretório para salvar PDFs, baseado no usuário ou usando o diretório padrão
        
        Args:
            username (str, optional): Nome do usuário. Se None ou inválido, usa o diretório padrão.
            
        Returns:
            str: Caminho para o diretório de saída
        """
        # Se não foi fornecido um nome de usuário válido, usa o diretório padrão
        if not username:
            logger.info(f"Usando diretório padrão: {self.base_output_dir}")
            return self.base_output_dir
        
        # Tratamento específico por sistema operacional
        if self.system == 'Windows':
            return self._get_user_output_dir_windows(username)
        elif self.system == 'Darwin':  # macOS
            return self._get_user_output_dir_macos(username)
        else:  # Linux
            return self._get_user_output_dir_linux(username)
    
    def _get_user_output_dir_windows(self, username):
        """Obtém diretório de saída para Windows"""
        try:
            # Tenta encontrar o perfil do usuário
            users_dir = os.path.join(os.environ.get('SystemDrive', 'C:'), 'Users')
            user_profile = os.path.join(users_dir, username)
            
            # Se o perfil do usuário existe
            if os.path.exists(user_profile):
                app_data = os.path.join(user_profile, 'AppData', 'Local')
                if os.path.exists(app_data):
                    user_dir = os.path.join(app_data, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                    try:
                        os.makedirs(user_dir, exist_ok=True)
                        logger.info(f"Usando diretório específico do usuário Windows: {user_dir}")
                        return user_dir
                    except PermissionError:
                        logger.warning(f"Sem permissão para criar diretório no AppData do usuário {username}")
                    except Exception as e:
                        logger.warning(f"Erro ao criar diretório do usuário {username}: {e}")
        except Exception as e:
            logger.warning(f"Erro ao processar diretório para usuário {username}: {e}")
        
        # Fallback para diretório base
        logger.info(f"Usando diretório base Windows: {self.base_output_dir}")
        return self.base_output_dir
    
    def _get_user_output_dir_macos(self, username):
        """Obtém diretório de saída para macOS"""
        try:
            # No macOS, os usuários ficam em /Users/
            user_home = os.path.join('/Users', username)
            
            if os.path.exists(user_home):
                # Usar Documents folder do usuário
                documents_dir = os.path.join(user_home, 'Documents')
                if os.path.exists(documents_dir):
                    user_dir = os.path.join(documents_dir, 'Impressora_LoQQuei')
                    try:
                        os.makedirs(user_dir, exist_ok=True)
                        # Verificar permissões
                        if os.access(user_dir, os.W_OK):
                            logger.info(f"Usando diretório específico do usuário macOS: {user_dir}")
                            return user_dir
                        else:
                            logger.warning(f"Sem permissão de escrita no diretório {user_dir}")
                    except PermissionError:
                        logger.warning(f"Sem permissão para criar diretório no Documents do usuário {username}")
                    except Exception as e:
                        logger.warning(f"Erro ao criar diretório do usuário {username}: {e}")
                
                # Tentar Application Support como alternativa
                app_support = os.path.join(user_home, 'Library', 'Application Support')
                if os.path.exists(app_support):
                    user_dir = os.path.join(app_support, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                    try:
                        os.makedirs(user_dir, exist_ok=True)
                        if os.access(user_dir, os.W_OK):
                            logger.info(f"Usando diretório Application Support do usuário macOS: {user_dir}")
                            return user_dir
                    except Exception as e:
                        logger.warning(f"Erro ao criar diretório Application Support: {e}")
        except Exception as e:
            logger.warning(f"Erro ao processar diretório para usuário macOS {username}: {e}")
        
        # Fallback para diretório base
        logger.info(f"Usando diretório base macOS: {self.base_output_dir}")
        return self.base_output_dir
    
    def _get_user_output_dir_linux(self, username):
        """Obtém diretório de saída para Linux"""
        try:
            # No Linux, os usuários ficam em /home/
            user_home = os.path.join('/home', username)
            
            if os.path.exists(user_home):
                # Tentar usar Documents primeiro
                documents_dir = os.path.join(user_home, 'Documents')
                if os.path.exists(documents_dir):
                    user_dir = os.path.join(documents_dir, 'Impressora_LoQQuei')
                    try:
                        os.makedirs(user_dir, exist_ok=True)
                        if os.access(user_dir, os.W_OK):
                            logger.info(f"Usando diretório específico do usuário Linux: {user_dir}")
                            return user_dir
                    except Exception as e:
                        logger.warning(f"Erro ao criar diretório Documents: {e}")
                
                # Tentar .local/share como alternativa (XDG)
                local_share = os.path.join(user_home, '.local', 'share')
                if os.path.exists(local_share):
                    user_dir = os.path.join(local_share, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                    try:
                        os.makedirs(user_dir, exist_ok=True)
                        if os.access(user_dir, os.W_OK):
                            logger.info(f"Usando diretório .local/share do usuário Linux: {user_dir}")
                            return user_dir
                    except Exception as e:
                        logger.warning(f"Erro ao criar diretório .local/share: {e}")
        except Exception as e:
            logger.warning(f"Erro ao processar diretório para usuário Linux {username}: {e}")
        
        # Fallback para diretório base
        logger.info(f"Usando diretório base Linux: {self.base_output_dir}")
        return self.base_output_dir
    
    def _decode_with_multiple_encodings(self, data):
        """Tenta decodificar dados com múltiplos encodings - Versão melhorada"""
        # Se os dados são muito pequenos, tenta como string
        if len(data) < 20:
            try:
                return data.decode('utf-8', errors='replace')
            except:
                return str(data)
        
        # Lista expandida de encodings
        encodings = [
            'utf-8',           # UTF-8 (padrão)
            'utf-8-sig',       # UTF-8 com BOM
            'utf-16',          # UTF-16 (Windows Unicode)
            'utf-16-le',       # UTF-16 Little Endian
            'utf-16-be',       # UTF-16 Big Endian
            'cp1252',          # Windows-1252 (Western Europe)
            'latin1',          # ISO-8859-1 (Western Europe)
            'cp850',           # DOS Western Europe
            'cp437',           # DOS US
            'cp1251',          # Windows-1251 (Cyrillic)
            'cp1250',          # Windows-1250 (Central Europe)
            'cp1253',          # Windows-1253 (Greek)
            'cp1254',          # Windows-1254 (Turkish)
            'cp1255',          # Windows-1255 (Hebrew)
            'cp1256',          # Windows-1256 (Arabic)
            'cp1257',          # Windows-1257 (Baltic)
            'cp1258',          # Windows-1258 (Vietnamese)
            'iso-8859-2',      # ISO-8859-2 (Central/Eastern Europe)
            'iso-8859-3',      # ISO-8859-3 (South European)
            'iso-8859-4',      # ISO-8859-4 (North European)
            'iso-8859-5',      # ISO-8859-5 (Cyrillic)
            'iso-8859-6',      # ISO-8859-6 (Arabic)
            'iso-8859-7',      # ISO-8859-7 (Greek)
            'iso-8859-8',      # ISO-8859-8 (Hebrew)
            'iso-8859-9',      # ISO-8859-9 (Turkish)
            'iso-8859-10',     # ISO-8859-10 (Nordic)
            'iso-8859-11',     # ISO-8859-11 (Thai)
            'iso-8859-13',     # ISO-8859-13 (Baltic)
            'iso-8859-14',     # ISO-8859-14 (Celtic)
            'iso-8859-15',     # ISO-8859-15 (Western Europe with Euro)
            'iso-8859-16',     # ISO-8859-16 (South-Eastern Europe)
            'koi8-r',          # KOI8-R (Russian)
            'koi8-u',          # KOI8-U (Ukrainian)
            'mac-roman',       # MacRoman
            'mac-cyrillic',    # MacCyrillic
            'ascii',           # ASCII básico (fallback)
        ]
        
        # Detecta BOM (Byte Order Mark) para UTF
        if data.startswith(b'\xff\xfe'):
            # UTF-16 LE BOM
            try:
                return data.decode('utf-16-le', errors='replace')
            except:
                pass
        elif data.startswith(b'\xfe\xff'):
            # UTF-16 BE BOM
            try:
                return data.decode('utf-16-be', errors='replace')
            except:
                pass
        elif data.startswith(b'\xef\xbb\xbf'):
            # UTF-8 BOM
            try:
                return data[3:].decode('utf-8', errors='replace')
            except:
                pass
        
        # Estratégia 1: Tentativa estrita com cada encoding
        best_encoding = None
        best_score = -1
        
        for encoding in encodings:
            try:
                decoded = data.decode(encoding, errors='strict')
                
                # Avalia a qualidade da decodificação
                score = self._evaluate_text_quality(decoded)
                
                if score > best_score:
                    best_score = score
                    best_encoding = encoding
                    
                    # Se a pontuação é muito alta, usamos imediatamente
                    if score > 0.95:
                        logger.debug(f"Decodificação de alta qualidade com {encoding} (score: {score:.2f})")
                        return decoded
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Estratégia 2: Se encontramos um encoding com boa pontuação, use-o
        if best_encoding and best_score > 0.75:
            logger.debug(f"Usando encoding {best_encoding} com score {best_score:.2f}")
            return data.decode(best_encoding, errors='replace')
        
        # Estratégia 3: Análise de frequência de bytes para detectar encoding
        # Muitos PDFs e PS usam encoding específico para caracteres não-ASCII
        if self._is_likely_pdf_or_ps(data):
            encodings_to_try = ['cp1252', 'latin1', 'utf-8']
            for enc in encodings_to_try:
                try:
                    decoded = data.decode(enc, errors='replace')
                    if '�' not in decoded[:1000]:  # Verifica se não há caracteres de substituição no início
                        logger.debug(f"Decodificado como possível PDF/PS usando {enc}")
                        return decoded
                except:
                    continue
        
        # Fallback final: UTF-8 com substituição de erros
        logger.warning("Todas as estratégias de decodificação falharam, usando UTF-8 com substituições")
        return data.decode('utf-8', errors='replace')

    def _evaluate_text_quality(self, text):
        """Avalia a qualidade de um texto decodificado com pontuação de 0 a 1"""
        if not text:
            return 0
        
        # Inicializa contadores
        total_chars = len(text)
        printable_chars = 0
        alpha_chars = 0
        digit_chars = 0
        punct_chars = 0
        whitespace_chars = 0
        control_chars = 0
        replacement_chars = 0
        
        import string
        
        # Conta diferentes tipos de caracteres
        for c in text:
            if c in string.printable:
                printable_chars += 1
                
            if c.isalpha():
                alpha_chars += 1
            elif c.isdigit():
                digit_chars += 1
            elif c in string.punctuation:
                punct_chars += 1
            elif c.isspace():
                whitespace_chars += 1
            elif ord(c) < 32 and c not in '\t\n\r':
                control_chars += 1
            
            if c == '�':
                replacement_chars += 1
        
        # Calcula proporções
        control_ratio = control_chars / total_chars if total_chars > 0 else 1
        replacement_ratio = replacement_chars / total_chars if total_chars > 0 else 1
        printable_ratio = printable_chars / total_chars if total_chars > 0 else 0
        text_ratio = (alpha_chars + digit_chars + punct_chars + whitespace_chars) / total_chars if total_chars > 0 else 0
        
        # Penaliza fortemente os caracteres de substituição
        score = 1.0
        score -= replacement_ratio * 2  # Penaliza caracteres de substituição
        score -= control_ratio          # Penaliza caracteres de controle
        score += printable_ratio * 0.3  # Bonifica caracteres imprimíveis
        score += text_ratio * 0.7       # Bonifica texto real
        
        # Ajusta para 0-1
        score = max(0, min(1, score))
        
        return score

    def _is_likely_pdf_or_ps(self, data):
        """Verifica se os dados parecem ser um PDF ou PostScript"""
        # Verifica assinaturas comuns
        if len(data) < 10:
            return False
        
        # Assinaturas comuns
        signatures = [
            b'%PDF-',          # PDF
            b'%!PS-Adobe-',    # PostScript
            b'%!PS',           # PostScript simplificado
            b'@PJL',           # HP Printer Job Language
            b'\x1B%-12345X',   # HP PCL
        ]
        
        # Verifica o início dos dados
        for sig in signatures:
            if data.startswith(sig):
                return True
        
        # Busca assinaturas em qualquer lugar nos primeiros bytes
        first_1k = data[:1024] if len(data) > 1024 else data
        for sig in signatures:
            if sig in first_1k:
                return True
        
        return False
    
    def _clean_filename(self, filename):
        """Limpa e normaliza o nome do arquivo mantendo caracteres especiais - Versão melhorada"""
        if not filename:
            return None
        
        # Remove espaços extras
        filename = filename.strip()
        
        # Normaliza caracteres Unicode (forma NFC - composta)
        import unicodedata
        filename = unicodedata.normalize('NFC', filename)
        
        # Caracteres problemáticos em sistemas de arquivo
        # Apenas os caracteres realmente impossíveis de usar em qualquer sistema
        problematic_chars = '<>:"|?*\\/\x00'
        
        # Substitui caracteres problemáticos por aproximações seguras em vez de removê-los
        replacements = {
            '<': '＜',  # Versão de largura total
            '>': '＞',  # Versão de largura total
            ':': '：',  # Versão de largura total
            '"': '＂',  # Versão de largura total
            '|': '｜',  # Versão de largura total
            '?': '？',  # Versão de largura total
            '*': '＊',  # Versão de largura total
            '\\': '＼', # Versão de largura total
            '/': '／',  # Versão de largura total
            '\x00': '',  # Nulo não tem substituto
        }
        
        # Aplica substituições
        for char, replacement in replacements.items():
            filename = filename.replace(char, replacement)
        
        # Remove múltiplos espaços
        import re
        filename = re.sub(r'\s+', ' ', filename)
        
        # Remove espaços no início e fim
        filename = filename.strip()
        
        # Se ficou vazio, retorna None
        if not filename:
            return None
        
        # Limita o tamanho (sistemas de arquivo têm limites)
        max_length = 200  # Deixa espaço para extensão e sufixos
        if len(filename) > max_length:
            # Tenta preservar a extensão
            if '.' in filename:
                name_part, ext_part = filename.rsplit('.', 1)
                available_length = max_length - len(ext_part) - 1  # -1 para o ponto
                filename = name_part[:available_length] + '.' + ext_part
            else:
                filename = filename[:max_length]
        
        return filename

    def _extract_pdf_filename(self, data):
        """Extrai o nome do arquivo diretamente de dados PDF - Versão melhorada"""
        try:
            # Primeiro, tenta decodificar como texto com métodos melhorados
            pdf_text = self._decode_with_multiple_encodings(data)
            
            # Padrões para metadados PDF
            title_patterns = [
                # Padrões básicos
                r'/Title\s*\(([^)]+)\)',
                r'/Title\s*<([^>]+)>',
                r'/Filename\s*\(([^)]+)\)',
                r'/DocumentName\s*\(([^)]+)\)',
                r'/Subject\s*\(([^)]+)\)',
                
                # Padrões com escape
                r'/Title\s*\(([^)\\]+(?:\\.[^)\\]*)*)\)',
                
                # Padrões com hex encoding
                r'/Title\s*<([0-9A-Fa-f]+)>',
                r'/DocumentName\s*<([0-9A-Fa-f]+)>',
                
                # Padrões XMP
                r'<dc:title>\s*<rdf:Alt>\s*<rdf:li[^>]*>([^<]+)</rdf:li>',
                r'<xmp:Title>([^<]+)</xmp:Title>',
                r'<dc:title>([^<]+)</dc:title>',
                
                # Padrões de informações do documento
                r'/Info\s*<<[^>]*?/Title\s*\(([^)]+)\)',
                r'/Creator\s*\(([^)]+)\)',
                r'/Producer\s*\(([^)]+)\)',
            ]
            
            import re
            
            for pattern in title_patterns:
                matches = re.findall(pattern, pdf_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    for match in matches:
                        title = match.strip()
                        
                        # Se é hex string, converte - algoritmo melhorado
                        if re.match(r'^[0-9A-Fa-f]+$', title) and len(title) % 2 == 0:
                            try:
                                # Tenta diferentes interpretações da string hex
                                decoded_versions = []
                                
                                # UTF-16BE (comum em PDFs)
                                try:
                                    hex_bytes = bytes.fromhex(title)
                                    if title.upper().startswith('FEFF'):
                                        # BOM UTF-16BE
                                        decoded = hex_bytes[2:].decode('utf-16-be', errors='replace')
                                    else:
                                        decoded = hex_bytes.decode('utf-16-be', errors='replace')
                                    if decoded and not all(c == '�' for c in decoded):
                                        decoded_versions.append(decoded)
                                except:
                                    pass
                                    
                                # UTF-8
                                try:
                                    hex_bytes = bytes.fromhex(title)
                                    decoded = hex_bytes.decode('utf-8', errors='replace')
                                    if decoded and not all(c == '�' for c in decoded):
                                        decoded_versions.append(decoded)
                                except:
                                    pass
                                    
                                # CP1252/Latin1 (comum em documentos antigos)
                                try:
                                    hex_bytes = bytes.fromhex(title)
                                    decoded = hex_bytes.decode('cp1252', errors='replace')
                                    if decoded and not all(c == '�' for c in decoded):
                                        decoded_versions.append(decoded)
                                except:
                                    pass
                                
                                # Escolhe o melhor resultado
                                if decoded_versions:
                                    # Ordena por qualidade da decodificação
                                    decoded_versions.sort(key=lambda x: self._evaluate_text_quality(x), reverse=True)
                                    title = decoded_versions[0]
                            except:
                                continue
                        
                        # Remove caracteres de escape de forma robusta
                        title = re.sub(r'\\(.)', r'\1', title)
                        
                        # Se parece um nome de arquivo válido
                        if title and len(title) > 2 and not title.isspace():
                            logger.info(f"Nome extraído do PDF (padrão {pattern}): {title}")
                            return title
                
            # Busca por nomes de arquivo com extensões conhecidas em qualquer lugar do PDF
            file_extensions = ['.pdf', '.txt', '.doc', '.xls', '.xlsx', '.docx', '.pptx', '.ppt', '.rtf', '.odt', '.ods',
                            '.jpg', '.jpeg', '.png', '.gif', '.csv', '.xml', '.html', '.zip']
            for ext in file_extensions:
                # Padrão mais abrangente que captura nomes com caracteres especiais
                pattern = r'([^\\/\s:"\'<>|*?]{3,}' + re.escape(ext) + r')'
                matches = re.findall(pattern, pdf_text, re.IGNORECASE | re.UNICODE)
                if matches:
                    for match in matches:
                        # Filtra matches que parecem nomes válidos
                        if len(match) > len(ext) + 2 and not match.startswith('.'):
                            logger.info(f"Nome de arquivo extraído do PDF por extensão ({ext}): {match}")
                            return match
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao extrair nome do PDF: {e}")
            return None

    def _extract_from_header(self, ps_text):
        """Extrai o nome do arquivo do cabeçalho PS usando múltiplos métodos - Versão melhorada"""
        # Verifica se há cabeçalho antes do PostScript
        header_text = ps_text.split('%!PS-', 1)[0] if '%!PS-' in ps_text else ps_text[:4000]
        
        logger.debug("Analisando cabeçalho do trabalho...")
        logger.debug(f"Primeiros 500 caracteres do cabeçalho: {header_text[:500]}")
        
        filename = None
        
        import re
        
        # Função interna para limpar nomes extraídos
        def clean_extracted_name(value):
            if not value:
                return None
                
            # Remove caracteres de controle e espaços extras
            value = re.sub(r'[\x00-\x1F\x7F]', '', value).strip()
            
            # Remove aspas se existirem
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
                
            # Se for um caminho, extrair apenas o nome do arquivo
            if '\\' in value or '/' in value:
                extracted_name = re.split(r'[/\\]', value)[-1]
            else:
                extracted_name = value
                
            return extracted_name
        
        # ----- PADRÕES MELHORADOS PARA IMPRESSÃO -----
        ms_office_patterns = [
            ('@PJL SET JOBNAME="', '"'),
            ('@PJL JOB NAME="', '"'),
            ('@PJL JOB FILE="', '"'),
            ('@PJL COMMENT DocumentName="', '"'),
            ('@PJL COMMENT "document="', '"'),
            ('@PJL SET FILENAME="', '"'),
            ('@PJL COMMENT FileName="', '"'),
            ('@PJL SET DOCNAME="', '"'),
            ('@PJL COMMENT "title="', '"'),
            ('@PJL COMMENT title="', '"'),
            ('%%Title: ', '\n'),
            ('%%DocumentName: ', '\n'),
            ('%%For: ', '\n'),
        ]
        
        # Primeiro tenta padrões de delimitadores
        for start_pattern, end_pattern in ms_office_patterns:
            if start_pattern in header_text:
                logger.debug(f"Padrão encontrado: {start_pattern}")
                start_idx = header_text.find(start_pattern) + len(start_pattern)
                if end_pattern == '\n':
                    end_idx = header_text.find('\n', start_idx)
                    if end_idx == -1:
                        end_idx = header_text.find('\r', start_idx)
                    if end_idx == -1:
                        end_idx = len(header_text)
                else:
                    end_idx = header_text.find(end_pattern, start_idx)
                
                if end_idx > start_idx:
                    value = header_text[start_idx:end_idx].strip()
                    logger.debug(f"Valor extraído: {value}")
                    
                    extracted_name = clean_extracted_name(value)
                    
                    # Verifica se parece ser um nome de arquivo válido
                    if extracted_name and len(extracted_name) > 2:
                        # Aceita nomes com ou sem extensão
                        if '.' in extracted_name or len(extracted_name) > 5:
                            filename = extracted_name
                            logger.info(f"Nome de arquivo extraído (padrão {start_pattern}): {filename}")
                            break
        
        # Se não encontrou com os padrões de delimitadores, tenta regex mais abrangentes
        if not filename:
            logger.debug("Tentando padrões regex melhorados...")
            
            regex_patterns = [
                # PostScript DSC comments - padrões melhorados
                r'%%Title:\s*(.+?)(?:\n|\r|$)',
                r'%%DocumentName:\s*(.+?)(?:\n|\r|$)',
                r'%%For:\s*(.+?)(?:\n|\r|$)',
                
                # PJL patterns sem aspas - mais abrangentes
                r'@PJL\s+SET\s+JOBNAME\s*=\s*([^\s\n\r"]+)',
                r'@PJL\s+JOB\s+NAME\s*=\s*([^\s\n\r"]+)',
                r'@PJL\s+SET\s+DOCNAME\s*=\s*([^\s\n\r"]+)',
                
                # PJL patterns com aspas - busca mais robusta
                r'@PJL[^\n\r"]*"([^"]+)"',
                
                # PostScript title/name
                r'/Title\s*\(([^)]+(?:\\\)[^)]*)*)\)',  # Lida com parênteses escapados
                r'/DocumentName\s*\(([^)]+(?:\\\)[^)]*)*)\)',
                r'/Creator\s*\(([^)]+(?:\\\)[^)]*)*)\)',
                
                # Caminhos de arquivo em qualquer lugar - mais abrangentes
                r'[\\/]([^\\/\s"\'<>|*?:]{3,}\.[a-zA-Z0-9]{2,6})(?=[\s\n\r"\'<>|*?:]|$)',
                
                # Nomes que parecem arquivos (com pelo menos uma extensão comum)
                r'\b([a-zA-ZÀ-ÿ0-9\s_\-!#$%&\'()\-@^`{}~,;=+\[\]]{3,}\.[a-zA-Z0-9]{2,6})\b',
            ]
            
            for pattern in regex_patterns:
                matches = re.findall(pattern, ps_text, re.MULTILINE | re.UNICODE | re.IGNORECASE)
                if matches:
                    for match in matches:
                        extracted_name = clean_extracted_name(match)
                        
                        logger.debug(f"Regex match encontrado: {extracted_name}")
                        
                        # Verifica se é um nome válido
                        if extracted_name and len(extracted_name) > 2:
                            # Filtra nomes que são claramente inválidos
                            invalid_names = ['microsoft', 'windows', 'system', 'temp', 'tmp', 'default']
                            if not any(invalid.lower() in extracted_name.lower() for invalid in invalid_names):
                                filename = extracted_name
                                logger.info(f"Nome de arquivo extraído por regex: {filename}")
                                break
                    
                    if filename:
                        break
        
        # Se ainda não encontrou, tenta buscar extensões conhecidas
        if not filename:
            logger.debug("Buscando por extensões conhecidas...")
            
            # Lista expandida de extensões
            extensions = [
                '.pdf', '.txt', '.doc', '.xls', '.xlsx', '.docx', '.pptx', '.ppt', 
                '.rtf', '.odt', '.ods', '.odp', '.csv', '.xml', '.html', '.htm',
                '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.svg',
                '.zip', '.rar', '.7z', '.tar', '.gz',
                '.mp3', '.mp4', '.avi', '.mov', '.wmv',
                '.exe', '.msi', '.deb', '.rpm'
            ]
            
            for ext in extensions:
                # Padrão que captura caracteres Unicode e especiais
                pattern = r'([^\\/\s"\'<>|*?:]{2,}' + re.escape(ext) + r')'
                matches = re.findall(pattern, ps_text, re.IGNORECASE | re.UNICODE)
                if matches:
                    # Filtra e ordena por qualidade
                    valid_matches = []
                    for match in matches:
                        extracted_name = clean_extracted_name(match)
                        if extracted_name and len(extracted_name) > len(ext) + 1 and not extracted_name.startswith('.'):
                            # Pontuação: prefer nomes mais longos e com caracteres "normais"
                            score = len(extracted_name)
                            if any(c.isalpha() for c in extracted_name):
                                score += 10
                            if any(c.isdigit() for c in extracted_name):
                                score += 5
                            valid_matches.append((score, extracted_name))
                    
                    if valid_matches:
                        # Pega o match com maior pontuação
                        valid_matches.sort(reverse=True)
                        filename = valid_matches[0][1]
                        logger.info(f"Nome de arquivo extraído por extensão ({ext}): {filename}")
                        break
        
        return filename
    
    def _save_pdf(self, pdf_data, title=None, author=None, filename=None):
        """Salva os dados PDF com verificação inteligente de duplicatas - VERSÃO MODIFICADA"""
        if not pdf_data:
            logger.error("Nenhum dado PDF para salvar.")
            return None
        
        try:
            # Extrai o nome do usuário que enviou o trabalho (pode ser None)
            username = self._extract_username_from_data(pdf_data)
            
            # Obtém o diretório de saída (diretório base ou específico do usuário)
            output_dir = self._get_user_output_dir(username)
            
            # Verifica se tem permissão de escrita no diretório
            if not os.access(output_dir, os.W_OK):
                logger.warning(f"Sem permissão de escrita em {output_dir}")
                # Tenta usar um diretório alternativo
                import tempfile
                output_dir = tempfile.gettempdir()
                logger.info(f"Usando diretório alternativo: {output_dir}")
            
            # Calcula hash para verificação inteligente de duplicatas
            import hashlib
            pdf_hash = hashlib.md5(pdf_data).hexdigest()
            
            # Determinar nome do arquivo
            if filename:
                base_name = filename
            elif title:
                base_name = title
            else:
                data_br = time.strftime('%d-%m-%Y')
                hora_br = time.strftime('%H-%M-%S')
                base_name = f"documento_{data_br}_{hora_br}"
            
            # Limpa o nome do arquivo
            base_name = self._clean_filename(base_name) or f"documento_{time.strftime('%d-%m-%Y_%H-%M-%S')}"
            
            # Garante extensão .pdf
            if not base_name.lower().endswith('.pdf'):
                base_name += '.pdf'
            
            # Caminho completo inicial
            output_path = os.path.join(output_dir, base_name)
            
            # Só considera duplicata se for o mesmo arquivo E mesmo nome E criado recentemente (< 5 minutos)
            try:
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        existing_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Se é o mesmo conteúdo e foi criado recentemente, é duplicata
                    file_stat = os.stat(output_path)
                    time_diff = time.time() - file_stat.st_mtime
                    
                    if existing_hash == pdf_hash and time_diff < 300:  # 5 minutos
                        logger.info(f"Arquivo duplicado recente detectado: {output_path}")
                        return output_path
            except Exception as e:
                logger.debug(f"Erro ao verificar duplicata: {e}")
            
            # Sistema de nomenclatura para evitar sobrescrever
            counter = 1
            original_output_path = output_path
            while os.path.exists(output_path):
                name_parts = base_name.rsplit('.', 1)
                if len(name_parts) == 2:
                    name_without_ext = name_parts[0]
                    extension = name_parts[1]
                else:
                    name_without_ext = base_name
                    extension = ""
                
                # Sistema de nomenclatura mais claro
                if counter == 1:
                    new_name = f"{name_without_ext}_v2"
                else:
                    new_name = f"{name_without_ext}_v{counter + 1}"
                
                if extension:
                    new_name += f".{extension}"
                    
                output_path = os.path.join(output_dir, new_name)
                counter += 1
                
                # Evita loop infinito
                if counter > 100:
                    # Usa timestamp único como último recurso
                    timestamp = int(time.time() * 1000)
                    unique_name = f"{name_without_ext}_{timestamp}"
                    if extension:
                        unique_name += f".{extension}"
                    output_path = os.path.join(output_dir, unique_name)
                    break
            
            # Garante que o diretório existe
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            # Operação atômica para salvar
            temp_path = output_path + '.tmp'
            try:
                # Salvar temporariamente
                with open(temp_path, 'wb') as f:
                    f.write(pdf_data)
                
                # Move atomicamente
                os.rename(temp_path, output_path)
                
            except Exception as e:
                # Remove arquivo temporário em caso de erro
                if os.path.exists(temp_path):
                    try:
                        os.remove(temp_path)
                    except:
                        pass
                raise e
            
            logger.info(f"PDF salvo em: {output_path}")
            
            # Chamar callback se fornecido
            if self.on_new_document:
                try:
                    from src.models.document import Document
                    doc = Document.from_file(output_path)
                    self.on_new_document(doc)
                except Exception as e:
                    logger.error(f"Erro ao processar callback: {e}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"Erro ao salvar PDF: {e}")
            
            # Tentativa de fallback para o diretório base
            try:
                fallback_filename = f"documento_{time.strftime('%d-%m-%Y_%H-%M-%S')}_{int(time.time() * 1000)}.pdf"
                fallback_path = os.path.join(self.base_output_dir, fallback_filename)
                
                # Garante que o diretório existe
                os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
                
                with open(fallback_path, 'wb') as f:
                    f.write(pdf_data)
                logger.info(f"PDF salvo em fallback: {fallback_path}")
                
                # Callback para o documento salvo em fallback
                if self.on_new_document:
                    try:
                        from src.models.document import Document
                        doc = Document.from_file(fallback_path)
                        self.on_new_document(doc)
                    except Exception as e:
                        logger.error(f"Erro ao processar callback para fallback: {e}")
                
                return fallback_path
            except Exception as fallback_error:
                logger.error(f"Erro ao salvar PDF no fallback: {fallback_error}")
                return None
    
    def start(self):
        """Inicia o servidor de impressão"""
        if self.running:
            return True
        
        try:
            # Criar socket ANTES de iniciar a thread
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            
            # Configurações do socket
            if self.system == 'Windows':
                # No Windows, use SO_EXCLUSIVEADDRUSE em vez de SO_REUSEADDR
                try:
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
                except AttributeError:
                    # Se não disponível, usa SO_REUSEADDR mesmo
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            else:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Tentar fazer bind
            self.socket.bind((self.ip, self.port))
            
            # Obter a porta real atribuída
            ip, port = self.socket.getsockname()
            self.port = port
            
            # Configurar socket para modo non-blocking
            self.socket.setblocking(False)
            
            # Iniciar listen
            self.socket.listen(5)
            
            logger.info(f'Socket criado e configurado em {ip}:{port}')
            
            # Agora que o socket está pronto, marcar como running e iniciar thread
            self.running = True
            self.keep_going = True
            
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            # Aguardar um pouco para garantir que a thread iniciou
            time.sleep(0.5)
            
            # Verificar se a thread está rodando
            if not self.server_thread.is_alive():
                self.running = False
                self.keep_going = False
                logger.error("Thread do servidor não iniciou corretamente")
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar servidor: {e}")
            self.running = False
            self.keep_going = False
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            return False
    
    def stop(self):
        """Para o servidor de impressão"""
        logger.info("Parando servidor de impressão...")
        self.keep_going = False
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None
        
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=5)
            if self.server_thread.is_alive():
                logger.warning("Thread do servidor não parou no tempo esperado")
        
        logger.info("Servidor de impressão parado")
    
    def get_server_info(self):
        """Retorna informações do servidor"""
        if self.socket:
            try:
                ip, port = self.socket.getsockname()
                return {'ip': ip, 'port': port, 'running': self.running}
            except:
                pass
        return {'ip': self.ip, 'port': self.port, 'running': self.running}
    
    def _run_server(self):
        """Executa o servidor em thread separada"""
        logger.info("Thread do servidor iniciada")
        
        try:
            while self.keep_going:
                try:
                    # Usar select com timeout para verificar se há conexões
                    readable, _, _ = select.select([self.socket], [], [], 1.0)
                    
                    if not readable:
                        continue
                    
                    # Aceitar conexão
                    try:
                        conn, addr = self.socket.accept()
                        logger.info(f'Conexão recebida de {addr}')
                        
                        # Configurar timeout para a conexão
                        conn.settimeout(30.0)
                        
                        # Processar em thread separada
                        handler_thread = threading.Thread(
                            target=self._handle_connection,
                            args=(conn, addr),
                            daemon=True
                        )
                        handler_thread.start()
                        
                    except socket.error as e:
                        if hasattr(e, 'errno') and e.errno == 10035:  # WSAEWOULDBLOCK no Windows
                            continue
                        else:
                            logger.error(f"Erro ao aceitar conexão: {e}")
                    
                except Exception as e:
                    if self.keep_going:
                        logger.error(f"Erro no loop do servidor: {e}")
                        time.sleep(1)
                        
        except Exception as e:
            logger.error(f"Erro crítico no servidor: {e}")
        finally:
            logger.info("Thread do servidor finalizando")
    
    def _handle_connection(self, conn, addr):
        """Processa uma conexão individual"""
        logger.info(f'Processando conexão de {addr}')
        
        try:
            # Receber dados
            buffer = []
            total_received = 0
            
            while True:
                try:
                    raw = conn.recv(self.buffer_size)
                    if not raw:
                        break
                    buffer.append(raw)
                    total_received += len(raw)
                    
                    # Log de progresso para grandes arquivos
                    if total_received % (100 * 1024) == 0:  # A cada 100KB
                        logger.debug(f"Recebidos {total_received} bytes...")
                        
                except socket.timeout:
                    logger.warning("Timeout ao receber dados")
                    break
                except Exception as e:
                    logger.error(f"Erro ao receber dados: {e}")
                    break
            
            if buffer:
                # Concatenar dados
                job_data = b''.join(buffer)
                logger.info(f"Recebidos {len(job_data)} bytes de dados de impressão")
                
                # Processar o trabalho
                self._process_print_job(job_data)
            else:
                logger.warning("Nenhum dado recebido")
                
        except Exception as e:
            logger.error(f"Erro ao processar conexão: {e}")
        finally:
            try:
                conn.close()
            except:
                pass
            logger.info(f"Conexão de {addr} fechada")
    
    def _process_print_job(self, job_data):
        """Processa um trabalho de impressão"""
        try:
            # Verificar o tipo de dados
            file_start = job_data[:20].decode('utf-8', errors='ignore')
            is_pdf = file_start.startswith('%PDF-') or 'PDF-' in file_start
            
            # Extrair nome do arquivo
            filename = self._extract_filename_from_data(job_data)
            logger.info(f"Nome do arquivo extraído: {filename}")
            
            # Se é um PDF direto, usamos os dados como estão
            if is_pdf:
                logger.info("Usando dados PDF diretamente...")
                pdf_data = job_data
            else:
                # Converter para PDF
                logger.info("Convertendo PostScript para PDF...")
                pdf_data = self._postscript_to_pdf(job_data)
            
            # Salvar o PDF
            saved_path = self._save_pdf(pdf_data, None, None, filename)
            if saved_path:
                logger.info(f"Trabalho de impressão processado: {os.path.basename(saved_path)}")
            
        except Exception as e:
            logger.error(f"Erro ao processar trabalho de impressão: {e}")
            import traceback
            logger.debug(f"Traceback completo: {traceback.format_exc()}")
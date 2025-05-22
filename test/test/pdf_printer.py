#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Impressora virtual PDF cross-platform que salva arquivos sem mostrar diálogos
Suporta Windows, Linux e macOS
"""
import os
import sys
import time
import socket
import select
import subprocess
import atexit
import platform
from pathlib import Path
from abc import ABC, abstractmethod

# Importar ctypes apenas no Windows
if platform.system() == 'Windows':
    import ctypes

class PrinterManager(ABC):
    """Classe abstrata para gerenciar impressoras específicas do sistema"""
    
    @abstractmethod
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona uma impressora virtual"""
        pass
    
    @abstractmethod
    def remove_printer(self, name):
        """Remove uma impressora"""
        pass
    
    @abstractmethod
    def remove_port(self, port_name):
        """Remove uma porta de impressora"""
        pass
    
    @abstractmethod
    def check_printer_exists(self, name):
        """Verifica se uma impressora existe"""
        pass
    
    @abstractmethod
    def check_port_exists(self, port_name):
        """Verifica se uma porta existe"""
        pass

class WindowsPrinterManager(PrinterManager):
    """Gerenciador de impressoras para Windows"""
    
    def __init__(self):
        self.postscript_printer_drivers = [
            'Microsoft Print To PDF',
            'Microsoft XPS Document Writer',
            'HP Universal Printing PS',
            'HP Color LaserJet 2800 Series PS',
            'Generic / Text Only'
        ]
        self.default_driver = self._find_available_driver()
    
    def _find_available_driver(self):
        """Encontra um driver disponível"""
        try:
            output = subprocess.check_output([
                'powershell', '-command',
                'Get-PrinterDriver | Select-Object Name | Format-Table -HideTableHeaders'
            ], universal_newlines=True)
            
            available_drivers = [line.strip() for line in output.splitlines() if line.strip()]
            
            for driver in self.postscript_printer_drivers:
                if driver in available_drivers:
                    return driver
            
            return available_drivers[0] if available_drivers else 'Microsoft Print To PDF'
        except:
            return 'Microsoft Print To PDF'
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Windows"""
        if printer_port_name is None:
            printer_port_name = f"{ip}:{port}"
        
        # Criar porta
        cmd = ['cscript', r'c:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
               '-md', '-a', '-o', 'raw', '-r', printer_port_name, '-h', ip, '-n', str(port)]
        
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
        except Exception as e:
            print(f"Erro ao criar porta: {e}")
            return False
        
        # Criar impressora
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/if',
               '/b', name, '/r', printer_port_name, '/m', self.default_driver, '/Z']
        
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
            print(f"Impressora Windows '{name}' instalada com sucesso!")
            return True
        except Exception as e:
            print(f"Erro ao criar impressora: {e}")
            return False
    
    def remove_printer(self, name):
        """Remove impressora no Windows"""
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/dl', '/n', name]
        try:
            subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            return True
        except:
            return False
    
    def remove_port(self, port_name):
        """Remove porta no Windows"""
        cmd = ['cscript', r'c:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
               '-d', '-r', port_name]
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
        except:
            pass
    
    def check_printer_exists(self, name):
        """Verifica se impressora existe no Windows"""
        try:
            cmd = ['powershell', '-command', 
                f'if (Get-Printer -Name "{name}" -ErrorAction SilentlyContinue) {{Write-Output "true"}} else {{Write-Output "false"}}']
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            return result.stdout.decode().strip().lower() == "true"
        except:
            return False
    
    def check_port_exists(self, port_name):
        """Verifica se porta existe no Windows"""
        try:
            cmd = ['powershell', '-command', 
                f'if (Get-PrinterPort -Name "{port_name}" -ErrorAction SilentlyContinue) {{Write-Output "true"}} else {{Write-Output "false"}}']
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            return result.stdout.decode().strip().lower() == "true"
        except:
            return False

class LinuxPrinterManager(PrinterManager):
    """Gerenciador de impressoras para Linux usando CUPS"""
    
    def __init__(self):
        self._ensure_cups_running()
    
    def _ensure_cups_running(self):
        """Garante que o CUPS está rodando"""
        try:
            # Verificar se o CUPS está instalado
            subprocess.run(['which', 'lpadmin'], check=True, capture_output=True)
        except subprocess.CalledProcessError:
            print("AVISO: CUPS não encontrado. Instale com: sudo apt-get install cups")
            return False
        
        # Tentar iniciar o CUPS se não estiver rodando
        try:
            subprocess.run(['sudo', 'systemctl', 'start', 'cups'], capture_output=True)
        except:
            pass  # Pode já estar rodando
        
        return True
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Linux usando CUPS"""
        device_uri = f"socket://{ip}:{port}"
        
        # Comando para adicionar impressora com driver PostScript genérico
        cmd = [
            'sudo', 'lpadmin',
            '-p', name,
            '-E',  # Habilitar impressora
            '-v', device_uri,
            '-m', 'lsb/usr/cupsfilters/generic-postscript-driver.ppd'  # Driver PostScript genérico
        ]
        
        # Se não tiver o driver acima, tentar com driver raw
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Tentar com driver raw se o PostScript falhar
                cmd = [
                    'sudo', 'lpadmin',
                    '-p', name,
                    '-E',
                    '-v', device_uri,
                    '-m', 'raw'
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            print(f"Erro ao criar impressora Linux: {e}")
            return False
        
        if result.returncode == 0:
            print(f"Impressora Linux '{name}' instalada com sucesso!")
            
            # Definir comentário se fornecido
            if comment:
                try:
                    subprocess.run(['sudo', 'lpadmin', '-p', name, '-D', comment], capture_output=True)
                except:
                    pass
            
            return True
        else:
            print(f"Erro ao instalar impressora: {result.stderr}")
            return False
    
    def remove_printer(self, name):
        """Remove impressora no Linux"""
        try:
            subprocess.run(['sudo', 'lpadmin', '-x', name], capture_output=True, timeout=10)
            return True
        except:
            return False
    
    def remove_port(self, port_name):
        """No Linux/CUPS, as portas são gerenciadas automaticamente"""
        pass
    
    def check_printer_exists(self, name):
        """Verifica se impressora existe no Linux"""
        try:
            result = subprocess.run(['lpstat', '-p', name], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def check_port_exists(self, port_name):
        """No Linux/CUPS, não é necessário verificar portas separadamente"""
        return True

class MacOSPrinterManager(PrinterManager):
    """Gerenciador de impressoras para macOS usando CUPS"""
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no macOS"""
        device_uri = f"socket://{ip}:{port}"
        
        cmd = [
            'lpadmin',
            '-p', name,
            '-E',
            '-v', device_uri,
            '-m', 'drv:///generic.drv/generic.ppd'  # Driver genérico para macOS
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                # Tentar com driver raw
                cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri, '-m', 'raw']
                result = subprocess.run(cmd, capture_output=True, text=True)
        except Exception as e:
            print(f"Erro ao criar impressora macOS: {e}")
            return False
        
        if result.returncode == 0:
            print(f"Impressora macOS '{name}' instalada com sucesso!")
            
            if comment:
                try:
                    subprocess.run(['lpadmin', '-p', name, '-D', comment], capture_output=True)
                except:
                    pass
            
            return True
        else:
            print(f"Erro ao instalar impressora: {result.stderr}")
            return False
    
    def remove_printer(self, name):
        """Remove impressora no macOS"""
        try:
            subprocess.run(['lpadmin', '-x', name], capture_output=True, timeout=10)
            return True
        except:
            return False
    
    def remove_port(self, port_name):
        """No macOS/CUPS, as portas são gerenciadas automaticamente"""
        pass
    
    def check_printer_exists(self, name):
        """Verifica se impressora existe no macOS"""
        try:
            result = subprocess.run(['lpstat', '-p', name], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def check_port_exists(self, port_name):
        """No macOS/CUPS, não é necessário verificar portas separadamente"""
        return True

class PDFPrinter:
    """Impressora virtual cross-platform que converte para PDF sem diálogos"""

    def __init__(self, 
                printer_name='Impressora LoQQuei',
                output_dir=None,
                ip='127.0.0.1', 
                port=None):
        """Inicializa a impressora virtual"""
        self.printer_name = printer_name
        self.ip = ip
        self.port = port if port else 0
        self.buffer_size = 1024
        self.running = False
        self.keep_going = False
        self.printer_manager = None
        self.printer_port_name = None
        self.system = platform.system()
        
        # Definir diretório de saída baseado no sistema
        if output_dir is None:
            if self.system == 'Windows':
                self.output_dir = 'c:/pdfs'
            else:
                self.output_dir = os.path.expanduser('~/pdfs')
        else:
            self.output_dir = output_dir
        
        # Criar diretório de saída
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        print(f"Diretório para PDFs criado: {self.output_dir}")
        
        # Inicializar gerenciador de impressoras específico do sistema
        self._init_printer_manager()
        
        # Verificar e instalar Ghostscript
        print("Verificando instalação do Ghostscript...")
        self.ghostscript_path = self._find_ghostscript()
        if not self.ghostscript_path:
            print("Ghostscript não encontrado. Iniciando instalação...")
            self.ghostscript_path = self._install_portable_ghostscript()
            if self.ghostscript_path:
                print(f"Ghostscript instalado com sucesso em: {self.ghostscript_path}")
            else:
                print("AVISO: Não foi possível instalar o Ghostscript automaticamente.")
        else:
            print(f"Ghostscript encontrado em: {self.ghostscript_path}")
    
    def _init_printer_manager(self):
        """Inicializa o gerenciador de impressoras baseado no sistema"""
        if self.system == 'Windows':
            self.printer_manager = WindowsPrinterManager()
        elif self.system == 'Linux':
            self.printer_manager = LinuxPrinterManager()
        elif self.system == 'Darwin':  # macOS
            self.printer_manager = MacOSPrinterManager()
        else:
            raise OSError(f"Sistema operacional não suportado: {self.system}")
    
    def _install_printer(self, ip, port):
        """Instala a impressora virtual"""
        atexit.register(self._uninstall_printer)
        
        self.printer_port_name = f"{self.printer_name} Port"
        comment = f'Impressora virtual PDF que salva automaticamente em {self.output_dir}'
        
        success = self.printer_manager.add_printer(
            self.printer_name, ip, port,
            self.printer_port_name, False, comment
        )
        
        if not success:
            print("Falha ao instalar a impressora virtual")
            return False
        
        return True
    
    def _uninstall_printer(self):
        """Remove a impressora virtual"""
        if not self.printer_manager:
            return
        
        print("Finalizando conexões com a impressora...")
        time.sleep(1)
        
        try:
            if self.printer_manager.check_printer_exists(self.printer_name):
                print(f"Removendo impressora: {self.printer_name}")
                self.printer_manager.remove_printer(self.printer_name)
            
            if hasattr(self.printer_manager, 'remove_port') and self.printer_port_name:
                if self.printer_manager.check_port_exists(self.printer_port_name):
                    print(f"Removendo porta: {self.printer_port_name}")
                    self.printer_manager.remove_port(self.printer_port_name)
        except Exception as e:
            print(f"Aviso: Erro durante a remoção da impressora: {e}")
        
        print("Processo de remoção da impressora concluído.")
    
    def _find_ghostscript(self):
        """Localiza o executável do Ghostscript cross-platform"""
        print(f"\n----- PROCURANDO GHOSTSCRIPT NO {self.system.upper()} -----")
        
        if self.system == 'Windows':
            return self._find_ghostscript_windows()
        else:
            return self._find_ghostscript_unix()
    
    def _find_ghostscript_windows(self):
        """Busca Ghostscript no Windows"""
        executable_names = [
            'gpcl6win64.exe', 'gpcl6win32.exe',
            'gspcl64c.exe', 'gspcl32c.exe',
            'gswin64c.exe', 'gswin32c.exe',
            'gswin.exe', 'gs.exe'
        ]
        
        # Verificar pasta portátil primeiro
        current_dir = os.path.dirname(os.path.abspath(__file__))
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
    
    def _find_ghostscript_unix(self):
        """Busca Ghostscript em sistemas Unix (Linux/macOS)"""
        # Verificar pasta portátil primeiro
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gs_dir = os.path.join(current_dir, 'gs')
        
        if os.path.exists(gs_dir):
            # Procurar por executável 'gs' na pasta portátil
            for root, dirs, files in os.walk(gs_dir):
                if 'gs' in files:
                    gs_path = os.path.join(root, 'gs')
                    if os.access(gs_path, os.X_OK) and self._test_ghostscript_executable(gs_path):
                        return gs_path
        
        # Verificar no PATH do sistema
        try:
            result = subprocess.run(['which', 'gs'], capture_output=True, text=True)
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
            '/opt/local/bin/gs',  # MacPorts
            '/usr/local/Cellar/ghostscript/*/bin/gs'  # Homebrew
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
                # Para GhostPCL no Windows
                process = subprocess.Popen(
                    [path, '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                stdout, stderr = process.communicate(timeout=5)
                return "PCL" in stdout or "PCL" in stderr or "Ghostscript" in stdout
            else:
                # Para Ghostscript padrão
                result = subprocess.run([path, '--version'], 
                                    capture_output=True, text=True, timeout=5)
                return result.returncode == 0
        except:
            return False
    
    def _install_portable_ghostscript(self):
        """Instala versão portátil do Ghostscript baseada no sistema"""
        if self.system == 'Windows':
            return self._install_ghostscript_windows()
        elif self.system == 'Linux':
            return self._install_ghostscript_linux()
        elif self.system == 'Darwin':
            return self._install_ghostscript_macos()
        return None
    
    def _install_ghostscript_windows(self):
        """Instala Ghostscript no Windows"""
        import urllib.request
        import zipfile
        import tempfile
        import shutil
        
        is_64bits = platform.architecture()[0] == '64bit'
        
        if is_64bits:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostpcl-10.0.0-win64.zip"
            expected_exe = "gpcl6win64.exe"
        else:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostpcl-10.0.0-win32.zip"
            expected_exe = "gpcl6win32.exe"
        
        return self._download_and_install_ghostscript(gs_url, expected_exe)
    
    def _install_ghostscript_linux(self):
        """Instala Ghostscript no Linux"""
        import urllib.request
        import tarfile
        import tempfile
        import shutil
        
        # Detectar arquitetura
        machine = platform.machine().lower()
        if 'x86_64' in machine or 'amd64' in machine:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostscript-10.0.0-linux-x86_64.tgz"
        else:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostscript-10.0.0-linux-x86.tgz"
        
        return self._download_and_install_ghostscript_unix(gs_url, 'gs')
    
    def _install_ghostscript_macos(self):
        """Instala Ghostscript no macOS"""
        # Primeiro tentar instalar via Homebrew se disponível
        try:
            subprocess.run(['which', 'brew'], check=True, capture_output=True)
            print("Homebrew encontrado, tentando instalar Ghostscript...")
            result = subprocess.run(['brew', 'install', 'ghostscript'], capture_output=True)
            if result.returncode == 0:
                gs_path = subprocess.run(['which', 'gs'], capture_output=True, text=True)
                if gs_path.returncode == 0:
                    return gs_path.stdout.strip()
        except:
            pass
        
        # Se Homebrew falhar, tentar download direto
        # Para macOS, vamos tentar a versão Linux x86_64 que pode funcionar
        import urllib.request
        import tarfile
        
        gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostscript-10.0.0-linux-x86_64.tgz"
        return self._download_and_install_ghostscript_unix(gs_url, 'gs')
    
    def _download_and_install_ghostscript(self, url, expected_exe):
        """Download e instalação para Windows (ZIP)"""
        import urllib.request
        import zipfile
        import tempfile
        import shutil
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gs_dir = os.path.join(current_dir, 'gs')
        
        temp_dir = tempfile.mkdtemp(prefix="gs_install_")
        
        try:
            zip_path = os.path.join(temp_dir, "ghostscript.zip")
            
            print(f"Baixando Ghostscript de {url}...")
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; Python)'}
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(zip_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            extract_dir = tempfile.mkdtemp(prefix="gs_extract_")
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
            
            os.makedirs(gs_dir, exist_ok=True)
            
            # Copiar conteúdo extraído
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
            
            # Buscar executável
            for root, dirs, files in os.walk(gs_dir):
                if expected_exe.lower() in [f.lower() for f in files]:
                    real_name = next(f for f in files if f.lower() == expected_exe.lower())
                    return os.path.join(root, real_name)
            
            return None
            
        except Exception as e:
            print(f"Erro na instalação: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _download_and_install_ghostscript_unix(self, url, expected_exe):
        """Download e instalação para Unix (TAR.GZ)"""
        import urllib.request
        import tarfile
        import tempfile
        import shutil
        
        current_dir = os.path.dirname(os.path.abspath(__file__))
        gs_dir = os.path.join(current_dir, 'gs')
        
        temp_dir = tempfile.mkdtemp(prefix="gs_install_")
        
        try:
            tar_path = os.path.join(temp_dir, "ghostscript.tgz")
            
            print(f"Baixando Ghostscript de {url}...")
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; Python)'}
            request = urllib.request.Request(url, headers=headers)
            
            with urllib.request.urlopen(request, timeout=120) as response:
                with open(tar_path, 'wb') as out_file:
                    shutil.copyfileobj(response, out_file)
            
            extract_dir = tempfile.mkdtemp(prefix="gs_extract_")
            
            with tarfile.open(tar_path, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_dir)
            
            os.makedirs(gs_dir, exist_ok=True)
            
            # Copiar conteúdo extraído
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
                    # Dar permissão de execução se for o executável
                    if os.path.basename(item) == expected_exe:
                        os.chmod(dst, 0o755)
            
            # Buscar executável
            for root, dirs, files in os.walk(gs_dir):
                if expected_exe in files:
                    gs_path = os.path.join(root, expected_exe)
                    os.chmod(gs_path, 0o755)  # Garantir permissão de execução
                    return gs_path
            
            return None
            
        except Exception as e:
            print(f"Erro na instalação: {e}")
            return None
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
    
    def _postscript_to_pdf(self, data):
        """Converte dados PostScript para PDF usando Ghostscript"""
        if not self.ghostscript_path:
            print("Erro: Ghostscript não disponível.")
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
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            pdf_data, stderr = process.communicate(input=data, timeout=60)
            
            if pdf_data and pdf_data.startswith(b'%PDF-'):
                print(f"Conversão bem-sucedida. Tamanho: {len(pdf_data)} bytes")
                return pdf_data
            else:
                print("Erro: Saída não contém um PDF válido.")
                return None
                
        except Exception as e:
            print(f"Erro ao converter PostScript para PDF: {e}")
            return None
    
    def _extract_pdf_filename(self, data):
        """Extrai o nome do arquivo diretamente de dados PDF"""
        try:
            # Convertemos para texto para procurar metadados
            pdf_text = data.decode('utf-8', errors='ignore')
            
            # Procurar por objetos de informação/metadados comuns em PDF
            import re
            
            # Tenta encontrar o título no objeto de informação do PDF
            title_patterns = [
                r'/Title\s*\(([^)]+)\)',
                r'/Title\s*<([^>]+)>',
                r'/Filename\s*\(([^)]+)\)',
                r'/DocumentName\s*\(([^)]+)\)'
            ]
            
            for pattern in title_patterns:
                matches = re.findall(pattern, pdf_text)
                if matches:
                    # Decodificar escape hexadecimal se necessário
                    title = matches[0]
                    if title.startswith('FEFF'):  # Marcador de ordem de bytes Unicode
                        # Tenta decodificar hex para texto
                        try:
                            hex_bytes = bytes.fromhex(title.replace(' ', ''))
                            title = hex_bytes.decode('utf-16-be', errors='ignore')
                        except:
                            pass  # Se falhar, usa o valor original
                    
                    print(f"Título encontrado no PDF: {title}")
                    return title
            
            # Se não encontrar título direto, procurar por nomes de arquivo no texto
            file_extensions = ['.pdf', '.txt', '.doc', '.xls', '.ppt', '.xlsx', '.docx', '.pptx']
            for ext in file_extensions:
                # Regex que procura por nomes de arquivo com a extensão específica
                pattern = r'([^\\/\s:"\']+' + re.escape(ext) + r')'
                matches = re.findall(pattern, pdf_text, re.IGNORECASE)
                if matches:
                    return matches[0]
                
            # Se tudo falhar, procurar pelo objeto XMP de metadados
            xmp_start = pdf_text.find('<x:xmpmeta')
            if xmp_start > 0:
                xmp_end = pdf_text.find('</x:xmpmeta>', xmp_start)
                if xmp_end > xmp_start:
                    xmp_data = pdf_text[xmp_start:xmp_end+12]
                    
                    # Procurar por dc:title no XMP
                    title_match = re.search(r'<dc:title>\s*<rdf:Alt>\s*<rdf:li[^>]*>(.*?)</rdf:li>', xmp_data)
                    if title_match:
                        return title_match.group(1)
            
            return None
        except Exception as e:
            print(f"Erro ao extrair nome do PDF: {e}")
            return None

    def _extract_from_header(self, ps_text):
        """Extrai o nome do arquivo do cabeçalho PS usando múltiplos métodos"""
        # Verificar se há cabeçalho antes do PostScript
        header_text = ps_text.split('%!PS-', 1)[0] if '%!PS-' in ps_text else ps_text[:1000]
        
        print("Analisando cabeçalho do trabalho...")
        print(f"Primeiros 200 caracteres do cabeçalho: {header_text[:200]}")
        
        filename = None
        
        # ----- MICROSOFT OFFICE APPS (EXCEL, WORD, ETC) -----
        # Padrões comuns do Microsoft Office
        ms_office_patterns = [
            '@PJL SET JOBNAME="',
            '@PJL JOB NAME="',
            '@PJL JOB FILE="',
            '@PJL COMMENT DocumentName="',
            '@PJL COMMENT "document="'
        ]
        
        for pattern in ms_office_patterns:
            if pattern in header_text:
                print(f"Padrão Microsoft Office encontrado: {pattern}")
                start_idx = header_text.find(pattern) + len(pattern)
                end_idx = header_text.find('"', start_idx)
                if end_idx > start_idx:
                    value = header_text[start_idx:end_idx]
                    print(f"Valor extraído: {value}")
                    
                    # Se for um caminho, extrair apenas o nome do arquivo
                    if '\\' in value or '/' in value:
                        extracted_name = os.path.basename(value)
                    else:
                        extracted_name = value
                    
                    # Se parece ser um nome de arquivo válido, use-o
                    if '.' in extracted_name and not extracted_name.startswith('.'):
                        filename = extracted_name
                        print(f"Nome de arquivo de MS Office: {filename}")
                        break
        
        # ----- BLOCO DE NOTAS -----
        # Padrões específicos para o Bloco de Notas
        if not filename:  # Só procuramos se ainda não encontramos um nome
            notepad_patterns = [
                '@PJL SET FILENAME="',
                '@PJL SET DOCUMENT="',
                '@PJL COMMENT FileName="',
                'text\\\\',  # Padrão comum em arquivos do Bloco de Notas
                '.txt"',     # Extensão comum de arquivos do Bloco de Notas
            ]
            
            for pattern in notepad_patterns:
                if pattern in ps_text:
                    print(f"Padrão Bloco de Notas encontrado: {pattern}")
                    
                    # Extrair o texto ao redor do padrão para análise
                    idx = ps_text.find(pattern)
                    context = ps_text[max(0, idx-50):min(len(ps_text), idx+100)]
                    print(f"Contexto: {context}")
                    
                    # Procurar pelo nome do arquivo com extensão .txt
                    import re
                    txt_files = re.findall(r'[\\\/]([^\\\/"]+\.txt)', context)
                    if txt_files:
                        filename = txt_files[0]
                        print(f"Nome de arquivo do Bloco de Notas: {filename}")
                        break
        
        # ----- ADOBE E APLICATIVOS PDF -----
        if not filename:
            pdf_app_patterns = [
                '@PJL SET JOBNAME="',
                '@PJL COMMENT "documentname=',
                '@PJL COMMENT document='
            ]
            
            for pattern in pdf_app_patterns:
                if pattern in ps_text:
                    print(f"Padrão de aplicativo PDF encontrado: {pattern}")
                    
                    if pattern.endswith('"'):
                        # Padrão com aspas
                        start_idx = ps_text.find(pattern) + len(pattern)
                        end_idx = ps_text.find('"', start_idx)
                        if end_idx > start_idx:
                            value = ps_text[start_idx:end_idx]
                    else:
                        # Padrão sem aspas
                        line = next((l for l in ps_text.split('\n') if pattern in l), '')
                        if line:
                            value = line.split(pattern, 1)[1].strip()
                            if ';' in value:
                                value = value.split(';', 1)[0].strip()
                    
                    print(f"Valor de documento PDF extraído: {value}")
                    
                    # Se for um caminho, extrair apenas o nome do arquivo
                    if '\\' in value or '/' in value:
                        filename = os.path.basename(value)
                    else:
                        filename = value
                    
                    print(f"Nome de arquivo de aplicativo PDF: {filename}")
                    break
        
        # ----- OUTRAS APLICAÇÕES -----
        # Procurar por outros padrões comuns se ainda não encontramos um nome
        if not filename:
            # Lista de padrões para procurar
            general_patterns = [
                '%%Title:', 
                '@PJL JOB NAME=',
                '@PJL SET JOBNAME=',
                '%%DocumentName:',
                '/Title',
                '@PJL COMMENT "filename='
            ]
            
            for pattern in general_patterns:
                if pattern in ps_text:
                    print(f"Padrão geral encontrado: {pattern}")
                    
                    # Extração baseada no tipo de padrão
                    if pattern.endswith('='):
                        # Padrões com =
                        for line in ps_text.split('\n'):
                            if pattern in line:
                                if '"' in line.split(pattern, 1)[1]:
                                    value = line.split(pattern, 1)[1].split('"', 1)[1].split('"', 1)[0]
                                else:
                                    value = line.split(pattern, 1)[1].strip()
                                
                                print(f"Valor extraído: {value}")
                                
                                # Se for um caminho, extrair apenas o nome do arquivo
                                if '\\' in value or '/' in value:
                                    filename = os.path.basename(value)
                                else:
                                    filename = value
                                
                                print(f"Nome de arquivo geral: {filename}")
                                break
                    elif pattern.endswith(':'):
                        # Padrões com :
                        for line in ps_text.split('\n'):
                            if pattern in line:
                                value = line.split(pattern, 1)[1].strip()
                                if '(' in value and ')' in value:
                                    value = value.split('(', 1)[1].split(')', 1)[0]
                                
                                print(f"Valor extraído: {value}")
                                filename = value
                                print(f"Nome de arquivo geral: {filename}")
                                break
                
                if filename:
                    break
        
        # Se após todas as tentativas, não encontramos o nome do arquivo
        if not filename:
            print("Tentando extrair qualquer nome de arquivo com regex...")
            
            # Tentar extrair qualquer nome de arquivo com extensão do texto
            import re
            # Procurar por extensões de arquivos comuns
            extensions = ['.pdf', '.txt', '.doc', '.xls', '.xlsx', '.docx', '.pptx', '.ppt', '.rtf']
            for ext in extensions:
                pattern = r'[\\\/]([^\\\/"]+' + re.escape(ext) + r')'
                matches = re.findall(pattern, ps_text, re.IGNORECASE)
                if matches:
                    filename = matches[0]
                    print(f"Nome de arquivo extraído por regex ({ext}): {filename}")
                    break
        
        return filename

    def _extract_filename_from_data(self, data):
        """Extrai nome do arquivo dos dados de impressão (método principal)"""
        try:
            # Verificar o tipo de dados com base nos primeiros bytes
            file_start = data[:20].decode('utf-8', errors='ignore')
            
            # Verificar se já é um arquivo PDF
            is_pdf = file_start.startswith('%PDF-') or 'PDF-' in file_start
            
            if is_pdf:
                print("Detectado arquivo PDF direto...")
                filename = self._extract_pdf_filename(data)
                if filename:
                    print(f"Nome extraído do PDF: {filename}")
                    return filename
                else:
                    # Tentar extrair do cabeçalho se disponível
                    print("Tentando extrair do cabeçalho...")
                    ps_text = data.decode('utf-8', errors='ignore')
                    filename = self._extract_from_header(ps_text)
                    return filename
            else:
                # Extrair informações do PostScript se possível
                ps_text = data.decode('utf-8', errors='ignore')
                
                # DEBUG: Salvar amostra do início do PostScript para análise
                debug_file = os.path.join(self.output_dir, f"debug_ps_sample_{time.strftime('%Y%m%d_%H%M%S')}.txt")
                with open(debug_file, "w", encoding="utf-8") as f:
                    f.write(ps_text[:5000])  # Salvar os primeiros 5000 caracteres para análise
                
                print(f"Arquivo de debug salvo em: {debug_file}")
                
                # Extrair nome do arquivo através de diversos métodos
                filename = self._extract_from_header(ps_text)
                return filename
                
        except Exception as e:
            print(f"Erro ao extrair metadados: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _save_pdf(self, pdf_data, title=None, author=None, filename=None):
        """Salva os dados PDF em um arquivo"""
        if not pdf_data:
            print("Nenhum dado PDF para salvar.")
            return
        
        print(f"Salvando PDF com - filename: {filename}, title: {title}, author: {author}")
        
        # Determinar nome do arquivo
        if filename:
            base_name = filename
        elif title:
            base_name = title
        else:
            # Formato brasileiro: dia-mes-ano_hora-min-seg
            data_br = time.strftime('%d-%m-%Y')
            hora_br = time.strftime('%H-%M-%S')
            base_name = f"sem título_{data_br}_{hora_br}"
        
        # Remover caracteres inválidos e garantir extensão .pdf
        base_name = ''.join(c for c in base_name if c.isalnum() or c in ' ._-')
        if not base_name.lower().endswith('.pdf'):
            base_name += '.pdf'
        
        # Caminho completo
        output_path = os.path.join(self.output_dir, base_name)
        
        # Evitar sobrescrever arquivos existentes
        counter = 1
        while os.path.exists(output_path):
            name_parts = base_name.rsplit('.', 1)
            if counter == 1:
                new_name = f"{name_parts[0]}_copia.{name_parts[1]}"
            else:
                new_name = f"{name_parts[0]}_copia{counter}.{name_parts[1]}"
            output_path = os.path.join(self.output_dir, new_name)
            counter += 1
        
        # Salvar o arquivo
        try:
            with open(output_path, 'wb') as f:
                f.write(pdf_data)
            print(f"PDF salvo em: {output_path}")
        except Exception as e:
            print(f"Erro ao salvar PDF: {e}")
    
    def run(self):
        """Inicia o servidor de impressão"""
        if self.running:
            return
        
        self.running = True
        self.keep_going = True
        
        # Verificar permissões no Linux/macOS
        if self.system in ['Linux', 'Darwin'] and os.geteuid() != 0:
            print("AVISO: Este programa pode precisar de privilégios de administrador (sudo)")
            print("Se houver erros de permissão, tente executar com sudo")
        
        # Criar socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((self.ip, self.port))
        ip, port = sock.getsockname()
        print(f'Servidor iniciado em {ip}:{port}')
        
        # Instalar impressora
        if not self._install_printer(ip, port):
            print("Falha ao instalar a impressora. Encerrando...")
            sock.close()
            return
        
        sock.listen(1)
        
        print(f"\nImportante:")
        print(f"1. A impressora '{self.printer_name}' foi instalada")
        print(f"2. Os arquivos PDF serão salvos em {self.output_dir}")
        print(f"3. Para parar o servidor, pressione Ctrl+C\n")
        
        try:
            while self.keep_going:
                print('\nAguardando trabalhos de impressão...')
                
                # Esperar por conexões
                ready_sockets, _, _ = select.select([sock], [], [], 1.0)
                if sock not in ready_sockets:
                    continue
                
                print('Recebendo trabalho... processando...')
                conn, addr = sock.accept()
                
                # Receber dados
                buffer = []
                while True:
                    raw = conn.recv(self.buffer_size)
                    if not raw:
                        break
                    buffer.append(raw)
                
                if buffer:
                    # Concatenar dados
                    job_data = b''.join(buffer)
                    
                    # Extrair metadados do trabalho
                    title = None
                    author = None
                    filename = None
                    
                    try:
                        # Verificar o tipo de dados com base nos primeiros bytes
                        file_start = job_data[:20].decode('utf-8', errors='ignore')
                        
                        # Verificar se já é um arquivo PDF
                        is_pdf = file_start.startswith('%PDF-') or 'PDF-' in file_start
                        
                        # Extrair nome do arquivo usando o método completo
                        filename = self._extract_filename_from_data(job_data)
                        
                        # Debug - mostrar metadados extraídos
                        print(f"Metadados finais - Nome: {filename}, Título: {title}, Autor: {author}")
                        
                    except Exception as e:
                        print(f"Erro ao extrair metadados: {e}")
                        import traceback
                        traceback.print_exc()
                    
                    # Se é um PDF direto, usamos os dados como estão
                    if is_pdf:
                        print("Usando dados PDF diretamente...")
                        pdf_data = job_data
                    else:
                        # Converter para PDF
                        print("Convertendo PostScript para PDF...")
                        pdf_data = self._postscript_to_pdf(job_data)
                    
                    # Salvar o PDF
                    self._save_pdf(pdf_data, title, author, filename)
                
                conn.close()
                
        except KeyboardInterrupt:
            print("\nInterrompendo servidor...")
        finally:
            sock.close()
            self.running = False
            self.keep_going = False
            self._uninstall_printer()
            print("Servidor encerrado e impressora removida.")

def main():
    """Função principal"""
    system = platform.system()
    
    # Verificar privilégios de administrador no Windows
    if system == 'Windows':
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if not is_admin:
                print("Este programa precisa ser executado como administrador no Windows.")
                print("Clique com o botão direito e selecione 'Executar como administrador'.")
                sys.exit(1)
        except Exception as e:
            print(f"Aviso: Não foi possível verificar privilégios: {e}")
    
    print(f"Iniciando impressora virtual PDF para {system}")
    
    try:
        printer = PDFPrinter()
        printer.run()
    except Exception as e:
        print(f"Erro: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
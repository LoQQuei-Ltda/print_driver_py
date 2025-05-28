#!/usr/bin/env python3
"""
TESTE
Sistema de impressão IPP para arquivos PDF
Suporta impressão de arquivos .pdf com fallback automático para JPG
Inclui sistema de retry para páginas que falharam
VERSÃO CORRIGIDA - Resolve erro HTTP 505
"""

import os
import tempfile
import time
import sys
import struct
import argparse
import subprocess
import socket
import http.client
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse
import urllib3
import platform
import zipfile
import urllib.request
import shutil
import re
import unicodedata

# Desabilita avisos SSL
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def normalize_filename(filename):
    """Normaliza um nome de arquivo removendo acentos e caracteres especiais"""
    # Remove acentos
    filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
    # Remove caracteres não alfanuméricos e substitui por underscores
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    # Limita o comprimento do nome
    if len(filename) > 30:
        base, ext = os.path.splitext(filename)
        filename = f"{base[:25]}{ext}"
    return filename

def test_printer_connectivity(printer_ip: str, port: int = 631) -> Tuple[bool, List[str]]:
    """Testa conectividade básica e descobre endpoints válidos"""
    print(f"🔍 Testando conectividade com {printer_ip}:{port}...")
    
    # Teste básico de socket
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((printer_ip, port))
        sock.close()
        
        if result != 0:
            print(f"  ✗ Porta {port} não está acessível")
            return False, []
        else:
            print(f"  ✓ Porta {port} está acessível")
    except Exception as e:
        print(f"  ✗ Erro no teste de socket: {e}")
        return False, []
    
    # Testa endpoints comuns
    valid_endpoints = []
    test_endpoints = [
        "/ipp/print",
        "/ipp",
        "/printers/ipp", 
        "/printers",
        "",
        "/ipp/printer",
        "/print"
    ]
    
    session = requests.Session()
    # Configurações para evitar HTTP 505
    session.headers.update({
        'User-Agent': 'IPP/2.1',
        'Connection': 'close',
        'Accept': '*/*'
    })
    
    for endpoint in test_endpoints:
        url = f"http://{printer_ip}:{port}{endpoint}"
        try:
            # Faz uma requisição OPTIONS primeiro para testar
            response = session.options(url, timeout=10, verify=False)
            if response.status_code in [200, 405, 501]:  # 405/501 são OK, significa que o endpoint existe
                valid_endpoints.append(endpoint)
                print(f"  ✓ Endpoint válido: {endpoint} (Status: {response.status_code})")
            else:
                print(f"  ✗ Endpoint inválido: {endpoint} (Status: {response.status_code})")
        except Exception as e:
            print(f"  ✗ Erro testando {endpoint}: {e}")
    
    session.close()
    return len(valid_endpoints) > 0, valid_endpoints

# Instalação automática de dependências
def install_package(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

# Instala dependências necessárias
required_packages = ['requests', 'Pillow', 'pdf2image']

for package in required_packages:
    try:
        if package == 'pdf2image':
            import pdf2image
        elif package == 'Pillow':
            from PIL import Image
        elif package == 'requests':
            import requests
    except ImportError:
        print(f"Instalando {package}...")
        install_package(package)
        if package == 'pdf2image':
            import pdf2image
        elif package == 'Pillow':
            from PIL import Image
        elif package == 'requests':
            import requests

def get_poppler_path():
    """Retorna o caminho do Poppler se estiver instalado"""
    system = platform.system().lower()
    
    if system == "windows":
        # Verifica se poppler já está no PATH
        try:
            result = subprocess.run(['pdftoppm', '-h'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return None  # Já está no PATH
        except:
            pass
        
        # Procura por instalação local do poppler
        possible_paths = [
            os.path.join(os.getcwd(), "poppler", "bin"),
            os.path.join(os.path.dirname(__file__), "poppler", "library", "bin"),
            r"C:\Program Files\poppler\library\bin",
            r"C:\poppler\library\bin",
        ]
        
        for path in possible_paths:
            if os.path.exists(os.path.join(path, "pdftoppm.exe")):
                return path
        
        return None
    
    # Para Linux/Mac, geralmente está no PATH
    return None

def install_poppler_windows():
    """Instala Poppler no Windows automaticamente"""
    print("🔄 Instalando Poppler para Windows...")
    
    try:
        # URL do Poppler para Windows (versão portável)
        poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.08.0-0/Release-23.08.0-0.zip"
        
        # Pasta de destino
        script_dir = os.path.dirname(os.path.abspath(__file__))
        poppler_dir = os.path.join(script_dir, "poppler")
        zip_path = os.path.join(script_dir, "poppler.zip")
        
        # Remove instalação anterior se existir
        if os.path.exists(poppler_dir):
            shutil.rmtree(poppler_dir)
        
        print("  → Baixando Poppler...")
        urllib.request.urlretrieve(poppler_url, zip_path)
        
        print("  → Extraindo arquivos...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(script_dir)
        
        # Renomeia a pasta extraída para "poppler"
        extracted_folders = [f for f in os.listdir(script_dir) 
                           if f.startswith("poppler-") and os.path.isdir(os.path.join(script_dir, f))]
        
        if extracted_folders:
            old_name = os.path.join(script_dir, extracted_folders[0])
            os.rename(old_name, poppler_dir)
        
        # Remove o arquivo zip
        os.remove(zip_path)
        
        # Verifica se a instalação foi bem-sucedida
        bin_path = os.path.join(poppler_dir, "bin")
        if os.path.exists(os.path.join(bin_path, "pdftoppm.exe")):
            print(f"  ✓ Poppler instalado com sucesso em: {bin_path}")
            return bin_path
        else:
            print("  ✗ Erro na instalação do Poppler")
            return None
            
    except Exception as e:
        print(f"  ✗ Erro ao instalar Poppler: {e}")
        return None

def setup_poppler():
    """Configura o Poppler para uso com pdf2image"""
    system = platform.system().lower()
    
    if system == "windows":
        poppler_path = get_poppler_path()
        
        if poppler_path is None:
            print("📦 Poppler não encontrado. Instalando automaticamente...")
            poppler_path = install_poppler_windows()
            
            if poppler_path is None:
                print("\n❌ Não foi possível instalar o Poppler automaticamente.")
                print("\n📋 Instalação manual:")
                print("1. Baixe: https://github.com/oschwartz10612/poppler-windows/releases")
                print("2. Extraia em uma pasta (ex: C:\\poppler)")
                print("3. Adicione C:\\poppler\\bin ao PATH do sistema")
                print("4. Ou coloque a pasta 'poppler' no mesmo diretório deste script")
                return None
        
        return poppler_path
    
    else:
        # Para Linux/Mac
        try:
            result = subprocess.run(['pdftoppm', '-h'], 
                                 capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return None  # Já está disponível
        except:
            pass
        
        print("\n❌ Poppler não encontrado.")
        print("\n📋 Instale usando:")
        print("Ubuntu/Debian: sudo apt-get install poppler-utils")
        print("CentOS/RHEL: sudo yum install poppler-utils")
        print("macOS: brew install poppler")
        return None


# Constantes IPP
class IPPVersion:
    IPP_1_1 = 0x0101

class IPPOperation:
    PRINT_JOB = 0x0002

class IPPTag:
    OPERATION = 0x01
    JOB = 0x02
    END = 0x03
    INTEGER = 0x21
    BOOLEAN = 0x22
    ENUM = 0x23
    TEXT = 0x41
    NAME = 0x42
    KEYWORD = 0x44
    URI = 0x45
    CHARSET = 0x47
    LANGUAGE = 0x48
    MIMETYPE = 0x49

class ColorMode(Enum):
    AUTO = "auto"
    COLORIDO = "color"
    MONOCROMO = "monochrome"

class Duplex(Enum):
    SIMPLES = "one-sided"
    DUPLEX_LONGO = "two-sided-long-edge"
    DUPLEX_CURTO = "two-sided-short-edge"

class Quality(Enum):
    RASCUNHO = 3
    NORMAL = 4
    ALTA = 5

@dataclass
class PrintOptions:
    color_mode: ColorMode = ColorMode.AUTO
    duplex: Duplex = Duplex.SIMPLES
    quality: Quality = Quality.NORMAL
    copies: int = 1
    orientation: str = "portrait"
    paper_size: str = "iso_a4_210x297mm"
    dpi: int = 300

@dataclass
class PageJob:
    """Representa uma página para impressão"""
    page_num: int
    image_path: str
    jpg_data: bytes
    job_name: str
    attempts: int = 0
    max_attempts: int = 3

class IPPEncoder:
    """Codificador para protocolo IPP"""
    
    @staticmethod
    def encode_string(tag: int, name: str, value: str) -> bytes:
        """Codifica um atributo string"""
        data = struct.pack('>B', tag)
        data += struct.pack('>H', len(name)) + name.encode('utf-8')
        data += struct.pack('>H', len(value)) + value.encode('utf-8')
        return data
    
    @staticmethod
    def encode_integer(tag: int, name: str, value: int) -> bytes:
        """Codifica um atributo inteiro"""
        data = struct.pack('>B', tag)
        data += struct.pack('>H', len(name)) + name.encode('utf-8')
        data += struct.pack('>HI', 4, value)
        return data
    
    @staticmethod
    def encode_boolean(name: str, value: bool) -> bytes:
        """Codifica um atributo booleano"""
        data = struct.pack('>B', IPPTag.BOOLEAN)
        data += struct.pack('>H', len(name)) + name.encode('utf-8')
        data += struct.pack('>HB', 1, 1 if value else 0)
        return data
    
    @staticmethod
    def encode_enum(name: str, value: int) -> bytes:
        """Codifica um atributo enum"""
        return IPPEncoder.encode_integer(IPPTag.ENUM, name, value)

class PDFPrinter:
    """Classe principal para impressão de arquivos PDF via IPP"""
    
    def __init__(self, printer_ip: str, port: int = 631, use_https: bool = False):
        self.printer_ip = printer_ip
        self.port = port
        self.use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.base_url = f"{self.protocol}://{printer_ip}:{port}"
        self.request_id = 1
        self.valid_endpoints = []
        
    def print_file(self, file_path: str, options: PrintOptions, 
                   job_name: Optional[str] = None) -> bool:
        """Imprime um arquivo PDF com fallback automático para JPG"""
        
        if not os.path.exists(file_path):
            print(f"❌ Erro: Arquivo não encontrado: {file_path}")
            return False
        
        # Verifica se é um arquivo PDF
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension != '.pdf':
            print(f"❌ Erro: Arquivo deve ser PDF (.pdf), recebido: {file_extension}")
            return False
        
        if job_name is None:
            # Normaliza o nome do arquivo para o job_name
            job_name = normalize_filename(os.path.basename(file_path))
        else:
            # Normaliza o job_name fornecido
            job_name = normalize_filename(job_name)
        
        print(f"\n📄 Preparando impressão de: {job_name}")
        print(f"🖨️  Impressora: {self.printer_ip}:{self.port}")
        
        # NOVO: Teste de conectividade antes de começar
        connectivity_ok, valid_endpoints = test_printer_connectivity(self.printer_ip, self.port)
        if not connectivity_ok:
            print(f"❌ Impressora não está acessível em {self.printer_ip}:{self.port}")
            return False
        
        # Atualiza a lista de endpoints para usar apenas os válidos
        if valid_endpoints:
            print(f"✅ Endpoints válidos encontrados: {', '.join(valid_endpoints)}")
            self.valid_endpoints = valid_endpoints
        
        # Lê o arquivo PDF
        try:
            with open(file_path, 'rb') as f:
                pdf_data = f.read()
        except Exception as e:
            print(f"❌ Erro ao ler arquivo: {e}")
            return False
        
        print(f"📋 Formato: PDF")
        print(f"📊 Tamanho do arquivo: {len(pdf_data):,} bytes")
        
        # Primeira tentativa: enviar como PDF
        print(f"\n🔄 Tentativa 1: Enviando como PDF")
        if self._print_as_pdf(pdf_data, job_name, options):
            print(f"✅ Impressão PDF enviada com sucesso!")
            return True
        
        # Segunda tentativa: converter para JPG e enviar
        print(f"\n🔄 Tentativa 2: Convertendo para JPG e enviando")
        if self._convert_and_print_as_jpg(file_path, job_name, options):
            print(f"✅ Impressão JPG enviada com sucesso!")
            return True
        
        print("\n❌ Ambas as tentativas falharam")
        return False
    
    def _print_as_pdf(self, pdf_data: bytes, job_name: str, options: PrintOptions) -> bool:
        """Tenta imprimir como PDF"""
        
        # Usa endpoints válidos se disponíveis, senão usa lista padrão
        if hasattr(self, 'valid_endpoints') and self.valid_endpoints:
            endpoints = self.valid_endpoints
            print(f"  → Usando endpoints validados: {endpoints}")
        else:
            endpoints = ["/ipp/print", "/ipp", "/printers/ipp", "/printers", ""]
        
        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            print(f"  → Testando endpoint: {url}")
            
            # Atributos IPP para PDF com nome normalizado
            attributes = {
                "printer-uri": url,
                "requesting-user-name": normalize_filename(os.getenv("USER", "usuario")),
                "job-name": job_name,
                "document-name": job_name,
                "document-format": "application/pdf",
                "ipp-attribute-fidelity": False,
                "job-priority": 50,
                "copies": options.copies,
                "orientation-requested": 3 if options.orientation == "portrait" else 4,
                "print-quality": options.quality.value,
                "media": options.paper_size,
            }
            
            # Adiciona opções condicionais
            if options.color_mode != ColorMode.AUTO:
                attributes["print-color-mode"] = options.color_mode.value
            if options.duplex != Duplex.SIMPLES:
                attributes["sides"] = options.duplex.value
                
            # Constrói e envia requisição IPP
            if self._send_ipp_request(url, attributes, pdf_data):
                return True
        
        return False
    
    def _create_temp_folder(self, base_name: str) -> str:
        """Cria uma pasta temporária para salvar as imagens convertidas"""
        # Normaliza o nome base para evitar problemas com caracteres especiais
        safe_name = normalize_filename(base_name)
        timestamp = int(time.time())
        # Usa um nome de pasta sem espaços ou caracteres especiais
        temp_dir = os.path.join(tempfile.gettempdir(), f"pdf_print_{safe_name}_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    def _convert_and_print_as_jpg(self, pdf_path: str, job_name: str, options: PrintOptions) -> bool:
        """Converte PDF para JPG e tenta imprimir com sistema de retry"""
        
        temp_folder = None
        
        try:
            print("  → Convertendo PDF para JPG...")
            
            # Configura Poppler
            poppler_path = setup_poppler()
            
            # Cria pasta temporária para salvar as imagens
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            # Normaliza o nome do arquivo para evitar problemas
            safe_base_name = normalize_filename(base_name)
            print(f"  → Base do nome: {safe_base_name} (normalizado de: {base_name})")
            temp_folder = self._create_temp_folder(safe_base_name)
            print(f"  → Pasta temporária: {temp_folder}")
            
            # Converte PDF para imagens com poppler_path se necessário
            convert_kwargs = {
                'pdf_path': pdf_path,
                'dpi': options.dpi,
                'fmt': 'jpeg',
                'thread_count': 1
            }
            
            if poppler_path:
                convert_kwargs['poppler_path'] = poppler_path
                print(f"  → Usando Poppler em: {poppler_path}")
            
            images = pdf2image.convert_from_path(**convert_kwargs)
            
            if not images:
                print("    ✗ Falha na conversão PDF para JPG")
                return False
            
            print(f"    ✓ Convertido para {len(images)} página(s)")
            
            # Prepara todas as páginas para impressão
            page_jobs = []
            
            for page_num, image in enumerate(images, 1):
                # Otimiza a imagem para impressão
                if options.color_mode == ColorMode.MONOCROMO:
                    image = image.convert('L')  # Converte para escala de cinza
                elif image.mode not in ['RGB', 'L']:
                    image = image.convert('RGB')
                
                # Define nome do arquivo (normalizado)
                if len(images) > 1:
                    image_filename = f"{safe_base_name}_p{page_num:02d}.jpg"
                    page_job_name = f"{job_name}_p{page_num:02d}"
                else:
                    image_filename = f"{safe_base_name}.jpg"
                    page_job_name = job_name
                
                image_path = os.path.join(temp_folder, image_filename)
                
                # Salva a imagem no disco
                jpg_quality = 95 if options.quality == Quality.ALTA else 85
                image.save(image_path, format='JPEG', quality=jpg_quality, optimize=True)
                
                # Lê a imagem salva do disco
                with open(image_path, 'rb') as f:
                    jpg_data = f.read()
                
                # Cria objeto PageJob
                page_job = PageJob(
                    page_num=page_num,
                    image_path=image_path,
                    jpg_data=jpg_data,
                    job_name=page_job_name
                )
                page_jobs.append(page_job)
                
                # Obtém tamanho do arquivo salvo
                file_size = len(jpg_data)
                print(f"    ✓ Página {page_num} preparada: {image_filename} ({file_size:,} bytes)")
            
            print(f"\n📁 Imagens salvas em: {temp_folder}")
            print("📋 Arquivos criados:")
            for page_job in page_jobs:
                print(f"  - {os.path.basename(page_job.image_path)}")
            
            # Processa as páginas com sistema de retry
            return self._process_pages_with_retry(page_jobs, options)
            
        except Exception as e:
            print(f"    ✗ Erro na conversão/preparação JPG: {e}")
            if temp_folder and os.path.exists(temp_folder):
                print(f"    📁 Imagens parciais mantidas em: {temp_folder}")
            return False
    
    def _process_pages_with_retry(self, page_jobs: list, options: PrintOptions) -> bool:
        """Processa páginas com sistema de retry inteligente"""
        
        # Usa endpoints válidos se disponíveis, senão usa lista padrão
        if hasattr(self, 'valid_endpoints') and self.valid_endpoints:
            endpoints = self.valid_endpoints
        else:
            endpoints = ["/ipp/print", "/ipp", "/printers/ipp", "/printers", ""]
            
        successful_pages = []
        failed_pages = list(page_jobs)  # Copia inicial
        retry_delays = [2, 5, 10]  # Delays progressivos em segundos
        
        # Primeira passada - tenta todas as páginas
        print(f"\n🔄 Processando {len(page_jobs)} página(s)...")
        
        for attempt in range(max(p.max_attempts for p in page_jobs)):
            if not failed_pages:
                break
                
            current_failed = []
            
            for page_job in failed_pages:
                page_job.attempts += 1
                
                print(f"\n  → Enviando página {page_job.page_num}/{len(page_jobs)} como JPG (tentativa {page_job.attempts}/{page_job.max_attempts})")
                print(f"    Tamanho JPG página {page_job.page_num}: {len(page_job.jpg_data):,} bytes")
                
                # Tenta enviar esta página
                page_success = False
                
                for endpoint_idx, endpoint in enumerate(endpoints):
                    url = f"{self.base_url}{endpoint}"
                    
                    # Atributos IPP para JPG - com nome normalizado
                    attributes = {
                        "printer-uri": url,
                        "requesting-user-name": normalize_filename(os.getenv("USER", "usuario")),
                        "job-name": page_job.job_name,
                        "document-name": page_job.job_name,
                        "document-format": "image/jpeg",
                        "ipp-attribute-fidelity": False,
                        "job-priority": 50,
                        "copies": options.copies if page_job.page_num == 1 else 1,  # Cópias apenas na primeira página
                        "orientation-requested": 3 if options.orientation == "portrait" else 4,
                        "print-quality": options.quality.value,
                        "media": options.paper_size,
                    }
                    
                    # Para JPG, não aplicamos duplex (cada página é individual)
                    if options.color_mode != ColorMode.AUTO:
                        attributes["print-color-mode"] = options.color_mode.value
                    
                    if self._send_ipp_request(url, attributes, page_job.jpg_data):
                        page_success = True
                        break
                    
                    # Se falhou no primeiro endpoint, aguarda um pouco antes do próximo
                    if endpoint_idx == 0 and not page_success:
                        print(f"    ⏳ Aguardando 1s antes do próximo endpoint...")
                        time.sleep(1)
                
                if page_success:
                    print(f"    ✓ Página {page_job.page_num} enviada com sucesso")
                    successful_pages.append(page_job)
                else:
                    print(f"    ✗ Falha ao enviar página {page_job.page_num}")
                    
                    if page_job.attempts < page_job.max_attempts:
                        current_failed.append(page_job)
                        # Aguarda antes da próxima tentativa
                        delay = retry_delays[min(page_job.attempts - 1, len(retry_delays) - 1)]
                        print(f"    ⏳ Aguardando {delay}s antes da próxima tentativa...")
                        time.sleep(delay)
                    else:
                        print(f"    ❌ Página {page_job.page_num} falhou após {page_job.max_attempts} tentativas")
            
            failed_pages = current_failed
            
            # Se ainda há páginas falhando e não é a última tentativa, aguarda mais um pouco
            if failed_pages and attempt < max(p.max_attempts for p in page_jobs) - 1:
                print(f"\n⏳ Aguardando 3s antes da próxima rodada de tentativas...")
                time.sleep(3)
        
        # Relatório final
        total_pages = len(page_jobs)
        successful_count = len(successful_pages)
        failed_count = total_pages - successful_count
        
        print(f"\n📊 Relatório de impressão:")
        print(f"  ✅ Páginas enviadas com sucesso: {successful_count}/{total_pages}")
        print(f"  ❌ Páginas que falharam: {failed_count}/{total_pages}")
        
        if successful_pages:
            print(f"  📄 Páginas bem-sucedidas: {', '.join(str(p.page_num) for p in successful_pages)}")
        
        remaining_failed = [p for p in page_jobs if p not in successful_pages]
        if remaining_failed:
            print(f"  🚫 Páginas que falharam: {', '.join(str(p.page_num) for p in remaining_failed)}")
            print(f"  📁 Imagens mantidas em: {os.path.dirname(remaining_failed[0].image_path)}")
            print(f"  💡 Você pode tentar reimprimir manualmente as páginas que falharam")
        else:
            print(f"  ✅ Todas as páginas foram processadas com sucesso!")
            temp_folder = os.path.dirname(page_jobs[0].image_path)
            print(f"  📁 Imagens temporárias mantidas em: {temp_folder}")
            print(f"  💡 Você pode remover a pasta manualmente após validar as impressões")
        
        return successful_count == total_pages

    def _build_ipp_request(self, operation: int, attributes: Dict[str, Any]) -> bytes:
        """Constrói uma requisição IPP completa"""
        
        # Cabeçalho IPP
        packet = struct.pack('>HHI', IPPVersion.IPP_1_1, operation, self.request_id)
        self.request_id += 1
        
        # Tag de operação
        packet += struct.pack('>B', IPPTag.OPERATION)
        
        # Atributos obrigatórios primeiro
        packet += IPPEncoder.encode_string(IPPTag.CHARSET, 
                                         "attributes-charset", "utf-8")
        packet += IPPEncoder.encode_string(IPPTag.LANGUAGE, 
                                         "attributes-natural-language", "en-us")
        
        # Adiciona outros atributos
        for name, value in attributes.items():
            if name in ["attributes-charset", "attributes-natural-language"]:
                continue
                
            if isinstance(value, str):
                if name == "printer-uri":
                    packet += IPPEncoder.encode_string(IPPTag.URI, name, value)
                elif name in ["requesting-user-name", "job-name", "document-name"]:
                    packet += IPPEncoder.encode_string(IPPTag.NAME, name, value)
                elif name == "document-format":
                    packet += IPPEncoder.encode_string(IPPTag.MIMETYPE, name, value)
                elif name in ["print-color-mode", "sides", "media"]:
                    packet += IPPEncoder.encode_string(IPPTag.KEYWORD, name, value)
                else:
                    packet += IPPEncoder.encode_string(IPPTag.TEXT, name, value)
                    
            elif isinstance(value, int):
                if name in ["copies", "job-priority"]:
                    packet += IPPEncoder.encode_integer(IPPTag.INTEGER, name, value)
                elif name in ["print-quality", "orientation-requested"]:
                    packet += IPPEncoder.encode_enum(name, value)
                    
            elif isinstance(value, bool):
                packet += IPPEncoder.encode_boolean(name, value)
        
        # Tag de job
        packet += struct.pack('>B', IPPTag.JOB)
        
        # Tag de fim
        packet += struct.pack('>B', IPPTag.END)
        
        return packet
    
    def _send_ipp_request(self, url: str, attributes: Dict[str, Any], document_data: bytes) -> bool:
        """Envia requisição IPP com múltiplas estratégias para máxima compatibilidade"""
        
        # Constrói requisição IPP
        ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
        ipp_request += document_data
        
        print(f"    Tentando: {url}")
        
        # Estratégia 1: Headers minimalistas
        if self._try_minimal_headers(url, ipp_request):
            return True
            
        # Estratégia 2: Headers compatíveis
        if self._try_compatible_headers(url, ipp_request):
            return True
            
        # Estratégia 3: HTTP/1.0 direto
        if self._send_ipp_request_http10(url, attributes, document_data):
            return True
            
        # Estratégia 4: Raw socket (último recurso)
        return self._try_raw_socket(url, ipp_request)
    
    def _try_minimal_headers(self, url: str, ipp_request: bytes) -> bool:
        """Tenta com headers mínimos essenciais"""
        try:
            headers = {
                'Content-Type': 'application/ipp',
                'Content-Length': str(len(ipp_request))
            }
            
            response = requests.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=30,
                verify=False
            )
            
            print(f"    Minimal Headers - HTTP Status: {response.status_code}")
            
            if response.status_code == 200 and len(response.content) >= 8:
                status_code = struct.unpack('>H', response.content[2:4])[0]
                if status_code in [0x0000, 0x0001]:
                    print(f"    ✓ Sucesso com headers mínimos!")
                    return True
            
        except Exception as e:
            print(f"    Minimal Headers - Erro: {e}")
        
        return False
    
    def _try_compatible_headers(self, url: str, ipp_request: bytes) -> bool:
        """Tenta com headers mais compatíveis"""
        try:
            headers = {
                'Content-Type': 'application/ipp',
                'User-Agent': 'CUPS/2.3',
                'Accept': 'application/ipp',
                'Content-Length': str(len(ipp_request)),
                'Connection': 'close'
            }
            
            response = requests.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=30,
                verify=False
            )
            
            print(f"    Compatible Headers - HTTP Status: {response.status_code}")
            
            if response.status_code == 200 and len(response.content) >= 8:
                status_code = struct.unpack('>H', response.content[2:4])[0]
                if status_code in [0x0000, 0x0001]:
                    print(f"    ✓ Sucesso com headers compatíveis!")
                    return True
            
        except Exception as e:
            print(f"    Compatible Headers - Erro: {e}")
        
        return False
    
    def _try_raw_socket(self, url: str, ipp_request: bytes) -> bool:
        """Último recurso: conexão raw socket com HTTP básico"""
        try:
            parsed_url = urlparse(url)
            host = parsed_url.hostname
            port = parsed_url.port or 631
            path = parsed_url.path or '/'
            
            # Constrói requisição HTTP manualmente
            http_request = f"POST {path} HTTP/1.0\r\n"
            http_request += f"Host: {host}:{port}\r\n"
            http_request += f"Content-Type: application/ipp\r\n"
            http_request += f"Content-Length: {len(ipp_request)}\r\n"
            http_request += f"Connection: close\r\n"
            http_request += "\r\n"
            
            # Conecta via socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(30)
            sock.connect((host, port))
            
            # Envia requisição
            sock.send(http_request.encode('ascii'))
            sock.send(ipp_request)
            
            # Lê resposta
            response_data = b""
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk:
                        break
                    response_data += chunk
                except socket.timeout:
                    break
            
            sock.close()
            
            # Analisa resposta
            if b"HTTP/1." in response_data[:20]:
                status_line = response_data.split(b'\r\n')[0].decode('ascii')
                status_code = int(status_line.split()[1])
                
                print(f"    Raw Socket - HTTP Status: {status_code}")
                
                if status_code == 200:
                    # Encontra início dos dados IPP (após headers HTTP)
                    ipp_start = response_data.find(b'\r\n\r\n')
                    if ipp_start >= 0:
                        ipp_data = response_data[ipp_start + 4:]
                        if len(ipp_data) >= 8:
                            ipp_status = struct.unpack('>H', ipp_data[2:4])[0]
                            if ipp_status in [0x0000, 0x0001]:
                                print(f"    ✓ Sucesso com raw socket!")
                                return True
            
        except Exception as e:
            print(f"    Raw Socket - Erro: {e}")
        
        return False

    def _send_ipp_request_http10(self, url: str, attributes: Dict[str, Any], document_data: bytes) -> bool:
        """Fallback usando HTTP/1.0 simplificado"""
        
        try:
            parsed_url = urlparse(url)
            
            # Constrói requisição IPP
            ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
            ipp_request += document_data
            
            # Usa HTTP/1.0 manualmente com headers mínimos
            if parsed_url.scheme == 'https':
                conn = http.client.HTTPSConnection(
                    parsed_url.hostname, 
                    parsed_url.port or 631,
                    timeout=30
                )
            else:
                conn = http.client.HTTPConnection(
                    parsed_url.hostname, 
                    parsed_url.port or 631,
                    timeout=30
                )
            
            # Headers mínimos para HTTP/1.0
            headers = {
                'Content-Type': 'application/ipp',
                'Content-Length': str(len(ipp_request))
            }
            
            path = parsed_url.path if parsed_url.path else '/'
            
            print(f"    Fallback HTTP/1.0: {url}")
            
            # Faz requisição HTTP/1.0 explícita
            conn.putrequest('POST', path, skip_host=True, skip_accept_encoding=True)
            conn.putheader('Host', f"{parsed_url.hostname}:{parsed_url.port or 631}")
            for header, value in headers.items():
                conn.putheader(header, value)
            conn.endheaders()
            
            # Envia dados
            conn.send(ipp_request)
            
            response = conn.getresponse()
            response_data = response.read()
            
            print(f"    HTTP/1.0 Status: {response.status}")
            
            conn.close()
            
            if response.status == 200 and len(response_data) >= 8:
                status_code = struct.unpack('>H', response_data[2:4])[0]
                print(f"    IPP Status (HTTP/1.0): 0x{status_code:04X}")
                
                if status_code in [0x0000, 0x0001]:
                    print(f"    ✓ HTTP/1.0 funcionou!")
                    return True
            
            return False
            
        except Exception as e:
            print(f"    ✗ Erro HTTP/1.0: {e}")
            return False
    
    def _extract_job_id_from_response(self, ipp_response: bytes) -> Optional[int]:
        """Extrai job-id de uma resposta IPP"""
        try:
            search_pattern = b'\x21\x00\x06job-id\x00\x04'
            idx = ipp_response.find(search_pattern)
            
            if idx >= 0:
                value_idx = idx + len(search_pattern)
                if value_idx + 4 <= len(ipp_response):
                    job_id = struct.unpack('>I', ipp_response[value_idx:value_idx+4])[0]
                    return job_id
                    
        except Exception as e:
            print(f"    Erro ao extrair job-id: {e}")
            
        return None

def main():
    parser = argparse.ArgumentParser(
        description='Sistema de impressão IPP para arquivos PDF com fallback JPG',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  # Impressão básica de arquivo PDF
  %(prog)s --ip 192.168.1.100 --file documento.pdf
  
  # Impressão colorida, frente e verso, 2 cópias
  %(prog)s --ip 192.168.1.100 --file documento.pdf --color --duplex --copies 2
  
  # Impressão com alta qualidade e resolução
  %(prog)s --ip 192.168.1.100 --file documento.pdf --quality alta --dpi 600
  
  # Usar HTTPS
  %(prog)s --ip 192.168.1.100 --file documento.pdf --https
        """
    )
    
    # Argumentos obrigatórios
    parser.add_argument('--ip', required=True, help='IP da impressora')
    parser.add_argument('--file', required=True, help='Arquivo PDF para imprimir (.pdf)')
    
    # Opções de conexão
    parser.add_argument('--port', type=int, default=631, help='Porta IPP (padrão: 631)')
    parser.add_argument('--https', action='store_true', help='Usar HTTPS')
    
    # Opções de impressão
    parser.add_argument('--color', action='store_true', help='Impressão colorida')
    parser.add_argument('--mono', action='store_true', help='Impressão monocromática')
    parser.add_argument('--duplex', action='store_true', help='Frente e verso (borda longa)')
    parser.add_argument('--duplex-short', action='store_true', help='Frente e verso (borda curta)')
    parser.add_argument('--copies', type=int, default=1, help='Número de cópias')
    parser.add_argument('--quality', choices=['rascunho', 'normal', 'alta'],
                       default='normal', help='Qualidade de impressão')
    parser.add_argument('--landscape', action='store_true', help='Orientação paisagem')
    parser.add_argument('--job-name', help='Nome do trabalho de impressão')
    parser.add_argument('--dpi', type=int, default=300, 
                       help='DPI para conversão JPG (padrão: 300)')
    
    args = parser.parse_args()
    
    # Normaliza o nome do job se fornecido
    if args.job_name:
        args.job_name = normalize_filename(args.job_name)
        print(f"Nome do trabalho normalizado: {args.job_name}")
    
    # Cria objeto da impressora
    printer = PDFPrinter(args.ip, args.port, args.https)
    
    # Configura opções
    options = PrintOptions()
    
    if args.mono:
        options.color_mode = ColorMode.MONOCROMO
    elif args.color:
        options.color_mode = ColorMode.COLORIDO
        
    if args.duplex_short:
        options.duplex = Duplex.DUPLEX_CURTO
    elif args.duplex:
        options.duplex = Duplex.DUPLEX_LONGO
        
    quality_map = {
        'rascunho': Quality.RASCUNHO,
        'normal': Quality.NORMAL,
        'alta': Quality.ALTA
    }
    options.quality = quality_map[args.quality]
    
    options.copies = args.copies
    options.orientation = "landscape" if args.landscape else "portrait"
    options.dpi = args.dpi
    
    success = printer.print_file(args.file, options, args.job_name)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
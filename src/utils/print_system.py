#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sistema de impressão IPP para arquivos PDF integrado ao sistema de gerenciamento
VERSÃO FINAL - IGUAL AO CÓDIGO DE TESTE QUE FUNCIONA
"""

import os
import tempfile
import time
import sys
import struct
import subprocess
import threading
import logging
import queue
import socket
from typing import Dict, Optional, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
import platform
import zipfile
import urllib.request
import shutil
import wx
import json
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import struct
import ssl
import requests
import re
import unicodedata
from src.utils.subprocess_utils import run_hidden, popen_hidden, check_output_hidden

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger("PrintManagementSystem.Utils.PrintSystem")

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

# Instalação automática de dependências
def install_package(package):
    try:
        result = run_hidden([sys.executable, "-m", "pip", "install", package],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    check=True)
        logger.info(f"Pacote {package} instalado com sucesso")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao instalar {package}: {e}")
        return False

# Verifica e instala dependências
def check_dependencies():
    required_packages = ['requests', 'Pillow', 'pdf2image']
    missing_packages = []
    
    # Verifica cada pacote
    for package in required_packages:
        try:
            if package == 'pdf2image':
                import pdf2image
            elif package == 'Pillow':
                from PIL import Image
            elif package == 'requests':
                import requests
        except ImportError:
            missing_packages.append(package)
    
    # Instala pacotes faltantes
    if missing_packages:
        logger.info(f"Instalando pacotes faltantes: {missing_packages}")
        for package in missing_packages:
            if install_package(package):
                logger.info(f"Pacote {package} instalado com sucesso")
            else:
                logger.error(f"Falha ao instalar {package}")
                return False
    
    # Importa os pacotes após instalação
    try:
        import requests
        from PIL import Image
        import pdf2image
        return True
    except ImportError as e:
        logger.error(f"Falha ao importar dependências após instalação: {e}")
        return False

# Gerencia o Poppler para conversão de PDF para imagem
import os
import platform
import subprocess
import urllib.request
import zipfile
import shutil
import logging
import tempfile
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

class PopplerManager:
    @staticmethod
    def get_poppler_path():
        """Retorna o caminho do Poppler se estiver instalado"""
        system = platform.system().lower()
        
        if system == "windows":
            # Verifica se poppler já está no PATH
            try:
                result = run_hidden(['pdftoppm', '-h'],
                    capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    logger.info("Poppler encontrado no PATH do sistema")
                    return None  # Já está no PATH
            except Exception as e:
                logger.debug(f"Poppler não encontrado no PATH: {e}")
            
            # Procura por instalação local do poppler
            possible_paths = [
                os.path.join(os.getcwd(), "poppler", "bin"),
                os.path.join(os.getcwd(), "poppler", "Library", "bin"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "bin"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "Library", "bin"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "library", "bin"),
                r"C:\Program Files\poppler\Library\bin",
                r"C:\Program Files\poppler\library\bin",
                r"C:\Program Files\poppler\bin",
                r"C:\Program Files (x86)\poppler\Library\bin",
                r"C:\Program Files (x86)\poppler\library\bin",
                r"C:\Program Files (x86)\poppler\bin",
                r"C:\poppler\Library\bin",
                r"C:\poppler\library\bin",
                r"C:\poppler\bin",
            ]
            
            for path in possible_paths:
                pdftoppm_path = os.path.join(path, "pdftoppm.exe")
                if os.path.exists(pdftoppm_path):
                    logger.info(f"Poppler encontrado em: {path}")
                    return path
            
            logger.info("Poppler não encontrado em nenhum caminho conhecido")
            return None
        
        # Para Linux/Mac, geralmente está no PATH
        return None

    @staticmethod
    def verify_permissions(directory):
        """Verifica se temos permissões adequadas no diretório"""
        try:
            # Testa criação de arquivo temporário
            test_file = os.path.join(directory, "test_permissions.tmp")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"Sem permissões adequadas em {directory}: {e}")
            return False

    @staticmethod
    def get_alternative_install_path():
        """Retorna um caminho alternativo para instalação quando não há permissões"""
        # Tenta usar o diretório do usuário
        user_dir = os.path.expanduser("~")
        poppler_dir = os.path.join(user_dir, ".poppler")
        
        if not os.path.exists(poppler_dir):
            try:
                os.makedirs(poppler_dir, exist_ok=True)
                if PopplerManager.verify_permissions(poppler_dir):
                    return poppler_dir
            except Exception as e:
                logger.error(f"Não foi possível criar diretório alternativo: {e}")
        
        # Tenta usar temp
        temp_dir = tempfile.gettempdir()
        poppler_temp = os.path.join(temp_dir, "poppler_portable")
        
        try:
            os.makedirs(poppler_temp, exist_ok=True)
            if PopplerManager.verify_permissions(poppler_temp):
                return poppler_temp
        except Exception as e:
            logger.error(f"Não foi possível usar diretório temporário: {e}")
        
        return None

    @staticmethod
    def install_poppler_windows():
        """Instala Poppler no Windows automaticamente"""
        logger.info("Instalando Poppler para Windows...")
        
        try:
            # URL do Poppler para Windows (versão portável)
            poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.08.0-0/Release-23.08.0-0.zip"
            
            # Determina pasta de destino
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            poppler_dir = os.path.join(script_dir, "poppler")
            
            # Verifica permissões no diretório do script
            if not PopplerManager.verify_permissions(script_dir):
                logger.warning("Sem permissões no diretório do script, usando alternativo...")
                alternative_base = PopplerManager.get_alternative_install_path()
                if alternative_base:
                    poppler_dir = alternative_base
                    script_dir = os.path.dirname(alternative_base)
                else:
                    logger.error("Não foi possível encontrar local adequado para instalação")
                    return None
            
            zip_path = os.path.join(script_dir, "poppler_temp.zip")
            
            logger.info(f"Instalando Poppler em: {poppler_dir}")
            
            # Remove instalação anterior se existir
            if os.path.exists(poppler_dir):
                try:
                    shutil.rmtree(poppler_dir)
                    logger.info("Instalação anterior removida")
                except Exception as e:
                    logger.error(f"Erro ao remover instalação anterior: {e}")
                    return None
            
            logger.info("Baixando Poppler...")
            # Adiciona headers para evitar bloqueios
            request = urllib.request.Request(
                poppler_url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
            )
            
            with urllib.request.urlopen(request, timeout=30) as response:
                with open(zip_path, 'wb') as f:
                    shutil.copyfileobj(response, f)
            
            # Verifica se o download foi bem-sucedido
            if not os.path.exists(zip_path) or os.path.getsize(zip_path) < 1000:
                logger.error("Download falhou ou arquivo corrompido")
                return None
            
            logger.info(f"Arquivo baixado: {os.path.getsize(zip_path)} bytes")
            logger.info("Extraindo arquivos...")
            
            # Extrai com tratamento de erro mais detalhado
            try:
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    # Lista o conteúdo do arquivo
                    file_list = zip_ref.namelist()
                    logger.info(f"Arquivos no ZIP: {len(file_list)}")
                    
                    # Extrai todos os arquivos
                    zip_ref.extractall(script_dir)
                    logger.info("Extração concluída")
                    
            except zipfile.BadZipFile:
                logger.error("Arquivo ZIP corrompido")
                return None
            except Exception as e:
                logger.error(f"Erro na extração: {e}")
                return None
            
            # Encontra e renomeia a pasta extraída
            extracted_folders = [f for f in os.listdir(script_dir) 
                               if f.startswith("poppler-") and os.path.isdir(os.path.join(script_dir, f))]
            
            if not extracted_folders:
                # Tenta encontrar qualquer pasta que contenha bin/pdftoppm.exe
                for item in os.listdir(script_dir):
                    item_path = os.path.join(script_dir, item)
                    if os.path.isdir(item_path):
                        bin_path = os.path.join(item_path, "bin", "pdftoppm.exe")
                        if os.path.exists(bin_path):
                            extracted_folders = [item]
                            break
            
            if extracted_folders:
                old_name = os.path.join(script_dir, extracted_folders[0])
                logger.info(f"Renomeando {old_name} para {poppler_dir}")
                
                try:
                    os.rename(old_name, poppler_dir)
                except Exception as e:
                    logger.error(f"Erro ao renomear pasta: {e}")
                    # Tenta copiar ao invés de renomear
                    try:
                        shutil.copytree(old_name, poppler_dir)
                        shutil.rmtree(old_name)
                        logger.info("Copiado com sucesso")
                    except Exception as e2:
                        logger.error(f"Erro ao copiar: {e2}")
                        return None
            else:
                logger.error("Pasta extraída não encontrada")
                return None
            
            # Remove o arquivo zip
            try:
                os.remove(zip_path)
            except Exception as e:
                logger.warning(f"Não foi possível remover arquivo ZIP: {e}")
            
            # Verifica se a instalação foi bem-sucedida
            possible_bin_paths = [
                os.path.join(poppler_dir, "bin"),
                os.path.join(poppler_dir, "Library", "bin"),
                os.path.join(poppler_dir, "library", "bin")
            ]
            
            for bin_path in possible_bin_paths:
                pdftoppm_path = os.path.join(bin_path, "pdftoppm.exe")
                if os.path.exists(pdftoppm_path):
                    logger.info(f"Poppler instalado com sucesso em: {bin_path}")
                    
                    # Testa se o executável funciona
                    try:
                        result = run_hidden([pdftoppm_path, '-h'],
                            capture_output=True, text=True, timeout=5)
                        if result.returncode == 0:
                            logger.info("Poppler testado e funcionando")
                            return bin_path
                        else:
                            logger.warning("Poppler instalado mas não está funcionando corretamente")
                    except Exception as e:
                        logger.warning(f"Erro ao testar Poppler: {e}")
                    
                    return bin_path
            
            logger.error("Executável pdftoppm.exe não encontrado após instalação")
            return None
                
        except urllib.error.URLError as e:
            logger.error(f"Erro de conexão ao baixar Poppler: {e}")
            return None
        except Exception as e:
            logger.error(f"Erro ao instalar Poppler: {e}")
            return None

    @staticmethod
    def setup_poppler():
        """Configura o Poppler para uso com pdf2image"""
        system = platform.system().lower()
        
        if system == "windows":
            poppler_path = PopplerManager.get_poppler_path()
            
            if poppler_path is None:
                logger.info("Poppler não encontrado. Instalando automaticamente...")
                poppler_path = PopplerManager.install_poppler_windows()
                
                if poppler_path is None:
                    logger.error("Não foi possível instalar o Poppler automaticamente.")
                    logger.error("Soluções alternativas:")
                    logger.error("1. Instale o Poppler manualmente: https://github.com/oschwartz10612/poppler-windows/releases")
                    logger.error("2. Adicione o Poppler ao PATH do sistema")
                    logger.error("3. Execute o script como administrador")
                    return None
            
            return poppler_path
        
        else:
            # Para Linux/Mac
            try:
                result = run_hidden(['pdftoppm', '-h'],
                    capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return None  # Já está disponível
            except Exception as e:
                logger.debug(f"Poppler não encontrado: {e}")
            
            logger.error("Poppler não encontrado.")
            logger.error("Instale com: sudo apt-get install poppler-utils (Ubuntu/Debian)")
            logger.error("ou: brew install poppler (macOS)")
            return None

    @staticmethod
    def diagnose_poppler():
        """Diagnóstica problemas com o Poppler"""
        logger.info("=== DIAGNÓSTICO POPPLER ===")
        
        system = platform.system().lower()
        logger.info(f"Sistema operacional: {system}")
        
        if system == "windows":
            # Verifica PATH
            try:
                result = subprocess.run(['pdftoppm', '-h'], 
                                     capture_output=True, text=True, timeout=5)
                logger.info(f"Poppler no PATH: {'SIM' if result.returncode == 0 else 'NÃO'}")
            except:
                logger.info("Poppler no PATH: NÃO")
            
            # Verifica caminhos conhecidos
            logger.info("Verificando caminhos conhecidos...")
            possible_paths = [
                os.path.join(os.getcwd(), "poppler", "bin"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "bin"),
                r"C:\Program Files\poppler\bin",
                r"C:\Program Files (x86)\poppler\bin",
                r"C:\poppler\bin",
            ]
            
            for path in possible_paths:
                exists = os.path.exists(os.path.join(path, "pdftoppm.exe"))
                logger.info(f"  {path}: {'ENCONTRADO' if exists else 'NÃO ENCONTRADO'}")
            
            # Verifica permissões
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            has_perms = PopplerManager.verify_permissions(script_dir) if os.path.exists(script_dir) else False
            logger.info(f"Permissões no diretório do script: {'OK' if has_perms else 'NEGADAS'}")
            
        logger.info("=== FIM DIAGNÓSTICO ===")

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

IPP_STATUS_CODES = {
    0x0000: "successful-ok",
    0x0001: "successful-ok-ignored-or-substituted-attributes",
    0x0002: "successful-ok-conflicting-attributes",
    0x0400: "client-error-bad-request",
    0x0401: "client-error-forbidden",
    0x0402: "client-error-not-authenticated",
    0x0403: "client-error-not-authorized",
    0x0404: "client-error-not-possible",
    0x0405: "client-error-timeout",
    0x0406: "client-error-not-found",
    0x0407: "client-error-gone",
    0x0408: "client-error-request-entity-too-large",
    0x0409: "client-error-request-value-too-long",
    0x040A: "client-error-document-format-not-supported",
    0x040B: "client-error-attributes-or-values-not-supported",
    0x040C: "client-error-uri-scheme-not-supported",
    0x040D: "client-error-charset-not-supported",
    0x040E: "client-error-conflicting-attributes",
    0x040F: "client-error-compression-not-supported",
    0x0410: "client-error-compression-error",
    0x0411: "client-error-document-format-error",
    0x0412: "client-error-document-access-error",
    0x0500: "server-error-internal-error",
    0x0501: "server-error-operation-not-supported",
    0x0502: "server-error-service-unavailable",
    0x0503: "server-error-version-not-supported",
    0x0504: "server-error-device-error",
    0x0505: "server-error-temporary-error",
    0x0506: "server-error-not-accepting-jobs",
    0x0507: "server-error-busy",
    0x0508: "server-error-job-canceled",
    0x0509: "server-error-multiple-document-jobs-not-supported",
}

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

@dataclass
class PrintJobInfo:
    """Armazena informações sobre um trabalho de impressão"""
    job_id: str
    document_path: str
    document_name: str
    printer_name: str
    printer_id: str
    printer_ip: str
    options: PrintOptions
    start_time: datetime
    status: str = "pending"
    total_pages: int = 0
    completed_pages: int = 0
    end_time: Optional[datetime] = None
    
    def to_dict(self):
        """Converte para dicionário para armazenamento no config"""
        return {
            "job_id": self.job_id,
            "document_path": self.document_path,
            "document_name": self.document_name,
            "printer_name": self.printer_name,
            "printer_id": self.printer_id,
            "printer_ip": self.printer_ip,
            "options": {
                "color_mode": self.options.color_mode.value,
                "duplex": self.options.duplex.value,
                "quality": self.options.quality.value,
                "copies": self.options.copies,
                "orientation": self.options.orientation,
                "paper_size": self.options.paper_size,
                "dpi": self.options.dpi
            },
            "start_time": self.start_time.isoformat(),
            "status": self.status,
            "total_pages": self.total_pages,
            "completed_pages": self.completed_pages,
            "end_time": self.end_time.isoformat() if self.end_time else None
        }

class IPPEncoder:
    """Codificador para protocolo IPP - IGUAL AO CÓDIGO DE TESTE"""
    
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

class IPPPrinter:
    """Classe principal para impressão de arquivos PDF via IPP - IGUAL AO CÓDIGO DE TESTE"""
    
    def __init__(self, printer_ip: str, port: int = 631, use_https: bool = False):
        # Verifica dependências
        if not check_dependencies():
            raise ImportError("Falha ao verificar/instalar dependências para impressão")
            
        # Importa após verificação
        global requests
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        # Configuração de retry para requisições HTTP
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Usa a sessão configurada
        self.session = session
        
        self.printer_ip = printer_ip
        self.port = port
        self.use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.base_url = f"{self.protocol}://{printer_ip}:{port}"
        self.request_id = 1
        self.discovered_endpoints = []
        
        # Se não especificou HTTPS, detecta automaticamente
        if not use_https:
            self._auto_detect_https()
        
        logger.info(f"Protocolo final: {self.protocol} - {self.base_url}")
        
        # Descobre endpoints disponíveis
        self.discovered_endpoints = self._discover_printer_endpoints()
    
    def _discover_printer_endpoints(self):
        """Descobre os endpoints disponíveis na impressora"""
        logger.info(f"Descobrindo endpoints para a impressora {self.printer_ip}")
        
        # Primeiro tenta o caminho padrão para HP, Brother, Epson, etc.
        base_endpoints = [
            "/ipp/print", 
            "/ipp/printer", 
            "/ipp", 
            "/printers/ipp", 
            "/printers",
            "/printer",
            "/ipp/port1",    # Comum em impressoras Brother
            "/Printer",      # Algumas HP e Xerox
            ""               # Fallback para raiz
        ]
        
        # Tenta encontrar o endpoint correto
        working_endpoints = []
        
        for endpoint in base_endpoints:
            url = f"{self.base_url}{endpoint}"
            try:
                logger.info(f"Testando endpoint: {url}")
                response = requests.get(
                    url,
                    timeout=5,
                    verify=False,
                    allow_redirects=False
                )
                
                status = response.status_code
                logger.info(f"Endpoint {endpoint} retornou HTTP {status}")
                
                # Considera os seguintes códigos como potencialmente válidos
                if status in [200, 400, 401, 403, 404, 405, 426]:
                    working_endpoints.append({
                        "endpoint": endpoint,
                        "status": status,
                        "url": url
                    })
                    
                    # Se receber 426, precisa mudar para HTTPS
                    if status == 426 and not self.use_https:
                        logger.info(f"Endpoint {endpoint} requer HTTPS")
                        self.use_https = True
                        self.protocol = "https"
                        self.base_url = f"https://{self.printer_ip}:{self.port}"
                        # Recomeça a descoberta com HTTPS
                        return self._discover_printer_endpoints()
                        
            except requests.exceptions.ConnectionError as e:
                if ("10054" in str(e) or "Connection aborted" in str(e)) and not self.use_https:
                    logger.info(f"Conexão abortada ao testar {endpoint}, tentando com HTTPS")
                    self.use_https = True
                    self.protocol = "https"
                    self.base_url = f"https://{self.printer_ip}:{self.port}"
                    # Recomeça a descoberta com HTTPS
                    return self._discover_printer_endpoints()
                else:
                    logger.info(f"Erro de conexão ao testar {endpoint}: {e}")
            except Exception as e:
                logger.info(f"Erro ao testar {endpoint}: {e}")
        
        # Ordena por status HTTP para priorizar endpoints que retornaram 200
        working_endpoints.sort(key=lambda x: x["status"])
        
        if working_endpoints:
            logger.info(f"Endpoints encontrados: {[e['endpoint'] for e in working_endpoints]}")
            return working_endpoints
        else:
            logger.warning("Nenhum endpoint encontrado!")
            return [{"endpoint": "", "status": 0, "url": self.base_url}] 
        
    def _auto_detect_https(self):
        """Detecta automaticamente se precisa de HTTPS"""
        # Testa HTTP primeiro
        try:
            response = requests.get(
                f"http://{self.printer_ip}:{self.port}/ipp/print",
                timeout=3,
                verify=False,
                allow_redirects=False
            )
            
            # Se recebeu 426 (Upgrade Required), usa HTTPS
            if response.status_code == 426:
                logger.info("HTTP retornou 426 (Upgrade Required), forçando HTTPS")
                self.use_https = True
                self.protocol = "https"
                self.base_url = f"https://{self.printer_ip}:{self.port}"
                return True
                
        except requests.exceptions.ConnectionError as e:
            # Connection Reset indica que precisa de HTTPS
            if "10054" in str(e) or "Connection aborted" in str(e):
                logger.info("HTTP deu Connection Reset, forçando HTTPS")
                self.use_https = True
                self.protocol = "https"
                self.base_url = f"https://{self.printer_ip}:{self.port}"
                return True
        except Exception as e:
            # Se deu erro, tenta HTTPS
            logger.info(f"Erro em HTTP: {e}, forçando HTTPS")
            self.use_https = True
            self.protocol = "https"
            self.base_url = f"https://{self.printer_ip}:{self.port}"
            return True
        
        return False
        
    def print_file(self, file_path: str, options: PrintOptions, 
               job_name: Optional[str] = None, progress_callback=None, 
               job_info: Optional[PrintJobInfo] = None) -> Tuple[bool, Dict]:
        """Imprime um arquivo PDF com fallback automático para JPG e discovery de endpoints"""
        
        if not os.path.exists(file_path):
            logger.error(f"Erro: Arquivo não encontrado: {file_path}")
            return False, {"error": "Arquivo não encontrado"}
        
        # Verifica se é um arquivo PDF
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension != '.pdf':
            logger.error(f"Erro: Arquivo deve ser PDF (.pdf), recebido: {file_extension}")
            return False, {"error": "Arquivo deve ser PDF"}
        
        if job_name is None:
            job_name = os.path.basename(file_path)
        
        logger.info(f"Preparando impressão de: {job_name}")

        job_name = normalize_filename(job_name)
        logger.info(f"Nome do trabalho normalizado: {job_name}")

        logger.info(f"Impressora: {self.printer_ip}:{self.port}")
        
        # Lê o arquivo PDF
        try:
            with open(file_path, 'rb') as f:
                pdf_data = f.read()
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return False, {"error": f"Erro ao ler arquivo: {e}"}
        
        logger.info(f"Formato: PDF")
        logger.info(f"Tamanho do arquivo: {len(pdf_data):,} bytes")
        
        # Primeira tentativa: enviar como PDF
        logger.info("Tentativa 1: Enviando como PDF")
        if progress_callback:
            progress_callback("Tentativa 1: Enviando como PDF...")
            
        if self._print_as_pdf(pdf_data, job_name, options):
            logger.info("Impressão PDF enviada com sucesso!")
            if progress_callback:
                progress_callback("Impressão PDF enviada com sucesso!")
            return True, {"method": "pdf"}
        
        # Segunda tentativa: converter para JPG e enviar
        logger.info("Tentativa 2: Convertendo para JPG e enviando")
        if progress_callback:
            progress_callback("Tentativa 2: Convertendo para JPG e enviando...")
        
        success, result = self._convert_and_print_as_jpg(file_path, job_name, options, progress_callback, job_info)
        
        if success:
            logger.info("Impressão JPG enviada com sucesso!")
            if progress_callback:
                progress_callback("Impressão JPG enviada com sucesso!")
            return True, result
        
        logger.error("Ambas as tentativas falharam")
        if progress_callback:
            progress_callback("Falha: Ambas as tentativas de impressão falharam")
        
        # Adicione informações de diagnóstico ao resultado
        error_info = result.copy() if isinstance(result, dict) else {}
        error_info.update({
            "error": "Ambas as tentativas de impressão falharam",
            "printer_ip": self.printer_ip,
            "protocol": self.protocol,
            "endpoints_tested": [
                f"{self.protocol}://{self.printer_ip}:{self.port}/ipp/print",
                f"{self.protocol}://{self.printer_ip}:{self.port}/ipp",
                f"{self.protocol}://{self.printer_ip}:{self.port}/printers/ipp",
                f"{self.protocol}://{self.printer_ip}:{self.port}/printers",
                f"{self.protocol}://{self.printer_ip}:{self.port}"
            ]
        })
        
        return False, error_info

    
    def _print_as_pdf(self, pdf_data: bytes, job_name: str, options: PrintOptions) -> bool:
        # Normaliza o nome do trabalho
        job_name = normalize_filename(job_name)
        logger.info(f"Nome de trabalho normalizado: {job_name}")
        
        # Limita o número de tentativas para não ficar em loop infinito
        max_endpoint_tries = 2
        endpoint_tries = 0
        
        # Tenta cada endpoint descoberto
        for endpoint_info in self.discovered_endpoints[:max_endpoint_tries]:
            endpoint = endpoint_info["endpoint"]
            url = endpoint_info["url"]
            
            # Garante que a URL use o protocolo correto
            if self.use_https and url.startswith("http://"):
                url = url.replace("http://", "https://", 1)
            
            logger.info(f"Tentando imprimir PDF em: {url} (protocolo: {self.protocol})")
            
            # Cria URI IPP correto
            if self.use_https:
                printer_uri = url.replace("https://", "ipps://", 1)
            else:
                printer_uri = url.replace("http://", "ipp://", 1)
            
            # Atributos IPP para PDF com nome normalizado
            attributes = {
                "printer-uri": printer_uri,
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
                
            # Limita o tempo máximo de tentativa para este endpoint
            endpoint_tries += 1
            if self._send_ipp_request(url, attributes, pdf_data):
                return True
            
            # Breve pausa antes de tentar próximo endpoint
            time.sleep(1)
        
        # Se falhar após tentar todos os endpoints, vai para o modo JPG
        logger.info("Falha na tentativa de enviar como PDF, passando para JPG")
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

    def _convert_and_print_as_jpg(self, pdf_path: str, job_name: str, options: PrintOptions, 
                              progress_callback=None, job_info: Optional[PrintJobInfo] = None) -> Tuple[bool, Dict]:
        """Converte PDF para JPG e tenta imprimir - IGUAL AO CÓDIGO DE TESTE"""
        
        temp_folder = None
        
        try:
            logger.info("Convertendo PDF para JPG...")
            if progress_callback:
                progress_callback("Convertendo PDF para JPG...")
            
            # Importa após verificação de dependências
            import pdf2image
            from PIL import Image
            
            # Normaliza o nome do trabalho
            job_name = normalize_filename(job_name)
            logger.info(f"Nome do trabalho normalizado: {job_name}")
            
            # Configura Poppler
            poppler_path = PopplerManager.setup_poppler()
            
            # Cria pasta temporária para salvar as imagens
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            # Normaliza o nome base
            safe_base_name = normalize_filename(base_name)
            logger.info(f"Base do nome: {safe_base_name} (normalizado de: {base_name})")
            temp_folder = self._create_temp_folder(safe_base_name)
            logger.info(f"Pasta temporária: {temp_folder}")
            
            # Converte PDF para imagens com poppler_path se necessário
            convert_kwargs = {
                'pdf_path': pdf_path,
                'dpi': options.dpi,
                'fmt': 'jpeg',
                'thread_count': 1
            }
            
            if poppler_path:
                convert_kwargs['poppler_path'] = poppler_path
                logger.info(f"Usando Poppler em: {poppler_path}")
            
            images = pdf2image.convert_from_path(**convert_kwargs)
            
            if not images:
                logger.error("Falha na conversão PDF para JPG")
                return False, {"error": "Falha na conversão PDF para JPG"}
            
            logger.info(f"Convertido para {len(images)} página(s)")
            if progress_callback:
                progress_callback(f"Convertido para {len(images)} página(s)")
            
            # Prepara todas as páginas para impressão
            page_jobs = []
            
            for page_num, image in enumerate(images, 1):
                # Otimiza a imagem para impressão
                if options.color_mode == ColorMode.MONOCROMO:
                    image = image.convert('L')  # Converte para escala de cinza
                elif image.mode not in ['RGB', 'L']:
                    image = image.convert('RGB')
                
                safe_base_name = normalize_filename(base_name)
                logger.info(f"Base do nome normalizado: {safe_base_name}")

                # Define nome do arquivo
                if len(images) > 1:
                    image_filename = f"{safe_base_name}_p{page_num:02d}.jpg"
                    page_job_name = f"{normalize_filename(job_name)}_p{page_num:02d}"
                else:
                    image_filename = f"{safe_base_name}.jpg"
                    page_job_name = normalize_filename(job_name)

                
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
                logger.info(f"Página {page_num} preparada: {image_filename} ({file_size:,} bytes)")
            
            logger.info(f"Imagens salvas em: {temp_folder}")
            logger.info("Arquivos criados:")
            for page_job in page_jobs:
                logger.info(f"  - {os.path.basename(page_job.image_path)}")
            
            # Processa as páginas com sistema de retry e discovery de endpoints
            return self._process_pages_with_retry(page_jobs, options, progress_callback, job_info)
            
        except Exception as e:
            logger.error(f"Erro na conversão/preparação JPG: {e}")
            if temp_folder and os.path.exists(temp_folder):
                logger.info(f"Imagens parciais mantidas em: {temp_folder}")
            return False, {"error": f"Erro na conversão/preparação JPG: {e}"}

    
    def _process_pages_with_retry(self, page_jobs: list, options: PrintOptions, 
                              progress_callback=None, job_info: Optional[PrintJobInfo] = None) -> Tuple[bool, Dict]:
        """Processa páginas com sistema de retry inteligente e discovery de endpoints"""
        
        # Descobre endpoints disponíveis
        discovered_endpoints = self._discover_printer_endpoints()
        
        successful_pages = []
        failed_pages = list(page_jobs)  # Copia inicial
        retry_delays = [2, 5, 10]  # Delays progressivos em segundos
        
        # Primeira passada - tenta todas as páginas
        logger.info(f"Processando {len(page_jobs)} página(s)...")
        if progress_callback:
            progress_callback(f"Processando {len(page_jobs)} página(s)...")
        
        for attempt in range(max(p.max_attempts for p in page_jobs)):
            if not failed_pages:
                break
                
            if job_info and job_info.status == "canceled":
                logger.info(f"Cancelamento detectado para o trabalho {job_info.job_id} antes de processar páginas na tentativa {attempt + 1}.")
                
                for pj in failed_pages:
                    if progress_callback:
                        wx.CallAfter(progress_callback, f"Página {pj.page_num} não enviada (trabalho cancelado).")

                result = {
                    "total_pages": len(page_jobs),
                    "successful_pages": len(successful_pages),
                    "failed_pages": len(page_jobs) - len(successful_pages),
                    "method": "jpg",
                    "status": "canceled",
                    "message": "Trabalho cancelado pelo usuário durante o processamento de páginas."
                }
                return False, result

            current_failed = []
            
            for page_job in failed_pages:
                if job_info and job_info.status == "canceled":
                    logger.info(f"Cancelamento detectado para o trabalho {job_info.job_id} ao tentar enviar a página {page_job.page_num}.")

                    if progress_callback:
                        wx.CallAfter(progress_callback, f"Página {page_job.page_num} não enviada (trabalho cancelado).")
                    continue
                
                page_job.attempts += 1
                
                logger.info(f"Enviando página {page_job.page_num}/{len(page_jobs)} como JPG (tentativa {page_job.attempts}/{page_job.max_attempts})")
                logger.info(f"Tamanho JPG página {page_job.page_num}: {len(page_job.jpg_data):,} bytes")
                
                if progress_callback:
                    progress_callback(f"Enviando página {page_job.page_num}/{len(page_jobs)} (tentativa {page_job.attempts})")
                
                # Tenta enviar esta página
                page_success = False
                
                for endpoint_info in discovered_endpoints:
                    endpoint = endpoint_info["endpoint"]
                    url = endpoint_info["url"]
                    
                    # Atributos IPP para JPG
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
                    if endpoint == discovered_endpoints[0]["endpoint"] and not page_success:
                        logger.info("Aguardando 1s antes do próximo endpoint...")
                        time.sleep(1)
                
                if page_success:
                    logger.info(f"Página {page_job.page_num} enviada com sucesso")
                    successful_pages.append(page_job)
                    if progress_callback:
                        progress_callback(f"✓ Página {page_job.page_num} impressa com sucesso")
                else:
                    logger.info(f"Falha ao enviar página {page_job.page_num}")
                    
                    if page_job.attempts < page_job.max_attempts:
                        current_failed.append(page_job)
                        # Aguarda antes da próxima tentativa
                        delay = retry_delays[min(page_job.attempts - 1, len(retry_delays) - 1)]
                        logger.info(f"Aguardando {delay}s antes da próxima tentativa...")
                        if progress_callback:
                            progress_callback(f"Aguardando {delay}s antes de tentar página {page_job.page_num} novamente...")
                        time.sleep(delay)
                    else:
                        logger.error(f"Página {page_job.page_num} falhou após {page_job.max_attempts} tentativas")
                        if progress_callback:
                            progress_callback(f"✗ Página {page_job.page_num} falhou após {page_job.max_attempts} tentativas")
            
            failed_pages = current_failed
            
            # Se ainda há páginas falhando e não é a última tentativa, aguarda mais um pouco
            if failed_pages and attempt < max(p.max_attempts for p in page_jobs) - 1:
                logger.info("Aguardando 3s antes da próxima rodada de tentativas...")
                time.sleep(3)
        
        # Relatório final
        total_pages = len(page_jobs)
        successful_count = len(successful_pages)
        failed_count = total_pages - successful_count
        
        logger.info("Relatório de impressão:")
        logger.info(f"Páginas enviadas com sucesso: {successful_count}/{total_pages}")
        logger.info(f"Páginas que falharam: {failed_count}/{total_pages}")
        
        if successful_pages:
            logger.info(f"Páginas bem-sucedidas: {', '.join(str(p.page_num) for p in successful_pages)}")
        
        remaining_failed = [p for p in page_jobs if p not in successful_pages]
        if remaining_failed:
            logger.info(f"Páginas que falharam: {', '.join(str(p.page_num) for p in remaining_failed)}")
            logger.info(f"Imagens mantidas em: {os.path.dirname(remaining_failed[0].image_path)}")
            logger.info("Você pode tentar reimprimir manualmente as páginas que falharam")
        else:
            logger.info("Todas as páginas foram processadas com sucesso!")
            temp_folder = os.path.dirname(page_jobs[0].image_path)
            logger.info(f"Imagens temporárias mantidas em: {temp_folder}")
            logger.info("Você pode remover a pasta manualmente após validar as impressões")
        
        # Cria um dicionário para retornar o resultado
        result = {
            "total_pages": total_pages,
            "successful_pages": successful_count,
            "failed_pages": failed_count,
            "method": "jpg"
        }
        
        # Retorna True apenas se TODAS as páginas foram impressas com sucesso
        return successful_count == total_pages, result


    def _build_ipp_request(self, operation: int, attributes: Dict[str, Any]) -> bytes:
        """Constrói uma requisição IPP completa com correção de URI"""
        
        # Corrige o formato do URI da impressora
        if "printer-uri" in attributes:
            printer_uri = attributes["printer-uri"]
            
            # Assegura que a URI tenha o formato correto
            if not printer_uri.startswith("ipp://") and not printer_uri.startswith("ipps://"):
                # Se for uma URL HTTP ou HTTPS, converte para IPP ou IPPS
                if printer_uri.startswith("http://"):
                    attributes["printer-uri"] = printer_uri.replace("http://", "ipp://", 1)
                elif printer_uri.startswith("https://"):
                    attributes["printer-uri"] = printer_uri.replace("https://", "ipps://", 1)
                else:
                    # Se não tem protocolo, adiciona o protocolo IPP apropriado
                    protocol = "ipps" if self.use_https else "ipp"
                    if printer_uri.startswith("/"):
                        attributes["printer-uri"] = f"{protocol}://{self.printer_ip}:{self.port}{printer_uri}"
                    else:
                        attributes["printer-uri"] = f"{protocol}://{self.printer_ip}:{self.port}/{printer_uri}"
        
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
        """Envia requisição IPP com correção de URI e retry inteligente"""
        
        # Corrige a URL para o protocolo correto
        if self.use_https and url.startswith("http:"):
            url = url.replace("http:", "https:", 1)
        
        # Armazena a URL original para diagnóstico
        original_url = url
        
        # Constrói requisição IPP
        ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
        ipp_request += document_data
        
        try:
            headers = {
                'Content-Type': 'application/ipp',
                'Accept': 'application/ipp',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
                'User-Agent': 'PDF-IPP/1.1'
            }
            
            # Usa sessão configurada com retry
            response = self.session.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=30, 
                verify=False,
                allow_redirects=False
            )
            
            logger.info(f"HTTP Status: {response.status_code}")
            
            # Verifica se HTTP foi 200
            if response.status_code != 200:
                logger.error(f"HTTP não é 200: {response.status_code}")
                
                # Se recebeu 426, tenta automaticamente com HTTPS
                if response.status_code == 426 and not self.use_https:
                    logger.info("Recebeu HTTP 426, mudando para HTTPS e tentando novamente")
                    self.use_https = True
                    self.protocol = "https"
                    self.base_url = f"https://{self.printer_ip}:{self.port}"
                    https_url = url.replace("http:", "https:", 1)
                    
                    # Atualiza o URI da impressora no atributo
                    if "printer-uri" in attributes:
                        attributes["printer-uri"] = https_url
                    
                    # Constrói nova requisição com URI atualizado
                    ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
                    ipp_request += document_data
                    
                    # Tenta novamente com HTTPS
                    try:
                        https_response = self.session.post(
                            https_url, 
                            data=ipp_request, 
                            headers=headers, 
                            timeout=30, 
                            verify=False,
                            allow_redirects=False
                        )
                        
                        logger.info(f"HTTPS Status: {https_response.status_code}")
                        
                        if https_response.status_code == 200:
                            # Sucesso com HTTPS
                            return self._verify_ipp_response(https_response)
                    except Exception as e:
                        logger.error(f"Erro na segunda tentativa com HTTPS: {e}")
                
                return False
            
            # Verifica resposta IPP
            return self._verify_ipp_response(response)
                
        except requests.exceptions.Timeout:
            logger.error("Timeout")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Conexão recusada: {e}")
            
            # Se for Connection Reset e estamos usando HTTP, tenta HTTPS
            if ("10054" in str(e) or "Connection aborted" in str(e)) and not self.use_https:
                logger.info("Conexão abortada (10054), mudando para HTTPS e tentando novamente")
                self.use_https = True
                self.protocol = "https"
                self.base_url = f"https://{self.printer_ip}:{self.port}"
                https_url = url.replace("http:", "https:", 1)
                
                # Atualiza o URI da impressora no atributo
                if "printer-uri" in attributes:
                    attributes["printer-uri"] = https_url
                
                # Constrói nova requisição com URI atualizado
                ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
                ipp_request += document_data
                
                # Tenta novamente com HTTPS
                try:
                    https_response = self.session.post(
                        https_url, 
                        data=ipp_request, 
                        headers=headers, 
                        timeout=30, 
                        verify=False,
                        allow_redirects=False
                    )
                    
                    logger.info(f"HTTPS Status: {https_response.status_code}")
                    
                    if https_response.status_code == 200:
                        # Sucesso com HTTPS
                        return self._verify_ipp_response(https_response)
                except Exception as e2:
                    logger.error(f"Erro na segunda tentativa com HTTPS: {e2}")
        except Exception as e:
            logger.error(f"Erro: {e}")
        
        return False

    
    def _verify_ipp_response(self, response):
        """Verifica se a resposta IPP é válida e trata códigos de status adequadamente"""
        # Verifica status IPP na resposta
        if len(response.content) >= 8:
            version = struct.unpack('>H', response.content[0:2])[0]
            status_code = struct.unpack('>H', response.content[2:4])[0]
            request_id = struct.unpack('>I', response.content[4:8])[0]
            
            # Obtém nome do status se disponível
            status_name = IPP_STATUS_CODES.get(status_code, "unknown")
            
            logger.info(f"IPP Version: {version >> 8}.{version & 0xFF}")
            logger.info(f"IPP Status: 0x{status_code:04X} ({status_name})")
            
            # Status de sucesso
            if status_code in [0x0000, 0x0001, 0x0002]:
                logger.info(f"Status IPP de sucesso: 0x{status_code:04X} ({status_name})")
                
                job_id = self._extract_job_id_from_response(response.content)
                if job_id:
                    logger.info(f"Job ID: {job_id}")
                
                return True
                
            # Analisa erros específicos
            elif status_code == 0x0400:  # bad-request
                logger.error(f"Erro IPP 0x0400: client-error-bad-request (requisição inválida)")
                return False
            elif status_code == 0x0401:  # forbidden
                logger.error(f"Erro IPP 0x0401: client-error-forbidden (acesso negado)")
                return False
            elif status_code == 0x0403 or status_code == 0x0402:  # not-authorized/not-authenticated
                logger.error(f"Erro IPP 0x{status_code:04X}: {status_name} (autenticação necessária)")
                return False
            elif status_code == 0x0406 or status_code == 0x0408:  # not-found/request-entity-too-large
                logger.error(f"Erro IPP 0x{status_code:04X}: {status_name} (endpoint incorreto ou dados muito grandes)")
                # Estes erros indicam que precisamos tentar outro endpoint
                return False
            elif status_code == 0x040A:  # document-format-not-supported
                logger.error(f"Erro IPP 0x040A: client-error-document-format-not-supported (formato não suportado)")
                return False
            elif status_code == 0x0507:  # document-format-error
                logger.error(f"Erro IPP 0x0507: client-error-document-format-error (formato não suportado)")
                return False
            elif status_code >= 0x0500:  # server-error-*
                logger.error(f"Erro IPP no servidor: 0x{status_code:04X} ({status_name})")
                return False
            else:
                logger.error(f"Status IPP não reconhecido: 0x{status_code:04X} ({status_name})")
                return False
        else:
            logger.error("Resposta IPP inválida ou muito curta")
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
            logger.error(f"Erro ao extrair job-id: {e}")
            
        return None

# Mantém as classes de gerenciamento e diálogos inalteradas
class PrintQueueManager:
    """Gerencia a fila de impressão"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Obtém instância única (singleton)"""
        if cls._instance is None:
            cls._instance = PrintQueueManager()
        return cls._instance
    
    def __init__(self):
        """Inicializa o gerenciador de fila"""
        self.print_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.current_job = None
        self.lock = threading.Lock()
        self.config = None
        self.job_history = []
        self.max_history = 100
        self.canceled_job_ids = set()
    
    def cancel_job_id(self, job_id: str):
        """Registra um job_id como cancelado."""
        with self.lock:
            self.canceled_job_ids.add(job_id)
            logger.info(f"Job ID {job_id} marcado para cancelamento.")

            if self.current_job and self.current_job["info"].job_id == job_id:
                self.current_job["info"].status = "canceled"
                
    def set_config(self, config):
        """Define o objeto de configuração"""
        self.config = config
        self._load_job_history()
    
    def _load_job_history(self):
        """Carrega histórico de trabalhos de impressão"""
        if self.config:
            self.job_history = self.config.get("print_jobs", [])
            # Limita o tamanho do histórico
            if len(self.job_history) > self.max_history:
                self.job_history = self.job_history[-self.max_history:]
    
    def _save_job_history(self):
        """Salva histórico de trabalhos de impressão"""
        if self.config:
            self.config.set("print_jobs", self.job_history)
    
    def start(self):
        """Inicia o processamento da fila de impressão"""
        with self.lock:
            if not self.is_running:
                self.is_running = True
                self.worker_thread = threading.Thread(target=self._process_queue)
                self.worker_thread.daemon = True
                self.worker_thread.start()
                logger.info("Gerenciador de fila de impressão iniciado")
    
    def stop(self):
        """Para o processamento da fila de impressão"""
        with self.lock:
            self.is_running = False
            if self.worker_thread:
                self.worker_thread.join(timeout=1.0)
                self.worker_thread = None
                logger.info("Gerenciador de fila de impressão parado")
    
    def add_job(self, print_job_info, printer_instance, callback=None):
        """Adiciona um trabalho à fila de impressão"""
        self.start()  # Garante que o worker está rodando
        
        job_item = {
            "info": print_job_info,
            "printer": printer_instance,
            "callback": callback
        }
        
        # Adiciona à fila
        self.print_queue.put(job_item)
        logger.info(f"Trabalho adicionado à fila: {print_job_info.document_name}")
        
        # Retorna um ID para rastreamento
        return print_job_info.job_id
    
    def get_queue_size(self):
        """Retorna o tamanho atual da fila"""
        return self.print_queue.qsize()
    
    def get_current_job(self):
        """Retorna o trabalho atual em processamento"""
        with self.lock:
            return self.current_job
    
    def _process_queue(self):
        """Processa a fila de impressão"""
        while self.is_running:
            try:
                # Obtém o próximo trabalho da fila
                if self.print_queue.empty():
                    time.sleep(1.0)
                    continue
                    
                job_item = self.print_queue.get(block=False)
                
                job_info = job_item["info"]
                printer = job_item["printer"]
                callback = job_item["callback"]
                
                with self.lock:
                    is_canceled = job_info.job_id in self.canceled_job_ids

                if is_canceled:
                    logger.info(f"Trabalho {job_info.document_name} (ID: {job_info.job_id}) foi cancelado antes do processamento.")
                    job_info.status = "canceled" 
                    job_info.end_time = datetime.now()
                    self._update_history(job_info)

                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "canceled", {"message": "Trabalho cancelado pelo usuário"})

                    self.print_queue.task_done()
                    with self.lock: 
                        if self.current_job and self.current_job["info"].job_id == job_info.job_id:
                            self.current_job = None
                    continue 
                
                with self.lock:
                    self.current_job = job_item
                
                logger.info(f"Processando trabalho: {job_info.document_name}")
                
                # Salva o trabalho no histórico antes de começar
                job_info.status = "processing"
                self._add_to_history(job_info)
                
                # Definir função de progresso
                def progress_callback(message):
                    with self.lock:
                        if self.current_job and self.current_job["info"].job_id == job_info.job_id and \
                        self.current_job["info"].status == "canceled":
                            raise InterruptedError("Trabalho cancelado durante o processamento")
                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "progress", message) 
                
                # Tenta imprimir
                try:
                    progress_callback("Iniciando impressão...")
                    
                    success, result = printer.print_file(
                        job_info.document_path,
                        job_info.options,
                        job_info.document_name,
                        progress_callback,
                        job_info=job_info
                    )
                    
                    # Atualiza informações do trabalho
                    job_info.end_time = datetime.now()
                    
                    if success:
                        job_info.status = "completed"
                        job_info.total_pages = result.get("total_pages", 0)
                        job_info.completed_pages = result.get("successful_pages", 0)
                        logger.info(f"Trabalho concluído com sucesso: {job_info.document_name}")
                        
                        # Tenta excluir o arquivo após impressão bem-sucedida
                        try:
                            if os.path.exists(job_info.document_path):
                                os.remove(job_info.document_path)
                                logger.info(f"Arquivo removido: {job_info.document_path}")
                        except Exception as e:
                            logger.error(f"Erro ao remover arquivo: {e}")
                        
                        # Inicia sincronização com o servidor
                        try:
                            from src.utils.print_sync_manager import PrintSyncManager
                            sync_manager = PrintSyncManager.get_instance()
                            if sync_manager:
                                sync_manager.sync_print_jobs()
                        except Exception as e:
                            logger.error(f"Erro ao iniciar sincronização: {e}")
                            
                    else:
                        with self.lock: # Re-check status
                            if job_info.status == "canceled":
                                logger.info(f"Trabalho {job_info.document_name} cancelado durante a impressão.")
                            else:
                                job_info.status = "failed"
                                logger.error(f"Falha no trabalho: {job_info.document_name}")

                        job_info.total_pages = result.get("total_pages", 0)
                        job_info.completed_pages = result.get("successful_pages", 0)
                    
                    # Atualiza histórico
                    self._update_history(job_info)
                    
                    # Notifica o callback
                    if callback:
                        status_cb = "complete" if success else ("canceled" if job_info.status == "canceled" else "error")
                        wx.CallAfter(callback, job_info.job_id, status_cb, result)
                    
                except InterruptedError: # Captura o erro de cancelamento
                    logger.info(f"Processamento do trabalho {job_info.document_name} interrompido devido ao cancelamento.")
                    job_info.status = "canceled"
                    job_info.end_time = datetime.now()
                    self._update_history(job_info)
                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "canceled", {"message": "Trabalho cancelado pelo usuário"})

                except Exception as e:
                    job_info.status = "failed"
                    job_info.end_time = datetime.now()
                    logger.error(f"Erro ao processar trabalho: {e}")
                    
                    # Atualiza histórico
                    self._update_history(job_info)
                    
                    # Notifica o callback
                    if callback:
                        callback(job_info.job_id, "error", {"error": str(e)})
                
                # Marca o trabalho como concluído na fila
                self.print_queue.task_done()
                
                with self.lock:
                    self.current_job = None
                
            except queue.Empty:
                time.sleep(1.0)
            except Exception as e:
                logger.error(f"Erro no processamento da fila: {e}")
                time.sleep(5.0)  # Aguarda antes de tentar novamente
    
    def _add_to_history(self, job_info):
        """Adiciona um trabalho ao histórico"""
        with self.lock:
            # Verifica se já existe no histórico
            for i, job in enumerate(self.job_history):
                if job.get("job_id") == job_info.job_id:
                    # Atualiza o existente
                    self.job_history[i] = job_info.to_dict()
                    self._save_job_history()
                    return
            
            # Adiciona novo
            self.job_history.append(job_info.to_dict())
            
            # Limita o tamanho do histórico
            if len(self.job_history) > self.max_history:
                self.job_history = self.job_history[-self.max_history:]
                
            self._save_job_history()
    
    def _update_history(self, job_info):
        """Atualiza um trabalho no histórico"""
        self._add_to_history(job_info)
    
    def get_job_history(self):
        """Retorna o histórico de trabalhos"""
        with self.lock:
            return list(self.job_history)

class PrintOptionsDialog(wx.Dialog):
    """Diálogo para configurar opções de impressão"""
    
    def __init__(self, parent, document, printer):
        """
        Inicializa o diálogo de opções de impressão
        
        Args:
            parent: Janela pai
            document: Documento a ser impresso
            printer: Impressora selecionada
        """
        super().__init__(
            parent,
            title=f"Opções de Impressão",
            size=(500, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.document = document
        self.printer = printer
        self.options = PrintOptions()
        
        # Cores para temas
        self.colors = {
            "bg_color": wx.Colour(18, 18, 18), 
            "panel_bg": wx.Colour(25, 25, 25),
            "card_bg": wx.Colour(35, 35, 35),
            "accent_color": wx.Colour(255, 90, 36),
            "text_color": wx.WHITE,
            "text_secondary": wx.Colour(180, 180, 180),
            "border_color": wx.Colour(45, 45, 45)
        }
        
        # Aplica o tema ao diálogo
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self._init_ui()
        
        # Centraliza o diálogo
        self.CenterOnParent()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Configura o painel principal
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(self.colors["bg_color"])
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cabeçalho com informações do documento
        header_panel = self._create_header_panel()
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Card de opções
        options_card = self._create_options_card()
        main_sizer.Add(options_card, 1, wx.EXPAND | wx.ALL, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para cancelar
        cancel_button = wx.Button(self.panel, wx.ID_CANCEL, label="Cancelar", size=(-1, 36))
        cancel_button.SetBackgroundColour(wx.Colour(60, 60, 60))
        cancel_button.SetForegroundColour(self.colors["text_color"])
        
        # Eventos de hover para o botão
        def on_cancel_enter(evt):
            cancel_button.SetBackgroundColour(wx.Colour(80, 80, 80))
            cancel_button.Refresh()
        
        def on_cancel_leave(evt):
            cancel_button.SetBackgroundColour(wx.Colour(60, 60, 60))
            cancel_button.Refresh()
        
        cancel_button.Bind(wx.EVT_ENTER_WINDOW, on_cancel_enter)
        cancel_button.Bind(wx.EVT_LEAVE_WINDOW, on_cancel_leave)
        
        # Botão para imprimir
        print_button = wx.Button(self.panel, wx.ID_OK, label="Imprimir", size=(-1, 36))
        print_button.SetBackgroundColour(self.colors["accent_color"])
        print_button.SetForegroundColour(self.colors["text_color"])
        
        # Eventos de hover para o botão
        def on_print_enter(evt):
            print_button.SetBackgroundColour(wx.Colour(255, 120, 70))
            print_button.Refresh()
        
        def on_print_leave(evt):
            print_button.SetBackgroundColour(self.colors["accent_color"])
            print_button.Refresh()
        
        print_button.Bind(wx.EVT_ENTER_WINDOW, on_print_enter)
        print_button.Bind(wx.EVT_LEAVE_WINDOW, on_print_leave)
        
        button_sizer.Add(cancel_button, 0, wx.RIGHT, 10)
        button_sizer.Add(print_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
        
        # Bind do evento de OK
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
    
    def _create_header_panel(self):
        """Cria o painel de cabeçalho com informações do documento e impressora"""
        header_panel = wx.Panel(self.panel)
        header_panel.SetBackgroundColour(self.colors["card_bg"])
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(header_panel, label="Configurações de Impressão")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(header_panel)
        header_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Informações do documento e impressora
        info_panel = wx.Panel(header_panel)
        info_panel.SetBackgroundColour(self.colors["card_bg"])
        info_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=5, hgap=10)
        info_sizer.AddGrowableCol(1, 1)
        
        # Documento
        doc_label = wx.StaticText(info_panel, label="Documento:")
        doc_label.SetForegroundColour(self.colors["text_secondary"])
        doc_value = wx.StaticText(info_panel, label=self.document.name)
        doc_value.SetForegroundColour(self.colors["text_color"])
        
        # Impressora
        printer_label = wx.StaticText(info_panel, label="Impressora:")
        printer_label.SetForegroundColour(self.colors["text_secondary"])
        printer_value = wx.StaticText(info_panel, label=self.printer.name)
        printer_value.SetForegroundColour(self.colors["text_color"])
        
        # Tamanho do arquivo
        size_label = wx.StaticText(info_panel, label="Tamanho:")
        size_label.SetForegroundColour(self.colors["text_secondary"])
        size_value = wx.StaticText(info_panel, label=self.document.formatted_size)
        size_value.SetForegroundColour(self.colors["text_color"])
        
        # Adiciona os itens ao sizer
        info_sizer.Add(doc_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(doc_value, 0, wx.EXPAND)
        info_sizer.Add(printer_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(printer_value, 0, wx.EXPAND)
        info_sizer.Add(size_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(size_value, 0, wx.EXPAND)
        
        info_panel.SetSizer(info_sizer)
        header_sizer.Add(info_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        header_panel.SetSizer(header_sizer)
        
        # Adiciona borda arredondada ao card
        def on_header_paint(event):
            dc = wx.BufferedPaintDC(header_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = header_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in header_panel.GetChildren():
                child.Refresh()
        
        header_panel.Bind(wx.EVT_PAINT, on_header_paint)
        header_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        return header_panel
    
    def _create_options_card(self):
        """Cria o card com opções de impressão"""
        options_panel = wx.Panel(self.panel)
        options_panel.SetBackgroundColour(self.colors["card_bg"])
        options_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(options_panel, label="Opções de Impressão")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        options_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(options_panel)
        options_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Grid de opções
        grid_panel = wx.Panel(options_panel)
        grid_panel.SetBackgroundColour(self.colors["card_bg"])
        grid_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=15, hgap=10)
        grid_sizer.AddGrowableCol(1, 1)
        
        # Modo de cor
        color_label = wx.StaticText(grid_panel, label="Modo de cor:")
        color_label.SetForegroundColour(self.colors["text_color"])
        
        color_choices = ["Automático", "Colorido", "Preto e branco"]
        self.color_choice = wx.Choice(grid_panel, choices=color_choices)
        self.color_choice.SetSelection(0)  # Automático
        
        grid_sizer.Add(color_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.color_choice, 0, wx.EXPAND)
        
        # Duplex
        duplex_label = wx.StaticText(grid_panel, label="Impressão frente e verso:")
        duplex_label.SetForegroundColour(self.colors["text_color"])
        
        duplex_choices = ["Somente frente", "Frente e verso (borda longa)", "Frente e verso (borda curta)"]
        self.duplex_choice = wx.Choice(grid_panel, choices=duplex_choices)
        self.duplex_choice.SetSelection(0)  # Somente frente
        
        grid_sizer.Add(duplex_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.duplex_choice, 0, wx.EXPAND)
        
        # Qualidade
        quality_label = wx.StaticText(grid_panel, label="Qualidade:")
        quality_label.SetForegroundColour(self.colors["text_color"])
        
        quality_choices = ["Rascunho", "Normal", "Alta"]
        self.quality_choice = wx.Choice(grid_panel, choices=quality_choices)
        self.quality_choice.SetSelection(1)  # Normal
        
        grid_sizer.Add(quality_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.quality_choice, 0, wx.EXPAND)
        
        # Orientação
        orientation_label = wx.StaticText(grid_panel, label="Orientação:")
        orientation_label.SetForegroundColour(self.colors["text_color"])
        
        orientation_choices = ["Retrato", "Paisagem"]
        self.orientation_choice = wx.Choice(grid_panel, choices=orientation_choices)
        self.orientation_choice.SetSelection(0)  # Retrato
        
        grid_sizer.Add(orientation_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.orientation_choice, 0, wx.EXPAND)
        
        # Cópias
        copies_label = wx.StaticText(grid_panel, label="Número de cópias:")
        copies_label.SetForegroundColour(self.colors["text_color"])
        
        self.copies_spin = wx.SpinCtrl(grid_panel, min=1, max=99, initial=1)
        
        grid_sizer.Add(copies_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        grid_sizer.Add(self.copies_spin, 0, wx.EXPAND)
        
        grid_panel.SetSizer(grid_sizer)
        options_sizer.Add(grid_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        options_panel.SetSizer(options_sizer)
        
        # Adiciona borda arredondada ao card
        def on_options_paint(event):
            dc = wx.BufferedPaintDC(options_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = options_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in options_panel.GetChildren():
                child.Refresh()
        
        options_panel.Bind(wx.EVT_PAINT, on_options_paint)
        options_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        return options_panel
    
    def on_ok(self, event):
        """Manipula o evento de OK (imprimir)"""
        # Configura as opções com os valores selecionados
        
        # Modo de cor
        color_idx = self.color_choice.GetSelection()
        if color_idx == 1:  # Colorido
            self.options.color_mode = ColorMode.COLORIDO
        elif color_idx == 2:  # Preto e branco
            self.options.color_mode = ColorMode.MONOCROMO
        else:  # Automático
            self.options.color_mode = ColorMode.AUTO
        
        # Duplex
        duplex_idx = self.duplex_choice.GetSelection()
        if duplex_idx == 1:  # Borda longa
            self.options.duplex = Duplex.DUPLEX_LONGO
        elif duplex_idx == 2:  # Borda curta
            self.options.duplex = Duplex.DUPLEX_CURTO
        else:  # Simples
            self.options.duplex = Duplex.SIMPLES
        
        # Qualidade
        quality_idx = self.quality_choice.GetSelection()
        if quality_idx == 0:  # Rascunho
            self.options.quality = Quality.RASCUNHO
        elif quality_idx == 2:  # Alta
            self.options.quality = Quality.ALTA
        else:  # Normal
            self.options.quality = Quality.NORMAL
        
        # Orientação
        orientation_idx = self.orientation_choice.GetSelection()
        self.options.orientation = "landscape" if orientation_idx == 1 else "portrait"
        
        # Cópias
        self.options.copies = self.copies_spin.GetValue()
        
        event.Skip()  # Continua o processamento do evento
    
    def get_options(self):
        """Retorna as opções de impressão configuradas"""
        return self.options

class PrintProgressDialog(wx.Dialog):
    """Diálogo de progresso de impressão"""
    
    def __init__(self, parent, job_id, document_name, printer_name):
        """
        Inicializa o diálogo de progresso
        
        Args:
            parent: Janela pai
            job_id: ID do trabalho de impressão
            document_name: Nome do documento
            printer_name: Nome da impressora
        """
        super().__init__(
            parent,
            title="Progresso da Impressão",
            size=(450, 300),
            style=wx.DEFAULT_DIALOG_STYLE
        )
        
        self.job_id = job_id
        self.document_name = document_name
        self.printer_name = printer_name
        self._is_destroyed = False  # Flag para controlar se o diálogo foi destruído
        
        # Cores para temas
        self.colors = {
            "bg_color": wx.Colour(18, 18, 18), 
            "panel_bg": wx.Colour(25, 25, 25),
            "card_bg": wx.Colour(35, 35, 35),
            "accent_color": wx.Colour(255, 90, 36),
            "text_color": wx.WHITE,
            "text_secondary": wx.Colour(180, 180, 180),
            "border_color": wx.Colour(45, 45, 45),
            "success_color": wx.Colour(40, 167, 69),
            "error_color": wx.Colour(220, 53, 69)
        }
        
        # Aplica o tema ao diálogo
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self._init_ui()
        
        # Bind eventos de fechamento
        self.Bind(wx.EVT_CLOSE, self.on_close_event)
        
        # Centraliza o diálogo
        self.CenterOnParent()
    
    def _is_control_valid(self, control):
        """Verifica se um controle ainda é válido e pode ser acessado"""
        try:
            if self._is_destroyed:
                return False
            return control and hasattr(control, 'GetParent') and control.GetParent() is not None
        except:
            return False

    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Configura o painel principal
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(self.colors["bg_color"])
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Card de informações
        info_panel = wx.Panel(self.panel)
        info_panel.SetBackgroundColour(self.colors["card_bg"])
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(info_panel, label="Imprimindo documento")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(info_panel)
        info_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Informações do trabalho
        job_info_panel = wx.Panel(info_panel)
        job_info_panel.SetBackgroundColour(self.colors["card_bg"])
        job_info_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=5, hgap=10)
        job_info_sizer.AddGrowableCol(1, 1)
        
        # Documento
        doc_label = wx.StaticText(job_info_panel, label="Documento:")
        doc_label.SetForegroundColour(self.colors["text_secondary"])
        doc_value = wx.StaticText(job_info_panel, label=self.document_name)
        doc_value.SetForegroundColour(self.colors["text_color"])
        
        # Impressora
        printer_label = wx.StaticText(job_info_panel, label="Impressora:")
        printer_label.SetForegroundColour(self.colors["text_secondary"])
        printer_value = wx.StaticText(job_info_panel, label=self.printer_name)
        printer_value.SetForegroundColour(self.colors["text_color"])
        
        # ID do trabalho
        job_id_label = wx.StaticText(job_info_panel, label="ID do trabalho:")
        job_id_label.SetForegroundColour(self.colors["text_secondary"])
        job_id_value = wx.StaticText(job_info_panel, label=self.job_id)
        job_id_value.SetForegroundColour(self.colors["text_color"])
        
        # Adiciona os itens ao sizer
        job_info_sizer.Add(doc_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        job_info_sizer.Add(doc_value, 0, wx.EXPAND)
        job_info_sizer.Add(printer_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        job_info_sizer.Add(printer_value, 0, wx.EXPAND)
        job_info_sizer.Add(job_id_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        job_info_sizer.Add(job_id_value, 0, wx.EXPAND)
        
        job_info_panel.SetSizer(job_info_sizer)
        info_sizer.Add(job_info_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Separador
        separator2 = wx.StaticLine(info_panel)
        info_sizer.Add(separator2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Status
        status_panel = wx.Panel(info_panel)
        status_panel.SetBackgroundColour(self.colors["card_bg"])
        status_sizer = wx.BoxSizer(wx.VERTICAL)
        
        status_label = wx.StaticText(status_panel, label="Status:")
        status_label.SetForegroundColour(self.colors["text_secondary"])
        status_sizer.Add(status_label, 0, wx.BOTTOM, 5)
        
        self.status_text = wx.StaticText(status_panel, label="Iniciando impressão...")
        self.status_text.SetForegroundColour(self.colors["text_color"])
        status_sizer.Add(self.status_text, 0, wx.BOTTOM, 10)
        
        # Indicador de progresso
        self.gauge = wx.Gauge(status_panel, range=100, size=(-1, 20))
        self.gauge.SetValue(0)
        status_sizer.Add(self.gauge, 0, wx.EXPAND | wx.BOTTOM, 10)
        
        # Log de mensagens
        log_label = wx.StaticText(status_panel, label="Log:")
        log_label.SetForegroundColour(self.colors["text_secondary"])
        status_sizer.Add(log_label, 0, wx.BOTTOM, 5)
        
        self.log_ctrl = wx.TextCtrl(status_panel, style=wx.TE_MULTILINE | wx.TE_READONLY)
        self.log_ctrl.SetBackgroundColour(wx.Colour(25, 25, 25))
        self.log_ctrl.SetForegroundColour(self.colors["text_color"])
        status_sizer.Add(self.log_ctrl, 1, wx.EXPAND)
        
        status_panel.SetSizer(status_sizer)
        info_sizer.Add(status_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        info_panel.SetSizer(info_sizer)
        
        # Adiciona borda arredondada ao card
        def on_info_paint(event):
            dc = wx.BufferedPaintDC(info_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = info_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in info_panel.GetChildren():
                child.Refresh()
        
        info_panel.Bind(wx.EVT_PAINT, on_info_paint)
        info_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        main_sizer.Add(info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para fechar
        self.close_button = wx.Button(self.panel, wx.ID_CLOSE, label="Fechar", size=(-1, 36))
        self.close_button.SetBackgroundColour(wx.Colour(60, 60, 60))
        self.close_button.SetForegroundColour(self.colors["text_color"])
        self.close_button.Disable()  # Desabilitado até o trabalho concluir
        
        # Eventos de hover para o botão
        def on_close_enter(evt):
            if self.close_button.IsEnabled():
                self.close_button.SetBackgroundColour(wx.Colour(80, 80, 80))
                self.close_button.Refresh()
        
        def on_close_leave(evt):
            if self.close_button.IsEnabled():
                self.close_button.SetBackgroundColour(wx.Colour(60, 60, 60))
                self.close_button.Refresh()
        
        self.close_button.Bind(wx.EVT_ENTER_WINDOW, on_close_enter)
        self.close_button.Bind(wx.EVT_LEAVE_WINDOW, on_close_leave)
        self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
        
        button_sizer.Add(self.close_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
    
    def add_log(self, message):
        """Adiciona uma mensagem ao log com verificação de segurança"""
        if self._is_destroyed:
            return
            
        try:
            # Verifica se os controles ainda existem antes de acessá-los
            if not self._is_control_valid(self.log_ctrl) or not self._is_control_valid(self.status_text):
                return
                
            # Adiciona timestamp
            timestamp = datetime.now().strftime("%H:%M:%S")
            log_message = f"[{timestamp}] {message}\n"
            
            # Adiciona ao controle de log
            self.log_ctrl.AppendText(log_message)
            
            # Atualiza o status
            self.status_text.SetLabel(message)
            
            # Incrementa a barra de progresso
            if self._is_control_valid(self.gauge):
                current = self.gauge.GetValue()
                if current < 95:  # Deixa um espaço para o final
                    self.gauge.SetValue(current + 5)
                    
        except RuntimeError as e:
            # Controle foi destruído, marca como destruído
            if "wrapped C/C++ object" in str(e) and "has been deleted" in str(e):
                self._is_destroyed = True
            logger.warning(f"Controle do diálogo foi destruído: {e}")
        except Exception as e:
            logger.error(f"Erro ao adicionar log: {e}")
    
    def set_success(self, message="Impressão concluída com sucesso"):
        """Define o status como sucesso com verificação de segurança"""
        if self._is_destroyed:
            return
            
        try:
            if self._is_control_valid(self.status_text):
                self.status_text.SetLabel(message)
                self.status_text.SetForegroundColour(self.colors["success_color"])
                
            if self._is_control_valid(self.gauge):
                self.gauge.SetValue(100)
                
            if self._is_control_valid(self.close_button):
                self.close_button.Enable()
                self.close_button.SetFocus()
            
            # Adiciona ao log
            self.add_log(message)
            
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e) and "has been deleted" in str(e):
                self._is_destroyed = True
            logger.warning(f"Controle do diálogo foi destruído: {e}")
        except Exception as e:
            logger.error(f"Erro ao definir sucesso: {e}")
    
    def set_error(self, message="Falha na impressão"):
        """Define o status como erro com verificação de segurança"""
        if self._is_destroyed:
            return
            
        try:
            if self._is_control_valid(self.status_text):
                self.status_text.SetLabel(message)
                self.status_text.SetForegroundColour(self.colors["error_color"])
                
            if self._is_control_valid(self.gauge):
                self.gauge.SetValue(100)
                
            if self._is_control_valid(self.close_button):
                self.close_button.Enable()
                self.close_button.SetFocus()
            
            # Adiciona ao log
            self.add_log(f"ERRO: {message}")
            
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e) and "has been deleted" in str(e):
                self._is_destroyed = True
            logger.warning(f"Controle do diálogo foi destruído: {e}")
        except Exception as e:
            logger.error(f"Erro ao definir erro: {e}")
    
    def on_close_event(self, event):
        """Manipula o evento de fechamento do diálogo"""
        self._is_destroyed = True
        event.Skip()
    
    def on_close(self, event):
        """Manipula o evento de fechar"""
        self._is_destroyed = True
        self.EndModal(wx.ID_CLOSE)

    def Destroy(self):
        """Override do método Destroy para marcar como destruído"""
        self._is_destroyed = True
        super().Destroy()

class PrintSystem:
    """Sistema integrado de impressão"""
    
    def __init__(self, config):
        """
        Inicializa o sistema de impressão
        
        Args:
            config: Objeto de configuração
        """
        self.config = config
        self.print_queue_manager = PrintQueueManager.get_instance()
        self.print_queue_manager.set_config(config)
        
        # Inicializa o gerenciador de fila
        self.print_queue_manager.start()
    
    def print_document(self, parent_window, document, printer=None):
        """
        Imprime um documento
        
        Args:
            parent_window: Janela pai para diálogos
            document: Documento a ser impresso
            printer: Impressora selecionada (opcional)
            
        Returns:
            bool: True se o trabalho foi adicionado à fila com sucesso
        """
        try:
            # Verifica se o documento existe
            if not os.path.exists(document.path):
                wx.MessageBox(f"Arquivo não encontrado: {document.path}", 
                            "Erro", wx.OK | wx.ICON_ERROR)
                return False
            
            # Se não foi fornecida uma impressora, pede para o usuário selecionar
            if printer is None:
                printer = self._select_printer(parent_window)
                if printer is None:
                    return False  # Usuário cancelou
            
            # Exibe diálogo com opções de impressão
            print_options_dialog = PrintOptionsDialog(parent_window, document, printer)
            if print_options_dialog.ShowModal() != wx.ID_OK:
                print_options_dialog.Destroy()
                return False  # Usuário cancelou
            
            # Obtém as opções de impressão
            options = print_options_dialog.get_options()
            print_options_dialog.Destroy()
            
            # Cria um ID único para o trabalho
            job_id = f"job_{int(time.time())}_{document.id}"
            
            # Cria objeto de informações do trabalho
            job_info = PrintJobInfo(
                job_id=job_id,
                document_path=document.path,
                document_name=document.name,
                printer_name=printer.name,
                printer_id=getattr(printer, 'id', printer.name),
                printer_ip=getattr(printer, 'ip', ''),
                options=options,
                start_time=datetime.now(),
                status="pending"
            )
            
            # Cria instância da impressora (detecta automaticamente HTTP/HTTPS)
            printer_ip = getattr(printer, 'ip', '')
            if not printer_ip:
                wx.MessageBox(f"A impressora '{printer.name}' não possui um endereço IP configurado.",
                            "Erro", wx.ID_ERROR)
                return False
            
            printer_instance = IPPPrinter(
                printer_ip=printer_ip,
                port=631,
                use_https=False  # Deixa detectar automaticamente
            )
            
            # Cria e exibe o diálogo de progresso
            progress_dialog = PrintProgressDialog(
                parent_window,
                job_id,
                document.name,
                printer.name
            )
            
            # Define o callback para atualização de progresso
            def print_callback(job_id, status, data):
                """Callback para atualização de progresso de impressão"""
                # Usa wx.CallAfter para garantir thread safety, mas com verificação de validade
                if progress_dialog and not progress_dialog._is_destroyed:
                    wx.CallAfter(self._update_progress_dialog, progress_dialog, status, data)
            
            # Adiciona o trabalho à fila
            self.print_queue_manager.add_job(
                job_info,
                printer_instance,
                print_callback
            )
            
            # Exibe o diálogo de progresso (não bloqueante)
            progress_dialog.ShowModal()
            progress_dialog.Destroy()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao preparar impressão: {e}")
            wx.MessageBox(f"Erro ao preparar impressão: {e}",
                         "Erro", wx.OK | wx.ICON_ERROR)
            return False
    
    def _select_printer(self, parent_window):
        """Exibe diálogo para selecionar impressora"""
        # Obtém a lista de impressoras
        printer_list = self._get_printers()
        
        if not printer_list:
            wx.MessageBox("Nenhuma impressora configurada. Configure impressoras na aba Impressoras.",
                         "Informação", wx.OK | wx.ICON_INFORMATION)
            return None
        
        # Cria a caixa de diálogo para escolher impressora
        choices = [printer.name for printer in printer_list]
        
        dialog = wx.SingleChoiceDialog(
            parent_window,
            "Escolha a impressora para enviar o documento:",
            "Selecionar Impressora",
            choices
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            selected_index = dialog.GetSelection()
            printer = printer_list[selected_index]
            dialog.Destroy()
            return printer
        
        dialog.Destroy()
        return None
    
    def _get_printers(self):
        """Obtém lista de impressoras configuradas"""
        try:
            printers_data = self.config.get_printers()
            
            if printers_data:
                from src.models.printer import Printer
                return [Printer(printer_data) for printer_data in printers_data]
            else:
                return []
        except Exception as e:
            logger.error(f"Erro ao obter lista de impressoras: {e}")
            return []
    
    def _update_progress_dialog(self, dialog, status, data):
        """Atualiza o diálogo de progresso com verificação de segurança"""
        try:
            # Verifica se o diálogo ainda existe e não foi destruído
            if not dialog or dialog._is_destroyed:
                return
                
            # Verifica se o diálogo ainda tem parent válido
            if not hasattr(dialog, 'GetParent') or dialog.GetParent() is None:
                return
                
            if status == "progress":
                # Mensagem de progresso
                dialog.add_log(data)
            elif status == "complete":
                # Trabalho concluído com sucesso
                dialog.set_success("Impressão concluída com sucesso")
            elif status == "canceled":
                message = "Trabalho cancelado pelo usuário."
                if isinstance(data, dict) and "message" in data:
                    message = data["message"]
                dialog.set_error(message) # Reutiliza set_error ou cria um set_canceled
                dialog.add_log(message)
            elif status == "error":
                # Erro no trabalho
                error_message = data.get("error", "Erro desconhecido") if isinstance(data, dict) else str(data)
                dialog.set_error(f"Falha na impressão: {error_message}")
                
        except RuntimeError as e:
            # Controle foi destruído
            if "wrapped C/C++ object" in str(e) and "has been deleted" in str(e):
                logger.warning("Tentativa de atualizar diálogo já destruído")
                if dialog:
                    dialog._is_destroyed = True
            else:
                logger.error(f"Erro ao atualizar diálogo de progresso: {e}")
        except Exception as e:
            logger.error(f"Erro inesperado ao atualizar diálogo de progresso: {e}")
    
    def test_printer_connection(self, printer_ip: str, use_https: bool = False) -> Dict[str, Any]:
        """Testa conexão com uma impressora (baseado no código de teste)"""
        try:
            test_printer = IPPPrinter(printer_ip, use_https=use_https)
            
            # Testa endpoints básicos
            endpoints = ["/ipp/print", "/ipp", "/printers/ipp", "/printers", ""]
            working_endpoints = []
            
            for endpoint in endpoints:
                url = f"{test_printer.base_url}{endpoint}"
                try:
                    response = requests.get(
                        url,
                        timeout=10,
                        verify=False,
                        allow_redirects=False
                    )
                    if response.status_code in [200, 400, 401, 404, 405]:
                        working_endpoints.append(endpoint)
                except requests.exceptions.ConnectionError as e:
                    # Tenta com HTTPS se falhar com HTTP
                    if "10054" in str(e) or "Connection aborted" in str(e):
                        if not test_printer.use_https:
                            test_printer.use_https = True
                            test_printer.protocol = "https"
                            test_printer.base_url = f"https://{test_printer.printer_ip}:{test_printer.port}"
                            https_url = url.replace("http:", "https:", 1)
                            try:
                                response = requests.get(
                                    https_url,
                                    timeout=10,
                                    verify=False,
                                    allow_redirects=False
                                )
                                if response.status_code in [200, 400, 401, 404, 405]:
                                    working_endpoints.append(endpoint)
                            except:
                                pass
                except:
                    pass
            
            protocol = test_printer.protocol.upper()
            
            return {
                "success": len(working_endpoints) > 0,
                "protocol": protocol,
                "working_endpoints": working_endpoints,
                "base_url": test_printer.base_url
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def shutdown(self):
        """Desliga o sistema de impressão"""
        if self.print_queue_manager:
            self.print_queue_manager.stop()

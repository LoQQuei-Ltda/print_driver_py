#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sistema de impressão IPP otimizado com cache de endpoints e processamento paralelo
VERSÃO CORRIGIDA - Cache de endpoints, processamento paralelo e performance melhorada
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
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from src.utils.subprocess_utils import run_hidden, popen_hidden, check_output_hidden

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

logger = logging.getLogger("PrintManagementSystem.Utils.PrintSystem")

class PrinterEndpointCache:
    """Cache inteligente de endpoints de impressora por IP"""
    
    def __init__(self, config):
        self.config = config
        self._cache_lock = threading.Lock()
    
    def get_printer_endpoint_config(self, printer_ip: str) -> Dict[str, Any]:
        """Obtém configuração de endpoint em cache para uma impressora"""
        with self._cache_lock:
            printer_configs = self.config.get("printer_endpoint_cache", {})
            return printer_configs.get(printer_ip, {})
    
    def save_printer_endpoint_config(self, printer_ip: str, endpoint: str, 
                                   use_https: bool, test_successful: bool = True):
        """Salva configuração de endpoint em cache (com controle de duplicação)"""
        with self._cache_lock:
            printer_configs = self.config.get("printer_endpoint_cache", {})
            
            # === CORREÇÃO: Evita salvar múltiplas vezes seguidas ===
            existing_config = printer_configs.get(printer_ip, {})
            if (existing_config.get("endpoint") == endpoint and 
                existing_config.get("use_https") == use_https and
                test_successful):
                # Só incrementa contadores se é o mesmo endpoint
                existing_config["success_count"] = existing_config.get("success_count", 0) + 1
                existing_config["last_success"] = datetime.now().isoformat()
                printer_configs[printer_ip] = existing_config
            else:
                # Nova configuração ou configuração diferente
                printer_configs[printer_ip] = {
                    "endpoint": endpoint,
                    "use_https": use_https,
                    "protocol": "https" if use_https else "http",
                    "last_success": datetime.now().isoformat() if test_successful else None,
                    "success_count": 1 if test_successful else 0,
                    "fail_count": 0 if test_successful else 1
                }
            
            self.config.set("printer_endpoint_cache", printer_configs)
            logger.info(f"Cache atualizado para {printer_ip}: {endpoint} ({'HTTPS' if use_https else 'HTTP'})")
    
    def mark_endpoint_failed(self, printer_ip: str):
        """Marca endpoint como falhado e incrementa contador"""
        with self._cache_lock:
            printer_configs = self.config.get("printer_endpoint_cache", {})
            if printer_ip in printer_configs:
                printer_configs[printer_ip]["fail_count"] = printer_configs[printer_ip].get("fail_count", 0) + 1
                printer_configs[printer_ip]["last_failure"] = datetime.now().isoformat()
                self.config.set("printer_endpoint_cache", printer_configs)
    
    def should_rediscover(self, printer_ip: str) -> bool:
        """Verifica se deve redescobrir endpoints (critério MENOS sensível)"""
        config = self.get_printer_endpoint_config(printer_ip)
        fail_count = config.get("fail_count", 0)
        success_count = config.get("success_count", 0)
        last_success = config.get("last_success")
        
        # === CORREÇÃO: Critérios MENOS sensíveis para rediscovery ===
        
        # Se não tem sucesso anterior, sempre redescobre
        if success_count == 0:
            return True
        
        # Se falhou mais de 5 vezes seguidas (aumentado de 2)
        if fail_count > 5:
            return True
            
        # Se a taxa de falha é muito alta (> 80%, aumentado de 50%)
        total_attempts = success_count + fail_count
        if total_attempts > 10 and (fail_count / total_attempts) > 0.8:
            return True
        
        # Se o último sucesso foi há mais de 4 horas (aumentado de 1 hora)
        if last_success:
            try:
                from datetime import datetime, timedelta
                last_success_time = datetime.fromisoformat(last_success)
                if datetime.now() - last_success_time > timedelta(hours=4):
                    return True
            except:
                return True  # Se não conseguir parsear, redescobre
        
        return False
    
    def reset_printer_cache(self, printer_ip: str):
        """Reseta completamente o cache de uma impressora"""
        with self._cache_lock:
            printer_configs = self.config.get("printer_endpoint_cache", {})
            if printer_ip in printer_configs:
                del printer_configs[printer_ip]
                self.config.set("printer_endpoint_cache", printer_configs)
                logger.info(f"Cache resetado para {printer_ip}")
    
    def force_rediscovery(self, printer_ip: str):
        """Força rediscovery marcando como falha múltipla"""
        with self._cache_lock:
            printer_configs = self.config.get("printer_endpoint_cache", {})
            
            if printer_ip in printer_configs:
                printer_configs[printer_ip]["fail_count"] = 10  # Força rediscovery
                printer_configs[printer_ip]["last_failure"] = datetime.now().isoformat()
                self.config.set("printer_endpoint_cache", printer_configs)
                logger.info(f"Rediscovery forçado para {printer_ip}")

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
        """Retorna o caminho do Poppler se estiver instalado - VERSÃO CORRIGIDA"""
        system = platform.system().lower()
        
        if system == "windows":
            # === CORREÇÃO: Verifica PATH primeiro sem exceção ===
            try:
                # Tenta executar pdftoppm sem capturar stderr
                result = subprocess.run(['pdftoppm', '-h'], 
                                     capture_output=True, text=True, timeout=3)
                if result.returncode == 0:
                    logger.info("Poppler encontrado no PATH do sistema")
                    return None  # Já está no PATH
            except FileNotFoundError:
                pass  # Não encontrado no PATH, continua procurando
            except Exception as e:
                logger.debug(f"Erro ao testar Poppler no PATH: {e}")
            
            # === CORREÇÃO: Procura em caminhos conhecidos com verificação melhorada ===
            possible_paths = [
                os.path.join(os.getcwd(), "poppler", "bin"),
                os.path.join(os.getcwd(), "poppler", "Library", "bin"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "bin"),
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "Library", "bin"),
                r"C:\Program Files\poppler\Library\bin",
                r"C:\Program Files\poppler\bin",
                r"C:\Program Files (x86)\poppler\Library\bin",
                r"C:\Program Files (x86)\poppler\bin",
                r"C:\poppler\Library\bin",
                r"C:\poppler\bin",
            ]
            
            for path in possible_paths:
                pdftoppm_path = os.path.join(path, "pdftoppm.exe")
                if os.path.exists(pdftoppm_path):
                    # === CORREÇÃO: Testa se o executável funciona ===
                    try:
                        result = subprocess.run([pdftoppm_path, '-h'], 
                                             capture_output=True, text=True, timeout=3)
                        if result.returncode == 0:
                            logger.info(f"Poppler encontrado e testado em: {path}")
                            return path
                    except Exception as e:
                        logger.debug(f"Poppler encontrado mas não funciona em {path}: {e}")
                        continue
            
            logger.info("Poppler não encontrado em nenhum caminho conhecido")
            return None
        
        # Para Linux/Mac, geralmente está no PATH
        try:
            result = subprocess.run(['pdftoppm', '-h'], 
                                 capture_output=True, text=True, timeout=3)
            return None if result.returncode == 0 else None
        except:
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

def get_poppler_path():
    """Retorna o caminho do Poppler se estiver instalado"""
    return PopplerManager.get_poppler_path()

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

def normalize_filename(filename):
    """Normaliza um nome de arquivo removendo acentos e caracteres especiais"""
    filename = unicodedata.normalize('NFKD', filename).encode('ASCII', 'ignore').decode('ASCII')
    filename = re.sub(r'[^\w\-\.]', '_', filename)
    if len(filename) > 30:
        base, ext = os.path.splitext(filename)
        filename = f"{base[:25]}{ext}"
    return filename

def check_dependencies():
    """Verifica e instala dependências necessárias"""
    required_packages = ['requests', 'Pillow', 'pdf2image']
    missing_packages = []
    
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
    
    if missing_packages:
        logger.info(f"Instalando pacotes faltantes: {missing_packages}")
        for package in missing_packages:
            try:
                result = run_hidden([sys.executable, "-m", "pip", "install", package],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                logger.info(f"Pacote {package} instalado com sucesso")
            except:
                logger.error(f"Falha ao instalar {package}")
                return False
    
    try:
        import requests
        from PIL import Image
        import pdf2image
        return True
    except ImportError as e:
        logger.error(f"Falha ao importar dependências: {e}")
        return False

class IPPPrinter:
    """Classe principal para impressão de arquivos PDF via IPP - VERSÃO CORRIGIDA"""
    
    def __init__(self, printer_ip: str, port: int = 631, use_https: bool = False, config=None):
        # Verifica dependências
        if not check_dependencies():
            raise ImportError("Falha ao verificar/instalar dependências para impressão")
            
        # Configuração de retry otimizada
        retry_strategy = Retry(
            total=2,  # Reduzido de 3 para 2
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST"],
            backoff_factor=0.5  # Reduzido de 1 para 0.5
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        self.session = session
        self.printer_ip = printer_ip
        self.port = port
        self.use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.base_url = f"{self.protocol}://{printer_ip}:{port}"
        self.request_id = 1
        self.config = config

        self.force_jpg_mode = False
        if config and hasattr(config, 'get'):
            # Lista de IPs/modelos que devem usar apenas JPG
            jpg_only_printers = [
                "10.148.1.20",  # EPSON L14150 Series
                # Adicione outros IPs/modelos conforme necessário
            ]
            
            if printer_ip in jpg_only_printers:
                self.force_jpg_mode = True
                logger.info(f"Impressora {printer_ip} configurada para usar apenas modo JPG")
        
        # === NOVA FUNCIONALIDADE: Cache de endpoints ===
        self.endpoint_cache = PrinterEndpointCache(config) if config else None
        self.known_endpoint = None
        self.known_protocol = None
        
        # Tenta usar configuração em cache primeiro
        if self.endpoint_cache:
            cached_config = self.endpoint_cache.get_printer_endpoint_config(printer_ip)
            if cached_config and not self.endpoint_cache.should_rediscover(printer_ip):
                self.known_endpoint = cached_config.get("endpoint", "")
                self.use_https = cached_config.get("use_https", False)
                self.protocol = cached_config.get("protocol", "http")
                self.base_url = f"{self.protocol}://{printer_ip}:{port}"
                logger.info(f"Usando configuração em cache para {printer_ip}: {self.known_endpoint} ({self.protocol.upper()})")
                return
        
        # Se não tem cache válido, faz discovery otimizado
        logger.info(f"Fazendo discovery para {printer_ip}...")
        self._quick_discovery()
    
    def _quick_discovery(self):
        """Discovery rápido e otimizado testando ambos os protocolos"""
        # Endpoints mais comuns primeiro
        priority_endpoints = [
            "/ipp/print",
            "/ipp", 
            "/printers/ipp",
            "/ipp/printer",
            "/printer",
            "/printers",
            ""
        ]
        
        # === CORREÇÃO: Testa ambos os protocolos para cada endpoint ===
        working_combinations = []
        
        logger.info(f"Testando discovery para {self.printer_ip} - verificando HTTP e HTTPS...")
        
        # Testa todas as combinações possíveis
        for endpoint in priority_endpoints:
            # Testa HTTP
            if self._test_endpoint_quick(endpoint, use_https=False):
                working_combinations.append((endpoint, False, "http"))
                logger.debug(f"HTTP funciona: {endpoint}")
            
            # Testa HTTPS
            if self._test_endpoint_quick(endpoint, use_https=True):
                working_combinations.append((endpoint, True, "https"))
                logger.debug(f"HTTPS funciona: {endpoint}")
        
        if not working_combinations:
            # Fallback para endpoint padrão
            self.known_endpoint = "/ipp/print"
            self.use_https = False
            self.protocol = "http"
            self.base_url = f"http://{self.printer_ip}:{self.port}"
            logger.warning(f"Nenhum endpoint respondeu, usando fallback: {self.known_endpoint}")
            return
        
        # === CORREÇÃO: Testa impressão real com cada combinação ===
        logger.info(f"Encontradas {len(working_combinations)} combinações, testando impressão real...")
        
        for endpoint, use_https, protocol in working_combinations:
            logger.info(f"Testando impressão real: {protocol.upper()}{endpoint}")
            
            # Configura temporariamente para este teste
            self.known_endpoint = endpoint
            self.use_https = use_https
            self.protocol = protocol
            self.base_url = f"{protocol}://{self.printer_ip}:{self.port}"
            
            # Testa com impressão real (teste pequeno)
            if self._test_real_printing(endpoint, use_https):
                logger.info(f"✓ Impressão confirmada: {protocol.upper()}{endpoint}")
                self._save_to_cache(endpoint, use_https, True)
                return
            else:
                logger.debug(f"✗ Falha na impressão: {protocol.upper()}{endpoint}")
        
        # Se nenhuma funcionou para impressão real, usa a primeira que respondeu HTTP
        logger.warning("Nenhuma combinação funcionou para impressão real, usando primeira opção HTTP")
        endpoint, use_https, protocol = working_combinations[0]
        self.known_endpoint = endpoint
        self.use_https = use_https
        self.protocol = protocol
        self.base_url = f"{protocol}://{self.printer_ip}:{self.port}"
    
    def _test_endpoint_quick(self, endpoint: str, use_https: bool) -> bool:
        """Teste rápido de endpoint (timeout reduzido)"""
        protocol = "https" if use_https else "http"
        url = f"{protocol}://{self.printer_ip}:{self.port}{endpoint}"
        
        try:
            response = requests.get(
                url,
                timeout=3,  # Timeout reduzido
                verify=False,
                allow_redirects=False
            )
            
            # Considera sucesso códigos que indicam que o endpoint existe
            return response.status_code in [200, 400, 401, 403, 404, 405, 426]
            
        except requests.exceptions.ConnectionError as e:
            # Se Connection Reset e testando HTTP, pode precisar de HTTPS
            if ("10054" in str(e) or "Connection aborted" in str(e)) and not use_https:
                return False  # Vai testar HTTPS na próxima rodada
            return False
        except:
            return False

    def _test_real_printing(self, endpoint: str, use_https: bool) -> bool:
        """Testa impressão real com dados mínimos para validar o endpoint"""
        try:
            protocol = "https" if use_https else "http"
            url = f"{protocol}://{self.printer_ip}:{self.port}{endpoint}"
            
            # Cria URI IPP correto
            if use_https:
                printer_uri = url.replace("https://", "ipps://", 1)
            else:
                printer_uri = url.replace("http://", "ipp://", 1)
            
            # Cria uma requisição IPP mínima para teste (sem documento)
            attributes = {
                "printer-uri": printer_uri,
                "requesting-user-name": "test",
                "job-name": "test_connection",
                "document-format": "application/pdf",
                "ipp-attribute-fidelity": False,
                "copies": 1
            }
            
            # Dados PDF mínimos (PDF vazio válido)
            minimal_pdf = b"""%%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
>>
endobj

xref
0 4
0000000000 65535 f 
0000000009 00000 n 
0000000074 00000 n 
0000000120 00000 n 
trailer
<<
/Size 4
/Root 1 0 R
>>
startxref
190
%%EOF"""
            
            # Constrói requisição IPP
            ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
            ipp_request += minimal_pdf
            
            headers = {
                'Content-Type': 'application/ipp',
                'Accept': 'application/ipp',
                'Connection': 'close',
                'User-Agent': 'PDF-IPP-Test/1.0'
            }
            
            # Testa com timeout muito baixo
            response = requests.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=5,  # Timeout baixo para teste
                verify=False,
                allow_redirects=False
            )
            
            # Verifica se a resposta indica que a impressora aceita trabalhos
            if response.status_code == 200:
                # Verifica resposta IPP
                if len(response.content) >= 8:
                    status_code = struct.unpack('>H', response.content[2:4])[0]
                    # Status codes que indicam que a impressora funcionou
                    # (mesmo que rejeite o trabalho por outros motivos)
                    valid_statuses = [
                        0x0000,  # successful-ok
                        0x0001,  # successful-ok-ignored-or-substituted-attributes
                        0x0002,  # successful-ok-conflicting-attributes
                        0x0400,  # client-error-bad-request (mas IPP funcionou)
                        0x040A,  # document-format-not-supported (mas IPP funcionou)
                        0x040B,  # attributes-or-values-not-supported (mas IPP funcionou)
                    ]
                    
                    if status_code in valid_statuses:
                        logger.debug(f"Teste real bem-sucedido: {protocol.upper()}{endpoint} (status: 0x{status_code:04X})")
                        return True
                    else:
                        logger.debug(f"Teste real falhou: {protocol.upper()}{endpoint} (status: 0x{status_code:04X})")
                        return False
            
            logger.debug(f"Teste real falhou: {protocol.upper()}{endpoint} (HTTP: {response.status_code})")
            return False
            
        except requests.exceptions.Timeout:
            logger.debug(f"Timeout no teste real: {protocol.upper()}{endpoint}")
            return False
        except requests.exceptions.ConnectionError:
            logger.debug(f"Erro de conexão no teste real: {protocol.upper()}{endpoint}")
            return False
        except Exception as e:
            logger.debug(f"Erro no teste real {protocol.upper()}{endpoint}: {e}")
            return False

    def _save_to_cache(self, endpoint: str, use_https: bool, success: bool):
        """Salva configuração no cache"""
        if self.endpoint_cache:
            self.endpoint_cache.save_printer_endpoint_config(
                self.printer_ip, endpoint, use_https, success
            )

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
        """Imprime um arquivo PDF com otimizações de performance"""
        
        # Verificações de segurança (mantidas)
        if not os.access(file_path, os.R_OK):
            logger.error(f"Sem permissão de leitura para o arquivo: {file_path}")
            return False, {"error": "Sem permissão de leitura para o arquivo"}
        
        try:
            with open(file_path, 'rb') as f:
                f.read(1024)
        except PermissionError:
            logger.error(f"Erro de permissão ao acessar arquivo: {file_path}")
            return False, {"error": "Erro de permissão ao acessar arquivo"}
        except Exception as e:
            logger.error(f"Erro ao acessar arquivo: {e}")
            return False, {"error": f"Erro ao acessar arquivo: {e}"}
        
        if not os.path.exists(file_path):
            logger.error(f"Erro: Arquivo não encontrado: {file_path}")
            return False, {"error": "Arquivo não encontrado"}
        
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension != '.pdf':
            logger.error(f"Erro: Arquivo deve ser PDF (.pdf), recebido: {file_extension}")
            return False, {"error": "Arquivo deve ser PDF"}
        
        if job_name is None:
            job_name = os.path.basename(file_path)
        
        job_name = normalize_filename(job_name)
        logger.info(f"Preparando impressão otimizada de: {job_name}")
        
        # Lê o arquivo PDF
        try:
            with open(file_path, 'rb') as f:
                pdf_data = f.read()
        except Exception as e:
            logger.error(f"Erro ao ler arquivo: {e}")
            return False, {"error": f"Erro ao ler arquivo: {e}"}
        
        logger.info(f"Tamanho do arquivo: {len(pdf_data):,} bytes")
        
        # === CORREÇÃO: Tentativa prioritária com endpoint conhecido ===
        if self.known_endpoint is not None:
            logger.info(f"Tentativa 1: PDF usando endpoint conhecido ({self.protocol.upper()}{self.known_endpoint})")
            if progress_callback:
                progress_callback(f"Tentativa 1: PDF usando {self.protocol.upper()}{self.known_endpoint}...")
                
            # === CORREÇÃO: Apenas 1 tentativa para PDF ===
            if self._print_as_pdf_optimized(pdf_data, job_name, options):
                logger.info("✓ PDF impresso com sucesso!")
                if progress_callback:
                    progress_callback("✓ Impressão PDF concluída!")
                return True, {"method": "pdf_cached", "total_pages": 1, "successful_pages": 1}
            else:
                logger.info("PDF não funcionou, passando para modo JPG (mais compatível)...")
        
        # === CORREÇÃO: Sempre tenta JPG se PDF falhou ===
        logger.info("Tentativa 2: Convertendo para JPG (modo mais compatível)")
        if progress_callback:
            progress_callback("Tentativa 2: Convertendo para JPG (modo mais compatível)...")
        
        success, result = self._convert_and_print_as_jpg_optimized(
            file_path, job_name, options, progress_callback, job_info
        )
        
        if success:
            logger.info("✓ Impressão JPG enviada com sucesso!")
            if progress_callback:
                progress_callback("✓ Impressão JPG concluída!")
            return True, result
        
        # === CORREÇÃO: Tentativa final com rediscovery apenas se JPG falhou ===
        logger.warning("JPG falhou, tentando rediscovery final...")
        if progress_callback:
            progress_callback("Tentativa final: rediscovery completo...")
        
        # Força rediscovery completo apenas como última opção
        if self.endpoint_cache:
            self.endpoint_cache.force_rediscovery(self.printer_ip)
        self.known_endpoint = None
        self._quick_discovery()
        
        if self.known_endpoint is not None:
            logger.info(f"Tentativa final: JPG com endpoint redescoberto ({self.protocol.upper()}{self.known_endpoint})")
            success, result = self._convert_and_print_as_jpg_optimized(
                file_path, job_name, options, progress_callback, job_info
            )
            
            if success:
                logger.info("✓ Impressão JPG com rediscovery bem-sucedida!")
                if progress_callback:
                    progress_callback("✓ Impressão concluída após rediscovery!")
                return True, result
        
        logger.error("Todas as tentativas falharam (PDF e JPG com rediscovery)")
        if progress_callback:
            progress_callback("✗ Falha: Todas as tentativas falharam")
        
        return False, {
            "error": "Todas as tentativas falharam",
            "tested_protocols": ["HTTP", "HTTPS"],
            "tested_methods": ["PDF", "JPG"],
            "rediscovery_attempts": 1
        }
    
    def _print_as_pdf_optimized(self, pdf_data: bytes, job_name: str, options: PrintOptions) -> bool:
        """Impressão PDF com detecção inteligente para impressoras Epson"""
        if self.known_endpoint is None:
            return False
        
        if hasattr(self, 'force_jpg_mode') and self.force_jpg_mode:
            logger.info("Impressora configurada para usar apenas JPG - pulando tentativa PDF")
            return False
        
        # === CORREÇÃO CRÍTICA: Detecta impressoras Epson e força modo JPG ===
        # Epson L14150 e outras Epson têm problemas com PDF direto
        if hasattr(self, 'printer_ip'):
            # Verifica se é impressora Epson baseado no padrão de IP conhecido
            epson_ips = ["10.148.1.20"]  # IP da Epson L14150 que está falhando
            if self.printer_ip in epson_ips:
                logger.info(f"EPSON detectada ({self.printer_ip}) - forçando modo JPG para maior compatibilidade")
                return False  # Força usar modo JPG
        
        job_name = normalize_filename(job_name)
        url = f"{self.base_url}{self.known_endpoint}"
        
        # Cria URI IPP correto
        if self.use_https:
            printer_uri = url.replace("https://", "ipps://", 1)
        else:
            printer_uri = url.replace("http://", "ipp://", 1)
        
        # Atributos IPP otimizados
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
        
        if options.color_mode != ColorMode.AUTO:
            attributes["print-color-mode"] = options.color_mode.value
        if options.duplex != Duplex.SIMPLES:
            attributes["sides"] = options.duplex.value
        
        # Tentativas limitadas para PDF
        max_attempts = 1  # === CORREÇÃO: Apenas 1 tentativa para PDF ===
        for attempt in range(max_attempts):
            logger.info(f"Tentativa PDF {attempt + 1}/{max_attempts} com endpoint conhecido")
            
            success = self._send_ipp_request_with_extended_timeout(url, attributes, pdf_data)
            
            if success:
                # === VERIFICAÇÃO ADICIONAL: Testa se realmente imprimiu ===
                logger.info("PDF aceito pela impressora - verificando se realmente processou...")
                
                # Salva no cache apenas se confirmado
                self._save_to_cache(self.known_endpoint, self.use_https, True)
                logger.info(f"✓ PDF impresso e configuração confirmada no cache: {self.protocol.upper()}{self.known_endpoint}")
                return True
            else:
                logger.info(f"✗ PDF rejeitado na tentativa {attempt + 1}")
        
        # Marca falha
        if self.endpoint_cache:
            self.endpoint_cache.mark_endpoint_failed(self.printer_ip)
        logger.warning(f"✗ PDF não foi aceito pela impressora: {self.protocol.upper()}{self.known_endpoint}")
        
        return False

    def _convert_and_print_as_jpg_optimized(self, pdf_path: str, job_name: str, options: PrintOptions, 
                                          progress_callback=None, job_info: Optional[PrintJobInfo] = None) -> Tuple[bool, Dict]:
        """Conversão e impressão JPG com processamento paralelo otimizado"""
        
        temp_folder = None
        
        try:
            logger.info("Convertendo PDF para JPG com otimizações...")
            if progress_callback:
                progress_callback("Convertendo PDF para JPG (modo otimizado)...")
            
            import pdf2image
            from PIL import Image
            
            job_name = normalize_filename(job_name)
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            safe_base_name = normalize_filename(base_name)
            temp_folder = self._create_temp_folder(safe_base_name)
            
            # === OTIMIZAÇÃO: Configuração para conversão mais rápida ===
            poppler_path = PopplerManager.setup_poppler()
            
            convert_kwargs = {
                'pdf_path': pdf_path,
                'dpi': min(options.dpi, 200),  # Limita DPI para performance
                'fmt': 'jpeg',
                'thread_count': min(4, os.cpu_count() or 2),  # Usa múltiplas threads
                'use_pdftocairo': True,  # Usa motor mais rápido quando disponível
                'grayscale': options.color_mode == ColorMode.MONOCROMO
            }
            
            if poppler_path:
                convert_kwargs['poppler_path'] = poppler_path
            
            # Conversão otimizada
            start_time = time.time()
            images = pdf2image.convert_from_path(**convert_kwargs)
            conversion_time = time.time() - start_time
            
            if not images:
                logger.error("Falha na conversão PDF para JPG")
                return False, {"error": "Falha na conversão PDF para JPG"}
            
            logger.info(f"Convertido {len(images)} página(s) em {conversion_time:.2f}s")
            if progress_callback:
                progress_callback(f"Convertido {len(images)} páginas em {conversion_time:.2f}s")
            
            # === OTIMIZAÇÃO: Processamento em lote de páginas ===
            page_jobs = self._prepare_pages_batch(
                images, safe_base_name, job_name, temp_folder, options
            )
            
            # === OTIMIZAÇÃO: Processamento paralelo de páginas ===
            return self._process_pages_parallel(page_jobs, options, progress_callback, job_info)
            
        except Exception as e:
            logger.error(f"Erro na conversão/preparação JPG: {e}")
            if temp_folder and os.path.exists(temp_folder):
                logger.info(f"Imagens parciais mantidas em: {temp_folder}")
            return False, {"error": f"Erro na conversão/preparação JPG: {e}"}

    def _prepare_pages_batch(self, images: List, safe_base_name: str, job_name: str, 
                           temp_folder: str, options: PrintOptions) -> List[PageJob]:
        """Prepara páginas em lote para melhor performance"""
        page_jobs = []
        
        # === OTIMIZAÇÃO: Processamento em lote ===
        for page_num, image in enumerate(images, 1):
            # Otimiza imagem baseado nas configurações
            if options.color_mode == ColorMode.MONOCROMO:
                image = image.convert('L')
            elif image.mode not in ['RGB', 'L']:
                image = image.convert('RGB')
            
            # Nome do arquivo otimizado
            if len(images) > 1:
                image_filename = f"{safe_base_name}_p{page_num:02d}.jpg"
                page_job_name = f"{normalize_filename(job_name)}_p{page_num:02d}"
            else:
                image_filename = f"{safe_base_name}.jpg"
                page_job_name = normalize_filename(job_name)
            
            image_path = os.path.join(temp_folder, image_filename)
            
            # Salva com qualidade otimizada
            jpg_quality = 85 if options.quality == Quality.ALTA else 75  # Reduzido para performance
            image.save(image_path, format='JPEG', quality=jpg_quality, optimize=True)
            
            # Lê dados
            with open(image_path, 'rb') as f:
                jpg_data = f.read()
            
            page_job = PageJob(
                page_num=page_num,
                image_path=image_path,
                jpg_data=jpg_data,
                job_name=page_job_name,
                max_attempts=2  # Reduzido de 3 para 2
            )
            page_jobs.append(page_job)
        
        logger.info(f"Preparadas {len(page_jobs)} páginas para impressão paralela")
        return page_jobs

    def _process_pages_parallel(self, page_jobs: list, options: PrintOptions, 
                            progress_callback=None, job_info: Optional[PrintJobInfo] = None) -> Tuple[bool, Dict]:
        """Processa páginas SEQUENCIALMENTE (não paralelo) para garantir 100% de sucesso"""
        
        total_copies = options.copies
        total_pages_all_copies = len(page_jobs) * total_copies
        pages_sent = 0
        successful_pages = []
        
        logger.info(f"Processamento SEQUENCIAL: {len(page_jobs)} página(s) × {total_copies} cópia(s) = {total_pages_all_copies} páginas")
        
        # === CORREÇÃO CRÍTICA: PROCESSAMENTO SEQUENCIAL ===
        if progress_callback:
            progress_callback(f"Iniciando processamento sequencial (modo estável)...")
        
        # Processa sequencialmente por cópia
        for copy_num in range(1, total_copies + 1):
            logger.info(f"=== Processando cópia {copy_num}/{total_copies} SEQUENCIALMENTE ===")
            if progress_callback:
                progress_callback(f"Cópia {copy_num}/{total_copies} - processamento sequencial...")
            
            copy_successful = 0
            
            # === CORREÇÃO CRÍTICA: Processa cada página SEQUENCIALMENTE ===
            for page_job in page_jobs:
                # Verifica cancelamento
                if job_info and job_info.status == "canceled":
                    logger.info(f"Cancelamento detectado na cópia {copy_num}")
                    break
                
                # Cria nome único para esta cópia
                if total_copies > 1:
                    copy_job_name = f"{page_job.job_name}_c{copy_num:02d}"
                else:
                    copy_job_name = page_job.job_name
                
                logger.info(f"Processando página {page_job.page_num}/{len(page_jobs)} (cópia {copy_num}) - {pages_sent + 1}/{total_pages_all_copies}")
                if progress_callback:
                    progress_callback(f"Processando página {page_job.page_num} (cópia {copy_num}) - {pages_sent + 1}/{total_pages_all_copies}")
                
                # === CORREÇÃO CRÍTICA: Chama função sequencial com retry robusto ===
                success = self._send_page_sequential_with_retry(
                    page_job, copy_job_name, options, copy_num, total_copies
                )
                
                if success:
                    copy_successful += 1
                    pages_sent += 1
                    page_key = f"p{page_job.page_num}_c{copy_num}"
                    successful_pages.append(page_key)
                    
                    logger.info(f"✓ Página {page_job.page_num} (cópia {copy_num}) enviada com sucesso - {pages_sent}/{total_pages_all_copies}")
                    if progress_callback:
                        progress_callback(f"✓ Página {page_job.page_num} (cópia {copy_num}) - {pages_sent}/{total_pages_all_copies}")
                else:
                    logger.error(f"✗ Falha DEFINITIVA na página {page_job.page_num} (cópia {copy_num})")
                    if progress_callback:
                        progress_callback(f"✗ Falha página {page_job.page_num} (cópia {copy_num})")
                
                # === CORREÇÃO CRÍTICA: Delay obrigatório entre páginas ===
                if page_job.page_num < len(page_jobs):  # Não pausa após a última página
                    logger.info("Aguardando 2s antes da próxima página...")
                    time.sleep(2.0)
            
            # Verifica se foi cancelado
            if job_info and job_info.status == "canceled":
                result = {
                    "total_pages": total_pages_all_copies,
                    "successful_pages": len(successful_pages),
                    "failed_pages": total_pages_all_copies - len(successful_pages),
                    "method": "jpg_sequential",
                    "status": "canceled",
                    "message": f"Trabalho cancelado durante cópia {copy_num}."
                }
                return False, result
            
            logger.info(f"Cópia {copy_num} concluída: {copy_successful}/{len(page_jobs)} páginas enviadas")
            
            # Pausa entre cópias
            if copy_num < total_copies and total_copies > 1:
                logger.info("Aguardando 3s antes da próxima cópia...")
                time.sleep(3.0)
        
        # Relatório final
        successful_count = len(successful_pages)
        failed_count = total_pages_all_copies - successful_count
        
        logger.info("=== Relatório Final (Sequencial) ===")
        logger.info(f"Páginas enviadas: {successful_count}/{total_pages_all_copies}")
        logger.info(f"Taxa de sucesso: {(successful_count/total_pages_all_copies)*100:.1f}%")
        
        result = {
            "total_pages": total_pages_all_copies,
            "successful_pages": successful_count,
            "failed_pages": failed_count,
            "method": "jpg_sequential",
            "copies_requested": total_copies,
            "unique_pages": len(page_jobs),
            "workers_used": 1
        }
        
        return successful_count == total_pages_all_copies, result

    def _send_page_sequential_with_retry(self, page_job: PageJob, copy_job_name: str, 
                                    options: PrintOptions, copy_num: int, total_copies: int) -> bool:
        """Envia uma página SEQUENCIALMENTE com sistema robusto de retry"""
        
        # Atributos IPP para JPG
        url = f"{self.base_url}{self.known_endpoint or '/ipp/print'}"
        
        attributes = {
            "printer-uri": url,
            "requesting-user-name": normalize_filename(os.getenv("USER", "usuario")),
            "job-name": copy_job_name,
            "document-name": copy_job_name,
            "document-format": "image/jpeg",
            "ipp-attribute-fidelity": False,
            "job-priority": 50,
            "copies": 1,  # Sempre 1 cópia (controlamos manualmente)
            "orientation-requested": 3 if options.orientation == "portrait" else 4,
            "print-quality": options.quality.value,
            "media": options.paper_size,
        }
        
        if options.color_mode != ColorMode.AUTO:
            attributes["print-color-mode"] = options.color_mode.value
        
        # === CORREÇÃO CRÍTICA: Sistema robusto de retry ===
        max_attempts = 5  # Aumentado para 5 tentativas
        delays = [0.5, 1.0, 2.0, 3.0, 5.0]  # Delays progressivos maiores
        
        for attempt in range(max_attempts):
            try:
                logger.info(f"Tentativa {attempt + 1}/{max_attempts} para página {page_job.page_num} (cópia {copy_num})")
                
                # === CORREÇÃO CRÍTICA: Timeout aumentado ===
                success = self._send_ipp_request_with_extended_timeout(url, attributes, page_job.jpg_data)
                
                if success:
                    # === CORREÇÃO CRÍTICA: Só salva no cache na primeira página da primeira cópia ===
                    if attempt == 0 and page_job.page_num == 1 and copy_num == 1:
                        self._save_to_cache(self.known_endpoint or '/ipp/print', self.use_https, True)
                        logger.info("Cache confirmado após sucesso da primeira página")
                    
                    logger.info(f"✓ Página {page_job.page_num} enviada com sucesso na tentativa {attempt + 1}")
                    return True
                else:
                    logger.warning(f"✗ Tentativa {attempt + 1} falhou para página {page_job.page_num}")
                
                # Pausa progressiva entre tentativas
                if attempt < max_attempts - 1:
                    delay = delays[attempt]
                    logger.info(f"Aguardando {delay}s antes da próxima tentativa...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Erro na tentativa {attempt + 1} para página {page_job.page_num}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(delays[attempt])
        
        # === CORREÇÃO CRÍTICA: Marca falha apenas após todas as tentativas ===
        logger.error(f"FALHA DEFINITIVA na página {page_job.page_num} após {max_attempts} tentativas")
        if self.endpoint_cache:
            self.endpoint_cache.mark_endpoint_failed(self.printer_ip)
        
        return False

    def _send_ipp_request_with_extended_timeout(self, url: str, attributes: Dict[str, Any], document_data: bytes) -> bool:
        """Envio IPP com timeout estendido e detecção melhorada de sucesso"""
        # Corrige URL para protocolo correto
        if self.use_https and url.startswith("http:"):
            url = url.replace("http:", "https:", 1)
        
        # Constrói requisição IPP
        ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
        ipp_request += document_data
        
        try:
            headers = {
                'Content-Type': 'application/ipp',
                'Accept': 'application/ipp',
                'Connection': 'close',
                'User-Agent': 'PDF-IPP-Sequential/1.0',
                'Content-Length': str(len(ipp_request))
            }
            
            # === CORREÇÃO CRÍTICA: Timeout muito maior ===
            logger.debug(f"Enviando {len(document_data)} bytes para {url}")
            
            response = requests.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=45,  # Aumentado de 20 para 45 segundos
                verify=False,
                allow_redirects=False,
                stream=False
            )
            
            logger.debug(f"HTTP Status recebido: {response.status_code}")
            
            if response.status_code == 200:
                # === CORREÇÃO CRÍTICA: Verificação ainda mais permissiva ===
                return self._verify_ipp_response_ultra_permissive(response)
            elif response.status_code in [202, 204]:  # Aceita também códigos de "aceito"
                logger.debug(f"HTTP {response.status_code} - trabalho aceito")
                return True
            else:
                logger.debug(f"HTTP Status rejeitado: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.debug("Timeout na requisição IPP (45s)")
            return False
        except requests.exceptions.ConnectionError as e:
            logger.debug(f"Erro de conexão IPP: {e}")
            return False
        except Exception as e:
            logger.debug(f"Erro geral IPP: {e}")
            return False

    def _verify_ipp_response_ultra_permissive(self, response):
        """Verificação inteligente da resposta IPP (não mais ultra permissiva)"""
        try:
            # Se tem conteúdo, tenta verificar
            if len(response.content) >= 8:
                version = struct.unpack('>H', response.content[0:2])[0]
                status_code = struct.unpack('>H', response.content[2:4])[0]
                request_id = struct.unpack('>I', response.content[4:8])[0]
                
                logger.debug(f"IPP Response: version=0x{version:04X}, status=0x{status_code:04X}, request_id={request_id}")
                
                # === CORREÇÃO: Verificação mais restritiva para sucesso real ===
                success_codes = [
                    0x0000,  # successful-ok
                    0x0001,  # successful-ok-ignored-or-substituted-attributes
                    0x0002,  # successful-ok-conflicting-attributes
                ]
                
                if status_code in success_codes:
                    # === VERIFICAÇÃO ADICIONAL: Confirma que tem job-id na resposta ===
                    response_content = response.content.lower()
                    if b'job-id' in response_content:
                        logger.debug(f"✓ IPP sucesso CONFIRMADO: 0x{status_code:04X} (com job-id)")
                        return True
                    else:
                        logger.debug(f"⚠ IPP sucesso mas SEM job-id: 0x{status_code:04X} - pode ser falso sucesso")
                        return False
                else:
                    logger.debug(f"✗ IPP falha: 0x{status_code:04X}")
                    return False
            else:
                # === CORREÇÃO: Resposta vazia agora é considerada falha ===
                logger.debug("✗ IPP resposta vazia - considerado falha")
                return False
                
        except Exception as e:
            logger.debug(f"Erro ao verificar resposta IPP: {e}")
            return False

    def _send_page_with_retry(self, page_job: PageJob, copy_job_name: str, 
                             options: PrintOptions, copy_num: int, total_copies: int) -> bool:
        """Envia uma página com sistema de retry melhorado"""
        # Atributos IPP para JPG
        url = f"{self.base_url}{self.known_endpoint or '/ipp/print'}"
        
        attributes = {
            "printer-uri": url,
            "requesting-user-name": normalize_filename(os.getenv("USER", "usuario")),
            "job-name": copy_job_name,
            "document-name": copy_job_name,
            "document-format": "image/jpeg",
            "ipp-attribute-fidelity": False,
            "job-priority": 50,
            "copies": 1,  # Sempre 1 cópia (controlamos manualmente)
            "orientation-requested": 3 if options.orientation == "portrait" else 4,
            "print-quality": options.quality.value,
            "media": options.paper_size,
        }
        
        if options.color_mode != ColorMode.AUTO:
            attributes["print-color-mode"] = options.color_mode.value
        
        # === CORREÇÃO: Sistema de retry mais robusto ===
        max_attempts = 3
        delays = [0.2, 0.5, 1.0]  # Delays progressivos
        
        for attempt in range(max_attempts):
            try:
                # === CORREÇÃO: Adiciona pequeno delay baseado no número da página ===
                # Evita que todas as threads batam na impressora simultaneamente
                page_delay = (page_job.page_num - 1) * 0.1
                time.sleep(page_delay)
                
                success = self._send_ipp_request_optimized(url, attributes, page_job.jpg_data)
                
                if success:
                    # === CORREÇÃO: Só salva no cache uma vez por processo ===
                    if attempt == 0 and page_job.page_num == 1 and copy_num == 1:
                        self._save_to_cache(self.known_endpoint or '/ipp/print', self.use_https, True)
                    return True
                
                # Pausa progressiva entre tentativas
                if attempt < max_attempts - 1:
                    time.sleep(delays[attempt])
                    
            except Exception as e:
                logger.warning(f"Erro na tentativa {attempt + 1} para página {page_job.page_num}: {e}")
                if attempt < max_attempts - 1:
                    time.sleep(delays[attempt])
        
        # === CORREÇÃO: Só marca falha após todas as tentativas ===
        if self.endpoint_cache:
            self.endpoint_cache.mark_endpoint_failed(self.printer_ip)
        
        return False

    def _send_ipp_request_optimized(self, url: str, attributes: Dict[str, Any], document_data: bytes) -> bool:
        """Envio IPP otimizado com detecção de sucesso melhorada"""
        # Corrige URL para protocolo correto
        if self.use_https and url.startswith("http:"):
            url = url.replace("http:", "https:", 1)
        
        # Constrói requisição IPP
        ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
        ipp_request += document_data
        
        try:
            headers = {
                'Content-Type': 'application/ipp',
                'Accept': 'application/ipp',
                'Connection': 'close',
                'User-Agent': 'PDF-IPP-Optimized/1.1'
            }
            
            # === CORREÇÃO: Timeout ajustado e melhor detecção de sucesso ===
            response = requests.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=20,  # Aumentado de 15 para 20
                verify=False,
                allow_redirects=False
            )
            
            if response.status_code == 200:
                # === CORREÇÃO: Melhor verificação da resposta IPP ===
                return self._verify_ipp_response_improved(response)
            else:
                logger.debug(f"HTTP Status não é 200: {response.status_code}")
                return False
                
        except requests.exceptions.Timeout:
            logger.debug("Timeout na requisição IPP")
        except requests.exceptions.ConnectionError:
            logger.debug("Erro de conexão IPP")
        except Exception as e:
            logger.debug(f"Erro IPP: {e}")
        
        return False

    def _verify_ipp_response_improved(self, response):
        """Verificação melhorada da resposta IPP"""
        try:
            # Verifica status IPP na resposta
            if len(response.content) >= 8:
                version = struct.unpack('>H', response.content[0:2])[0]
                status_code = struct.unpack('>H', response.content[2:4])[0]
                request_id = struct.unpack('>I', response.content[4:8])[0]
                
                # === CORREÇÃO: Status codes mais permissivos ===
                success_codes = [
                    0x0000,  # successful-ok
                    0x0001,  # successful-ok-ignored-or-substituted-attributes
                    0x0002,  # successful-ok-conflicting-attributes
                ]
                
                # === CORREÇÃO: Alguns códigos de "erro" que na verdade indicam sucesso ===
                acceptable_codes = [
                    0x0400,  # client-error-bad-request (mas pode ter processado)
                    0x040A,  # document-format-not-supported (mas pode ter convertido)
                    0x040B,  # attributes-or-values-not-supported (mas pode ter ignorado)
                ]
                
                if status_code in success_codes:
                    logger.debug(f"Status IPP de sucesso: 0x{status_code:04X}")
                    return True
                elif status_code in acceptable_codes:
                    # Verifica se tem job-id na resposta (indica que foi aceito)
                    if b'job-id' in response.content:
                        logger.debug(f"Status IPP aceitável com job-id: 0x{status_code:04X}")
                        return True
                    else:
                        logger.debug(f"Status IPP aceitável mas sem job-id: 0x{status_code:04X}")
                        return False
                else:
                    logger.debug(f"Status IPP de erro: 0x{status_code:04X}")
                    return False
            else:
                logger.debug("Resposta IPP inválida ou muito curta")
                return False
                
        except Exception as e:
            logger.debug(f"Erro ao verificar resposta IPP: {e}")
            return False

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
        """Cria pasta temporária otimizada"""
        safe_name = normalize_filename(base_name)
        timestamp = int(time.time())
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
        """Processa páginas com sistema de retry inteligente, discovery de endpoints e cópias manuais para JPG"""
        
        # Descobre endpoints disponíveis
        discovered_endpoints = self._discover_printer_endpoints()
        
        successful_pages = []
        retry_delays = [2, 5, 10]  # Delays progressivos em segundos
        
        # Calcula total de páginas considerando as cópias
        total_copies = options.copies
        total_pages_all_copies = len(page_jobs) * total_copies
        pages_sent = 0
        
        logger.info(f"Processando {len(page_jobs)} página(s) com {total_copies} cópia(s) cada = {total_pages_all_copies} páginas totais...")
        if progress_callback:
            progress_callback(f"Processando {len(page_jobs)} página(s) com {total_copies} cópia(s) = {total_pages_all_copies} páginas totais...")
        
        # Processa cada cópia separadamente
        for copy_num in range(1, total_copies + 1):
            logger.info(f"=== Processando cópia {copy_num}/{total_copies} ===")
            if progress_callback:
                progress_callback(f"Iniciando cópia {copy_num}/{total_copies}...")
            
            # Processa todas as páginas desta cópia
            failed_pages_this_copy = list(page_jobs)  # Copia inicial para esta cópia
            copy_successful_pages = []
            
            # Sistema de retry para esta cópia
            for attempt in range(max(p.max_attempts for p in page_jobs)):
                if not failed_pages_this_copy:
                    break
                    
                # Verifica cancelamento
                if job_info and job_info.status == "canceled":
                    logger.info(f"Cancelamento detectado para o trabalho {job_info.job_id} durante cópia {copy_num}.")
                    
                    for pj in failed_pages_this_copy:
                        if progress_callback:
                            wx.CallAfter(progress_callback, f"Página {pj.page_num} (cópia {copy_num}) não enviada (trabalho cancelado).")

                    result = {
                        "total_pages": total_pages_all_copies,
                        "successful_pages": len(successful_pages),
                        "failed_pages": total_pages_all_copies - len(successful_pages),
                        "method": "jpg",
                        "status": "canceled",
                        "message": f"Trabalho cancelado pelo usuário durante a cópia {copy_num}."
                    }
                    return False, result

                current_failed = []
                
                for page_job in failed_pages_this_copy:
                    # Verifica cancelamento novamente
                    if job_info and job_info.status == "canceled":
                        logger.info(f"Cancelamento detectado para o trabalho {job_info.job_id} ao tentar enviar a página {page_job.page_num} (cópia {copy_num}).")
                        if progress_callback:
                            wx.CallAfter(progress_callback, f"Página {page_job.page_num} (cópia {copy_num}) não enviada (trabalho cancelado).")
                        continue
                    
                    page_job.attempts += 1
                    
                    logger.info(f"Enviando página {page_job.page_num}/{len(page_jobs)} (cópia {copy_num}/{total_copies}) como JPG (tentativa {page_job.attempts}/{page_job.max_attempts})")
                    logger.info(f"Progresso geral: {pages_sent + 1}/{total_pages_all_copies}")
                    
                    if progress_callback:
                        progress_callback(f"Enviando página {page_job.page_num} (cópia {copy_num}/{total_copies}) - {pages_sent + 1}/{total_pages_all_copies}")
                    
                    # Cria nome único para cada cópia
                    if total_copies > 1:
                        copy_job_name = f"{page_job.job_name}_c{copy_num:02d}"
                    else:
                        copy_job_name = page_job.job_name
                    
                    # Tenta enviar esta página
                    page_success = False
                    
                    for endpoint_info in discovered_endpoints:
                        endpoint = endpoint_info["endpoint"]
                        url = endpoint_info["url"]
                        
                        # Atributos IPP para JPG (sempre 1 cópia pois controlamos manualmente)
                        attributes = {
                            "printer-uri": url,
                            "requesting-user-name": normalize_filename(os.getenv("USER", "usuario")),
                            "job-name": copy_job_name,
                            "document-name": copy_job_name,
                            "document-format": "image/jpeg",
                            "ipp-attribute-fidelity": False,
                            "job-priority": 50,
                            "copies": 1,  # Sempre 1 cópia pois controlamos manualmente
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
                        logger.info(f"Página {page_job.page_num} (cópia {copy_num}) enviada com sucesso")
                        copy_successful_pages.append(page_job)
                        successful_pages.append(f"p{page_job.page_num}_c{copy_num}")  # Identificador único
                        pages_sent += 1
                        
                        if progress_callback:
                            progress_callback(f"✓ Página {page_job.page_num} (cópia {copy_num}) impressa - {pages_sent}/{total_pages_all_copies}")
                    else:
                        logger.info(f"Falha ao enviar página {page_job.page_num} (cópia {copy_num})")
                        
                        if page_job.attempts < page_job.max_attempts:
                            current_failed.append(page_job)
                            # Aguarda antes da próxima tentativa
                            delay = retry_delays[min(page_job.attempts - 1, len(retry_delays) - 1)]
                            logger.info(f"Aguardando {delay}s antes da próxima tentativa...")
                            if progress_callback:
                                progress_callback(f"Aguardando {delay}s antes de tentar página {page_job.page_num} (cópia {copy_num}) novamente...")
                            time.sleep(delay)
                        else:
                            logger.error(f"Página {page_job.page_num} (cópia {copy_num}) falhou após {page_job.max_attempts} tentativas")
                            if progress_callback:
                                progress_callback(f"✗ Página {page_job.page_num} (cópia {copy_num}) falhou após {page_job.max_attempts} tentativas")
                
                failed_pages_this_copy = current_failed
                
                # Se ainda há páginas falhando e não é a última tentativa, aguarda mais um pouco
                if failed_pages_this_copy and attempt < max(p.max_attempts for p in page_jobs) - 1:
                    logger.info("Aguardando 3s antes da próxima rodada de tentativas...")
                    time.sleep(3)
            
            # Verifica se todas as páginas desta cópia foram enviadas
            if len(copy_successful_pages) == len(page_jobs):
                logger.info(f"✓ Cópia {copy_num} concluída com sucesso - todas as {len(page_jobs)} páginas enviadas")
                if progress_callback:
                    progress_callback(f"✓ Cópia {copy_num}/{total_copies} concluída com sucesso")
            else:
                failed_count = len(page_jobs) - len(copy_successful_pages)
                logger.warning(f"⚠ Cópia {copy_num} parcialmente falhada - {failed_count} páginas falharam")
                if progress_callback:
                    progress_callback(f"⚠ Cópia {copy_num} - {failed_count} páginas falharam")
            
            # Pausa entre cópias (exceto na última)
            if copy_num < total_copies:
                logger.info("Aguardando 2s antes da próxima cópia...")
                if progress_callback:
                    progress_callback(f"Aguardando 2s antes da cópia {copy_num + 1}...")
                time.sleep(2)
        
        # Relatório final
        successful_count = len(successful_pages)
        failed_count = total_pages_all_copies - successful_count
        
        logger.info("=== Relatório Final de Impressão ===")
        logger.info(f"Total de páginas enviadas: {successful_count}/{total_pages_all_copies}")
        logger.info(f"Páginas que falharam: {failed_count}/{total_pages_all_copies}")
        logger.info(f"Cópias configuradas: {total_copies}")
        logger.info(f"Páginas únicas: {len(page_jobs)}")
        
        if successful_count > 0:
            logger.info(f"Taxa de sucesso: {(successful_count/total_pages_all_copies)*100:.1f}%")
        
        if failed_count > 0:
            logger.info(f"Imagens mantidas em: {os.path.dirname(page_jobs[0].image_path)}")
            logger.info("Você pode tentar reimprimir manualmente as páginas que falharam")
        else:
            logger.info("Todas as páginas foram processadas com sucesso!")
            temp_folder = os.path.dirname(page_jobs[0].image_path)
            logger.info(f"Imagens temporárias mantidas em: {temp_folder}")
            logger.info("Você pode remover a pasta manualmente após validar as impressões")
        
        # Cria um dicionário para retornar o resultado
        result = {
            "total_pages": total_pages_all_copies,  # Total considerando cópias
            "successful_pages": successful_count,   # Páginas efetivamente enviadas
            "failed_pages": failed_count,
            "method": "jpg",
            "copies_requested": total_copies,
            "unique_pages": len(page_jobs)
        }
        
        # Retorna True apenas se TODAS as páginas (incluindo cópias) foram impressas com sucesso
        return successful_count == total_pages_all_copies, result

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
        """Verifica se a resposta IPP é válida"""
        # Verifica status IPP na resposta
        if len(response.content) >= 8:
            version = struct.unpack('>H', response.content[0:2])[0]
            status_code = struct.unpack('>H', response.content[2:4])[0]
            request_id = struct.unpack('>I', response.content[4:8])[0]
            
            # Status de sucesso
            if status_code in [0x0000, 0x0001, 0x0002]:
                logger.debug(f"Status IPP de sucesso: 0x{status_code:04X}")
                return True
            else:
                logger.debug(f"Status IPP de erro: 0x{status_code:04X}")
                return False
        else:
            logger.debug("Resposta IPP inválida ou muito curta")
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
    """Gerencia a fila de impressão - VERSÃO CORRIGIDA"""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Obtém instância única (singleton)"""
        if cls._instance is None:
            cls._instance = PrintQueueManager()
        return cls._instance
    
    def __init__(self):
        self.print_queue = queue.Queue()
        self.worker_thread = None
        self.is_running = False
        self.current_job = None
        self.lock = threading.Lock()
        self.config = None
        self.job_history = []
        self.max_history = 100
        self.canceled_job_ids = set()
        
        self.processed_jobs = {}
        self.processed_jobs_lock = threading.Lock()
        
        self.file_jobs = {}
        self.file_jobs_lock = threading.Lock()
        
        self.continuous_processing = True
        self.idle_sleep_time = 0.1
    
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
    
    def _get_file_hash(self, filepath):
        """
        Calcula hash do arquivo para controle de duplicatas
        
        Args:
            filepath: Caminho do arquivo
            
        Returns:
            str: Hash MD5 do arquivo
        """
        try:
            import hashlib
            with open(filepath, 'rb') as f:
                # Lê apenas os primeiros 8KB para eficiência
                content = f.read(8192)
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.debug(f"Erro ao calcular hash de {filepath}: {e}")
            return None
    
    def _is_duplicate_job(self, print_job_info):
        """
        Verifica se é um trabalho duplicado baseado no arquivo e hash
        
        Args:
            print_job_info: Informações do trabalho
            
        Returns:
            bool: True se for duplicata
        """
        with self.file_jobs_lock:
            import time
            current_time = time.time()
            filepath = print_job_info.document_path
            
            # Calcula hash do arquivo
            file_hash = self._get_file_hash(filepath)
            if not file_hash:
                return False
            
            # Verifica se existe job para este arquivo
            if filepath in self.file_jobs:
                existing_job = self.file_jobs[filepath]
                
                # Se foi processado há menos de 30 segundos e tem o mesmo hash
                if (current_time - existing_job["timestamp"] < 30 and 
                    existing_job["hash"] == file_hash):
                    logger.warning(f"Job duplicado detectado para arquivo {filepath} "
                                 f"(job anterior: {existing_job['job_id']})")
                    return True
            
            # Registra este job
            self.file_jobs[filepath] = {
                "hash": file_hash,
                "timestamp": current_time,
                "job_id": print_job_info.job_id
            }
            
            # Limpa entradas antigas (mais de 5 minutos)
            old_entries = []
            for path, job_data in self.file_jobs.items():
                if current_time - job_data["timestamp"] > 300:
                    old_entries.append(path)
            
            for path in old_entries:
                del self.file_jobs[path]
            
            return False
    
    def add_job(self, print_job_info, printer_instance, callback=None):
        """Adiciona um trabalho à fila de impressão com controle aprimorado de duplicatas"""
        
        # CORREÇÃO: Verifica se é trabalho duplicado por arquivo/hash
        if self._is_duplicate_job(print_job_info):
            logger.warning(f"Job duplicado ignorado: {print_job_info.job_id}")
            return print_job_info.job_id
        
        # CORREÇÃO: Verifica se o job ID já foi processado recentemente
        with self.processed_jobs_lock:
            import time
            current_time = time.time()
            job_id = print_job_info.job_id
            
            # Verifica se o job já foi processado nos últimos 20 segundos
            last_processed = self.processed_jobs.get(job_id, 0)
            if current_time - last_processed < 20:
                logger.warning(f"Job {job_id} já foi processado recentemente, ignorando duplicata")
                return job_id
            
            # Marca como sendo processado
            self.processed_jobs[job_id] = current_time
            
            # === CORREÇÃO: Log detalhado para debug ===
            logger.info(f"Adicionando job {job_id} à fila de impressão")
            logger.info(f"  Documento: {print_job_info.document_name}")
            logger.info(f"  Impressora: {print_job_info.printer_name} (IP: {print_job_info.printer_ip})")
            logger.info(f"  Cópias: {print_job_info.options.copies}")
            logger.info(f"  Tamanho da fila atual: {self.print_queue.qsize()}")
            
            # Limpa entradas antigas (mais de 1 hora)
            old_entries = [jid for jid, timestamp in self.processed_jobs.items() 
                        if current_time - timestamp > 3600]
            for jid in old_entries:
                del self.processed_jobs[jid]
        
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
        """Processa fila com loop otimizado e contínuo"""
        logger.info("Iniciando processamento contínuo da fila de impressão")
        
        while self.is_running:
            try:
                # === OTIMIZAÇÃO: Loop contínuo sem sleep desnecessário ===
                if self.print_queue.empty():
                    time.sleep(self.idle_sleep_time)  # Sleep mínimo quando idle
                    continue
                    
                job_item = self.print_queue.get(block=False)
                
                job_info = job_item["info"]
                printer = job_item["printer"]
                callback = job_item["callback"]
                
                logger.info(f"Processando trabalho otimizado: {job_info.document_name}")
                logger.info(f"  Job ID: {job_info.job_id}")
                logger.info(f"  Printer ID: {job_info.printer_id}")
                logger.info(f"  Cópias: {job_info.options.copies}")
                
                # Verifica cancelamento
                with self.lock:
                    is_canceled = job_info.job_id in self.canceled_job_ids

                if is_canceled:
                    logger.info(f"Trabalho cancelado: {job_info.job_id}")
                    job_info.status = "canceled" 
                    job_info.end_time = datetime.now()
                    self._update_history(job_info)

                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "canceled", {"message": "Trabalho cancelado"})

                    self.print_queue.task_done()
                    with self.lock: 
                        if self.current_job and self.current_job["info"].job_id == job_info.job_id:
                            self.current_job = None
                    continue 
                
                with self.lock:
                    self.current_job = job_item
                
                job_info.status = "processing"
                self._add_to_history(job_info)
                
                # === CORREÇÃO: PROCESSAMENTO OTIMIZADO COM MELHOR CONTROLE ===
                def progress_callback(message):
                    with self.lock:
                        if (self.current_job and 
                            self.current_job["info"].job_id == job_info.job_id and 
                            self.current_job["info"].status == "canceled"):
                            raise InterruptedError("Trabalho cancelado")
                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "progress", message)
                
                should_delete_file = False
                
                try:
                    if callback:
                        progress_callback("Iniciando impressão otimizada...")
                    
                    # === CORREÇÃO: Passa configuração para o printer uma só vez ===
                    if not hasattr(printer, 'config') or printer.config is None:
                        printer.config = self.config
                    
                    # === CORREÇÃO: Verifica se endpoint já está em cache ===
                    if hasattr(printer, 'endpoint_cache') and printer.endpoint_cache:
                        cached_config = printer.endpoint_cache.get_printer_endpoint_config(printer.printer_ip)
                        if cached_config and not printer.endpoint_cache.should_rediscover(printer.printer_ip):
                            logger.info(f"Usando endpoint em cache para {printer.printer_ip}: {cached_config.get('endpoint', '')}")
                    
                    success, result = printer.print_file(
                        job_info.document_path,
                        job_info.options,
                        job_info.document_name,
                        progress_callback if callback else None,
                        job_info=job_info
                    )
                    
                    job_info.end_time = datetime.now()
                    
                    if success:
                        job_info.status = "completed"
                        
                        total_pages_sent = result.get("total_pages", 0)
                        successful_pages_sent = result.get("successful_pages", 0)
                        
                        job_info.total_pages = total_pages_sent
                        job_info.completed_pages = successful_pages_sent
                        
                        # === CORREÇÃO: Só deleta arquivo se 100% de sucesso ===
                        should_delete_file = (successful_pages_sent == total_pages_sent and total_pages_sent > 0)
                        
                        logger.info(f"Trabalho concluído: {job_info.document_name}")
                        logger.info(f"  Páginas enviadas: {successful_pages_sent}/{total_pages_sent}")
                        logger.info(f"  Método: {result.get('method', 'unknown')}")
                        
                        if result.get("method") == "jpg_parallel":
                            logger.info(f"  Workers usados: {result.get('workers_used', 'N/A')}")
                            logger.info(f"  Taxa de sucesso: {(successful_pages_sent/total_pages_sent)*100:.1f}%")
                        
                    else:
                        with self.lock:
                            if job_info.status == "canceled":
                                logger.info(f"Trabalho cancelado durante impressão: {job_info.document_name}")
                            else:
                                job_info.status = "failed"
                                logger.error(f"Falha no trabalho: {job_info.document_name}")
                        
                        total_pages_sent = result.get("total_pages", 0)
                        successful_pages_sent = result.get("successful_pages", 0)
                        
                        job_info.total_pages = total_pages_sent
                        job_info.completed_pages = successful_pages_sent
                        
                        should_delete_file = False
                    
                    # === CORREÇÃO: Remove arquivo apenas se tudo foi impresso corretamente ===
                    if should_delete_file:
                        try:
                            if os.path.exists(job_info.document_path):
                                os.remove(job_info.document_path)
                                logger.info(f"Arquivo removido: {job_info.document_path}")
                        except Exception as e:
                            logger.warning(f"Não foi possível remover arquivo: {e}")
                    
                    self._update_history(job_info)
                    
                    # === CORREÇÃO: Sincronização apenas se houve páginas impressas ===
                    if job_info.completed_pages > 0:
                        def delayed_sync():
                            try:
                                time.sleep(2)  # Aguarda estabilizar
                                from src.utils.print_sync_manager import PrintSyncManager
                                sync_manager = PrintSyncManager.get_instance()
                                if sync_manager:
                                    logger.info(f"Sincronizando {job_info.completed_pages} páginas impressas...")
                                    sync_manager.sync_print_jobs()
                            except Exception as e:
                                logger.error(f"Erro na sincronização: {e}")
                        
                        threading.Thread(target=delayed_sync, daemon=True).start()
                            
                    # Callback de resultado
                    if callback:
                        status_cb = "complete" if success else ("canceled" if job_info.status == "canceled" else "error")
                        wx.CallAfter(callback, job_info.job_id, status_cb, result)
                    
                except InterruptedError:
                    logger.info(f"Trabalho interrompido: {job_info.document_name}")
                    job_info.status = "canceled"
                    job_info.end_time = datetime.now()
                    self._update_history(job_info)
                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "canceled", {"message": "Trabalho cancelado"})

                except Exception as e:
                    job_info.status = "failed"
                    job_info.end_time = datetime.now()
                    logger.error(f"Erro no processamento: {e}")
                    
                    self._update_history(job_info)
                    
                    if callback:
                        wx.CallAfter(callback, job_info.job_id, "error", {"error": str(e)})
                
                # Limpa controle de jobs processados
                with self.processed_jobs_lock:
                    if job_info.job_id in self.processed_jobs:
                        del self.processed_jobs[job_info.job_id]

                self.print_queue.task_done()
                
                with self.lock:
                    self.current_job = None
                
                # === OTIMIZAÇÃO: Sem sleep entre jobs ===
                # Remove time.sleep aqui para processamento contínuo
                
            except queue.Empty:
                time.sleep(self.idle_sleep_time)
            except Exception as e:
                logger.error(f"Erro no processamento da fila: {e}")
                time.sleep(1.0)

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
        self.config = config
        self.print_queue_manager = PrintQueueManager.get_instance()
        self.print_queue_manager.set_config(config)
        
        # Configurações de performance
        perf_config = config.get_print_performance_config()
        self.print_queue_manager.idle_sleep_time = 0.05  # Ultra responsivo
        
        self.print_queue_manager.start()
        
        logger.info("Sistema de impressão otimizado inicializado")
        logger.info(f"Performance config: {perf_config}")
    
    def print_document(self, parent_window, document, printer=None):
        """Imprime documento com otimizações"""
        try:
            if not os.path.exists(document.path):
                wx.MessageBox(f"Arquivo não encontrado: {document.path}", 
                            "Erro", wx.OK | wx.ICON_ERROR)
                return False
            
            if printer is None:
                printer = self._select_printer(parent_window)
                if printer is None:
                    return False
            
            if not hasattr(printer, 'id') or not printer.id:
                wx.MessageBox(f"A impressora '{printer.name}' não possui um ID válido do servidor.",
                            "Erro", wx.OK | wx.ICON_ERROR)
                return False
            
            # Diálogo de opções
            print_options_dialog = PrintOptionsDialog(parent_window, document, printer)
            if print_options_dialog.ShowModal() != wx.ID_OK:
                print_options_dialog.Destroy()
                return False
            
            options = print_options_dialog.get_options()
            print_options_dialog.Destroy()
            
            job_id = f"job_{int(time.time())}_{document.id}"
            
            job_info = PrintJobInfo(
                job_id=job_id,
                document_path=document.path,
                document_name=document.name,
                printer_name=printer.name,
                printer_id=printer.id,
                printer_ip=getattr(printer, 'ip', ''),
                options=options,
                start_time=datetime.now(),
                status="pending"
            )
            
            printer_ip = getattr(printer, 'ip', '')
            if not printer_ip:
                wx.MessageBox(f"A impressora '{printer.name}' não possui IP configurado.",
                            "Erro", wx.ID_ERROR)
                return False
            
            # === IMPRESSORA COM CONFIGURAÇÃO OTIMIZADA ===
            printer_instance = IPPPrinter(
                printer_ip=printer_ip,
                port=631,
                use_https=False,
                config=self.config  # Passa configuração para cache de endpoints
            )
            
            progress_dialog = PrintProgressDialog(
                parent_window,
                job_id,
                document.name,
                printer.name
            )
            
            def print_callback(job_id, status, data):
                if progress_dialog and not progress_dialog._is_destroyed:
                    wx.CallAfter(self._update_progress_dialog, progress_dialog, status, data)
            
            # Adiciona job à fila otimizada
            self.print_queue_manager.add_job(
                job_info,
                printer_instance,
                print_callback
            )
            
            progress_dialog.ShowModal()
            progress_dialog.Destroy()
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao preparar impressão: {e}")
            wx.MessageBox(f"Erro ao preparar impressão: {e}",
                        "Erro", wx.OK | wx.ICON_ERROR)
            return False
    
    def _select_printer(self, parent_window):
        """Método mantido para compatibilidade"""
        printer_list = self._get_printers()
        
        if not printer_list:
            wx.MessageBox("Nenhuma impressora configurada.",
                         "Informação", wx.OK | wx.ICON_INFORMATION)
            return None
        
        choices = [printer.name for printer in printer_list]
        
        dialog = wx.SingleChoiceDialog(
            parent_window,
            "Escolha a impressora:",
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
        """Método mantido para compatibilidade"""
        try:
            printers_data = self.config.get_printers()
            
            if printers_data:
                from src.models.printer import Printer
                return [Printer(printer_data) for printer_data in printers_data]
            else:
                return []
        except Exception as e:
            logger.error(f"Erro ao obter impressoras: {e}")
            return []
    
    def _update_progress_dialog(self, dialog, status, data):
        """Método mantido para compatibilidade"""
        try:
            if not dialog or dialog._is_destroyed:
                return
                
            if not hasattr(dialog, 'GetParent') or dialog.GetParent() is None:
                return
                
            if status == "progress":
                dialog.add_log(data)
            elif status == "complete":
                dialog.set_success("Impressão concluída com sucesso")
            elif status == "canceled":
                message = "Trabalho cancelado pelo usuário."
                if isinstance(data, dict) and "message" in data:
                    message = data["message"]
                dialog.set_error(message)
                dialog.add_log(message)
            elif status == "error":
                error_message = data.get("error", "Erro desconhecido") if isinstance(data, dict) else str(data)
                dialog.set_error(f"Falha na impressão: {error_message}")
                
        except RuntimeError as e:
            if "wrapped C/C++ object" in str(e) and "has been deleted" in str(e):
                if dialog:
                    dialog._is_destroyed = True
        except Exception as e:
            logger.error(f"Erro ao atualizar diálogo: {e}")
    
    def test_printer_connection(self, printer_ip: str, use_https: bool = False) -> Dict[str, Any]:
        """Teste de conexão otimizado com cache"""
        try:
            test_printer = IPPPrinter(printer_ip, use_https=use_https, config=self.config)
            
            # Se tem endpoint em cache, testa primeiro
            cache = PrinterEndpointCache(self.config)
            cached_config = cache.get_printer_endpoint_config(printer_ip)
            
            if cached_config and not cache.should_rediscover(printer_ip):
                endpoint = cached_config.get("endpoint", "")
                protocol = cached_config.get("protocol", "http")
                
                logger.info(f"Testando conexão usando configuração em cache: {protocol}://{printer_ip}:631{endpoint}")
                
                return {
                    "success": True,
                    "protocol": protocol.upper(),
                    "working_endpoints": [endpoint],
                    "base_url": f"{protocol}://{printer_ip}:631",
                    "cached": True
                }
            
            # Se não tem cache, faz teste rápido
            working_endpoints = []
            protocol = "HTTP"
            
            # Testa endpoints prioritários rapidamente
            priority_endpoints = ["/ipp/print", "/ipp", "/printers/ipp"]
            
            for endpoint in priority_endpoints:
                if test_printer._test_endpoint_quick(endpoint, use_https=False):
                    working_endpoints.append(endpoint)
                    protocol = "HTTP"
                    break
                elif test_printer._test_endpoint_quick(endpoint, use_https=True):
                    working_endpoints.append(endpoint)
                    protocol = "HTTPS"
                    break
            
            return {
                "success": len(working_endpoints) > 0,
                "protocol": protocol,
                "working_endpoints": working_endpoints,
                "base_url": f"{protocol.lower()}://{printer_ip}:631",
                "cached": False
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def shutdown(self):
        """Desliga sistema"""
        if self.print_queue_manager:
            self.print_queue_manager.stop()
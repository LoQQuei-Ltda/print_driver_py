#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sistema de impressão IPP para arquivos PDF integrado ao sistema de gerenciamento
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

logger = logging.getLogger("PrintManagementSystem.Utils.PrintSystem")

# Instalação automática de dependências
def install_package(package):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package], 
                             stdout=subprocess.PIPE, 
                             stderr=subprocess.PIPE)
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
class PopplerManager:
    @staticmethod
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
                os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "poppler", "bin"),
                r"C:\Program Files\poppler\library\bin",
                r"C:\poppler\library\bin",
            ]
            
            for path in possible_paths:
                if os.path.exists(os.path.join(path, "pdftoppm.exe")):
                    return path
            
            return None
        
        # Para Linux/Mac, geralmente está no PATH
        return None

    @staticmethod
    def install_poppler_windows():
        """Instala Poppler no Windows automaticamente"""
        logger.info("Instalando Poppler para Windows...")
        
        try:
            # URL do Poppler para Windows (versão portável)
            poppler_url = "https://github.com/oschwartz10612/poppler-windows/releases/download/v23.08.0-0/Release-23.08.0-0.zip"
            
            # Pasta de destino
            script_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            poppler_dir = os.path.join(script_dir, "poppler")
            zip_path = os.path.join(script_dir, "poppler.zip")
            
            # Remove instalação anterior se existir
            if os.path.exists(poppler_dir):
                shutil.rmtree(poppler_dir)
            
            logger.info("Baixando Poppler...")
            urllib.request.urlretrieve(poppler_url, zip_path)
            
            logger.info("Extraindo arquivos...")
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
                logger.info(f"Poppler instalado com sucesso em: {bin_path}")
                return bin_path
            else:
                logger.error("Erro na instalação do Poppler")
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
            
            logger.error("Poppler não encontrado.")
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

class IPPPrinter:
    """Classe principal para impressão de arquivos PDF via IPP"""
    
    def __init__(self, printer_ip: str, port: int = 631, use_https: bool = False):
        # Verifica dependências
        if not check_dependencies():
            raise ImportError("Falha ao verificar/instalar dependências para impressão")
            
        # Importa após verificação
        global requests
        import requests
        
        self.printer_ip = printer_ip
        self.port = port
        self.use_https = use_https
        self.protocol = "https" if use_https else "http"
        self.base_url = f"{self.protocol}://{printer_ip}:{port}"
        self.request_id = 1
        
    def print_file(self, file_path: str, options: PrintOptions, 
                   job_name: Optional[str] = None, progress_callback=None) -> Tuple[bool, Dict]:
        """Imprime um arquivo PDF com fallback automático para JPG
        
        Args:
            file_path: Caminho do arquivo PDF
            options: Opções de impressão
            job_name: Nome do trabalho de impressão
            progress_callback: Callback para atualização de progresso
            
        Returns:
            Tuple[bool, Dict]: Sucesso e informações detalhadas do trabalho
        """
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
            
        pdf_result = self._print_as_pdf(pdf_data, job_name, options)
        if pdf_result[0]:
            logger.info("Impressão PDF enviada com sucesso!")
            if progress_callback:
                progress_callback("Impressão PDF enviada com sucesso!")
            return True, pdf_result[1]
        
        # Segunda tentativa: converter para JPG e enviar
        logger.info("Tentativa 2: Convertendo para JPG e enviando")
        if progress_callback:
            progress_callback("Tentativa 2: Convertendo para JPG e enviando...")
            
        jpg_result = self._convert_and_print_as_jpg(file_path, job_name, options, progress_callback)
        if jpg_result[0]:
            logger.info("Impressão JPG enviada com sucesso!")
            if progress_callback:
                progress_callback("Impressão JPG enviada com sucesso!")
            return True, jpg_result[1]
        
        logger.error("Ambas as tentativas falharam")
        if progress_callback:
            progress_callback("Falha: Ambas as tentativas de impressão falharam")
        return False, {"error": "Ambas as tentativas de impressão falharam", 
                     "pdf_error": pdf_result[1].get("error", ""),
                     "jpg_error": jpg_result[1].get("error", "")}
    
    def _print_as_pdf(self, pdf_data: bytes, job_name: str, options: PrintOptions) -> Tuple[bool, Dict]:
        """Tenta imprimir como PDF"""
        
        endpoints = ["/ipp/print", "/ipp", "/printers/ipp", "/printers", ""]
        result_info = {"method": "pdf"}
        
        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"Testando endpoint: {url}")
            
            # Atributos IPP para PDF
            attributes = {
                "printer-uri": url,
                "requesting-user-name": os.getenv("USER", "usuario"),
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
            ipp_result = self._send_ipp_request(url, attributes, pdf_data)
            if ipp_result[0]:
                result_info.update(ipp_result[1])
                return True, result_info
        
        result_info["error"] = "Falha ao imprimir arquivo PDF em todos os endpoints"
        return False, result_info
    
    def _create_temp_folder(self, base_name: str) -> str:
        """Cria uma pasta temporária para salvar as imagens convertidas"""
        timestamp = int(time.time())
        temp_dir = os.path.join(tempfile.gettempdir(), f"pdf_to_jpg_{base_name}_{timestamp}")
        os.makedirs(temp_dir, exist_ok=True)
        return temp_dir

    def _convert_and_print_as_jpg(self, pdf_path: str, job_name: str, options: PrintOptions, 
                                progress_callback=None) -> Tuple[bool, Dict]:
        """Converte PDF para JPG e tenta imprimir com sistema de retry"""
        
        temp_folder = None
        result_info = {"method": "jpg"}
        
        try:
            logger.info("Convertendo PDF para JPG...")
            if progress_callback:
                progress_callback("Convertendo PDF para JPG...")
            
            # Importa após verificação de dependências
            import pdf2image
            from PIL import Image
            
            # Configura Poppler
            poppler_path = PopplerManager.setup_poppler()
            
            # Cria pasta temporária para salvar as imagens
            base_name = os.path.splitext(os.path.basename(pdf_path))[0]
            logger.info(f"Base do nome: {base_name}")
            temp_folder = self._create_temp_folder(base_name)
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
            
            if progress_callback:
                progress_callback("Processando páginas...")
                
            images = pdf2image.convert_from_path(**convert_kwargs)
            
            if not images:
                logger.error("Falha na conversão PDF para JPG")
                result_info["error"] = "Falha na conversão PDF para JPG"
                return False, result_info
            
            total_pages = len(images)
            logger.info(f"Convertido para {total_pages} página(s)")
            
            if progress_callback:
                progress_callback(f"Convertido para {total_pages} página(s)")
            
            # Prepara todas as páginas para impressão
            page_jobs = []
            
            for page_num, image in enumerate(images, 1):
                # Otimiza a imagem para impressão
                if options.color_mode == ColorMode.MONOCROMO:
                    image = image.convert('L')  # Converte para escala de cinza
                elif image.mode not in ['RGB', 'L']:
                    image = image.convert('RGB')
                
                # Define nome do arquivo
                if len(images) > 1:
                    image_filename = f"{base_name}_pagina_{page_num:02d}.jpg"
                    page_job_name = f"{job_name}_pagina_{page_num}"
                else:
                    image_filename = f"{base_name}.jpg"
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
                logger.info(f"Página {page_num} preparada: {image_filename} ({file_size:,} bytes)")
                
                if progress_callback and page_num % 5 == 0:
                    progress_callback(f"Preparada página {page_num}/{total_pages}")
            
            logger.info(f"Imagens salvas em: {temp_folder}")
            
            # Processa as páginas com sistema de retry
            process_result = self._process_pages_with_retry(page_jobs, options, progress_callback)
            result_info.update(process_result[1])
            result_info["temp_folder"] = temp_folder
            result_info["total_pages"] = total_pages
            
            return process_result[0], result_info
            
        except Exception as e:
            logger.error(f"Erro na conversão/preparação JPG: {e}")
            if temp_folder and os.path.exists(temp_folder):
                logger.info(f"Imagens parciais mantidas em: {temp_folder}")
                
            result_info["error"] = f"Erro na conversão/preparação JPG: {e}"
            result_info["temp_folder"] = temp_folder
            return False, result_info
    
    def _process_pages_with_retry(self, page_jobs: list, options: PrintOptions, 
                                progress_callback=None) -> Tuple[bool, Dict]:
        """Processa páginas com sistema de retry inteligente"""
        
        endpoints = ["/ipp/print", "/ipp", "/printers/ipp", "/printers", ""]
        successful_pages = []
        failed_pages = list(page_jobs)  # Copia inicial
        retry_delays = [2, 5, 10]  # Delays progressivos em segundos
        result_info = {}
        
        # Primeira passada - tenta todas as páginas
        total_pages = len(page_jobs)
        logger.info(f"Processando {total_pages} página(s)...")
        
        if progress_callback:
            progress_callback(f"Processando {total_pages} página(s)...")
        
        for attempt in range(max(p.max_attempts for p in page_jobs)):
            if not failed_pages:
                break
                
            current_failed = []
            
            for page_job in failed_pages:
                page_job.attempts += 1
                
                logger.info(f"Enviando página {page_job.page_num}/{total_pages} como JPG (tentativa {page_job.attempts}/{page_job.max_attempts})")
                
                if progress_callback:
                    progress_callback(f"Enviando página {page_job.page_num}/{total_pages} (tentativa {page_job.attempts})")
                
                # Tenta enviar esta página
                page_success = False
                
                for endpoint_idx, endpoint in enumerate(endpoints):
                    url = f"{self.base_url}{endpoint}"
                    
                    # Atributos IPP para JPG
                    attributes = {
                        "printer-uri": url,
                        "requesting-user-name": os.getenv("USER", "usuario"),
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
                    
                    ipp_result = self._send_ipp_request(url, attributes, page_job.jpg_data)
                    if ipp_result[0]:
                        page_success = True
                        break
                    
                    # Se falhou no primeiro endpoint, aguarda um pouco antes do próximo
                    if endpoint_idx == 0 and not page_success:
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
        successful_count = len(successful_pages)
        failed_count = total_pages - successful_count
        
        logger.info(f"Relatório de impressão:")
        logger.info(f"Páginas enviadas com sucesso: {successful_count}/{total_pages}")
        logger.info(f"Páginas que falharam: {failed_count}/{total_pages}")
        
        # Constrói informações de resultado
        result_info["successful_pages"] = successful_count
        result_info["failed_pages"] = failed_count
        result_info["total_pages"] = total_pages
        
        if successful_pages:
            result_info["successful_page_numbers"] = [p.page_num for p in successful_pages]
        
        remaining_failed = [p for p in page_jobs if p not in successful_pages]
        if remaining_failed:
            result_info["failed_page_numbers"] = [p.page_num for p in remaining_failed]
            result_info["error"] = f"Falha ao imprimir {failed_count} página(s)"
            return False, result_info
        else:
            return True, result_info

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
    
    def _send_ipp_request(self, url: str, attributes: Dict[str, Any], document_data: bytes) -> Tuple[bool, Dict]:
        """Envia requisição IPP e verifica se teve sucesso"""
        
        # Constrói requisição IPP
        ipp_request = self._build_ipp_request(IPPOperation.PRINT_JOB, attributes)
        ipp_request += document_data
        
        result_info = {}
        
        try:
            headers = {
                'Content-Type': 'application/ipp',
                'Accept': 'application/ipp',
                'Accept-Encoding': 'identity',
                'Connection': 'close',
                'User-Agent': 'PDF-IPP/1.1'
            }
            
            response = requests.post(
                url, 
                data=ipp_request, 
                headers=headers, 
                timeout=30, 
                verify=False,
                allow_redirects=False
            )
            
            http_status = response.status_code
            logger.info(f"HTTP Status: {http_status}")
            result_info["http_status"] = http_status
            
            # Verifica se HTTP foi 200
            if http_status != 200:
                result_info["error"] = f"HTTP status não é 200: {http_status}"
                return False, result_info
            
            # Verifica status IPP na resposta
            if len(response.content) >= 8:
                version = struct.unpack('>H', response.content[0:2])[0]
                status_code = struct.unpack('>H', response.content[2:4])[0]
                request_id = struct.unpack('>I', response.content[4:8])[0]
                
                logger.info(f"IPP Version: {version >> 8}.{version & 0xFF}")
                logger.info(f"IPP Status: 0x{status_code:04X}")
                
                result_info["ipp_version"] = f"{version >> 8}.{version & 0xFF}"
                result_info["ipp_status"] = f"0x{status_code:04X}"
                
                # Trata códigos de status
                if status_code == 0x0507:
                    result_info["error"] = "Erro IPP 0x0507: client-error-document-format-error (formato não suportado)"
                    return False, result_info
                elif status_code == 0x040A:
                    result_info["error"] = "Erro IPP 0x040A: client-error-gone (recurso não disponível)"
                    return False, result_info
                elif status_code == 0x0400:
                    result_info["error"] = "Erro IPP 0x0400: client-error-bad-request (requisição inválida)"
                    return False, result_info
                elif status_code == 0x0001:  # Status esperado
                    logger.info("Status IPP correto (0x0001)")
                    
                    job_id = self._extract_job_id_from_response(response.content)
                    if job_id:
                        logger.info(f"Job ID: {job_id}")
                        result_info["job_id"] = job_id
                    
                    return True, result_info
                elif status_code == 0x0000:  # Também aceitável
                    logger.info("Status IPP alternativo (0x0000)")
                    return True, result_info
                else:
                    result_info["error"] = f"Status IPP não reconhecido: 0x{status_code:04X}"
                    return False, result_info
            else:
                result_info["error"] = "Resposta IPP inválida"
                return False, result_info
                
        except requests.exceptions.Timeout:
            logger.error("Timeout")
            result_info["error"] = "Timeout na comunicação com a impressora"
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Conexão recusada: {e}")
            result_info["error"] = f"Conexão recusada: {e}"
        except Exception as e:
            logger.error(f"Erro: {e}")
            result_info["error"] = f"Erro: {e}"
        
        return False, result_info
    
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
        """Adiciona um trabalho à fila de impressão
        
        Args:
            print_job_info: Informações do trabalho
            printer_instance: Instância do IPPPrinter
            callback: Função de retorno de chamada para notificação
        """
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
                
                with self.lock:
                    self.current_job = job_item
                
                job_info = job_item["info"]
                printer = job_item["printer"]
                callback = job_item["callback"]
                
                logger.info(f"Processando trabalho: {job_info.document_name}")
                
                # Salva o trabalho no histórico antes de começar
                job_info.status = "processing"
                self._add_to_history(job_info)
                
                # Definir função de progresso
                def progress_callback(message):
                    if callback:
                        callback(job_info.job_id, "progress", message)
                
                # Tenta imprimir
                try:
                    progress_callback("Iniciando impressão...")
                    
                    success, result = printer.print_file(
                        job_info.document_path,
                        job_info.options,
                        job_info.document_name,
                        progress_callback
                    )
                    
                    # Atualiza informações do trabalho
                    job_info.end_time = datetime.now()
                    
                    if success:
                        job_info.status = "completed"
                        job_info.total_pages = result.get("total_pages", 0)
                        job_info.completed_pages = result.get("successful_pages", 0)
                        logger.info(f"Trabalho concluído com sucesso: {job_info.document_name}")
                        
                        # Extrai o ID do documento do caminho (se existir)
                        document_id = None
                        if hasattr(job_info, 'document_id'):
                            document_id = job_info.document_id
                        
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
                        job_info.status = "failed"
                        job_info.total_pages = result.get("total_pages", 0)
                        job_info.completed_pages = result.get("successful_pages", 0)
                        logger.error(f"Falha no trabalho: {job_info.document_name}")
                    
                    # Atualiza histórico
                    self._update_history(job_info)
                    
                    # Notifica o callback
                    if callback:
                        callback(job_info.job_id, "complete" if success else "error", result)
                    
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
        
        # Centraliza o diálogo
        self.CenterOnParent()
    
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
        """Adiciona uma mensagem ao log"""
        # Adiciona timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"
        
        # Adiciona ao controle de log
        self.log_ctrl.AppendText(log_message)
        
        # Atualiza o status
        self.status_text.SetLabel(message)
        
        # Incrementa a barra de progresso
        current = self.gauge.GetValue()
        if current < 95:  # Deixa um espaço para o final
            self.gauge.SetValue(current + 5)
    
    def set_success(self, message="Impressão concluída com sucesso"):
        """Define o status como sucesso"""
        self.status_text.SetLabel(message)
        self.status_text.SetForegroundColour(self.colors["success_color"])
        self.gauge.SetValue(100)
        self.close_button.Enable()
        self.close_button.SetFocus()
        
        # Adiciona ao log
        self.add_log(message)
    
    def set_error(self, message="Falha na impressão"):
        """Define o status como erro"""
        self.status_text.SetLabel(message)
        self.status_text.SetForegroundColour(self.colors["error_color"])
        self.gauge.SetValue(100)
        self.close_button.Enable()
        self.close_button.SetFocus()
        
        # Adiciona ao log
        self.add_log(f"ERRO: {message}")
    
    def on_close(self, event):
        """Manipula o evento de fechar"""
        self.EndModal(wx.ID_CLOSE)

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
            
            # Cria instância da impressora
            printer_ip = getattr(printer, 'ip', '')
            if not printer_ip:
                wx.MessageBox(f"A impressora '{printer.name}' não possui um endereço IP configurado.",
                            "Erro", wx.ID_ERROR)
                return False
            
            printer_instance = IPPPrinter(
                printer_ip=printer_ip,
                port=631
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
        """Atualiza o diálogo de progresso"""
        if status == "progress":
            # Mensagem de progresso
            dialog.add_log(data)
        elif status == "complete":
            # Trabalho concluído com sucesso
            dialog.set_success("Impressão concluída com sucesso")
        elif status == "error":
            # Erro no trabalho
            error_message = data.get("error", "Erro desconhecido")
            dialog.set_error(f"Falha na impressão: {error_message}")
    
    def shutdown(self):
        """Desliga o sistema de impressão"""
        if self.print_queue_manager:
            self.print_queue_manager.stop()
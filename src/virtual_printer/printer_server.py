#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servidor de impressora virtual cross-platform
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
        self.ghostscript_path = None
        
        # Diretório de saída baseado na configuração
        self.output_dir = config.pdf_dir
        
        # Criar diretório de saída
        Path(self.output_dir).mkdir(parents=True, exist_ok=True)
        logger.info(f"Diretório para PDFs: {self.output_dir}")
        
        # Verificar e instalar Ghostscript
        self._init_ghostscript()
    
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
    
    def _find_ghostscript_unix(self):
        """Busca Ghostscript em sistemas Unix (Linux/macOS)"""
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
            '/opt/local/bin/gs',
            '/usr/local/Cellar/ghostscript/*/bin/gs'
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
                process = subprocess.Popen(
                    [path, '--help'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True
                )
                stdout, stderr = process.communicate(timeout=5)
                return "PCL" in stdout or "PCL" in stderr or "Ghostscript" in stdout
            else:
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
        
        machine = platform.machine().lower()
        if 'x86_64' in machine or 'amd64' in machine:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostscript-10.0.0-linux-x86_64.tgz"
        else:
            gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostscript-10.0.0-linux-x86.tgz"
        
        return self._download_and_install_ghostscript_unix(gs_url, 'gs')
    
    def _install_ghostscript_macos(self):
        """Instala Ghostscript no macOS"""
        try:
            subprocess.run(['which', 'brew'], check=True, capture_output=True)
            logger.info("Homebrew encontrado, tentando instalar Ghostscript...")
            result = subprocess.run(['brew', 'install', 'ghostscript'], capture_output=True)
            if result.returncode == 0:
                gs_path = subprocess.run(['which', 'gs'], capture_output=True, text=True)
                if gs_path.returncode == 0:
                    return gs_path.stdout.strip()
        except:
            pass
        
        gs_url = "https://github.com/ArtifexSoftware/ghostpdl-downloads/releases/download/gs1000/ghostscript-10.0.0-linux-x86_64.tgz"
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
            process = subprocess.Popen(
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
    
    def _decode_with_multiple_encodings(self, data):
        """Tenta decodificar dados com múltiplos encodings"""
        encodings = [
            'utf-8',           # UTF-8 (padrão)
            'utf-16',          # UTF-16 (Windows Unicode)
            'utf-16-le',       # UTF-16 Little Endian
            'utf-16-be',       # UTF-16 Big Endian
            'latin1',          # ISO-8859-1 (Western Europe)
            'cp1252',          # Windows-1252 (Western Europe)
            'cp1251',          # Windows-1251 (Cyrillic)
            'cp1250',          # Windows-1250 (Central Europe)
            'iso-8859-15',     # ISO-8859-15 (Western Europe with Euro)
            'ascii',           # ASCII básico
        ]
        
        # Se os dados são muito pequenos, tenta como string
        if len(data) < 20:
            try:
                return data.decode('utf-8', errors='replace')
            except:
                return str(data)
        
        # Detecta BOM (Byte Order Mark) para UTF
        if data.startswith(b'\xff\xfe'):
            # UTF-16 LE BOM
            try:
                return data[2:].decode('utf-16-le', errors='replace')
            except:
                pass
        elif data.startswith(b'\xfe\xff'):
            # UTF-16 BE BOM
            try:
                return data[2:].decode('utf-16-be', errors='replace')
            except:
                pass
        elif data.startswith(b'\xef\xbb\xbf'):
            # UTF-8 BOM
            try:
                return data[3:].decode('utf-8', errors='replace')
            except:
                pass
        
        # Tenta cada encoding
        for encoding in encodings:
            try:
                decoded = data.decode(encoding, errors='strict')
                # Verifica se a decodificação faz sentido (não há muitos caracteres de controle)
                if self._is_reasonable_text(decoded):
                    logger.debug(f"Decodificado com sucesso usando {encoding}")
                    return decoded
            except (UnicodeDecodeError, LookupError):
                continue
        
        # Se nada funcionou, usa UTF-8 com substituição de erros
        logger.warning("Nenhum encoding funcionou perfeitamente, usando UTF-8 com substituições")
        return data.decode('utf-8', errors='replace')
    
    def _is_reasonable_text(self, text):
        """Verifica se o texto decodificado é razoável"""
        if not text:
            return False
        
        # Conta caracteres de controle (exceto whitespace comum)
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\t\n\r ')
        
        # Se mais de 5% são caracteres de controle, provavelmente é encoding errado
        return (control_chars / len(text)) < 0.05
    
    def _clean_filename(self, filename):
        """Limpa e normaliza o nome do arquivo mantendo caracteres especiais permitidos"""
        if not filename:
            return None
        
        # Remove espaços extras
        filename = filename.strip()
        
        # Normaliza caracteres Unicode (mantém acentos e caracteres especiais)
        filename = unicodedata.normalize('NFC', filename)
        
        # Caracteres permitidos: letras (incluindo acentuadas), números, espaços e símbolos especiais
        # Baseado na lista fornecida: "áàâãäéèêëíìîïóòôõöúùûüçñÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ!#$%&'()-@^_`{}~,;=+[]ªº°ßØøÆæœ¿¡¬¨§¶µ✓✔★☆♫♯♻☼☺☻"
        allowed_chars = (
            'abcdefghijklmnopqrstuvwxyz'
            'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
            '0123456789'
            'áàâãäéèêëíìîïóòôõöúùûüçñ'
            'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ'
            '!#$%&\'()-@^_`{}~,;=+[]'
            'ªº°ßØøÆæœ¿¡¬¨§¶µ✓✔★☆♫♯♻☼☺☻'
            ' .'  # espaço e ponto
        )
        
        # Remove apenas caracteres realmente problemáticos para sistemas de arquivo
        # Mantém todos os caracteres da lista fornecida
        problematic_chars = '<>:"|?*\\/\x00'  # Caracteres que causam problemas em sistemas de arquivo
        
        cleaned = ''.join(c for c in filename if c not in problematic_chars)
        
        # Remove múltiplos espaços
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        # Remove espaços no início e fim
        cleaned = cleaned.strip()
        
        # Se ficou vazio, retorna None
        if not cleaned:
            return None
        
        # Limita o tamanho (sistemas de arquivo têm limites)
        max_length = 200  # Deixa espaço para extensão e sufixos
        if len(cleaned) > max_length:
            # Tenta preservar a extensão
            if '.' in cleaned:
                name_part, ext_part = cleaned.rsplit('.', 1)
                available_length = max_length - len(ext_part) - 1  # -1 para o ponto
                cleaned = name_part[:available_length] + '.' + ext_part
            else:
                cleaned = cleaned[:max_length]
        
        return cleaned
    
    def _extract_pdf_filename(self, data):
        """Extrai o nome do arquivo diretamente de dados PDF"""
        try:
            # Primeiro, tenta decodificar como texto
            pdf_text = self._decode_with_multiple_encodings(data)
            
            # Padrões para metadados PDF
            title_patterns = [
                # Padrões básicos
                r'/Title\s*\(([^)]+)\)',
                r'/Title\s*<([^>]+)>',
                r'/Filename\s*\(([^)]+)\)',
                r'/DocumentName\s*\(([^)]+)\)',
                r'/Subject\s*\(([^)]+)\)',
                
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
            
            for pattern in title_patterns:
                matches = re.findall(pattern, pdf_text, re.IGNORECASE | re.DOTALL)
                if matches:
                    for match in matches:
                        title = match.strip()
                        
                        # Se é hex string, converte
                        if re.match(r'^[0-9A-Fa-f]+$', title) and len(title) % 2 == 0:
                            try:
                                # Tenta UTF-16 BE primeiro (comum em PDFs)
                                if title.upper().startswith('FEFF'):
                                    hex_bytes = bytes.fromhex(title)
                                    title = hex_bytes[2:].decode('utf-16-be', errors='ignore')
                                else:
                                    hex_bytes = bytes.fromhex(title)
                                    title = hex_bytes.decode('utf-16-be', errors='ignore')
                                    if not title or len(title) < 3:
                                        title = hex_bytes.decode('utf-8', errors='ignore')
                            except:
                                continue
                        
                        # Remove caracteres de escape
                        title = title.replace('\\(', '(').replace('\\)', ')').replace('\\\\', '\\')
                        
                        # Se parece um nome de arquivo válido
                        if title and len(title) > 2 and not title.isspace():
                            print(f"Nome extraído do PDF (padrão {pattern}): {title}")
                            logger.info(f"Nome extraído do PDF (padrão {pattern}): {title}")
                            return title
            
            # Busca por nomes de arquivo com extensões conhecidas em qualquer lugar do PDF
            file_extensions = ['.pdf', '.txt', '.doc', '.xls', '.xlsx', '.docx', '.pptx', '.ppt', '.rtf', '.odt', '.ods']
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
        """Extrai o nome do arquivo do cabeçalho PS usando múltiplos métodos melhorados"""
        # Verifica se há cabeçalho antes do PostScript
        header_text = ps_text.split('%!PS-', 1)[0] if '%!PS-' in ps_text else ps_text[:3000]  # Aumentado ainda mais
        
        logger.debug("Analisando cabeçalho do trabalho...")
        logger.debug(f"Primeiros 500 caracteres do cabeçalho: {header_text[:500]}")
        
        filename = None
        
        # ----- PADRÕES MELHORADOS PARA MICROSOFT OFFICE -----
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
                    
                    # Se for um caminho, extrair apenas o nome do arquivo
                    if '\\' in value or '/' in value:
                        extracted_name = os.path.basename(value)
                    else:
                        extracted_name = value
                    
                    # Verifica se parece ser um nome de arquivo válido
                    if extracted_name and len(extracted_name) > 2:
                        # Aceita nomes com ou sem extensão
                        if '.' in extracted_name or len(extracted_name) > 5:
                            filename = extracted_name
                            logger.info(f"Nome de arquivo extraído (padrão {start_pattern}): {filename}")
                            break
        
        # ----- PADRÕES REGEX MELHORADOS -----
        if not filename:
            logger.debug("Tentando padrões regex melhorados...")
            
            regex_patterns = [
                # PostScript DSC comments
                r'%%Title:\s*(.+?)(?:\n|\r|$)',
                r'%%DocumentName:\s*(.+?)(?:\n|\r|$)',
                r'%%For:\s*(.+?)(?:\n|\r|$)',
                
                # PJL patterns sem aspas
                r'@PJL\s+SET\s+JOBNAME\s*=\s*([^\s\n\r]+)',
                r'@PJL\s+JOB\s+NAME\s*=\s*([^\s\n\r]+)',
                r'@PJL\s+SET\s+DOCNAME\s*=\s*([^\s\n\r]+)',
                
                # PostScript title/name
                r'/Title\s*\(([^)]+)\)',
                r'/DocumentName\s*\(([^)]+)\)',
                r'/Creator\s*\(([^)]+)\)',
                
                # Caminhos de arquivo em qualquer lugar
                r'[\\/]([^\\/\s"\'<>|*?:]{3,}\.[a-zA-Z]{2,4})(?=[\s\n\r"\'<>|*?:]|$)',
                
                # Nomes que parecem arquivos (com pelo menos uma extensão comum)
                r'\b([a-zA-ZÀ-ÿ0-9\s_\-!#$%&\'()\-@^`{}~,;=+\[\]]{3,}\.[a-zA-Z]{2,4})\b',
            ]
            
            for pattern in regex_patterns:
                matches = re.findall(pattern, ps_text, re.MULTILINE | re.UNICODE | re.IGNORECASE)
                if matches:
                    for match in matches:
                        value = match.strip()
                        
                        # Remove aspas se existirem
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        
                        logger.debug(f"Regex match encontrado: {value}")
                        
                        # Se for um caminho, extrair apenas o nome do arquivo
                        if '\\' in value or '/' in value:
                            extracted_name = os.path.basename(value)
                        else:
                            extracted_name = value
                        
                        # Verifica se é um nome válido
                        if extracted_name and len(extracted_name) > 2:
                            # Filtra nomes que são claramente inválidos
                            invalid_names = ['microsoft', 'windows', 'system', 'temp', 'tmp', 'default']
                            if extracted_name.lower() not in invalid_names:
                                filename = extracted_name
                                logger.info(f"Nome de arquivo extraído por regex: {filename}")
                                break
                
                if filename:
                    break
        
        # ----- BUSCA POR QUALQUER EXTENSÃO CONHECIDA -----
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
                        if len(match) > len(ext) + 1 and not match.startswith('.'):
                            # Pontuação: prefer nomes mais longos e com caracteres "normais"
                            score = len(match)
                            if any(c.isalpha() for c in match):
                                score += 10
                            if any(c.isdigit() for c in match):
                                score += 5
                            valid_matches.append((score, match))
                    
                    if valid_matches:
                        # Pega o match com maior pontuação
                        valid_matches.sort(reverse=True)
                        filename = valid_matches[0][1]
                        logger.info(f"Nome de arquivo extraído por extensão ({ext}): {filename}")
                        break
        
        # ----- BUSCA FINAL POR QUALQUER SEQUÊNCIA QUE PAREÇA NOME DE ARQUIVO -----
        if not filename:
            logger.debug("Tentativa final: busca por qualquer nome aparente...")
            
            # Busca por sequências que parecem nomes de arquivo
            # Aceita letras, números, espaços, e caracteres especiais da lista
            pattern = r'\b([a-zA-ZÀ-ÿ0-9][a-zA-ZÀ-ÿ0-9\s_\-!#$%&\'()\-@^`{}~,;=+\[\]ªº°ßØøÆæœ¿¡¬¨§¶µ✓✔★☆♫♯♻☼☺☻]{2,}\.[a-zA-Z]{2,4})\b'
            matches = re.findall(pattern, ps_text, re.UNICODE)
            
            if matches:
                # Filtra matches muito genéricos
                filtered_matches = []
                for match in matches:
                    match = match.strip()
                    # Evita nomes muito genéricos ou muito curtos
                    if len(match) > 6 and not any(generic in match.lower() for generic in 
                                                  ['default', 'temp', 'tmp', 'unnamed', 'document', 'file']):
                        filtered_matches.append(match)
                
                if filtered_matches:
                    filename = filtered_matches[0]  # Pega o primeiro válido
                    logger.info(f"Nome de arquivo da busca final: {filename}")
        
        return filename
    
    def _save_pdf(self, pdf_data, title=None, author=None, filename=None):
        """Salva os dados PDF em um arquivo"""
        if not pdf_data:
            logger.error("Nenhum dado PDF para salvar.")
            return None
        
        # Determinar nome do arquivo
        if filename:
            base_name = filename
        elif title:
            base_name = title
        else:
            data_br = time.strftime('%d-%m-%Y')
            hora_br = time.strftime('%H-%M-%S')
            base_name = f"sem_titulo_{data_br}_{hora_br}"
        
        # Limpa o nome do arquivo (usando a nova função de limpeza)
        base_name = self._clean_filename(base_name) or f"documento_{time.strftime('%d-%m-%Y_%H-%M-%S')}"
        
        # Garante extensão .pdf
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
                        if e.errno != 10035:  # WSAEWOULDBLOCK no Windows
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
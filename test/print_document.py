#!/usr/bin/env python3
"""
Sistema simplificado de impressão IPP com suporte a opções de impressão
"""

import os
import sys
import argparse
import subprocess
from typing import Dict, Optional, Union
from dataclasses import dataclass
from enum import Enum

# Tenta importar bibliotecas necessárias
try:
    import requests
except ImportError:
    print("Instalando dependências necessárias...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

try:
    from pyipp import IPP
except ImportError:
    print("Instalando python-ipp...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyipp"])
    from pyipp import IPP


class ColorMode(Enum):
    """Modos de cor disponíveis"""
    MONOCROMO = "monochrome"
    COLORIDO = "color"
    AUTO = "auto"


class Duplex(Enum):
    """Modos de impressão duplex (frente e verso)"""
    SIMPLES = "one-sided"
    DUPLEX_LONGO = "two-sided-long-edge"  # Virar na borda longa
    DUPLEX_CURTO = "two-sided-short-edge"  # Virar na borda curta


class MediaType(Enum):
    """Tipos de mídia/papel"""
    NORMAL = "stationery"
    FOTOGRAFICO = "photographic"
    TRANSPARENCIA = "transparency"
    ENVELOPE = "envelope"
    CARTAO = "cardstock"
    RECICLADO = "recycled"
    GLOSSY = "glossy"
    MATTE = "matte"


class Quality(Enum):
    """Qualidade de impressão"""
    RASCUNHO = 3
    NORMAL = 4
    ALTA = 5


@dataclass
class PrintOptions:
    """Opções de impressão"""
    color_mode: ColorMode = ColorMode.AUTO
    duplex: Duplex = Duplex.SIMPLES
    media_type: MediaType = MediaType.NORMAL
    quality: Quality = Quality.NORMAL
    copies: int = 1
    collate: bool = True
    orientation: str = "portrait"  # portrait ou landscape
    page_ranges: Optional[str] = None  # ex: "1-5,7,9-12"
    fit_to_page: bool = False
    paper_size: str = "iso_a4_210x297mm"  # A4 padrão


class SimplePrinter:
    """Classe simplificada para impressão IPP"""
    
    def __init__(self, printer_ip: str, port: int = 631):
        self.printer_ip = printer_ip
        self.port = port
        self.base_url = f"ipp://{printer_ip}:{port}"
        
    def print_file(self, file_path: str, options: PrintOptions, job_name: Optional[str] = None) -> bool:
        """
        Imprime um arquivo com as opções especificadas
        """
        if not os.path.exists(file_path):
            print(f"Erro: Arquivo não encontrado: {file_path}")
            return False
            
        if job_name is None:
            job_name = os.path.basename(file_path)
            
        print(f"\n📄 Preparando impressão de: {job_name}")
        print(f"🖨️  Impressora: {self.printer_ip}:{self.port}")
        
        if file_path.lower().endswith(".pdf"):
            ps_path = self.convert_pdf_to_ps(file_path)
            if ps_path:
                print(f"📄 PDF convertido para PostScript: {ps_path}")
                file_path = ps_path
            else:
                print("❌ Falha na conversão de PDF para PS")
                return False
            
        # Detecta o tipo de arquivo
        file_extension = os.path.splitext(file_path)[1].lower()
        document_format = self._get_document_format(file_extension)
        
        # Monta os atributos IPP
        ipp_attributes = self._build_ipp_attributes(options, job_name, document_format)
        
        
        # Lê o arquivo
        try:
            with open(file_path, 'rb') as f:
                document_data = f.read()
        except Exception as e:
            print(f"Erro ao ler arquivo: {e}")
            return False
            
        # Tenta diferentes endpoints IPP
        endpoints = ["/ipp/print", "/ipp", "/ipp/printer", "/printers/.printer"]
        
        for endpoint in endpoints:
            url = f"https://{self.printer_ip}:{self.port}{endpoint}"
            print(f"\n🔄 Tentando endpoint: {url}")
            
            if self._send_print_job(url, ipp_attributes, document_data):
                return True
                
        print("\n❌ Todas as tentativas de impressão falharam")
        return False
        
    def _get_document_format(self, extension: str) -> str:
        """Retorna o MIME type baseado na extensão do arquivo"""
        if extension == ".ps":
            return "application/postscript"

        formats = {
            '.pdf': 'application/pdf',
            '.ps': 'application/postscript',
            '.txt': 'text/plain',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.tiff': 'image/tiff',
            '.html': 'text/html',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',

        }
        return formats.get(extension, 'application/octet-stream')
        
    def _build_ipp_attributes(self, options: PrintOptions, job_name: str, document_format: str) -> Dict:
        """Constrói os atributos IPP para o trabalho de impressão"""
        attributes = {
            # Atributos obrigatórios
            "attributes-charset": "utf-8",
            "attributes-natural-language": "pt-br",
            "printer-uri": f"{self.base_url}/ipp/print",
            "requesting-user-name": os.getenv("USER", "usuario"),
            "job-name": job_name,
            "document-format": document_format,
            
            # Número de cópias
            "copies": options.copies,
            "multiple-document-handling": "separate-documents-collated-copies" if options.collate else "separate-documents-uncollated-copies",
            
            # Orientação
            "orientation-requested": 3 if options.orientation == "portrait" else 4,
            
            # Qualidade
            "print-quality": options.quality.value,
            
            # Tamanho do papel
            "media": options.paper_size,
            "media-type": options.media_type.value,
        }
        
        # Modo de cor
        if options.color_mode != ColorMode.AUTO:
            attributes["print-color-mode"] = options.color_mode.value
            
        # Duplex
        if options.duplex != Duplex.SIMPLES:
            attributes["sides"] = options.duplex.value
            
        # Intervalo de páginas
        if options.page_ranges:
            attributes["page-ranges"] = options.page_ranges
            
        # Ajustar à página
        if options.fit_to_page:
            attributes["fit-to-page"] = True
            
        return attributes
        
    def _send_print_job(self, url: str, attributes: Dict, document_data: bytes) -> bool:
        """Envia o trabalho de impressão via IPP"""
        try:
            # Usa a biblioteca pyipp se disponível
            try:
                from pyipp import IPP
                ipp = IPP(url, debug=True)
                response = ipp.print_job(
                    document=document_data,
                    document_name=attributes.get("job-name", "documento"),
                    document_format=attributes.get("document-format", "application/pdf")
                )
                print("✅ Documento enviado com sucesso via pyipp!")
                return True
            except:
                # Fallback para requisição manual
                return self._manual_ipp_request(url, attributes, document_data)
                
        except Exception as e:
            print(f"❌ Erro ao enviar: {e}")
            return False
            
    def _manual_ipp_request(self, url: str, attributes: Dict, document_data: bytes) -> bool:
        """Envia requisição IPP manualmente"""
        import struct
        
        # Constrói pacote IPP básico
        version = struct.pack('>bb', 1, 1)  # IPP 1.1
        operation = struct.pack('>h', 0x0002)  # Print-Job
        request_id = struct.pack('>i', 1)
        
        packet = version + operation + request_id
        packet += struct.pack('>b', 1)  # Operation attributes tag
        
        # Adiciona atributos básicos
        for name, value in attributes.items():
            if isinstance(value, str):
                packet += struct.pack('>b', 0x45)  # Text with language
                packet += struct.pack('>h', len(name)) + name.encode('utf-8')
                packet += struct.pack('>h', len(value)) + value.encode('utf-8')
            elif isinstance(value, int):
                packet += struct.pack('>b', 0x21)  # Integer
                packet += struct.pack('>h', len(name)) + name.encode('utf-8')
                packet += struct.pack('>h', 4) + struct.pack('>i', value)
                
        packet += struct.pack('>b', 3)  # End of attributes
        packet += document_data
        
        # Envia requisição
        headers = {'Content-Type': 'application/ipp'}
        response = requests.post(url, data=packet, headers=headers, timeout=10, verify=False)
        
        if response.status_code < 300:
            print("✅ Documento enviado com sucesso!")
            return True
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            return False
    
    def convert_pdf_to_ps(self, pdf_path: str) -> Optional[str]:
        """
        Converte um arquivo PDF para PostScript (.ps) usando o Ghostscript.
        Retorna o caminho do arquivo .ps ou None em caso de erro.
        """
        import subprocess
        import os

        if not pdf_path.lower().endswith(".pdf"):
            return None

        ps_path = pdf_path[:-4] + ".ps"

        try:
            subprocess.check_call([
                "gs\\gpcl6win64.exe",
                "-dNOPAUSE",
                "-dBATCH",
                "-sDEVICE=ps2write",
                "-sDEVICE=ps2write",
                f"-sOutputFile={ps_path}",
                pdf_path
            ])
            return ps_path
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao converter PDF para PS com Ghostscript: {e}")
            return None

    def _try_raw_print(self, document_data: bytes) -> bool:
        """Tenta impressão RAW na porta 9100"""
        import socket
        
        print("\n🔄 Tentando impressão RAW na porta 9100...")
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.printer_ip, 9100))
            sock.sendall(document_data)
            sock.close()
            print("✅ Documento enviado via RAW!")
            return True
        except Exception as e:
            print(f"❌ Erro RAW: {e}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description='Sistema de impressão IPP com opções avançadas',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  # Impressão básica
  %(prog)s --ip 192.168.1.100 --file documento.pdf
  
  # Impressão colorida, frente e verso, 2 cópias
  %(prog)s --ip 192.168.1.100 --file documento.pdf --color --duplex --copies 2
  
  # Impressão de alta qualidade em papel fotográfico
  %(prog)s --ip 192.168.1.100 --file foto.jpg --quality alta --media fotografico
  
  # Impressão de páginas específicas
  %(prog)s --ip 192.168.1.100 --file documento.pdf --pages "1-5,10,15-20"
        """
    )
    
    # Argumentos obrigatórios
    parser.add_argument('--ip', required=True, help='IP da impressora')
    parser.add_argument('--file', required=True, help='Arquivo para imprimir')
    
    # Opções de conexão
    parser.add_argument('--port', type=int, default=631, help='Porta IPP (padrão: 631)')
    
    # Opções de cor
    parser.add_argument('--color', action='store_true', help='Impressão colorida')
    parser.add_argument('--mono', action='store_true', help='Impressão monocromática')
    
    # Opções de duplex
    parser.add_argument('--duplex', action='store_true', help='Frente e verso (borda longa)')
    parser.add_argument('--duplex-short', action='store_true', help='Frente e verso (borda curta)')
    
    # Tipo de mídia
    parser.add_argument('--media', choices=['normal', 'fotografico', 'transparencia', 
                                           'envelope', 'cartao', 'reciclado', 'glossy', 'matte'],
                       default='normal', help='Tipo de papel')
    
    # Qualidade
    parser.add_argument('--quality', choices=['rascunho', 'normal', 'alta'],
                       default='normal', help='Qualidade de impressão')
    
    # Outras opções
    parser.add_argument('--copies', type=int, default=1, help='Número de cópias')
    parser.add_argument('--no-collate', action='store_true', help='Não agrupar cópias')
    parser.add_argument('--landscape', action='store_true', help='Orientação paisagem')
    parser.add_argument('--pages', help='Páginas a imprimir (ex: "1-5,7,10-15")')
    parser.add_argument('--fit', action='store_true', help='Ajustar à página')
    parser.add_argument('--paper', default='iso_a4_210x297mm', help='Tamanho do papel')
    parser.add_argument('--job-name', help='Nome do trabalho de impressão')
    
    args = parser.parse_args()
    
    # Configura opções de impressão
    options = PrintOptions()
    
    # Cor
    if args.mono:
        options.color_mode = ColorMode.MONOCROMO
    elif args.color:
        options.color_mode = ColorMode.COLORIDO
        
    # Duplex
    if args.duplex_short:
        options.duplex = Duplex.DUPLEX_CURTO
    elif args.duplex:
        options.duplex = Duplex.DUPLEX_LONGO
        
    # Mídia
    media_map = {
        'normal': MediaType.NORMAL,
        'fotografico': MediaType.FOTOGRAFICO,
        'transparencia': MediaType.TRANSPARENCIA,
        'envelope': MediaType.ENVELOPE,
        'cartao': MediaType.CARTAO,
        'reciclado': MediaType.RECICLADO,
        'glossy': MediaType.GLOSSY,
        'matte': MediaType.MATTE
    }
    options.media_type = media_map[args.media]
    
    # Qualidade
    quality_map = {
        'rascunho': Quality.RASCUNHO,
        'normal': Quality.NORMAL,
        'alta': Quality.ALTA
    }
    options.quality = quality_map[args.quality]
    
    # Outras opções
    options.copies = args.copies
    options.collate = not args.no_collate
    options.orientation = "landscape" if args.landscape else "portrait"
    options.page_ranges = args.pages
    options.fit_to_page = args.fit
    options.paper_size = args.paper
    
    # Exibe resumo das opções
    print("\n🖨️  CONFIGURAÇÕES DE IMPRESSÃO")
    print("=" * 40)
    print(f"📄 Arquivo: {args.file}")
    print(f"🌐 Impressora: {args.ip}:{args.port}")
    print(f"🎨 Modo de cor: {options.color_mode.name}")
    print(f"📃 Duplex: {options.duplex.name}")
    print(f"📋 Tipo de papel: {options.media_type.name}")
    print(f"⚡ Qualidade: {options.quality.name}")
    print(f"🔢 Cópias: {options.copies}")
    if options.page_ranges:
        print(f"📑 Páginas: {options.page_ranges}")
    print("=" * 40)
    
    # Cria objeto da impressora e imprime
    printer = SimplePrinter(args.ip, args.port)
    success = printer.print_file(args.file, options, args.job_name)
    
    if success:
        print("\n✅ Impressão concluída com sucesso!")
        sys.exit(0)
    else:
        print("\n❌ Falha na impressão")
        sys.exit(1)


if __name__ == "__main__":
    main()
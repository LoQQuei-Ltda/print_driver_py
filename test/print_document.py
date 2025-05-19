#!/usr/bin/env python3
"""
Script simplificado para enviar um arquivo PDF para impressão usando IPP (Internet Printing Protocol)
Baseado no get_attributes.py, focando apenas na funcionalidade de impressão via IP
"""

import argparse
import os
import sys
import asyncio
import requests
from urllib.parse import urlparse
import socket
import struct

# Configurações globais
TIMEOUT_REQUEST = 5  # Timeout para requisições HTTP/IPP (aumentado)
IPP_PORTS = [631, 9100, 80, 443]  # Portas comuns para IPP

def install_dependencies():
    """Instala dependências necessárias"""
    import subprocess
    required_packages = ["requests"]
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Instalando dependências: {', '.join(missing)}")
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
        print("Dependências instaladas com sucesso")

def is_port_open(ip, port, timeout=1):
    """Verifica se uma porta está aberta"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def detect_printer_url(ip):
    """Detecta a URL IPP da impressora"""
    # Verifica se as portas comuns para IPP estão abertas
    open_ports = []
    for port in IPP_PORTS:
        if is_port_open(ip, port):
            open_ports.append(port)
            print(f"Porta {port} aberta em {ip}")
    
    if not open_ports:
        print(f"Nenhuma porta IPP comum aberta em {ip}")
        # Tenta usar a porta padrão IPP
        return f"https://{ip}:631/ipp/print"
    
    # Prioriza porta 631 (IPP padrão)
    if 631 in open_ports:
        # Tenta diferentes caminhos de URL IPP
        paths = ["/ipp/print", "/ipp/printer", "/ipp", ""]
        for path in paths:
            url = f"https://{ip}:631{path}"
            try:
                response = requests.head(url, timeout=TIMEOUT_REQUEST)
                if response.status_code < 400:
                    print(f"URL IPP válida encontrada: {url}")
                    return url
            except Exception as e:
                pass
        
        # Se nenhum caminho funcionou, usa o padrão
        print(f"Usando URL IPP padrão na porta 631: https://{ip}:631/ipp/print")
        return f"https://{ip}:631/ipp/print"
    
    # Se 631 não estiver disponível, verifica outras portas
    for port in open_ports:
        paths = ["/ipp/print", "/ipp/printer", "/ipp", ""]
        for path in paths:
            url = f"https://{ip}:{port}{path}"
            try:
                response = requests.head(url, timeout=TIMEOUT_REQUEST)
                if response.status_code < 400:
                    print(f"URL IPP válida encontrada: {url}")
                    return url
            except Exception as e:
                pass
    
    # Se nenhuma URL IPP válida for encontrada, retorna a URL padrão para IPP
    default_url = f"https://{ip}:631/ipp/print"
    print(f"Usando URL IPP padrão: {default_url}")
    return default_url

def print_with_http(url, pdf_path):
    """
    Imprime um PDF usando requisições HTTP POST simples
    Algumas impressoras aceitam envio direto via HTTP
    """
    print(f"Tentando imprimir via HTTP POST: {url}")
    
    try:
        # Lê o arquivo PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Informações do arquivo
        filename = os.path.basename(pdf_path)
        
        # Configura headers para envio do PDF
        headers = {
            'Content-Type': 'application/pdf',
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        
        # Envia a requisição HTTP
        response = requests.post(
            url,
            data=pdf_data,
            headers=headers,
            timeout=TIMEOUT_REQUEST
        )
        
        if response.status_code < 300:
            print(f"✓ Impressão enviada via HTTP (status: {response.status_code})")
            return True
        else:
            print(f"✗ Erro na resposta HTTP: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Erro ao imprimir com HTTP: {e}")
        return False

def print_with_ipp(url, pdf_path):
    """
    Imprime um PDF usando requisições IPP diretas
    Implementa o protocolo IPP conforme RFC 8010
    """
    print(f"Enviando documento para impressão via IPP: {url}")
    
    try:
        # Lê o arquivo PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Parse URL
        parsed_url = urlparse(url)
        host = parsed_url.netloc
        path = parsed_url.path
        if not path:
            path = "/ipp/print"
        
        # Cria requisição IPP
        operation_id = 0x0002  # Print-Job operation
        request_id = 1
        
        # Atributos do trabalho
        attributes = {
            "attributes-charset": "utf-8",
            "attributes-natural-language": "en-us",
            "printer-uri": f"ipp://{host}{path}",
            "requesting-user-name": "anonymous",
            "job-name": os.path.basename(pdf_path),
            "document-format": "application/pdf"
        }
        
        # Constrói pacote IPP
        version = struct.pack('>bb', 1, 1)  # IPP version 1.1
        operation = struct.pack('>h', operation_id)
        req_id = struct.pack('>i', request_id)
        
        # Início do pacote
        packet = version + operation + req_id
        
        # Adiciona grupo de atributos de operação (grupo 1)
        packet += struct.pack('>b', 1)  # Operation attributes tag
        
        # Adiciona atributos
        for name, value in attributes.items():
            if isinstance(value, str):
                packet += struct.pack('>b', 0x45)  # value-tag for text
                packet += struct.pack('>h', len(name)) + name.encode('utf-8')
                packet += struct.pack('>h', len(value)) + value.encode('utf-8')
        
        # Fim dos atributos
        packet += struct.pack('>b', 3)  # End-of-attributes tag
        
        # Adiciona dados do documento
        packet += pdf_data
        
        # Envia a requisição
        headers = {
            'Content-Type': 'application/ipp',
        }
        
        response = requests.post(
            url,
            data=packet,
            headers=headers,
            timeout=TIMEOUT_REQUEST
        )
        
        if response.status_code < 300:
            print(f"✓ Impressão enviada via IPP (status: {response.status_code})")
            return True
        else:
            print(f"✗ Erro na resposta IPP: {response.status_code}")
            # Debug da resposta em caso de erro
            print(f"Conteúdo da resposta: {response}...")
            return False
    except Exception as e:
        print(f"✗ Erro ao imprimir com IPP: {e}")
        return False

def print_with_socket(ip, port, pdf_path):
    """Imprime usando socket direto (para impressoras RAW)"""
    print(f"Enviando documento para impressão via socket: {ip}:{port}")
    
    try:
        # Lê o arquivo PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Conecta ao socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ip, port))
        
        # Envia o documento
        sock.sendall(pdf_data)
        
        # Envia sequência de fechamento para algumas impressoras
        try:
            sock.sendall(b'\x1D\x12\x07\x00')  # Sequência de finalização comum
        except:
            pass
            
        # Fecha a conexão corretamente
        sock.close()
        
        print(f"✓ Documento enviado com sucesso via socket para {ip}:{port}")
        return True
    except Exception as e:
        print(f"✗ Erro ao imprimir com socket: {e}")
        return False

async def print_document(ip, pdf_path):
    """Função principal para imprimir um documento"""
    # Verifica se o arquivo existe
    if not os.path.exists(pdf_path):
        print(f"✗ Erro: Arquivo não encontrado: {pdf_path}")
        return False
    
    print(f"Documento para impressão: {os.path.basename(pdf_path)}")
    print(f"Detectando impressora em: {ip}")
    
    # Detecta URL IPP da impressora
    url = detect_printer_url(ip)
    parsed_url = urlparse(url)
    host = parsed_url.netloc.split(':')[0]  # Extrai o IP sem a porta
    port = int(parsed_url.netloc.split(':')[1]) if ":" in parsed_url.netloc else 631
    
    # Tenta primeiro imprimir usando IPP (método mais padronizado)
    if print_with_ipp(url, pdf_path):
        return True
    
    # Se falhar IPP, tenta imprimir usando HTTP simples
    if print_with_http(url, pdf_path):
        return True
    
    # Se ambos os métodos HTTP falharem, tenta imprimir usando socket
    # Primeiro na porta 9100 (porta RAW padrão)
    if is_port_open(ip, 9100):
        if print_with_socket(ip, 9100, pdf_path):
            return True
    
    # Se a porta especificada não for 631 ou 9100, tenta com socket também
    if port not in [631, 9100] and is_port_open(ip, port):
        if print_with_socket(ip, port, pdf_path):
            return True
    
    # Tenta na porta 515 (LPR/LPD) como último recurso
    if is_port_open(ip, 515):
        if print_with_socket(ip, 515, pdf_path):
            return True
    
    print("✗ Todas as tentativas de impressão falharam")
    return False

async def main():
    parser = argparse.ArgumentParser(description='Ferramenta simplificada para impressão IPP.')
    parser.add_argument('--ip', required=True, help='Endereço IP da impressora')
    parser.add_argument('--pdf', required=True, help='Caminho para o arquivo PDF a ser impresso')
    parser.add_argument('--port', type=int, help='Porta específica para conexão (opcional)')
    
    args = parser.parse_args()
    
    # Instala dependências
    install_dependencies()
    
    # Se uma porta específica foi fornecida, tenta diretamente com socket
    if args.port:
        if is_port_open(args.ip, args.port):
            if print_with_socket(args.ip, args.port, args.pdf):
                print("\n✓ Documento enviado para impressão com sucesso!")
                sys.exit(0)
    
    # Processo normal de detecção e impressão
    success = await print_document(args.ip, args.pdf)
    
    if success:
        print("\n✓ Documento enviado para impressão com sucesso!")
        sys.exit(0)
    else:
        print("\n✗ Falha ao enviar documento para impressão")
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
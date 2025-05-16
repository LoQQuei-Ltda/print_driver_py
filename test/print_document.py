#!/usr/bin/env python3
"""
Script para enviar um arquivo PDF para impressão usando endereço MAC da impressora e IPP
"""

import argparse
import os
import sys
import subprocess
import socket
import time
from urllib.parse import urlparse
import requests
import netifaces
import ipaddress

def mac_to_ip(mac_address):
    """
    Tenta encontrar o endereço IP associado ao endereço MAC fornecido.
    Utiliza uma combinação de ARP e descoberta de rede.
    """
    # Normaliza o formato do endereço MAC (remove ":" ou "-" e converte para minúsculas)
    mac_address = mac_address.lower().replace(":", "").replace("-", "")
    normalized_mac = ":".join([mac_address[i:i+2] for i in range(0, len(mac_address), 2)])
    
    print(f"Procurando impressora com MAC: {normalized_mac}")
    
    # Método 1: Consulta da tabela ARP
    try:
        # Em sistemas Unix/Linux
        if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
            output = subprocess.check_output(['arp', '-a'], universal_newlines=True)
        # Em sistemas Windows
        elif sys.platform.startswith('win'):
            output = subprocess.check_output(['arp', '-a'], universal_newlines=True)
        else:
            print("Sistema operacional não suportado para consulta ARP")
            output = ""
            
        for line in output.splitlines():
            if normalized_mac in line.lower():
                # Extrai o endereço IP da linha
                ip = line.split()[1].strip('()')
                if '(' in ip:
                    ip = ip.split('(')[1].split(')')[0]
                print(f"Encontrado IP {ip} para MAC {normalized_mac} via tabela ARP")
                return ip
    except Exception as e:
        print(f"Erro ao consultar tabela ARP: {e}")
    
    # Método 2: Verificação de rede local
    try:
        # Obtém interfaces de rede
        interfaces = netifaces.interfaces()
        
        for interface in interfaces:
            if netifaces.AF_INET in netifaces.ifaddresses(interface):
                addr_info = netifaces.ifaddresses(interface)[netifaces.AF_INET][0]
                if 'addr' in addr_info and 'netmask' in addr_info:
                    ip = addr_info['addr']
                    netmask = addr_info['netmask']
                    
                    # Calcula endereço de rede
                    net_addr = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                    
                    print(f"Verificando rede: {net_addr}")
                    
                    # Ping na rede para popular tabela ARP
                    for host in net_addr.hosts():
                        # Limita a 254 hosts para evitar varredura excessiva
                        if int(str(host).split('.')[-1]) > 254:
                            continue
                        
                        try:
                            # Ping com timeout curto
                            subprocess.call(
                                ['ping', '-c', '1', '-W', '1', str(host)],
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL
                            )
                        except:
                            pass
                    
                    # Verifica tabela ARP novamente
                    try:
                        if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                            output = subprocess.check_output(['arp', '-a'], universal_newlines=True)
                        elif sys.platform.startswith('win'):
                            output = subprocess.check_output(['arp', '-a'], universal_newlines=True)
                            
                        for line in output.splitlines():
                            if normalized_mac in line.lower():
                                ip = line.split()[1].strip('()')
                                if '(' in ip:
                                    ip = ip.split('(')[1].split(')')[0]
                                print(f"Encontrado IP {ip} para MAC {normalized_mac} via varredura de rede")
                                return ip
                    except Exception as e:
                        print(f"Erro ao consultar tabela ARP após varredura: {e}")
    except Exception as e:
        print(f"Erro ao verificar rede local: {e}")
    
    # Se não encontrou, tenta usar ferramentas externas
    try:
        # Nmap (se disponível)
        try:
            output = subprocess.check_output(['nmap', '-sP', '192.168.1.0/24'], universal_newlines=True)
            # Consulta ARP novamente após nmap
            if sys.platform.startswith('linux') or sys.platform.startswith('darwin'):
                output = subprocess.check_output(['arp', '-a'], universal_newlines=True)
            elif sys.platform.startswith('win'):
                output = subprocess.check_output(['arp', '-a'], universal_newlines=True)
                
            for line in output.splitlines():
                if normalized_mac in line.lower():
                    ip = line.split()[1].strip('()')
                    if '(' in ip:
                        ip = ip.split('(')[1].split(')')[0]
                    print(f"Encontrado IP {ip} para MAC {normalized_mac} via nmap")
                    return ip
        except:
            pass
    except:
        pass
    
    return None

def discover_ipp_url(ip_address):
    """
    Descobre a URL IPP de uma impressora a partir de seu endereço IP.
    """
    # Tenta várias portas e caminhos comuns do IPP
    common_ports = [631, 80, 443, 9100]
    common_paths = [
        "/ipp/print",
        "/ipp",
        "/printer",
        "/printers/default",
        "/printers/ipp"
    ]
    
    for port in common_ports:
        for path in common_paths:
            url = f"http://{ip_address}:{port}{path}"
            try:
                response = requests.get(url, timeout=2)
                if response.status_code == 200:
                    print(f"Encontrado possível endpoint IPP: {url}")
                    return url
            except:
                pass
    
    # Se não encontrou um endpoint específico, retorna a URL padrão IPP
    print(f"Usando URL IPP padrão para {ip_address}")
    return f"http://{ip_address}:631/ipp/print"

def send_pdf_to_printer(mac_address, pdf_path):
    """
    Envia um arquivo PDF para uma impressora usando seu endereço MAC.
    """
    if not os.path.exists(pdf_path):
        print(f"Erro: O arquivo {pdf_path} não existe.")
        return False
    
    if not pdf_path.lower().endswith('.pdf'):
        print(f"Aviso: O arquivo {pdf_path} não parece ser um PDF.")
    
    # Encontra IP a partir do MAC
    ip_address = mac_to_ip(mac_address)
    if not ip_address:
        print(f"Erro: Não foi possível encontrar um endereço IP para o MAC {mac_address}")
        return False
    
    print(f"Impressora encontrada no IP: {ip_address}")
    
    # Descobre URL IPP
    ipp_url = discover_ipp_url(ip_address)
    
    # Tenta vários métodos para imprimir
    methods = [
        # Método 1: CUPS/lpr (Linux/Mac)
        lambda: print_with_cups(ip_address, pdf_path),
        # Método 2: IPP direto
        lambda: print_with_ipp(ipp_url, pdf_path),
        # Método 3: Windows (para sistemas Windows)
        lambda: print_with_windows(ip_address, pdf_path)
    ]
    
    for method in methods:
        try:
            if method():
                return True
        except Exception as e:
            print(f"Método de impressão falhou: {e}")
    
    print("Todos os métodos de impressão falharam.")
    return False

def print_with_cups(ip_address, pdf_path):
    """
    Tenta imprimir usando CUPS (Linux/Mac)
    """
    if not (sys.platform.startswith('linux') or sys.platform.startswith('darwin')):
        return False
    
    print("Tentando imprimir usando CUPS...")
    
    # Adiciona impressora temporária
    printer_name = f"temp_printer_{int(time.time())}"
    
    try:
        # Adiciona a impressora
        subprocess.check_call([
            'lpadmin', 
            '-p', printer_name, 
            '-v', f"ipp://{ip_address}/ipp/print", 
            '-E'
        ])
        
        # Imprime o arquivo
        result = subprocess.check_call([
            'lpr', 
            '-P', printer_name, 
            pdf_path
        ])
        
        print(f"Arquivo enviado para impressão via CUPS: {pdf_path}")
        
        # Remove a impressora temporária
        subprocess.check_call(['lpadmin', '-x', printer_name])
        
        return True
    except Exception as e:
        print(f"Erro ao imprimir com CUPS: {e}")
        
        # Tenta remover a impressora temporária mesmo em caso de erro
        try:
            subprocess.check_call(['lpadmin', '-x', printer_name])
        except:
            pass
            
        return False

def print_with_ipp(ipp_url, pdf_path):
    """
    Tenta imprimir usando requisições IPP diretas
    """
    print(f"Tentando imprimir usando IPP direto para {ipp_url}...")
    
    try:
        # Carrega o arquivo PDF
        with open(pdf_path, 'rb') as f:
            pdf_data = f.read()
        
        # Cabeçalhos para IPP
        headers = {
            'Content-Type': 'application/pdf',
            'X-Print-Job': 'true'
        }
        
        # Envia o arquivo para o endpoint IPP
        response = requests.post(
            ipp_url,
            data=pdf_data,
            headers=headers,
            timeout=10
        )
        
        if response.status_code >= 200 and response.status_code < 300:
            print(f"Arquivo enviado para impressão via IPP: {pdf_path}")
            return True
        else:
            print(f"Erro ao imprimir via IPP. Código: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Erro ao imprimir com IPP: {e}")
        return False

def print_with_windows(ip_address, pdf_path):
    """
    Tenta imprimir usando o sistema do Windows
    """
    if not sys.platform.startswith('win'):
        return False
    
    print("Tentando imprimir usando o Windows...")
    
    try:
        # Adiciona impressora temporária
        printer_name = f"TempPrinter{int(time.time())}"
        port_name = f"IP_{ip_address}"
        
        # Cria porta TCP/IP (se necessário)
        try:
            subprocess.check_call([
                'cscript', 
                '//nologo', 
                os.path.join(os.environ['WINDIR'], 'System32', 'Printing_Admin_Scripts', 'en-US', 'prnport.vbs'),
                '-a', 
                '-r', port_name,
                '-h', ip_address,
                '-o', 'raw',
                '-n', '9100'
            ])
        except:
            # Pode ser que a porta já exista
            pass
            
        # Adiciona a impressora
        subprocess.check_call([
            'cscript',
            '//nologo',
            os.path.join(os.environ['WINDIR'], 'System32', 'Printing_Admin_Scripts', 'en-US', 'prnmngr.vbs'),
            '-a',
            '-p', printer_name,
            '-m', 'Generic / Text Only',
            '-r', port_name
        ])
        
        # Imprime o PDF
        subprocess.check_call([
            'rundll32',
            'mshtml.dll,PrintHTML',
            pdf_path,
            printer_name
        ])
        
        print(f"Arquivo enviado para impressão via Windows: {pdf_path}")
        
        # Remove a impressora temporária
        try:
            subprocess.check_call([
                'cscript',
                '//nologo',
                os.path.join(os.environ['WINDIR'], 'System32', 'Printing_Admin_Scripts', 'en-US', 'prnmngr.vbs'),
                '-d',
                '-p', printer_name
            ])
        except:
            pass
            
        return True
        
    except Exception as e:
        print(f"Erro ao imprimir com Windows: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Envia um arquivo PDF para uma impressora usando seu endereço MAC.')
    parser.add_argument('mac_address', help='Endereço MAC da impressora (formato: AA:BB:CC:DD:EE:FF)')
    parser.add_argument('pdf_path', help='Caminho para o arquivo PDF a ser impresso')
    
    args = parser.parse_args()
    
    # Verificações iniciais
    if not os.path.exists(args.pdf_path):
        print(f"Erro: Arquivo '{args.pdf_path}' não encontrado.")
        sys.exit(1)
    
    print(f"Iniciando impressão do arquivo: {args.pdf_path}")
    print(f"Impressora MAC: {args.mac_address}")
    
    # Instala dependências se necessário
    try:
        import netifaces
    except ImportError:
        print("Instalando dependências necessárias...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "netifaces", "requests"])
        
        # Recarrega após instalação
        import netifaces
    
    success = send_pdf_to_printer(args.mac_address, args.pdf_path)
    
    if success:
        print("Arquivo enviado para impressão com sucesso!")
        sys.exit(0)
    else:
        print("Falha ao enviar arquivo para impressão.")
        sys.exit(1)

if __name__ == "__main__":
    main()
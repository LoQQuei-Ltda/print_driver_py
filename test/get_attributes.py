#!/usr/bin/env python3
"""
Script otimizado para descobrir impressoras na rede e obter seus atributos.
Combina velocidade e confiabilidade para encontrar dispositivos por MAC ou IP.
"""

import argparse
import asyncio
import os
import sys
import subprocess
import socket
import time
import ipaddress
import re
import json
import concurrent.futures
from datetime import datetime

def install_dependencies():
    """Instala dependências necessárias"""
    required_packages = ["pyipp", "tabulate"]
    missing = []
    
    for package in required_packages:
        try:
            __import__(package.replace("-", "_"))
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"Instalando: {', '.join(missing)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
            print("Dependências instaladas com sucesso")
        except Exception as e:
            print(f"Erro ao instalar automaticamente: {e}")
            print(f"Por favor, instale manualmente: pip install {' '.join(missing)}")
            sys.exit(1)

# Instalar dependências
try:
    install_dependencies()
except Exception as e:
    print(f"Erro ao instalar dependências: {e}")
    print("Por favor, instale manualmente: pip install pyipp tabulate")

# Importar bibliotecas após instalação
import pyipp
from tabulate import tabulate

# Configurações globais
TIMEOUT_REQUEST = 2      # Timeout para requisições HTTP/IPP
TIMEOUT_SCAN = 0.3       # Timeout para escaneamento de portas (curto para mais velocidade)
PARALLEL_HOSTS = 50      # Número de hosts para verificar em paralelo
COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515]  # Portas a verificar, ordenadas por prioridade

# Mapeamento de estados IPP para texto legível
PRINTER_STATE_MAP = {
    3: "Idle (Pronta)",
    4: "Processing (Ocupada)",
    5: "Stopped (Parada)"
}

def normalize_mac(mac):
    """Normaliza o formato do MAC para comparação"""
    if not mac:
        return None
        
    # Remove todos os separadores e converte para minúsculas
    clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac.lower())
    
    # Verifica se o MAC está completo (12 caracteres hexadecimais)
    if len(clean_mac) != 12:
        print(f"Aviso: MAC incompleto: {mac} ({len(clean_mac)} caracteres em vez de 12)")
        # Se estiver incompleto, completa com zeros
        clean_mac = clean_mac.ljust(12, '0')
    
    # Retorna no formato XX:XX:XX:XX:XX:XX
    return ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])

def get_local_ip():
    """Obtém o endereço IP local da máquina"""
    try:
        # Cria um socket e conecta a um servidor externo
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        # Fallback para localhost
        return "127.0.0.1"

def get_network_from_ip(ip):
    """Determina a rede a partir do IP local"""
    networks = []
    
    # Primeiro, tenta a subnet /24 do IP atual
    try:
        parts = ip.split('.')
        network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
        networks.append(ipaddress.IPv4Network(network))
        print(f"Usando rede: {network}")
    except:
        pass
    
    # Se não tiver nenhuma rede, use redes padrão comuns
    if not networks:
        fallback_networks = ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24"]
        for net in fallback_networks:
            try:
                networks.append(ipaddress.IPv4Network(net))
                print(f"Usando rede padrão: {net}")
            except:
                pass
                
    return networks

def is_port_open(ip, port, timeout=TIMEOUT_SCAN):
    """Verifica se uma porta está aberta"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        return result == 0
    except:
        return False

def get_common_ips(subnet):
    """Retorna os IPs mais comuns para impressoras em uma subnet"""
    # Gateways comuns
    common_hosts = []
    
    try:
        network = ipaddress.IPv4Network(subnet, strict=False)
        base = int(network.network_address)
        
        # IPs com finais comuns para impressoras
        common_suffixes = [1, 2, 10, 20, 30, 50, 100, 101, 102, 200, 250, 251, 252, 253, 254]
        
        # Cria lista de IPs comuns para esta rede
        for suffix in common_suffixes:
            if suffix < network.num_addresses:
                ip = str(network.network_address + suffix)
                common_hosts.append(ip)
        
        # Adiciona 5 IPs aleatórios da rede para diversidade
        import random
        all_ips = [str(ip) for ip in network.hosts()]
        if len(all_ips) > 10:  # Se a rede tem mais de 10 IPs
            sample_size = min(5, len(all_ips) // 2)
            random_ips = random.sample(all_ips, sample_size)
            for ip in random_ips:
                if ip not in common_hosts:
                    common_hosts.append(ip)
    except Exception as e:
        print(f"Erro ao gerar IPs comuns: {e}")
    
    return common_hosts

def get_mac_for_ip(ip):
    """Tenta obter o MAC de um endereço IP usando ARP"""
    try:
        if sys.platform.startswith(('linux', 'darwin')):
            cmd = ['arp', '-n', ip]
        else:  # Windows
            cmd = ['arp', '-a', ip]
            
        output = subprocess.check_output(cmd, universal_newlines=True, timeout=1)
        
        # Procura pelo MAC usando regex
        mac_pattern = re.compile(r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})')
        mac_match = mac_pattern.search(output)
        
        if mac_match:
            return mac_match.group(1)
            
        # Padrão alternativo para Windows (espaços)
        mac_pattern2 = re.compile(r'([0-9A-Fa-f]{2}[-\s][0-9A-Fa-f]{2}[-\s][0-9A-Fa-f]{2}[-\s][0-9A-Fa-f]{2}[-\s][0-9A-Fa-f]{2}[-\s][0-9A-Fa-f]{2})')
        mac_match2 = mac_pattern2.search(output)
        
        if mac_match2:
            return mac_match2.group(1).replace(' ', '-')
    except:
        pass
        
    # Se não encontrou o MAC, tenta um ping para atualizar a tabela ARP
    try:
        if sys.platform.startswith(('linux', 'darwin')):
            cmd = ['ping', '-c', '1', '-W', '1', ip]
        else:  # Windows
            cmd = ['ping', '-n', '1', '-w', '1000', ip]
            
        subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
        
        # Tenta novamente após o ping
        if sys.platform.startswith(('linux', 'darwin')):
            cmd = ['arp', '-n', ip]
        else:  # Windows
            cmd = ['arp', '-a', ip]
            
        output = subprocess.check_output(cmd, universal_newlines=True, timeout=1)
        
        mac_match = re.search(r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})', output)
        if mac_match:
            return mac_match.group(1)
    except:
        pass
    
    return "desconhecido"

def run_nmap_scan(subnet, quick=False):
    """Executa nmap para descobrir impressoras na rede (se disponível)"""
    printers = []
    
    try:
        # Verifica se o nmap está instalado
        try:
            subprocess.check_output(["nmap", "--version"], stderr=subprocess.STDOUT)
        except:
            print("nmap não encontrado, usando escaneamento manual")
            return []
            
        # Define parâmetros do nmap
        if quick:
            # Rápido: apenas verifica portas 631 e 9100, com tempos de timeout curtos
            print(f"Escaneamento rápido de {subnet} com nmap...")
            cmd = ["nmap", "-p", "631,9100", "-T5", "--open", "-n", "--max-retries", "1", str(subnet)]
        else:
            # Completo: verifica todas as portas comuns de impressora
            print(f"Escaneamento completo de {subnet} com nmap...")
            cmd = ["nmap", "-p", "631,9100,80,443,515", "-T4", "--open", str(subnet)]
        
        # Executa nmap
        output = subprocess.check_output(cmd, universal_newlines=True)
        
        # Processa a saída do nmap
        ip_pattern = re.compile(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})')
        unique_ips = set()
        
        for line in output.splitlines():
            if "Nmap scan report for" in line:
                ip_match = ip_pattern.search(line)
                if ip_match:
                    ip = ip_match.group(1)
                    unique_ips.add(ip)
        
        # Para cada IP encontrado, obtém o MAC e adiciona à lista
        for ip in unique_ips:
            mac = get_mac_for_ip(ip)
            printers.append({"ip": ip, "mac": mac})
            print(f"Encontrada impressora: {ip} (MAC: {mac})")
        
        return printers
    except Exception as e:
        print(f"Erro no nmap: {e}")
        return []

def quick_mac_lookup(target_mac, subnet=None):
    """
    Tenta descobrir o IP correspondente a um MAC rapidamente.
    Usa vários métodos diretos antes de fazer uma varredura completa.
    """
    normalized_target_mac = normalize_mac(target_mac)
    
    if not normalized_target_mac:
        print("MAC inválido")
        return None
    
    print(f"Procurando rapidamente dispositivo com MAC: {normalized_target_mac}")
    
    # Método 1: Verificar tabela ARP atual
    try:
        if sys.platform.startswith(('linux', 'darwin')):
            cmd = ['arp', '-n']
        else:  # Windows
            cmd = ['arp', '-a']
            
        output = subprocess.check_output(cmd, universal_newlines=True, timeout=1)
        
        # Procurar pelo MAC em diferentes formatos possíveis
        mac_variations = [
            normalized_target_mac,
            normalized_target_mac.replace(':', '-'),
            normalized_target_mac.replace(':', '').upper(),
            normalized_target_mac.replace(':', '').lower()
        ]
        
        for line in output.splitlines():
            line_lower = line.lower()
            
            for mac_var in mac_variations:
                if mac_var in line_lower:
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    if ip_match:
                        ip = ip_match.group(1)
                        print(f"✓ Dispositivo encontrado: {ip} (via tabela ARP)")
                        return ip
    except Exception as e:
        print(f"Erro ao consultar tabela ARP: {e}")
    
    # Método 2: Usar nmap (muito mais rápido que escaneamento manual)
    if subnet:
        try:
            networks = [ipaddress.IPv4Network(subnet, strict=False)]
        except:
            networks = get_network_from_ip(get_local_ip())
    else:
        networks = get_network_from_ip(get_local_ip())
        
    for network in networks:
        print(f"Escaneando {network} para MAC {normalized_target_mac}")
        
        # Tenta usar nmap para descoberta rápida
        printers = run_nmap_scan(network, quick=True)
        
        # Verifica se algum dos dispositivos encontrados tem o MAC alvo
        for printer in printers:
            if normalize_mac(printer["mac"]) == normalized_target_mac:
                print(f"✓ Dispositivo encontrado: {printer['ip']} (via nmap)")
                return printer["ip"]
    
    # Método 3: Ping em IPs comuns para atualizar a tabela ARP
    for network in networks:
        common_ips = get_common_ips(network)
        print(f"Fazendo ping em {len(common_ips)} endereços comuns...")
        
        def ping_host(ip):
            try:
                if sys.platform.startswith(('linux', 'darwin')):
                    cmd = ['ping', '-c', '1', '-W', '1', ip]
                else:  # Windows
                    cmd = ['ping', '-n', '1', '-w', '1000', ip]
                    
                subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                return ip
            except:
                return None
                
        # Executa pings em paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
            executor.map(ping_host, common_ips)
            
        # Verifica a tabela ARP após pings
        try:
            if sys.platform.startswith(('linux', 'darwin')):
                cmd = ['arp', '-n']
            else:  # Windows
                cmd = ['arp', '-a']
                
            output = subprocess.check_output(cmd, universal_newlines=True, timeout=1)
            
            # Procurar pelo MAC em diferentes formatos possíveis
            for line in output.splitlines():
                line_lower = line.lower()
                
                for mac_var in mac_variations:
                    if mac_var in line_lower:
                        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                        if ip_match:
                            ip = ip_match.group(1)
                            print(f"✓ Dispositivo encontrado: {ip} (após ping)")
                            return ip
        except Exception as e:
            print(f"Erro ao consultar tabela ARP após ping: {e}")
    
    # Se nenhum método rápido funcionou, retorna None
    print("Métodos rápidos não encontraram o dispositivo.")
    return None

async def scan_printer_ports(ip):
    """Verifica as portas de impressora em um único IP"""
    open_ports = []
    
    # Verifica cada uma das portas comuns
    for port in COMMON_PRINTER_PORTS:
        if is_port_open(ip, port):
            open_ports.append(port)
    
    # Se tiver alguma porta aberta que seja comum para impressoras
    if open_ports:
        mac = get_mac_for_ip(ip)
        
        # Presume que é uma impressora se alguma porta comum estiver aberta
        printer_info = {
            "ip": ip,
            "mac": mac,
            "ports": open_ports
        }
        
        return printer_info
    
    return None

async def scan_subset(ips, target_mac=None):
    """Escaneia um subconjunto de IPs"""
    results = []
    target_ip = None
    normalized_target_mac = normalize_mac(target_mac) if target_mac else None
    
    # Processa os IPs em pedaços para limitar o paralelismo
    for i in range(0, len(ips), PARALLEL_HOSTS):
        chunk = ips[i:i+PARALLEL_HOSTS]
        tasks = [scan_printer_ports(ip) for ip in chunk]
        
        chunk_results = await asyncio.gather(*tasks)
        
        for printer_info in chunk_results:
            if printer_info:  # Se encontrou uma impressora
                results.append(printer_info)
                print(f"Encontrada impressora: {printer_info['ip']} (MAC: {printer_info['mac']})")
                
                # Se está procurando por um MAC específico
                if normalized_target_mac and normalize_mac(printer_info['mac']) == normalized_target_mac:
                    target_ip = printer_info['ip']
                    print(f"✓ Encontrado dispositivo com MAC {target_mac}: {target_ip}")
        
        # Se encontrou o alvo, pode parar
        if target_ip:
            break
    
    return target_ip, results

async def optimized_scan(target_mac=None, subnet=None, full_scan=False):
    """
    Faz uma varredura otimizada para encontrar impressoras.
    Usa uma estratégia em etapas, começando pelos métodos mais rápidos.
    """
    # Se está procurando por um MAC específico, tenta primeiro os métodos rápidos
    if target_mac:
        quick_ip = quick_mac_lookup(target_mac, subnet)
        if quick_ip:
            return quick_ip, [{"ip": quick_ip, "mac": target_mac}]
    
    # Determina as redes a escanear
    if subnet:
        try:
            networks = [ipaddress.IPv4Network(subnet, strict=False)]
        except Exception as e:
            print(f"Erro ao processar subnet {subnet}: {e}")
            networks = get_network_from_ip(get_local_ip())
    else:
        networks = get_network_from_ip(get_local_ip())
    
    all_printers = []
    target_ip = None
    
    # Para cada rede
    for network in networks:
        print(f"Escaneando rede: {network}")
        
        # Método 1: Usar nmap se disponível (muito mais rápido)
        nmap_printers = run_nmap_scan(network, quick=not full_scan)
        if nmap_printers:
            all_printers.extend(nmap_printers)
            
            # Verifica se encontrou o MAC alvo
            if target_mac:
                normalized_target_mac = normalize_mac(target_mac)
                for printer in nmap_printers:
                    if normalize_mac(printer["mac"]) == normalized_target_mac:
                        target_ip = printer["ip"]
                        print(f"✓ Encontrado dispositivo com MAC {target_mac}: {target_ip}")
                        return target_ip, all_printers
        
        # Se nmap não encontrou nada ou não está disponível, faz escaneamento manual
        if not nmap_printers or full_scan:
            # Método 2: Verificar IPs comuns para impressoras (para escaneamento rápido)
            if not full_scan:
                common_ips = get_common_ips(network)
                print(f"Verificando {len(common_ips)} IPs comuns para impressoras...")
                
                ip, printers = await scan_subset(common_ips, target_mac)
                all_printers.extend(printers)
                
                if ip:  # Se encontrou o MAC alvo
                    target_ip = ip
                    return target_ip, all_printers
            
            # Método 3: Escaneamento completo da rede (se full_scan ou ainda não encontrou)
            if full_scan or (target_mac and not target_ip):
                # Limita a 254 hosts por rede para evitar sobrecarga
                all_ips = [str(ip) for ip in network.hosts()][0:254]
                print(f"Executando varredura completa em {len(all_ips)} IPs...")
                
                ip, printers = await scan_subset(all_ips, target_mac)
                all_printers.extend(printers)
                
                if ip:  # Se encontrou o MAC alvo
                    target_ip = ip
                    return target_ip, all_printers
    
    # Deduplica os resultados
    unique_printers = []
    seen_ips = set()
    
    for printer in all_printers:
        if printer["ip"] not in seen_ips:
            unique_printers.append(printer)
            seen_ips.add(printer["ip"])
    
    return target_ip, unique_printers

async def get_ipp_attributes(ip, port=631):
    """
    Obtém atributos da impressora usando pyipp de forma assíncrona.
    Tenta automaticamente com TLS (HTTPS) e sem TLS (HTTP).
    """
    protocols = [
        {"name": "HTTP", "tls": False},
        {"name": "HTTPS", "tls": True}
    ]
    
    # Endpoints a serem testados
    endpoints = ["/ipp/print", "/ipp/printer", "/ipp", ""]
    
    for protocol in protocols:
        tls_mode = protocol["tls"]
        protocol_name = protocol["name"]
        
        url_scheme = "https" if tls_mode else "http"
        url_base = f"{url_scheme}://{ip}:{port}"
        
        for endpoint in endpoints:
            url = f"{url_base}{endpoint}"
            print(f"Tentando conectar via {protocol_name}: {url}...")
            
            try:
                # Cria cliente IPP com o modo TLS configurado
                client = pyipp.IPP(host=ip, port=port, tls=tls_mode)
                client.url_path = endpoint
                
                # Solicita todos os atributos disponíveis
                printer_attrs = await asyncio.wait_for(client.printer(), timeout=TIMEOUT_REQUEST)
                
                if printer_attrs:
                    print(f"✓ Conexão bem-sucedida usando {protocol_name} com endpoint: {endpoint}")
                    
                    # Exibe informações da impressora para ajudar a depurar
                    if hasattr(printer_attrs, 'info'):
                        print(f"Impressora: {printer_attrs.info.name}")
                    
                    # Se for um objeto Printer, extrai informações estruturadas
                    if hasattr(printer_attrs, 'info') and hasattr(printer_attrs, 'state'):
                        return process_printer_object(printer_attrs, ip)
                    # Se for um dicionário, processa normalmente
                    elif isinstance(printer_attrs, dict):
                        return process_printer_dict(printer_attrs, ip)
                    else:
                        print(f"Tipo de dados inesperado: {type(printer_attrs)}")
                        return {"ip": ip, "raw_data": str(printer_attrs)}
            except Exception as e:
                print(f"Tentativa com {protocol_name} e endpoint {endpoint} falhou: {str(e)}")
                continue
    
    # Se chegou aqui, não conseguiu conectar-se com nenhum protocolo/endpoint
    print(f"✗ Não foi possível conectar à impressora em {ip}:{port} usando IPP")
    
    # Retorna informações básicas, mesmo sem IPP
    basic_info = {
        "ip": ip,
        "name": f"Impressora {ip}",
        "printer-state": "Desconhecido (não responde a IPP)"
    }
    
    return basic_info

def process_printer_object(printer_obj, ip):
    """Processa um objeto Printer retornado pelo pyipp."""
    result = {"ip": ip}
    
    # Extrai informações básicas
    if hasattr(printer_obj, 'info'):
        info = printer_obj.info
        result['name'] = info.name
        result['printer-make-and-model'] = info.model
        result['printer-location'] = info.location
        result['printer-info'] = info.printer_info
        result['manufacturer'] = info.manufacturer
        result['printer-more-info'] = info.more_info
        result['printer-uri-supported'] = info.printer_uri_supported
        
        # Informações adicionais
        if hasattr(info, 'command_set'):
            result['command-set'] = info.command_set
        if hasattr(info, 'serial'):
            result['serial'] = info.serial
        if hasattr(info, 'uuid'):
            result['uuid'] = info.uuid
        if hasattr(info, 'version'):
            result['version'] = info.version
    
    # Extrai estado da impressora
    if hasattr(printer_obj, 'state'):
        state = printer_obj.state
        state_map = {
            'idle': "Idle (Pronta)",
            'processing': "Processing (Ocupada)",
            'stopped': "Stopped (Parada)"
        }
        result['printer-state'] = state_map.get(state.printer_state, state.printer_state)
        
        if state.message:
            result['printer-state-message'] = state.message
        if state.reasons:
            result['printer-state-reasons'] = state.reasons
    
    # Extrai informações de suprimentos
    if hasattr(printer_obj, 'markers') and printer_obj.markers:
        supplies = []
        for marker in printer_obj.markers:
            supply_info = {
                'id': marker.marker_id,
                'name': marker.name,
                'type': marker.marker_type,
                'color': marker.color,
                'level': marker.level,
                'low_level': marker.low_level,
                'high_level': marker.high_level
            }
            supplies.append(supply_info)
        result['supplies'] = supplies
    
    # Extrai URIs suportadas
    if hasattr(printer_obj, 'uris') and printer_obj.uris:
        uris = []
        for uri in printer_obj.uris:
            uri_info = {
                'uri': uri.uri,
                'authentication': uri.authentication,
                'security': uri.security
            }
            uris.append(uri_info)
        result['uris'] = uris
    
    return result

def process_printer_dict(printer_dict, ip):
    """Processa um dicionário de atributos retornado pelo pyipp."""
    result = {"ip": ip}
    
    # Extrair dados da resposta
    if isinstance(printer_dict, dict):
        # Extrai atributos da tag principal
        attrs = printer_dict.get('printer-attributes-tag', {})
        
        # Extrai informações básicas
        result['name'] = attrs.get('printer-name', ['Desconhecido'])[0] if isinstance(attrs.get('printer-name'), list) else attrs.get('printer-name', 'Desconhecido')
        result['printer-make-and-model'] = attrs.get('printer-make-and-model', ['Desconhecido'])[0] if isinstance(attrs.get('printer-make-and-model'), list) else attrs.get('printer-make-and-model', 'Desconhecido')
        result['printer-location'] = attrs.get('printer-location', ['Desconhecida'])[0] if isinstance(attrs.get('printer-location'), list) else attrs.get('printer-location', 'Desconhecida')
        
        # Obtém e converte o estado da impressora
        state_code = attrs.get('printer-state', [3])[0] if isinstance(attrs.get('printer-state'), list) else attrs.get('printer-state', 3)
        state_map = {3: "Idle (Pronta)", 4: "Processing (Ocupada)", 5: "Stopped (Parada)"}
        result['printer-state'] = state_map.get(state_code, f"Desconhecido ({state_code})")
        
        # Adiciona todos os outros atributos ao resultado
        for key, value in attrs.items():
            if key not in result:  # Evita sobrescrever valores já processados
                # Limpa valores, especialmente para listas
                if isinstance(value, list) and len(value) == 1:
                    result[key] = value[0]
                else:
                    result[key] = value
    
    return result

def display_printer_summary(printer_info):
    """Exibe um resumo formatado das informações da impressora"""
    if not printer_info:
        return
        
    print("\n" + "=" * 50)
    print(f"RESUMO DA IMPRESSORA: {printer_info.get('name', 'Desconhecida')}")
    print("=" * 50)
    print(f"IP: {printer_info.get('ip', 'Desconhecido')}")
    print(f"Modelo: {printer_info.get('printer-make-and-model', 'Desconhecido')}")
    print(f"Localização: {printer_info.get('printer-location', 'Desconhecida')}")
    print(f"Status: {printer_info.get('printer-state', 'Desconhecido')}")
    
    # Informações adicionais que podem ser úteis
    if 'manufacturer' in printer_info:
        print(f"Fabricante: {printer_info['manufacturer']}")
    if 'version' in printer_info:
        print(f"Versão: {printer_info['version']}")
    if 'serial' in printer_info:
        print(f"Número de Série: {printer_info['serial']}")
    if 'printer-uri-supported' in printer_info:
        print(f"URIs suportadas: {printer_info['printer-uri-supported']}")
    if 'printer-type' in printer_info:
        print(f"Tipo: {printer_info['printer-type']}")
    
    # Exibe informações de suprimentos se disponíveis
    if 'supplies' in printer_info and printer_info['supplies']:
        print("\nInformações de Suprimentos:")
        for supply in printer_info['supplies']:
            print(f"  {supply['name']}: {supply['level']}% (Tipo: {supply['type']}, Cor: {supply['color']})")
    
    print("=" * 50)

async def main():
    parser = argparse.ArgumentParser(description='Ferramenta otimizada para descobrir impressoras e obter seus atributos.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--ip', help='Endereço IP da impressora')
    group.add_argument('--mac', help='Endereço MAC da impressora (formato: AA:BB:CC:DD:EE:FF)')
    group.add_argument('--scan', action='store_true', help='Escanear rede para encontrar todas as impressoras')
    parser.add_argument('--subnet', help='Sub-rede específica (formato: 192.168.1.0/24)')
    parser.add_argument('--port', type=int, default=0, help='Porta IPP (padrão: auto-detectar)')
    parser.add_argument('--full', action='store_true', help='Mostrar todos os atributos detalhados')
    parser.add_argument('--save', help='Salvar resultados em arquivo (formato JSON)')
    parser.add_argument('--quick', action='store_true', help='Usar apenas métodos rápidos de escaneamento')
    
    args = parser.parse_args()
    
    # Se não houver parâmetros, mostrar ajuda
    if len(sys.argv) == 1:
        parser.print_help()
        return
    
    # Arquivo para salvar resultados, se especificado
    results_file = args.save
    start_time = time.time()
    
    # Modo de escaneamento de rede
    if args.scan:
        print("Iniciando escaneamento da rede para encontrar impressoras...")
        _, printers = await optimized_scan(subnet=args.subnet, full_scan=not args.quick)
        
        if printers:
            # Exibe em formato de tabela
            table_data = []
            for printer in printers:
                ports = printer.get("ports", [])
                if not ports and isinstance(printer.get("port"), int):
                    ports = [printer.get("port")]
                
                table_data.append([
                    printer["ip"], 
                    printer["mac"], 
                    ", ".join(str(p) for p in ports) if ports else "N/A"
                ])
            
            elapsed = time.time() - start_time
            print(f"\nImpressoras encontradas em {elapsed:.1f} segundos:")
            print(tabulate(table_data, headers=["IP", "MAC", "Portas"], tablefmt="grid"))
            
            # Salva resultados se solicitado
            if results_file:
                with open(results_file, 'w') as f:
                    json.dump(printers, f, indent=2)
                print(f"Resultados salvos em {results_file}")
            
            print("\nPara obter atributos de uma impressora específica, execute:")
            print(f"python {sys.argv[0]} --ip <endereço_ip>")
        else:
            print("Nenhuma impressora encontrada na rede.")
        return
    
    # Define o IP a ser usado
    target_ip = None
    if args.ip:
        target_ip = args.ip
        print(f"Usando IP fornecido: {target_ip}")
    elif args.mac:
        print(f"Procurando impressora com MAC: {args.mac}")
        target_ip, _ = await optimized_scan(args.mac, args.subnet, full_scan=not args.quick)
        
        if not target_ip:
            print("Operação interrompida: dispositivo não encontrado.")
            return
        
        elapsed = time.time() - start_time
        print(f"Dispositivo encontrado em {elapsed:.1f} segundos")
    else:
        print("Especifique --ip, --mac ou --scan")
        return
    
    # Determina a porta a ser usada
    port = args.port if args.port > 0 else 631
    
    # Obtém atributos da impressora
    printer_info = await get_ipp_attributes(target_ip, port)
    
    if printer_info:
        # Exibe resumo da impressora
        display_printer_summary(printer_info)
        
        # Opcional: exibir todos os atributos
        if args.full:
            print("\nTodos os atributos encontrados:")
            for key, value in sorted(printer_info.items()):
                if key != "supplies":  # Já mostramos os suprimentos no resumo
                    print(f"{key}: {value}")
        
        # Salva resultados se solicitado
        if results_file:
            with open(results_file, 'w') as f:
                json.dump(printer_info, f, indent=2)
            print(f"Detalhes da impressora salvos em {results_file}")
    else:
        print(f"Falha ao obter atributos de {target_ip}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nOperação cancelada pelo usuário.")
    except Exception as e:
        print(f"Erro inesperado: {str(e)}")
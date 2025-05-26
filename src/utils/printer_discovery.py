#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitário para descoberta automática de impressoras na rede
"""

import asyncio
import os
import sys
import socket
import subprocess
import re
import logging
import ipaddress
import concurrent.futures
import threading
import time
import json
from datetime import datetime
import platform

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterDiscovery")

# Configurações globais
TIMEOUT_REQUEST = 2       # Timeout para requisições HTTP/IPP
TIMEOUT_SCAN = 0.3        # Timeout para escaneamento de portas
PARALLEL_HOSTS = 25       # Número de hosts para verificar em paralelo
COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515]  # Portas a verificar

# Configurações para o IPP
try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    HAS_PYIPP = False
    logger.warning("Módulo pyipp não encontrado. Informações detalhadas de impressoras não estarão disponíveis.")

class PrinterDiscovery:
    """Classe para descoberta automática de impressoras na rede"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.system = platform.system()
    
    def normalize_mac(self, mac):
        """Normaliza o formato do MAC para comparação"""
        if not mac:
            return None
            
        # Remove todos os separadores e converte para minúsculas
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac.lower())
        
        # Verifica se o MAC está completo (12 caracteres hexadecimais)
        if len(clean_mac) != 12:
            logger.warning(f"Aviso: MAC incompleto: {mac} ({len(clean_mac)} caracteres em vez de 12)")
            # Se estiver incompleto, completa com zeros
            clean_mac = clean_mac.ljust(12, '0')
        
        # Retorna no formato XX:XX:XX:XX:XX:XX
        return ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    
    def discover_printers(self, subnet=None):
        """
        Descobre impressoras na rede de forma síncrona
        
        Args:
            subnet: Subnet específica para escanear (formato: 192.168.1.0/24)
            
        Returns:
            list: Lista de impressoras encontradas
        """
        try:
            # Executa a varredura de forma síncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            _, printers = loop.run_until_complete(self._scan_network(subnet))
            loop.close()
            
            # Verifica se todas as impressoras têm IP definido
            for printer in printers:
                if "ip" not in printer or not printer["ip"]:
                    logger.warning(f"Impressora sem IP: {printer}")
                else:
                    logger.info(f"Impressora descoberta com IP: {printer['ip']}")
            
            self.printers = printers
            return printers
        except Exception as e:
            logger.error(f"Erro na descoberta de impressoras: {str(e)}")
            return []
    
    def get_printer_details(self, ip):
        """
        Obtém detalhes de uma impressora específica de forma síncrona
        
        Args:
            ip: Endereço IP da impressora
            
        Returns:
            dict: Detalhes da impressora
        """
        if not ip:
            return None
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        details = loop.run_until_complete(self._get_printer_attributes(ip))
        loop.close()
        
        return details
    
    async def _scan_network(self, subnet=None):
        """
        Escaneia a rede para encontrar impressoras
        
        Args:
            subnet: Subnet específica para escanear
            
        Returns:
            tuple: (IP do alvo, lista de impressoras)
        """
        # Determina as redes a escanear
        if subnet:
            try:
                networks = [ipaddress.IPv4Network(subnet, strict=False)]
            except Exception as e:
                logger.error(f"Erro ao processar subnet {subnet}: {str(e)}")
                networks = self._get_network_from_ip(self._get_local_ip())
        else:
            networks = self._get_network_from_ip(self._get_local_ip())
        
        all_printers = []
        
        # Para cada rede
        for network in networks:
            logger.info(f"Escaneando rede: {network}")
            
            # Primeiro tenta usar nmap para descoberta rápida
            nmap_printers = self._run_nmap_scan(network)
            if nmap_printers:
                all_printers.extend(nmap_printers)
            
            # Se nmap não encontrou ou não está disponível, usa método alternativo
            if not nmap_printers:
                # Verifica IPs comuns para impressoras
                common_ips = self._get_common_ips(network)
                logger.info(f"Verificando {len(common_ips)} IPs comuns para impressoras...")
                
                _, printers = await self._scan_subset(common_ips)
                all_printers.extend(printers)
        
        # Deduplica os resultados
        unique_printers = []
        seen_ips = set()
        
        for printer in all_printers:
            if printer["ip"] not in seen_ips:
                unique_printers.append(printer)
                seen_ips.add(printer["ip"])
        
        return None, unique_printers
    
    async def _scan_subset(self, ips):
        """
        Escaneia um subconjunto de IPs
        
        Args:
            ips: Lista de IPs para escanear
            
        Returns:
            tuple: (IP alvo, impressoras encontradas)
        """
        results = []
        
        # Processa os IPs em pedaços para limitar o paralelismo
        for i in range(0, len(ips), PARALLEL_HOSTS):
            chunk = ips[i:i+PARALLEL_HOSTS]
            tasks = [self._scan_printer_ports(ip) for ip in chunk]
            
            chunk_results = await asyncio.gather(*tasks)
            
            for printer_info in chunk_results:
                if printer_info:  # Se encontrou uma impressora
                    results.append(printer_info)
                    logger.info(f"Encontrada impressora: {printer_info['ip']} (MAC: {printer_info.get('mac_address', 'desconhecido')})")
        
        return None, results
    
    async def _scan_printer_ports(self, ip):
        """
        Verifica as portas de impressora em um único IP de forma mais robusta
        
        Args:
            ip: Endereço IP a verificar
            
        Returns:
            dict: Informações da impressora, ou None
        """
        try:
            # Primeiro verifica se o host responde
            if not self._ping_host(ip, 0.5):
                return None
            
            open_ports = []
            
            # Verifica as portas em paralelo com timeout menor
            def check_port(port):
                return port if self._is_port_open(ip, port, 0.3) else None
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(check_port, port): port for port in COMMON_PRINTER_PORTS}
                
                for future in concurrent.futures.as_completed(futures, timeout=3):
                    try:
                        result = future.result()
                        if result:
                            open_ports.append(result)
                    except:
                        continue
            
            # Se não tem portas abertas, não é uma impressora
            if not open_ports:
                return None
            
            # Verifica se realmente parece ser uma impressora
            printer_indicators = 0
            
            # Portas típicas de impressoras aumentam a pontuação
            if 631 in open_ports:  # IPP
                printer_indicators += 3
            if 9100 in open_ports:  # AppSocket/JetDirect
                printer_indicators += 3
            if 515 in open_ports:  # LPD
                printer_indicators += 2
            
            # Se tem porta 80/443 mas nenhuma outra, pode não ser impressora
            if open_ports == [80] or open_ports == [443] or open_ports == [80, 443]:
                # Tenta verificar se responde a requisições HTTP típicas de impressora
                try:
                    import urllib.request
                    import urllib.error
                    
                    url = f"http://{ip}" if 80 in open_ports else f"https://{ip}"
                    req = urllib.request.Request(url)
                    req.add_header('User-Agent', 'PrinterDiscovery/1.0')
                    
                    with urllib.request.urlopen(req, timeout=2) as response:
                        content = response.read().decode('utf-8', errors='ignore').lower()
                        
                        # Procura por indicadores de impressora no conteúdo
                        printer_keywords = ['printer', 'print', 'toner', 'cartridge', 'samsung', 'hp', 'canon', 'epson', 'brother', 'lexmark']
                        for keyword in printer_keywords:
                            if keyword in content:
                                printer_indicators += 1
                                break
                except:
                    pass
            
            # Se não tem indicadores suficientes, provavelmente não é impressora
            if printer_indicators == 0 and not (631 in open_ports or 9100 in open_ports):
                return None
            
            # Obtém MAC address
            mac = self._get_mac_for_ip(ip)
            
            # Determina o melhor URI
            uri = None
            if 631 in open_ports:
                uri = f"ipp://{ip}/ipp/print"
            elif 9100 in open_ports:
                uri = f"socket://{ip}:9100"
            elif 515 in open_ports:
                uri = f"lpd://{ip}/queue"
            elif 80 in open_ports:
                uri = f"http://{ip}"
            elif 443 in open_ports:
                uri = f"https://{ip}"
            
            printer_info = {
                "ip": ip,
                "mac_address": mac,
                "ports": open_ports,
                "uri": uri,
                "name": f"Impressora {ip}",
                "is_online": True
            }
            
            logger.info(f"Impressora encontrada: {ip} (MAC: {mac}, Portas: {open_ports})")
            return printer_info
            
        except Exception as e:
            logger.error(f"Erro ao verificar IP {ip}: {e}")
            return None

    
    async def _get_printer_attributes(self, ip, port=631):
        """
        Obtém atributos da impressora usando IPP
        
        Args:
            ip: Endereço IP da impressora
            port: Porta IPP (padrão: 631)
            
        Returns:
            dict: Atributos da impressora
        """
        if not HAS_PYIPP:
            return {"ip": ip, "error": "Módulo pyipp não disponível"}
        
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
                logger.info(f"Tentando conectar via {protocol_name}: {url}...")
                
                try:
                    # Cria cliente IPP com o modo TLS configurado
                    client = pyipp.IPP(host=ip, port=port, tls=tls_mode)
                    client.url_path = endpoint
                    
                    # Solicita todos os atributos disponíveis
                    printer_attrs = await asyncio.wait_for(client.printer(), timeout=TIMEOUT_REQUEST)
                    
                    if printer_attrs:
                        logger.info(f"Conexão bem-sucedida usando {protocol_name} com endpoint: {endpoint}")
                        
                        # Se for um objeto Printer, extrai informações estruturadas
                        if hasattr(printer_attrs, 'info') and hasattr(printer_attrs, 'state'):
                            result = self._process_printer_object(printer_attrs, ip)
                        # Se for um dicionário, processa normalmente
                        elif isinstance(printer_attrs, dict):
                            result = self._process_printer_dict(printer_attrs, ip)
                        else:
                            logger.info(f"Tipo de dados inesperado: {type(printer_attrs)}")
                            result = {"ip": ip, "raw_data": str(printer_attrs)}
                        
                        # Garante que o IP e nome estão definidos
                        result['ip'] = ip
                        if 'name' not in result or not result['name']:
                            result['name'] = f"Impressora {ip}"
                            
                        return result
                except Exception as e:
                    logger.warning(f"Tentativa com {protocol_name} e endpoint {endpoint} falhou: {str(e)}")
                    continue
        
        # Se chegou aqui, não conseguiu conectar-se com nenhum protocolo/endpoint
        logger.info(f"Não foi possível conectar à impressora em {ip}:{port} usando IPP")
        
        # Retorna informações básicas, mesmo sem IPP
        basic_info = {
            "ip": ip,
            "name": f"Impressora {ip}",
            "printer-state": "Desconhecido (não responde a IPP)"
        }
        
        return basic_info
    
    def _process_printer_object(self, printer_obj, ip):
        """
        Processa um objeto Printer retornado pelo pyipp
        
        Args:
            printer_obj: Objeto Printer
            ip: Endereço IP da impressora
            
        Returns:
            dict: Atributos processados
        """
        result = {"ip": ip}
        
        # Extrai informações básicas
        if hasattr(printer_obj, 'info'):
            info = printer_obj.info
            result['name'] = info.name if hasattr(info, 'name') else f"Impressora {ip}"
            
            # Garante que todos os campos estão presentes
            if hasattr(info, 'model'):
                result['printer-make-and-model'] = info.model
            if hasattr(info, 'location'):
                result['printer-location'] = info.location
            if hasattr(info, 'printer_info'):
                result['printer-info'] = info.printer_info
            if hasattr(info, 'manufacturer'):
                result['manufacturer'] = info.manufacturer
            if hasattr(info, 'more_info'):
                result['printer-more-info'] = info.more_info
            if hasattr(info, 'printer_uri_supported'):
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
            
            if hasattr(state, 'printer_state'):
                result['printer-state'] = state_map.get(state.printer_state, state.printer_state)
            
            if hasattr(state, 'message') and state.message:
                result['printer-state-message'] = state.message
            if hasattr(state, 'reasons') and state.reasons:
                result['printer-state-reasons'] = state.reasons
        
        # Extrai informações de suprimentos
        if hasattr(printer_obj, 'markers') and printer_obj.markers:
            supplies = []
            for marker in printer_obj.markers:
                supply_info = {}
                
                # Garante que todos os campos estão presentes
                if hasattr(marker, 'marker_id'):
                    supply_info['id'] = marker.marker_id
                if hasattr(marker, 'name'):
                    supply_info['name'] = marker.name
                if hasattr(marker, 'marker_type'):
                    supply_info['type'] = marker.marker_type
                if hasattr(marker, 'color'):
                    supply_info['color'] = marker.color
                if hasattr(marker, 'level'):
                    supply_info['level'] = marker.level
                if hasattr(marker, 'low_level'):
                    supply_info['low_level'] = marker.low_level
                if hasattr(marker, 'high_level'):
                    supply_info['high_level'] = marker.high_level
                
                supplies.append(supply_info)
            
            result['supplies'] = supplies
        
        # Extrai URIs suportadas
        if hasattr(printer_obj, 'uris') and printer_obj.uris:
            uris = []
            for uri in printer_obj.uris:
                uri_info = {}
                
                if hasattr(uri, 'uri'):
                    uri_info['uri'] = uri.uri
                if hasattr(uri, 'authentication'):
                    uri_info['authentication'] = uri.authentication
                if hasattr(uri, 'security'):
                    uri_info['security'] = uri.security
                    
                uris.append(uri_info)
            
            result['uris'] = uris
        
        return result
    
    def _process_printer_dict(self, printer_dict, ip):
        """
        Processa um dicionário de atributos retornado pelo pyipp
        
        Args:
            printer_dict: Dicionário de atributos
            ip: Endereço IP da impressora
            
        Returns:
            dict: Atributos processados
        """
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
    
    def _is_port_open(self, ip, port, timeout=0.5):
        """
        Verifica se uma porta está aberta de forma mais robusta
        
        Args:
            ip: Endereço IP
            port: Número da porta
            timeout: Tempo limite em segundos
            
        Returns:
            bool: True se a porta estiver aberta
        """
        try:
            # Primeiro tenta com timeout mais rápido
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            if result == 0:
                return True
                
            # Se falhou, tenta novamente com timeout maior
            time.sleep(0.1)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout * 2)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            return result == 0
            
        except Exception as e:
            logger.debug(f"Erro ao verificar porta {port} em {ip}: {e}")
            return False

    
    def _get_local_ip(self):
        """
        Obtém o endereço IP local da máquina de forma mais robusta
        
        Returns:
            str: Endereço IP local
        """
        try:
            # Método 1: Conectar a um servidor externo
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            
            # Valida se o IP obtido é válido
            if local_ip and not local_ip.startswith('127.'):
                return local_ip
        except Exception as e:
            logger.warning(f"Método 1 falhou: {e}")
        
        try:
            # Método 2: Usando hostname
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and not local_ip.startswith('127.'):
                return local_ip
        except Exception as e:
            logger.warning(f"Método 2 falhou: {e}")
        
        try:
            # Método 3: Listar todas as interfaces de rede
            import netifaces
            for interface in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr_info in addrs[netifaces.AF_INET]:
                            ip = addr_info.get('addr')
                            if ip and not ip.startswith('127.') and not ip.startswith('169.254'):
                                return ip
                except:
                    continue
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"Método 3 falhou: {e}")
        
        try:
            # Método 4: Parsing de ifconfig/ipconfig
            if sys.platform.startswith('win'):
                result = subprocess.run(['ipconfig'], capture_output=True, text=True, timeout=5, 
                                    creationflags=subprocess.CREATE_NO_WINDOW)
                output = result.stdout
                # Procura por IPv4 Address
                ip_pattern = re.compile(r'IPv4 Address[.\s]*:\s*(\d+\.\d+\.\d+\.\d+)')
            else:
                result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=5)
                output = result.stdout
                # Procura por inet addr
                ip_pattern = re.compile(r'inet (?:addr:)?(\d+\.\d+\.\d+\.\d+)')
            
            for match in ip_pattern.finditer(output):
                ip = match.group(1)
                if not ip.startswith('127.') and not ip.startswith('169.254'):
                    return ip
                    
        except Exception as e:
            logger.warning(f"Método 4 falhou: {e}")
        
        # Fallback final
        logger.warning("Usando fallback 192.168.1.100")
        return "192.168.1.100"

    
    def _get_network_from_ip(self, ip):
        """
        Determina múltiplas redes a partir do IP local de forma mais robusta
        
        Args:
            ip: Endereço IP
            
        Returns:
            list: Lista de redes para escanear
        """
        networks = []
        
        try:
            # Rede principal baseada no IP atual
            parts = ip.split('.')
            if len(parts) == 4:
                # Tenta /24 primeiro
                network_24 = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                networks.append(ipaddress.IPv4Network(network_24))
                logger.info(f"Adicionada rede principal: {network_24}")
                
                # Se for uma rede classe A ou B, adiciona subredes menores
                if parts[0] in ['10']:
                    # Rede classe A - adiciona algumas subredes /16
                    for i in range(0, 256, 64):
                        subnet = f"10.{i}.0.0/16"
                        try:
                            networks.append(ipaddress.IPv4Network(subnet))
                        except:
                            pass
                elif parts[0] == '172' and int(parts[1]) >= 16 and int(parts[1]) <= 31:
                    # Rede classe B
                    subnet = f"172.{parts[1]}.0.0/16"
                    try:
                        networks.append(ipaddress.IPv4Network(subnet))
                    except:
                        pass
        except Exception as e:
            logger.warning(f"Erro ao processar IP {ip}: {e}")
        
        # Adiciona redes comuns sempre
        common_networks = [
            "192.168.1.0/24",
            "192.168.0.0/24", 
            "192.168.2.0/24",
            "10.0.0.0/24",
            "10.0.1.0/24",
            "172.16.0.0/24"
        ]
        
        for net_str in common_networks:
            try:
                net = ipaddress.IPv4Network(net_str)
                if net not in networks:
                    networks.append(net)
                    logger.info(f"Adicionada rede comum: {net_str}")
            except:
                pass
        
        return networks
    
    def _get_common_ips(self, subnet):
        """
        Retorna os IPs mais comuns para impressoras em uma subnet
        
        Args:
            subnet: Subnet
            
        Returns:
            list: Lista de IPs comuns
        """
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
            logger.error(f"Erro ao gerar IPs comuns: {str(e)}")
        
        return common_hosts
    
    def _get_mac_for_ip(self, ip):
        """
        Tenta obter o MAC de um endereço IP de forma mais robusta
        
        Args:
            ip: Endereço IP
            
        Returns:
            str: Endereço MAC normalizado ou "desconhecido"
        """
        # Primeiro faz ping para garantir que o IP está na tabela ARP
        self._ping_host(ip, 1)
        time.sleep(0.2)  # Pequena pausa para atualizar ARP
        
        try:
            system_name = platform.system().lower()
            
            if system_name == "windows":
                cmd = ['arp', '-a']
            else:
                cmd = ['arp', '-a']  # Funciona tanto no Linux quanto no macOS
            
            # Tenta múltiplas vezes
            for attempt in range(3):
                try:
                    result = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        timeout=3,
                        creationflags=subprocess.CREATE_NO_WINDOW if system_name == "windows" else 0
                    )
                    
                    if result.returncode == 0:
                        output = result.stdout
                        
                        # Múltiplos padrões de regex para diferentes formatos
                        mac_patterns = [
                            rf'{re.escape(ip)}\s+([0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}})',
                            rf'({re.escape(ip)}).*?([0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}})',
                            rf'([0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}[:-][0-9A-Fa-f]{{2}}).*?{re.escape(ip)}'
                        ]
                        
                        # Procura em cada linha que contém o IP
                        for line in output.split('\n'):
                            if ip in line:
                                for pattern in mac_patterns:
                                    match = re.search(pattern, line, re.IGNORECASE)
                                    if match:
                                        mac = match.group(-1)  # Pega o último grupo (o MAC)
                                        return self.normalize_mac(mac)
                    
                except subprocess.TimeoutExpired:
                    logger.warning(f"Timeout ao executar ARP (tentativa {attempt + 1})")
                    continue
                except Exception as e:
                    logger.debug(f"Erro na tentativa {attempt + 1} de ARP: {e}")
                    continue
        
        except Exception as e:
            logger.warning(f"Erro ao obter MAC para {ip}: {e}")
        
        # Se chegou aqui, tenta método alternativo no Windows
        if platform.system().lower() == "windows":
            try:
                cmd = ['nbtstat', '-A', ip]
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    # Procura por MAC address na saída do nbtstat
                    mac_match = re.search(r'([0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2})', result.stdout)
                    if mac_match:
                        return self.normalize_mac(mac_match.group(1))
            except:
                pass
        
        return "desconhecido"

    
    def _ping_host(self, ip, timeout=1):
        """
        Faz ping em um host de forma mais robusta
        
        Args:
            ip: Endereço IP
            timeout: Tempo limite em segundos
            
        Returns:
            bool: True se o ping foi bem-sucedido
        """
        try:
            system_name = platform.system().lower()
            
            if system_name == "windows":
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
                creation_flags = subprocess.CREATE_NO_WINDOW
            elif system_name == "darwin":  # macOS
                cmd = ["ping", "-c", "1", "-W", str(int(timeout * 1000)), ip]
                creation_flags = 0
            else:  # Linux e outros Unix
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
                creation_flags = 0
            
            # Tenta três vezes com timeouts crescentes
            for attempt in range(3):
                try:
                    result = subprocess.run(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=timeout + attempt,
                        creationflags=creation_flags
                    )
                    
                    if result.returncode == 0:
                        return True
                        
                except subprocess.TimeoutExpired:
                    continue
                except Exception as e:
                    logger.debug(f"Tentativa {attempt + 1} falhou para {ip}: {e}")
                    continue
            
            return False
            
        except Exception as e:
            logger.warning(f"Erro ao executar ping para {ip}: {e}")
            return False

        
    def _create_printer_info(self, ip, mac):
        """
        Cria informações básicas da impressora com IP e MAC
        
        Args:
            ip: Endereço IP
            mac: MAC address
            
        Returns:
            dict: Informações básicas da impressora
        """
        # Verifica quais portas estão abertas
        open_ports = []
        for port in COMMON_PRINTER_PORTS:
            if self._is_port_open(ip, port):
                open_ports.append(port)
        
        # Determina o URI
        uri = None
        if 631 in open_ports:
            uri = f"ipp://{ip}/ipp/print"
        elif 9100 in open_ports:
            uri = f"socket://{ip}:9100"
        elif 80 in open_ports:
            uri = f"http://{ip}"
        elif 443 in open_ports:
            uri = f"https://{ip}"
        
        # Cria as informações da impressora
        printer_info = {
            "ip": ip,
            "mac_address": mac,
            "ports": open_ports,
            "uri": uri,
            "is_online": True,
            "name": f"Impressora {ip}"
        }
        
        return printer_info

    def _quick_mac_lookup_arp(self, normalized_mac):
        """
        Procura rapidamente um MAC na tabela ARP
        
        Args:
            normalized_mac: MAC normalizado 
            
        Returns:
            str: IP se encontrado, None caso contrário
        """
        try:
            if sys.platform.startswith(('linux', 'darwin')):
                cmd = ['arp', '-n']
            else:  # Windows
                cmd = ['arp', '-a']
                
            output = subprocess.check_output(cmd, universal_newlines=True, timeout=1)
            
            # Cria variações do MAC para procurar
            mac_variations = [
                normalized_mac,
                normalized_mac.replace(':', '-'),
                normalized_mac.replace(':', '').upper(),
                normalized_mac.replace(':', '').lower()
            ]
            
            # Procura o MAC em cada linha da saída
            for line in output.splitlines():
                line_lower = line.lower()
                
                for mac_var in mac_variations:
                    if mac_var in line_lower:
                        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                        if ip_match:
                            return ip_match.group(1)
        except Exception as e:
            logger.warning(f"Erro na consulta ARP: {str(e)}")
        
        return None

    def discover_printer_by_mac(self, target_mac):
        """
        Tenta descobrir o IP correspondente a um MAC específico
        
        Args:
            target_mac: MAC address da impressora (formato: XX:XX:XX:XX:XX:XX)
            
        Returns:
            dict: Informações da impressora encontrada ou None
        """
        # Normaliza o MAC
        normalized_target_mac = self.normalize_mac(target_mac)
        if not normalized_target_mac:
            logger.warning(f"MAC inválido: {target_mac}")
            return None
            
        logger.info(f"Procurando impressora com MAC: {normalized_target_mac}")
        
        # Métodos rápidos
        
        # Método 1: Verificar tabela ARP atual
        try:
            logger.info("Verificando tabela ARP atual...")
            ip = self._quick_mac_lookup_arp(normalized_target_mac)
            if ip:
                logger.info(f"Encontrado IP na tabela ARP: {ip}")
                return self._create_printer_info(ip, normalized_target_mac)
        except Exception as e:
            logger.warning(f"Erro ao verificar tabela ARP: {str(e)}")
        
        # Método 2: Tentar com nmap
        try:
            logger.info("Tentando com nmap...")
            networks = self._get_network_from_ip(self._get_local_ip())
            for network in networks:
                printers = self._run_nmap_scan(network)
                for printer in printers:
                    if self.normalize_mac(printer.get('mac_address', '')) == normalized_target_mac:
                        logger.info(f"Encontrado via nmap: {printer}")
                        return printer
        except Exception as e:
            logger.warning(f"Erro ao tentar nmap: {str(e)}")
        
        # Método 3: Procurar em IPs comuns
        try:
            logger.info("Verificando IPs comuns...")
            networks = self._get_network_from_ip(self._get_local_ip())
            for network in networks:
                common_ips = self._get_common_ips(network)
                logger.info(f"Fazendo ping em {len(common_ips)} IPs comuns...")
                
                # Faz ping em paralelo
                with concurrent.futures.ThreadPoolExecutor(max_workers=25) as executor:
                    executor.map(self._ping_host, common_ips)
                
                # Verifica tabela ARP novamente
                ip = self._quick_mac_lookup_arp(normalized_target_mac)
                if ip:
                    logger.info(f"Encontrado IP após pings: {ip}")
                    return self._create_printer_info(ip, normalized_target_mac)
        except Exception as e:
            logger.warning(f"Erro ao verificar IPs comuns: {str(e)}")
        
        # Não encontrou
        logger.warning(f"Não foi possível encontrar o IP para o MAC: {normalized_target_mac}")
        return None

    def _run_nmap_scan(self, subnet):
        """
        Executa nmap de forma mais robusta
        
        Args:
            subnet: Subnet a escanear
            
        Returns:
            list: Lista de impressoras encontradas
        """
        printers = []
        
        try:
            # Verifica se nmap está disponível
            try:
                result = subprocess.run(
                    ["nmap", "--version"], 
                    capture_output=True, 
                    timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower() == "windows" else 0
                )
                if result.returncode != 0:
                    return []
            except:
                logger.info("nmap não encontrado ou não funcional")
                return []
            
            logger.info(f"Escaneando {subnet} com nmap...")
            
            # Comando nmap otimizado para descoberta rápida
            cmd = [
                "nmap", 
                "-p", "631,9100,515,80,443",  # Portas de impressora
                "-T4",  # Timing template agressivo mas não muito
                "--open",  # Só portas abertas
                "-n",  # Não resolve DNS
                "--host-timeout", "30s",  # Timeout por host
                "--max-retries", "1",  # Só uma tentativa
                str(subnet)
            ]
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,  # Timeout total
                    creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower() == "windows" else 0
                )
                
                if result.returncode != 0:
                    logger.warning(f"nmap retornou código {result.returncode}")
                    return []
                    
                output = result.stdout
                
            except subprocess.TimeoutExpired:
                logger.warning("nmap timeout - rede muito grande ou lenta")
                return []
            except Exception as e:
                logger.error(f"Erro ao executar nmap: {e}")
                return []
            
            # Processa saída do nmap
            current_ip = None
            current_ports = []
            
            for line in output.split('\n'):
                line = line.strip()
                
                # Linha com IP
                if line.startswith('Nmap scan report for'):
                    # Processa IP anterior se existe
                    if current_ip and current_ports:
                        printer = self._process_nmap_result(current_ip, current_ports)
                        if printer:
                            printers.append(printer)
                    
                    # Extrai novo IP
                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                    current_ip = ip_match.group(1) if ip_match else None
                    current_ports = []
                    
                # Linha com porta aberta
                elif current_ip and '/tcp' in line and 'open' in line:
                    port_match = re.search(r'(\d+)/tcp', line)
                    if port_match:
                        current_ports.append(int(port_match.group(1)))
            
            # Processa último IP
            if current_ip and current_ports:
                printer = self._process_nmap_result(current_ip, current_ports)
                if printer:
                    printers.append(printer)
            
            logger.info(f"nmap encontrou {len(printers)} impressoras em {subnet}")
            return printers
            
        except Exception as e:
            logger.error(f"Erro no escaneamento nmap: {e}")
            return []

    def _process_nmap_result(self, ip, ports):
        """
        Processa resultado individual do nmap
        
        Args:
            ip: IP encontrado
            ports: Lista de portas abertas
            
        Returns:
            dict: Informações da impressora ou None
        """
        try:
            # Verifica se tem portas típicas de impressora
            printer_ports = [p for p in ports if p in COMMON_PRINTER_PORTS]
            
            if not printer_ports:
                return None
            
            # Obtém MAC
            mac = self._get_mac_for_ip(ip)
            
            # Determina URI
            uri = None
            if 631 in printer_ports:
                uri = f"ipp://{ip}/ipp/print"
            elif 9100 in printer_ports:
                uri = f"socket://{ip}:9100"
            elif 515 in printer_ports:
                uri = f"lpd://{ip}/queue"
            
            printer_info = {
                "ip": ip,
                "mac_address": mac,
                "ports": printer_ports,
                "uri": uri,
                "name": f"Impressora {ip}",
                "is_online": True
            }
            
            # Tenta obter detalhes adicionais se tem IPP
            if 631 in printer_ports:
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    details = loop.run_until_complete(self._get_printer_attributes(ip))
                    loop.close()
                    
                    if details and isinstance(details, dict):
                        # Merge dos detalhes
                        for key, value in details.items():
                            if value and (key not in printer_info or not printer_info[key]):
                                printer_info[key] = value
                                
                except Exception as e:
                    logger.debug(f"Não foi possível obter detalhes IPP para {ip}: {e}")
            
            return printer_info
            
        except Exception as e:
            logger.error(f"Erro ao processar resultado nmap para {ip}: {e}")
            return None
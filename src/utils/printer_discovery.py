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
        Verifica as portas de impressora em um único IP
        
        Args:
            ip: Endereço IP a verificar
            
        Returns:
            dict: Informações da impressora, ou None
        """
        open_ports = []
        
        try:
            # Verifica cada uma das portas comuns
            for port in COMMON_PRINTER_PORTS:
                if self._is_port_open(ip, port):
                    open_ports.append(port)
            
            # Se tiver alguma porta aberta que seja comum para impressoras
            if open_ports:
                mac = self._get_mac_for_ip(ip)
                
                # Determina o melhor URI para a impressora
                uri = None
                for port in open_ports:
                    if port == 631:
                        uri = f"ipp://{ip}/ipp/print"
                        break
                    elif port == 9100:
                        uri = f"socket://{ip}:9100"
                        break
                    elif port == 80:
                        uri = f"http://{ip}"
                        break
                    elif port == 443:
                        uri = f"https://{ip}"
                        break
                
                # Presume que é uma impressora se alguma porta comum estiver aberta
                printer_info = {
                    "ip": ip,
                    "mac_address": mac,
                    "ports": open_ports,
                    "uri": uri,
                    "name": f"Impressora {ip}"  # Adiciona um nome padrão baseado no IP
                }
                
                logger.info(f"Encontrada impressora com IP: {ip}, MAC: {mac}, Portas: {open_ports}")
                return printer_info
            
            return None
        except Exception as e:
            logger.error(f"Erro ao verificar portas para IP {ip}: {str(e)}")
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
    
    def _is_port_open(self, ip, port, timeout=TIMEOUT_SCAN):
        """
        Verifica se uma porta está aberta
        
        Args:
            ip: Endereço IP
            port: Número da porta
            timeout: Tempo limite em segundos
            
        Returns:
            bool: True se a porta estiver aberta
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _get_local_ip(self):
        """
        Obtém o endereço IP local da máquina
        
        Returns:
            str: Endereço IP local
        """
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
    
    def _get_network_from_ip(self, ip):
        """
        Determina a rede a partir do IP local
        
        Args:
            ip: Endereço IP
            
        Returns:
            list: Lista de redes
        """
        networks = []
        
        # Primeiro, tenta a subnet /24 do IP atual
        try:
            parts = ip.split('.')
            network = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
            networks.append(ipaddress.IPv4Network(network))
            logger.info(f"Usando rede: {network}")
        except:
            pass
        
        # Se não tiver nenhuma rede, use redes padrão comuns
        if not networks:
            fallback_networks = ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24"]
            for net in fallback_networks:
                try:
                    networks.append(ipaddress.IPv4Network(net))
                    logger.info(f"Usando rede padrão: {net}")
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
        Tenta obter o MAC de um endereço IP usando ARP
        
        Args:
            ip: Endereço IP
            
        Returns:
            str: Endereço MAC ou "desconhecido"
        """
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
                
            subprocess.call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1, creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0)
            
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
    
    def _ping_host(self, ip, timeout=1):
        """
        Faz ping em um host
        
        Args:
            ip: Endereço IP
            timeout: Tempo limite em segundos
            
        Returns:
            bool: True se o ping foi bem-sucedido
        """
        try:
            # Comando de ping depende do sistema operacional
            if sys.platform.startswith("win"):
                # Windows
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
                flags = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
            else:
                # Linux/macOS
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
                flags = 0
            
            # Executa o comando
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=timeout + 1,
                creationflags=flags
            )
            
            # Retorna True se o comando foi bem-sucedido
            return result.returncode == 0
            
        except Exception as e:
            logger.warning(f"Erro ao executar ping para {ip}: {str(e)}")
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
        Executa nmap para descobrir impressoras na rede (se disponível)
        
        Args:
            subnet: Subnet a escanear
            
        Returns:
            list: Lista de impressoras encontradas
        """
        printers = []
        
        try:
            # Verifica se o nmap está instalado
            try:
                subprocess.check_output(["nmap", "--version"], stderr=subprocess.STDOUT)
            except:
                logger.info("nmap não encontrado, usando escaneamento manual")
                return []
                
            # Define parâmetros do nmap
            logger.info(f"Escaneamento rápido de {subnet} com nmap...")
            cmd = ["nmap", "-p", "631,9100", "-T5", "--open", "-n", "--max-retries", "1", str(subnet)]
            
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
                try:
                    mac = self._get_mac_for_ip(ip)
                    
                    # Determina a melhor porta e URI para a impressora
                    uri = None
                    ports = []
                    
                    # Verifica cada porta comum
                    for port in COMMON_PRINTER_PORTS:
                        if self._is_port_open(ip, port):
                            ports.append(port)
                    
                    # Se nenhuma porta estiver aberta, pula
                    if not ports:
                        logger.warning(f"IP {ip} sem portas abertas, pulando")
                        continue
                    
                    # Determina o URI
                    if 631 in ports:
                        uri = f"ipp://{ip}/ipp/print"
                    elif 9100 in ports:
                        uri = f"socket://{ip}:9100"
                    elif 80 in ports:
                        uri = f"http://{ip}"
                    elif 443 in ports:
                        uri = f"https://{ip}"
                    
                    # Cria um objeto de impressora com os dados coletados
                    printer_info = {
                        "ip": ip, 
                        "mac_address": mac,
                        "name": f"Impressora {ip}",
                        "ports": ports,
                        "uri": uri,
                        "is_online": True,
                        "is_ready": True  # Assumimos que está pronta inicialmente
                    }
                    
                    # Tenta obter detalhes adicionais da impressora
                    try:
                        if 631 in ports:
                            logger.info(f"Tentando obter detalhes da impressora {ip}")
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            details = loop.run_until_complete(self._get_printer_attributes(ip))
                            loop.close()
                            
                            if details:
                                # Atualiza as informações com os detalhes obtidos
                                for key, value in details.items():
                                    if key not in printer_info or not printer_info[key]:
                                        printer_info[key] = value
                                
                                # Garante que o IP está definido
                                printer_info["ip"] = ip
                                logger.info(f"Detalhes obtidos para {ip}: {details.get('printer-make-and-model', 'Desconhecido')}")
                    except Exception as e:
                        logger.error(f"Erro ao obter detalhes da impressora {ip}: {str(e)}")
                    
                    logger.info(f"Impressora encontrada via nmap: {ip} (MAC: {mac}, Portas: {ports})")
                    printers.append(printer_info)
                except Exception as e:
                    logger.error(f"Erro ao processar impressora {ip}: {str(e)}")
            
            return printers
        except Exception as e:
            logger.error(f"Erro no nmap: {str(e)}")
            return []
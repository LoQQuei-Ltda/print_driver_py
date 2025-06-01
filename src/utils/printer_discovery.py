#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitário para descoberta automática de impressoras na rede - Versão Universalmente Compatível
Funciona perfeitamente em Windows 10, Windows 11, Windows Server, Linux e macOS
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
import random
import traceback
import struct

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterDiscovery")

# Configurações globais base
BASE_TIMEOUT_REQUEST = 5
BASE_TIMEOUT_SCAN = 2
BASE_TIMEOUT_PING = 3
BASE_PARALLEL_HOSTS = 10
RETRY_ATTEMPTS = 3
COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515, 8080, 8443]

# Configurações para o IPP
try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    HAS_PYIPP = False
    logger.warning("Módulo pyipp não encontrado. Informações detalhadas de impressoras não estarão disponíveis.")

class PrinterDiscovery:
    """Classe para descoberta automática de impressoras na rede - Versão Universalmente Compatível"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        
        # Detecção detalhada do Windows
        self.windows_version = self._detect_windows_version()
        self.is_server = self.windows_version.get('is_server', False)
        self.is_win10 = self.windows_version.get('is_win10', False)
        self.is_win11 = self.windows_version.get('is_win11', False)
        
        self.is_admin = self._check_admin_privileges()
        
        # Cache para MACs descobertos
        self.mac_cache = {}
        self.last_arp_update = 0
        
        # Configurações específicas do sistema
        self.config = self._setup_system_configs()
        
        logger.info(f"Sistema: {self.system}, Versão: {self.windows_version}, Admin: {self.is_admin}")
        logger.info(f"Configurações: Timeouts={self.config['timeouts']}, Parallelismo={self.config['parallel_hosts']}")
    
    def _detect_windows_version(self):
        """Detecta versão específica do Windows"""
        if not self.is_windows:
            return {'version': 'not_windows', 'is_server': False, 'is_win10': False, 'is_win11': False}
        
        version_info = {
            'version': 'unknown',
            'is_server': False,
            'is_win10': False,
            'is_win11': False,
            'build': 0
        }
        
        try:
            # Método 1: Registry
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            
            product_name = winreg.QueryValueEx(key, "ProductName")[0]
            current_build = winreg.QueryValueEx(key, "CurrentBuild")[0]
            
            try:
                display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
            except:
                display_version = ""
            
            winreg.CloseKey(key)
            
            version_info['version'] = product_name
            version_info['build'] = int(current_build)
            version_info['is_server'] = "server" in product_name.lower()
            
            # Windows 10: builds 10240-19044
            # Windows 11: builds 22000+
            if version_info['build'] >= 22000:
                version_info['is_win11'] = True
            elif version_info['build'] >= 10240:
                version_info['is_win10'] = True
            
            logger.info(f"Windows detectado: {product_name}, Build: {current_build}, DisplayVersion: {display_version}")
            
        except Exception as e:
            logger.warning(f"Erro detectando versão do Windows via registry: {str(e)}")
            
            # Método 2: WMIC como fallback
            try:
                result = subprocess.run(
                    ["wmic", "os", "get", "Caption,Version,ProductType", "/value"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    if "Windows 10" in output:
                        version_info['is_win10'] = True
                        version_info['version'] = "Windows 10"
                    elif "Windows 11" in output:
                        version_info['is_win11'] = True
                        version_info['version'] = "Windows 11"
                    
                    if "ProductType=3" in output:
                        version_info['is_server'] = True
                        
            except Exception as e2:
                logger.warning(f"Erro detectando versão do Windows via WMIC: {str(e2)}")
        
        return version_info
    
    def _setup_system_configs(self):
        """Configura timeouts e parâmetros específicos do sistema"""
        config = {
            'timeouts': {
                'request': BASE_TIMEOUT_REQUEST,
                'scan': BASE_TIMEOUT_SCAN,
                'ping': BASE_TIMEOUT_PING
            },
            'parallel_hosts': BASE_PARALLEL_HOSTS,
            'arp_method': 'standard',
            'ping_method': 'standard',
            'socket_method': 'standard'
        }
        
        if self.is_windows:
            if self.is_server:
                # Windows Server: mais conservador
                config['timeouts'] = {
                    'request': 8,
                    'scan': 4,
                    'ping': 6
                }
                config['parallel_hosts'] = 6
                config['arp_method'] = 'robust'
                
            elif self.is_win10:
                # Windows 10: configurações específicas
                config['timeouts'] = {
                    'request': 6,
                    'scan': 3,
                    'ping': 4
                }
                config['parallel_hosts'] = 8
                config['arp_method'] = 'win10_specific'
                config['ping_method'] = 'win10_specific'
                config['socket_method'] = 'win10_specific'
                
            elif self.is_win11:
                # Windows 11: configurações otimizadas
                config['timeouts'] = {
                    'request': 5,
                    'scan': 2,
                    'ping': 3
                }
                config['parallel_hosts'] = 12
                config['arp_method'] = 'modern'
        
        return config
    
    def _check_admin_privileges(self):
        """Verifica se tem privilégios de administrador"""
        try:
            if self.is_windows:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            else:
                return os.geteuid() == 0
        except:
            return False
    
    def normalize_mac(self, mac):
        """Normaliza o formato do MAC para comparação"""
        if not mac or mac == "desconhecido":
            return None
            
        # Remove todos os separadores e converte para minúsculas
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', str(mac).lower())
        
        # Verifica se o MAC está completo (12 caracteres hexadecimais)
        if len(clean_mac) != 12:
            logger.warning(f"MAC incompleto: {mac} ({len(clean_mac)} caracteres)")
            if len(clean_mac) < 12:
                return None  # MAC muito incompleto, descartar
        
        # Usa apenas os primeiros 12 caracteres se for maior
        clean_mac = clean_mac[:12]
        
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
            logger.info("Iniciando descoberta de impressoras...")
            
            # Força atualização do cache ARP primeiro
            self._force_arp_refresh()
            
            # Executa a varredura de forma síncrona
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                _, printers = loop.run_until_complete(self._scan_network(subnet))
            finally:
                loop.close()
            
            # Filtra e valida impressoras
            valid_printers = self._filter_valid_printers(printers)
            
            logger.info(f"Descoberta concluída: {len(valid_printers)} impressoras válidas encontradas")
            self.printers = valid_printers
            return valid_printers
        except Exception as e:
            logger.error(f"Erro na descoberta de impressoras: {str(e)}")
            logger.error(traceback.format_exc())
            return []
    
    def _force_arp_refresh(self):
        """Força atualização do cache ARP usando múltiplos métodos"""
        logger.info("Forçando atualização do cache ARP...")
        
        try:
            # Método 1: Limpa cache ARP existente (Windows)
            if self.is_windows:
                try:
                    subprocess.run(
                        ["arp", "-d", "*"], 
                        capture_output=True, 
                        timeout=5,
                        creationflags=subprocess.CREATE_NO_WINDOW
                    )
                except:
                    pass
            
            # Método 2: Faz ping broadcast na rede local
            networks = self._get_local_networks()
            for network in networks[:2]:  # Limita a 2 redes para não demorar muito
                broadcast_ip = str(network.broadcast_address)
                self._ping_host(broadcast_ip, 1)
            
            # Método 3: Atualiza cache ARP convencional
            self._update_arp_cache()
            
        except Exception as e:
            logger.warning(f"Erro forçando refresh ARP: {str(e)}")
    
    def _filter_valid_printers(self, printers):
        """Filtra e valida impressoras encontradas"""
        valid_printers = []
        seen_ips = set()
        
        for printer in printers:
            if not printer or not isinstance(printer, dict):
                continue
                
            ip = printer.get("ip")
            if not ip or ip in seen_ips:
                continue
                
            # Valida IP
            try:
                ipaddress.IPv4Address(ip)
            except:
                logger.warning(f"IP inválido ignorado: {ip}")
                continue
            
            # Verifica se tem pelo menos uma porta de impressora
            ports = printer.get("ports", [])
            if not ports:
                logger.warning(f"Impressora sem portas válidas ignorada: {ip}")
                continue
            
            # Normaliza MAC
            mac = self.normalize_mac(printer.get("mac_address", ""))
            if mac:
                printer["mac_address"] = mac
            else:
                printer["mac_address"] = "desconhecido"
            
            # Garante campos obrigatórios
            if "name" not in printer or not printer["name"]:
                printer["name"] = f"Impressora {ip}"
            
            valid_printers.append(printer)
            seen_ips.add(ip)
            
        return valid_printers
    
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
            
        logger.info(f"Obtendo detalhes da impressora: {ip}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            details = loop.run_until_complete(self._get_printer_attributes(ip))
        finally:
            loop.close()
        
        return details
    
    async def _scan_network(self, subnet=None):
        """
        Escaneia a rede para encontrar impressoras
        
        Args:
            subnet: Subnet específica para escanear
            
        Returns:
            tuple: (None, lista de impressoras)
        """
        all_printers = []
        
        try:
            # Determina as redes a escanear
            networks = self._get_networks_to_scan(subnet)
            
            for network in networks:
                logger.info(f"Escaneando rede: {network}")
                
                # Método 1: Tenta usar nmap se disponível
                nmap_printers = self._run_nmap_scan(network)
                if nmap_printers:
                    logger.info(f"NMAP encontrou {len(nmap_printers)} dispositivos em {network}")
                    all_printers.extend(nmap_printers)
                else:
                    # Método 2: Escaneamento manual
                    logger.info(f"NMAP não disponível ou falhou, usando escaneamento manual para {network}")
                    manual_printers = await self._manual_network_scan(network)
                    all_printers.extend(manual_printers)
        
        except Exception as e:
            logger.error(f"Erro no escaneamento de rede: {str(e)}")
            logger.error(traceback.format_exc())
        
        # Deduplica os resultados
        unique_printers = self._deduplicate_printers(all_printers)
        return None, unique_printers
    
    def _get_networks_to_scan(self, subnet=None):
        """Determina as redes a serem escaneadas"""
        networks = []
        
        if subnet:
            try:
                networks = [ipaddress.IPv4Network(subnet, strict=False)]
                logger.info(f"Usando subnet especificada: {subnet}")
            except Exception as e:
                logger.warning(f"Erro ao processar subnet {subnet}: {str(e)}")
                networks = self._get_local_networks()
        else:
            networks = self._get_local_networks()
        
        return networks
    
    def _get_local_networks(self):
        """Obtém as redes locais para escanear - Versão ultra-robusta"""
        networks = []
        
        # Método 1: Detecta todas as interfaces de rede
        local_ips = self._get_all_local_ips()
        
        for local_ip in local_ips:
            if local_ip and not local_ip.startswith('127.'):
                try:
                    network = self._detect_network_for_ip(local_ip)
                    if network and network not in networks:
                        networks.append(network)
                        logger.info(f"Rede detectada para {local_ip}: {network}")
                except Exception as e:
                    logger.warning(f"Erro detectando rede para {local_ip}: {str(e)}")
        
        # Método 2: Windows 10 específico - usa comando route
        if self.is_win10:
            win10_networks = self._get_win10_networks()
            for network in win10_networks:
                if network not in networks:
                    networks.append(network)
                    logger.info(f"Rede Win10 detectada: {network}")
        
        # Método 3: Fallback baseado em gateway padrão
        if not networks:
            gateway_networks = self._get_networks_from_gateway()
            networks.extend(gateway_networks)
        
        # Método 4: Fallback final - redes comuns
        if not networks:
            logger.info("Usando redes comuns como fallback")
            common_networks = [
                "192.168.1.0/24", "192.168.0.0/24", "192.168.2.0/24",
                "10.0.0.0/24", "10.0.1.0/24", "172.16.0.0/24",
                "192.168.10.0/24", "192.168.100.0/24", "192.168.254.0/24"
            ]
            for net_str in common_networks:
                try:
                    networks.append(ipaddress.IPv4Network(net_str))
                except:
                    pass
        
        return networks
    
    def _get_win10_networks(self):
        """Método específico para detectar redes no Windows 10"""
        networks = []
        
        try:
            # Comando route específico para Windows 10
            result = subprocess.run(
                ["route", "print", "-4"],
                capture_output=True, text=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                # Processa a tabela de rotas
                in_table = False
                for line in result.stdout.split('\n'):
                    line = line.strip()
                    
                    if "Network Destination" in line:
                        in_table = True
                        continue
                    
                    if in_table and line:
                        # Formato: Network Destination    Netmask    Gateway    Interface    Metric
                        parts = line.split()
                        if len(parts) >= 4:
                            dest = parts[0]
                            netmask = parts[1]
                            interface = parts[3]
                            
                            # Pula rota padrão e loopback
                            if dest in ['0.0.0.0', '127.0.0.1'] or interface.startswith('127.'):
                                continue
                            
                            try:
                                # Converte netmask para CIDR
                                if '.' in netmask:
                                    cidr = self._netmask_to_cidr(netmask)
                                    if cidr and dest != '0.0.0.0':
                                        network_str = f"{dest}/{cidr}"
                                        network = ipaddress.IPv4Network(network_str, strict=False)
                                        networks.append(network)
                            except:
                                continue
                                
        except Exception as e:
            logger.warning(f"Erro detectando redes Win10: {str(e)}")
        
        return networks
    
    def _netmask_to_cidr(self, netmask):
        """Converte netmask para notação CIDR"""
        try:
            return ipaddress.IPv4Network(f"0.0.0.0/{netmask}").prefixlen
        except:
            # Conversão manual para netmasks comuns
            netmask_map = {
                '255.255.255.0': 24,
                '255.255.0.0': 16,
                '255.0.0.0': 8,
                '255.255.255.128': 25,
                '255.255.255.192': 26,
                '255.255.255.224': 27,
                '255.255.255.240': 28,
                '255.255.255.248': 29,
                '255.255.255.252': 30
            }
            return netmask_map.get(netmask)
    
    def _get_networks_from_gateway(self):
        """Detecta redes baseado no gateway padrão"""
        networks = []
        
        try:
            if self.is_windows:
                result = subprocess.run(
                    ["ipconfig"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    gateway_pattern = r'Default Gateway.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                    gateways = re.findall(gateway_pattern, result.stdout, re.IGNORECASE)
                    
                    for gateway in gateways:
                        if not gateway.startswith('169.254.'):  # Pula APIPA
                            # Assume rede /24 baseada no gateway
                            parts = gateway.split('.')
                            if len(parts) == 4:
                                network_addr = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                                try:
                                    networks.append(ipaddress.IPv4Network(network_addr))
                                except:
                                    pass
        except:
            pass
        
        return networks
    
    def _get_all_local_ips(self):
        """Obtém todos os IPs locais da máquina - Versão aprimorada"""
        local_ips = []
        
        try:
            # Método 1: socket.getaddrinfo (mais confiável)
            hostname = socket.gethostname()
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if not ip.startswith('127.') and '::' not in ip and not ip.startswith('169.254.'):
                    local_ips.append(ip)
        except:
            pass
        
        try:
            # Método 2: Conecta a diferentes IPs externos
            external_ips = ["8.8.8.8", "1.1.1.1", "208.67.222.222", "4.4.4.4"]
            for ext_ip in external_ips:
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                        s.settimeout(3)
                        s.connect((ext_ip, 80))
                        local_ip = s.getsockname()[0]
                        if local_ip and not local_ip.startswith('127.') and not local_ip.startswith('169.254.'):
                            local_ips.append(local_ip)
                except:
                    continue
        except:
            pass
        
        try:
            # Método 3: Comando específico do sistema
            if self.is_windows:
                result = subprocess.run(
                    ["ipconfig", "/all"], capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                if result.returncode == 0:
                    # Procura IPs IPv4 ativos
                    patterns = [
                        r'IPv4 Address.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})',
                        r'IP Address.*?(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
                    ]
                    
                    for pattern in patterns:
                        ips = re.findall(pattern, result.stdout, re.IGNORECASE)
                        for ip in ips:
                            if not ip.startswith('127.') and not ip.startswith('169.254.'):
                                local_ips.append(ip)
            else:
                result = subprocess.run(
                    ["ip", "addr", "show"], capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0:
                    ips = re.findall(r'inet (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', result.stdout)
                    for ip in ips:
                        if not ip.startswith('127.') and not ip.startswith('169.254.'):
                            local_ips.append(ip)
        except:
            pass
        
        # Remove duplicatas e ordena
        unique_ips = list(set(local_ips))
        logger.info(f"IPs locais detectados: {unique_ips}")
        return unique_ips
    
    def _detect_network_for_ip(self, ip):
        """Detecta a rede para um IP específico"""
        try:
            # Assume rede /24 como padrão mais comum
            ip_parts = ip.split('.')
            if len(ip_parts) == 4:
                network_addr = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.0/24"
                return ipaddress.IPv4Network(network_addr)
                
        except Exception as e:
            logger.debug(f"Erro detectando rede para {ip}: {str(e)}")
        
        return None
    
    async def _manual_network_scan(self, network):
        """Escaneamento manual da rede - Versão otimizada para Windows 10"""
        printers = []
        
        try:
            # Windows 10: Estratégia mais agressiva de descoberta
            if self.is_win10:
                printers = await self._win10_optimized_scan(network)
            else:
                printers = await self._standard_network_scan(network)
                
        except Exception as e:
            logger.error(f"Erro no escaneamento manual: {str(e)}")
        
        return printers
    
    async def _win10_optimized_scan(self, network):
        """Escaneamento otimizado específico para Windows 10"""
        printers = []
        
        # Passo 1: Verifica IPs do cache ARP
        arp_ips = [ip for ip in self.mac_cache.keys() if ipaddress.IPv4Address(ip) in network]
        if arp_ips:
            logger.info(f"Windows 10: Verificando {len(arp_ips)} IPs do cache ARP...")
            arp_printers = await self._scan_ip_list(arp_ips)
            printers.extend(arp_printers)
        
        # Passo 2: Escaneamento de IPs comuns (mais agressivo para Win10)
        common_ips = self._get_extended_common_ips(network)
        common_ips = [ip for ip in common_ips if ip not in arp_ips]
        if common_ips:
            logger.info(f"Windows 10: Escaneando {len(common_ips)} IPs comuns...")
            common_printers = await self._scan_ip_list(common_ips)
            printers.extend(common_printers)
        
        # Passo 3: Se ainda não encontrou suficientes, escaneamento completo
        if len(printers) < 2:
            logger.info("Windows 10: Escaneamento completo da rede...")
            all_hosts = list(network.hosts())
            scanned_ips = set(arp_ips + common_ips)
            remaining_ips = [str(ip) for ip in all_hosts if str(ip) not in scanned_ips]
            
            if remaining_ips:
                # Para Windows 10, escaneia mais IPs
                if len(remaining_ips) > 100:
                    # Usa amostragem inteligente
                    sample_size = min(80, len(remaining_ips))
                    remaining_ips = random.sample(remaining_ips, sample_size)
                
                logger.info(f"Windows 10: Escaneando {len(remaining_ips)} IPs adicionais...")
                additional_printers = await self._scan_ip_list(remaining_ips)
                printers.extend(additional_printers)
        
        return printers
    
    async def _standard_network_scan(self, network):
        """Escaneamento padrão para outros sistemas"""
        printers = []
        
        # Estratégia em camadas padrão
        arp_ips = [ip for ip in self.mac_cache.keys() if ipaddress.IPv4Address(ip) in network]
        if arp_ips:
            logger.info(f"Verificando {len(arp_ips)} IPs do cache ARP...")
            arp_printers = await self._scan_ip_list(arp_ips)
            printers.extend(arp_printers)
        
        common_ips = self._get_common_printer_ips(network)
        common_ips = [ip for ip in common_ips if ip not in arp_ips]
        if common_ips:
            logger.info(f"Escaneando {len(common_ips)} IPs comuns...")
            common_printers = await self._scan_ip_list(common_ips)
            printers.extend(common_printers)
        
        if len(printers) < 3:
            all_hosts = list(network.hosts())
            if len(all_hosts) > 50:
                scanned_ips = set(arp_ips + common_ips)
                remaining_ips = [str(ip) for ip in all_hosts if str(ip) not in scanned_ips]
                
                sample_size = min(30, len(remaining_ips))
                extended_ips = random.sample(remaining_ips, sample_size)
                
                if extended_ips:
                    logger.info(f"Expandindo busca para {len(extended_ips)} IPs...")
                    extended_printers = await self._scan_ip_list(extended_ips)
                    printers.extend(extended_printers)
        
        return printers
    
    def _get_extended_common_ips(self, network):
        """Gera lista estendida de IPs comuns para Windows 10"""
        common_ips = []
        
        try:
            # IPs mais comuns para Windows 10 (expandido)
            common_suffixes = [
                1, 2, 3, 4, 5, 10, 11, 12, 13, 14, 15, 20, 21, 22, 23, 24, 25,
                30, 31, 32, 40, 41, 42, 50, 51, 52, 53, 54, 55, 60, 61, 62,
                70, 71, 72, 80, 81, 82, 90, 91, 92, 100, 101, 102, 103, 104, 105,
                110, 111, 112, 120, 121, 122, 130, 131, 132, 140, 141, 142,
                150, 151, 152, 160, 161, 162, 170, 171, 172, 180, 181, 182,
                190, 191, 192, 200, 201, 202, 203, 204, 205, 210, 211, 212,
                220, 221, 222, 230, 231, 232, 240, 241, 242, 250, 251, 252, 253, 254
            ]
            
            network_addr = network.network_address
            for suffix in common_suffixes:
                try:
                    ip = str(network_addr + suffix)
                    if ipaddress.IPv4Address(ip) in network:
                        common_ips.append(ip)
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Erro ao gerar IPs comuns: {str(e)}")
        
        return common_ips
    
    def _get_common_printer_ips(self, network):
        """Gera lista de IPs comuns para impressoras"""
        common_ips = []
        
        try:
            # IPs com finais típicos de impressoras
            common_suffixes = [
                1, 2, 3, 10, 11, 12, 20, 21, 22, 30, 31, 32, 
                50, 51, 52, 100, 101, 102, 103, 110, 111, 112,
                150, 151, 152, 200, 201, 202, 250, 251, 252, 253, 254
            ]
            
            network_addr = network.network_address
            for suffix in common_suffixes:
                try:
                    ip = str(network_addr + suffix)
                    if ipaddress.IPv4Address(ip) in network:
                        common_ips.append(ip)
                except:
                    continue
                    
        except Exception as e:
            logger.warning(f"Erro ao gerar IPs comuns: {str(e)}")
        
        return common_ips
    
    async def _scan_ip_list(self, ip_list):
        """Escaneia uma lista de IPs - Versão adaptativa"""
        printers = []
        
        # Ajusta chunk size baseado no sistema
        chunk_size = self.config['parallel_hosts']
        
        for i in range(0, len(ip_list), chunk_size):
            chunk = ip_list[i:i+chunk_size]
            
            # Cria tasks para este chunk
            tasks = [self._scan_single_ip(ip) for ip in chunk]
            
            try:
                # Timeout baseado na configuração do sistema
                base_timeout = self.config['timeouts']['scan']
                timeout = base_timeout * len(chunk) + 10
                
                chunk_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=timeout
                )
                
                for result in chunk_results:
                    if isinstance(result, dict) and result:
                        printers.append(result)
                        logger.info(f"Impressora encontrada: {result['ip']} - Portas: {result.get('ports', [])}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout no escaneamento do chunk {i//chunk_size + 1}")
            except Exception as e:
                logger.warning(f"Erro no chunk {i//chunk_size + 1}: {str(e)}")
            
            # Pausa entre chunks (menor para Win10)
            if i + chunk_size < len(ip_list):
                pause = 0.1 if not self.is_win10 else 0.05
                await asyncio.sleep(pause)
        
        return printers
    
    async def _scan_single_ip(self, ip):
        """Escaneia um único IP para verificar se é impressora"""
        try:
            # Ping com timeout baseado na configuração
            ping_timeout = self.config['timeouts']['ping']
            if not self._ping_host(ip, ping_timeout):
                return None
            
            # Verifica portas de impressora
            open_ports = []
            port_tasks = [self._check_port_async(ip, port) for port in COMMON_PRINTER_PORTS]
            
            try:
                scan_timeout = self.config['timeouts']['scan']
                port_timeout = scan_timeout * len(COMMON_PRINTER_PORTS) + 5
                
                port_results = await asyncio.wait_for(
                    asyncio.gather(*port_tasks, return_exceptions=True),
                    timeout=port_timeout
                )
                
                for i, result in enumerate(port_results):
                    if result is True:
                        open_ports.append(COMMON_PRINTER_PORTS[i])
                        
            except asyncio.TimeoutError:
                logger.debug(f"Timeout verificando portas de {ip}")
                return None
            
            # Se não tem portas de impressora abertas, não é impressora
            if not open_ports:
                return None
            
            # Verifica se realmente parece ser uma impressora
            if not self._looks_like_printer(ip, open_ports):
                return None
            
            # Obtém MAC address
            mac = self._get_mac_for_ip(ip)
            
            # Cria informações da impressora
            printer_info = {
                "ip": ip,
                "mac_address": mac,
                "ports": open_ports,
                "uri": self._determine_uri(ip, open_ports),
                "name": f"Impressora {ip}",
                "is_online": True
            }
            
            return printer_info
            
        except Exception as e:
            logger.debug(f"Erro escaneando {ip}: {str(e)}")
            return None
    
    async def _check_port_async(self, ip, port):
        """Verifica uma porta de forma assíncrona"""
        try:
            scan_timeout = self.config['timeouts']['scan']
            future = asyncio.get_event_loop().run_in_executor(
                None, self._is_port_open, ip, port, scan_timeout
            )
            return await asyncio.wait_for(future, timeout=scan_timeout + 2)
        except:
            return False
    
    def _looks_like_printer(self, ip, open_ports):
        """Verifica se o dispositivo parece ser uma impressora"""
        # Se tem porta IPP ou JetDirect, provavelmente é impressora
        if 631 in open_ports or 9100 in open_ports:
            return True
        
        # Se tem apenas HTTP/HTTPS, verifica melhor
        if open_ports == [80] or open_ports == [443] or set(open_ports) == {80, 443}:
            return self._check_http_printer_indicators(ip, open_ports)
        
        # Se tem LPD, provavelmente é impressora
        if 515 in open_ports:
            return True
            
        # Se tem múltiplas portas típicas de impressora
        if len(open_ports) >= 2:
            return True
        
        return False
    
    def _check_http_printer_indicators(self, ip, open_ports):
        """Verifica indicadores HTTP de que é uma impressora"""
        try:
            port = 80 if 80 in open_ports else 443
            protocol = "http" if port == 80 else "https"
            url = f"{protocol}://{ip}:{port}"
            
            # Importa apenas quando necessário
            import urllib.request
            import urllib.error
            import ssl
            
            # Cria contexto SSL que aceita certificados auto-assinados
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'PrinterDiscovery/1.0')
            
            # Timeout baseado na configuração
            timeout = self.config['timeouts']['request']
            
            with urllib.request.urlopen(req, timeout=timeout, context=ctx) as response:
                content = response.read().decode('utf-8', errors='ignore').lower()
                
                # Palavras-chave que indicam impressora (expandido)
                printer_keywords = [
                    'printer', 'print', 'toner', 'cartridge', 'ink', 'drum',
                    'samsung', 'hp', 'canon', 'epson', 'brother', 'lexmark',
                    'xerox', 'kyocera', 'ricoh', 'sharp', 'konica', 'dell',
                    'status', 'supplies', 'maintenance', 'queue', 'job',
                    'laserjet', 'deskjet', 'officejet', 'imageclass',
                    'workforce', 'stylus', 'colorlaserjet', 'pagewide'
                ]
                
                return any(keyword in content for keyword in printer_keywords)
                
        except Exception as e:
            logger.debug(f"Erro verificando HTTP para {ip}: {str(e)}")
            return False
    
    def _determine_uri(self, ip, open_ports):
        """Determina o melhor URI para a impressora"""
        if 631 in open_ports:
            return f"ipp://{ip}/ipp/print"
        elif 9100 in open_ports:
            return f"socket://{ip}:9100"
        elif 515 in open_ports:
            return f"lpd://{ip}/queue"
        elif 443 in open_ports:
            return f"https://{ip}"
        elif 80 in open_ports:
            return f"http://{ip}"
        else:
            return f"ipp://{ip}/ipp/print"  # Fallback
    
    def _deduplicate_printers(self, printers):
        """Remove impressoras duplicadas"""
        unique_printers = []
        seen_ips = set()
        seen_macs = set()
        
        for printer in printers:
            if not printer:
                continue
                
            ip = printer.get("ip")
            mac = printer.get("mac_address")
            
            # Pula se IP já foi visto
            if ip in seen_ips:
                continue
                
            # Se tem MAC válido e já foi visto, pula
            if mac and mac != "desconhecido" and mac in seen_macs:
                continue
            
            unique_printers.append(printer)
            seen_ips.add(ip)
            if mac and mac != "desconhecido":
                seen_macs.add(mac)
        
        return unique_printers
    
    def _update_arp_cache(self):
        """Atualiza o cache ARP - Versão específica por sistema"""
        current_time = time.time()
        
        # Só atualiza se passou mais de 30 segundos (20s para Win10)
        min_interval = 20 if self.is_win10 else 30
        if current_time - self.last_arp_update < min_interval:
            return
        
        try:
            logger.info("Atualizando cache ARP...")
            old_cache_size = len(self.mac_cache)
            
            # Método específico baseado na configuração
            if self.config['arp_method'] == 'win10_specific':
                self._update_arp_cache_win10()
            else:
                self._update_arp_cache_standard()
                
            self.last_arp_update = current_time
            new_cache_size = len(self.mac_cache)
            logger.info(f"Cache ARP atualizado: {old_cache_size} -> {new_cache_size} entradas")
            
        except Exception as e:
            logger.warning(f"Erro ao atualizar cache ARP: {str(e)}")
    
    def _update_arp_cache_win10(self):
        """Atualização específica do cache ARP para Windows 10"""
        try:
            # Método 1: arp -a
            result = subprocess.run(
                ['arp', '-a'],
                capture_output=True, text=True, timeout=8,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            if result.returncode == 0:
                self._parse_arp_output(result.stdout)
            
            # Método 2: netsh (específico Win10)
            try:
                result = subprocess.run(
                    ['netsh', 'interface', 'ip', 'show', 'neighbors'],
                    capture_output=True, text=True, timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                
                if result.returncode == 0:
                    self._parse_netsh_output(result.stdout)
            except:
                pass
                
        except Exception as e:
            logger.warning(f"Erro atualizando cache ARP Win10: {str(e)}")
    
    def _update_arp_cache_standard(self):
        """Atualização padrão do cache ARP"""
        try:
            if self.is_windows:
                cmd = ['arp', '-a']
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                cmd = ['arp', '-a']
                creation_flags = 0
            
            timeout = self.config['timeouts']['request']
            
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout,
                creationflags=creation_flags
            )
            
            if result.returncode == 0:
                self._parse_arp_output(result.stdout)
            else:
                logger.warning(f"Comando ARP falhou com código {result.returncode}")
                
        except subprocess.TimeoutExpired:
            logger.warning("Timeout ao executar comando ARP")
        except Exception as e:
            logger.warning(f"Erro ao atualizar cache ARP: {str(e)}")
    
    def _parse_netsh_output(self, output):
        """Processa saída do comando netsh (Windows 10)"""
        try:
            for line in output.split('\n'):
                line = line.strip()
                
                # Formato netsh: "Interface: Local Area Connection"
                # Seguido por: "Internet Address      Physical Address      Type"
                # E dados: "192.168.1.1           00-11-22-33-44-55     dynamic"
                
                if re.match(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', line):
                    parts = line.split()
                    if len(parts) >= 2:
                        ip = parts[0]
                        mac_raw = parts[1]
                        
                        mac = self.normalize_mac(mac_raw)
                        if mac and ip:
                            self.mac_cache[ip] = mac
                            
        except Exception as e:
            logger.warning(f"Erro processando saída netsh: {str(e)}")
    
    def _parse_arp_output(self, output):
        """Processa a saída do comando ARP - Versão robusta"""
        try:
            # Múltiplos padrões para diferentes formatos
            patterns = [
                # Windows padrão: "  192.168.1.1          00-11-22-33-44-55     dynamic"
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})',
                # Windows formato alternativo
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2})',
                # Linux/Unix: formato com "ether"
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}).*?ether\s+([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})',
                # Formato genérico
                r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s.*?([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})'
            ]
            
            for line in output.split('\n'):
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        ip = match.group(1)
                        mac = self.normalize_mac(match.group(2))
                        if mac and ip:
                            self.mac_cache[ip] = mac
                            break
                        
        except Exception as e:
            logger.warning(f"Erro ao processar saída ARP: {str(e)}")
    
    def _get_mac_for_ip(self, ip):
        """Obtém MAC address para um IP - Versão robusta"""
        # Primeiro verifica cache
        if ip in self.mac_cache:
            return self.mac_cache[ip]
        
        # Faz ping para atualizar ARP
        ping_timeout = self.config['timeouts']['ping']
        self._ping_host(ip, ping_timeout)
        time.sleep(0.3 if self.is_win10 else 0.2)
        
        # Tenta obter MAC usando múltiplos métodos
        for attempt in range(RETRY_ATTEMPTS):
            mac = self._query_mac_from_arp(ip)
            if mac and mac != "desconhecido":
                self.mac_cache[ip] = mac
                return mac
            
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(0.4 if self.is_win10 else 0.3)
        
        return "desconhecido"
    
    def _query_mac_from_arp(self, ip):
        """Consulta MAC da tabela ARP"""
        try:
            if self.is_windows:
                cmd = ['arp', '-a', ip]
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                cmd = ['arp', '-n', ip]
                creation_flags = 0
            
            timeout = self.config['timeouts']['scan'] + 1
            
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout,
                creationflags=creation_flags
            )
            
            if result.returncode == 0:
                # Múltiplos padrões para encontrar MAC
                mac_patterns = [
                    r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})',
                    r'([0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2}-[0-9A-Fa-f]{2})'
                ]
                
                for pattern in mac_patterns:
                    match = re.search(pattern, result.stdout, re.IGNORECASE)
                    if match:
                        return self.normalize_mac(match.group(1))
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout consultando MAC para {ip}")
        except Exception as e:
            logger.debug(f"Erro consultando MAC para {ip}: {str(e)}")
        
        return "desconhecido"
    
    def _is_port_open(self, ip, port, timeout=1):
        """Verifica se uma porta está aberta - Versão específica por sistema"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                
                # Método específico para Windows 10
                if self.config['socket_method'] == 'win10_specific':
                    return self._is_port_open_win10(sock, ip, port, timeout)
                else:
                    result = sock.connect_ex((ip, port))
                    return result == 0
                    
        except Exception as e:
            logger.debug(f"Erro verificando porta {port} em {ip}: {str(e)}")
            return False
    
    def _is_port_open_win10(self, sock, ip, port, timeout):
        """Método específico de verificação de porta para Windows 10"""
        try:
            # Windows 10: usa método não-bloqueante mais confiável
            sock.setblocking(False)
            
            try:
                sock.connect((ip, port))
                return True
            except socket.error as e:
                if e.errno == 10035:  # WSAEWOULDBLOCK
                    # Socket em modo não-bloqueante, usa select
                    import select
                    _, ready, error = select.select([], [sock], [sock], timeout)
                    if ready:
                        return True
                    elif error:
                        return False
                    else:
                        return False  # Timeout
                elif e.errno == 10056:  # WSAEISCONN - já conectado
                    return True
                else:
                    return False
        except:
            return False
    
    def _ping_host(self, ip, timeout=1):
        """Faz ping em um host - Versão específica por sistema"""
        try:
            if self.config['ping_method'] == 'win10_specific':
                return self._ping_host_win10(ip, timeout)
            else:
                return self._ping_host_standard(ip, timeout)
                
        except Exception as e:
            logger.debug(f"Erro fazendo ping em {ip}: {str(e)}")
            return False
    
    def _ping_host_win10(self, ip, timeout):
        """Ping específico para Windows 10"""
        try:
            # Windows 10: usa parâmetros mais agressivos
            cmd = ["ping", "-n", "2", "-w", str(int(timeout * 800)), ip]
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout + 3,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout fazendo ping Win10 em {ip}")
            return False
    
    def _ping_host_standard(self, ip, timeout):
        """Ping padrão para outros sistemas"""
        try:
            if self.is_windows:
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
                creation_flags = 0
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=timeout + 2,
                creationflags=creation_flags
            )
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout fazendo ping em {ip}")
            return False
    
    def _run_nmap_scan(self, subnet):
        """Executa nmap para descoberta rápida - Versão específica por sistema"""
        try:
            # Verifica se nmap está disponível
            result = subprocess.run(
                ["nmap", "--version"],
                capture_output=True, timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            )
            if result.returncode != 0:
                return []
        except:
            logger.info("nmap não disponível")
            return []
        
        try:
            logger.info(f"Executando nmap em {subnet}...")
            
            # Parâmetros específicos por sistema
            if self.is_win10:
                cmd = [
                    "nmap",
                    "-p", "631,9100,80,443,515",
                    "-T4",  # Mais agressivo para Win10
                    "--open",
                    "-n",
                    "--host-timeout", "8s",
                    "--max-retries", "2",
                    "--min-rate", "100",  # Adicional para Win10
                    str(subnet)
                ]
                timeout = 90
            elif self.is_server:
                cmd = [
                    "nmap",
                    "-p", "631,9100,80,443,515",
                    "-T3",
                    "--open",
                    "-n",
                    "--host-timeout", "20s",
                    "--max-retries", "2",
                    str(subnet)
                ]
                timeout = 120
            else:
                cmd = [
                    "nmap",
                    "-p", "631,9100,80,443,515",
                    "-T4",
                    "--open",
                    "-n",
                    "--host-timeout", "10s",
                    "--max-retries", "1",
                    str(subnet)
                ]
                timeout = 60
            
            result = subprocess.run(
                cmd,
                capture_output=True, text=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            )
            
            if result.returncode != 0:
                logger.warning(f"nmap falhou com código {result.returncode}")
                return []
            
            return self._parse_nmap_output(result.stdout)
            
        except subprocess.TimeoutExpired:
            logger.warning("Timeout executando nmap")
            return []
        except Exception as e:
            logger.warning(f"Erro executando nmap: {str(e)}")
            return []
    
    def _parse_nmap_output(self, output):
        """Processa saída do nmap"""
        printers = []
        current_ip = None
        current_ports = []
        
        try:
            for line in output.split('\n'):
                line = line.strip()
                
                # Linha com IP
                if line.startswith('Nmap scan report for'):
                    # Processa IP anterior se existe
                    if current_ip and current_ports:
                        printer = self._create_printer_from_nmap(current_ip, current_ports)
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
                        port = int(port_match.group(1))
                        if port in COMMON_PRINTER_PORTS:
                            current_ports.append(port)
            
            # Processa último IP
            if current_ip and current_ports:
                printer = self._create_printer_from_nmap(current_ip, current_ports)
                if printer:
                    printers.append(printer)
                    
        except Exception as e:
            logger.error(f"Erro processando saída nmap: {str(e)}")
        
        return printers
    
    def _create_printer_from_nmap(self, ip, ports):
        """Cria informações de impressora a partir do resultado nmap"""
        try:
            # Obtém MAC
            mac = self._get_mac_for_ip(ip)
            
            printer_info = {
                "ip": ip,
                "mac_address": mac,
                "ports": ports,
                "uri": self._determine_uri(ip, ports),
                "name": f"Impressora {ip}",
                "is_online": True
            }
            
            return printer_info
            
        except Exception as e:
            logger.warning(f"Erro criando impressora para {ip}: {str(e)}")
            return None
    
    def discover_printer_by_mac(self, target_mac):
        """
        Descobre impressora por MAC address
        
        Args:
            target_mac: MAC address da impressora
            
        Returns:
            dict: Informações da impressora ou None
        """
        normalized_mac = self.normalize_mac(target_mac)
        if not normalized_mac:
            logger.warning(f"MAC inválido: {target_mac}")
            return None
        
        logger.info(f"Procurando impressora com MAC: {normalized_mac}")
        
        # Força atualização do cache ARP
        self._force_arp_refresh()
        
        # Verifica se já está no cache
        for ip, mac in self.mac_cache.items():
            if mac == normalized_mac:
                logger.info(f"MAC encontrado no cache: {ip}")
                # Verifica se é uma impressora
                if self._verify_printer_by_ip(ip):
                    return self._create_printer_info(ip, normalized_mac)
        
        # Faz ping em IPs comuns para atualizar ARP
        networks = self._get_local_networks()
        for network in networks:
            if self.is_win10:
                common_ips = self._get_extended_common_ips(network)
            else:
                common_ips = self._get_common_printer_ips(network)
            
            # Ping em paralelo com configurações adequadas
            max_workers = self.config['parallel_hosts']
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                ping_timeout = self.config['timeouts']['ping']
                executor.map(lambda ip: self._ping_host(ip, ping_timeout), common_ips)
            
            # Atualiza cache ARP
            self._update_arp_cache()
            
            # Verifica se encontrou o MAC
            for ip, mac in self.mac_cache.items():
                if mac == normalized_mac:
                    logger.info(f"MAC encontrado após ping: {ip}")
                    if self._verify_printer_by_ip(ip):
                        return self._create_printer_info(ip, normalized_mac)
        
        logger.warning(f"Não foi possível encontrar impressora com MAC: {normalized_mac}")
        return None
    
    def _verify_printer_by_ip(self, ip):
        """Verifica se um IP é de uma impressora"""
        try:
            # Verifica se alguma porta de impressora está aberta
            scan_timeout = self.config['timeouts']['scan']
            for port in COMMON_PRINTER_PORTS:
                if self._is_port_open(ip, port, scan_timeout):
                    return True
            return False
        except:
            return False
    
    def _create_printer_info(self, ip, mac):
        """Cria informações da impressora com IP e MAC"""
        try:
            # Verifica portas abertas
            open_ports = []
            scan_timeout = self.config['timeouts']['scan']
            for port in COMMON_PRINTER_PORTS:
                if self._is_port_open(ip, port, scan_timeout):
                    open_ports.append(port)
            
            printer_info = {
                "ip": ip,
                "mac_address": mac,
                "ports": open_ports,
                "uri": self._determine_uri(ip, open_ports),
                "name": f"Impressora {ip}",
                "is_online": True
            }
            
            return printer_info
            
        except Exception as e:
            logger.error(f"Erro criando informações da impressora: {str(e)}")
            return None
    
    async def _get_printer_attributes(self, ip, port=631):
        """Obtém atributos da impressora usando IPP"""
        if not HAS_PYIPP:
            return {"ip": ip, "error": "Módulo pyipp não disponível"}
        
        protocols = [
            {"name": "HTTP", "tls": False},
            {"name": "HTTPS", "tls": True}
        ]
        
        endpoints = ["/ipp/print", "/ipp/printer", "/ipp", ""]
        
        # Timeout baseado na configuração
        timeout = self.config['timeouts']['request']
        
        for protocol in protocols:
            tls_mode = protocol["tls"]
            protocol_name = protocol["name"]
            
            for endpoint in endpoints:
                try:
                    logger.debug(f"Tentando {protocol_name} com endpoint {endpoint} em {ip}")
                    
                    client = pyipp.IPP(host=ip, port=port, tls=tls_mode)
                    client.url_path = endpoint
                    
                    printer_attrs = await asyncio.wait_for(client.printer(), timeout=timeout)
                    
                    if printer_attrs:
                        logger.info(f"Conexão IPP bem-sucedida: {protocol_name} - {endpoint}")
                        
                        if hasattr(printer_attrs, 'info') and hasattr(printer_attrs, 'state'):
                            return self._process_printer_object(printer_attrs, ip)
                        elif isinstance(printer_attrs, dict):
                            return self._process_printer_dict(printer_attrs, ip)
                        else:
                            return {"ip": ip, "raw_data": str(printer_attrs)}
                            
                except Exception as e:
                    logger.debug(f"Falha {protocol_name}-{endpoint}: {str(e)}")
                    continue
        
        # Retorna informações básicas se IPP falhar
        return {
            "ip": ip,
            "name": f"Impressora {ip}",
            "printer-state": "Desconhecido (IPP indisponível)"
        }
    
    def _process_printer_object(self, printer_obj, ip):
        """Processa objeto Printer do pyipp"""
        result = {"ip": ip}
        
        try:
            if hasattr(printer_obj, 'info'):
                info = printer_obj.info
                result['name'] = getattr(info, 'name', f"Impressora {ip}")
                result['printer-make-and-model'] = getattr(info, 'model', '')
                result['printer-location'] = getattr(info, 'location', '')
                result['manufacturer'] = getattr(info, 'manufacturer', '')
                
                # Campos opcionais
                for attr in ['printer_info', 'more_info', 'printer_uri_supported', 
                           'command_set', 'serial', 'uuid', 'version']:
                    if hasattr(info, attr):
                        result[attr.replace('_', '-')] = getattr(info, attr)
            
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
            
            if hasattr(printer_obj, 'markers') and printer_obj.markers:
                supplies = []
                for marker in printer_obj.markers:
                    supply_info = {}
                    for attr in ['marker_id', 'name', 'marker_type', 'color', 'level', 'low_level', 'high_level']:
                        if hasattr(marker, attr):
                            key = 'id' if attr == 'marker_id' else ('type' if attr == 'marker_type' else attr)
                            supply_info[key] = getattr(marker, attr)
                    supplies.append(supply_info)
                result['supplies'] = supplies
                
        except Exception as e:
            logger.warning(f"Erro processando objeto printer: {str(e)}")
        
        return result
    
    def _process_printer_dict(self, printer_dict, ip):
        """Processa dicionário de atributos do pyipp"""
        result = {"ip": ip}
        
        try:
            if isinstance(printer_dict, dict):
                attrs = printer_dict.get('printer-attributes-tag', {})
                
                # Campos principais
                result['name'] = self._extract_attr_value(attrs, 'printer-name', f'Impressora {ip}')
                result['printer-make-and-model'] = self._extract_attr_value(attrs, 'printer-make-and-model', 'Desconhecido')
                result['printer-location'] = self._extract_attr_value(attrs, 'printer-location', 'Desconhecida')
                
                # Estado da impressora
                state_code = self._extract_attr_value(attrs, 'printer-state', 3)
                state_map = {3: "Idle (Pronta)", 4: "Processing (Ocupada)", 5: "Stopped (Parada)"}
                result['printer-state'] = state_map.get(state_code, f"Desconhecido ({state_code})")
                
                # Outros atributos
                for key, value in attrs.items():
                    if key not in result:
                        result[key] = self._extract_attr_value(attrs, key, value)
                        
        except Exception as e:
            logger.warning(f"Erro processando dicionário printer: {str(e)}")
        
        return result
    
    def _extract_attr_value(self, attrs, key, default=None):
        """Extrai valor de atributo, tratando listas"""
        value = attrs.get(key, default)
        if isinstance(value, list) and len(value) == 1:
            return value[0]
        return value
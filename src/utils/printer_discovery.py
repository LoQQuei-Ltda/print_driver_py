#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VERSÃO COMPLETA: printer_discovery.py - Varredura 1-254 + Sistema IPP Robusto
Mantém TODAS as funcionalidades originais + varredura completa de rede
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
import xml.etree.ElementTree as ET
from typing import List, Dict, Set, Optional, Tuple
import warnings

# Suprime warnings
warnings.filterwarnings('ignore')

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterDiscovery")

# ========== DETECÇÃO DE AMBIENTE EMPACOTADO ==========
def is_frozen():
    """Detecta se está rodando como executável empacotado"""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

# ========== CONFIGURAÇÕES OTIMIZADAS MAS COMPLETAS ==========
if is_frozen():
    # AMBIENTE EMPACOTADO: Balanceamento entre velocidade e funcionalidade
    BASE_TIMEOUT_REQUEST = 6      # Tempo para requisições gerais
    BASE_TIMEOUT_SCAN = 2         # Tempo para port scan
    BASE_TIMEOUT_PING = 1         # Tempo para ping
    MAX_WORKERS = 80              # Workers para paralelismo
    DISCOVERY_TIMEOUT = 60        # Timeout total de descoberta
    MDNS_WAIT_TIME = 6            # Tempo de espera mDNS
    SSDP_WAIT_TIME = 10           # Tempo de espera SSDP
    MIN_DISCOVERY_TIME = 0        # Sem tempo mínimo forçado
    IPP_ATTRIBUTE_TIMEOUT = 12    # CRÍTICO: Tempo para buscar atributos IPP
    BATCH_SIZE = 40               # IPs por lote
    ENABLE_FULL_SCAN = True       # Habilita varredura completa
else:
    # DESENVOLVIMENTO: Valores otimizados
    BASE_TIMEOUT_REQUEST = 5
    BASE_TIMEOUT_SCAN = 1.5
    BASE_TIMEOUT_PING = 0.8
    MAX_WORKERS = 100
    DISCOVERY_TIMEOUT = 45
    MDNS_WAIT_TIME = 4
    SSDP_WAIT_TIME = 8
    MIN_DISCOVERY_TIME = 0
    IPP_ATTRIBUTE_TIMEOUT = 10
    BATCH_SIZE = 50
    ENABLE_FULL_SCAN = True

COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515, 8080, 8443, 5353, 161, 3702]

# Bibliotecas opcionais
HAS_PYIPP = False
HAS_ZEROCONF = False
HAS_PYSNMP = False
HAS_REQUESTS = False
HAS_NETIFACES = False

try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    logger.debug("pyipp não disponível")

HAS_ZEROCONF = False
ServiceListener = None
try:
    from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
    HAS_ZEROCONF = True
except ImportError:
    logger.debug("zeroconf não disponível")

try:
    from pysnmp.hlapi import *
    HAS_PYSNMP = True
except ImportError:
    logger.debug("pysnmp não disponível")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.debug("requests não disponível")

try:
    import netifaces
    HAS_NETIFACES = True
except ImportError:
    logger.debug("netifaces não disponível")

if HAS_ZEROCONF and ServiceListener:
    class MDNSListener(ServiceListener):
        """Listener para descoberta mDNS/Bonjour"""
        
        def __init__(self, discovery_instance):
            self.discovery = discovery_instance
            self.found_services = set()
        
        def add_service(self, zeroconf, type, name):
            """Serviço encontrado"""
            try:
                info = zeroconf.get_service_info(type, name)
                if info:
                    service_id = f"{name}:{type}"
                    if service_id not in self.found_services:
                        self.found_services.add(service_id)
                        self.discovery._process_mdns_service(info)
            except Exception as e:
                logger.debug(f"Erro processando serviço mDNS {name}: {str(e)}")
        
        def remove_service(self, zeroconf, type, name):
            pass
        
        def update_service(self, zeroconf, type, name):
            pass
else:
    class MDNSListener:
        def __init__(self, discovery_instance):
            self.discovery = discovery_instance


class PrinterDiscovery:
    """Descoberta de impressoras COMPLETA - Varredura 1-254 + IPP Robusto"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.discovered_printers = {}
        self.discovery_lock = threading.Lock()
        
        # Informações do sistema
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        self.is_frozen = is_frozen()
        self.is_admin = self._check_admin_privileges()
        
        # Detecção do Windows
        self.windows_version = self._detect_windows_version()
        
        # Cache
        self.mac_cache = {}
        self.last_arp_update = 0
        
        # Cache de IPs já testados para evitar duplicação
        self.tested_ips = set()
        
        # Configurações adaptativas
        self.config = self._setup_system_configs()
        
        # Estatísticas
        self.stats = {
            'total_ips_tested': 0,
            'responsive_ips': 0,
            'printers_found': 0,
            'start_time': 0
        }
        
        # Log do ambiente
        logger.info(f"PrinterDiscovery COMPLETO - Sistema: {self.system}, "
                   f"Frozen: {self.is_frozen}, Admin: {self.is_admin}")
        logger.info(f"Configurações: SCAN_TIMEOUT={BASE_TIMEOUT_SCAN}s, "
                   f"IPP_TIMEOUT={IPP_ATTRIBUTE_TIMEOUT}s, WORKERS={MAX_WORKERS}")
        
        if self.is_frozen:
            logger.info("🔒 EXECUTANDO EM MODO EMPACOTADO")
            logger.info(f"Bibliotecas disponíveis: zeroconf={HAS_ZEROCONF}, "
                       f"pysnmp={HAS_PYSNMP}, requests={HAS_REQUESTS}, "
                       f"netifaces={HAS_NETIFACES}, pyipp={HAS_PYIPP}")
    
    def _detect_windows_version(self):
        """Detecta versão do Windows"""
        if not self.is_windows:
            return {'version': 'not_windows', 'is_server': False}
        
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, 
                               r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
            
            product_name = winreg.QueryValueEx(key, "ProductName")[0]
            current_build = winreg.QueryValueEx(key, "CurrentBuild")[0]
            winreg.CloseKey(key)
            
            return {
                'version': product_name,
                'build': int(current_build),
                'is_server': "server" in product_name.lower()
            }
        except:
            return {'version': 'unknown', 'is_server': False}
    
    def _check_admin_privileges(self):
        """Verifica privilégios de administrador"""
        try:
            if self.is_windows:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            else:
                return os.geteuid() == 0
        except:
            return False
    
    def _setup_system_configs(self):
        """Configura parâmetros adaptativos"""
        return {
            'timeouts': {
                'request': BASE_TIMEOUT_REQUEST,
                'scan': BASE_TIMEOUT_SCAN,
                'ping': BASE_TIMEOUT_PING,
                'ipp_attributes': IPP_ATTRIBUTE_TIMEOUT
            },
            'parallel_hosts': MAX_WORKERS,
            'batch_size': BATCH_SIZE,
            'enable_full_scan': ENABLE_FULL_SCAN
        }
    
    def normalize_mac(self, mac):
        """Normaliza formato MAC address"""
        if not mac or mac == "desconhecido":
            return None
            
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', str(mac).lower())
        
        if len(clean_mac) != 12:
            return None
            
        return ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])
    
    def discover_printers(self, subnet=None):
        """
        Descoberta COMPLETA de impressoras com varredura 1-254
        """
        logger.info("=== DESCOBERTA COMPLETA DE IMPRESSORAS (1-254) ===")
        logger.info(f"Ambiente: {'EMPACOTADO' if self.is_frozen else 'DESENVOLVIMENTO'}")
        start_time = time.time()
        self.stats['start_time'] = start_time
        
        # Limpa descobertas anteriores
        self.discovered_printers.clear()
        self.tested_ips.clear()
        self.stats = {'total_ips_tested': 0, 'responsive_ips': 0, 'printers_found': 0, 'start_time': start_time}
        
        # Força atualização do ARP primeiro
        self._update_arp_cache()
        
        # Lista de métodos de descoberta COMPLETA
        discovery_methods = []
        
        # Ordena métodos por eficácia (mDNS primeiro por ser mais preciso)
        if HAS_ZEROCONF:
            discovery_methods.append(("mDNS/Bonjour", self._discover_mdns))
        
        # DESCOBERTA PRINCIPAL: Varredura completa da rede
        discovery_methods.append(("Varredura Completa 1-254", self._discover_complete_network_scan))
        
        # Métodos auxiliares
        discovery_methods.append(("Cache ARP", self._discover_arp_cache))
        discovery_methods.append(("IPP Direct", self._discover_ipp_direct))
        
        if self.is_windows:
            discovery_methods.append(("WSD", self._discover_wsd))
        
        if HAS_PYSNMP:
            discovery_methods.append(("SNMP", self._discover_snmp))
        
        discovery_methods.append(("SSDP/UPnP", self._discover_ssdp))
        
        # Executa descobertas em paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(discovery_methods)) as executor:
            futures = []
            
            for method_name, method_func in discovery_methods:
                logger.info(f"▶ Iniciando {method_name}...")
                future = executor.submit(self._run_discovery_method, method_name, method_func, subnet)
                futures.append((method_name, future))
            
            # Aguarda com timeout
            timeout = DISCOVERY_TIMEOUT
            
            for method_name, future in futures:
                try:
                    result = future.result(timeout=timeout)
                    logger.info(f"✓ {method_name}: {result} impressoras")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"⏱ {method_name}: Timeout")
                except Exception as e:
                    logger.error(f"✗ {method_name}: {str(e)}")
        
        # Processa resultados (LÓGICA ORIGINAL QUE FUNCIONAVA)
        unique_printers = self._process_discovered_printers()
        
        # Estatísticas finais
        total_elapsed = time.time() - start_time
        logger.info(f"=== DESCOBERTA CONCLUÍDA ===")
        logger.info(f"Tempo total: {total_elapsed:.1f}s")
        logger.info(f"IPs testados: {self.stats['total_ips_tested']}")
        logger.info(f"IPs responsivos: {self.stats['responsive_ips']}")
        logger.info(f"Impressoras encontradas: {len(unique_printers)}")
        
        # Log detalhado dos IPs encontrados
        if unique_printers:
            ips_found = [p['ip'] for p in unique_printers]
            ips_found.sort(key=lambda ip: [int(x) for x in ip.split('.')])
            logger.info(f"IPs descobertos: {', '.join(ips_found)}")
            
            # Contadores de status
            green_count = sum(1 for p in unique_printers if p.get('is_ready', False))
            yellow_count = len(unique_printers) - green_count
            logger.info(f"Status: 🟢 {green_count} VERDES, 🟡 {yellow_count} AMARELAS")
        
        self.printers = unique_printers
        return unique_printers
    
    def _run_discovery_method(self, method_name, method_func, subnet):
        """Executa método de descoberta com logging"""
        try:
            start = time.time()
            count = method_func(subnet)
            elapsed = time.time() - start
            logger.debug(f"{method_name} completado em {elapsed:.1f}s")
            return count
        except Exception as e:
            logger.error(f"Erro em {method_name}: {str(e)}")
            return 0
    
    def _add_discovered_printer(self, printer_info):
        """Adiciona impressora descoberta"""
        with self.discovery_lock:
            ip = printer_info.get('ip')
            if not ip:
                return
            
            if ip in self.discovered_printers:
                existing = self.discovered_printers[ip]
                # Mescla informações
                for key, value in printer_info.items():
                    if value and (key not in existing or not existing[key]):
                        existing[key] = value
                if 'ports' in printer_info:
                    existing_ports = set(existing.get('ports', []))
                    new_ports = set(printer_info['ports'])
                    existing['ports'] = sorted(list(existing_ports | new_ports))
            else:
                self.discovered_printers[ip] = printer_info
                logger.debug(f"Nova impressora descoberta: {ip}")
    
    def _discover_mdns(self, subnet=None):
        """Descoberta via mDNS/Bonjour"""
        if not HAS_ZEROCONF:
            return 0
        
        count = 0
        try:
            zeroconf = Zeroconf()
            listener = MDNSListener(self)
            
            # Serviços de impressora expandidos
            services = [
                "_ipp._tcp.local.",
                "_printer._tcp.local.",
                "_pdl-datastream._tcp.local.",
                "_airprint._tcp.local.",
                "_ipps._tcp.local.",
                "_http._tcp.local.",
                "_device-info._tcp.local."
            ]
            
            browsers = []
            for service in services:
                browser = ServiceBrowser(zeroconf, service, listener)
                browsers.append(browser)
            
            # Aguarda anúncios
            wait_time = MDNS_WAIT_TIME
            logger.info(f"mDNS aguardando {wait_time}s por anúncios...")
            time.sleep(wait_time)
            
            count = len([p for p in self.discovered_printers.values() 
                        if p.get('discovery_method') == 'mDNS'])
            
            zeroconf.close()
            
        except Exception as e:
            logger.error(f"Erro mDNS: {str(e)}")
        
        return count
    
    def _process_mdns_service(self, info):
        """Processa serviço mDNS descoberto"""
        try:
            if not info.addresses:
                return
            
            ip = socket.inet_ntoa(info.addresses[0])
            
            printer_info = {
                'ip': ip,
                'name': info.name.split('.')[0],
                'port': info.port,
                'discovery_method': 'mDNS',
                'mdns_properties': {}
            }
            
            if info.properties:
                for key, value in info.properties.items():
                    if isinstance(value, bytes):
                        value = value.decode('utf-8', errors='ignore')
                    printer_info['mdns_properties'][key.decode('utf-8', errors='ignore')] = value
                
                props = printer_info['mdns_properties']
                if 'ty' in props:
                    printer_info['model'] = props['ty']
                if 'note' in props:
                    printer_info['location'] = props['note']
            
            if info.port:
                printer_info['ports'] = [info.port]
                if info.port == 631:
                    printer_info['uri'] = f"ipp://{ip}:631/ipp/print"
            
            self._add_discovered_printer(printer_info)
            
        except Exception as e:
            logger.debug(f"Erro processando mDNS: {str(e)}")
    
    def _discover_complete_network_scan(self, subnet=None):
        """
        DESCOBERTA PRINCIPAL: Varredura completa da rede (1-254)
        """
        networks = self._get_networks_to_scan(subnet)
        total_count = 0
        
        for network in networks[:2]:  # Máximo 2 redes
            logger.info(f"Iniciando varredura completa: {network}")
            
            # Gera TODOS os IPs da rede (1-254)
            all_ips = self._generate_all_network_ips(network)
            logger.info(f"Testando {len(all_ips)} IPs na rede {network}")
            self.stats['total_ips_tested'] += len(all_ips)
            
            # Marca IPs como testados
            for ip in all_ips:
                self.tested_ips.add(ip)
            
            # Processa em lotes para melhor controle
            count = self._scan_ip_range_parallel(all_ips, f"Rede {network}")
            total_count += count
            
            logger.info(f"Rede {network}: {count} impressoras encontradas")
        
        return total_count
    
    def _discover_arp_cache(self, subnet=None):
        """Descoberta usando cache ARP"""
        count = 0
        
        # Testa IPs do ARP que ainda não foram testados
        arp_ips = []
        for ip in self.mac_cache.keys():
            if ip not in self.tested_ips:
                arp_ips.append(ip)
                self.tested_ips.add(ip)
        
        if arp_ips:
            logger.info(f"Testando {len(arp_ips)} IPs do cache ARP")
            count = self._scan_ip_range_parallel(arp_ips, "Cache ARP")
        
        return count
    
    def _discover_ipp_direct(self, subnet=None):
        """IPP Direct expandido"""
        count = 0
        networks = self._get_networks_to_scan(subnet)
        
        for network in networks[:1]:  # Apenas primeira rede
            # IPs que comumente usam IPP
            ipp_ips = self._get_ipp_likely_ips(network)
            
            # Remove IPs já testados
            test_ips = [ip for ip in ipp_ips if ip not in self.tested_ips]
            
            # Marca como testados
            for ip in test_ips:
                self.tested_ips.add(ip)
            
            if test_ips:
                with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                    futures = [executor.submit(self._check_ipp_printer, ip) for ip in test_ips]
                    
                    for future in concurrent.futures.as_completed(futures, timeout=25):
                        try:
                            if future.result():
                                count += 1
                        except:
                            pass
        
        return count
    
    def _discover_wsd(self, subnet=None):
        """Web Services for Devices (Windows)"""
        if not self.is_windows:
            return 0
        
        count = 0
        try:
            probe_message = self._create_wsd_probe()
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(2)
            
            # Envia probe
            sock.sendto(probe_message.encode('utf-8'), ('239.255.255.250', 3702))
            
            # Escuta respostas
            start_time = time.time()
            timeout = 8
            
            while time.time() - start_time < timeout:
                try:
                    data, addr = sock.recvfrom(65536)
                    if self._process_wsd_response(data, addr[0]):
                        count += 1
                except socket.timeout:
                    continue
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"Erro WSD: {str(e)}")
        
        return count
    
    def _discover_snmp(self, subnet=None):
        """Simple Network Management Protocol"""
        if not HAS_PYSNMP:
            return 0
        
        count = 0
        networks = self._get_networks_to_scan(subnet)
        
        for network in networks[:1]:  # Apenas uma rede
            # IPs comuns para SNMP
            snmp_ips = self._get_snmp_likely_ips(network)
            
            for ip in snmp_ips:
                if ip not in self.tested_ips and self._is_port_open(ip, 161, 1):
                    printer_info = {
                        'ip': ip,
                        'name': f"Impressora SNMP {ip}",
                        'discovery_method': 'SNMP',
                        'ports': [161],
                        'uri': f"socket://{ip}:9100"
                    }
                    self._add_discovered_printer(printer_info)
                    count += 1
                    self.tested_ips.add(ip)
        
        return count
    
    def _discover_ssdp(self, subnet=None):
        """Simple Service Discovery Protocol / UPnP"""
        count = 0
        
        try:
            ssdp_request = """M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 3
ST: ssdp:all

"""
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(2)
            
            # Envia probe
            sock.sendto(ssdp_request.encode('utf-8'), ('239.255.255.250', 1900))
            
            # Escuta respostas
            start_time = time.time()
            timeout = SSDP_WAIT_TIME
            
            while time.time() - start_time < timeout:
                try:
                    data, addr = sock.recvfrom(65536)
                    response = data.decode('utf-8', errors='ignore')
                    
                    if any(k in response.lower() for k in ['printer', 'print']):
                        location_match = re.search(r'LOCATION:\s*(.+)', response, re.IGNORECASE)
                        if location_match:
                            location = location_match.group(1).strip()
                            ip_match = re.search(r'http[s]?://([^:/]+)', location)
                            if ip_match:
                                ip = ip_match.group(1)
                                printer_info = {
                                    'ip': ip,
                                    'name': f"Impressora UPnP {ip}",
                                    'discovery_method': 'SSDP/UPnP',
                                    'ports': [80],
                                    'uri': location
                                }
                                self._add_discovered_printer(printer_info)
                                count += 1
                
                except socket.timeout:
                    continue
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"Erro SSDP: {str(e)}")
        
        return count
    
    def _generate_all_network_ips(self, network):
        """Gera TODOS os IPs válidos da rede (1-254)"""
        all_ips = []
        
        try:
            # Para redes /24 (mais comum) - otimização especial
            if network.prefixlen >= 24:
                base_ip = str(network.network_address)
                base_parts = base_ip.split('.')
                
                # Gera IPs de .1 até .254
                for i in range(1, 255):
                    ip = f"{base_parts[0]}.{base_parts[1]}.{base_parts[2]}.{i}"
                    all_ips.append(ip)
            else:
                # Para redes maiores, usa a biblioteca
                for host in network.hosts():
                    all_ips.append(str(host))
                    if len(all_ips) >= 254:  # Limita para não explodir
                        break
                        
        except Exception as e:
            logger.error(f"Erro gerando IPs da rede {network}: {e}")
        
        return all_ips
    
    def _get_ipp_likely_ips(self, network):
        """IPs com maior probabilidade de ter IPP"""
        ipp_ips = []
        
        try:
            base_ip = network.network_address
            
            # IPs comuns para impressoras IPP
            ipp_endings = list(range(1, 255, 2))  # IPs ímpares são comuns
            ipp_endings.extend([20, 21, 100, 101, 110, 111, 120, 121, 200, 201])
            
            for ending in ipp_endings[:50]:  # Limita para não sobrecarregar
                try:
                    ip = str(base_ip + ending)
                    if ipaddress.IPv4Address(ip) in network:
                        ipp_ips.append(ip)
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Erro gerando IPs IPP: {e}")
        
        return ipp_ips
    
    def _get_snmp_likely_ips(self, network):
        """IPs com maior probabilidade de ter SNMP"""
        snmp_ips = []
        
        try:
            base_ip = network.network_address
            
            # IPs comuns para SNMP
            snmp_endings = [1, 2, 10, 20, 100, 101, 110, 111, 200, 201, 250, 251, 252, 253, 254]
            
            for ending in snmp_endings:
                try:
                    ip = str(base_ip + ending)
                    if ipaddress.IPv4Address(ip) in network:
                        snmp_ips.append(ip)
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Erro gerando IPs SNMP: {e}")
        
        return snmp_ips
    
    def _scan_ip_range_parallel(self, ip_list, range_name):
        """Escaneia range de IPs em paralelo"""
        if not ip_list:
            return 0
        
        count = 0
        
        # Divide em lotes para melhor controle
        batches = [ip_list[i:i + BATCH_SIZE] for i in range(0, len(ip_list), BATCH_SIZE)]
        
        for batch_num, batch_ips in enumerate(batches, 1):
            logger.info(f"{range_name} - Lote {batch_num}/{len(batches)}: testando {len(batch_ips)} IPs")
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                # Ping rápido primeiro para filtrar IPs ativos
                ping_futures = {executor.submit(self._quick_ping, ip): ip for ip in batch_ips}
                active_ips = []
                
                for future in concurrent.futures.as_completed(ping_futures, timeout=15):
                    try:
                        if future.result():
                            active_ips.append(ping_futures[future])
                    except:
                        pass
                
                logger.debug(f"Lote {batch_num}: {len(active_ips)}/{len(batch_ips)} IPs responsivos")
                self.stats['responsive_ips'] += len(active_ips)
                
                # Port scan nos IPs ativos
                if active_ips:
                    scan_futures = {executor.submit(self._scan_single_ip_comprehensive, ip): ip 
                                   for ip in active_ips}
                    
                    for future in concurrent.futures.as_completed(scan_futures, timeout=30):
                        try:
                            result = future.result()
                            if result:
                                self._add_discovered_printer(result)
                                count += 1
                                logger.info(f"✓ {range_name}: Impressora em {result['ip']} "
                                          f"(Portas: {result.get('ports', [])})")
                        except:
                            pass
        
        return count
    
    def _quick_ping(self, ip):
        """Ping super rápido para testar conectividade"""
        try:
            if self.is_windows:
                cmd = ["ping", "-n", "1", "-w", str(int(BASE_TIMEOUT_PING * 1000)), ip]
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(BASE_TIMEOUT_PING)), ip]
                creation_flags = 0
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=BASE_TIMEOUT_PING + 1,
                creationflags=creation_flags
            )
            
            return result.returncode == 0
        except:
            return False
    
    def _scan_single_ip_comprehensive(self, ip):
        """Escaneia um IP de forma abrangente"""
        # Testa portas de impressora em ordem de prioridade
        priority_ports = [631, 9100]  # IPP e RAW primeiro
        secondary_ports = [80, 443, 515, 8080]
        
        open_ports = []
        
        # Testa portas principais
        for port in priority_ports:
            if self._is_port_open(ip, port, BASE_TIMEOUT_SCAN):
                open_ports.append(port)
        
        # Se encontrou porta principal, testa secundárias
        if open_ports:
            for port in secondary_ports:
                if self._is_port_open(ip, port, 1):  # Timeout menor para secundárias
                    open_ports.append(port)
        else:
            return None  # Não é impressora se não tem portas principais
        
        # Verifica se realmente parece ser impressora
        if not self._looks_like_printer(ip, open_ports):
            return None
        
        # Obtém MAC address
        mac = self._get_mac_for_ip(ip)
        
        # Cria informações básicas da impressora
        printer_info = {
            'ip': ip,
            'name': f"Impressora {ip}",
            'mac_address': mac,
            'ports': open_ports,
            'uri': self._determine_uri(ip, open_ports),
            'discovery_method': 'Network Scan',
            'is_online': True,
            'is_ready': True  # Padrão: pronta (será refinado pelo IPP)
        }
        
        return printer_info
    
    def _check_ipp_printer(self, ip):
        """Verifica se é impressora IPP"""
        if not self._is_port_open(ip, 631, 2):
            return False
        
        printer_info = {
            'ip': ip,
            'name': f"Impressora IPP {ip}",
            'discovery_method': 'IPP Direct',
            'ports': [631],
            'uri': f"ipp://{ip}/ipp/print",
            'is_online': True,
            'is_ready': True
        }
        
        self._add_discovered_printer(printer_info)
        return True
    
    def _create_wsd_probe(self):
        """Cria mensagem de probe WSD"""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" 
               xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <soap:Header>
    <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
    <wsa:MessageID>urn:uuid:{int(time.time() * 1000)}</wsa:MessageID>
  </soap:Header>
  <soap:Body>
    <wsd:Probe>
      <wsd:Types>wsdp:Device</wsd:Types>
    </wsd:Probe>
  </soap:Body>
</soap:Envelope>"""
    
    def _process_wsd_response(self, data, ip):
        """Processa resposta WSD"""
        try:
            device_info = data.decode('utf-8', errors='ignore').lower()
            if any(k in device_info for k in ['print', 'printer', 'mfp']):
                printer_info = {
                    'ip': ip,
                    'name': f"Impressora WSD {ip}",
                    'discovery_method': 'WSD',
                    'ports': [80, 5357],
                    'uri': f"http://{ip}",
                    'is_online': True,
                    'is_ready': True
                }
                self._add_discovered_printer(printer_info)
                return True
        except:
            pass
        return False
    
    def _process_discovered_printers(self):
        """
        Processa impressoras descobertas - LÓGICA ORIGINAL RESTAURADA
        """
        unique_printers = []
        
        with self.discovery_lock:
            logger.info(f"Processando {len(self.discovered_printers)} impressoras descobertas...")
            
            for ip, printer_info in self.discovered_printers.items():
                # Enriquece com MAC se não tem
                if not printer_info.get('mac_address'):
                    printer_info['mac_address'] = self._get_mac_for_ip(ip)
                
                # Normaliza MAC
                mac = self.normalize_mac(printer_info.get('mac_address'))
                printer_info['mac_address'] = mac or 'desconhecido'
                
                # Garante campos obrigatórios
                if not printer_info.get('name'):
                    printer_info['name'] = f"Impressora {ip}"
                
                if not printer_info.get('uri'):
                    ports = printer_info.get('ports', [])
                    printer_info['uri'] = self._determine_uri(ip, ports)
                
                # Garante status online
                printer_info['is_online'] = True
                
                # CRÍTICO: Enriquecimento IPP para impressoras com porta 631
                if 631 in printer_info.get('ports', []) and HAS_PYIPP:
                    logger.debug(f"Enriquecendo com IPP: {ip}")
                    self._enrich_with_ipp_details(printer_info)
                else:
                    # Se não tem IPP, assume que está pronta
                    printer_info.setdefault('is_ready', True)
                
                # Log do status final
                ready_status = "🟢 VERDE" if printer_info.get('is_ready') else "🟡 AMARELA"
                method = printer_info.get('discovery_method', 'Unknown')
                model = printer_info.get('printer-make-and-model') or printer_info.get('model', '')
                logger.info(f"Processada: {ip} via {method} → {ready_status}" + 
                           (f" ({model})" if model else ""))
                
                unique_printers.append(printer_info)
        
        # Ordena por IP
        unique_printers.sort(key=lambda p: socket.inet_aton(p['ip']))
        
        # Log de resumo
        green_count = sum(1 for p in unique_printers if p.get('is_ready', False))
        yellow_count = len(unique_printers) - green_count
        
        logger.info(f"RESUMO FINAL: {len(unique_printers)} impressoras")
        logger.info(f"  🟢 VERDES (prontas): {green_count}")
        logger.info(f"  🟡 AMARELAS (não prontas): {yellow_count}")
        
        # Debug detalhado das amarelas
        if yellow_count > 0:
            logger.warning(f"IMPRESSORAS AMARELAS DETECTADAS:")
            for p in unique_printers:
                if not p.get('is_ready', False):
                    logger.warning(f"  • {p['ip']} - {p.get('name', 'Sem nome')}")
                    logger.warning(f"    Estado: {p.get('printer-state', 'N/A')}")
                    logger.warning(f"    Método: {p.get('discovery_method', 'N/A')}")
        
        return unique_printers
    
    def _enrich_with_ipp_details(self, printer_info):
        """
        Enriquecimento IPP COMPLETO - VERSÃO ORIGINAL RESTAURADA
        """
        if not HAS_PYIPP:
            logger.debug(f"pyipp não disponível para {printer_info.get('ip')}")
            return

        ip = printer_info.get('ip')
        if not ip:
            return

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            details = loop.run_until_complete(
                asyncio.wait_for(
                    self._get_printer_attributes(ip), 
                    timeout=IPP_ATTRIBUTE_TIMEOUT
                )
            )
            loop.close()
            
            if details:
                logger.debug(f"IPP enriquecido com sucesso para {ip}: {list(details.keys())}")
                
                # LÓGICA ORIGINAL: Mescla atributos IPP
                printer_info.update(details)
                
                # CRÍTICO: Status final baseado em IPP
                if 'is_ready' in details:
                    printer_info['is_ready'] = details['is_ready']
                elif 'printer-state-code' in details:
                    state_code = details['printer-state-code']
                    printer_info['is_ready'] = state_code in [3, 4]  # idle ou processing
                else:
                    printer_info['is_ready'] = True  # Se conseguiu IPP, assume pronta
                
                # Log do resultado
                ready_status = "🟢 VERDE" if printer_info.get('is_ready') else "🟡 AMARELA"
                model = printer_info.get('printer-make-and-model', 'Modelo desconhecido')
                logger.info(f"IPP {ip}: {model} → {ready_status}")
            else:
                logger.debug(f"Nenhum detalhe IPP retornado para {ip}")
                # Se falhou IPP mas tem porta 631, ainda considera online
                printer_info['is_ready'] = True
                
        except asyncio.TimeoutError:
            logger.warning(f"Timeout IPP para {ip} ({IPP_ATTRIBUTE_TIMEOUT}s)")
            printer_info['is_ready'] = True  # Timeout não significa que não está pronta
        except Exception as e:
            logger.error(f"Erro IPP para {ip}: {str(e)}")
            printer_info['is_ready'] = True  # Erro não significa que não está pronta
    
    async def _get_printer_attributes(self, ip, port=631, tls=False, _retry_with_tls=True):
        """
        FUNÇÃO IPP ORIGINAL COMPLETA - Obtém atributos da impressora
        """
        if not HAS_PYIPP:
            return None

        endpoints = ["/ipp/print", "/ipp/printer", "/ipp", ""]
        ipp_call_timeout = IPP_ATTRIBUTE_TIMEOUT
        
        logger.debug(f"Buscando atributos IPP para {ip}:{port} (TLS: {tls})")

        for endpoint in endpoints:
            client = None
            try:
                uri = f"{'https' if tls else 'http'}://{ip}:{port}{endpoint if endpoint else '/'}"
                logger.debug(f"Tentando endpoint IPP: {uri}")
                
                client = pyipp.IPP(host=ip, port=port, tls=tls, base_path=endpoint)
                                
                printer_attrs_raw = await asyncio.wait_for(
                    client.printer(), 
                    timeout=ipp_call_timeout
                )
                                
                if printer_attrs_raw:
                    result = {'ip': ip, 'ipp_uri_used': uri, 'ipp_attributes_source': 'pyipp'}
                    
                    # Processa informações básicas da impressora
                    if hasattr(printer_attrs_raw, 'info') and printer_attrs_raw.info:
                        info = printer_attrs_raw.info
                        result['name'] = getattr(info, 'name', f"Impressora IPP {ip}")
                        result['printer-make-and-model'] = getattr(info, 'model', '')
                        result['printer-location'] = getattr(info, 'location', '')
                        result['printer-info'] = getattr(info, 'printer_info', '') 
                        result['printer-uri-supported'] = getattr(info, 'uris', [])
                        result['manufacturer'] = getattr(info, 'manufacturer', '')
                        result['serial'] = getattr(info, 'serial', '')
                        result['version'] = getattr(info, 'version', '')
                    
                    # CRÍTICO: Processamento do estado da impressora
                    result['is_ready'] = True  # Padrão: pronta
                    result['printer-state'] = "Online"
                    
                    if hasattr(printer_attrs_raw, 'state') and printer_attrs_raw.state:
                        state = printer_attrs_raw.state
                        
                        # Código de estado numérico
                        raw_state_code = None
                        if hasattr(state, 'printer_state_code') and state.printer_state_code:
                            raw_state_code = state.printer_state_code
                        elif isinstance(state.printer_state, int):
                            raw_state_code = state.printer_state

                        # Estado textual
                        textual_state = getattr(state, 'printer_state', 'idle').lower()
                        logger.debug(f"Estado IPP {ip}: texto='{textual_state}', código={raw_state_code}")
                        
                        # Interpretação do estado
                        if textual_state == 'idle':
                            result['printer-state'] = "Idle (Pronta)"
                            result['is_ready'] = True  # 🟢 VERDE
                            raw_state_code = raw_state_code or 3
                        elif textual_state == 'processing':
                            result['printer-state'] = "Processing (Ocupada)"
                            result['is_ready'] = True  # 🟢 VERDE (temporariamente ocupada)
                            raw_state_code = raw_state_code or 4
                        elif textual_state == 'stopped':
                            result['printer-state'] = "Stopped (Parada)"
                            result['is_ready'] = False  # 🟡 AMARELA (problema real)
                            raw_state_code = raw_state_code or 5
                        else:
                            # Estados desconhecidos = assume pronta
                            result['printer-state'] = textual_state.capitalize()
                            result['is_ready'] = True  # 🟢 VERDE por padrão

                        result['printer-state-reasons'] = getattr(state, 'reasons', [])
                        result['printer-state-message'] = getattr(state, 'message', '')
                        
                        if raw_state_code:
                            result['printer-state-code'] = raw_state_code
                            # Override apenas se realmente parada
                            if raw_state_code == 5:  # stopped
                                result['is_ready'] = False
                        else:
                            result['printer-state-code'] = 3  # idle por padrão
                    
                    # Log do estado processado
                    ready_status = "🟢 VERDE" if result['is_ready'] else "🟡 AMARELA"
                    logger.info(f"IPP {ip}: '{result['printer-state']}' → {ready_status}")

                    # Processa suprimentos (toner, papel, etc.)
                    if hasattr(printer_attrs_raw, 'markers') and printer_attrs_raw.markers:
                        supplies = []
                        for marker in printer_attrs_raw.markers:
                            supplies.append({
                                'name': getattr(marker, 'name', 'N/A'),
                                'type': getattr(marker, 'marker_type', 'N/A'),
                                'color': getattr(marker, 'color', 'N/A'),
                                'level': getattr(marker, 'level', -1),
                            })
                        if supplies:
                            result['supplies'] = supplies

                    # Processa atributos adicionais
                    if hasattr(printer_attrs_raw, 'attributes') and printer_attrs_raw.attributes:
                        for group_name, group_attrs in printer_attrs_raw.attributes.items():
                            if isinstance(group_attrs, dict):
                                for attr_name, attr_value in group_attrs.items():
                                    key_name = f"{group_name}_{attr_name.replace('-', '_')}" if group_name != 'printer' else attr_name.replace('-', '_')
                                    if key_name not in result:
                                        if isinstance(attr_value, list) and len(attr_value) == 1:
                                            result[key_name] = attr_value[0]
                                        else:
                                            result[key_name] = attr_value
                    
                    # Garante campos essenciais
                    result.setdefault('printer-make-and-model', '')
                    result.setdefault('printer-location', '')
                    result.setdefault('name', f"Impressora IPP {ip}")

                    logger.info(f"Atributos IPP obtidos para {ip}: {len(result)} campos")
                    if client:
                        await client.close() 
                    return result 

            except pyipp.exceptions.IPPConnectionUpgradeRequired:
                logger.warning(f"IPP requer upgrade para TLS: {ip}")
                if client:
                    await client.close()
                if not tls and _retry_with_tls:
                    return await self._get_printer_attributes(ip, port=port, tls=True, _retry_with_tls=False)
                continue 
            
            except asyncio.TimeoutError:
                logger.warning(f"Timeout IPP para {uri} ({ipp_call_timeout}s)")
            except ConnectionRefusedError:
                logger.warning(f"Conexão IPP recusada: {uri}")
            except Exception as e:
                logger.debug(f"Erro IPP em {uri}: {str(e)}")
            
            finally:
                if client:
                    try:
                        await client.close()
                    except:
                        pass
        
        # Tenta com TLS se ainda não tentou
        if not tls and _retry_with_tls:
            return await self._get_printer_attributes(ip, port=port, tls=True, _retry_with_tls=False)
        
        logger.warning(f"Falha ao obter atributos IPP para {ip}")
        return None
    
    def _looks_like_printer(self, ip, open_ports):
        """Verifica se parece ser uma impressora"""
        # Porta IPP = quase certeza de impressora
        if 631 in open_ports:
            return True
        
        # Porta de impressão direta = muito provável
        if 9100 in open_ports:
            return True
        
        # Porta LPD = possível impressora
        if 515 in open_ports:
            return True
        
        # Múltiplas portas = pode ser multifuncional
        if len(open_ports) >= 2:
            return True
        
        return False
    
    def _determine_uri(self, ip, open_ports):
        """Determina a melhor URI para a impressora"""
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
            return f"ipp://{ip}/ipp/print"
    
    def _get_networks_to_scan(self, subnet=None):
        """Obtém redes para escanear"""
        if subnet:
            try:
                return [ipaddress.IPv4Network(subnet, strict=False)]
            except:
                pass
        
        return self._get_local_networks()
    
    def _get_local_networks(self):
        """Detecta redes locais automaticamente"""
        networks = []
        
        # Usa netifaces se disponível
        if HAS_NETIFACES:
            try:
                for interface in netifaces.interfaces():
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr.get('addr')
                            netmask = addr.get('netmask')
                            if ip and netmask and not ip.startswith('127.'):
                                try:
                                    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                    if network not in networks:
                                        networks.append(network)
                                except:
                                    pass
            except Exception as e:
                logger.debug(f"Erro netifaces: {e}")
        
        # Fallback: detecta via hostname
        if not networks:
            try:
                hostname = socket.gethostname()
                for info in socket.getaddrinfo(hostname, None):
                    ip = info[4][0]
                    if not ip.startswith('127.') and '.' in ip:
                        try:
                            network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                            if network not in networks:
                                networks.append(network)
                        except:
                            pass
            except:
                pass
        
        # Fallback final: redes comuns
        if not networks:
            common_networks = ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24", "172.16.0.0/24"]
            for net_str in common_networks:
                try:
                    networks.append(ipaddress.IPv4Network(net_str))
                except:
                    pass
        
        logger.info(f"Redes detectadas: {[str(n) for n in networks]}")
        return networks
    
    def _is_port_open(self, ip, port, timeout=1):
        """Verifica se uma porta está aberta"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _update_arp_cache(self):
        """Atualiza cache ARP para descoberta de MAC"""
        current_time = time.time()
        if current_time - self.last_arp_update < 30:
            return
        
        self.mac_cache.clear()
        
        try:
            if self.is_windows:
                result = subprocess.run(
                    ['arp', '-a'],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ['arp', '-a'],
                    capture_output=True, text=True, timeout=10
                )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    match = re.search(
                        r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9A-Fa-f:.-]+)',
                        line
                    )
                    if match:
                        ip = match.group(1)
                        mac = self.normalize_mac(match.group(2))
                        if mac:
                            self.mac_cache[ip] = mac
            
            self.last_arp_update = current_time
            logger.debug(f"Cache ARP atualizado: {len(self.mac_cache)} entradas")
            
        except Exception as e:
            logger.debug(f"Erro atualizando ARP: {e}")
    
    def _get_mac_for_ip(self, ip):
        """Obtém MAC address para um IP"""
        # Verifica cache primeiro
        if ip in self.mac_cache:
            return self.mac_cache[ip]
        
        # Ping para forçar entrada no ARP
        self._quick_ping(ip)
        time.sleep(0.2)
        
        # Busca no ARP
        try:
            if self.is_windows:
                result = subprocess.run(
                    ['arp', '-a', ip],
                    capture_output=True, text=True, timeout=3,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ['arp', '-n', ip],
                    capture_output=True, text=True, timeout=3
                )
            
            if result.returncode == 0:
                match = re.search(r'([0-9A-Fa-f:.-]+)', result.stdout)
                if match:
                    mac = self.normalize_mac(match.group(1))
                    if mac:
                        self.mac_cache[ip] = mac
                        return mac
        except:
            pass
        
        return "desconhecido"
    
    def discover_printer_by_mac(self, target_mac):
        """Busca impressora específica por MAC address"""
        normalized_mac = self.normalize_mac(target_mac)
        if not normalized_mac:
            return None
        
        # Faz descoberta completa
        self.discover_printers()
        
        # Busca pela impressora com o MAC especificado
        for printer in self.printers:
            if self.normalize_mac(printer.get('mac_address')) == normalized_mac:
                return printer
        
        return None
    
    def get_printer_details(self, ip):
        """Obtém detalhes específicos de uma impressora"""
        logger.debug(f"Obtendo detalhes para {ip}")
        
        # Scan básico do IP
        result = self._scan_single_ip_comprehensive(ip)
        
        if result and 631 in result.get('ports', []) and HAS_PYIPP:
            logger.debug(f"Enriquecendo {ip} com IPP")
            self._enrich_with_ipp_details(result)
        
        return result


# ========== FUNÇÃO DE TESTE COMPLETA ==========
if __name__ == "__main__":
    print("=== TESTE COMPLETO DO PRINTER DISCOVERY ===")
    print(f"Ambiente: {'EMPACOTADO' if is_frozen() else 'DESENVOLVIMENTO'}")
    print(f"Configurações:")
    print(f"  - PING_TIMEOUT: {BASE_TIMEOUT_PING}s")
    print(f"  - SCAN_TIMEOUT: {BASE_TIMEOUT_SCAN}s")
    print(f"  - IPP_TIMEOUT: {IPP_ATTRIBUTE_TIMEOUT}s")
    print(f"  - MAX_WORKERS: {MAX_WORKERS}")
    print(f"  - BATCH_SIZE: {BATCH_SIZE}")
    print(f"Bibliotecas disponíveis:")
    print(f"  - pyipp: {HAS_PYIPP}")
    print(f"  - zeroconf: {HAS_ZEROCONF}")
    print(f"  - netifaces: {HAS_NETIFACES}")
    print(f"  - pysnmp: {HAS_PYSNMP}")
    print(f"  - requests: {HAS_REQUESTS}")
    
    discovery = PrinterDiscovery()
    print("\n" + "="*60)
    print("INICIANDO DESCOBERTA COMPLETA...")
    print("="*60)
    
    start_time = time.time()
    printers = discovery.discover_printers()
    total_time = time.time() - start_time
    
    print("\n" + "="*60)
    print(f"DESCOBERTA CONCLUÍDA EM {total_time:.1f}s")
    print("="*60)
    
    if printers:
        print(f"\n🎯 {len(printers)} IMPRESSORAS ENCONTRADAS:")
        print("-" * 60)
        
        green_count = 0
        yellow_count = 0
        
        for i, printer in enumerate(printers, 1):
            is_ready = printer.get('is_ready', False)
            is_online = printer.get('is_online', False)
            
            if is_ready and is_online:
                status_icon = "🟢"
                status_text = "VERDE (Pronta)"
                green_count += 1
            elif is_online:
                status_icon = "🟡"
                status_text = "AMARELA (Online mas não pronta)"
                yellow_count += 1
            else:
                status_icon = "🔴"
                status_text = "VERMELHA (Offline)"
                yellow_count += 1
            
            print(f"\n{i}. {status_icon} {printer['name']} ({printer['ip']})")
            print(f"   Status: {status_text}")
            print(f"   Método: {printer.get('discovery_method', 'Desconhecido')}")
            print(f"   Portas: {printer.get('ports', [])}")
            print(f"   MAC: {printer.get('mac_address', 'N/A')}")
            
            # Detalhes IPP se disponíveis
            model = printer.get('printer-make-and-model') or printer.get('model', '')
            if model:
                print(f"   Modelo: {model}")
            
            state = printer.get('printer-state', '')
            if state:
                print(f"   Estado: {state}")
            
            location = printer.get('printer-location') or printer.get('location', '')
            if location:
                print(f"   Local: {location}")
        
        print("\n" + "="*60)
        print(f"RESUMO FINAL:")
        print(f"  🟢 VERDES (prontas): {green_count}")
        print(f"  🟡 AMARELAS/VERMELHAS: {yellow_count}")
        print(f"  📊 Taxa de sucesso IPP: {green_count}/{len(printers)} ({green_count/len(printers)*100:.1f}%)")
        print("="*60)
        
        if yellow_count > 0:
            print(f"\n⚠️  DIAGNÓSTICO DAS IMPRESSORAS AMARELAS:")
            print("    Verifique se essas impressoras estão:")
            print("    - Ligadas e conectadas à rede")
            print("    - Com firmware IPP atualizado")
            print("    - Sem erros de papel/toner")
            
    else:
        print("\n❌ NENHUMA IMPRESSORA ENCONTRADA")
        print("Possíveis causas:")
        print("- Nenhuma impressora ligada na rede")
        print("- Firewall bloqueando descoberta")
        print("- Impressoras em subnet diferente")
        print("- Impressoras sem suporte a IPP/descoberta automática")
    
    print(f"\n📈 ESTATÍSTICAS:")
    print(f"- IPs testados: {discovery.stats.get('total_ips_tested', 0)}")
    print(f"- IPs responsivos: {discovery.stats.get('responsive_ips', 0)}")
    print(f"- Tempo total: {total_time:.1f}s")
    print(f"- Velocidade: {discovery.stats.get('total_ips_tested', 0)/total_time:.1f} IPs/s")
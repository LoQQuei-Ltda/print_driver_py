#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
VERSÃO CORRIGIDA PARA macOS: printer_discovery.py - Varredura 1-254 + Sistema IPP Robusto
Corrige problemas específicos do macOS para descoberta de impressoras
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
    DISCOVERY_TIMEOUT = 20        # Timeout total de descoberta
    MDNS_WAIT_TIME = 8            # Tempo de espera mDNS (aumentado para macOS)
    SSDP_WAIT_TIME = 10           # Tempo de espera SSDP
    MIN_DISCOVERY_TIME = 0        # Sem tempo mínimo forçado
    IPP_ATTRIBUTE_TIMEOUT = 12    # CRÍTICO: Tempo para buscar atributos IPP
    BATCH_SIZE = 40               # IPs por lote
    ENABLE_FULL_SCAN = True       # Habilita varredura completa
else:
    # DESENVOLVIMENTO: Valores otimizados
    BASE_TIMEOUT_REQUEST = 5
    BASE_TIMEOUT_SCAN = 1.5
    BASE_TIMEOUT_PING = 1.2       # Aumentado para macOS
    MAX_WORKERS = 100
    DISCOVERY_TIMEOUT = 20
    MDNS_WAIT_TIME = 6            # Aumentado para macOS
    SSDP_WAIT_TIME = 8
    MIN_DISCOVERY_TIME = 0
    IPP_ATTRIBUTE_TIMEOUT = 10
    BATCH_SIZE = 50
    ENABLE_FULL_SCAN = True

COMMON_PRINTER_PORTS = [631, 9100, 80, 443]

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
    """Descoberta de impressoras COMPLETA - Varredura 1-254 + IPP Robusto - CORRIGIDO PARA macOS"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.discovered_printers = {}
        self.discovery_lock = threading.Lock()
        
        # Informações do sistema
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        self.is_macos = self.system == "darwin"
        self.is_linux = self.system == "linux"
        self.is_frozen = is_frozen()
        self.is_admin = self._check_admin_privileges()
        
        # Detecção do macOS
        self.macos_version = self._detect_macos_version()
        
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
                   f"macOS: {self.is_macos}, Frozen: {self.is_frozen}, Admin: {self.is_admin}")
        logger.info(f"Configurações: SCAN_TIMEOUT={BASE_TIMEOUT_SCAN}s, "
                   f"IPP_TIMEOUT={IPP_ATTRIBUTE_TIMEOUT}s, WORKERS={MAX_WORKERS}")
        
        if self.is_macos:
            logger.info(f"🍎 MODO macOS ATIVADO - Versão: {self.macos_version}")
        
        if self.is_frozen:
            logger.info("🔒 EXECUTANDO EM MODO EMPACOTADO")
            
        logger.info(f"Bibliotecas disponíveis: zeroconf={HAS_ZEROCONF}, "
                   f"pysnmp={HAS_PYSNMP}, requests={HAS_REQUESTS}, "
                   f"netifaces={HAS_NETIFACES}, pyipp={HAS_PYIPP}")
    
    def _detect_macos_version(self):
        """Detecta versão do macOS"""
        if not self.is_macos:
            return None
        
        try:
            result = subprocess.run(['uname', '-r'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                kernel_version = result.stdout.strip()
                
                # Mapeamento aproximado Darwin -> macOS
                try:
                    major_version = int(kernel_version.split('.')[0])
                    if major_version >= 20:
                        return f"macOS 11+ (Darwin {kernel_version})"
                    elif major_version >= 19:
                        return f"macOS 10.15 (Darwin {kernel_version})"
                    else:
                        return f"macOS 10.x (Darwin {kernel_version})"
                except:
                    return f"macOS (Darwin {kernel_version})"
        except:
            pass
        
        try:
            result = subprocess.run(['sw_vers', '-productVersion'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                return f"macOS {result.stdout.strip()}"
        except:
            pass
        
        return "macOS (versão desconhecida)"
    
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
        Descoberta COMPLETA de impressoras com varredura 1-254 - OTIMIZADA PARA macOS
        """
        logger.info("=== DESCOBERTA COMPLETA DE IMPRESSORAS (1-254) - macOS ===")
        logger.info(f"Ambiente: {'EMPACOTADO' if self.is_frozen else 'DESENVOLVIMENTO'}")
        start_time = time.time()
        self.stats['start_time'] = start_time
        
        # Limpa descobertas anteriores
        self.discovered_printers.clear()
        self.tested_ips.clear()
        self.stats = {'total_ips_tested': 0, 'responsive_ips': 0, 'printers_found': 0, 'start_time': start_time}
        
        # ESPECÍFICO macOS: Força refresh do DNS primeiro
        if self.is_macos:
            self._flush_dns_cache_macos()
        
        # Força atualização do ARP primeiro
        self._update_arp_cache()
        
        # Lista de métodos de descoberta OTIMIZADA PARA macOS
        discovery_methods = []
        
        # Para macOS, Bonjour/mDNS é MUITO importante
        if self.is_macos:
            # Método nativo do macOS primeiro
            discovery_methods.append(("DNS-SD Nativo (macOS)", self._discover_dns_sd_macos))
        
        # mDNS/Zeroconf
        if HAS_ZEROCONF:
            discovery_methods.append(("mDNS/Bonjour", self._discover_mdns))
        
        # DESCOBERTA PRINCIPAL: Varredura completa da rede
        discovery_methods.append(("Varredura Completa 1-254", self._discover_complete_network_scan))
        
        # Métodos auxiliares
        discovery_methods.append(("Cache ARP", self._discover_arp_cache))
        discovery_methods.append(("IPP Direct", self._discover_ipp_direct))
        
        # macOS específicos
        if self.is_macos:
            discovery_methods.append(("CUPS Local", self._discover_cups_local_macos))
        
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
    
    def _flush_dns_cache_macos(self):
        """Força limpeza do cache DNS no macOS"""
        if not self.is_macos:
            return
        
        try:
            logger.debug("Limpando cache DNS do macOS...")
            # Comando para flush DNS no macOS
            subprocess.run(['dscacheutil', '-flushcache'], 
                         timeout=5, capture_output=True)
        except:
            try:
                # Alternativa sem sudo
                subprocess.run(['dscacheutil', '-flushcache'], 
                             timeout=5, capture_output=True)
            except:
                logger.debug("Não foi possível limpar cache DNS")
    
    def _discover_dns_sd_macos(self, subnet=None):
        """Descoberta usando dns-sd nativo do macOS"""
        if not self.is_macos:
            return 0
        
        count = 0
        logger.info("🍎 Usando DNS-SD nativo do macOS...")
        
        try:
            # Procura por serviços de impressora usando dns-sd
            services_to_find = [
                '_ipp._tcp',
                '_printer._tcp', 
                '_pdl-datastream._tcp',
                '_airprint._tcp',
                '_ipps._tcp'
            ]
            
            for service in services_to_find:
                try:
                    logger.debug(f"Buscando serviço {service}...")
                    # dns-sd -B _ipp._tcp local.
                    result = subprocess.run([
                        'dns-sd', '-B', service, 'local.'
                    ], timeout=6, capture_output=True, text=True)
                    
                    if result.returncode == 0:
                        # Processa output do dns-sd
                        for line in result.stdout.split('\n'):
                            if 'ADD' in line and service in line:
                                # Extrai informações do serviço
                                parts = line.split()
                                if len(parts) >= 6:
                                    service_name = parts[6] if len(parts) > 6 else "Unknown"
                                    logger.debug(f"Serviço encontrado: {service_name}")
                                    
                                    # Resolve o serviço para obter IP
                                    try:
                                        resolve_result = subprocess.run([
                                            'dns-sd', '-L', service_name, service, 'local.'
                                        ], timeout=3, capture_output=True, text=True)
                                        
                                        if resolve_result.returncode == 0:
                                            ip = self._extract_ip_from_dns_sd(resolve_result.stdout)
                                            if ip:
                                                printer_info = {
                                                    'ip': ip,
                                                    'name': service_name,
                                                    'discovery_method': 'DNS-SD macOS',
                                                    'service_type': service,
                                                    'ports': [631] if 'ipp' in service else [9100]
                                                }
                                                
                                                if 'ipp' in service:
                                                    printer_info['uri'] = f"ipp://{ip}/ipp/print"
                                                
                                                self._add_discovered_printer(printer_info)
                                                count += 1
                                                logger.info(f"✓ DNS-SD: {service_name} em {ip}")
                                    except subprocess.TimeoutExpired:
                                        logger.debug(f"Timeout resolvendo {service_name}")
                                    except Exception as e:
                                        logger.debug(f"Erro resolvendo {service_name}: {e}")
                
                except subprocess.TimeoutExpired:
                    logger.debug(f"Timeout buscando {service}")
                except Exception as e:
                    logger.debug(f"Erro buscando {service}: {e}")
        
        except Exception as e:
            logger.error(f"Erro DNS-SD macOS: {e}")
        
        return count
    
    def _extract_ip_from_dns_sd(self, dns_sd_output):
        """Extrai IP do output do dns-sd"""
        try:
            # Procura por padrões de IP no output
            ip_pattern = r'\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b'
            matches = re.findall(ip_pattern, dns_sd_output)
            
            # Filtra IPs válidos (não localhost)
            for match in matches:
                if not match.startswith('127.') and not match.startswith('169.254.'):
                    return match
        except:
            pass
        return None
    
    def _discover_cups_local_macos(self, subnet=None):
        """Descobre impressoras via CUPS local no macOS"""
        if not self.is_macos:
            return 0
        
        count = 0
        logger.info("🍎 Consultando CUPS local do macOS...")
        
        try:
            # lpstat -v mostra impressoras configuradas
            result = subprocess.run(['lpstat', '-v'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if 'device for' in line.lower():
                        # Extrai informações da impressora
                        # Formato típico: device for PrinterName: ipp://192.168.1.100/ipp/print
                        match = re.search(r'device for ([^:]+):\s*(.+)', line)
                        if match:
                            printer_name = match.group(1).strip()
                            device_uri = match.group(2).strip()
                            
                            # Extrai IP da URI
                            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', device_uri)
                            if ip_match:
                                ip = ip_match.group(1)
                                
                                printer_info = {
                                    'ip': ip,
                                    'name': printer_name,
                                    'discovery_method': 'CUPS Local',
                                    'uri': device_uri,
                                    'ports': [631] if 'ipp' in device_uri else [9100],
                                    'is_configured': True  # Já está configurada no CUPS
                                }
                                
                                self._add_discovered_printer(printer_info)
                                count += 1
                                logger.info(f"✓ CUPS: {printer_name} em {ip}")
            
            # Também verifica impressoras disponíveis mas não configuradas
            result2 = subprocess.run(['lpstat', '-e'], 
                                   capture_output=True, text=True, timeout=5)
            if result2.returncode == 0:
                logger.debug(f"Impressoras CUPS disponíveis: {result2.stdout.strip()}")
        
        except Exception as e:
            logger.debug(f"Erro CUPS local: {e}")
        
        return count
    
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
        """Descoberta via mDNS/Bonjour - OTIMIZADA PARA macOS"""
        if not HAS_ZEROCONF:
            return 0
        
        count = 0
        try:
            zeroconf = Zeroconf()
            listener = MDNSListener(self)
            
            # Serviços de impressora expandidos para macOS
            services = [
                "_ipp._tcp.local.",
                "_printer._tcp.local.",
                "_pdl-datastream._tcp.local.",
                "_airprint._tcp.local.",
                "_ipps._tcp.local.",
                "_http._tcp.local.",
                "_device-info._tcp.local.",
                "_cups._tcp.local.",      # CUPS específico
                "_print-caps._tcp.local." # Print capabilities
            ]
            
            browsers = []
            for service in services:
                try:
                    browser = ServiceBrowser(zeroconf, service, listener)
                    browsers.append(browser)
                except Exception as e:
                    logger.debug(f"Erro criando browser para {service}: {e}")
            
            # Aguarda anúncios - tempo maior para macOS
            wait_time = MDNS_WAIT_TIME
            logger.info(f"mDNS aguardando {wait_time}s por anúncios...")
            time.sleep(wait_time)
            
            count = len([p for p in self.discovered_printers.values() 
                        if p.get('discovery_method') == 'mDNS'])
            
            # Fecha browsers primeiro
            for browser in browsers:
                try:
                    browser.cancel()
                except:
                    pass
            
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
                if 'pdl' in props:
                    printer_info['supported_formats'] = props['pdl']
            
            if info.port:
                printer_info['ports'] = [info.port]
                if info.port == 631:
                    printer_info['uri'] = f"ipp://{ip}:631/ipp/print"
            
            self._add_discovered_printer(printer_info)
            
        except Exception as e:
            logger.debug(f"Erro processando mDNS: {str(e)}")
    
    def _discover_complete_network_scan(self, subnet=None):
        """
        DESCOBERTA PRINCIPAL: Varredura completa da rede (1-254) - OTIMIZADA PARA macOS
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
        """Descoberta usando cache ARP - CORRIGIDA PARA macOS"""
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
        """IPP Direct expandido - OTIMIZADO PARA macOS"""
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
        """Escaneia range de IPs em paralelo - OTIMIZADO PARA macOS"""
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
                
                for future in concurrent.futures.as_completed(ping_futures, timeout=20):
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
                    
                    for future in concurrent.futures.as_completed(scan_futures, timeout=40):
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
        """Ping super rápido para testar conectividade - CORRIGIDO PARA macOS"""
        try:
            if self.is_windows:
                cmd = ["ping", "-n", "1", "-w", str(int(BASE_TIMEOUT_PING * 1000)), ip]
                creation_flags = subprocess.CREATE_NO_WINDOW
            elif self.is_macos:
                # macOS usa -t para timeout em segundos
                cmd = ["ping", "-c", "1", "-t", str(int(BASE_TIMEOUT_PING)), ip]
                creation_flags = 0
            else:
                # Linux
                cmd = ["ping", "-c", "1", "-W", str(int(BASE_TIMEOUT_PING)), ip]
                creation_flags = 0
            
            result = subprocess.run(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=BASE_TIMEOUT_PING + 1,
                creationflags=creation_flags if self.is_windows else 0
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
        """Obtém redes para escanear - MELHORADA PARA macOS"""
        if subnet:
            try:
                return [ipaddress.IPv4Network(subnet, strict=False)]
            except:
                pass
        
        return self._get_local_networks()
    
    def _get_local_networks(self):
        """Detecta redes locais automaticamente - CORRIGIDA PARA macOS"""
        networks = []
        
        # Método 1: ifconfig no macOS
        if self.is_macos:
            try:
                result = subprocess.run(['ifconfig'], capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    current_interface = None
                    ip_address = None
                    netmask = None
                    
                    for line in result.stdout.split('\n'):
                        # Detecta interface
                        if line and not line.startswith('\t') and not line.startswith(' '):
                            if 'en' in line or 'wlan' in line or 'wifi' in line:
                                current_interface = line.split(':')[0]
                        
                        # Detecta IP e netmask
                        if current_interface and 'inet ' in line and 'netmask' in line:
                            parts = line.strip().split()
                            for i, part in enumerate(parts):
                                if part == 'inet' and i + 1 < len(parts):
                                    ip_address = parts[i + 1]
                                elif part == 'netmask' and i + 1 < len(parts):
                                    netmask_hex = parts[i + 1]
                                    if netmask_hex.startswith('0x'):
                                        # Converte netmask hexadecimal para decimal
                                        netmask = self._hex_to_netmask(netmask_hex)
                            
                            if ip_address and netmask and not ip_address.startswith('127.'):
                                try:
                                    network = ipaddress.IPv4Network(f"{ip_address}/{netmask}", strict=False)
                                    if network not in networks:
                                        networks.append(network)
                                        logger.debug(f"Rede detectada via ifconfig: {network}")
                                except Exception as e:
                                    logger.debug(f"Erro processando rede {ip_address}/{netmask}: {e}")
                            
                            ip_address = None
                            netmask = None
            except Exception as e:
                logger.debug(f"Erro ifconfig macOS: {e}")
        
        # Método 2: route no macOS para gateway padrão
        if self.is_macos and not networks:
            try:
                result = subprocess.run(['route', '-n', 'get', 'default'], 
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    gateway = None
                    interface = None
                    
                    for line in result.stdout.split('\n'):
                        if 'gateway:' in line:
                            gateway = line.split(':')[1].strip()
                        elif 'interface:' in line:
                            interface = line.split(':')[1].strip()
                    
                    if gateway:
                        # Assume rede /24 baseada no gateway
                        gateway_parts = gateway.split('.')
                        if len(gateway_parts) == 4:
                            network_str = f"{gateway_parts[0]}.{gateway_parts[1]}.{gateway_parts[2]}.0/24"
                            try:
                                network = ipaddress.IPv4Network(network_str)
                                networks.append(network)
                                logger.debug(f"Rede detectada via gateway: {network}")
                            except:
                                pass
            except Exception as e:
                logger.debug(f"Erro route macOS: {e}")
        
        # Método 3: netifaces se disponível
        if HAS_NETIFACES:
            try:
                for interface in netifaces.interfaces():
                    if interface.startswith('lo'):  # Skip loopback
                        continue
                        
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr.get('addr')
                            netmask = addr.get('netmask')
                            if ip and netmask and not ip.startswith('127.') and not ip.startswith('169.254.'):
                                try:
                                    network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                    if network not in networks:
                                        networks.append(network)
                                        logger.debug(f"Rede detectada via netifaces: {network}")
                                except Exception as e:
                                    logger.debug(f"Erro netifaces: {e}")
            except Exception as e:
                logger.debug(f"Erro netifaces: {e}")
        
        # Método 4: Fallback via hostname
        if not networks:
            try:
                hostname = socket.gethostname()
                for info in socket.getaddrinfo(hostname, None):
                    ip = info[4][0]
                    if not ip.startswith('127.') and '.' in ip and not ip.startswith('169.254.'):
                        try:
                            network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                            if network not in networks:
                                networks.append(network)
                                logger.debug(f"Rede detectada via hostname: {network}")
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
                    logger.debug(f"Rede fallback: {net_str}")
                except:
                    pass
        
        logger.info(f"Redes detectadas para macOS: {[str(n) for n in networks]}")
        return networks
    
    def _hex_to_netmask(self, hex_netmask):
        """Converte netmask hexadecimal para formato decimal"""
        try:
            if hex_netmask.startswith('0x'):
                hex_value = int(hex_netmask, 16)
                # Converte para formato dotted decimal
                octets = []
                for i in range(4):
                    octets.append(str((hex_value >> (8 * (3 - i))) & 0xFF))
                return '.'.join(octets)
        except:
            pass
        return None
    
    def _is_port_open(self, ip, port, timeout=1):
        """Verifica se uma porta está aberta - OTIMIZADA PARA macOS"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            # Para macOS, configura socket options adicionais
            if self.is_macos:
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _update_arp_cache(self):
        """Atualiza cache ARP para descoberta de MAC - CORRIGIDA PARA macOS"""
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
            elif self.is_macos:
                # macOS: arp -a tem formato diferente
                result = subprocess.run(
                    ['arp', '-a'],
                    capture_output=True, text=True, timeout=10
                )
            else:
                # Linux
                result = subprocess.run(
                    ['arp', '-a'],
                    capture_output=True, text=True, timeout=10
                )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if self.is_macos:
                        # Formato macOS: hostname (192.168.1.1) at aa:bb:cc:dd:ee:ff [ethernet]
                        match = re.search(
                            r'\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)\s+at\s+([0-9A-Fa-f:]+)',
                            line
                        )
                    else:
                        # Formato Windows/Linux
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
        """Obtém MAC address para um IP - CORRIGIDA PARA macOS"""
        # Verifica cache primeiro
        if ip in self.mac_cache:
            return self.mac_cache[ip]
        
        # Ping para forçar entrada no ARP
        self._quick_ping(ip)
        time.sleep(0.5)  # Tempo maior para macOS
        
        # Busca no ARP
        try:
            if self.is_windows:
                result = subprocess.run(
                    ['arp', '-a', ip],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            elif self.is_macos:
                # macOS: arp -n IP
                result = subprocess.run(
                    ['arp', '-n', ip],
                    capture_output=True, text=True, timeout=5
                )
            else:
                # Linux
                result = subprocess.run(
                    ['arp', '-n', ip],
                    capture_output=True, text=True, timeout=5
                )
            
            if result.returncode == 0:
                logger.debug(f"ARP output para {ip}: {result.stdout}")
                
                if self.is_macos:
                    # Formato macOS: "10.148.1.20 (10.148.1.20) at 50:57:9c:6b:48:88 on en0 ifscope [ethernet]"
                    # ou: "? (10.148.1.20) at 50:57:9c:6b:48:88 on en0 ifscope [ethernet]"
                    match = re.search(r'at\s+([0-9A-Fa-f:]+)', result.stdout)
                    if not match:
                        # Formato alternativo: só o MAC
                        match = re.search(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2}:[0-9A-Fa-f]{2})', result.stdout)
                else:
                    match = re.search(r'([0-9A-Fa-f:.-]+)', result.stdout)
                
                if match:
                    mac = self.normalize_mac(match.group(1))
                    if mac:
                        self.mac_cache[ip] = mac
                        logger.debug(f"MAC encontrado para {ip}: {mac}")
                        return mac
                    else:
                        logger.debug(f"MAC inválido para {ip}: {match.group(1)}")
                else:
                    logger.debug(f"Nenhum MAC encontrado no ARP para {ip}")
        except Exception as e:
            logger.debug(f"Erro ARP para {ip}: {e}")
        
        # Tentativa adicional para macOS: usar ping + arp -a
        if self.is_macos:
            try:
                # Ping múltiplo para forçar ARP
                for _ in range(3):
                    subprocess.run(['ping', '-c', '1', '-W', '1000', ip], 
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
                    time.sleep(0.1)
                
                # ARP table completa
                result = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if ip in line:
                            match = re.search(r'at\s+([0-9A-Fa-f:]+)', line)
                            if match:
                                mac = self.normalize_mac(match.group(1))
                                if mac:
                                    self.mac_cache[ip] = mac
                                    logger.debug(f"MAC encontrado via arp -a para {ip}: {mac}")
                                    return mac
            except Exception as e:
                logger.debug(f"Erro arp -a para {ip}: {e}")
        
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
        """Obtém detalhes específicos de uma impressora - MELHORADA"""
        logger.debug(f"Obtendo detalhes para {ip}")
        
        # Scan básico do IP
        result = self._scan_single_ip_comprehensive(ip)
        
        if result and 631 in result.get('ports', []) and HAS_PYIPP:
            logger.debug(f"Enriquecendo {ip} com IPP")
            self._enrich_with_ipp_details(result)
        
        return result
    
    def correlate_discovered_with_configured(self, discovered_printers, configured_printers):
        """
        NOVA FUNÇÃO: Correlaciona impressoras descobertas com as configuradas
        usando MAC, nome e modelo como critérios
        """
        logger.info(f"Correlacionando {len(discovered_printers)} descobertas com {len(configured_printers)} configuradas")
        
        # Força atualização completa do ARP
        self._update_arp_cache()
        
        # Obtém MACs atualizados para todas as impressoras descobertas
        for printer in discovered_printers:
            ip = printer.get('ip')
            if ip and not printer.get('mac_address'):
                mac = self._get_mac_for_ip(ip)
                if mac != "desconhecido":
                    printer['mac_address'] = mac
                    logger.info(f"MAC atualizado para {ip}: {mac}")
        
        # Correlaciona impressoras
        correlated = []
        for configured in configured_printers:
            config_mac = self.normalize_mac(configured.get('mac_address', ''))
            config_name = configured.get('name', '').lower()
            
            best_match = None
            match_score = 0
            
            for discovered in discovered_printers:
                score = 0
                
                # Critério 1: MAC address (peso 100)
                discovered_mac = self.normalize_mac(discovered.get('mac_address', ''))
                if config_mac and discovered_mac and config_mac == discovered_mac:
                    score += 100
                    logger.info(f"MAC match: {config_name} <-> {discovered.get('ip')} ({config_mac})")
                
                # Critério 2: Nome/Modelo (peso 50)
                discovered_model = discovered.get('printer-make-and-model', '').lower()
                discovered_name = discovered.get('name', '').lower()
                
                if config_name and (discovered_model or discovered_name):
                    # Verifica se o nome configurado contém partes do modelo descoberto
                    config_parts = config_name.replace('_', ' ').split()
                    discovered_text = (discovered_model + ' ' + discovered_name).lower()
                    
                    for part in config_parts:
                        if len(part) > 2 and part in discovered_text:
                            score += 10
                            logger.debug(f"Nome match: '{part}' em '{discovered_text}'")
                
                # Critério 3: Porta IPP (peso 20)
                if 631 in discovered.get('ports', []):
                    score += 20
                
                # Escolhe o melhor match
                if score > match_score:
                    match_score = score
                    best_match = discovered
            
            # Se encontrou um match razoável
            if best_match and match_score >= 50:  # Mínimo de 50 pontos
                # Mescla informações
                merged = configured.copy()
                merged.update({
                    'ip': best_match.get('ip'),
                    'mac_address': best_match.get('mac_address', configured.get('mac_address')),
                    'ports': best_match.get('ports', []),
                    'uri': best_match.get('uri'),
                    'is_online': True,
                    'is_ready': best_match.get('is_ready', True),
                    'printer-make-and-model': best_match.get('printer-make-and-model', ''),
                    'printer-state': best_match.get('printer-state', 'Online'),
                    'discovery_method': best_match.get('discovery_method', 'Network Scan'),
                    'discovery_score': match_score
                })
                
                logger.info(f"✓ Correlação: {configured.get('name')} -> {best_match.get('ip')} (score: {match_score})")
                correlated.append(merged)
            else:
                # Não encontrou match - mantém offline
                offline = configured.copy()
                offline.update({
                    'ip': '',
                    'is_online': False,
                    'is_ready': False,
                    'discovery_method': 'Not Found'
                })
                logger.warning(f"✗ Sem correlação: {configured.get('name')} (melhor score: {match_score})")
                correlated.append(offline)
        
        logger.info(f"Correlação concluída: {len(correlated)} impressoras processadas")
        return correlated

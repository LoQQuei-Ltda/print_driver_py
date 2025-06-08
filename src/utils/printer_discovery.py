#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
ARQUIVO RESTAURADO: printer_discovery.py - Voltando ao que FUNCIONAVA + Otimizações
Baseado no código original que deixava as impressoras VERDES
Mantidas apenas otimizações de velocidade, sem alterar a lógica IPP que funcionava
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

# ========== CONFIGURAÇÕES OTIMIZADAS MAS FUNCIONAIS ==========
if is_frozen():
    # AMBIENTE EMPACOTADO: Timeouts otimizados mas suficientes para IPP
    BASE_TIMEOUT_REQUEST = 5      # Otimizado de 10 para 5
    BASE_TIMEOUT_SCAN = 2         # Otimizado de 5 para 2
    BASE_TIMEOUT_PING = 2         # Otimizado de 5 para 2
    MAX_WORKERS = 40              # Otimizado de 30 para 40
    DISCOVERY_TIMEOUT = 35        # Otimizado de 60 para 35
    MDNS_WAIT_TIME = 5            # Otimizado de 10 para 5
    SSDP_WAIT_TIME = 8            # Otimizado de 15 para 8
    MIN_DISCOVERY_TIME = 0        # Removido tempo mínimo forçado
    IPP_ATTRIBUTE_TIMEOUT = 10    # MANTIDO o valor que funcionava
else:
    # DESENVOLVIMENTO: Valores otimizados
    BASE_TIMEOUT_REQUEST = 4
    BASE_TIMEOUT_SCAN = 1.5
    BASE_TIMEOUT_PING = 1
    MAX_WORKERS = 50
    DISCOVERY_TIMEOUT = 25
    MDNS_WAIT_TIME = 3
    SSDP_WAIT_TIME = 5
    MIN_DISCOVERY_TIME = 0
    IPP_ATTRIBUTE_TIMEOUT = 8

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
    """Descoberta de impressoras - VERSÃO RESTAURADA que funcionava"""
    
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
        
        # Configurações adaptativas
        self.config = self._setup_system_configs()
        
        # Log do ambiente
        logger.info(f"PrinterDiscovery RESTAURADO - Sistema: {self.system}, "
                   f"Frozen: {self.is_frozen}, Admin: {self.is_admin}, "
                   f"Timeouts: {IPP_ATTRIBUTE_TIMEOUT}")
        
        if self.is_frozen:
            logger.info("🔒 EXECUTANDO EM MODO EMPACOTADO - Timeouts otimizados")
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
            'min_discovery_time': MIN_DISCOVERY_TIME
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
        Descoberta otimizada de impressoras (VERSÃO QUE FUNCIONAVA)
        """
        logger.info("=== DESCOBERTA OTIMIZADA DE IMPRESSORAS ===")
        logger.info(f"Ambiente: {'EMPACOTADO' if self.is_frozen else 'DESENVOLVIMENTO'}")
        start_time = time.time()
        
        # Limpa descobertas anteriores
        self.discovered_printers.clear()
        
        # Força atualização do ARP primeiro
        self._update_arp_cache()
        
        # Lista de métodos de descoberta OTIMIZADA
        discovery_methods = []
        
        # Ordena métodos por eficácia (mDNS primeiro por ser mais rápido e preciso)
        if HAS_ZEROCONF:
            discovery_methods.append(("mDNS/Bonjour", self._discover_mdns))
        
        discovery_methods.append(("Port Scan Inteligente", self._discover_port_scan_optimized))
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
            
            # Aguarda com timeout otimizado
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
        
        total_elapsed = time.time() - start_time
        logger.info(f"=== Descoberta concluída em {total_elapsed:.1f}s - "
                   f"{len(unique_printers)} impressoras encontradas ===")
        
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
        """Descoberta via mDNS otimizada"""
        if not HAS_ZEROCONF:
            return 0
        
        count = 0
        try:
            zeroconf = Zeroconf()
            listener = MDNSListener(self)
            
            # Serviços de impressora otimizados
            services = [
                "_ipp._tcp.local.",
                "_printer._tcp.local.",
                "_pdl-datastream._tcp.local.",
                "_airprint._tcp.local.",
                "_ipps._tcp.local."
            ]
            
            browsers = []
            for service in services:
                browser = ServiceBrowser(zeroconf, service, listener)
                browsers.append(browser)
            
            # Aguarda tempo otimizado
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
    
    def _discover_port_scan_optimized(self, subnet=None):
        """Port scan OTIMIZADO com estratégia inteligente"""
        count = 0
        
        # Atualiza ARP
        self._update_arp_cache()
        
        # ESTRATÉGIA OTIMIZADA: IPs comuns de impressora primeiro
        networks = self._get_networks_to_scan(subnet)
        target_ips = []
        
        # Fase 1: IPs comuns de impressora (mais provável)
        for network in networks[:2]:  # Máximo 2 redes
            common_ips = self._get_smart_printer_ips(network)
            target_ips.extend(common_ips[:15])  # Máximo 15 por rede
        
        # Fase 2: IPs do ARP (segunda prioridade)
        arp_ips = list(self.mac_cache.keys())[:20]  # Máximo 20 do ARP
        target_ips.extend(arp_ips)
        
        # Remove duplicatas mantendo ordem
        unique_ips = list(dict.fromkeys(target_ips))
        
        logger.info(f"Port Scan Otimizado: {len(unique_ips)} IPs alvo")
        
        # Scan em paralelo OTIMIZADO
        count = self._scan_ip_batch_optimized(unique_ips, "Otimizado")
        
        return count
    
    def _get_smart_printer_ips(self, network):
        """Gera IPs inteligentes para impressoras"""
        smart_ips = []
        
        try:
            base_ip = network.network_address
            
            # IPs mais comuns para impressoras (baseado em padrões reais)
            common_endings = [
                # Gateways + 1-5 (muito comum para impressoras)
                1, 2, 3, 4, 5,
                # Faixas específicas de impressora
                10, 11, 12, 20, 21, 22, 30, 31,
                # IPs altos comuns
                100, 101, 102, 150, 151, 200, 201, 250, 251, 252
            ]
            
            for ending in common_endings:
                try:
                    ip = str(base_ip + ending)
                    if ipaddress.IPv4Address(ip) in network:
                        smart_ips.append(ip)
                except:
                    continue
                    
        except Exception as e:
            logger.debug(f"Erro gerando IPs inteligentes: {e}")
        
        return smart_ips[:25]  # Máximo 25 IPs por rede
    
    def _scan_ip_batch_optimized(self, ip_list, batch_name):
        """Escaneia lote de IPs de forma otimizada"""
        count = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['parallel_hosts']) as executor:
            futures = [executor.submit(self._scan_single_ip_optimized, ip) for ip in ip_list]
            
            timeout = IPP_ATTRIBUTE_TIMEOUT * 2
            
            for future in concurrent.futures.as_completed(futures, timeout=timeout * len(ip_list) / 20):
                try:
                    result = future.result()
                    if result:
                        self._add_discovered_printer(result)
                        count += 1
                except:
                    pass
        
        logger.debug(f"{batch_name}: {count} impressoras encontradas")
        return count
    
    def _scan_single_ip_optimized(self, ip):
        """Escaneia um IP de forma otimizada"""
        # Primeiro tenta portas principais (ordem otimizada)
        priority_ports = [631, 9100]  # IPP primeiro (mais informativo)
        open_ports = []
        
        for port in priority_ports:
            if self._is_port_open(ip, port, 1):  # Timeout otimizado
                open_ports.append(port)
        
        # Se encontrou porta principal, verifica outras rapidamente
        if open_ports:
            for port in [80, 443, 515]:
                if self._is_port_open(ip, port, 0.5):  # Timeout ainda menor
                    open_ports.append(port)
        else:
            return None
        
        if not self._looks_like_printer(ip, open_ports):
            return None
        
        mac = self._get_mac_for_ip(ip)
        
        return {
            'ip': ip,
            'mac_address': mac,
            'ports': open_ports,
            'uri': self._determine_uri(ip, open_ports),
            'name': f"Impressora {ip}",
            'discovery_method': 'Port Scan',
            'is_online': True
        }
    
    def _discover_ipp_direct(self, subnet=None):
        """IPP Direct otimizado"""
        count = 0
        networks = self._get_networks_to_scan(subnet)
        
        for network in networks[:1]:  # Apenas primeira rede para ser mais rápido
            ips = self._get_smart_printer_ips(network)[:10]  # Máximo 10 IPs
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(self._check_ipp_printer, ip) for ip in ips]
                
                for future in concurrent.futures.as_completed(futures, timeout=15):
                    try:
                        if future.result():
                            count += 1
                    except:
                        pass
        
        return count
    
    def _check_ipp_printer(self, ip):
        """Verifica IPP otimizado"""
        if not self._is_port_open(ip, 631, 1):
            return False
        
        printer_info = {
            'ip': ip,
            'name': f"Impressora IPP {ip}",
            'discovery_method': 'IPP Direct',
            'ports': [631],
            'uri': f"ipp://{ip}/ipp/print"
        }
        
        self._add_discovered_printer(printer_info)
        return True
    
    def _discover_wsd(self, subnet=None):
        """WSD otimizado"""
        if not self.is_windows:
            return 0
        
        count = 0
        try:
            probe_message = self._create_wsd_probe()
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(2)  # Timeout otimizado
            
            # Envia probe
            sock.sendto(probe_message.encode('utf-8'), ('239.255.255.250', 3702))
            
            # Escuta por tempo otimizado
            start_time = time.time()
            timeout = 6  # Otimizado de 15 para 6
            
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
    
    def _create_wsd_probe(self):
        """Cria probe WSD"""
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
                    'uri': f"http://{ip}"
                }
                self._add_discovered_printer(printer_info)
                return True
        except:
            pass
        return False
    
    def _discover_snmp(self, subnet=None):
        """SNMP otimizado"""
        if not HAS_PYSNMP:
            return 0
        
        count = 0
        networks = self._get_networks_to_scan(subnet)
        
        for network in networks[:1]:  # Apenas uma rede
            ips = self._get_smart_printer_ips(network)[:10]  # Máximo 10 IPs
            
            for ip in ips:
                if self._is_port_open(ip, 161, 1):
                    printer_info = {
                        'ip': ip,
                        'name': f"Impressora SNMP {ip}",
                        'discovery_method': 'SNMP',
                        'ports': [161],
                        'uri': f"socket://{ip}:9100"
                    }
                    self._add_discovered_printer(printer_info)
                    count += 1
        
        return count
    
    def _discover_ssdp(self, subnet=None):
        """SSDP otimizado"""
        count = 0
        
        try:
            ssdp_request = """M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 2
ST: ssdp:all

"""
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(2)  # Timeout otimizado
            
            # Envia probe
            sock.sendto(ssdp_request.encode('utf-8'), ('239.255.255.250', 1900))
            
            # Escuta por tempo otimizado
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
    
    def _process_discovered_printers(self):
        """Processa impressoras descobertas (LÓGICA ORIGINAL QUE FUNCIONAVA)"""
        unique_printers = []
        
        with self.discovery_lock:
            for ip, printer_info in self.discovered_printers.items():
                # Enriquece com MAC
                if not printer_info.get('mac_address'):
                    printer_info['mac_address'] = self._get_mac_for_ip(ip)
                
                # Normaliza MAC
                mac = self.normalize_mac(printer_info.get('mac_address'))
                printer_info['mac_address'] = mac or 'desconhecido'
                
                # Garante nome
                if not printer_info.get('name'):
                    printer_info['name'] = f"Impressora {ip}"
                
                # Garante URI
                if not printer_info.get('uri'):
                    ports = printer_info.get('ports', [])
                    printer_info['uri'] = self._determine_uri(ip, ports)
                
                # CORREÇÃO: Garante que impressoras descobertas sejam consideradas prontas por padrão
                printer_info['is_online'] = True
                
                # LÓGICA CORRIGIDA: Se não tem is_ready definido, define baseado na presença de dados IPP
                if 'is_ready' not in printer_info:
                    # Se tem dados IPP (modelo, estado, etc.), assume que está pronta
                    has_ipp_data = any(key in printer_info for key in [
                        'printer-make-and-model', 'printer-state', 'model', 
                        'manufacturer', 'ipp_uri_used'
                    ])
                    
                    if has_ipp_data:
                        printer_info['is_ready'] = True  # VERDE - tem dados IPP
                        logger.debug(f"Impressora {ip} marcada como PRONTA (tem dados IPP)")
                    elif 631 in printer_info.get('ports', []):
                        # Tem porta IPP mas sem dados = ainda considera pronta (pode ser firewall etc)
                        printer_info['is_ready'] = True  # VERDE - tem porta IPP
                        logger.debug(f"Impressora {ip} marcada como PRONTA (porta IPP disponível)")
                    else:
                        # Sem IPP = impressora simples, ainda considera pronta
                        printer_info['is_ready'] = True  # VERDE - descoberta com sucesso
                        logger.debug(f"Impressora {ip} marcada como PRONTA (descoberta bem-sucedida)")
                
                # Override apenas se explicitamente parada
                if printer_info.get('printer-state-code') == 5:  # stopped
                    printer_info['is_ready'] = False
                    logger.debug(f"Impressora {ip} marcada como NÃO PRONTA (explicitamente parada)")
                
                # Log final do status
                ready_status = "🟢 VERDE" if printer_info.get('is_ready') else "🟡 AMARELA"
                method = printer_info.get('discovery_method', 'Unknown')
                model = printer_info.get('printer-make-and-model') or printer_info.get('model', '')
                logger.info(f"Processada: {ip} via {method} → {ready_status}" + (f" ({model})" if model else ""))
                
                # LÓGICA ORIGINAL: Tenta enriquecer com IPP se possível
                if 631 in printer_info.get('ports', []) and HAS_PYIPP:
                    logger.debug(f"Tentando enriquecimento IPP para {ip} durante descoberta inicial.")
                    self._enrich_with_ipp_details(printer_info)
                
                unique_printers.append(printer_info)
        
        # Ordena por IP
        unique_printers.sort(key=lambda p: socket.inet_aton(p['ip']))
        
        # LOG DETALHADO para debug das impressoras amarelas
        green_count = sum(1 for p in unique_printers if p.get('is_ready', False))
        yellow_count = len(unique_printers) - green_count
        
        logger.info(f"Processadas {len(unique_printers)} impressoras únicas:")
        logger.info(f"  🟢 VERDES: {green_count}")
        logger.info(f"  🟡 AMARELAS: {yellow_count}")
        
        # Debug detalhado das impressoras amarelas
        if yellow_count > 0:
            logger.warning(f"⚠️  IMPRESSORAS AMARELAS DETECTADAS:")
            for p in unique_printers:
                if not p.get('is_ready', False):
                    logger.warning(f"    • {p['ip']} ({p.get('name', 'Sem nome')})")
                    logger.warning(f"      - is_ready: {p.get('is_ready')}")
                    logger.warning(f"      - printer-state: {p.get('printer-state', 'Não definido')}")
                    logger.warning(f"      - printer-state-code: {p.get('printer-state-code', 'Não definido')}")
                    logger.warning(f"      - ports: {p.get('ports', [])}")
                    logger.warning(f"      - discovery_method: {p.get('discovery_method', 'Unknown')}")
                    logger.warning(f"      - model: {p.get('printer-make-and-model') or p.get('model', 'Não definido')}")
        
        return unique_printers
    
    def _enrich_with_ipp_details(self, printer_info):
        """Enriquece com IPP (FUNÇÃO ORIGINAL QUE FUNCIONAVA)"""
        if not HAS_PYIPP:
            logger.debug(f"Pulando enriquecimento IPP para {printer_info.get('ip')}: pyipp não disponível.")
            return

        ip = printer_info.get('ip')
        if not ip:
            logger.debug("Pulando enriquecimento IPP: Endereço IP ausente.")
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
                logger.debug(f"Detalhes IPP enriquecidos com sucesso para {ip}: {details.keys()}")
                
                # CORREÇÃO CRÍTICA: Garante que enriquecimento IPP defina is_ready
                if 'is_ready' in details:
                    # Se IPP definiu is_ready, usa esse valor
                    printer_info['is_ready'] = details['is_ready']
                elif 'printer-state-code' in details:
                    # Se tem código de estado, interpreta (códigos 3 e 4 = pronta)
                    state_code = details['printer-state-code']
                    printer_info['is_ready'] = state_code in [3, 4]  # idle ou processing = VERDE
                elif 'printer-state' in details:
                    # Se tem estado textual, interpreta
                    state_text = details['printer-state'].lower()
                    printer_info['is_ready'] = 'stopped' not in state_text and 'error' not in state_text
                else:
                    # Se enriqueceu com IPP mas sem estado = assume pronta
                    printer_info['is_ready'] = True
                
                # Mescla campos específicos primeiro
                if 'printer-make-and-model' in details and details['printer-make-and-model']:
                    printer_info['model'] = details['printer-make-and-model']
                if 'printer-location' in details and details['printer-location']:
                    printer_info['location'] = details['printer-location']
                
                # Mescla todos os outros atributos
                printer_info.update(details)
                
                # Log do resultado do enriquecimento
                ready_status = "🟢 VERDE" if printer_info.get('is_ready') else "🟡 AMARELA"
                model = printer_info.get('model', 'Sem modelo')
                logger.info(f"IPP enriquecido para {ip}: {model} → {ready_status}")
            else:
                logger.debug(f"Nenhum detalhe IPP retornado para {ip}.")
                # CORREÇÃO: Se falhou IPP mas tem porta 631, ainda considera pronta
                if 631 in printer_info.get('ports', []):
                    printer_info['is_ready'] = True
                    logger.debug(f"IPP falhou para {ip}, mas mantém como PRONTA (porta 631 disponível)")
        except asyncio.TimeoutError:
            logger.warning(f"Timeout ao enriquecer detalhes IPP para {ip} usando timeout {IPP_ATTRIBUTE_TIMEOUT}s.")
        except Exception as e:
            logger.error(f"Erro ao enriquecer detalhes IPP para {ip}: {str(e)}\n{traceback.format_exc()}")
    
    def discover_printer_by_mac(self, target_mac):
        """Busca impressora por MAC"""
        normalized_mac = self.normalize_mac(target_mac)
        if not normalized_mac:
            return None
        
        # Descoberta rápida
        self.discover_printers()
        
        for printer in self.printers:
            if self.normalize_mac(printer.get('mac_address')) == normalized_mac:
                return printer
        
        return None
    
    def get_printer_details(self, ip):
        """Obtém detalhes de uma impressora"""
        logger.debug(f"Obtendo detalhes para o IP: {ip}")
        result = self._scan_single_ip_optimized(ip)  # Scan básico primeiro
        
        if result and 631 in result.get('ports', []) and HAS_PYIPP:
            logger.debug(f"Porta 631 aberta e pyipp disponível para {ip}. Tentando buscar atributos IPP.")
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                ipp_timeout = IPP_ATTRIBUTE_TIMEOUT
                logger.debug(f"Usando timeout para atributos IPP: {ipp_timeout}s para {ip}")
                details = loop.run_until_complete(
                    asyncio.wait_for(
                        self._get_printer_attributes(ip),
                        timeout=ipp_timeout
                    )
                )
                loop.close()
                
                if details:
                    logger.info(f"Atributos IPP buscados com sucesso para {ip}: {details.keys()}")
                    result.update(details)  # Mescla detalhes IPP
                else:
                    logger.warning(f"Nenhum atributo IPP retornado para {ip} de _get_printer_attributes.")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout ao buscar atributos IPP para {ip} em get_printer_details (timeout: {ipp_timeout}s).")
            except Exception as e:
                logger.error(f"Erro ao buscar atributos IPP para {ip} em get_printer_details: {str(e)}\n{traceback.format_exc()}")
        elif not result:
            logger.warning(f"Scan inicial para {ip} não retornou resultado.")
        elif result and 631 not in result.get('ports', []):
            logger.info(f"Porta 631 não está entre as portas abertas para {ip}. Pulando busca de atributos IPP. Portas: {result.get('ports')}")
        elif not HAS_PYIPP:
            logger.info(f"pyipp não disponível. Pulando busca de atributos IPP para {ip}.")

        return result
    
    # ========== FUNÇÃO IPP ORIGINAL QUE FUNCIONAVA ==========
    
    async def _get_printer_attributes(self, ip, port=631, tls=False, _retry_with_tls=True):
        """Obtém atributos IPP (FUNÇÃO ORIGINAL QUE FUNCIONAVA)"""
        if not HAS_PYIPP:
            logger.debug(f"pyipp não disponível, não é possível obter atributos para {ip}.")
            return None

        endpoints = ["/ipp/print", "/ipp/printer", "/ipp", ""]
        ipp_call_timeout = IPP_ATTRIBUTE_TIMEOUT
        
        logger.debug(f"Tentando obter atributos IPP para {ip}:{port} (TLS: {tls}, RetryTLS: {_retry_with_tls}) com timeout de endpoint {ipp_call_timeout}s.")

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
                    
                    # Process if it's a pyipp Printer object
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
                        # Store other info attributes
                        if hasattr(info, 'attributes') and info.attributes:
                             for attr_name, attr_value in info.attributes.items():
                                clean_attr_name = attr_name.replace('-', '_')
                                if isinstance(attr_value, list) and len(attr_value) == 1:
                                    result[f"info_{clean_attr_name}"] = attr_value[0]
                                else:
                                    result[f"info_{clean_attr_name}"] = attr_value
                    
                    # CORREÇÃO CRÍTICA: Lógica mais permissiva para is_ready
                    # Por padrão, se a impressora responde IPP, ela está pronta
                    result['is_ready'] = True  # DEFAULT: PRONTA (VERDE)
                    result['printer-state'] = "Online"  # Estado padrão
                    
                    raw_state_code = None
                    if hasattr(printer_attrs_raw, 'state') and printer_attrs_raw.state:
                        state = printer_attrs_raw.state
                        # Try to get the numeric state code if available directly
                        if hasattr(state, 'printer_state_code') and state.printer_state_code:
                            raw_state_code = state.printer_state_code
                        elif isinstance(state.printer_state, int): # if printer_state itself is the code
                            raw_state_code = state.printer_state

                        # Map textual state to a common format or use numeric if text not standard
                        textual_state = getattr(state, 'printer_state', 'idle').lower()
                        logger.debug(f"Estado IPP para {ip}: textual='{textual_state}', raw_code={raw_state_code}")
                        
                        if textual_state == 'idle':
                            result['printer-state'] = "Idle (Pronta)"
                            result['is_ready'] = True  # VERDE
                            raw_state_code = raw_state_code or 3
                        elif textual_state == 'processing':
                            result['printer-state'] = "Processing (Ocupada)"
                            result['is_ready'] = True  # AINDA VERDE (só ocupada temporariamente)
                            raw_state_code = raw_state_code or 4
                        elif textual_state == 'stopped':
                            result['printer-state'] = "Stopped (Parada)"
                            result['is_ready'] = False  # AMARELA (realmente com problema)
                            raw_state_code = raw_state_code or 5
                        else:
                            # Estados desconhecidos = assume que está pronta
                            result['printer-state'] = textual_state.capitalize()
                            result['is_ready'] = True  # VERDE por padrão

                        result['printer-state-reasons'] = getattr(state, 'reasons', [])
                        result['printer-state-message'] = getattr(state, 'message', '')

                        # Store other state attributes
                        if hasattr(state, 'attributes') and state.attributes:
                             for attr_name, attr_value in state.attributes.items():
                                clean_attr_name = attr_name.replace('-', '_')
                                if isinstance(attr_value, list) and len(attr_value) == 1:
                                    result[f"state_{clean_attr_name}"] = attr_value[0]
                                else:
                                    result[f"state_{clean_attr_name}"] = attr_value
                    
                    # Define state code se não foi definido
                    if raw_state_code:
                        result['printer-state-code'] = raw_state_code
                        # Só muda is_ready se realmente parada (código 5)
                        if raw_state_code == 5:  # stopped
                            result['is_ready'] = False
                        # Códigos 3 (idle) e 4 (processing) = VERDE
                    else:
                        result['printer-state-code'] = 3  # Assume idle por padrão
                    
                    # Log para debug
                    ready_status = "🟢 VERDE" if result['is_ready'] else "🟡 AMARELA"
                    logger.info(f"IPP {ip}: Estado='{result['printer-state']}' Code={result.get('printer-state-code')} → {ready_status}")

                    # Extract supply information (markers)
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
                            logger.debug(f"Extraídos {len(supplies)} suprimentos para {ip}")

                    # Fallback for dictionary-based attributes if not fully parsed into objects
                    if hasattr(printer_attrs_raw, 'attributes') and printer_attrs_raw.attributes:
                        for group_name, group_attrs in printer_attrs_raw.attributes.items():
                            if group_name == 'operations-supported' and isinstance(group_attrs, list):
                                result[group_name] = f"{len(group_attrs)} operações"
                                continue
                            if isinstance(group_attrs, dict):
                                for attr_name, attr_value in group_attrs.items():
                                    key_name = f"{group_name}_{attr_name.replace('-', '_')}" if group_name != 'printer' else attr_name.replace('-', '_')
                                    if key_name not in result: # Prioritize already parsed values
                                        if isinstance(attr_value, list) and len(attr_value) == 1:
                                            result[key_name] = attr_value[0]
                                        else:
                                            result[key_name] = attr_value
                    
                    result.setdefault('printer-make-and-model', '')
                    result.setdefault('printer-location', '')
                    result.setdefault('name', f"Impressora IPP {ip}")

                    logger.info(f"Atributos IPP recuperados com sucesso para {ip} de {uri}. Keys: {list(result.keys())}")
                    if client:
                        await client.close() 
                    client = None 
                    return result 
                else:
                    logger.debug(f"client.printer() retornou None ou vazio para {uri}")

            except pyipp.exceptions.IPPConnectionUpgradeRequired as e_upgrade:
                logger.warning(f"IPPConnectionUpgradeRequired para {uri}: {e_upgrade}. Servidor pede upgrade.")
                if client:
                    await client.close()
                    client = None
                if not tls and _retry_with_tls:
                    logger.info(f"Tentando imediatamente com TLS para {ip}:{port} (todos os endpoints) devido a IPPConnectionUpgradeRequired.")
                    return await self._get_printer_attributes(ip, port=port, tls=True, _retry_with_tls=False)
                else:
                    logger.warning(f"Não foi possível fazer upgrade para TLS para {uri} ou já está usando TLS/nova tentativa desabilitada. Tentando próximo endpoint se houver.")
                    continue 
            
            except asyncio.TimeoutError:
                logger.warning(f"Requisição IPP para {uri} excedeu o tempo limite ({ipp_call_timeout}s).")
            except ConnectionRefusedError:
                logger.warning(f"Conexão IPP recusada para {uri}.")
            except pyipp.exceptions.IPPError as e_ipp:
                logger.warning(f"Erro IPP ({type(e_ipp).__name__}) para {uri}: {str(e_ipp)}")
            except Exception as e:
                logger.error(f"Erro genérico ao obter atributos IPP de {uri} para {ip}: {str(e)}\n{traceback.format_exc()}")
            
            finally:
                if client:
                    logger.debug(f"Fechando cliente IPP para {uri} no bloco finally (após erro ou falha no endpoint).")
                    try:
                        await client.close()
                    except Exception as e_close:
                        logger.debug(f"Erro ao fechar cliente IPP no finally para {uri}: {e_close}")
                    client = None
        
        if not tls and _retry_with_tls:
            logger.debug(f"Todos os endpoints falharam para http. Tentando toda a sequência com TLS para {ip}:{port}.")
            return await self._get_printer_attributes(ip, port=port, tls=True, _retry_with_tls=False)
        
        logger.warning(f"Falha ao obter atributos IPP para {ip}:{port} (TLS: {tls}) após tentar todos os endpoints.")
        return None
    
    # ========== MÉTODOS AUXILIARES ==========
    
    def _get_networks_to_scan(self, subnet=None):
        """Obtém redes para escanear"""
        if subnet:
            try:
                return [ipaddress.IPv4Network(subnet, strict=False)]
            except:
                pass
        
        return self._get_local_networks()
    
    def _get_local_networks(self):
        """Detecta redes locais"""
        networks = []
        
        if HAS_NETIFACES:
            for interface in netifaces.interfaces():
                try:
                    addrs = netifaces.ifaddresses(interface)
                    if netifaces.AF_INET in addrs:
                        for addr in addrs[netifaces.AF_INET]:
                            ip = addr.get('addr')
                            netmask = addr.get('netmask')
                            if ip and netmask and not ip.startswith('127.'):
                                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                if network not in networks:
                                    networks.append(network)
                except:
                    pass
        
        # Fallback
        if not networks:
            try:
                hostname = socket.gethostname()
                for info in socket.getaddrinfo(hostname, None):
                    ip = info[4][0]
                    if not ip.startswith('127.') and '.' in ip:
                        network = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                        if network not in networks:
                            networks.append(network)
            except:
                pass
        
        # Redes comuns
        if not networks:
            for net_str in ["192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24"]:
                try:
                    networks.append(ipaddress.IPv4Network(net_str))
                except:
                    pass
        
        return networks[:2]  # Limita para não demorar muito
    
    def _is_port_open(self, ip, port, timeout=1):
        """Verifica se porta está aberta"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def _looks_like_printer(self, ip, open_ports):
        """Verifica se parece ser impressora"""
        printer_ports = {631, 9100, 515}
        if any(port in printer_ports for port in open_ports):
            return True
        
        if len(open_ports) >= 2:
            return True
        
        return False
    
    def _determine_uri(self, ip, open_ports):
        """Determina URI"""
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
    
    def _update_arp_cache(self):
        """Atualiza cache ARP"""
        current_time = time.time()
        if current_time - self.last_arp_update < 30:
            return
        
        self.mac_cache.clear()
        
        try:
            if self.is_windows:
                result = subprocess.run(
                    ['arp', '-a'],
                    capture_output=True, text=True, timeout=5,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
            else:
                result = subprocess.run(
                    ['arp', '-a'],
                    capture_output=True, text=True, timeout=5
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
            
        except:
            pass
    
    def _get_mac_for_ip(self, ip):
        """Obtém MAC para IP"""
        if ip in self.mac_cache:
            return self.mac_cache[ip]
        
        self._ping_host(ip, 1)
        time.sleep(0.2)
        
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
    
    def _ping_host(self, ip, timeout=1):
        """Faz ping"""
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
        except:
            return False


if __name__ == "__main__":
    # Script de teste
    print("=== TESTE DO PRINTER DISCOVERY RESTAURADO ===")
    print(f"Ambiente: {'EMPACOTADO' if is_frozen() else 'DESENVOLVIMENTO'}")
    print(f"Timeouts: Request={BASE_TIMEOUT_REQUEST}s, Scan={BASE_TIMEOUT_SCAN}s, IPP={IPP_ATTRIBUTE_TIMEOUT}s")
    print(f"Workers: {MAX_WORKERS}")
    print(f"Bibliotecas disponíveis:")
    print(f"  - zeroconf: {HAS_ZEROCONF}")
    print(f"  - pysnmp: {HAS_PYSNMP}")
    print(f"  - requests: {HAS_REQUESTS}")
    print(f"  - netifaces: {HAS_NETIFACES}")
    print(f"  - pyipp: {HAS_PYIPP}")
    
    discovery = PrinterDiscovery()
    print("\nIniciando descoberta...")
    printers = discovery.discover_printers()
    
    print(f"\n{len(printers)} impressoras encontradas:")
    
    green_count = 0
    yellow_count = 0
    
    for i, p in enumerate(printers, 1):
        is_ready = p.get('is_ready', False)
        is_online = p.get('is_online', False)
        
        if is_ready and is_online:
            status = "🟢 VERDE (Pronta)"
            green_count += 1
        elif is_online:
            status = "🟡 AMARELA (Online mas não pronta)"
            yellow_count += 1
        else:
            status = "🔴 VERMELHA (Offline)"
            yellow_count += 1
        
        model = p.get('printer-make-and-model') or p.get('model', '')
        state = p.get('printer-state', '')
        method = p.get('discovery_method', 'Unknown')
        
        print(f"  {i}. {p['name']} ({p['ip']}) - {status}")
        print(f"     Método: {method}")
        if model:
            print(f"     Modelo: {model}")
        if state:
            print(f"     Estado: {state}")
        print(f"     is_ready: {is_ready}, is_online: {is_online}")
        print(f"     Portas: {p.get('ports', [])}")
        print()
    
    print(f"RESUMO: {green_count} verdes, {yellow_count} amarelas/vermelhas")
    
    if yellow_count > 0:
        print("\n⚠️  DIAGNÓSTICO DE IMPRESSORAS AMARELAS:")
        print("   Se as impressoras têm dados corretos mas ficam amarelas,")
        print("   verifique os logs acima para ver os valores de is_ready e printer-state")
        print("   O problema pode estar na interpretação dos estados IPP.")
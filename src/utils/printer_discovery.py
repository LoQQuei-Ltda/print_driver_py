#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitário para descoberta automática de impressoras na rede - Versão Multi-Protocolo Robusta
Suporta: mDNS/Bonjour, SNMP, WSD, NetBIOS, SSDP/UPnP, IPP, Raw Sockets
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

# Suprime warnings de bibliotecas externas
warnings.filterwarnings('ignore')

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterDiscovery")

# Configurações globais
BASE_TIMEOUT_REQUEST = 5
BASE_TIMEOUT_SCAN = 2
BASE_TIMEOUT_PING = 3
MAX_WORKERS = 50  # Aumentado para descoberta mais rápida
DISCOVERY_TIMEOUT = 30  # Timeout total para descoberta
COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515, 8080, 8443, 5353, 161, 3702]

# Tenta importar bibliotecas opcionais
HAS_PYIPP = False
HAS_ZEROCONF = False
HAS_PYSNMP = False
HAS_REQUESTS = False
HAS_NETIFACES = False

try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    logger.debug("pyipp não disponível - descoberta IPP limitada")

try:
    from zeroconf import ServiceBrowser, Zeroconf, ServiceListener
    HAS_ZEROCONF = True
except ImportError:
    logger.debug("zeroconf não disponível - descoberta mDNS desabilitada")

try:
    from pysnmp.hlapi import *
    HAS_PYSNMP = True
except ImportError:
    logger.debug("pysnmp não disponível - descoberta SNMP desabilitada")

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    logger.debug("requests não disponível - descoberta HTTP limitada")

try:
    import netifaces
    HAS_NETIFACES = True
except ImportError:
    logger.debug("netifaces não disponível - detecção de rede limitada")


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
                # Processa apenas se não foi processado antes
                service_id = f"{name}:{type}"
                if service_id not in self.found_services:
                    self.found_services.add(service_id)
                    self.discovery._process_mdns_service(info)
        except Exception as e:
            logger.debug(f"Erro processando serviço mDNS {name}: {str(e)}")
    
    def remove_service(self, zeroconf, type, name):
        """Serviço removido"""
        pass
    
    def update_service(self, zeroconf, type, name):
        """Serviço atualizado"""
        pass


class PrinterDiscovery:
    """Classe para descoberta automática de impressoras - Multi-Protocolo"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.discovered_printers = {}  # IP -> printer_info
        self.discovery_lock = threading.Lock()
        
        # Informações do sistema
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        self.is_admin = self._check_admin_privileges()
        
        # Detecção do Windows
        self.windows_version = self._detect_windows_version()
        
        # Cache
        self.mac_cache = {}
        self.last_arp_update = 0
        
        # Configurações adaptativas
        self.config = self._setup_system_configs()
        
        logger.info(f"PrinterDiscovery inicializado - Sistema: {self.system}, "
                   f"Admin: {self.is_admin}, Bibliotecas: "
                   f"zeroconf={HAS_ZEROCONF}, pysnmp={HAS_PYSNMP}, "
                   f"requests={HAS_REQUESTS}, netifaces={HAS_NETIFACES}")
    
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
                'is_server': "server" in product_name.lower(),
                'is_win10': int(current_build) >= 10240 and int(current_build) < 22000,
                'is_win11': int(current_build) >= 22000
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
        """Configura parâmetros do sistema"""
        return {
            'timeouts': {
                'request': BASE_TIMEOUT_REQUEST,
                'scan': BASE_TIMEOUT_SCAN,
                'ping': BASE_TIMEOUT_PING
            },
            'parallel_hosts': MAX_WORKERS
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
        Descobre impressoras usando múltiplos protocolos em paralelo
        
        Args:
            subnet: Subnet específica (opcional)
            
        Returns:
            list: Lista de impressoras encontradas
        """
        logger.info("=== Iniciando descoberta multi-protocolo de impressoras ===")
        start_time = time.time()
        
        # Limpa descobertas anteriores
        self.discovered_printers.clear()
        
        # Lista de métodos de descoberta
        discovery_methods = []
        
        # 1. mDNS/Bonjour (muito eficaz para impressoras modernas)
        if HAS_ZEROCONF:
            discovery_methods.append(("mDNS/Bonjour", self._discover_mdns))
        
        # 2. SNMP (eficaz para impressoras empresariais)
        if HAS_PYSNMP:
            discovery_methods.append(("SNMP", self._discover_snmp))
        
        # 3. WSD - Web Services for Devices (Windows)
        if self.is_windows:
            discovery_methods.append(("WSD", self._discover_wsd))
        
        # 4. NetBIOS/SMB
        discovery_methods.append(("NetBIOS", self._discover_netbios))
        
        # 5. SSDP/UPnP
        discovery_methods.append(("SSDP/UPnP", self._discover_ssdp))
        
        # 6. IPP Direct
        discovery_methods.append(("IPP Direct", self._discover_ipp_direct))
        
        # 7. Port Scan (fallback)
        discovery_methods.append(("Port Scan", self._discover_port_scan))
        
        # Executa todos os métodos em paralelo
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(discovery_methods)) as executor:
            futures = []
            
            for method_name, method_func in discovery_methods:
                logger.info(f"Iniciando descoberta via {method_name}...")
                future = executor.submit(self._run_discovery_method, method_name, method_func, subnet)
                futures.append((method_name, future))
            
            # Aguarda com timeout
            for method_name, future in futures:
                try:
                    result = future.result(timeout=DISCOVERY_TIMEOUT)
                    logger.info(f"{method_name}: {result} impressoras encontradas")
                except concurrent.futures.TimeoutError:
                    logger.warning(f"{method_name}: Timeout")
                except Exception as e:
                    logger.error(f"{method_name}: Erro - {str(e)}")
        
        # Processa e deduplica resultados
        unique_printers = self._process_discovered_printers()
        
        elapsed = time.time() - start_time
        logger.info(f"=== Descoberta concluída em {elapsed:.1f}s - "
                   f"{len(unique_printers)} impressoras únicas encontradas ===")
        
        self.printers = unique_printers
        return unique_printers
    
    def _run_discovery_method(self, method_name, method_func, subnet):
        """Executa um método de descoberta com tratamento de erros"""
        try:
            count = method_func(subnet)
            return count
        except Exception as e:
            logger.error(f"Erro em {method_name}: {str(e)}")
            logger.debug(traceback.format_exc())
            return 0
    
    def _add_discovered_printer(self, printer_info):
        """Adiciona impressora descoberta de forma thread-safe"""
        with self.discovery_lock:
            ip = printer_info.get('ip')
            if not ip:
                return
            
            # Se já existe, mescla informações
            if ip in self.discovered_printers:
                existing = self.discovered_printers[ip]
                # Mescla informações, priorizando novas se mais completas
                for key, value in printer_info.items():
                    if value and (key not in existing or not existing[key]):
                        existing[key] = value
                # Mescla portas
                if 'ports' in printer_info:
                    existing_ports = set(existing.get('ports', []))
                    new_ports = set(printer_info['ports'])
                    existing['ports'] = sorted(list(existing_ports | new_ports))
            else:
                self.discovered_printers[ip] = printer_info
    
    def _discover_mdns(self, subnet=None):
        """Descoberta via mDNS/Bonjour"""
        if not HAS_ZEROCONF:
            return 0
        
        count = 0
        try:
            zeroconf = Zeroconf()
            listener = MDNSListener(self)
            
            # Serviços de impressora conhecidos
            services = [
                "_ipp._tcp.local.",
                "_printer._tcp.local.",
                "_pdl-datastream._tcp.local.",
                "_print._tcp.local.",
                "_http._tcp.local.",  # Muitas impressoras anunciam HTTP
                "_https._tcp.local.",
                "_scanner._tcp.local.",  # Multifuncionais
                "_airprint._tcp.local.",  # Apple AirPrint
                "_ipps._tcp.local."
            ]
            
            browsers = []
            for service in services:
                browser = ServiceBrowser(zeroconf, service, listener)
                browsers.append(browser)
            
            # Aguarda descobertas
            time.sleep(5)
            
            # Conta impressoras encontradas via mDNS
            count = len([p for p in self.discovered_printers.values() 
                        if p.get('discovery_method') == 'mDNS'])
            
            zeroconf.close()
            
        except Exception as e:
            logger.error(f"Erro na descoberta mDNS: {str(e)}")
        
        return count
    
    def _process_mdns_service(self, info):
        """Processa serviço mDNS descoberto"""
        try:
            if not info.addresses or len(info.addresses) == 0:
                return
            
            # Converte endereço para string IP
            ip = socket.inet_ntoa(info.addresses[0])
            
            # Extrai informações
            printer_info = {
                'ip': ip,
                'name': info.name.replace('._ipp._tcp.local.', '').replace('._printer._tcp.local.', ''),
                'port': info.port,
                'discovery_method': 'mDNS',
                'mdns_properties': {}
            }
            
            # Processa propriedades mDNS
            if info.properties:
                for key, value in info.properties.items():
                    if isinstance(value, bytes):
                        value = value.decode('utf-8', errors='ignore')
                    printer_info['mdns_properties'][key.decode('utf-8', errors='ignore')] = value
                
                # Extrai informações úteis das propriedades
                props = printer_info['mdns_properties']
                if 'ty' in props:
                    printer_info['model'] = props['ty']
                if 'note' in props:
                    printer_info['location'] = props['note']
                if 'product' in props:
                    printer_info['product'] = props['product']
            
            # Determina portas baseado no serviço
            if info.port:
                printer_info['ports'] = [info.port]
                if info.port == 631:
                    printer_info['uri'] = f"ipp://{ip}:631/ipp/print"
                elif info.port == 80:
                    printer_info['uri'] = f"http://{ip}"
                elif info.port == 443:
                    printer_info['uri'] = f"https://{ip}"
            
            self._add_discovered_printer(printer_info)
            
        except Exception as e:
            logger.debug(f"Erro processando serviço mDNS: {str(e)}")
    
    def _discover_snmp(self, subnet=None):
        """Descoberta via SNMP"""
        if not HAS_PYSNMP:
            return 0
        
        count = 0
        networks = self._get_networks_to_scan(subnet)
        
        # OIDs SNMP para impressoras
        printer_oids = [
            '1.3.6.1.2.1.1.1.0',  # sysDescr
            '1.3.6.1.2.1.1.5.0',  # sysName
            '1.3.6.1.2.1.25.3.2.1.3.1',  # hrDeviceDescr
            '1.3.6.1.2.1.43.5.1.1.16.1'  # prtGeneralModelName
        ]
        
        for network in networks:
            # IPs comuns para testar SNMP
            test_ips = self._get_common_printer_ips(network)[:30]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(self._snmp_get, ip, printer_oids) 
                          for ip in test_ips]
                
                for future in concurrent.futures.as_completed(futures, timeout=10):
                    try:
                        result = future.result()
                        if result:
                            self._add_discovered_printer(result)
                            count += 1
                    except:
                        pass
        
        return count
    
    def _snmp_get(self, ip, oids):
        """Consulta SNMP em um IP"""
        if not HAS_PYSNMP:
            return None
        
        try:
            # Tenta community strings comuns
            for community in ['public', 'private']:
                for oid in oids:
                    iterator = getCmd(
                        SnmpEngine(),
                        CommunityData(community, mpModel=0),
                        UdpTransportTarget((ip, 161), timeout=2, retries=1),
                        ContextData(),
                        ObjectType(ObjectIdentity(oid))
                    )
                    
                    errorIndication, errorStatus, errorIndex, varBinds = next(iterator)
                    
                    if not errorIndication and not errorStatus:
                        for varBind in varBinds:
                            value = str(varBind[1])
                            if value and 'print' in value.lower():
                                return {
                                    'ip': ip,
                                    'name': f"Impressora SNMP {ip}",
                                    'model': value,
                                    'discovery_method': 'SNMP',
                                    'ports': [161, 9100, 631],
                                    'uri': f"socket://{ip}:9100"
                                }
        except:
            pass
        
        return None
    
    def _discover_wsd(self, subnet=None):
        """Descoberta via WSD (Web Services for Devices) - Windows"""
        if not self.is_windows:
            return 0
        
        count = 0
        try:
            # Envia probe WS-Discovery
            probe_message = self._create_wsd_probe()
            
            # Socket UDP para multicast
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(5)
            
            # Envia para endereço multicast WSD
            sock.sendto(probe_message.encode('utf-8'), ('239.255.255.250', 3702))
            
            # Escuta respostas
            start_time = time.time()
            while time.time() - start_time < 8:
                try:
                    data, addr = sock.recvfrom(65536)
                    if self._process_wsd_response(data, addr[0]):
                        count += 1
                except socket.timeout:
                    break
                except:
                    continue
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"Erro na descoberta WSD: {str(e)}")
        
        return count
    
    def _create_wsd_probe(self):
        """Cria mensagem probe WS-Discovery"""
        return """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope" 
               xmlns:wsa="http://schemas.xmlsoap.org/ws/2004/08/addressing" 
               xmlns:wsd="http://schemas.xmlsoap.org/ws/2005/04/discovery">
  <soap:Header>
    <wsa:To>urn:schemas-xmlsoap-org:ws:2005:04:discovery</wsa:To>
    <wsa:Action>http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</wsa:Action>
    <wsa:MessageID>urn:uuid:""" + str(time.time()) + """</wsa:MessageID>
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
            # Parse XML response
            root = ET.fromstring(data)
            
            # Verifica se é uma impressora
            device_info = data.decode('utf-8', errors='ignore').lower()
            if any(keyword in device_info for keyword in ['print', 'printer', 'mfp']):
                printer_info = {
                    'ip': ip,
                    'name': f"Impressora WSD {ip}",
                    'discovery_method': 'WSD',
                    'ports': [80, 5357],  # WSD usa estas portas
                    'uri': f"http://{ip}"
                }
                self._add_discovered_printer(printer_info)
                return True
        except:
            pass
        
        return False
    
    def _discover_netbios(self, subnet=None):
        """Descoberta via NetBIOS"""
        count = 0
        
        try:
            if self.is_windows:
                # Usa nbtstat no Windows
                result = subprocess.run(['nbtstat', '-r'], 
                                      capture_output=True, text=True, 
                                      timeout=10,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
                
                if result.returncode == 0:
                    # Processa cache NetBIOS
                    for line in result.stdout.split('\n'):
                        if 'printer' in line.lower() or '<20>' in line:
                            # Extrai IP se possível
                            ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                            if ip_match:
                                ip = ip_match.group(1)
                                if self._verify_printer(ip):
                                    count += 1
            else:
                # Em Linux/Mac, usa nmblookup se disponível
                networks = self._get_networks_to_scan(subnet)
                for network in networks:
                    try:
                        broadcast = str(network.broadcast_address)
                        result = subprocess.run(['nmblookup', '-B', broadcast, '*'],
                                              capture_output=True, text=True,
                                              timeout=10)
                        
                        if result.returncode == 0:
                            for line in result.stdout.split('\n'):
                                if '<20>' in line:  # Compartilhamento de arquivo/impressora
                                    ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                                    if ip_match:
                                        ip = ip_match.group(1)
                                        if self._verify_printer(ip):
                                            count += 1
                    except:
                        pass
        except:
            pass
        
        return count
    
    def _discover_ssdp(self, subnet=None):
        """Descoberta via SSDP/UPnP"""
        count = 0
        
        try:
            # Mensagem M-SEARCH SSDP
            ssdp_request = """M-SEARCH * HTTP/1.1
HOST: 239.255.255.250:1900
MAN: "ssdp:discover"
MX: 3
ST: ssdp:all

"""
            
            # Socket UDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(5)
            
            # Envia M-SEARCH
            sock.sendto(ssdp_request.encode('utf-8'), ('239.255.255.250', 1900))
            
            # Escuta respostas
            start_time = time.time()
            while time.time() - start_time < 8:
                try:
                    data, addr = sock.recvfrom(65536)
                    response = data.decode('utf-8', errors='ignore')
                    
                    # Verifica se é impressora
                    if any(keyword in response.lower() for keyword in 
                          ['printer', 'print', 'mfp', 'scanner']):
                        
                        # Extrai location
                        location_match = re.search(r'LOCATION:\s*(.+)', response, re.IGNORECASE)
                        if location_match:
                            location = location_match.group(1).strip()
                            # Extrai IP da URL
                            ip_match = re.search(r'http[s]?://([^:/]+)', location)
                            if ip_match:
                                ip = ip_match.group(1)
                                printer_info = {
                                    'ip': ip,
                                    'name': f"Impressora UPnP {ip}",
                                    'discovery_method': 'SSDP/UPnP',
                                    'location_url': location,
                                    'ports': [80, 1900],
                                    'uri': location
                                }
                                self._add_discovered_printer(printer_info)
                                count += 1
                
                except socket.timeout:
                    break
                except:
                    continue
            
            sock.close()
            
        except Exception as e:
            logger.debug(f"Erro na descoberta SSDP: {str(e)}")
        
        return count
    
    def _discover_ipp_direct(self, subnet=None):
        """Descoberta direta via IPP em IPs comuns"""
        count = 0
        networks = self._get_networks_to_scan(subnet)
        
        for network in networks:
            # IPs mais prováveis
            common_ips = self._get_common_printer_ips(network)[:50]
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(self._check_ipp_printer, ip) 
                          for ip in common_ips]
                
                for future in concurrent.futures.as_completed(futures, timeout=15):
                    try:
                        if future.result():
                            count += 1
                    except:
                        pass
        
        return count
    
    def _check_ipp_printer(self, ip):
        """Verifica se IP tem serviço IPP"""
        # Primeiro verifica se porta 631 está aberta
        if not self._is_port_open(ip, 631, 2):
            return False
        
        printer_info = {
            'ip': ip,
            'name': f"Impressora IPP {ip}",
            'discovery_method': 'IPP Direct',
            'ports': [631],
            'uri': f"ipp://{ip}/ipp/print"
        }
        
        # Tenta obter detalhes via IPP se disponível
        if HAS_PYIPP:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                details = loop.run_until_complete(
                    asyncio.wait_for(self._get_printer_attributes(ip), timeout=5)
                )
                loop.close()
                
                if details and 'name' in details:
                    printer_info.update(details)
            except:
                pass
        
        self._add_discovered_printer(printer_info)
        return True
    
    def _discover_port_scan(self, subnet=None):
        """Descoberta via escaneamento de portas (fallback)"""
        count = 0
        
        # Atualiza cache ARP
        self._update_arp_cache()
        
        # IPs do cache ARP primeiro
        arp_ips = list(self.mac_cache.keys())
        
        if arp_ips:
            logger.info(f"Verificando {len(arp_ips)} IPs do cache ARP...")
            with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                futures = [executor.submit(self._scan_single_ip, ip) for ip in arp_ips]
                
                for future in concurrent.futures.as_completed(futures, timeout=20):
                    try:
                        result = future.result()
                        if result:
                            self._add_discovered_printer(result)
                            count += 1
                    except:
                        pass
        
        # Escaneia redes adicionais se encontrou poucas
        if count < 3:
            networks = self._get_networks_to_scan(subnet)
            for network in networks[:2]:  # Limita para não demorar muito
                common_ips = self._get_common_printer_ips(network)[:30]
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                    futures = [executor.submit(self._scan_single_ip, ip) for ip in common_ips]
                    
                    for future in concurrent.futures.as_completed(futures, timeout=15):
                        try:
                            result = future.result()
                            if result:
                                self._add_discovered_printer(result)
                                count += 1
                        except:
                            pass
        
        return count
    
    def _scan_single_ip(self, ip):
        """Escaneia um único IP"""
        open_ports = []
        
        # Verifica portas comuns de impressora
        for port in COMMON_PRINTER_PORTS:
            if self._is_port_open(ip, port, 1):
                open_ports.append(port)
        
        if not open_ports:
            return None
        
        # Verifica se parece ser impressora
        if not self._looks_like_printer(ip, open_ports):
            return None
        
        # Obtém MAC
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
    
    def _verify_printer(self, ip):
        """Verifica se IP é de uma impressora e adiciona se for"""
        result = self._scan_single_ip(ip)
        if result:
            self._add_discovered_printer(result)
            return True
        return False
    
    def _process_discovered_printers(self):
        """Processa e enriquece impressoras descobertas"""
        unique_printers = []
        
        with self.discovery_lock:
            for ip, printer_info in self.discovered_printers.items():
                # Enriquece com MAC se não tiver
                if not printer_info.get('mac_address'):
                    printer_info['mac_address'] = self._get_mac_for_ip(ip)
                
                # Normaliza MAC
                mac = self.normalize_mac(printer_info.get('mac_address'))
                printer_info['mac_address'] = mac or 'desconhecido'
                
                # Garante que tem nome
                if not printer_info.get('name'):
                    printer_info['name'] = f"Impressora {ip}"
                
                # Garante que tem URI
                if not printer_info.get('uri'):
                    ports = printer_info.get('ports', [])
                    printer_info['uri'] = self._determine_uri(ip, ports)
                
                # Marca como online
                printer_info['is_online'] = True
                
                # Tenta obter mais detalhes se tiver IPP
                if 631 in printer_info.get('ports', []) and HAS_PYIPP:
                    self._enrich_with_ipp_details(printer_info)
                
                unique_printers.append(printer_info)
        
        # Ordena por IP para consistência
        unique_printers.sort(key=lambda p: socket.inet_aton(p['ip']))
        
        return unique_printers
    
    def _enrich_with_ipp_details(self, printer_info):
        """Enriquece com detalhes IPP se possível"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            details = loop.run_until_complete(
                asyncio.wait_for(
                    self._get_printer_attributes(printer_info['ip']), 
                    timeout=5
                )
            )
            loop.close()
            
            if details:
                # Atualiza com detalhes IPP
                if 'printer-make-and-model' in details:
                    printer_info['model'] = details['printer-make-and-model']
                if 'printer-location' in details:
                    printer_info['location'] = details['printer-location']
                if 'printer-state' in details:
                    printer_info['state'] = details['printer-state']
                    printer_info['is_ready'] = 'idle' in details['printer-state'].lower()
                if 'name' in details and details['name'] != printer_info['name']:
                    printer_info['name'] = details['name']
        except:
            pass
    
    def discover_printer_by_mac(self, target_mac):
        """Descobre impressora por MAC address"""
        normalized_mac = self.normalize_mac(target_mac)
        if not normalized_mac:
            return None
        
        logger.info(f"Procurando impressora com MAC: {normalized_mac}")
        
        # Primeiro faz uma descoberta geral rápida
        self.discover_printers()
        
        # Procura nos resultados
        for printer in self.printers:
            if self.normalize_mac(printer.get('mac_address')) == normalized_mac:
                return printer
        
        return None
    
    def get_printer_details(self, ip):
        """Obtém detalhes de uma impressora específica"""
        logger.info(f"Obtendo detalhes da impressora: {ip}")
        
        # Primeiro verifica se é uma impressora
        result = self._scan_single_ip(ip)
        if not result:
            return None
        
        # Tenta obter detalhes IPP se disponível
        if 631 in result.get('ports', []) and HAS_PYIPP:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                details = loop.run_until_complete(self._get_printer_attributes(ip))
                loop.close()
                
                if details:
                    result.update(details)
            except:
                pass
        
        return result
    
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
        """Detecta redes locais - versão melhorada"""
        networks = []
        
        if HAS_NETIFACES:
            # Usa netifaces para detecção precisa
            for interface in netifaces.interfaces():
                addrs = netifaces.ifaddresses(interface)
                if netifaces.AF_INET in addrs:
                    for addr in addrs[netifaces.AF_INET]:
                        ip = addr.get('addr')
                        netmask = addr.get('netmask')
                        if ip and netmask and not ip.startswith('127.'):
                            try:
                                # Calcula a rede
                                network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                                if network not in networks:
                                    networks.append(network)
                                    logger.info(f"Rede detectada via netifaces: {network}")
                            except:
                                pass
        
        # Métodos alternativos se netifaces não disponível
        if not networks:
            # Tenta via socket
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
        
        # Fallback: redes comuns
        if not networks:
            common_networks = [
                "192.168.1.0/24", "192.168.0.0/24", "10.0.0.0/24",
                "192.168.2.0/24", "172.16.0.0/24", "192.168.100.0/24"
            ]
            for net_str in common_networks:
                try:
                    networks.append(ipaddress.IPv4Network(net_str))
                except:
                    pass
        
        return networks[:3]  # Limita a 3 redes para não demorar muito
    
    def _get_common_printer_ips(self, network):
        """Gera IPs comuns para impressoras em uma rede"""
        common_ips = []
        
        try:
            # Sufixos típicos de impressoras
            common_suffixes = [
                1, 2, 3, 4, 5, 10, 11, 20, 21, 30, 50, 51, 100, 101, 102,
                110, 111, 150, 200, 201, 250, 251, 252, 253, 254
            ]
            
            network_addr = network.network_address
            for suffix in common_suffixes:
                try:
                    ip = str(network_addr + suffix)
                    if ipaddress.IPv4Address(ip) in network:
                        common_ips.append(ip)
                except:
                    continue
        except:
            pass
        
        return common_ips
    
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
    
    def _ping_host(self, ip, timeout=1):
        """Faz ping em um host"""
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
    
    def _looks_like_printer(self, ip, open_ports):
        """Verifica se parece ser uma impressora"""
        # Portas definitivas de impressora
        printer_ports = {631, 9100, 515}
        if any(port in printer_ports for port in open_ports):
            return True
        
        # Se tem várias portas abertas, provavelmente é
        if len(open_ports) >= 3:
            return True
        
        # Se tem HTTP, verifica conteúdo
        if 80 in open_ports or 443 in open_ports:
            if HAS_REQUESTS:
                try:
                    port = 80 if 80 in open_ports else 443
                    protocol = 'http' if port == 80 else 'https'
                    
                    resp = requests.get(
                        f"{protocol}://{ip}",
                        timeout=3,
                        verify=False,
                        headers={'User-Agent': 'PrinterDiscovery/1.0'}
                    )
                    
                    content = resp.text.lower()
                    printer_keywords = [
                        'printer', 'print', 'toner', 'cartridge', 'ink',
                        'hp', 'epson', 'canon', 'brother', 'samsung', 'xerox'
                    ]
                    
                    return any(keyword in content for keyword in printer_keywords)
                except:
                    pass
        
        return False
    
    def _determine_uri(self, ip, open_ports):
        """Determina URI da impressora"""
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
                # Parse ARP output
                for line in result.stdout.split('\n'):
                    # Padrão: IP MAC
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
            
        except:
            pass
    
    def _get_mac_for_ip(self, ip):
        """Obtém MAC para um IP"""
        # Verifica cache
        if ip in self.mac_cache:
            return self.mac_cache[ip]
        
        # Faz ping e atualiza ARP
        self._ping_host(ip, 1)
        time.sleep(0.2)
        
        # Consulta ARP específico
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
    
    async def _get_printer_attributes(self, ip, port=631):
        """Obtém atributos via IPP"""
        if not HAS_PYIPP:
            return None
        
        endpoints = ["/ipp/print", "/ipp/printer", "/ipp", ""]
        
        for tls in [False, True]:
            for endpoint in endpoints:
                try:
                    client = pyipp.IPP(host=ip, port=port, tls=tls)
                    client.url_path = endpoint
                    
                    printer_attrs = await asyncio.wait_for(
                        client.printer(), 
                        timeout=5
                    )
                    
                    if printer_attrs:
                        # Processa resposta
                        result = {'ip': ip}
                        
                        if hasattr(printer_attrs, 'info'):
                            info = printer_attrs.info
                            result['name'] = getattr(info, 'name', f"Impressora {ip}")
                            result['printer-make-and-model'] = getattr(info, 'model', '')
                            result['printer-location'] = getattr(info, 'location', '')
                        
                        if hasattr(printer_attrs, 'state'):
                            state = printer_attrs.state
                            if hasattr(state, 'printer_state'):
                                states = {
                                    'idle': 'Idle (Pronta)',
                                    'processing': 'Processing',
                                    'stopped': 'Stopped'
                                }
                                result['printer-state'] = states.get(
                                    state.printer_state, 
                                    state.printer_state
                                )
                        
                        return result
                        
                except:
                    continue
        
        return None
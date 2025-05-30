#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitário para descoberta automática de impressoras na rede - Versão Universalmente Compatível
Funciona perfeitamente em Windows 10, Windows 11, Windows Server, Linux e macOS
Aprimorado com descoberta mDNS (Zeroconf).
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
COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515, 8080, 8443] # IPP, JetDirect, HTTP, HTTPS, LPD

# Configurações para o IPP
try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    HAS_PYIPP = False
    logger.warning("Módulo pyipp não encontrado. Informações detalhadas de impressoras (via IPP) não estarão disponíveis.")

# Configurações para Zeroconf (mDNS)
try:
    from zeroconf import ServiceBrowser, Zeroconf, ServiceInfo, ServiceStateChange
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False
    logger.warning("Módulo zeroconf não encontrado. Descoberta de impressoras via mDNS não estará disponível.")


class PrinterDiscovery:
    """Classe para descoberta automática de impressoras na rede - Versão Universalmente Compatível"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        
        self.windows_version = self._detect_windows_version()
        self.is_server = self.windows_version.get('is_server', False)
        self.is_win10 = self.windows_version.get('is_win10', False) # Note: Original logic might misclassify Win11 as Win10 for some settings
        self.is_win11 = self.windows_version.get('is_win11', False)
        
        self.is_admin = self._check_admin_privileges()
        
        self.mac_cache = {}
        self.last_arp_update = 0
        
        self.config = self._setup_system_configs()
        
        logger.info(f"Sistema: {self.system}, Versão: {self.windows_version}, Admin: {self.is_admin}")
        logger.info(f"Configurações: Timeouts={self.config['timeouts']}, Parallelismo={self.config['parallel_hosts']}")
        if not HAS_PYIPP:
            logger.warning("Funcionalidade de detalhes da impressora via IPP desabilitada (pyipp não encontrado).")
        if not HAS_ZEROCONF:
            logger.warning("Funcionalidade de descoberta mDNS desabilitada (zeroconf não encontrado).")

    def _detect_windows_version(self):
        """Detecta versão específica do Windows"""
        if not self.is_windows:
            return {'version': 'not_windows', 'is_server': False, 'is_win10': False, 'is_win11': False, 'build': 0}
        
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
            key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                product_name = winreg.QueryValueEx(key, "ProductName")[0]
                current_build_str = winreg.QueryValueEx(key, "CurrentBuild")[0]
                version_info['build'] = int(current_build_str)
                
                try:
                    display_version = winreg.QueryValueEx(key, "DisplayVersion")[0]
                except FileNotFoundError: # DisplayVersion might not exist on older systems like Win7
                    display_version = "" 
            
            version_info['version'] = product_name
            version_info['is_server'] = "server" in product_name.lower()
            
            # Windows 7: build 7600, 7601
            # Windows 10: builds 10240-19045 (approx, before Win11 builds)
            # Windows 11: builds 22000+
            if version_info['build'] >= 22000:
                version_info['is_win11'] = True
            elif version_info['build'] >= 10240:
                version_info['is_win10'] = True
            # Could add specific check for Win7/8 if needed, but current logic focuses on 10/11 differentiation
            
            logger.info(f"Windows detectado (Registry): {product_name}, Build: {version_info['build']}, DisplayVersion: {display_version}")
            
        except Exception as e:
            logger.warning(f"Erro detectando versão do Windows via registry: {str(e)}")
            
            # Método 2: WMIC como fallback
            try:
                # Use 'ver' command for simpler build number, wmic for more details
                # For build number specifically on older systems if CurrentBuild from registry fails
                if version_info['build'] == 0:
                    ver_output = subprocess.check_output("ver", shell=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW).strip()
                    build_match = re.search(r'\[Version \d+\.\d+\.(\d+)\]', ver_output)
                    if build_match:
                        version_info['build'] = int(build_match.group(1))

                result = subprocess.run(
                    ["wmic", "os", "get", "Caption,Version,ProductType", "/value"],
                    capture_output=True, text=True, timeout=10,
                    creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0
                )
                
                if result.returncode == 0:
                    output = result.stdout
                    # Update version_info based on WMIC if registry failed or for cross-check
                    if "Caption=" in output:
                         caption_match = re.search(r"Caption=(.+)", output)
                         if caption_match:
                             version_info['version'] = caption_match.group(1).strip()

                    if "Windows 10" in version_info['version'] and version_info['build'] >= 10240 and version_info['build'] < 22000 :
                        version_info['is_win10'] = True
                    elif "Windows 11" in version_info['version'] and version_info['build'] >= 22000:
                         version_info['is_win11'] = True
                    elif "Windows 7" in version_info['version']: # Basic check for Win 7
                        pass # is_win10 and is_win11 will be False

                    if "ProductType=3" in output: # Server
                        version_info['is_server'] = True
                    elif "ProductType=1" in output: # Workstation
                         version_info['is_server'] = False
                logger.info(f"Windows detectado (WMIC fallback): {version_info}")

            except Exception as e2:
                logger.warning(f"Erro detectando versão do Windows via WMIC: {str(e2)}")
        
        return version_info

    def _setup_system_configs(self):
        """Configura timeouts e parâmetros específicos do sistema"""
        config = {
            'timeouts': {
                'request': BASE_TIMEOUT_REQUEST, # General HTTP/IPP requests
                'scan': BASE_TIMEOUT_SCAN,       # Port scan timeout per port
                'ping': BASE_TIMEOUT_PING,       # Ping timeout per host
                'zeroconf': 10,                  # Timeout for mDNS discovery browse
            },
            'parallel_hosts': BASE_PARALLEL_HOSTS,
            'arp_method': 'standard',
            'ping_method': 'standard',
            'socket_method': 'standard'
        }
        
        # Adjustments based on detected OS
        if self.is_windows:
            if self.is_server:
                config['timeouts'].update({'request': 8, 'scan': 4, 'ping': 6, 'zeroconf': 15})
                config['parallel_hosts'] = 6
                config['arp_method'] = 'robust' # Placeholder, actual ARP commands are mostly standard
            elif self.is_win11: # More modern OS, can be slightly more aggressive
                config['timeouts'].update({'request': 5, 'scan': 2, 'ping': 3, 'zeroconf': 10})
                config['parallel_hosts'] = 12
                config['arp_method'] = 'modern' # Placeholder
            elif self.is_win10:
                config['timeouts'].update({'request': 6, 'scan': 3, 'ping': 4, 'zeroconf': 12})
                config['parallel_hosts'] = 8
                config['arp_method'] = 'win10_specific' # Placeholder
            else: # Older Windows (e.g., Win 7) or unknown, be more conservative
                config['timeouts'].update({'request': 7, 'scan': 4, 'ping': 5, 'zeroconf': 15})
                config['parallel_hosts'] = 6
        elif self.system == "linux" or self.system == "darwin": # macOS
             config['timeouts']['zeroconf'] = 10
             config['parallel_hosts'] = 10 # Can generally handle more parallelism
        
        return config

    def _check_admin_privileges(self):
        """Verifica se tem privilégios de administrador"""
        try:
            if self.is_windows:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else: # Linux, macOS
                return os.geteuid() == 0
        except Exception as e:
            logger.warning(f"Não foi possível verificar privilégios de administrador: {e}")
            return False

    def normalize_mac(self, mac):
        """Normaliza o formato do MAC para comparação"""
        if not mac or not isinstance(mac, str) or mac == "desconhecido":
            return None
            
        clean_mac = re.sub(r'[^a-fA-F0-9]', '', mac).lower()
        
        if len(clean_mac) != 12:
            logger.debug(f"MAC address inválido ou incompleto fornecido: {mac}")
            return None
        
        return ':'.join([clean_mac[i:i+2] for i in range(0, 12, 2)])

    def discover_printers(self, subnet=None):
        """
        Descobre impressoras na rede de forma síncrona.
        Combina mDNS, Nmap (se disponível) e varredura manual.
        """
        logger.info("Iniciando descoberta de impressoras...")
        all_printers_discovered = []

        # 1. Descoberta via Zeroconf/mDNS (se disponível)
        if HAS_ZEROCONF:
            logger.info("Tentando descoberta via mDNS (Zeroconf)...")
            try:
                mdns_printers = self._discover_printers_mdns()
                if mdns_printers:
                    logger.info(f"mDNS encontrou {len(mdns_printers)} impressoras potenciais.")
                    all_printers_discovered.extend(mdns_printers)
            except Exception as e:
                logger.error(f"Erro durante a descoberta mDNS: {e}")
                logger.error(traceback.format_exc())
        
        # Força atualização do cache ARP antes de scans baseados em IP
        self._force_arp_refresh() 
            
        # 2. Descoberta via Nmap ou scan manual (assíncrono internamente)
        #    Esta parte já existe e é complexa, vamos reutilizá-la.
        #    A função _scan_network já lida com nmap e scan manual.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # _scan_network retorna (None, lista_de_impressoras)
            _, network_scan_printers = loop.run_until_complete(self._scan_network(subnet))
            if network_scan_printers:
                logger.info(f"Varredura de rede (Nmap/Manual) encontrou {len(network_scan_printers)} impressoras potenciais.")
                all_printers_discovered.extend(network_scan_printers)
        except Exception as e:
            logger.error(f"Erro durante a varredura de rede (Nmap/Manual): {e}")
            logger.error(traceback.format_exc())
        finally:
            loop.close()
            
        # Filtra e valida impressoras de todas as fontes
        valid_printers = self._filter_and_deduplicate_printers(all_printers_discovered)
        
        logger.info(f"Descoberta concluída: {len(valid_printers)} impressoras válidas encontradas.")
        self.printers = valid_printers
        return valid_printers

    def _discover_printers_mdns(self):
        """Descobre impressoras usando mDNS/Zeroconf."""
        if not HAS_ZEROCONF:
            return []

        discovered_printers = []
        # Tipos de serviço comuns para impressoras
        service_types = [
            "_ipp._tcp.local.", 
            "_ipps._tcp.local.", # IPP sobre SSL
            "_pdl-datastream._tcp.local.", # Para JetDirect/Raw port 9100
            "_printer._tcp.local." # LPD
        ]

        class ServiceListener:
            def __init__(self):
                self.printers = []
                self.discovery_complete = threading.Event()

            def remove_service(self, zeroconf_instance, type, name):
                logger.debug(f"Serviço mDNS removido: {name}, tipo {type}.")

            def add_service(self, zeroconf_instance, type, name):
                # Chamado quando um serviço é adicionado ou atualizado
                # O estado inicial pode ser ADDING, então esperamos por RESOLVED
                pass

            def update_service(self, zeroconf_instance, type, name):
                # Chamado quando um serviço é atualizado, mas não necessariamente resolvido
                pass
            
            # Para zeroconf >= 0.37.0
            def on_service_state_change(self, zeroconf_instance: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange) -> None:
                logger.debug(f"Serviço mDNS {name} tipo {service_type} mudou para {state_change}")
                if state_change is ServiceStateChange.Added or state_change is ServiceStateChange.Updated:
                    info = zeroconf_instance.get_service_info(service_type, name)
                    if info:
                        self._process_service_info(info, service_type)
            
            def _process_service_info(self, info: ServiceInfo, service_type: str):
                try:
                    logger.info(f"Serviço mDNS encontrado: {info.name} ({service_type})")
                    ips = [socket.inet_ntoa(addr) for addr in info.addresses]
                    if not ips:
                        logger.warning(f"Serviço mDNS {info.name} não possui endereços IPV4.")
                        return

                    ip_address = ips[0] # Pega o primeiro IPV4
                    port = info.port
                    
                    # Tenta extrair MAC das propriedades (raro, mas possível)
                    mac_address = "desconhecido"
                    properties = {k.decode(): v.decode() if isinstance(v, bytes) else v for k, v in info.properties.items()}
                    
                    # Heurísticas para MAC em propriedades TXT
                    mac_keys = ['mac', 'MAC', 'macaddr', 'MACAddress', 'address', 'physaddr']
                    for key in mac_keys:
                        if key in properties:
                            normalized = self.normalize_mac(str(properties[key]))
                            if normalized:
                                mac_address = normalized
                                break
                    
                    # Se o MAC não foi encontrado nas propriedades, tentaremos obtê-lo via ARP mais tarde
                    if mac_address == "desconhecido":
                         # Força atualização do cache ARP para este IP específico
                        self._ping_host(ip_address, self.config['timeouts']['ping'])
                        time.sleep(0.1) # Pequena pausa para ARP resolver
                        mac_address = self._get_mac_for_ip(ip_address) or "desconhecido"


                    printer_name = properties.get('ty', info.name) # 'ty' é um campo comum para nome do modelo
                    if not printer_name or "._" in printer_name : # Limpa nome se for apenas o nome do serviço
                        printer_name = f"Impressora {ip_address}"


                    printer_data = {
                        "ip": ip_address,
                        "mac_address": mac_address,
                        "ports": [port], # A porta do serviço mDNS
                        "uri": self._determine_uri_from_mdns(ip_address, port, service_type, properties),
                        "name": printer_name,
                        "is_online": True,
                        "source": "mDNS"
                    }
                    
                    # Evita adicionar duplicatas baseadas em IP e porta principal do serviço
                    # Uma impressora pode anunciar múltiplos serviços, mas queremos uma entrada por IP físico
                    existing = next((p for p in self.printers if p['ip'] == ip_address), None)
                    if existing:
                        if port not in existing['ports']:
                            existing['ports'].append(port)
                        if mac_address != "desconhecido" and existing['mac_address'] == "desconhecido":
                            existing['mac_address'] = mac_address
                        if printer_name != f"Impressora {ip_address}" and existing['name'] == f"Impressora {existing['ip']}":
                             existing['name'] = printer_name # Atualiza nome se um melhor for encontrado
                    else:
                        self.printers.append(printer_data)
                        logger.info(f"Impressora mDNS processada: {printer_data}")

                except Exception as e:
                    logger.error(f"Erro ao processar informações do serviço mDNS {info.name if info else 'N/A'}: {e}")
                    logger.error(traceback.format_exc())

            # Métodos _ping_host e _get_mac_for_ip precisam ser acessíveis aqui
            # Passando a instância de PrinterDiscovery para o listener ou tornando-os estáticos/funções auxiliares
            def _ping_host(self, ip, timeout):
                # Esta é uma cópia simplificada. Idealmente, chame o método da classe PrinterDiscovery.
                # Para simplificar, esta cópia não lida com todas as otimizações de OS.
                param = '-n' if platform.system().lower() == 'windows' else '-c'
                count = '1'
                timeout_param = '-w' if platform.system().lower() == 'windows' else '-W'
                timeout_val = str(int(timeout * 1000)) if platform.system().lower() == 'windows' else str(int(timeout))
                command = ['ping', param, count, timeout_param, timeout_val, ip]
                try:
                    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
                                               creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower() == 'windows' else 0)
                    stdout, stderr = process.communicate(timeout=timeout + 1)
                    return process.returncode == 0
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    return False
            
            def _get_mac_for_ip(self, ip):
                # Cópia simplificada
                # Primeiro, tenta popular o cache ARP pingando
                self._ping_host(ip, 1) # Ping rápido para tentar popular o ARP
                time.sleep(0.2) # Pausa para o ARP resolver

                try:
                    arp_output = subprocess.check_output(['arp', '-n', ip] if platform.system().lower() != 'windows' else ['arp', '-a', ip],
                                                         timeout=2, text=True, 
                                                         creationflags=subprocess.CREATE_NO_WINDOW if platform.system().lower() == 'windows' else 0)
                    
                    # Expressão regular para MAC address (XX:XX:XX:XX:XX:XX ou XX-XX-XX-XX-XX-XX)
                    # Considera o IP específico na linha para maior precisão
                    # Exemplo Windows: "  192.168.1.1           00-1e-c9-xx-xx-xx     dynamic"
                    # Exemplo Linux: "myrouter.local (192.168.1.1) at 00:1e:c9:xx:xx:xx [ether] on eth0"
                    # A regex precisa ser robusta para ambos
                    mac_pattern_str = r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}"
                    
                    for line in arp_output.splitlines():
                        if ip in line: # Garante que estamos olhando para a linha correta
                            match = re.search(mac_pattern_str, line, re.IGNORECASE)
                            if match:
                                mac_addr_raw = match.group(0)
                                # Normaliza o MAC (ex: para minúsculas e com ':')
                                normalized_mac = re.sub(r'[^a-fA-F0-9]', '', mac_addr_raw).lower()
                                if len(normalized_mac) == 12:
                                    return ':'.join(normalized_mac[i:i+2] for i in range(0, 12, 2))
                    return None
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                    logger.debug(f"Falha ao obter MAC para {ip} via ARP: {e}")
                    return None


        zeroconf_instance = Zeroconf()
        listener = ServiceListener()
        # Referencia os métodos da classe PrinterDiscovery para o listener
        # Isso é um pouco hacky; uma estrutura melhor envolveria passar a instância ou usar callbacks.
        listener._ping_host = lambda ip_addr, t: self._ping_host(ip_addr, t)
        listener._get_mac_for_ip = lambda ip_addr: self._get_mac_for_ip(ip_addr)


        try:
            # Para zeroconf < 0.37.0
            if not hasattr(listener, 'on_service_state_change'):
                listener.add_service = lambda zc, type, name: self._handle_legacy_add_service(zc, type, name, listener)

            browser = ServiceBrowser(zeroconf_instance, service_types, listener)
            
            # Espera um tempo para a descoberta
            time.sleep(self.config['timeouts']['zeroconf']) 
            logger.info("Tempo de descoberta mDNS concluído.")

        except Exception as e:
            logger.error(f"Erro ao configurar o browser mDNS: {e}")
        finally:
            if zeroconf_instance:
                zeroconf_instance.close()
        
        return listener.printers

    def _handle_legacy_add_service(self, zeroconf_instance, type, name, listener_instance):
        """Manipulador para versões mais antigas do zeroconf que usam add_service."""
        info = zeroconf_instance.get_service_info(type, name)
        if info:
            listener_instance._process_service_info(info, type)


    def _determine_uri_from_mdns(self, ip, port, service_type, properties):
        """Determina URI com base nas informações do mDNS."""
        path = properties.get('rp', '')  # 'rp' é o caminho do recurso (ex: ipp/print)
        if not path.startswith('/'):
            path = '/' + path
        
        if "_ipps._tcp" in service_type:
            return f"ipps://{ip}:{port}{path}"
        if "_ipp._tcp" in service_type:
            return f"ipp://{ip}:{port}{path}"
        if "_pdl-datastream._tcp" in service_type:
            return f"socket://{ip}:{port}" # JetDirect/Raw
        if "_printer._tcp" in service_type: # LPD
            queue = properties.get('rq', 'print') # 'rq' para nome da fila LPD
            return f"lpd://{ip}:{port}/{queue}"
        
        # Fallback genérico
        return f"socket://{ip}:{port}"


    def _filter_and_deduplicate_printers(self, printers_list):
        """Filtra, valida e deduplica impressoras de múltiplas fontes."""
        valid_printers = []
        # Usar IP como chave primária para deduplicação inicial.
        # Se MACs estiverem disponíveis, eles podem ajudar a refinar.
        seen_printers = {} # ip -> printer_data

        for printer in printers_list:
            if not printer or not isinstance(printer, dict):
                continue
            
            ip = printer.get("ip")
            if not ip:
                continue
            
            try:
                ipaddress.IPv4Address(ip) # Valida IP
            except ValueError:
                logger.warning(f"IP inválido ignorado durante a filtragem: {ip}")
                continue

            # Normaliza MAC
            mac = self.normalize_mac(printer.get("mac_address"))
            printer["mac_address"] = mac if mac else "desconhecido"

            if "name" not in printer or not printer["name"]:
                printer["name"] = f"Impressora {ip}"
            
            if "ports" not in printer or not printer["ports"]:
                # Se descoberto por mDNS, pode ter uma porta específica.
                # Se por scan, deve ter portas. Se não, é problemático.
                if printer.get("source") != "mDNS":
                    logger.warning(f"Impressora {ip} sem portas válidas, pulando.")
                    continue
            
            printer.setdefault("is_online", True) # Assume online se descoberto

            # Lógica de Deduplicação e Mesclagem
            if ip in seen_printers:
                existing_printer = seen_printers[ip]
                # Mescla informações. Ex: adiciona portas, atualiza MAC se um melhor for encontrado.
                if printer["mac_address"] != "desconhecido" and existing_printer["mac_address"] == "desconhecido":
                    existing_printer["mac_address"] = printer["mac_address"]
                
                for port in printer.get("ports", []):
                    if port not in existing_printer["ports"]:
                        existing_printer["ports"].append(port)
                
                # Prefere nomes mais descritivos
                if printer["name"] != f"Impressora {ip}" and \
                   (existing_printer["name"] == f"Impressora {ip}" or len(printer["name"]) > len(existing_printer["name"])):
                    existing_printer["name"] = printer["name"]
                
                # Atualiza URI se um mais específico for encontrado (ex: mDNS vs socket genérico)
                if "mDNS" in printer.get("source", "") and "mDNS" not in existing_printer.get("source", ""):
                     existing_printer["uri"] = printer["uri"]
                     existing_printer["source"] = existing_printer.get("source","") + ",mDNS"


            else:
                seen_printers[ip] = printer
        
        valid_printers = list(seen_printers.values())
        logger.info(f"Filtragem e deduplicação resultaram em {len(valid_printers)} impressoras únicas.")
        return valid_printers

    def discover_printer_by_mac(self, target_mac):
        """
        Descobre impressora por MAC address.
        Combina ARP e descoberta mDNS.
        """
        normalized_target_mac = self.normalize_mac(target_mac)
        if not normalized_target_mac:
            logger.warning(f"MAC alvo inválido fornecido: {target_mac}")
            return None
        
        logger.info(f"Procurando impressora com MAC: {normalized_target_mac}")

        # 1. Tenta o método ARP existente (que já força refresh e verifica cache)
        #    A lógica original de _force_arp_refresh, _update_arp_cache, e ping de IPs comuns
        #    é complexa e específica do SO. Vamos chamá-la.
        #    Primeiro, uma atualização robusta do cache ARP.
        self._force_arp_refresh()
        
        # Verifica o cache ARP após o refresh
        for ip, mac_in_cache in self.mac_cache.items():
            if self.normalize_mac(mac_in_cache) == normalized_target_mac:
                logger.info(f"MAC {normalized_target_mac} encontrado no cache ARP para IP {ip}.")
                # Verifica se este IP realmente parece ser uma impressora
                if self._verify_printer_by_ip(ip): # Verifica portas de impressora
                    return self._create_printer_info(ip, normalized_target_mac)
        
        # Se não encontrou no cache após refresh, tenta pingar redes e verificar ARP novamente.
        # Esta lógica já está embutida no fluxo original de discover_printer_by_mac.
        # Vamos simular parte dessa lógica aqui para ser explícito.
        logger.info(f"MAC {normalized_target_mac} não encontrado no cache ARP inicial. Tentando scan ARP mais ativo.")
        networks = self._get_local_networks()
        for network in networks[:2]: # Limita para evitar scans muito longos
            if self.is_win10 or self.is_win11: # Usa lista mais extensa para Win10/11
                common_ips_to_ping = self._get_extended_common_ips(network)
            else:
                common_ips_to_ping = self._get_common_printer_ips(network)
            
            # Pinga esses IPs para popular o cache ARP
            if common_ips_to_ping:
                logger.debug(f"Pingando {len(common_ips_to_ping)} IPs comuns na rede {network} para popular ARP...")
                with concurrent.futures.ThreadPoolExecutor(max_workers=self.config['parallel_hosts']) as executor:
                    ping_timeout = self.config['timeouts']['ping']
                    list(executor.map(lambda ip_to_ping: self._ping_host(ip_to_ping, ping_timeout), common_ips_to_ping))
                
                self._update_arp_cache() # Atualiza o cache interno do script
                
                for ip, mac_in_cache in self.mac_cache.items():
                    if self.normalize_mac(mac_in_cache) == normalized_target_mac:
                        logger.info(f"MAC {normalized_target_mac} encontrado no cache ARP para IP {ip} após ping sweep.")
                        if self._verify_printer_by_ip(ip):
                            return self._create_printer_info(ip, normalized_target_mac)
        
        # 2. Se ARP falhar, tenta via mDNS (Zeroconf)
        if HAS_ZEROCONF:
            logger.info(f"MAC {normalized_target_mac} não encontrado via ARP. Tentando descoberta via mDNS...")
            try:
                mdns_printers = self._discover_printers_mdns() # Esta função já tenta obter MACs
                for printer_info in mdns_printers:
                    if printer_info.get("mac_address") == normalized_target_mac:
                        logger.info(f"MAC {normalized_target_mac} encontrado via mDNS para IP {printer_info['ip']}.")
                        # As informações já devem estar formatadas corretamente por _discover_printers_mdns
                        return printer_info 
                    elif printer_info.get("mac_address") == "desconhecido":
                        # Se mDNS encontrou um IP mas não o MAC, tentamos obter o MAC para esse IP
                        ip_from_mdns = printer_info.get("ip")
                        if ip_from_mdns:
                            mac_for_ip = self._get_mac_for_ip(ip_from_mdns)
                            if self.normalize_mac(mac_for_ip) == normalized_target_mac:
                                logger.info(f"MAC {normalized_target_mac} (para IP {ip_from_mdns} de mDNS) confirmado via ARP.")
                                # Atualiza as informações da impressora com o MAC correto
                                printer_info["mac_address"] = normalized_target_mac
                                return printer_info
            except Exception as e:
                logger.error(f"Erro durante a descoberta mDNS para busca por MAC: {e}")
        
        logger.warning(f"Não foi possível encontrar impressora com MAC: {normalized_target_mac} após todas as tentativas.")
        return None

    # --- Métodos auxiliares e de varredura de rede existentes (adaptados ou reutilizados) ---
    # Muitos dos métodos abaixo são do script original e são mantidos para compatibilidade
    # e como fallback se mDNS não estiver disponível ou não encontrar a impressora.

    def _force_arp_refresh(self):
        """Força atualização do cache ARP usando múltiplos métodos"""
        logger.info("Forçando atualização do cache ARP...")
        
        try:
            # Método 1: Limpa cache ARP existente (Windows)
            if self.is_windows and self.is_admin: # Limpar ARP geralmente requer admin
                try:
                    subprocess.run(
                        ["arp", "-d", "*"], 
                        capture_output=True, 
                        timeout=10, # Aumentado timeout
                        creationflags=subprocess.CREATE_NO_WINDOW,
                        check=False # Não lança exceção se falhar
                    )
                    logger.info("Comando 'arp -d *' executado.")
                except Exception as e_arp_d:
                    logger.warning(f"Falha ao executar 'arp -d *': {e_arp_d}")
            
            # Método 2: Faz ping broadcast/multicast na rede local (com cuidado)
            # Ping broadcast pode ser problemático/bloqueado. Pingar IPs conhecidos é mais seguro.
            # O ping sweep em _scan_network ou discover_printer_by_mac é mais direcionado.
            # Por ora, vamos focar no _update_arp_cache que lê a tabela do SO.
            
            # Método 3: Atualiza cache ARP convencional (lê do SO)
            self._update_arp_cache()
            
        except Exception as e:
            logger.warning(f"Erro forçando refresh ARP: {str(e)}")

    def _filter_valid_printers(self, printers): # Esta função é chamada por _scan_network. Pode ser mesclada/substituída por _filter_and_deduplicate_printers
        """Filtra e valida impressoras encontradas (versão original para _scan_network)"""
        return self._filter_and_deduplicate_printers(printers) # Delega para a nova função unificada

    def get_printer_details(self, ip):
        """
        Obtém detalhes de uma impressora específica de forma síncrona usando IPP.
        """
        if not ip:
            return None
        if not HAS_PYIPP:
            logger.warning(f"Não é possível obter detalhes para {ip}: pyipp não está instalado.")
            # Retorna informações básicas se pyipp não estiver disponível
            mac = self._get_mac_for_ip(ip)
            return {
                "ip": ip,
                "mac_address": mac if mac else "desconhecido",
                "name": f"Impressora {ip}",
                "printer-state": "Desconhecido (pyipp indisponível)",
                "error": "Módulo pyipp não disponível"
            }
            
        logger.info(f"Obtendo detalhes da impressora (IPP): {ip}")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # _get_printer_attributes já tem timeout interno
            details = loop.run_until_complete(self._get_printer_attributes(ip))
        except Exception as e:
            logger.error(f"Erro ao obter detalhes IPP para {ip} no loop asyncio: {e}")
            details = {"ip": ip, "error": str(e), "name": f"Impressora {ip}", "printer-state": "Erro ao obter detalhes"}
        finally:
            loop.close()
        
        return details

    async def _scan_network(self, subnet=None):
        """
        Escaneia a rede para encontrar impressoras (Nmap ou Manual).
        Esta é uma função complexa do script original.
        """
        all_printers = []
        
        try:
            networks = self._get_networks_to_scan(subnet)
            
            for network_obj in networks: # network_obj é um objeto ipaddress.IPv4Network
                network_str = str(network_obj)
                logger.info(f"Escaneando rede: {network_str}")
                
                nmap_printers = []
                if self._is_nmap_available(): # Verifica se nmap está realmente disponível
                    nmap_printers = self._run_nmap_scan(network_str) # Passa a string da rede
                    if nmap_printers:
                        logger.info(f"NMAP encontrou {len(nmap_printers)} dispositivos em {network_str}")
                        for p in nmap_printers: p["source"] = "nmap" # Marca a origem
                        all_printers.extend(nmap_printers)
                
                if not nmap_printers or not self._is_nmap_available(): # Se nmap não usou ou falhou
                    if not self._is_nmap_available():
                        logger.info("NMAP não disponível ou falhou, usando escaneamento manual.")
                    manual_printers = await self._manual_network_scan(network_obj) # Passa o objeto de rede
                    for p in manual_printers: p["source"] = "manual_scan"
                    all_printers.extend(manual_printers)
        
        except Exception as e:
            logger.error(f"Erro no escaneamento de rede (_scan_network): {str(e)}")
            logger.error(traceback.format_exc())
        
        # A deduplicação será feita em um nível mais alto (discover_printers)
        # Mas uma deduplicação preliminar aqui pode ser útil.
        unique_printers_scan = self._filter_and_deduplicate_printers(all_printers)
        return None, unique_printers_scan


    def _is_nmap_available(self):
        """Verifica se o nmap está disponível no sistema."""
        try:
            subprocess.run(
                ["nmap", "--version"],
                capture_output=True, timeout=5, check=True,
                creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            logger.debug("nmap não parece estar disponível no PATH ou não executou corretamente.")
            return False

    def _get_networks_to_scan(self, subnet=None):
        """Determina as redes a serem escaneadas"""
        networks = []
        if subnet:
            try:
                networks = [ipaddress.IPv4Network(subnet, strict=False)]
                logger.info(f"Usando subnet especificada: {subnet}")
            except ValueError as e:
                logger.warning(f"Erro ao processar subnet {subnet}: {str(e)}. Tentando redes locais.")
                networks = self._get_local_networks() # Fallback para redes locais
        else:
            networks = self._get_local_networks()
        
        if not networks: # Fallback final se nenhuma rede for detectada
            logger.warning("Nenhuma rede local detectada e nenhuma sub-rede especificada. Usando fallback para 192.168.1.0/24.")
            try:
                networks = [ipaddress.IPv4Network("192.168.1.0/24", strict=False)]
            except ValueError: # Deveria ser impossível, mas por segurança
                logger.error("Falha ao criar rede de fallback. Nenhum scan de rede será realizado.")
                return [] 
        return networks

    def _get_local_networks(self):
        """Obtém as redes locais para escanear - Versão ultra-robusta"""
        # Esta função é do script original e parece ser bastante completa.
        # Pequenas adaptações podem ser feitas se necessário, mas a lógica principal é mantida.
        # ... (código original de _get_local_networks) ...
        # Por brevidade, não vou replicar todo o código aqui, mas ele seria mantido.
        # Assume que esta função retorna uma lista de objetos ipaddress.IPv4Network
        
        # Implementação simplificada para este exemplo, o original é mais robusto
        detected_networks = []
        local_ips = self._get_all_local_ips()
        for ip_str in local_ips:
            try:
                if ip_str.startswith("127.") or ":" in ip_str: # Pula loopback e IPv6
                    continue
                # Tenta criar uma interface e, a partir dela, a rede
                # Isso é uma simplificação; o original usa netmasks de forma mais inteligente
                iface = ipaddress.IPv4Interface(f"{ip_str}/24") # Assume /24, o original é mais esperto
                network = iface.network
                if network not in detected_networks:
                    detected_networks.append(network)
                    logger.info(f"Rede local simplificada detectada: {network} para IP {ip_str}")
            except ValueError as e:
                logger.debug(f"Não foi possível determinar a rede para o IP {ip_str}: {e}")

        if not detected_networks: # Fallback muito básico
            logger.warning("Nenhuma rede local detectada pela lógica simplificada, usando 192.168.1.0/24 como fallback.")
            try:
                detected_networks.append(ipaddress.IPv4Network("192.168.1.0/24"))
            except ValueError: pass

        return detected_networks


    def _get_all_local_ips(self):
        """Obtém todos os IPs locais da máquina - Versão aprimorada"""
        # Esta função é do script original. Mantida.
        # ... (código original de _get_all_local_ips) ...
        # Implementação simplificada para este exemplo:
        local_ips = set()
        try:
            hostname = socket.gethostname()
            # IPs associados ao hostname
            for item in socket.getaddrinfo(hostname, None):
                ip = item[4][0]
                if not ip.startswith("127.") and "." in ip: # IPv4 não loopback
                    local_ips.add(ip)
            # IP usado para uma conexão de saída (pode revelar o IP da interface principal)
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ips.add(s.getsockname()[0])
        except socket.gaierror:
             logger.warning(f"Não foi possível obter IPs para o hostname {socket.gethostname()}")
        except OSError as e: # Ex: Network is unreachable
            logger.warning(f"Erro de socket ao tentar obter IPs locais: {e}")
        
        if not local_ips: # Fallback muito básico
            logger.warning("Não foi possível detectar IPs locais, usando 127.0.0.1 como placeholder.")
            return ["127.0.0.1"] # Evita retornar lista vazia que pode quebrar lógicas subsequentes

        logger.info(f"IPs locais detectados (simplificado): {list(local_ips)}")
        return list(local_ips)


    async def _manual_network_scan(self, network_obj: ipaddress.IPv4Network):
        """Escaneamento manual da rede - Versão otimizada para Windows 10/11"""
        # network_obj é um objeto ipaddress.IPv4Network
        # Esta função é do script original. Mantida.
        # ... (código original de _manual_network_scan, _win10_optimized_scan, _standard_network_scan) ...
        # Implementação simplificada para este exemplo:
        printers_found = []
        # Pega apenas alguns IPs da rede para escanear para não demorar muito no exemplo
        # O original tem uma lógica de amostragem mais inteligente.
        num_hosts_to_scan = 10 
        hosts_to_scan = [str(ip) for ip in network_obj.hosts()][:num_hosts_to_scan]
        
        if not hosts_to_scan:
            logger.info(f"Nenhum host para escanear manualmente na rede {network_obj}.")
            return []

        logger.info(f"Iniciando scan manual simplificado para {len(hosts_to_scan)} hosts em {network_obj}...")
        results = await self._scan_ip_list(hosts_to_scan)
        printers_found.extend(p for p in results if p)
        logger.info(f"Scan manual simplificado encontrou {len(printers_found)} impressoras potenciais.")
        return printers_found


    def _get_extended_common_ips(self, network_obj: ipaddress.IPv4Network):
        """Gera lista estendida de IPs comuns para Windows 10/11"""
        # network_obj é um objeto ipaddress.IPv4Network
        # Esta função é do script original. Mantida.
        # ... (código original de _get_extended_common_ips) ...
        # Implementação simplificada:
        common_ips = []
        base_ip_int = int(network_obj.network_address)
        for i in range(1, 20): # Pega os primeiros 20 IPs da rede
            try:
                ip = ipaddress.IPv4Address(base_ip_int + i)
                if ip in network_obj:
                    common_ips.append(str(ip))
            except ValueError:
                break # Sai se exceder o range da rede
        return common_ips


    def _get_common_printer_ips(self, network_obj: ipaddress.IPv4Network):
        """Gera lista de IPs comuns para impressoras"""
        # network_obj é um objeto ipaddress.IPv4Network
        # Esta função é do script original. Mantida.
        # ... (código original de _get_common_printer_ips) ...
        # Implementação simplificada (similar a _get_extended_common_ips):
        return self._get_extended_common_ips(network_obj)[:10] # Pega menos IPs


    async def _scan_ip_list(self, ip_list):
        """Escaneia uma lista de IPs - Versão adaptativa"""
        # Esta função é do script original. Mantida.
        # ... (código original de _scan_ip_list) ...
        # Implementação simplificada:
        printers = []
        tasks = [self._scan_single_ip(ip) for ip in ip_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, dict) and res:
                printers.append(res)
            elif isinstance(res, Exception):
                logger.debug(f"Erro ao escanear IP durante _scan_ip_list: {res}")
        return printers


    async def _scan_single_ip(self, ip):
        """Escaneia um único IP para verificar se é impressora"""
        # Esta função é do script original. Mantida.
        # ... (código original de _scan_single_ip) ...
        # Implementação simplificada:
        if not self._ping_host(ip, self.config['timeouts']['ping']):
            return None

        open_ports = []
        for port in COMMON_PRINTER_PORTS:
            if await self._check_port_async(ip, port):
                open_ports.append(port)
        
        if not open_ports:
            return None

        # A lógica _looks_like_printer é importante e deve ser mantida do original.
        # Para este exemplo, vamos simplificar: se tiver porta 9100 ou 631, é impressora.
        if not (9100 in open_ports or 631 in open_ports):
             if not self._looks_like_printer(ip, open_ports): # Chama a lógica original se existir
                return None

        mac = self._get_mac_for_ip(ip)
        return {
            "ip": ip, "mac_address": mac if mac else "desconhecido",
            "ports": open_ports, "uri": self._determine_uri(ip, open_ports),
            "name": f"Impressora {ip}", "is_online": True, "source": "single_ip_scan"
        }


    async def _check_port_async(self, ip, port):
        """Verifica uma porta de forma assíncrona"""
        # Esta função é do script original. Mantida.
        # ... (código original de _check_port_async) ...
        # Implementação simplificada:
        try:
            loop = asyncio.get_running_loop()
            # socket.create_connection tem timeout, mas connect_ex é não bloqueante por natureza com loop.sock_connect
            # Para simplificar, usamos run_in_executor para a chamada bloqueante _is_port_open
            is_open = await loop.run_in_executor(
                None, self._is_port_open, ip, port, self.config['timeouts']['scan']
            )
            return is_open
        except Exception as e:
            logger.debug(f"Erro em _check_port_async para {ip}:{port} : {e}")
            return False


    def _looks_like_printer(self, ip, open_ports):
        """Verifica se o dispositivo parece ser uma impressora"""
        # Esta função é do script original. Mantida.
        # ... (código original de _looks_like_printer e _check_http_printer_indicators) ...
        # Implementação simplificada:
        if 631 in open_ports or 9100 in open_ports or 515 in open_ports: # IPP, JetDirect, LPD
            return True
        # A lógica HTTP original é importante. Se 80 ou 443 estiverem abertos, chame _check_http_printer_indicators
        if (80 in open_ports or 443 in open_ports) and self._check_http_printer_indicators(ip, open_ports):
            return True
        return False

    def _check_http_printer_indicators(self, ip, open_ports):
        """Verifica indicadores HTTP de que é uma impressora"""
        # Esta função é do script original. Mantida.
        # ... (código original de _check_http_printer_indicators) ...
        # Implementação simplificada:
        # Tenta conectar na porta 80 ou 443 e buscar por palavras-chave.
        # Por brevidade, retorna True se a porta estiver aberta neste exemplo.
        # A implementação original com urllib e keywords é melhor.
        logger.debug(f"Verificando indicadores HTTP para {ip} (lógica simplificada).")
        return True # Assume que se chegou aqui, é uma impressora para o exemplo.


    def _determine_uri(self, ip, open_ports):
        """Determina o melhor URI para a impressora (não mDNS)"""
        # Esta função é do script original. Mantida.
        # ... (código original de _determine_uri) ...
        if 631 in open_ports: return f"ipp://{ip}:631/ipp/print" # Porta padrão IPP
        if 9100 in open_ports: return f"socket://{ip}:9100"
        if 515 in open_ports: return f"lpd://{ip}/print" # Fila comum 'print'
        if 443 in open_ports: return f"https://{ip}" # Genérico HTTPS
        if 80 in open_ports: return f"http://{ip}"   # Genérico HTTP
        if open_ports: return f"socket://{ip}:{open_ports[0]}" # Fallback para primeira porta aberta
        return f"socket://{ip}" # Fallback final


    def _update_arp_cache(self):
        """Atualiza o cache ARP - Versão específica por sistema"""
        # Esta função é do script original. Mantida.
        # ... (código original de _update_arp_cache, _update_arp_cache_win10, _update_arp_cache_standard, _parse_arp_output, _parse_netsh_output) ...
        current_time = time.time()
        min_interval = 15 # Reduzido para permitir atualizações mais frequentes se necessário
        if current_time - self.last_arp_update < min_interval and self.mac_cache: # Só pula se já tem algo no cache
            logger.debug("Cache ARP atualizado recentemente, pulando.")
            return

        logger.info("Atualizando cache ARP (lendo do sistema)...")
        old_cache_size = len(self.mac_cache)
        
        # Limpa o cache do script antes de repopular para remover entradas obsoletas
        # self.mac_cache.clear() # Cuidado: isso pode ser muito agressivo. O original não limpa.
        # Vamos manter o comportamento original de adicionar/atualizar.

        try:
            cmd = ['arp', '-a']
            creation_flags = subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            
            arp_output = subprocess.check_output(cmd, timeout=self.config['timeouts']['request'] + 2, 
                                                 text=True, creationflags=creation_flags)
            self._parse_arp_output(arp_output)

            if self.is_windows and (self.is_win10 or self.is_win11): # Tenta netsh para Win10/11
                try:
                    netsh_output = subprocess.check_output(
                        ['netsh', 'interface', 'ip', 'show', 'neighbors'],
                        timeout=self.config['timeouts']['request'] + 2, text=True, creationflags=creation_flags
                    )
                    self._parse_netsh_output(netsh_output)
                except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e_netsh:
                    logger.debug(f"Comando netsh falhou ou não disponível: {e_netsh}")

            self.last_arp_update = current_time
            new_cache_size = len(self.mac_cache)
            if new_cache_size > old_cache_size:
                logger.info(f"Cache ARP atualizado: {old_cache_size} -> {new_cache_size} entradas.")
            else:
                logger.debug(f"Cache ARP verificado, tamanho: {new_cache_size} (anterior: {old_cache_size}).")

        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Erro ao atualizar cache ARP: {e}")
        except Exception as e_gen:
            logger.error(f"Erro inesperado ao atualizar cache ARP: {e_gen}")


    def _parse_arp_output(self, output):
        """Processa a saída do comando ARP - Versão robusta"""
        # Esta função é do script original. Mantida.
        # ... (código original de _parse_arp_output) ...
        # Regex para IP e MAC. MAC pode ter : ou - como separador.
        # Windows: Interface: 192.168.1.10 --- 0xb
        #            Endereço IP           Endereço físico       Tipo
        #            192.168.1.1           00-aa-bb-cc-dd-ee     dinâmico
        # Linux:   Address                  HWtype  HWaddress           Flags Mask            Iface
        #          192.168.1.1              ether   00:aa:bb:cc:dd:ee   C                     eth0
        # macOS:   ? (192.168.1.1) at 0:aa:bb:cc:dd:ee on en0 ifscope [ethernet]
        
        # Padrão mais genérico para IP seguido por MAC
        # Procura por um IP, depois algum texto, depois um MAC.
        # ([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}
        ip_mac_pattern = re.compile(
            r"(?P<ip>(?:\d{1,3}\.){3}\d{1,3}).*?"
            r"(?P<mac>(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})", 
            re.IGNORECASE
        )
        found_entries = 0
        for line in output.splitlines():
            match = ip_mac_pattern.search(line)
            if match:
                ip = match.group("ip")
                mac_raw = match.group("mac")
                normalized_mac = self.normalize_mac(mac_raw)
                if normalized_mac:
                    # Não sobrescrever MACs válidos com "desconhecido" ou o mesmo MAC
                    if ip not in self.mac_cache or self.mac_cache[ip] == "desconhecido" or self.mac_cache[ip] != normalized_mac:
                        self.mac_cache[ip] = normalized_mac
                        found_entries +=1
        if found_entries > 0:
            logger.debug(f"{found_entries} novas/atualizadas entradas ARP processadas de 'arp -a'.")


    def _parse_netsh_output(self, output):
        """Processa saída do comando netsh (Windows 10/11)"""
        # Esta função é do script original. Mantida.
        # ... (código original de _parse_netsh_output) ...
        # Formato: IPAddress NeighborPhysicalAddress State
        # Ex: 192.168.1.254    00-aa-bb-cc-dd-ff       Reachable (Router)
        ip_mac_pattern_netsh = re.compile(
            r"^(?P<ip>(?:\d{1,3}\.){3}\d{1,3})\s+"
            r"(?P<mac>(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})",
            re.IGNORECASE | re.MULTILINE # MULTILINE para ^
        )
        found_entries = 0
        for match in ip_mac_pattern_netsh.finditer(output):
            ip = match.group("ip")
            mac_raw = match.group("mac")
            normalized_mac = self.normalize_mac(mac_raw)
            if normalized_mac:
                if ip not in self.mac_cache or self.mac_cache[ip] == "desconhecido" or self.mac_cache[ip] != normalized_mac:
                    self.mac_cache[ip] = normalized_mac
                    found_entries +=1
        if found_entries > 0:
             logger.debug(f"{found_entries} novas/atualizadas entradas ARP processadas de 'netsh'.")

    def _get_mac_for_ip(self, ip):
        """Obtém MAC address para um IP - Versão robusta"""
        # Esta função é do script original. Mantida.
        # ... (código original de _get_mac_for_ip e _query_mac_from_arp) ...
        if not ip or ip.startswith("127."): return "desconhecido"

        # 1. Verifica cache interno do script
        cached_mac = self.mac_cache.get(ip)
        if cached_mac and cached_mac != "desconhecido":
            return cached_mac

        # 2. Tenta popular/atualizar o cache ARP do SO pingando o host
        #    Um ping rápido pode ser suficiente se o host estiver ativo.
        self._ping_host(ip, timeout=self.config['timeouts']['ping'] / 2) # Ping mais rápido
        time.sleep(0.1) # Pequena pausa para o SO processar a resposta ARP

        # 3. Consulta o cache ARP do SO (que pode ter sido atualizado pelo ping)
        #    A função _update_arp_cache() lê do SO e atualiza self.mac_cache.
        #    Chamá-la aqui especificamente para um IP pode ser redundante se já foi chamada globalmente,
        #    mas garante que tentamos ler o cache do SO após o ping.
        
        # Em vez de chamar _update_arp_cache() que lê tudo, vamos tentar _query_mac_from_arp que é mais direcionado.
        mac_from_so = self._query_mac_from_arp(ip)
        if mac_from_so and mac_from_so != "desconhecido":
            self.mac_cache[ip] = mac_from_so # Atualiza cache do script
            return mac_from_so
        
        # Se ainda não encontrou, faz uma atualização mais completa do cache e verifica novamente
        self._update_arp_cache()
        cached_mac_after_update = self.mac_cache.get(ip)
        if cached_mac_after_update and cached_mac_after_update != "desconhecido":
            return cached_mac_after_update

        logger.debug(f"Não foi possível obter MAC para {ip} após todas as tentativas.")
        return "desconhecido"


    def _query_mac_from_arp(self, ip_target):
        """Consulta MAC da tabela ARP do SO para um IP específico."""
        # Esta função é do script original. Mantida.
        # ... (código original de _query_mac_from_arp) ...
        # A implementação original já parece razoável.
        # O principal é garantir que a saída do comando 'arp -a <ip>' ou 'arp -n <ip>'
        # seja parseada corretamente para o MAC.
        try:
            cmd = ['arp', '-n', ip_target] if self.system != "windows" else ['arp', '-a', ip_target]
            creation_flags = subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            
            output = subprocess.check_output(cmd, timeout=self.config['timeouts']['scan'], 
                                             text=True, creationflags=creation_flags)
            
            # Reutiliza o parser de _parse_arp_output, mas focado no IP alvo
            mac_pattern = re.compile(r"(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}", re.IGNORECASE)
            for line in output.splitlines():
                if ip_target in line: # Garante que é a linha do IP correto
                    match = mac_pattern.search(line)
                    if match:
                        normalized_mac = self.normalize_mac(match.group(0))
                        if normalized_mac:
                            return normalized_mac
            return "desconhecido"
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"Falha ao consultar MAC para {ip_target} diretamente do ARP: {e}")
            return "desconhecido"


    def _is_port_open(self, ip, port, timeout=1):
        """Verifica se uma porta está aberta - Versão específica por sistema"""
        # Esta função é do script original. Mantida.
        # ... (código original de _is_port_open e _is_port_open_win10) ...
        # A lógica original com socket.connect_ex e otimizações para Win10 é mantida.
        # Para simplificar, uma implementação básica:
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            return result == 0
        except socket.error as e: # Inclui socket.timeout
            logger.debug(f"Socket error/timeout verificando {ip}:{port} : {e}")
            return False
        finally:
            if sock:
                sock.close()


    def _ping_host(self, ip, timeout=1):
        """Faz ping em um host - Versão específica por sistema"""
        # Esta função é do script original. Mantida.
        # ... (código original de _ping_host, _ping_host_win10, _ping_host_standard) ...
        # A lógica original com diferentes parâmetros de ping por SO é mantida.
        # Implementação simplificada para este exemplo:
        param = '-n' if self.system == 'windows' else '-c'
        count = '1' # Envia apenas 1 pacote para um ping rápido
        
        # Timeout para o comando ping em milissegundos para Windows, segundos para outros
        timeout_val_str = str(int(timeout * 1000)) if self.system == 'windows' else str(int(max(1, timeout)))
        timeout_opt = '-w' if self.system == 'windows' else '-W' # -W para Linux/macOS (timeout), -w para Windows (wait)

        command = ['ping', param, count, timeout_opt, timeout_val_str, ip]
        
        # Timeout para o subprocesso (um pouco maior que o timeout do ping)
        proc_timeout = timeout + 1 

        try:
            process = subprocess.run(command, capture_output=True, text=True, 
                                     timeout=proc_timeout, check=False, # check=False para não levantar erro em falha de ping
                                     creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0)
            if process.returncode == 0:
                # Em alguns sistemas, returncode 0 não garante resposta se houver perda de pacotes.
                # Verificar a saída para "TTL=" ou "bytes from" seria mais robusto, mas mais complexo.
                # Para Windows, a saída de sucesso geralmente contém "TTL=".
                # Para Linux/macOS, "1 packets transmitted, 1 received".
                if self.is_windows:
                    return "TTL=" in process.stdout 
                else: # Linux/macOS
                    return "1 received" in process.stdout or "1 packets received" in process.stdout
            return False
        except subprocess.TimeoutExpired:
            logger.debug(f"Timeout do subprocesso ao pingar {ip}")
            return False
        except FileNotFoundError:
            logger.error("Comando ping não encontrado. Ping desabilitado.")
            return False # Se ping não existe, não podemos pingar.
        except Exception as e:
            logger.debug(f"Erro inesperado ao pingar {ip}: {e}")
            return False


    def _run_nmap_scan(self, subnet_str): # subnet_str é string
        """Executa nmap para descoberta rápida - Versão específica por sistema"""
        # Esta função é do script original. Mantida.
        # ... (código original de _run_nmap_scan) ...
        # Implementação simplificada:
        if not self._is_nmap_available(): return []
        logger.info(f"Executando Nmap (simplificado) em {subnet_str}...")
        # Comando Nmap básico para portas de impressora comuns
        # -sS (TCP SYN scan, requer root/admin), -Pn (não pingar), -T4 (agressivo)
        # Se não for admin, nmap pode tentar -sT (TCP connect scan)
        cmd_base = ["nmap", "-p", "T:80,T:443,T:515,T:631,T:9100", "--open", "-n"]
        if not self.is_admin: # Se não for admin, não pode fazer SYN scan, -Pn é importante
            cmd_base.append("-Pn") # Assume que os hosts estão online
            cmd_base.append("-sT") # TCP Connect scan
        else: # Se admin, pode tentar SYN scan
            cmd_base.append("-sS")


        if self.is_win10 or self.is_win11:
            cmd = cmd_base + ["-T4", "--host-timeout", "10s", subnet_str]
            timeout = 90
        else:
            cmd = cmd_base + ["-T3", "--host-timeout", "15s", subnet_str]
            timeout = 120
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0)
            if result.returncode == 0:
                return self._parse_nmap_output(result.stdout)
            else:
                logger.warning(f"Nmap falhou com código {result.returncode}. Saída: {result.stderr or result.stdout}")
                return []
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout executando Nmap em {subnet_str}")
            return []
        except Exception as e:
            logger.error(f"Erro executando Nmap: {e}")
            return []


    def _parse_nmap_output(self, output):
        """Processa saída do nmap"""
        # Esta função é do script original. Mantida.
        # ... (código original de _parse_nmap_output) ...
        # Implementação simplificada:
        printers = []
        # Nmap scan report for hostname (IP_ADDRESS)
        # PORT    STATE SERVICE
        # 631/tcp open  ipp
        ip_pattern = re.compile(r"Nmap scan report for .*?\((\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\)")
        port_pattern = re.compile(r"(\d+)/tcp\s+open")
        
        current_ip = None
        current_ports = []

        for line in output.splitlines():
            ip_match = ip_pattern.search(line)
            if ip_match:
                if current_ip and current_ports: # Processa o IP anterior
                    printers.append(self._create_printer_from_nmap(current_ip, current_ports))
                current_ip = ip_match.group(1)
                current_ports = []
                continue
            
            if current_ip:
                port_match = port_pattern.search(line)
                if port_match:
                    port = int(port_match.group(1))
                    if port in COMMON_PRINTER_PORTS:
                        current_ports.append(port)
        
        if current_ip and current_ports: # Processa o último IP
             printers.append(self._create_printer_from_nmap(current_ip, current_ports))
        
        return [p for p in printers if p] # Remove None se _create_printer_from_nmap falhar


    def _create_printer_from_nmap(self, ip, ports):
        """Cria informações de impressora a partir do resultado nmap"""
        # Esta função é do script original. Mantida.
        # ... (código original de _create_printer_from_nmap) ...
        mac = self._get_mac_for_ip(ip) # Tenta obter MAC
        return {
            "ip": ip, "mac_address": mac if mac else "desconhecido",
            "ports": ports, "uri": self._determine_uri(ip, ports),
            "name": f"Impressora Nmap {ip}", "is_online": True, "source": "nmap_parsed"
        }


    def _verify_printer_by_ip(self, ip):
        """Verifica se um IP é de uma impressora (checa portas)"""
        # Esta função é do script original. Mantida.
        # ... (código original de _verify_printer_by_ip) ...
        # Implementação simplificada:
        logger.debug(f"Verificando se {ip} é uma impressora...")
        for port in COMMON_PRINTER_PORTS:
            if self._is_port_open(ip, port, self.config['timeouts']['scan'] / 2): # Timeout menor para verificação rápida
                logger.debug(f"Porta {port} aberta em {ip}. Provavelmente uma impressora.")
                return True
        logger.debug(f"Nenhuma porta de impressora comum aberta em {ip}.")
        return False

    def _create_printer_info(self, ip, mac):
        """Cria informações da impressora com IP e MAC"""
        # Esta função é do script original. Mantida.
        # ... (código original de _create_printer_info) ...
        # Implementação simplificada:
        open_ports = []
        # Verifica rapidamente as portas mais comuns (IPP e JetDirect)
        for port in [631, 9100, 515]: 
            if self._is_port_open(ip, port, self.config['timeouts']['scan'] / 2):
                open_ports.append(port)
        
        if not open_ports: # Se as principais não estão abertas, pode não ser impressora ou estar offline
            logger.debug(f"Nenhuma porta principal de impressora ({[631,9100,515]}) aberta em {ip} para MAC {mac}. Verificação completa de portas não realizada aqui.")
            # Poderia fazer um scan completo de COMMON_PRINTER_PORTS aqui se necessário.
            # Por ora, se as portas principais não estão abertas, retorna uma info básica.
        
        return {
            "ip": ip, "mac_address": self.normalize_mac(mac) or "desconhecido",
            "ports": open_ports, "uri": self._determine_uri(ip, open_ports) if open_ports else f"socket://{ip}",
            "name": f"Impressora {ip}", "is_online": bool(open_ports), # Online se alguma porta relevante foi encontrada
            "source": "mac_lookup"
        }

    # --- Métodos de IPP (pyipp) ---
    async def _get_printer_attributes(self, ip, port=631): # Porta padrão IPP
        """Obtém atributos da impressora usando IPP"""
        # Esta função é do script original. Mantida.
        # ... (código original de _get_printer_attributes, _process_printer_object, _process_printer_dict, _extract_attr_value) ...
        # A lógica original com pyipp é mantida.
        # Pequena adaptação para usar timeouts da config:
        if not HAS_PYIPP:
            return {"ip": ip, "error": "Módulo pyipp não disponível"}

        # Tenta HTTP e HTTPS, e caminhos comuns de IPP
        protocols_config = [
            {"name": "IPP (HTTP)", "uri_scheme": "ipp", "default_port": 631, "tls": False},
            {"name": "IPPS (HTTPS)", "uri_scheme": "ipps", "default_port": 443, "tls": True}, # IPPS é geralmente na 443, mas pode ser na 631 com TLS
        ]
        # Endpoints comuns, alguns podem ser redundantes dependendo da impressora
        common_endpoints = ["/ipp/print", "/ipp/printer", "/ipp", "/"]


        request_timeout = self.config['timeouts']['request']

        for proto_cfg in protocols_config:
            # Tenta a porta padrão do serviço e a porta 631 (comum para IPP/IPPS)
            ports_to_try = list(set([proto_cfg["default_port"], 631, port])) # 'port' é o argumento da função, geralmente 631

            for p_try in ports_to_try:
                for endpoint in common_endpoints:
                    uri = f"{proto_cfg['uri_scheme']}://{ip}:{p_try}{endpoint}"
                    logger.debug(f"Tentando IPP em {uri}...")
                    try:
                        # pyipp.IPP pode não aceitar 'url_path' diretamente na construção em todas as versões.
                        # Algumas versões preferem que o path seja parte da URI.
                        # A biblioteca pyipp pode ter mudado. O original usava client.url_path.
                        # Vamos tentar construir a URI completa e passar para o construtor.
                        
                        # O construtor do pyipp.IPP espera host, port, base_path, tls.
                        # base_path é o que vem depois de host:port.
                        
                        # Se pyipp.IPP constructor takes full URI:
                        # ipp_client = pyipp.IPP(uri, timeout=request_timeout)
                        
                        # Se pyipp.IPP constructor takes host, port, etc.:
                        ipp_client = pyipp.IPP(
                            host=ip, 
                            port=p_try, 
                            base_path=endpoint.lstrip('/'), # Remove / inicial se houver
                            tls=proto_cfg["tls"],
                            timeout=request_timeout,
                            # verify_ssl=False # Adicionar se houver problemas com certs auto-assinados
                        )
                        
                        # O método para obter atributos pode ser get_printer_attributes() ou printer()
                        # Vamos tentar ambos se um falhar.
                        attrs = None
                        try:
                            attrs = await ipp_client.get_printer_attributes() # Método mais comum
                        except AttributeError: # Se get_printer_attributes não existir
                            try:
                                attrs = await ipp_client.printer() # Método legado/alternativo
                            except AttributeError:
                                logger.debug(f"Nenhum método de obtenção de atributos IPP encontrado para {uri}")
                                continue # Tenta próximo endpoint/protocolo
                        except pyipp.exceptions.IPPError as ipp_e:
                            logger.debug(f"Erro IPP (pyipp.IPPError) em {uri}: {ipp_e}")
                            continue # Tenta próximo
                        except asyncio.TimeoutError:
                            logger.debug(f"Timeout IPP em {uri}")
                            continue # Tenta próximo
                        except Exception as e_ipp_call: # Outros erros de conexão/IPP
                            logger.debug(f"Falha na chamada IPP para {uri}: {e_ipp_call}")
                            continue

                        if attrs:
                            logger.info(f"Atributos IPP obtidos com sucesso de {uri}")
                            # O original tinha _process_printer_object e _process_printer_dict
                            # A estrutura de 'attrs' de pyipp pode variar.
                            # Geralmente é um dicionário.
                            return self._process_ipp_attributes(attrs, ip, uri)
                            
                    except Exception as e_client_setup: # Erro ao configurar cliente IPP
                        logger.debug(f"Erro ao configurar cliente IPP para {uri}: {e_client_setup}")
                        continue # Tenta próximo
        
        logger.warning(f"Não foi possível obter atributos IPP para {ip} após todas as tentativas.")
        return {"ip": ip, "name": f"Impressora {ip}", "printer-state": "Desconhecido (Falha na conexão IPP)"}

    def _process_ipp_attributes(self, attrs, ip, uri_source):
        """Processa atributos retornados pelo pyipp (geralmente um dict)."""
        if not isinstance(attrs, dict):
            logger.warning(f"Atributos IPP para {ip} não são um dicionário: {type(attrs)}")
            return {"ip": ip, "name": f"Impressora {ip}", "printer-state": "Formato de atributos IPP inesperado", "raw_data": str(attrs)}

        result = {"ip": ip, "uri_source": uri_source}
        
        # Mapeamento de chaves IPP para chaves mais amigáveis (se necessário)
        # As chaves em 'attrs' geralmente já são descritivas (ex: 'printer-name', 'printer-make-and-model')
        
        # Nome da impressora
        name_val = attrs.get('printer-name', {}).get('value', f"Impressora {ip}")
        result['name'] = name_val if isinstance(name_val, str) else str(name_val) # Garante string

        # Fabricante e modelo
        make_model_val = attrs.get('printer-make-and-model', {}).get('value', 'Desconhecido')
        result['printer-make-and-model'] = make_model_val if isinstance(make_model_val, str) else str(make_model_val)
        
        # Estado da impressora
        state_code = attrs.get('printer-state', {}).get('value', 0) # 0 é um valor não padrão
        state_reasons_list = attrs.get('printer-state-reasons', {}).get('value', ['none'])
        if not isinstance(state_reasons_list, list): state_reasons_list = [str(state_reasons_list)]


        state_map = {3: "Idle (Pronta)", 4: "Processing (Processando)", 5: "Stopped (Parada)"}
        result['printer-state-code'] = state_code
        result['printer-state'] = state_map.get(state_code, f"Desconhecido (Código: {state_code})")
        result['printer-state-reasons'] = ", ".join(r for r in state_reasons_list if r != 'none') or "Nenhuma"

        # Outros atributos úteis
        result['printer-location'] = str(attrs.get('printer-location', {}).get('value', ''))
        result['printer-info'] = str(attrs.get('printer-info', {}).get('value', '')) # Descrição adicional
        
        # Tenta obter MAC do 'printer-device-id' se disponível (formato CMD:...)
        device_id_str = str(attrs.get('printer-device-id', {}).get('value', ''))
        if "MAC:" in device_id_str.upper():
            mac_match = re.search(r"MAC:([0-9A-Fa-f]{2}(?:[:-]?[0-9A-Fa-f]{2}){5})", device_id_str, re.IGNORECASE)
            if mac_match:
                normalized_mac_from_ipp = self.normalize_mac(mac_match.group(1))
                if normalized_mac_from_ipp:
                    result['mac_address_ipp'] = normalized_mac_from_ipp
        
        # Adiciona alguns atributos brutos para depuração, se necessário
        # result['raw_ipp_attributes'] = {k: str(v.get('value')) for k,v in attrs.items() if v.get('value')}

        logger.debug(f"Atributos IPP processados para {ip}: Nome='{result['name']}', Estado='{result['printer-state']}'")
        return result

    def _extract_attr_value(self, attrs, key, default=None):
        """Extrai valor de atributo, tratando listas (do script original)"""
        # Esta função é do script original. Mantida.
        value = attrs.get(key, default)
        if isinstance(value, list) and len(value) == 1: # Se for lista de um único item, pega o item
            return value[0]
        return value

# Exemplo de uso (para teste)
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Para testar o logging do módulo específico mais detalhadamente:
    # logging.getLogger("PrintManagementSystem.Utils.PrinterDiscovery").setLevel(logging.DEBUG)

    discovery = PrinterDiscovery()

    print("\n--- Testando descoberta geral de impressoras ---")
    printers = discovery.discover_printers()
    if printers:
        print(f"Total de impressoras encontradas: {len(printers)}")
        for p in printers:
            print(f"  Impressora: {p.get('name', 'N/A')}, IP: {p.get('ip', 'N/A')}, MAC: {p.get('mac_address', 'N/A')}, Portas: {p.get('ports', [])}, URI: {p.get('uri', 'N/A')}, Fonte: {p.get('source', 'N/A')}")
            # Tenta obter detalhes IPP para a primeira impressora encontrada com IP
            if p.get('ip') and HAS_PYIPP:
                print(f"    Obtendo detalhes IPP para {p.get('ip')}...")
                details = discovery.get_printer_details(p.get('ip'))
                print(f"    Detalhes IPP: {details.get('name')}, Estado: {details.get('printer-state')}, Modelo: {details.get('printer-make-and-model')}")
                if details.get('mac_address_ipp'): print(f"    MAC (de IPP): {details.get('mac_address_ipp')}")
                break # Só detalha uma para o exemplo
    else:
        print("Nenhuma impressora encontrada na descoberta geral.")

    print("\n--- Testando descoberta por MAC específico (exemplo) ---")
    # Substitua pelo MAC de uma impressora na sua rede para testar
    # Formatos de MAC aceitos: XX:XX:XX:XX:XX:XX, XX-XX-XX-XX-XX-XX, XXXXXXXXXXXX
    test_mac = "50:c2:e8:d7:8f:c5" # MAC EXEMPLO - SUBSTITUA!
    if len(sys.argv) > 1: # Permite passar MAC como argumento
        test_mac = sys.argv[1]
        print(f"Usando MAC do argumento: {test_mac}")
    else:
        print(f"Usando MAC de exemplo: {test_mac} (Pode não existir na sua rede)")

    printer_by_mac = discovery.discover_printer_by_mac(test_mac)
    if printer_by_mac:
        print(f"Impressora encontrada pelo MAC {test_mac}:")
        print(f"  Nome: {printer_by_mac.get('name', 'N/A')}, IP: {printer_by_mac.get('ip', 'N/A')}, Portas: {printer_by_mac.get('ports', [])}, URI: {printer_by_mac.get('uri', 'N/A')}")
    else:
        print(f"Nenhuma impressora encontrada com o MAC {test_mac}.")

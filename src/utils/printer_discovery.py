#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitário para descoberta automática de impressoras na rede - Versão Corrigida
Melhorada para maior compatibilidade com Windows 11 e robustez geral
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

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterDiscovery")

# Configurações globais ajustadas para maior compatibilidade
TIMEOUT_REQUEST = 3         # Aumentado de 2 para 3 segundos
TIMEOUT_SCAN = 1           # Aumentado de 0.3 para 1 segundo
TIMEOUT_PING = 2           # Novo timeout específico para ping
PARALLEL_HOSTS = 15        # Reduzido de 25 para 15 para evitar sobrecarga
RETRY_ATTEMPTS = 3         # Número de tentativas para comandos que podem falhar
COMMON_PRINTER_PORTS = [631, 9100, 80, 443, 515]

# Configurações para o IPP
try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    HAS_PYIPP = False
    logger.warning("Módulo pyipp não encontrado. Informações detalhadas de impressoras não estarão disponíveis.")

class PrinterDiscovery:
    """Classe para descoberta automática de impressoras na rede - Versão Melhorada"""
    
    def __init__(self):
        """Inicializa o descobridor de impressoras"""
        self.printers = []
        self.system = platform.system().lower()
        self.is_windows = self.system == "windows"
        self.is_admin = self._check_admin_privileges()
        
        # Cache para MACs descobertos
        self.mac_cache = {}
        self.last_arp_update = 0
        
        logger.info(f"Sistema: {self.system}, Admin: {self.is_admin}")
    
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
            
            # Atualiza cache ARP primeiro
            self._update_arp_cache()
            
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
        """Obtém as redes locais para escanear"""
        networks = []
        local_ip = self._get_local_ip()
        
        if not local_ip or local_ip.startswith('127.'):
            # Fallback para redes comuns
            common_networks = [
                "192.168.1.0/24", "192.168.0.0/24", "192.168.2.0/24",
                "10.0.0.0/24", "10.0.1.0/24", "172.16.0.0/24"
            ]
            for net_str in common_networks:
                try:
                    networks.append(ipaddress.IPv4Network(net_str))
                except:
                    pass
        else:
            # Rede principal baseada no IP atual
            try:
                parts = local_ip.split('.')
                if len(parts) == 4:
                    network_24 = f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
                    networks.append(ipaddress.IPv4Network(network_24))
                    logger.info(f"Rede principal detectada: {network_24}")
            except:
                pass
        
        return networks
    
    async def _manual_network_scan(self, network):
        """Escaneamento manual da rede"""
        printers = []
        
        try:
            # Primeiro escaneamento: IPs comuns para impressoras
            common_ips = self._get_common_printer_ips(network)
            logger.info(f"Escaneando {len(common_ips)} IPs comuns para impressoras...")
            
            common_printers = await self._scan_ip_list(common_ips)
            printers.extend(common_printers)
            
            # Se não encontrou muitas impressoras, expande a busca
            if len(common_printers) < 3:
                # Pega mais IPs da rede (mas limita para não sobrecarregar)
                all_hosts = list(network.hosts())
                if len(all_hosts) > 50:
                    # Para redes grandes, pega uma amostra
                    sample_size = min(50, len(all_hosts))
                    extended_ips = random.sample([str(ip) for ip in all_hosts], sample_size)
                else:
                    extended_ips = [str(ip) for ip in all_hosts]
                
                # Remove IPs já escaneados
                extended_ips = [ip for ip in extended_ips if ip not in common_ips]
                
                if extended_ips:
                    logger.info(f"Expandindo busca para {len(extended_ips)} IPs adicionais...")
                    extended_printers = await self._scan_ip_list(extended_ips)
                    printers.extend(extended_printers)
        
        except Exception as e:
            logger.error(f"Erro no escaneamento manual: {str(e)}")
        
        return printers
    
    def _get_common_printer_ips(self, network):
        """Gera lista de IPs comuns para impressoras"""
        common_ips = []
        
        try:
            # IPs com finais típicos de impressoras
            common_suffixes = [1, 2, 10, 20, 30, 50, 100, 101, 102, 150, 200, 250, 251, 252, 253, 254]
            
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
        """Escaneia uma lista de IPs"""
        printers = []
        
        # Processa em chunks para evitar sobrecarga
        for i in range(0, len(ip_list), PARALLEL_HOSTS):
            chunk = ip_list[i:i+PARALLEL_HOSTS]
            
            # Cria tasks para este chunk
            tasks = [self._scan_single_ip(ip) for ip in chunk]
            
            try:
                # Aguarda todas as tasks do chunk com timeout
                chunk_results = await asyncio.wait_for(
                    asyncio.gather(*tasks, return_exceptions=True),
                    timeout=TIMEOUT_SCAN * len(chunk) + 5
                )
                
                for result in chunk_results:
                    if isinstance(result, dict) and result:
                        printers.append(result)
                        logger.info(f"Impressora encontrada: {result['ip']}")
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout no escaneamento do chunk {i//PARALLEL_HOSTS + 1}")
            except Exception as e:
                logger.warning(f"Erro no chunk {i//PARALLEL_HOSTS + 1}: {str(e)}")
        
        return printers
    
    async def _scan_single_ip(self, ip):
        """Escaneia um único IP para verificar se é impressora"""
        try:
            # Primeiro verifica se o host responde
            if not self._ping_host(ip, TIMEOUT_PING):
                return None
            
            # Verifica portas de impressora
            open_ports = []
            port_tasks = [self._check_port_async(ip, port) for port in COMMON_PRINTER_PORTS]
            
            try:
                port_results = await asyncio.wait_for(
                    asyncio.gather(*port_tasks, return_exceptions=True),
                    timeout=TIMEOUT_SCAN * len(COMMON_PRINTER_PORTS)
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
            future = asyncio.get_event_loop().run_in_executor(
                None, self._is_port_open, ip, port, TIMEOUT_SCAN
            )
            return await asyncio.wait_for(future, timeout=TIMEOUT_SCAN + 1)
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
            
            with urllib.request.urlopen(req, timeout=2, context=ctx) as response:
                content = response.read().decode('utf-8', errors='ignore').lower()
                
                # Palavras-chave que indicam impressora
                printer_keywords = [
                    'printer', 'print', 'toner', 'cartridge', 'ink',
                    'samsung', 'hp', 'canon', 'epson', 'brother', 'lexmark',
                    'xerox', 'kyocera', 'ricoh', 'sharp', 'konica',
                    'status', 'supplies', 'maintenance'
                ]
                
                return any(keyword in content for keyword in printer_keywords)
                
        except:
            return False  # Se falhar, assume que não é impressora
    
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
        """Atualiza o cache ARP"""
        current_time = time.time()
        
        # Só atualiza se passou mais de 30 segundos
        if current_time - self.last_arp_update < 30:
            return
        
        try:
            logger.info("Atualizando cache ARP...")
            self.mac_cache = {}
            
            # Comando para obter tabela ARP
            if self.is_windows:
                cmd = ['arp', '-a']
                creation_flags = subprocess.CREATE_NO_WINDOW
            else:
                cmd = ['arp', '-a']
                creation_flags = 0
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creation_flags
            )
            
            if result.returncode == 0:
                self._parse_arp_output(result.stdout)
                self.last_arp_update = current_time
                logger.info(f"Cache ARP atualizado com {len(self.mac_cache)} entradas")
            
        except Exception as e:
            logger.warning(f"Erro ao atualizar cache ARP: {str(e)}")
    
    def _parse_arp_output(self, output):
        """Processa a saída do comando ARP"""
        try:
            # Padrões para diferentes sistemas
            if self.is_windows:
                # Windows: "  192.168.1.1          00-11-22-33-44-55     dynamic"
                pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s+([0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2}[-:][0-9A-Fa-f]{2})'
            else:
                # Linux/macOS: formato pode variar
                pattern = r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\s.*?([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})'
            
            for line in output.split('\n'):
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    ip = match.group(1)
                    mac = self.normalize_mac(match.group(2))
                    if mac:
                        self.mac_cache[ip] = mac
                        
        except Exception as e:
            logger.warning(f"Erro ao processar saída ARP: {str(e)}")
    
    def _get_mac_for_ip(self, ip):
        """Obtém MAC address para um IP"""
        # Primeiro verifica cache
        if ip in self.mac_cache:
            return self.mac_cache[ip]
        
        # Faz ping para atualizar ARP
        self._ping_host(ip, 1)
        time.sleep(0.1)
        
        # Tenta obter MAC usando múltiplos métodos
        for attempt in range(RETRY_ATTEMPTS):
            mac = self._query_mac_from_arp(ip)
            if mac and mac != "desconhecido":
                self.mac_cache[ip] = mac
                return mac
            
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(0.2)
        
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
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=2,
                creationflags=creation_flags
            )
            
            if result.returncode == 0:
                # Procura MAC na saída
                mac_pattern = r'([0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2}[:-][0-9A-Fa-f]{2})'
                match = re.search(mac_pattern, result.stdout, re.IGNORECASE)
                if match:
                    return self.normalize_mac(match.group(1))
            
        except Exception as e:
            logger.debug(f"Erro consultando MAC para {ip}: {str(e)}")
        
        return "desconhecido"
    
    def _get_local_ip(self):
        """Obtém o endereço IP local da máquina"""
        try:
            # Método mais confiável: conecta a um servidor externo
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(2)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                
                if local_ip and not local_ip.startswith('127.'):
                    return local_ip
        except:
            pass
        
        # Fallback: usa hostname
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            if local_ip and not local_ip.startswith('127.'):
                return local_ip
        except:
            pass
        
        return "192.168.1.100"  # Fallback final
    
    def _is_port_open(self, ip, port, timeout=1):
        """Verifica se uma porta está aberta"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(timeout)
                result = sock.connect_ex((ip, port))
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
                timeout=timeout + 1,
                creationflags=creation_flags
            )
            
            return result.returncode == 0
            
        except:
            return False
    
    def _run_nmap_scan(self, subnet):
        """Executa nmap para descoberta rápida"""
        try:
            # Verifica se nmap está disponível
            result = subprocess.run(
                ["nmap", "--version"],
                capture_output=True,
                timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            )
            if result.returncode != 0:
                return []
        except:
            logger.info("nmap não disponível")
            return []
        
        try:
            logger.info(f"Executando nmap em {subnet}...")
            
            cmd = [
                "nmap",
                "-p", "631,9100,80,443,515",  # Portas de impressora
                "-T4",  # Timing template
                "--open",  # Só portas abertas
                "-n",  # Não resolve DNS
                "--host-timeout", "10s",
                "--max-retries", "1",
                str(subnet)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                creationflags=subprocess.CREATE_NO_WINDOW if self.is_windows else 0
            )
            
            if result.returncode != 0:
                logger.warning(f"nmap falhou com código {result.returncode}")
                return []
            
            return self._parse_nmap_output(result.stdout)
            
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
        
        # Atualiza cache ARP
        self._update_arp_cache()
        
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
            common_ips = self._get_common_printer_ips(network)
            
            # Ping em paralelo
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                executor.map(lambda ip: self._ping_host(ip, 1), common_ips)
            
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
            for port in COMMON_PRINTER_PORTS:
                if self._is_port_open(ip, port, 1):
                    return True
            return False
        except:
            return False
    
    def _create_printer_info(self, ip, mac):
        """Cria informações da impressora com IP e MAC"""
        try:
            # Verifica portas abertas
            open_ports = []
            for port in COMMON_PRINTER_PORTS:
                if self._is_port_open(ip, port, 1):
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
        
        for protocol in protocols:
            tls_mode = protocol["tls"]
            protocol_name = protocol["name"]
            
            for endpoint in endpoints:
                try:
                    logger.debug(f"Tentando {protocol_name} com endpoint {endpoint} em {ip}")
                    
                    client = pyipp.IPP(host=ip, port=port, tls=tls_mode)
                    client.url_path = endpoint
                    
                    printer_attrs = await asyncio.wait_for(client.printer(), timeout=TIMEOUT_REQUEST)
                    
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
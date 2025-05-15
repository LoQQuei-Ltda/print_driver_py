#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitários para impressão
"""

import os
import sys
import platform
import logging
import subprocess
import tempfile
import socket
import time

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterUtils")

class PrinterUtils:
    """Utilitários para impressão de documentos"""
    
    @staticmethod
    def get_system_printers():
        """
        Obtém lista de impressoras instaladas no sistema
        
        Returns:
            list: Lista de dicionários com informações das impressoras
        """
        printers = []
        system = platform.system()
        
        try:
            if system == "Windows":
                printers = PrinterUtils._get_windows_printers()
            elif system == "Darwin":  # macOS
                printers = PrinterUtils._get_macos_printers()
            else:  # Linux ou outros
                printers = PrinterUtils._get_linux_printers()
        except Exception as e:
            logger.error(f"Erro ao obter impressoras do sistema: {str(e)}")
        
        return printers
    
    @staticmethod
    def _get_windows_printers():
        """
        Obtém impressoras no Windows
        
        Returns:
            list: Lista de impressoras
        """
        printers = []
        
        try:
            import win32print
            
            # Obtém impressora padrão
            default_printer = win32print.GetDefaultPrinter()
            
            # Lista todas as impressoras
            for flags, description, name, comment in win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS):
                try:
                    # Tenta obter informações adicionais
                    handle = win32print.OpenPrinter(name)
                    info = win32print.GetPrinter(handle, 2)
                    win32print.ClosePrinter(handle)
                    
                    status_str = "Unknown"
                    if "Status" in info:
                        status = info["Status"]
                        if status == 0:
                            status_str = "Ready"
                        elif status & win32print.PRINTER_STATUS_OFFLINE:
                            status_str = "Offline"
                        elif status & win32print.PRINTER_STATUS_ERROR:
                            status_str = "Error"
                        elif status & win32print.PRINTER_STATUS_BUSY:
                            status_str = "Busy"
                    
                    printer_info = {
                        "id": name,
                        "name": description,
                        "system_name": name,
                        "status": status_str,
                        "default": name == default_printer,
                        "location": info.get("Location", ""),
                        "model": info.get("DriverName", ""),
                        "mac_address": "",  # Não disponível diretamente no Windows
                        "ip_address": ""   # Não disponível diretamente no Windows
                    }
                    
                    printers.append(printer_info)
                except Exception as e:
                    logger.warning(f"Erro ao obter informações da impressora {name}: {str(e)}")
            
        except ImportError:
            logger.error("Módulo win32print não encontrado. Instale-o com 'pip install pywin32'")
        except Exception as e:
            logger.error(f"Erro ao obter impressoras do Windows: {str(e)}")
        
        return printers
    
    @staticmethod
    def _get_macos_printers():
        """
        Obtém impressoras no macOS
        
        Returns:
            list: Lista de impressoras
        """
        printers = []
        
        try:
            # Usa o comando lpstat para listar impressoras
            output = subprocess.check_output(["lpstat", "-p"], universal_newlines=True)
            default_output = subprocess.check_output(["lpstat", "-d"], universal_newlines=True)
            
            # Extrai a impressora padrão
            default_printer = ""
            if "system default destination:" in default_output:
                default_printer = default_output.split("system default destination:")[1].strip()
            
            # Processa a saída
            lines = output.splitlines()
            for line in lines:
                if line.startswith("printer "):
                    parts = line.split("printer ", 1)[1].split(" ", 1)
                    if len(parts) >= 1:
                        name = parts[0]
                        status = "Ready"
                        if len(parts) > 1 and "disabled" in parts[1]:
                            status = "Offline"
                        
                        printer_info = {
                            "id": name,
                            "name": name,
                            "system_name": name,
                            "status": status,
                            "default": name == default_printer,
                            "location": "",
                            "model": "",
                            "mac_address": "",
                            "ip_address": ""
                        }
                        
                        printers.append(printer_info)
        
        except subprocess.CalledProcessError as e:
            logger.error(f"Erro ao executar comando lpstat: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao obter impressoras do macOS: {str(e)}")
        
        return printers
    
    @staticmethod
    def _get_linux_printers():
        """
        Obtém impressoras no Linux
        
        Returns:
            list: Lista de impressoras
        """
        printers = []
        
        try:
            import cups
            
            conn = cups.Connection()
            printers_dict = conn.getPrinters()
            default_printer = conn.getDefault()
            
            for name, printer in printers_dict.items():
                try:
                    status = "Ready"
                    if "printer-state" in printer:
                        state = printer["printer-state"]
                        if state == 3:
                            status = "Ready"
                        elif state == 4:
                            status = "Processing"
                        elif state == 5:
                            status = "Stopped"
                        else:
                            status = f"Unknown ({state})"
                    
                    # Tenta obter o endereço IP da impressora do URI
                    ip_address = ""
                    if "device-uri" in printer:
                        uri = printer["device-uri"]
                        if "://" in uri:
                            host_part = uri.split("://")[1].split("/")[0]
                            if ":" in host_part:
                                host_part = host_part.split(":")[0]
                            
                            # Verifica se parece um IP
                            if all(part.isdigit() and int(part) < 256 for part in host_part.split(".") if part):
                                ip_address = host_part
                    
                    printer_info = {
                        "id": name,
                        "name": printer.get("printer-info", name),
                        "system_name": name,
                        "status": status,
                        "default": name == default_printer,
                        "location": printer.get("printer-location", ""),
                        "model": printer.get("printer-make-and-model", ""),
                        "mac_address": "",  # Não disponível diretamente no CUPS
                        "ip_address": ip_address
                    }
                    
                    printers.append(printer_info)
                    
                except Exception as e:
                    logger.warning(f"Erro ao processar impressora {name}: {str(e)}")
            
        except ImportError:
            logger.error("Módulo cups não encontrado. Instale-o com 'pip install pycups'")
        except Exception as e:
            logger.error(f"Erro ao obter impressoras do Linux: {str(e)}")
        
        return printers
    
    @staticmethod
    def print_file(file_path, printer_name=None, options=None):
        """
        Imprime um arquivo na impressora especificada
        
        Args:
            file_path (str): Caminho do arquivo para impressão
            printer_name (str, optional): Nome da impressora
            options (dict, optional): Opções de impressão
            
        Returns:
            bool: True se a impressão foi iniciada com sucesso
            
        Raises:
            FileNotFoundError: Se o arquivo não for encontrado
            ValueError: Se ocorrer um erro na impressão
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        system = platform.system()
        options = options or {}
        
        try:
            if system == "Windows":
                return PrinterUtils._print_windows(file_path, printer_name, options)
            elif system == "Darwin":  # macOS
                return PrinterUtils._print_macos(file_path, printer_name, options)
            else:  # Linux ou outros
                return PrinterUtils._print_linux(file_path, printer_name, options)
                
        except Exception as e:
            logger.error(f"Erro ao imprimir arquivo: {str(e)}")
            raise ValueError(f"Erro ao imprimir arquivo: {str(e)}")
    
    @staticmethod
    def _print_windows(file_path, printer_name, options):
        """
        Imprime um arquivo no Windows
        
        Args:
            file_path (str): Caminho do arquivo
            printer_name (str): Nome da impressora
            options (dict): Opções de impressão
            
        Returns:
            bool: True se a impressão foi iniciada com sucesso
        """
        try:
            import win32print
            import win32api
            
            if not printer_name:
                printer_name = win32print.GetDefaultPrinter()
            
            if file_path.lower().endswith(('.pdf', '.txt')):
                # Para PDF e TXT, usamos ShellExecute
                win32api.ShellExecute(
                    0,
                    "print",
                    file_path,
                    f'"{printer_name}"',
                    ".",
                    0
                )
            else:
                # Para outros tipos de arquivo, tentamos abrir a impressora diretamente
                handle = win32print.OpenPrinter(printer_name)
                try:
                    job = win32print.StartDocPrinter(handle, 1, ("Print Job", None, "RAW"))
                    try:
                        win32print.StartPagePrinter(handle)
                        with open(file_path, 'rb') as f:
                            data = f.read()
                            win32print.WritePrinter(handle, data)
                        win32print.EndPagePrinter(handle)
                    finally:
                        win32print.EndDocPrinter(handle)
                finally:
                    win32print.ClosePrinter(handle)
            
            return True
            
        except ImportError:
            logger.error("Módulo win32print não encontrado. Instale-o com 'pip install pywin32'")
            raise
        except Exception as e:
            logger.error(f"Erro ao imprimir no Windows: {str(e)}")
            raise
    
    @staticmethod
    def _print_macos(file_path, printer_name, options):
        """
        Imprime um arquivo no macOS
        
        Args:
            file_path (str): Caminho do arquivo
            printer_name (str): Nome da impressora
            options (dict): Opções de impressão
            
        Returns:
            bool: True se a impressão foi iniciada com sucesso
        """
        cmd = ["lp"]
        
        if printer_name:
            cmd.extend(["-d", printer_name])
        
        # Adiciona opções de impressão
        for key, value in options.items():
            cmd.extend(["-o", f"{key}={value}"])
        
        cmd.append(file_path)
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            _, stderr = process.communicate()
            
            if process.returncode != 0:
                error = stderr.decode('utf-8', errors='replace')
                logger.error(f"Erro ao imprimir no macOS: {error}")
                raise ValueError(f"Erro ao imprimir: {error}")
            
            return True
            
        except subprocess.SubprocessError as e:
            logger.error(f"Erro ao executar comando lp: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Erro ao imprimir no macOS: {str(e)}")
            raise
    
    @staticmethod
    def _print_linux(file_path, printer_name, options):
        """
        Imprime um arquivo no Linux
        
        Args:
            file_path (str): Caminho do arquivo
            printer_name (str): Nome da impressora
            options (dict): Opções de impressão
            
        Returns:
            bool: True se a impressão foi iniciada com sucesso
        """
        try:
            import cups
            
            conn = cups.Connection()
            
            if not printer_name:
                printer_name = conn.getDefault()
                if not printer_name:
                    printers = conn.getPrinters()
                    if printers:
                        printer_name = list(printers.keys())[0]
                    else:
                        raise ValueError("Nenhuma impressora disponível")
            
            # Converte opções para o formato do CUPS
            cups_options = {}
            for key, value in options.items():
                cups_options[key] = str(value)
            
            job_id = conn.printFile(printer_name, file_path, "Print Job", cups_options)
            
            return job_id > 0
            
        except ImportError:
            logger.error("Módulo cups não encontrado. Instale-o com 'pip install pycups'")
            
            # Tenta usar lp como alternativa
            return PrinterUtils._print_macos(file_path, printer_name, options)
            
        except Exception as e:
            logger.error(f"Erro ao imprimir no Linux: {str(e)}")
            raise
    
    @staticmethod
    def print_to_network_printer(file_path, ip_address, port=9100, timeout=30):
        """
        Imprime diretamente em uma impressora de rede usando o protocolo RAW
        
        Args:
            file_path (str): Caminho do arquivo para impressão
            ip_address (str): Endereço IP da impressora
            port (int): Porta da impressora (padrão: 9100 para RAW)
            timeout (int): Tempo limite em segundos
            
        Returns:
            bool: True se a impressão foi enviada com sucesso
            
        Raises:
            FileNotFoundError: Se o arquivo não for encontrado
            ConnectionError: Se não for possível conectar à impressora
            ValueError: Se ocorrer um erro na impressão
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        try:
            # Abre o arquivo
            with open(file_path, 'rb') as f:
                data = f.read()
            
            # Conecta à impressora
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            try:
                sock.connect((ip_address, port))
                
                # Envia os dados
                sock.sendall(data)
                
                # Aguarda confirmação (alguns dispositivos precisam de tempo)
                time.sleep(1)
                
                return True
                
            finally:
                sock.close()
                
        except socket.timeout:
            logger.error(f"Tempo limite excedido ao conectar à impressora {ip_address}:{port}")
            raise ConnectionError(f"Tempo limite excedido ao conectar à impressora {ip_address}:{port}")
        except socket.error as e:
            logger.error(f"Erro de socket ao imprimir para {ip_address}:{port}: {str(e)}")
            raise ConnectionError(f"Erro ao conectar à impressora {ip_address}:{port}: {str(e)}")
        except Exception as e:
            logger.error(f"Erro ao imprimir para impressora de rede: {str(e)}")
            raise ValueError(f"Erro ao imprimir para impressora de rede: {str(e)}")
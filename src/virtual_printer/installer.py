#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Instalador da impressora virtual cross-platform
"""

import os
import sys
import platform
import logging
import subprocess
import tempfile
import shutil
import ctypes
import typing
from pathlib import Path

logger = logging.getLogger("PrintManagementSystem.VirtualPrinter.Installer")

class PrinterManager:
    """Classe base para gerenciar impressoras específicas do sistema"""
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona uma impressora virtual"""
        raise NotImplementedError
    
    def remove_printer(self, name):
        """Remove uma impressora"""
        raise NotImplementedError
    
    def remove_port(self, port_name):
        """Remove uma porta de impressora"""
        raise NotImplementedError
    
    def check_printer_exists(self, name):
        """Verifica se uma impressora existe"""
        raise NotImplementedError
    
    def check_port_exists(self, port_name):
        """Verifica se uma porta existe"""
        raise NotImplementedError

class WindowsPrinterManager(PrinterManager):
    """Gerenciador de impressoras para Windows"""
    
    def __init__(self):
        self.postscript_printer_drivers = [
            'Microsoft Print To PDF',
            'Microsoft XPS Document Writer',
            'HP Universal Printing PS',
            'HP Color LaserJet 2800 Series PS',
            'Generic / Text Only'
        ]
        self.default_driver = self._find_available_driver()
    
    def _find_available_driver(self):
        """Encontra um driver disponível"""
        try:
            output = subprocess.check_output([
                'powershell', '-command',
                'Get-PrinterDriver | Select-Object Name | Format-Table -HideTableHeaders'
            ], universal_newlines=True)
            
            available_drivers = [line.strip() for line in output.splitlines() if line.strip()]
            
            for driver in self.postscript_printer_drivers:
                if driver in available_drivers:
                    return driver
            
            return available_drivers[0] if available_drivers else 'Microsoft Print To PDF'
        except:
            return 'Microsoft Print To PDF'
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Windows"""
        if printer_port_name is None:
            printer_port_name = f"{ip}:{port}"
        
        # Criar porta
        cmd = ['cscript', r'c:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
               '-md', '-a', '-o', 'raw', '-r', printer_port_name, '-h', ip, '-n', str(port)]
        
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
        except Exception as e:
            logger.error(f"Erro ao criar porta: {e}")
            return False
        
        # Criar impressora
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/if',
               '/b', name, '/r', printer_port_name, '/m', self.default_driver, '/Z']
        
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
            logger.info(f"Impressora Windows '{name}' instalada com sucesso!")
            
            # Definir comentário se fornecido
            if comment:
                self._set_printer_comment(name, comment)
            
            return True
        except Exception as e:
            logger.error(f"Erro ao criar impressora: {e}")
            return False
    
    def _set_printer_comment(self, name, comment):
        """Adiciona um comentário à impressora"""
        comment = comment.replace('"', '\\"').replace('\n', '\\n')
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/Xs',
               '/n', name, 'comment', comment]
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
        except Exception as e:
            logger.warning(f"Erro ao definir comentário: {e}")
    
    def remove_printer(self, name):
        """Remove impressora no Windows"""
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/dl', '/n', name]
        try:
            subprocess.run(cmd, shell=True, capture_output=True, timeout=10)
            return True
        except:
            return False
    
    def remove_port(self, port_name):
        """Remove porta no Windows"""
        cmd = ['cscript', r'c:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
               '-d', '-r', port_name]
        try:
            subprocess.run(cmd, shell=True, capture_output=True)
        except:
            pass
    
    def check_printer_exists(self, name):
        """Verifica se impressora existe no Windows"""
        try:
            cmd = ['powershell', '-command', 
                f'if (Get-Printer -Name "{name}" -ErrorAction SilentlyContinue) {{Write-Output "true"}} else {{Write-Output "false"}}']
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            return result.stdout.decode().strip().lower() == "true"
        except:
            return False
    
    def check_port_exists(self, port_name):
        """Verifica se porta existe no Windows"""
        try:
            cmd = ['powershell', '-command', 
                f'if (Get-PrinterPort -Name "{port_name}" -ErrorAction SilentlyContinue) {{Write-Output "true"}} else {{Write-Output "false"}}']
            result = subprocess.run(cmd, shell=True, capture_output=True, timeout=5)
            return result.stdout.decode().strip().lower() == "true"
        except:
            return False

class UnixPrinterManager(PrinterManager):
    """Gerenciador de impressoras para sistemas Unix (Linux/macOS) usando CUPS"""
    
    def __init__(self):
        self.system = platform.system()
        self.cups_available = self._check_cups_availability()
        
        if not self.cups_available:
            self._install_cups_suggestions()
    
    def _check_cups_availability(self):
        """Verifica se CUPS está instalado e acessível"""
        try:
            result = subprocess.run(['which', 'lpadmin'], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            
            result = subprocess.run(['which', 'lpstat'], capture_output=True, text=True)
            if result.returncode != 0:
                return False
            
            try:
                result = subprocess.run(['lpstat', '-r'], capture_output=True, text=True, timeout=5)
                if "not ready" in result.stdout.lower():
                    self._start_cups_service()
            except subprocess.TimeoutExpired:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Erro ao verificar CUPS: {e}")
            return False
    
    def _start_cups_service(self):
        """Tenta iniciar o serviço CUPS"""
        logger.info("Tentando iniciar o serviço CUPS...")
        
        if self.system == 'Linux':
            service_commands = [
                ['sudo', 'systemctl', 'start', 'cups'],
                ['sudo', 'service', 'cups', 'start'],
                ['sudo', '/etc/init.d/cups', 'start']
            ]
        elif self.system == 'Darwin':  # macOS
            service_commands = [
                ['sudo', 'launchctl', 'load', '/System/Library/LaunchDaemons/org.cups.cupsd.plist'],
                ['sudo', 'brew', 'services', 'start', 'cups']
            ]
        else:
            service_commands = []
        
        for cmd in service_commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    logger.info("Serviço CUPS iniciado com sucesso.")
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        return False
    
    def _install_cups_suggestions(self):
        """Fornece sugestões para instalar CUPS"""
        logger.warning("CUPS não encontrado no sistema")
        if self.system == 'Linux':
            logger.info("Para instalar CUPS no Linux: sudo apt-get install cups cups-client")
        elif self.system == 'Darwin':
            logger.info("No macOS, CUPS geralmente está pré-instalado. Tente: brew install cups")
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Unix usando CUPS"""
        if not self.cups_available:
            logger.error("CUPS não está disponível. Não é possível adicionar impressora.")
            return False

        device_uri = f"socket://{ip}:{port}"
        
        cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri]
        
        if os.geteuid() != 0:
            cmd.insert(0, 'sudo')
        
        # Tentar diferentes drivers
        drivers = ['raw', 'drv:///generic.drv/generic.ppd', 'textonly.ppd']
        
        success = False
        for driver in drivers:
            try:
                current_cmd = cmd + ['-m', driver]
                result = subprocess.run(current_cmd, capture_output=True, text=True, timeout=30)
                
                if result.returncode == 0:
                    logger.info(f"Impressora '{name}' instalada com sucesso usando driver: {driver}")
                    success = True
                    break
            except subprocess.TimeoutExpired:
                continue
            except Exception as e:
                logger.warning(f"Erro ao instalar com driver {driver}: {e}")
                continue
        
        if not success:
            logger.error("Não foi possível instalar a impressora com nenhum driver disponível.")
            return False
        
        # Configurações adicionais
        try:
            if comment:
                cmd_comment = ['lpadmin', '-p', name, '-D', comment]
                if os.geteuid() != 0:
                    cmd_comment.insert(0, 'sudo')
                subprocess.run(cmd_comment, capture_output=True, timeout=10)
        except Exception as e:
            logger.warning(f"Erro ao aplicar configurações adicionais: {e}")
        
        return True
    
    def remove_printer(self, name):
        """Remove impressora no Unix"""
        if not self.cups_available:
            return False
        
        cmd = ['lpadmin', '-x', name]
        if os.geteuid() != 0:
            cmd.insert(0, 'sudo')
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                logger.info(f"Impressora '{name}' removida com sucesso.")
                return True
            return False
        except Exception as e:
            logger.error(f"Erro ao remover impressora: {e}")
            return False
    
    def remove_port(self, port_name):
        """No Unix/CUPS, as portas são gerenciadas automaticamente"""
        pass
    
    def check_printer_exists(self, name):
        """Verifica se impressora existe no Unix"""
        try:
            result = subprocess.run(['lpstat', '-p', name], capture_output=True, timeout=5)
            return result.returncode == 0
        except:
            return False
    
    def check_port_exists(self, port_name):
        """No Unix/CUPS, não é necessário verificar portas separadamente"""
        return True

class VirtualPrinterInstaller:
    """Instalador da impressora virtual cross-platform"""
    
    PRINTER_NAME = "Impressora LoQQuei"
    
    def __init__(self, config):
        """
        Inicializa o instalador
        
        Args:
            config: Configuração da aplicação
        """
        self.config = config
        self.system = platform.system()
        self.printer_manager = self._init_printer_manager()
        self.server_info = None
    
    def _init_printer_manager(self):
        """Inicializa o gerenciador de impressoras baseado no sistema"""
        if self.system == 'Windows':
            return WindowsPrinterManager()
        else:  # Linux ou macOS
            return UnixPrinterManager()
    
    def install_with_server_info(self, server_info):
        """
        Instala a impressora virtual com informações do servidor
        
        Args:
            server_info: Dicionário com ip e port do servidor
            
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        self.server_info = server_info
        
        try:
            if self.is_installed():
                logger.info("Impressora virtual já está instalada, reinstalando...")
                self.uninstall()
            
            ip = server_info['ip']
            port = server_info['port']
            
            comment = f'Impressora virtual PDF que salva automaticamente em {self.config.pdf_dir}'
            
            success = self.printer_manager.add_printer(
                self.PRINTER_NAME, ip, port,
                None, False, comment
            )
            
            if success:
                logger.info(f"Impressora virtual '{self.PRINTER_NAME}' instalada com sucesso!")
                return True
            else:
                logger.error("Falha ao instalar a impressora virtual")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao instalar impressora virtual: {str(e)}")
            return False
    
    def reinstall(self):
        """
        Reinstala a impressora virtual
        
        Returns:
            bool: True se a reinstalação foi bem-sucedida
        """
        if not self.server_info:
            logger.error("Informações do servidor não disponíveis para reinstalação")
            return False
        
        logger.info("Reinstalando impressora virtual...")
        self.uninstall()
        return self.install_with_server_info(self.server_info)
    
    def install(self):
        """
        Instala a impressora virtual (método legado)
        
        Returns:
            bool: True se a instalação foi bem-sucedida
        """
        logger.warning("Método install() é legado. Use install_with_server_info() em vez disso.")
        return False
    
    def uninstall(self):
        """
        Remove a impressora virtual
        
        Returns:
            bool: True se a remoção foi bem-sucedida
        """
        logger.info(f"Removendo impressora virtual")
        
        if not self.is_installed():
            logger.info("Impressora virtual não está instalada")
            return True
        
        try:
            success = self.printer_manager.remove_printer(self.PRINTER_NAME)
            if success:
                logger.info("Impressora virtual removida com sucesso")
            return success
        except Exception as e:
            logger.error(f"Erro ao remover impressora virtual: {str(e)}")
            return False
    
    def is_installed(self):
        """
        Verifica se a impressora virtual está instalada
        
        Returns:
            bool: True se a impressora está instalada
        """
        try:
            return self.printer_manager.check_printer_exists(self.PRINTER_NAME)
        except Exception as e:
            logger.error(f"Erro ao verificar instalação da impressora virtual: {str(e)}")
            return False
    
    def _is_admin(self):
        """
        Verifica se o aplicativo está sendo executado como administrador/root
        
        Returns:
            bool: True se o aplicativo está sendo executado com privilégios elevados
        """
        try:
            if self.system == "Windows":
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception:
            return False
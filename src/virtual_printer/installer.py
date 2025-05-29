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
import time
from pathlib import Path
from src.utils.subprocess_utils import run_hidden, popen_hidden, check_output_hidden

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
        self._debug_environment()
    
    def _debug_environment(self):
        """Debug do ambiente Windows"""
        logger.debug(f"Sistema operacional: {platform.system()} {platform.release()}")
        logger.debug(f"Versão do Windows: {platform.version()}")
        logger.debug(f"Arquitetura: {platform.machine()}")
        logger.debug(f"Usuário: {os.environ.get('USERNAME', 'Unknown')}")
        logger.debug(f"É admin: {self._is_admin()}")
    
    def _is_admin(self):
        """Verifica se está rodando como administrador"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    
    def _find_available_driver(self):
        """Encontra um driver disponível"""
        try:
            # Método 1: PowerShell
            result = run_hidden([
                'powershell', '-command',
                'Get-PrinterDriver | Select-Object Name | Format-Table -HideTableHeaders'
            ], timeout=10)
            
            if result.returncode == 0:
                available_drivers = [line.strip() for line in result.stdout.splitlines() if line.strip()]
                
                for driver in self.postscript_printer_drivers:
                    if driver in available_drivers:
                        logger.info(f"Driver encontrado: {driver}")
                        return driver
                
                if available_drivers:
                    logger.info(f"Usando primeiro driver disponível: {available_drivers[0]}")
                    return available_drivers[0]
        except Exception as e:
            logger.warning(f"Erro ao listar drivers via PowerShell: {e}")
        
        # Método 2: wmic
        try:
            result = run_hidden([
                'wmic', 'path', 'Win32_PrinterDriver', 'get', 'Name'
            ], timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    for line in lines[1:]:  # Pula o cabeçalho
                        driver_info = line.strip()
                        if driver_info:
                            # wmic retorna no formato "Nome,Versão,Ambiente"
                            driver_name = driver_info.split(',')[0].strip()
                            for known_driver in self.postscript_printer_drivers:
                                if known_driver in driver_name:
                                    logger.info(f"Driver encontrado via wmic: {known_driver}")
                                    return known_driver
        except Exception as e:
            logger.warning(f"Erro ao listar drivers via wmic: {e}")
        
        # Fallback
        logger.warning("Nenhum driver específico encontrado, usando Microsoft Print To PDF")
        return 'Microsoft Print To PDF'
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Windows"""
        if printer_port_name is None:
            printer_port_name = f"IP_{ip}:{port}"
        
        logger.info(f"Instalando impressora: {name}")
        logger.info(f"Driver: {self.default_driver}")
        logger.info(f"Porta: {printer_port_name}")
        logger.info(f"IP: {ip}:{port}")
        
        # Criar porta usando diferentes métodos
        port_created = self._create_port(printer_port_name, ip, port)
        
        if not port_created:
            logger.error("Falha ao criar porta de impressora")
            return False
        
        # Aguardar um pouco para a porta ser registrada
        time.sleep(2)
        
        # Criar impressora usando diferentes métodos
        printer_created = self._create_printer(name, printer_port_name)
        
        if printer_created:
            logger.info(f"Impressora '{name}' instalada com sucesso!")
            
            # Aguardar um pouco para a impressora ser registrada
            time.sleep(2)
            
            # Definir comentário se fornecido
            if comment:
                self._set_printer_comment(name, comment)
            
            return True
        else:
            logger.error("Falha ao criar impressora")
            # Tentar remover a porta criada
            self.remove_port(printer_port_name)
            return False
    
    def _create_port(self, port_name, ip, port):
        """Cria uma porta de impressora TCP/IP"""
        # Método 1: PowerShell (Windows 8+)
        try:
            cmd = [
                'powershell', '-command',
                f'Add-PrinterPort -Name "{port_name}" -PrinterHostAddress "{ip}" -PortNumber {port} -ErrorAction Stop'
            ]
            
            result = run_hidden(cmd, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Porta criada via PowerShell: {port_name}")
                return True
            else:
                logger.warning(f"PowerShell Add-PrinterPort falhou: {result.stderr}")
        except Exception as e:
            logger.warning(f"Erro ao criar porta via PowerShell: {e}")
        
        # Método 2: cscript prnport.vbs
        try:
            # Tentar diferentes localizações do script
            script_paths = [
                r'C:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
                r'C:\Windows\System32\Printing_Admin_Scripts\pt-BR\prnport.vbs',
                r'C:\Windows\System32\prnport.vbs'
            ]
            
            script_path = None
            for path in script_paths:
                if os.path.exists(path):
                    script_path = path
                    break
            
            if script_path:
                cmd = [
                    'cscript', script_path,
                    '-a', '-r', port_name, '-h', ip, '-o', 'raw', '-n', str(port)
                ]
                
                result = run_hidden(cmd, timeout=30)
                
                if result.returncode == 0 or 'already exists' in result.stdout.lower():
                    logger.info(f"Porta criada via prnport.vbs: {port_name}")
                    return True
                else:
                    logger.warning(f"prnport.vbs falhou: {result.stderr}")
            else:
                logger.warning("Script prnport.vbs não encontrado")
        except Exception as e:
            logger.warning(f"Erro ao criar porta via prnport.vbs: {e}")
        
        # Método 3: Comando TCP/IP direto (fallback)
        try:
            # Criar registro diretamente
            import winreg
            
            port_key = rf"SYSTEM\CurrentControlSet\Control\Print\Monitors\Standard TCP/IP Port\Ports\{port_name}"
            
            with winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, port_key) as key:
                winreg.SetValueEx(key, "Protocol", 0, winreg.REG_DWORD, 1)  # RAW
                winreg.SetValueEx(key, "Version", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key, "HostName", 0, winreg.REG_SZ, ip)
                winreg.SetValueEx(key, "IPAddress", 0, winreg.REG_SZ, ip)
                winreg.SetValueEx(key, "PortNumber", 0, winreg.REG_DWORD, int(port))
                winreg.SetValueEx(key, "SNMP Community", 0, winreg.REG_SZ, "public")
                winreg.SetValueEx(key, "SNMP Enabled", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key, "SNMP Index", 0, winreg.REG_DWORD, 1)
            
            logger.info(f"Porta criada via registro: {port_name}")
            
            # Reiniciar o spooler para aplicar mudanças
            self._restart_spooler()
            
            return True
        except Exception as e:
            logger.warning(f"Erro ao criar porta via registro: {e}")
        
        return False
    
    def _create_printer(self, name, port_name):
        """Cria a impressora usando diferentes métodos"""
        # Método 1: PowerShell (Windows 8+)
        try:
            cmd = [
                'powershell', '-command',
                f'Add-Printer -Name "{name}" -DriverName "{self.default_driver}" -PortName "{port_name}" -ErrorAction Stop'
            ]
            
            result = run_hidden(cmd, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Impressora criada via PowerShell: {name}")
                return True
            else:
                logger.warning(f"PowerShell Add-Printer falhou: {result.stderr}")
        except Exception as e:
            logger.warning(f"Erro ao criar impressora via PowerShell: {e}")
        
        # Método 2: rundll32 printui.dll
        try:
            cmd = [
                'rundll32', 'printui.dll,PrintUIEntry',
                '/if', '/b', name, '/r', port_name, '/m', self.default_driver
            ]
            
            result = run_hidden(cmd, timeout=30)
            
            # rundll32 não retorna códigos de erro confiáveis, verificar se foi criada
            time.sleep(2)
            if self.check_printer_exists(name):
                logger.info(f"Impressora criada via rundll32: {name}")
                return True
            else:
                logger.warning("rundll32 printui.dll executado mas impressora não foi criada")
        except Exception as e:
            logger.warning(f"Erro ao criar impressora via rundll32: {e}")
        
        # Método 3: cscript prnmngr.vbs
        try:
            script_paths = [
                r'C:\Windows\System32\Printing_Admin_Scripts\en-US\prnmngr.vbs',
                r'C:\Windows\System32\Printing_Admin_Scripts\pt-BR\prnmngr.vbs',
                r'C:\Windows\System32\prnmngr.vbs'
            ]
            
            script_path = None
            for path in script_paths:
                if os.path.exists(path):
                    script_path = path
                    break
            
            if script_path:
                cmd = [
                    'cscript', script_path,
                    '-a', '-p', name, '-m', self.default_driver, '-r', port_name
                ]
                
                result = run_hidden(cmd, timeout=30)
                
                if result.returncode == 0 or 'added printer' in result.stdout.lower():
                    logger.info(f"Impressora criada via prnmngr.vbs: {name}")
                    return True
                else:
                    logger.warning(f"prnmngr.vbs falhou: {result.stderr}")
        except Exception as e:
            logger.warning(f"Erro ao criar impressora via prnmngr.vbs: {e}")
        
        return False
    
    def _restart_spooler(self):
        """Reinicia o serviço de spooler"""
        try:
            run_hidden(['net', 'stop', 'spooler'], timeout=10)
            time.sleep(1)
            run_hidden(['net', 'start', 'spooler'], timeout=10)
            time.sleep(2)
            logger.info("Serviço de spooler reiniciado")
        except Exception as e:
            logger.warning(f"Erro ao reiniciar spooler: {e}")
    
    def _set_printer_comment(self, name, comment):
        """Adiciona um comentário à impressora"""
        try:
            # PowerShell
            comment_escaped = comment.replace('"', '`"').replace('\n', ' ')
            cmd = [
                'powershell', '-command',
                f'Set-Printer -Name "{name}" -Comment "{comment_escaped}"'
            ]
            run_hidden(cmd, timeout=10)
        except:
            pass
        
        try:
            # rundll32 como fallback
            comment_escaped = comment.replace('"', '\\"').replace('\n', ' ')
            cmd = [
                'rundll32', 'printui.dll,PrintUIEntry',
                '/Xs', '/n', name, 'comment', comment_escaped
            ]
            run_hidden(cmd, timeout=10)
        except:
            pass
    
    def remove_printer(self, name):
        """Remove impressora no Windows"""
        success = False
        
        # Método 1: PowerShell
        try:
            cmd = ['powershell', '-command', f'Remove-Printer -Name "{name}" -ErrorAction Stop']
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                success = True
                logger.info(f"Impressora removida via PowerShell: {name}")
        except:
            pass
        
        # Método 2: rundll32
        if not success:
            try:
                cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/dl', '/n', name]
                run_hidden(cmd, timeout=10)
                time.sleep(1)
                if not self.check_printer_exists(name):
                    success = True
                    logger.info(f"Impressora removida via rundll32: {name}")
            except:
                pass
        
        return success
    
    def remove_port(self, port_name):
        """Remove porta no Windows"""
        # Método 1: PowerShell
        try:
            cmd = ['powershell', '-command', f'Remove-PrinterPort -Name "{port_name}" -ErrorAction SilentlyContinue']
            run_hidden(cmd, timeout=10)
        except:
            pass
        
        # Método 2: prnport.vbs
        try:
            script_paths = [
                r'C:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
                r'C:\Windows\System32\Printing_Admin_Scripts\pt-BR\prnport.vbs'
            ]
            
            for script_path in script_paths:
                if os.path.exists(script_path):
                    cmd = ['cscript', script_path, '-d', '-r', port_name]
                    run_hidden(cmd, timeout=10)
                    break
        except:
            pass
    
    def check_printer_exists(self, name):
        """Verifica se impressora existe no Windows"""
        # Método 1: PowerShell
        try:
            cmd = [
                'powershell', '-command',
                f'$p = Get-Printer -Name "{name}" -ErrorAction SilentlyContinue; if ($p) {{ "True" }} else {{ "False" }}'
            ]
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip().lower() == "true"
        except Exception as e:
            logger.debug(f"Erro ao verificar via PowerShell: {e}")
        
        # Método 2: wmic
        try:
            cmd = ['wmic', 'printer', 'where', f'name="{name}"', 'get', 'name']
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                return name in result.stdout
        except Exception as e:
            logger.debug(f"Erro ao verificar via wmic: {e}")
        
        # Método 3: Listar todas as impressoras
        try:
            # PowerShell list
            cmd = ['powershell', '-command', 'Get-Printer | Select-Object -ExpandProperty Name']
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                printers = [p.strip() for p in result.stdout.splitlines() if p.strip()]
                return name in printers
        except:
            pass
        
        try:
            # wmic list
            cmd = ['wmic', 'printer', 'get', 'name']
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) > 1:
                    printers = [line.strip() for line in lines[1:] if line.strip()]
                    return name in printers
        except:
            pass
        
        return False
    
    def check_port_exists(self, port_name):
        """Verifica se porta existe no Windows"""
        # Método 1: PowerShell
        try:
            cmd = [
                'powershell', '-command',
                f'$p = Get-PrinterPort -Name "{port_name}" -ErrorAction SilentlyContinue; if ($p) {{ "True" }} else {{ "False" }}'
            ]
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip().lower() == "true"
        except:
            pass
        
        # Método 2: Verificar no registro
        try:
            import winreg
            port_key = rf"SYSTEM\CurrentControlSet\Control\Print\Monitors\Standard TCP/IP Port\Ports\{port_name}"
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, port_key):
                return True
        except:
            pass
        
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
            result = run_hidden(['which', 'lpadmin'])
            if result.returncode != 0:
                return False
            
            result = run_hidden(['which', 'lpstat'])
            if result.returncode != 0:
                return False
            
            try:
                result = run_hidden(['lpstat', '-r'], timeout=5)
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
                result = run_hidden(cmd, timeout=100)
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
                result = run_hidden(current_cmd, timeout=30)
                
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
                run_hidden(cmd_comment, timeout=10)
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
            result = run_hidden(cmd, timeout=15)
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
            result = run_hidden(['lpstat', '-p', name], timeout=5)
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
            # Verificar se já existe antes de tentar remover
            if self.is_installed():
                logger.info("Impressora virtual já está instalada, reinstalando...")
                self.uninstall()
                time.sleep(2)  # Aguardar um pouco após remover
            
            ip = server_info['ip']
            port = server_info['port']
            
            comment = f'Impressora virtual PDF que salva automaticamente em {self.config.pdf_dir}'
            
            logger.info(f"Iniciando instalação da impressora virtual...")
            logger.info(f"Nome: {self.PRINTER_NAME}")
            logger.info(f"Servidor: {ip}:{port}")
            
            success = self.printer_manager.add_printer(
                self.PRINTER_NAME, ip, port,
                None, False, comment
            )
            
            if success:
                # Verificar se realmente foi instalada
                time.sleep(2)  # Aguardar um pouco para o sistema processar
                if self.is_installed():
                    logger.info(f"Impressora virtual '{self.PRINTER_NAME}' instalada e verificada com sucesso!")
                    return True
                else:
                    logger.error("Impressora foi instalada mas não é detectável pelo sistema")
                    return False
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
        time.sleep(2)  # Aguardar entre desinstalar e reinstalar
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
                # Remover porta associada se existir
                if self.server_info:
                    port_name = f"IP_{self.server_info['ip']}:{self.server_info['port']}"
                    self.printer_manager.remove_port(port_name)
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
            exists = self.printer_manager.check_printer_exists(self.PRINTER_NAME)
            logger.debug(f"Verificação de instalação: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Erro ao verificar instalação da impressora")
            return False
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Instalador da impressora virtual cross-platform com suporte multi-usuário
Versão corrigida com melhor suporte para macOS, Windows 7+ e Linux
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
    """Gerenciador de impressoras para Windows com suporte multi-usuário"""
    
    def __init__(self):
        self.windows_version = self._get_windows_version()
        self.postscript_printer_drivers = [
            'Microsoft Print To PDF',
            'Microsoft XPS Document Writer',
            'HP Universal Printing PS',
            'HP Color LaserJet 2800 Series PS',
            'Generic / Text Only'
        ]
        self.default_driver = self._find_available_driver()
        self._debug_environment()
    
    def _get_windows_version(self):
        """Obtém a versão do Windows"""
        try:
            version = platform.version()
            release = platform.release()
            
            # Detecta versões específicas
            if release == "7":
                return "7"
            elif release == "8":
                return "8"
            elif release == "8.1":
                return "8.1"
            elif release == "10":
                return "10"
            elif release == "11":
                return "11"
            else:
                # Fallback baseado na versão
                if version.startswith("6.1"):
                    return "7"
                elif version.startswith("6.2"):
                    return "8"
                elif version.startswith("6.3"):
                    return "8.1"
                elif version.startswith("10."):
                    return "10"
                else:
                    return "unknown"
        except:
            return "unknown"
    
    def _debug_environment(self):
        """Debug do ambiente Windows com informações multi-usuário"""
        logger.debug(f"Sistema operacional: {platform.system()} {platform.release()}")
        logger.debug(f"Versão do Windows: {self.windows_version}")
        logger.debug(f"Versão completa: {platform.version()}")
        logger.debug(f"Arquitetura: {platform.machine()}")
        logger.debug(f"Usuário: {os.environ.get('USERNAME', 'Unknown')}")
        logger.debug(f"É admin: {self._is_admin()}")
        
        # Detectar tipo de Windows
        try:
            result = run_hidden(['wmic', 'os', 'get', 'ProductType'], timeout=5)
            if result.returncode == 0:
                if 'Server' in result.stdout:
                    logger.info("Detectado Windows Server - modo multi-usuário otimizado")
                else:
                    logger.info("Detectado Windows Desktop")
        except:
            pass
        
        # Verificar PowerShell disponível
        self._check_powershell_availability()
        
        # Verificar sessões de usuário ativas (apenas em servidores)
        try:
            result = run_hidden(['query', 'user'], timeout=5)
            if result.returncode == 0:
                logger.debug("Sessões de usuário ativas:")
                logger.debug(result.stdout)
        except:
            pass
    
    def _check_powershell_availability(self):
        """Verifica se PowerShell está disponível e qual versão"""
        try:
            # Tenta PowerShell 5.1+ primeiro
            result = run_hidden(['powershell', '-command', '$PSVersionTable.PSVersion.Major'], timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"PowerShell disponível - versão: {version}")
                return True
        except:
            pass
        
        try:
            # Tenta PowerShell Core (pwsh)
            result = run_hidden(['pwsh', '-command', '$PSVersionTable.PSVersion.Major'], timeout=5)
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info(f"PowerShell Core disponível - versão: {version}")
                return True
        except:
            pass
        
        logger.warning("PowerShell não encontrado - usando métodos alternativos")
        return False
    
    def _is_admin(self):
        """Verifica se está rodando como administrador"""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except:
            return False
    
    def _find_available_driver(self):
        """Encontra um driver disponível com melhor compatibilidade"""
        # Para Windows 7, usa métodos mais simples
        if self.windows_version == "7":
            return self._find_driver_windows7()
        else:
            return self._find_driver_modern_windows()
    
    def _find_driver_windows7(self):
        """Encontra driver no Windows 7 usando métodos compatíveis"""
        try:
            # Método 1: wmic (mais compatível com Windows 7)
            result = run_hidden([
                'wmic', 'path', 'Win32_PrinterDriver', 'get', 'Name'
            ], timeout=15)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                available_drivers = []
                
                for line in lines[1:]:  # Pula o cabeçalho
                    driver_info = line.strip()
                    if driver_info:
                        # wmic pode retornar formato complexo, extrair nome
                        driver_name = driver_info.split(',')[0].strip()
                        available_drivers.append(driver_name)
                
                # Procura por drivers conhecidos
                for driver in self.postscript_printer_drivers:
                    for available in available_drivers:
                        if driver.lower() in available.lower():
                            logger.info(f"Driver encontrado no Windows 7: {driver}")
                            return driver
                
                # Se não encontrou nenhum conhecido, usa o primeiro disponível
                if available_drivers:
                    for driver in available_drivers:
                        if driver and len(driver) > 3:
                            logger.info(f"Usando driver disponível no Windows 7: {driver}")
                            return driver
        except Exception as e:
            logger.warning(f"Erro ao listar drivers no Windows 7: {e}")
        
        # Fallback para Windows 7
        logger.info("Usando driver padrão para Windows 7: Generic / Text Only")
        return 'Generic / Text Only'
    
    def _find_driver_modern_windows(self):
        """Encontra driver no Windows 8+ usando PowerShell"""
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
        
        # Fallback para wmic
        return self._find_driver_windows7()
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Windows com configuração multi-usuário"""
        if printer_port_name is None:
            printer_port_name = f"IP_{ip}:{port}"
        
        logger.info(f"Instalando impressora: {name}")
        logger.info(f"Driver: {self.default_driver}")
        logger.info(f"Porta: {printer_port_name}")
        logger.info(f"IP: {ip}:{port}")
        logger.info(f"Versão do Windows: {self.windows_version}")
        
        # Para Windows Server, verificar se precisa configurar para todos os usuários
        is_server = self._is_windows_server()
        if is_server:
            logger.info("Configurando impressora para ambiente Windows Server (multi-usuário)")
        
        # Criar porta usando diferentes métodos
        port_created = self._create_port(printer_port_name, ip, port)
        
        if not port_created:
            logger.error("Falha ao criar porta de impressora")
            return False
        
        # Aguardar um pouco para a porta ser registrada
        time.sleep(2)
        
        # Criar impressora usando diferentes métodos
        printer_created = self._create_printer(name, printer_port_name, is_server)
        
        if printer_created:
            logger.info(f"Impressora '{name}' instalada com sucesso!")
            
            # Aguardar um pouco para a impressora ser registrada
            time.sleep(2)
            
            # Definir comentário se fornecido
            if comment:
                # Adicionar informação sobre multi-usuário ao comentário
                if is_server:
                    comment += " (Configurado para multi-usuário)"
                self._set_printer_comment(name, comment)
            
            # Configurar permissões para todos os usuários em servidores
            if is_server:
                self._configure_multiuser_permissions(name)
            
            return True
        else:
            logger.error("Falha ao criar impressora")
            # Tentar remover a porta criada
            self.remove_port(printer_port_name)
            return False
    
    def _is_windows_server(self):
        """Verifica se está rodando em Windows Server"""
        try:
            result = run_hidden(['wmic', 'os', 'get', 'ProductType'], timeout=5)
            if result.returncode == 0:
                return 'Server' in result.stdout
        except:
            pass
        return False
    
    def _configure_multiuser_permissions(self, printer_name):
        """Configura permissões da impressora para todos os usuários"""
        try:
            # Tentar dar permissão para o grupo "Everyone" usando PowerShell
            logger.info("Configurando permissões multi-usuário...")
            
            # Método 1: PowerShell com Set-Printer (Windows 8+)
            if self.windows_version not in ["7"]:
                try:
                    cmd = [
                        'powershell', '-command',
                        f'$printer = Get-Printer -Name "{printer_name}"; '
                        f'$printer.PermissionSDDL = $null; '
                        f'Set-Printer -InputObject $printer'
                    ]
                    run_hidden(cmd, timeout=15)
                    logger.info("Permissões configuradas via PowerShell")
                except Exception as e:
                    logger.debug(f"Erro na configuração via PowerShell: {e}")
            
            # Método 2: Usar rundll32 para configurar permissões (compatível com Windows 7)
            try:
                cmd = [
                    'rundll32', 'printui.dll,PrintUIEntry',
                    '/Xs', '/n', printer_name, 'attributes', '+shared'
                ]
                run_hidden(cmd, timeout=15)
                logger.info("Impressora configurada como compartilhada")
            except Exception as e:
                logger.debug(f"Erro na configuração de compartilhamento: {e}")
            
        except Exception as e:
            logger.warning(f"Erro ao configurar permissões multi-usuário: {e}")
    
    def _create_port(self, port_name, ip, port):
        """Cria uma porta de impressora TCP/IP"""
        # Para Windows 7, usar métodos mais compatíveis primeiro
        if self.windows_version == "7":
            return self._create_port_windows7(port_name, ip, port)
        else:
            return self._create_port_modern_windows(port_name, ip, port)
    
    def _create_port_windows7(self, port_name, ip, port):
        """Cria porta no Windows 7 usando métodos compatíveis"""
        # Método 1: cscript prnport.vbs (mais compatível)
        try:
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
                    logger.info(f"Porta criada via prnport.vbs no Windows 7: {port_name}")
                    return True
                else:
                    logger.warning(f"prnport.vbs falhou no Windows 7: {result.stderr}")
        except Exception as e:
            logger.warning(f"Erro ao criar porta via prnport.vbs no Windows 7: {e}")
        
        # Método 2: Registro direto (fallback para Windows 7)
        return self._create_port_registry(port_name, ip, port)
    
    def _create_port_modern_windows(self, port_name, ip, port):
        """Cria porta no Windows 8+ usando PowerShell"""
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
        
        # Fallback para métodos do Windows 7
        return self._create_port_windows7(port_name, ip, port)
    
    def _create_port_registry(self, port_name, ip, port):
        """Cria porta diretamente no registro (método universal)"""
        try:
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
    
    def _create_printer(self, name, port_name, is_server=False):
        """Cria a impressora usando diferentes métodos"""
        # Para Windows 7, usar métodos mais compatíveis
        if self.windows_version == "7":
            return self._create_printer_windows7(name, port_name, is_server)
        else:
            return self._create_printer_modern_windows(name, port_name, is_server)
    
    def _create_printer_windows7(self, name, port_name, is_server=False):
        """Cria impressora no Windows 7"""
        # Método 1: rundll32 printui.dll (mais compatível com Windows 7)
        try:
            cmd = [
                'rundll32', 'printui.dll,PrintUIEntry',
                '/if', '/b', name, '/r', port_name, '/m', self.default_driver
            ]
            
            result = run_hidden(cmd, timeout=30)
            
            # rundll32 não retorna códigos de erro confiáveis, verificar se foi criada
            time.sleep(3)
            if self.check_printer_exists(name):
                logger.info(f"Impressora criada via rundll32 no Windows 7: {name}")
                return True
            else:
                logger.warning("rundll32 printui.dll executado mas impressora não foi criada no Windows 7")
        except Exception as e:
            logger.warning(f"Erro ao criar impressora via rundll32 no Windows 7: {e}")
        
        # Método 2: cscript prnmngr.vbs
        return self._create_printer_vbs(name, port_name)
    
    def _create_printer_modern_windows(self, name, port_name, is_server=False):
        """Cria impressora no Windows 8+"""
        # Método 1: PowerShell (Windows 8+)
        try:
            cmd = [
                'powershell', '-command',
                f'Add-Printer -Name "{name}" -DriverName "{self.default_driver}" -PortName "{port_name}" -ErrorAction Stop'
            ]
            
            # Para servidores, adicionar configurações específicas
            if is_server:
                cmd = [
                    'powershell', '-command',
                    f'Add-Printer -Name "{name}" -DriverName "{self.default_driver}" -PortName "{port_name}" -Shared $true -ErrorAction Stop'
                ]
            
            result = run_hidden(cmd, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"Impressora criada via PowerShell: {name}")
                return True
            else:
                logger.warning(f"PowerShell Add-Printer falhou: {result.stderr}")
        except Exception as e:
            logger.warning(f"Erro ao criar impressora via PowerShell: {e}")
        
        # Fallback para métodos do Windows 7
        return self._create_printer_windows7(name, port_name, is_server)
    
    def _create_printer_vbs(self, name, port_name):
        """Cria impressora usando cscript prnmngr.vbs"""
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
            time.sleep(2)
            run_hidden(['net', 'start', 'spooler'], timeout=10)
            time.sleep(3)
            logger.info("Serviço de spooler reiniciado")
        except Exception as e:
            logger.warning(f"Erro ao reiniciar spooler: {e}")
    
    def _set_printer_comment(self, name, comment):
        """Adiciona um comentário à impressora"""
        # PowerShell para Windows 8+
        if self.windows_version not in ["7"]:
            try:
                comment_escaped = comment.replace('"', '`"').replace('\n', ' ')
                cmd = [
                    'powershell', '-command',
                    f'Set-Printer -Name "{name}" -Comment "{comment_escaped}"'
                ]
                run_hidden(cmd, timeout=10)
                return
            except:
                pass
        
        # rundll32 como fallback (compatível com Windows 7)
        try:
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
        
        # PowerShell para Windows 8+
        if self.windows_version not in ["7"]:
            try:
                cmd = ['powershell', '-command', f'Remove-Printer -Name "{name}" -ErrorAction Stop']
                result = run_hidden(cmd, timeout=10)
                if result.returncode == 0:
                    success = True
                    logger.info(f"Impressora removida via PowerShell: {name}")
            except:
                pass
        
        # rundll32 (compatível com todas as versões)
        if not success:
            try:
                cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/dl', '/n', name]
                run_hidden(cmd, timeout=10)
                time.sleep(2)
                if not self.check_printer_exists(name):
                    success = True
                    logger.info(f"Impressora removida via rundll32: {name}")
            except:
                pass
        
        return success
    
    def remove_port(self, port_name):
        """Remove porta no Windows"""
        # PowerShell para Windows 8+
        if self.windows_version not in ["7"]:
            try:
                cmd = ['powershell', '-command', f'Remove-PrinterPort -Name "{port_name}" -ErrorAction SilentlyContinue']
                run_hidden(cmd, timeout=10)
            except:
                pass
        
        # prnport.vbs (compatível com todas as versões)
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
        # PowerShell para Windows 8+
        if self.windows_version not in ["7"]:
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
        
        # wmic (compatível com todas as versões)
        try:
            cmd = ['wmic', 'printer', 'where', f'name="{name}"', 'get', 'name']
            result = run_hidden(cmd, timeout=10)
            if result.returncode == 0:
                return name in result.stdout
        except Exception as e:
            logger.debug(f"Erro ao verificar via wmic: {e}")
        
        return False
    
    def check_port_exists(self, port_name):
        """Verifica se porta existe no Windows"""
        # PowerShell para Windows 8+
        if self.windows_version not in ["7"]:
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
        
        # Verificar no registro (compatível com todas as versões)
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
        self.system_version = self._get_system_version()
        self.architecture = self._get_architecture()
        self.cups_available = self._check_cups_availability()
        
        if not self.cups_available:
            self._install_cups_suggestions()
            # Tentar instalar CUPS automaticamente
            self._auto_install_cups()
    
    def _get_system_version(self):
        """Obtém versão específica do sistema"""
        try:
            if self.system == 'Darwin':  # macOS
                version = platform.mac_ver()[0]
                return version
            elif self.system == 'Linux':
                # Tentar identificar a distribuição
                try:
                    with open('/etc/os-release', 'r') as f:
                        lines = f.readlines()
                        for line in lines:
                            if line.startswith('PRETTY_NAME='):
                                return line.split('=', 1)[1].strip().strip('"')
                except:
                    pass
                return platform.release()
            else:
                return platform.release()
        except:
            return "unknown"
    
    def _get_architecture(self):
        """Detecta a arquitetura do sistema"""
        machine = platform.machine().lower()
        
        if self.system == 'Darwin':  # macOS
            if 'arm' in machine or 'aarch64' in machine:
                return 'apple_silicon'  # Apple Silicon (M1, M2, etc.)
            else:
                return 'intel'  # Intel Mac
        elif 'x86_64' in machine or 'amd64' in machine:
            return 'x86_64'
        elif 'i386' in machine or 'i686' in machine:
            return 'x86'
        elif 'arm' in machine or 'aarch64' in machine:
            return 'arm64'
        else:
            return machine
    
    def _check_cups_availability(self):
        """Verifica se CUPS está instalado e acessível"""
        try:
            # Verificar comandos básicos
            commands_to_check = ['lpadmin', 'lpstat', 'lp']
            
            for cmd in commands_to_check:
                try:
                    if self.system == 'Darwin':
                        result = run_hidden(['which', cmd], timeout=5)
                    else:
                        result = run_hidden(['which', cmd], timeout=5)
                    
                    if result.returncode != 0:
                        logger.warning(f"Comando {cmd} não encontrado")
                        return False
                except:
                    logger.warning(f"Erro ao verificar comando {cmd}")
                    return False
            
            # Verificar se o serviço CUPS está rodando
            try:
                result = run_hidden(['lpstat', '-r'], timeout=5)
                if "not ready" in result.stdout.lower() or result.returncode != 0:
                    logger.info("CUPS não está rodando, tentando iniciar...")
                    if not self._start_cups_service():
                        return False
            except subprocess.TimeoutExpired:
                logger.warning("Timeout ao verificar status do CUPS")
                return False
            except Exception as e:
                logger.warning(f"Erro ao verificar CUPS: {e}")
                return False
            
            logger.info("CUPS está disponível e funcionando")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao verificar CUPS: {e}")
            return False
    
    def _start_cups_service(self):
        """Tenta iniciar o serviço CUPS"""
        logger.info("Tentando iniciar o serviço CUPS...")
        
        if self.system == 'Darwin':  # macOS
            service_commands = [
                # macOS moderno (launchctl)
                ['sudo', 'launchctl', 'load', '-w', '/System/Library/LaunchDaemons/org.cups.cupsd.plist'],
                ['sudo', 'launchctl', 'start', 'org.cups.cupsd'],
                # Homebrew
                ['sudo', 'brew', 'services', 'start', 'cups'],
                # Comando direto
                ['sudo', 'cupsd'],
            ]
        elif self.system == 'Linux':
            service_commands = [
                # systemd (distribuições modernas)
                ['sudo', 'systemctl', 'start', 'cups'],
                ['sudo', 'systemctl', 'enable', 'cups'],
                # SysV init
                ['sudo', 'service', 'cups', 'start'],
                ['sudo', '/etc/init.d/cups', 'start'],
                # Comando direto
                ['sudo', 'cupsd'],
            ]
        else:
            service_commands = []
        
        for cmd in service_commands:
            try:
                logger.debug(f"Tentando comando: {' '.join(cmd)}")
                result = run_hidden(cmd, timeout=15)
                if result.returncode == 0:
                    logger.info(f"Serviço CUPS iniciado com sucesso usando: {' '.join(cmd)}")
                    # Aguardar um pouco para o serviço inicializar
                    time.sleep(3)
                    # Verificar se realmente está funcionando
                    try:
                        test_result = run_hidden(['lpstat', '-r'], timeout=5)
                        if test_result.returncode == 0 and "not ready" not in test_result.stdout.lower():
                            return True
                    except:
                        pass
            except (subprocess.TimeoutExpired, FileNotFoundError) as e:
                logger.debug(f"Comando falhou: {e}")
                continue
            except Exception as e:
                logger.debug(f"Erro inesperado: {e}")
                continue
        
        logger.warning("Não foi possível iniciar o serviço CUPS automaticamente")
        return False
    
    def _auto_install_cups(self):
        """Tenta instalar CUPS automaticamente"""
        if self.cups_available:
            return True
        
        logger.info("Tentando instalar CUPS automaticamente...")
        
        if self.system == 'Darwin':  # macOS
            # No macOS, CUPS geralmente está pré-instalado
            logger.info("No macOS, CUPS deveria estar pré-instalado. Verificando Homebrew...")
            install_commands = [
                ['brew', 'install', 'cups'],
            ]
        elif self.system == 'Linux':
            # Detectar gerenciador de pacotes
            install_commands = []
            
            # Debian/Ubuntu (apt)
            if os.path.exists('/usr/bin/apt-get') or os.path.exists('/usr/bin/apt'):
                install_commands.extend([
                    ['sudo', 'apt-get', 'update'],
                    ['sudo', 'apt-get', 'install', '-y', 'cups', 'cups-client'],
                ])
            
            # Red Hat/CentOS/Fedora (yum/dnf)
            elif os.path.exists('/usr/bin/yum'):
                install_commands.append(['sudo', 'yum', 'install', '-y', 'cups'])
            elif os.path.exists('/usr/bin/dnf'):
                install_commands.append(['sudo', 'dnf', 'install', '-y', 'cups'])
            
            # Arch Linux (pacman)
            elif os.path.exists('/usr/bin/pacman'):
                install_commands.append(['sudo', 'pacman', '-S', '--noconfirm', 'cups'])
            
            # openSUSE (zypper)
            elif os.path.exists('/usr/bin/zypper'):
                install_commands.append(['sudo', 'zypper', 'install', '-y', 'cups'])
        
        for cmd in install_commands:
            try:
                logger.info(f"Executando: {' '.join(cmd)}")
                result = run_hidden(cmd, timeout=120)  # Timeout maior para instalação
                if result.returncode == 0:
                    logger.info("Comando de instalação executado com sucesso")
                else:
                    logger.warning(f"Comando falhou com código {result.returncode}")
            except Exception as e:
                logger.warning(f"Erro ao executar comando de instalação: {e}")
        
        # Verificar se a instalação foi bem-sucedida
        time.sleep(2)
        self.cups_available = self._check_cups_availability()
        return self.cups_available
    
    def _install_cups_suggestions(self):
        """Fornece sugestões para instalar CUPS"""
        logger.warning(f"CUPS não encontrado no sistema {self.system}")
        
        if self.system == 'Darwin':  # macOS
            logger.info("No macOS, CUPS deveria estar pré-instalado.")
            logger.info("Se não estiver funcionando, tente:")
            logger.info("1. sudo launchctl load -w /System/Library/LaunchDaemons/org.cups.cupsd.plist")
            logger.info("2. brew install cups (se você usa Homebrew)")
        elif self.system == 'Linux':
            logger.info("Para instalar CUPS no Linux:")
            logger.info("Ubuntu/Debian: sudo apt-get install cups cups-client")
            logger.info("Red Hat/CentOS: sudo yum install cups")
            logger.info("Fedora: sudo dnf install cups")
            logger.info("Arch Linux: sudo pacman -S cups")
            logger.info("openSUSE: sudo zypper install cups")
    
    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Unix usando CUPS"""
        if not self.cups_available:
            logger.error("CUPS não está disponível. Não é possível adicionar impressora.")
            return False

        device_uri = f"socket://{ip}:{port}"
        
        logger.info(f"Instalando impressora: {name}")
        logger.info(f"Sistema: {self.system} {self.system_version}")
        logger.info(f"Arquitetura: {self.architecture}")
        logger.info(f"URI do dispositivo: {device_uri}")
        
        # Verificar se precisa de sudo
        needs_sudo = os.geteuid() != 0 if hasattr(os, 'geteuid') else True
        
        cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri]
        
        if needs_sudo:
            cmd.insert(0, 'sudo')
        
        # Tentar diferentes drivers baseados no sistema
        if self.system == 'Darwin':  # macOS
            drivers = [
                'everywhere',  # Driver genérico moderno
                'raw',
                'textonly',
                'drv:///generic.drv/generic.ppd',
            ]
        else:  # Linux
            drivers = [
                'everywhere',  # Driver genérico moderno (CUPS 2.2+)
                'raw',
                'drv:///generic.drv/generic.ppd',
                'textonly.ppd',
                'lsb/usr/cups/generic-postscript-driver.ppd',
            ]
        
        success = False
        for driver in drivers:
            try:
                current_cmd = cmd + ['-m', driver]
                logger.debug(f"Tentando instalar com driver: {driver}")
                logger.debug(f"Comando: {' '.join(current_cmd)}")
                
                result = run_hidden(current_cmd, timeout=30)
                
                if result.returncode == 0:
                    logger.info(f"Impressora '{name}' instalada com sucesso usando driver: {driver}")
                    success = True
                    break
                else:
                    logger.debug(f"Driver {driver} falhou: {result.stderr}")
            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout ao instalar com driver {driver}")
                continue
            except Exception as e:
                logger.warning(f"Erro ao instalar com driver {driver}: {e}")
                continue
        
        if not success:
            logger.error("Não foi possível instalar a impressora com nenhum driver disponível.")
            return False
        
        # Aguardar um pouco para a impressora ser registrada
        time.sleep(2)
        
        # Configurações adicionais
        try:
            additional_cmds = []
            
            if comment:
                cmd_comment = ['lpadmin', '-p', name, '-D', comment]
                if needs_sudo:
                    cmd_comment.insert(0, 'sudo')
                additional_cmds.append(('comentário', cmd_comment))
            
            # Habilitar a impressora
            cmd_enable = ['cupsenable', name]
            if needs_sudo:
                cmd_enable.insert(0, 'sudo')
            additional_cmds.append(('habilitar', cmd_enable))
            
            # Aceitar trabalhos
            cmd_accept = ['cupsaccept', name]
            if needs_sudo:
                cmd_accept.insert(0, 'sudo')
            additional_cmds.append(('aceitar trabalhos', cmd_accept))
            
            for desc, cmd in additional_cmds:
                try:
                    result = run_hidden(cmd, timeout=10)
                    if result.returncode == 0:
                        logger.debug(f"Configuração '{desc}' aplicada com sucesso")
                    else:
                        logger.warning(f"Falha ao aplicar configuração '{desc}': {result.stderr}")
                except Exception as e:
                    logger.warning(f"Erro ao aplicar configuração '{desc}': {e}")
                    
        except Exception as e:
            logger.warning(f"Erro ao aplicar configurações adicionais: {e}")
        
        return True
    
    def remove_printer(self, name):
        """Remove impressora no Unix"""
        if not self.cups_available:
            return False
        
        needs_sudo = os.geteuid() != 0 if hasattr(os, 'geteuid') else True
        
        cmd = ['lpadmin', '-x', name]
        if needs_sudo:
            cmd.insert(0, 'sudo')
        
        try:
            result = run_hidden(cmd, timeout=15)
            if result.returncode == 0:
                logger.info(f"Impressora '{name}' removida com sucesso.")
                return True
            else:
                logger.warning(f"Falha ao remover impressora: {result.stderr}")
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
    """Instalador da impressora virtual cross-platform com suporte multi-usuário"""
    
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
        self.is_multiuser_env = self._detect_multiuser_environment()
    
    def _init_printer_manager(self):
        """Inicializa o gerenciador de impressoras baseado no sistema"""
        if self.system == 'Windows':
            return WindowsPrinterManager()
        else:  # Linux ou macOS
            return UnixPrinterManager()
    
    def _detect_multiuser_environment(self):
        """Detecta se está em um ambiente multi-usuário"""
        if self.system == 'Windows':
            try:
                # Verificar se é Windows Server
                result = run_hidden(['wmic', 'os', 'get', 'ProductType'], timeout=5)
                if result.returncode == 0 and 'Server' in result.stdout:
                    return True
                
                # Verificar se há múltiplas sessões ativas
                result = run_hidden(['query', 'user'], timeout=5)
                if result.returncode == 0:
                    lines = result.stdout.strip().split('\n')
                    active_sessions = [line for line in lines if 'Active' in line]
                    return len(active_sessions) > 1
                    
            except:
                pass
        elif self.system in ['Linux', 'Darwin']:
            try:
                # Verificar múltiplos usuários logados
                result = run_hidden(['who'], timeout=5)
                if result.returncode == 0:
                    unique_users = set()
                    for line in result.stdout.strip().split('\n'):
                        if line.strip():
                            username = line.split()[0]
                            unique_users.add(username)
                    return len(unique_users) > 1
            except:
                pass
        
        return False
    
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
            
            # Comentário adaptado para ambiente multi-usuário
            if self.is_multiuser_env:
                comment = f'LoQQuei {ip}:{port}'
            else:
                comment = f'LoQQuei {ip}:{port} Single'
            
            logger.info(f"Iniciando instalação da impressora virtual...")
            logger.info(f"Nome: {self.PRINTER_NAME}")
            logger.info(f"Sistema: {self.system}")
            logger.info(f"Servidor: {ip}:{port}")
            logger.info(f"Ambiente multi-usuário: {self.is_multiuser_env}")
            
            success = self.printer_manager.add_printer(
                self.PRINTER_NAME, ip, port,
                None, False, comment
            )
            
            if success:
                # Verificar se realmente foi instalada
                time.sleep(3)  # Aguardar mais tempo para o sistema processar
                verification_attempts = 3
                
                for attempt in range(verification_attempts):
                    if self.is_installed():
                        logger.info(f"Impressora virtual '{self.PRINTER_NAME}' instalada e verificada com sucesso!")
                        
                        if self.is_multiuser_env:
                            logger.info("IMPORTANTE: A impressora está configurada para ambiente multi-usuário.")
                            logger.info("Cada usuário terá seus PDFs salvos em sua própria pasta Documents/Impressora_LoQQuei")
                        
                        return True
                    else:
                        logger.warning(f"Tentativa {attempt + 1}/{verification_attempts}: Impressora não detectada ainda, aguardando...")
                        time.sleep(2)
                
                logger.error("Impressora foi instalada mas não é detectável pelo sistema após várias tentativas")
                return False
            else:
                logger.error("Falha ao instalar a impressora virtual")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao instalar impressora virtual: {str(e)}")
            import traceback
            logger.debug(f"Traceback completo: {traceback.format_exc()}")
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
        time.sleep(3)  # Aguardar entre desinstalar e reinstalar
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
                
                # Aguardar e verificar se realmente foi removida
                time.sleep(2)
                if not self.is_installed():
                    logger.info("Remoção da impressora virtual verificada com sucesso")
                    return True
                else:
                    logger.warning("Impressora ainda aparece como instalada após remoção")
                    return False
            else:
                logger.error("Falha ao remover impressora virtual")
                return False
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
            logger.error(f"Erro ao verificar instalação da impressora: {e}")
            return False
    
    def get_installation_info(self):
        """
        Obtém informações sobre a instalação
        
        Returns:
            dict: Informações da instalação
        """
        info = {
            'installed': self.is_installed(),
            'printer_name': self.PRINTER_NAME,
            'system': self.system,
            'multiuser_environment': self.is_multiuser_env,
            'server_info': self.server_info
        }
        
        # Adicionar informações específicas do sistema
        if hasattr(self.printer_manager, 'system_version'):
            info['system_version'] = self.printer_manager.system_version
        if hasattr(self.printer_manager, 'architecture'):
            info['architecture'] = self.printer_manager.architecture
        if hasattr(self.printer_manager, 'windows_version'):
            info['windows_version'] = self.printer_manager.windows_version
        
        if self.is_multiuser_env:
            info['description'] = 'Impressora configurada para ambiente multi-usuário'
            info['save_location'] = 'Documents/Impressora_LoQQuei de cada usuário'
        else:
            info['description'] = 'Impressora configurada para usuário único'
            info['save_location'] = self.config.pdf_dir if hasattr(self.config, 'pdf_dir') else 'Configuração padrão'
        
        return info
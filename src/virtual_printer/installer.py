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
        """Verifica se impressora existe - com tratamento de encoding"""
        try:
            # Método 1: lpstat direto
            result = run_hidden(['lpstat', '-p', name], timeout=5)
            if result.returncode == 0:
                # Verificar se o nome está na saída
                if name in result.stdout:
                    return True
            
            # Método 2: listar todas
            result = run_hidden(['lpstat', '-a'], timeout=5)
            if result.returncode == 0 and name in result.stdout:
                return True
            
            # Método 3: Tentar comando diferente
            result = run_hidden(['lpstat', '-v', name], timeout=5)
            if result.returncode == 0:
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Erro ao verificar impressora: {e}")
            return False
    
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

# CORREÇÃO COMPLETA PARA UnixPrinterManager - VERSÃO COM DIAGNÓSTICOS DETALHADOS

class UnixPrinterManager(PrinterManager):
    """Gerenciador de impressoras para sistemas Unix (Linux/macOS) usando CUPS"""
    
    def __init__(self):
        self.system = platform.system()
        self.system_version = self._get_system_version()
        self.architecture = self._get_architecture()
        self.cups_available = self._check_cups_availability()
        self.auth_available = False  # Para controlar se temos autorização elevada
        
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
        """Verifica se CUPS está instalado e acessível - Versão melhorada para macOS"""
        try:
            # Verificar comandos básicos
            commands_to_check = ['lpadmin', 'lpstat', 'lp']
            
            for cmd in commands_to_check:
                try:
                    result = run_hidden(['which', cmd], timeout=5)
                    if result.returncode != 0:
                        logger.warning(f"Comando {cmd} não encontrado")
                        return False
                except:
                    logger.warning(f"Erro ao verificar comando {cmd}")
                    return False
            
            # No macOS, verificar se CUPS está rodando de forma mais robusta
            if self.system == 'Darwin':
                return self._check_cups_macos()
            else:
                return self._check_cups_linux()
            
        except Exception as e:
            logger.error(f"Erro ao verificar CUPS: {e}")
            return False
    
    def _check_cups_macos(self):
        """Verificação específica do CUPS no macOS"""
        try:
            # Método 1: Verificar se o daemon está rodando
            result = run_hidden(['pgrep', 'cupsd'], timeout=5)
            if result.returncode == 0:
                logger.info("CUPS daemon está rodando")
                
                # Verificar se consegue listar impressoras (teste básico)
                result = run_hidden(['lpstat', '-p'], timeout=10)
                if result.returncode == 0:
                    logger.info("CUPS está funcionando corretamente")
                    return True
                else:
                    logger.info("CUPS daemon rodando, mas lpstat falhou - tentando iniciar")
            
            # Método 2: Tentar iniciar CUPS se não está rodando
            logger.info("Tentando iniciar CUPS...")
            if self._start_cups_service_macos():
                # Aguardar um pouco e verificar novamente
                time.sleep(3)
                result = run_hidden(['lpstat', '-p'], timeout=10)
                if result.returncode == 0:
                    logger.info("CUPS iniciado com sucesso")
                    return True
            
            logger.warning("CUPS não está disponível ou não pode ser iniciado")
            return False
            
        except Exception as e:
            logger.warning(f"Erro na verificação específica do macOS: {e}")
            return False
    
    def _check_cups_linux(self):
        """Verificação específica do CUPS no Linux"""
        try:
            # Verificar se o serviço CUPS está rodando
            result = run_hidden(['lpstat', '-r'], timeout=5)
            if "not ready" in result.stdout.lower() or result.returncode != 0:
                logger.info("CUPS não está rodando, tentando iniciar...")
                if not self._start_cups_service():
                    return False
            
            logger.info("CUPS está disponível e funcionando")
            return True
            
        except subprocess.TimeoutExpired:
            logger.warning("Timeout ao verificar status do CUPS")
            return False
        except Exception as e:
            logger.warning(f"Erro ao verificar CUPS no Linux: {e}")
            return False
    
    def _start_cups_service(self):
        """Tenta iniciar o serviço CUPS - Versão original para Linux"""
        logger.info("Tentando iniciar o serviço CUPS...")
        
        if self.system == 'Darwin':  # macOS
            return self._start_cups_service_macos()
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
    
    def _start_cups_service_macos(self):
        """Inicia o serviço CUPS no macOS com melhor compatibilidade"""
        logger.info("Tentando iniciar CUPS no macOS...")
        
        # Comandos para tentar iniciar CUPS no macOS (sem sudo primeiro)
        start_commands = [
            # Tentar sem sudo primeiro (pode funcionar em alguns casos)
            ['launchctl', 'load', '/System/Library/LaunchDaemons/org.cups.cupsd.plist'],
            ['launchctl', 'start', 'org.cups.cupsd'],
            
            # Homebrew CUPS (se instalado)
            ['brew', 'services', 'start', 'cups'],
        ]
        
        # Tentar comandos sem sudo primeiro
        for cmd in start_commands:
            try:
                logger.debug(f"Tentando comando sem sudo: {' '.join(cmd)}")
                result = run_hidden(cmd, timeout=15)
                if result.returncode == 0:
                    logger.info(f"CUPS iniciado sem sudo: {' '.join(cmd)}")
                    time.sleep(2)
                    # Verificar se realmente está funcionando
                    test_result = run_hidden(['lpstat', '-r'], timeout=5)
                    if test_result.returncode == 0 and "not ready" not in test_result.stdout.lower():
                        return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
            except Exception as e:
                logger.debug(f"Comando sem sudo falhou: {e}")
                continue
        
        # Se comandos sem sudo falharam, tentar com autenticação visual
        logger.info("Comandos sem sudo falharam, tentando com autenticação administrativa...")
        return self._start_cups_with_visual_auth()
    
    def _start_cups_with_visual_auth(self):
        """Inicia CUPS usando autenticação visual no macOS"""
        try:
            # Usar osascript para mostrar diálogo de autenticação
            script = '''
            do shell script "launchctl load -w /System/Library/LaunchDaemons/org.cups.cupsd.plist; launchctl start org.cups.cupsd" with administrator privileges
            '''
            
            result = run_hidden(['osascript', '-e', script], timeout=30)
            
            if result.returncode == 0:
                logger.info("CUPS iniciado com autenticação administrativa")
                self.auth_available = True
                time.sleep(3)
                
                # Verificar se funcionou
                test_result = run_hidden(['lpstat', '-r'], timeout=5)
                if test_result.returncode == 0 and "not ready" not in test_result.stdout.lower():
                    return True
            else:
                logger.warning(f"Falha na autenticação administrativa: {result.stderr}")
                
        except Exception as e:
            logger.warning(f"Erro na autenticação visual: {e}")
        
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
    
    def _request_admin_privileges(self, command_description="configurar impressora"):
        """Solicita privilégios administrativos usando interface visual do macOS"""
        if self.system != 'Darwin':
            return False
        
        try:
            # Script AppleScript para solicitar autenticação
            script = f'''
            display dialog "A aplicação precisa de privilégios administrativos para {command_description}. Digite sua senha quando solicitado." buttons {{"Cancelar", "Continuar"}} default button "Continuar" with icon note
            
            if button returned of result is "Continuar" then
                return "authorized"
            else
                return "cancelled"
            end if
            '''
            
            result = run_hidden(['osascript', '-e', script], timeout=30)
            
            if result.returncode == 0 and "authorized" in result.stdout:
                self.auth_available = True
                logger.info("Autorização administrativa concedida pelo usuário")
                return True
            else:
                logger.info("Autorização administrativa cancelada pelo usuário")
                return False
                
        except Exception as e:
            logger.error(f"Erro ao solicitar privilégios administrativos: {e}")
            return False
    
    def _execute_with_visual_auth(self, command, description="executar comando"):
        """Executa comando com autenticação visual - VERSÃO TOTALMENTE REESCRITA"""
        try:
            # Para macOS 15+, usar método mais simples
            import tempfile
            import os
            
            # Criar script shell temporário
            with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as script_file:
                script_file.write('#!/bin/bash\n')
                script_file.write(' '.join([f'"{arg}"' for arg in command]) + '\n')
                script_path = script_file.name
            
            try:
                # Tornar executável
                os.chmod(script_path, 0o755)
                
                # Usar osascript com script mais simples
                applescript = f'''
                do shell script "{script_path}" with administrator privileges
                '''
                
                result = run_hidden(['osascript', '-e', applescript], timeout=60)
                return result
                
            finally:
                # Remover arquivo temporário
                try:
                    os.unlink(script_path)
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Erro ao executar comando com autenticação visual: {e}")
            return None

    
    def _list_available_drivers(self):
        """Lista os drivers disponíveis no sistema"""
        try:
            logger.info("Listando drivers disponíveis...")
            
            # Método 1: lpinfo -m (mais confiável)
            result = run_hidden(['lpinfo', '-m'], timeout=15)
            if result.returncode == 0:
                drivers = []
                for line in result.stdout.split('\n'):
                    if line.strip():
                        # Formato: drv:///dir/file.ppd Description
                        driver_path = line.split(' ')[0]
                        if driver_path and driver_path != 'drv:///dir/file.ppd':
                            drivers.append(driver_path)
                
                logger.info(f"Drivers encontrados via lpinfo: {len(drivers)}")
                for i, driver in enumerate(drivers[:10]):  # Mostrar apenas os primeiros 10
                    logger.debug(f"  {i+1}. {driver}")
                
                return drivers
            
        except Exception as e:
            logger.warning(f"Erro ao listar drivers via lpinfo: {e}")
        
        # Método 2: Verificar diretórios padrão do CUPS
        try:
            ppd_dirs = [
                '/usr/share/cups/model',
                '/usr/share/ppd',
                '/Library/Printers/PPDs/Contents/Resources',
                '/System/Library/Printers/PPDs/Contents/Resources',
            ]
            
            drivers = []
            for ppd_dir in ppd_dirs:
                if os.path.exists(ppd_dir):
                    for root, dirs, files in os.walk(ppd_dir):
                        for file in files:
                            if file.endswith('.ppd') or file.endswith('.ppd.gz'):
                                rel_path = os.path.relpath(os.path.join(root, file), ppd_dir)
                                drivers.append(f"drv:///{rel_path}")
            
            logger.info(f"Drivers encontrados nos diretórios: {len(drivers)}")
            return drivers
            
        except Exception as e:
            logger.warning(f"Erro ao buscar drivers nos diretórios: {e}")
        
        # Fallback: drivers padrão conhecidos
        default_drivers = [
            'everywhere',
            'raw',
            'drv:///generic.drv/generic.ppd',
            'textonly.ppd',
            'lsb/usr/cups/generic-postscript-driver.ppd',
        ]
        
        logger.info(f"Usando drivers padrão: {default_drivers}")
        return default_drivers
    
    def _try_direct_command_installation(self, name, device_uri, comment):
        """
        Tenta instalação usando comando direto sem AppleScript
        Método mais simples que pode funcionar quando AppleScript falha
        """
        try:
            logger.info("Tentando instalação com comando direto...")
            
            # Tentar com sudo direto (usuário já autenticou)
            cmd = ['sudo', 'lpadmin', '-p', name, '-E', '-v', device_uri, '-m', 'raw']
            
            logger.debug(f"Executando comando direto: {' '.join(cmd)}")
            result = run_hidden(cmd, timeout=30)
            
            if result.returncode == 0:
                logger.info(f"✅ Impressora '{name}' instalada com comando direto!")
                
                # Configurações adicionais com sudo
                additional_commands = [
                    ['sudo', 'cupsenable', name],
                    ['sudo', 'cupsaccept', name],
                ]
                
                if comment:
                    additional_commands.append(['sudo', 'lpadmin', '-p', name, '-D', comment])
                
                for cmd in additional_commands:
                    try:
                        run_hidden(cmd, timeout=10)
                    except:
                        pass  # Não é crítico se falhar
                
                return True
            else:
                logger.warning(f"Comando direto falhou: {result.stderr}")
                
        except Exception as e:
            logger.warning(f"Erro no comando direto: {e}")
        
        return False

    def add_printer(self, name, ip, port, printer_port_name=None, make_default=False, comment=None):
        """Adiciona impressora no Unix usando CUPS - Versão melhorada para macOS"""
        if not self.cups_available:
            logger.error("CUPS não está disponível. Não é possível adicionar impressora.")
            return False

        # MUDANÇA: Sanitizar o nome da impressora
        original_name = name
        name = self._sanitize_printer_name(name)
        
        if name != original_name:
            logger.info(f"Nome da impressora sanitizado: '{original_name}' -> '{name}'")

        device_uri = f"socket://{ip}:{port}"
        
        logger.info(f"Instalando impressora: {name}")
        logger.info(f"Sistema: {self.system} {self.system_version}")
        logger.info(f"Arquitetura: {self.architecture}")
        logger.info(f"URI do dispositivo: {device_uri}")
        
        # Verificar se a impressora já existe
        if self.check_printer_exists(name):
            logger.info(f"Impressora '{name}' já existe, removendo para reinstalar...")
            self.remove_printer(name)
            time.sleep(2)
        
        # Escolher estratégia baseada no sistema
        if self.system == 'Darwin':
            return self._add_printer_macos(name, device_uri, comment)
        else:
            return self._add_printer_linux(name, device_uri, comment)

    def _create_backend_script(self, name, device_uri, spool_dir):
        """Cria script para processar trabalhos da impressora virtual"""
        try:
            # Extrair IP e porta do device_uri
            if device_uri.startswith('socket://'):
                uri_parts = device_uri.replace('socket://', '').split(':')
                ip = uri_parts[0]
                port = uri_parts[1] if len(uri_parts) > 1 else '9100'
            else:
                ip = '127.0.0.1'
                port = '9100'
            
            # Criar script que monitora o diretório e envia para o servidor
            script_path = os.path.join(spool_dir, 'process_jobs.sh')
            
            script_content = f'''#!/bin/bash
    # Script para processar trabalhos da impressora virtual

    SPOOL_DIR="{spool_dir}"
    SERVER_IP="{ip}"
    SERVER_PORT="{port}"

    # Monitorar arquivos no diretório
    while true; do
        for file in "$SPOOL_DIR"/*; do
            if [ -f "$file" ]; then
                # Enviar arquivo para o servidor
                nc -w 10 "$SERVER_IP" "$SERVER_PORT" < "$file" 2>/dev/null
                
                # Remover arquivo após envio
                rm -f "$file"
            fi
        done
        sleep 1
    done
    '''
            
            with open(script_path, 'w') as f:
                f.write(script_content)
            
            # Tornar executável
            os.chmod(script_path, 0o755)
            
            # Criar LaunchAgent para executar o script
            self._create_launch_agent(script_path)
            
        except Exception as e:
            logger.error(f"Erro ao criar script backend: {e}")
    
    def _create_launch_agent(self, script_path):
        """Cria LaunchAgent para processar trabalhos automaticamente"""
        try:
            launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
            os.makedirs(launch_agents_dir, exist_ok=True)
            
            plist_path = os.path.join(launch_agents_dir, "com.loqquei.printprocessor.plist")
            
            plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
    <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
    <plist version="1.0">
    <dict>
        <key>Label</key>
        <string>com.loqquei.printprocessor</string>
        <key>Program</key>
        <string>{script_path}</string>
        <key>RunAtLoad</key>
        <true/>
        <key>KeepAlive</key>
        <true/>
        <key>StandardErrorPath</key>
        <string>/tmp/loqquei-print-error.log</string>
    </dict>
    </plist>'''
            
            with open(plist_path, 'w') as f:
                f.write(plist_content)
            
            # Carregar o agent
            run_hidden(['launchctl', 'unload', plist_path], timeout=5)
            time.sleep(1)
            run_hidden(['launchctl', 'load', plist_path], timeout=5)
            
            logger.info("LaunchAgent criado para processar trabalhos")
            
        except Exception as e:
            logger.debug(f"Nota sobre LaunchAgent: {e}")

    def _configure_virtual_printer(self, name, device_uri, spool_dir):
        """Configura impressora virtual e cria backend personalizado"""
        try:
            # Habilitar impressora
            commands = [
                (['cupsenable', name], "habilitar"),
                (['cupsaccept', name], "aceitar trabalhos"),
            ]
            
            for cmd, desc in commands:
                try:
                    run_hidden(cmd, timeout=5)
                    logger.debug(f"✅ {desc}")
                except:
                    self._execute_with_visual_auth(cmd, desc)
            
            # Criar script backend para processar trabalhos
            self._create_backend_script(name, device_uri, spool_dir)
            
            logger.info("Impressora virtual configurada com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao configurar impressora virtual: {e}")

    def _find_generic_ppd(self):
        """Encontra PPDs genéricos do sistema"""
        ppd_locations = [
            # PPDs genéricos do macOS
            "/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/PrintCore.framework/Resources/Generic.ppd",
            "/System/Library/Frameworks/ApplicationServices.framework/Frameworks/PrintCore.framework/Resources/Generic.ppd",
            "/System/Library/Frameworks/ApplicationServices.framework/Resources/Generic.ppd",
            
            # PPDs PostScript genéricos
            "/usr/share/cups/model/Generic-PostScript_Printer-Postscript.ppd",
            "/Library/Printers/PPDs/Contents/Resources/Generic-PostScript_Printer.ppd",
            
            # PPDs de texto genérico
            "/usr/share/cups/model/textonly.ppd",
            "/usr/share/cups/model/generic.ppd",
        ]
        
        found_ppds = []
        
        # Verificar cada localização
        for ppd in ppd_locations:
            if os.path.exists(ppd):
                found_ppds.append(ppd)
                logger.debug(f"PPD encontrado: {ppd}")
        
        # Buscar PPDs adicionais no sistema
        try:
            import glob
            
            # Diretórios onde PPDs podem estar
            ppd_dirs = [
                "/Library/Printers/PPDs/Contents/Resources/",
                "/System/Library/Printers/PPDs/Contents/Resources/",
                "/usr/share/cups/model/",
            ]
            
            for ppd_dir in ppd_dirs:
                if os.path.exists(ppd_dir):
                    # Buscar PPDs genéricos
                    for pattern in ["*eneric*.ppd", "*eneric*.ppd.gz"]:
                        matches = glob.glob(os.path.join(ppd_dir, pattern))
                        for match in matches:
                            if match not in found_ppds:
                                found_ppds.append(match)
        except:
            pass
        
        return found_ppds

    def _try_alternative_installation(self, name, device_uri, comment):
        """Instalação alternativa usando lpd ou método genérico"""
        try:
            # Extrair IP e porta
            if device_uri.startswith('socket://'):
                uri_parts = device_uri.replace('socket://', '').split(':')
            else:
                uri_parts = device_uri.replace('ipp://', '').split(':')
                
            ip = uri_parts[0] if len(uri_parts) > 0 else '127.0.0.1'
            port = uri_parts[1].split('/')[0] if len(uri_parts) > 1 else '9100'
            
            # Tentar com lpd:// como alternativa
            lpd_uri = f'lpd://{ip}/raw'
            
            cmd = ['lpadmin', '-p', name, '-E', '-v', lpd_uri, '-P', '/System/Library/Frameworks/ApplicationServices.framework/Versions/A/Frameworks/PrintCore.framework/Versions/A/Resources/Generic.ppd']
            
            if comment:
                cmd.extend(['-D', comment])
            
            logger.info("Tentando instalação com driver genérico do sistema...")
            
            if self.auth_available or self._request_admin_privileges("instalar impressora com driver genérico"):
                result = self._execute_with_visual_auth(cmd, "instalar impressora genérica")
                
                if result and result.returncode == 0:
                    logger.info("✅ Impressora instalada com driver genérico")
                    self._enable_printer_simple(name)
                    return True
            
            # Última tentativa: criar impressora sem driver específico
            cmd = ['lpadmin', '-p', name, '-E', '-v', f'ipp://{ip}:{port}']
            result = self._execute_with_visual_auth(cmd, "criar impressora IPP básica")
            
            if result and result.returncode == 0:
                logger.info("✅ Impressora IPP básica criada")
                self._enable_printer_simple(name)
                return True
                
        except Exception as e:
            logger.error(f"Erro na instalação alternativa: {e}")
        
        return False

    def _check_available_drivers(self):
        """Verifica quais drivers estão disponíveis no sistema"""
        try:
            # Listar drivers disponíveis
            result = run_hidden(['lpinfo', '-m'], timeout=15)
            if result.returncode == 0:
                drivers = result.stdout.lower()
                
                available = []
                if 'everywhere' in drivers:
                    available.append('everywhere')
                if 'driverless' in drivers:
                    available.append('driverless')
                if 'airprint' in drivers:
                    available.append('airprint')
                    
                logger.info(f"Drivers disponíveis: {available}")
                return available
        except:
            pass
        
        return []

    def _add_printer_macos(self, name, device_uri, comment=None):
        """Adiciona impressora no macOS usando PPD genérico do sistema"""
        
        logger.info("Instalando impressora virtual no macOS...")
        
        # Procurar PPDs genéricos do sistema
        generic_ppds = self._find_generic_ppd()
        
        if not generic_ppds:
            logger.error("Nenhum PPD genérico encontrado no sistema")
            return False
        
        # Converter socket para lpd para melhor compatibilidade
        if device_uri.startswith('socket://'):
            uri_parts = device_uri.replace('socket://', '').split(':')
            ip = uri_parts[0] if len(uri_parts) > 0 else '127.0.0.1'
            device_uri = f'lpd://{ip}/raw'
            logger.info(f"Usando URI LPD: {device_uri}")
        
        # Usar o primeiro PPD genérico encontrado
        ppd_path = generic_ppds[0]
        logger.info(f"Usando PPD: {ppd_path}")
        
        # Comando para criar impressora
        cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri, '-P', ppd_path]
        
        if comment:
            cmd.extend(['-D', comment])
        
        # Tentar sem autenticação primeiro
        result = run_hidden(cmd, timeout=10)
        
        if result.returncode == 0:
            logger.info(f"✅ Impressora instalada com PPD {os.path.basename(ppd_path)}")
            self._configure_printer_options(name)
            return True
        
        # Se falhou, tentar com autenticação
        if self._request_admin_privileges("instalar a impressora virtual"):
            result = self._execute_with_visual_auth(cmd, "instalar impressora virtual")
            
            if result and result.returncode == 0:
                logger.info(f"✅ Impressora instalada com PPD {os.path.basename(ppd_path)} (com auth)")
                self._configure_printer_options(name)
                return True
        
        logger.error("Falha ao instalar impressora")
        return False

    def _configure_printer_options(self, name):
        """Configura opções da impressora para aceitar qualquer tipo de arquivo"""
        try:
            options = [
                # Aceitar trabalhos
                (['cupsenable', name], "habilitar impressora"),
                (['cupsaccept', name], "aceitar trabalhos"),
                
                # Configurar para aceitar raw - IMPORTANTE!
                (['lpadmin', '-p', name, '-o', 'raw'], "aceitar dados raw"),
                (['lpadmin', '-p', name, '-o', 'document-format-supported=application/octet-stream'], "suportar formato binário"),
                (['lpadmin', '-p', name, '-o', 'printer-is-shared=false'], "não compartilhar"),
            ]
            
            for cmd, desc in options:
                try:
                    result = run_hidden(cmd, timeout=5)
                    if result.returncode != 0:
                        # Tentar com auth se falhar
                        self._execute_with_visual_auth(cmd, desc)
                except:
                    pass
                    
            logger.info("Opções da impressora configuradas")
            
        except Exception as e:
            logger.debug(f"Erro ao configurar opções: {e}")

    def _enable_printer_simple(self, name):
        """Habilita a impressora de forma simples"""
        try:
            # Comandos básicos
            commands = [
                ['cupsenable', name],
                ['cupsaccept', name]
            ]
            
            for cmd in commands:
                try:
                    run_hidden(cmd, timeout=5)
                except:
                    # Se falhar, tentar com auth
                    try:
                        self._execute_with_visual_auth(cmd, f"{cmd[0]} {name}")
                    except:
                        pass
                        
            logger.info("Impressora habilitada")
        except Exception as e:
            logger.debug(f"Nota ao habilitar: {e}")

    def _apply_basic_settings(self, name):
        """Aplica apenas configurações básicas sem causar timeouts"""
        try:
            # Apenas habilitar e aceitar trabalhos
            basic_commands = [
                (['cupsenable', name], False),
                (['cupsaccept', name], False),
            ]
            
            for cmd, needs_auth in basic_commands:
                try:
                    if needs_auth and self.auth_available:
                        self._execute_with_visual_auth(cmd, f"configurar {cmd[0]}")
                    else:
                        run_hidden(cmd, timeout=5)
                except:
                    pass  # Não é crítico
                    
        except Exception as e:
            logger.debug(f"Erro ao aplicar configurações básicas: {e}")


    def _try_manual_installation(self, name, device_uri):
        """Método manual usando ferramentas do sistema"""
        try:
            logger.info("Iniciando instalação manual...")
            
            # Extrair informações da URI
            uri_parts = device_uri.replace('socket://', '').split(':')
            ip = uri_parts[0] if len(uri_parts) > 0 else '127.0.0.1'
            port = uri_parts[1] if len(uri_parts) > 1 else '9100'
            
            # Método 1: Tentar com System Preferences via comando
            try:
                logger.info("Tentando via comando do sistema...")
                
                # Usar comando system_profiler para verificar impressoras disponíveis
                check_cmd = ['system_profiler', 'SPPrintersDataType']
                run_hidden(check_cmd, timeout=10)
                
                # Tentar adicionar via linha de comando direta
                direct_cmd = [
                    'lpadmin', '-p', name, 
                    '-v', f'ipp://{ip}:{port}/ipp/print',  # Usar IPP em vez de socket
                    '-m', 'everywhere', '-E'
                ]
                
                result = self._execute_with_visual_auth(direct_cmd, "adicionar impressora IPP")
                
                if result and result.returncode == 0:
                    logger.info("✅ Sucesso com comando IPP direto")
                    return True
                    
            except Exception as e:
                logger.debug(f"Comando direto falhou: {e}")
            
            # Método 2: Usar printersetup (se disponível)
            try:
                # Verificar se printersetup existe
                which_result = run_hidden(['which', 'printersetup'], timeout=5)
                if which_result.returncode == 0:
                    logger.info("Tentando com printersetup...")
                    
                    setup_cmd = [
                        'printersetup', '-a', name,
                        '-v', device_uri,
                        '-m', 'everywhere'
                    ]
                    
                    result = self._execute_with_visual_auth(setup_cmd, "configurar impressora")
                    
                    if result and result.returncode == 0:
                        logger.info("✅ Sucesso com printersetup")
                        return True
                        
            except Exception as e:
                logger.debug(f"printersetup falhou: {e}")
            
            # Método 3: Interface gráfica como último recurso
            return self._open_system_preferences_printer(name, ip, port)
            
        except Exception as e:
            logger.error(f"Erro na instalação manual: {e}")
            return False

    def _try_install_with_driver(self, name, device_uri, driver, use_auth=False):
        """Tenta instalar com um driver específico - VERSÃO CORRIGIDA"""
        try:
            if driver is None:
                cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri]
                description = "instalação automática"
            else:
                cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri, '-m', driver]
                description = f"instalação com driver {driver}"
            
            logger.info(f"Tentando {description} {'com auth' if use_auth else 'sem auth'}")
            
            if use_auth and self.auth_available:
                result = self._execute_with_visual_auth(cmd, description)
                success = result and result.returncode == 0
            else:
                # Timeout menor para evitar travamentos
                result = run_hidden(cmd, timeout=30)
                success = result.returncode == 0
            
            if success:
                logger.info(f"✅ Sucesso na {description}")
                return True
            else:
                if result:
                    logger.debug(f"Falhou: {result.stderr.strip()}")
                    
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout no driver {driver or 'auto'}")
        except Exception as e:
            logger.warning(f"Erro: {e}")
        
        return False

    def _try_native_macos_installation(self, name, device_uri, comment):
        """Tenta usar o método nativo do macOS para adicionar impressora com integração completa"""
        try:
            logger.info("Tentando instalação nativa do macOS com integração completa...")
            
            # Extrair IP e porta
            uri_parts = device_uri.replace('socket://', '').split(':')
            ip = uri_parts[0] if len(uri_parts) > 0 else '127.0.0.1'
            port = uri_parts[1] if len(uri_parts) > 1 else '9100'
            
            # Método 1: Instalação completa com configurações do sistema
            success = self._install_with_system_integration(name, ip, port, comment)
            if success:
                return True
            
            # Método 2: Instalação básica e depois configurar
            if self._install_basic_and_configure(name, device_uri, comment):
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Erro no método nativo: {e}")
            return False

    def _configure_system_integration(self, name):
        """Configuração mínima e funcional"""
        try:
            logger.info("Aplicando configurações básicas...")
            
            # Apenas o essencial
            commands = [
                (['cupsenable', name], 5),
                (['cupsaccept', name], 5),
            ]
            
            for cmd, timeout in commands:
                try:
                    run_hidden(cmd, timeout=timeout)
                except:
                    pass  # Não é crítico
            
            logger.info("✅ Configurações aplicadas")
            return True
            
        except Exception as e:
            logger.debug(f"Nota nas configurações: {e}")
            return True  # Retorna True mesmo com erro pois não é crítico

    def _install_basic_and_configure(self, name, device_uri, comment):
        """Instala de forma básica e depois configura completamente"""
        try:
            logger.info("Tentando instalação básica seguida de configuração...")
            
            # Primeiro criar a impressora de forma mais simples
            basic_cmd = ['lpadmin', '-p', name, '-v', device_uri, '-E']
            
            result = run_hidden(basic_cmd, timeout=30)
            
            if result.returncode != 0:
                # Tentar com auth
                result = self._execute_with_visual_auth(basic_cmd, "criar impressora básica")
                if not result or result.returncode != 0:
                    logger.warning("Falha na criação básica")
                    return False
            
            logger.info("✅ Impressora criada, configurando integração...")
            
            # Aguardar criação
            time.sleep(2)
            
            # Verificar se foi criada
            if not self.check_printer_exists(name):
                logger.warning("Impressora não foi detectada após criação")
                return False
            
            # Configurar integração completa
            return self._configure_system_integration(name)
            
        except Exception as e:
            logger.warning(f"Erro na instalação básica: {e}")
            return False

    def _restart_cups_service(self):
        """Reinicia o serviço CUPS de forma segura no macOS - VERSÃO CORRIGIDA"""
        try:
            logger.info("Reiniciando serviço CUPS...")
            
            # Não usar sudo para evitar timeouts - deixar o sistema gerenciar
            simple_commands = [
                # Tentar sem sudo primeiro
                (['killall', '-HUP', 'cupsd'], 5),
                # Verificar status apenas
                (['lpstat', '-r'], 5),
            ]
            
            for cmd, timeout in simple_commands:
                try:
                    result = run_hidden(cmd, timeout=timeout)
                    if cmd[0] == 'lpstat' and result.returncode == 0:
                        if "scheduler is running" in result.stdout:
                            logger.info("✅ CUPS está funcionando")
                            return
                except:
                    continue
            
            logger.info("CUPS será reiniciado automaticamente pelo sistema quando necessário")
            
        except Exception as e:
            logger.debug(f"Nota sobre CUPS: {e}")

    def _register_with_macos_system(self, name):
        """Registra a impressora no sistema macOS para aparecer nas preferências"""
        try:
            logger.info("Registrando impressora no sistema macOS...")
            
            # Tentar notificar o sistema sobre a nova impressora
            notification_commands = [
                # Atualizar cache de impressoras do sistema
                (['sudo', 'killall', '-HUP', 'cupsd'], "atualizar cupsd"),
                
                # Notificar o sistema sobre mudanças
                (['sudo', 'launchctl', 'kickstart', '-k', 'system/com.apple.cupsd'], "reiniciar serviço"),
                
                # Forçar refresh do sistema de impressão
                (['lpstat', '-r'], "verificar sistema"),
            ]
            
            for cmd, description in notification_commands:
                try:
                    result = run_hidden(cmd, timeout=10)
                    logger.debug(f"Sistema notificado: {description}")
                except:
                    pass  # Não é crítico se falhar
            
            # Aguardar o sistema processar
            time.sleep(2)
            
        except Exception as e:
            logger.debug(f"Erro ao registrar no sistema: {e}")

    def _install_with_system_integration(self, name, ip, port, comment):
        """Instala impressora com integração completa ao sistema macOS"""
        try:
            logger.info("Instalando com integração completa ao sistema...")
            
            # Comando que integra melhor com o sistema macOS
            cmd = [
                'lpadmin', 
                '-p', name,
                '-v', f'ipp://{ip}:{port}/ipp/print',  # IPP funciona melhor que socket
                '-m', 'everywhere',  # Driver universal
                '-E',  # Habilitar
                '-o', 'printer-is-shared=false',  # Não compartilhar
                '-o', 'printer-state-reasons=none',  # Limpar estados de erro
            ]
            
            if comment:
                cmd.extend(['-D', comment])
            
            logger.debug(f"Comando de integração: {' '.join(cmd)}")
            
            # Tentar sem autenticação primeiro
            result = run_hidden(cmd, timeout=60)
            
            if result.returncode != 0:
                # Tentar com autenticação
                logger.info("Tentando com autenticação...")
                result = self._execute_with_visual_auth(cmd, "instalar impressora integrada")
                if not result or result.returncode != 0:
                    return False
            
            # Aguardar um pouco para o sistema processar
            time.sleep(3)
            
            # Configurações adicionais para integração
            if self._configure_system_integration(name):
                logger.info("✅ Impressora instalada com integração completa")
                return True
            
            return False
            
        except Exception as e:
            logger.warning(f"Erro na instalação com integração: {e}")
            return False

    def _try_add_printer_without_sudo(self, name, device_uri, drivers, comment):
        """Tenta adicionar impressora sem sudo - com timeout maior para everywhere"""
        for i, driver in enumerate(drivers):
            try:
                logger.info(f"Tentativa {i+1}/{len(drivers)}: Testando driver '{driver}' sem sudo")
                
                # Verificar se o driver realmente existe (para drivers de arquivo)
                if driver and driver.startswith('drv:///') and not self._driver_exists(driver):
                    logger.debug(f"Driver {driver} não existe no sistema, pulando")
                    continue
                
                cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri]
                if driver:
                    cmd.extend(['-m', driver])
                
                logger.debug(f"Executando comando: {' '.join(cmd)}")
                
                # Timeout especial para driver everywhere (pode demorar mais)
                timeout = 60 if driver == 'everywhere' else 30
                
                result = run_hidden(cmd, timeout=timeout)
                
                if result.returncode == 0:
                    logger.info(f"✅ Impressora '{name}' instalada sem sudo usando driver: {driver or 'auto'}")
                    
                    # Configurações adicionais
                    self._apply_printer_settings(name, comment, use_auth=False)
                    return True
                else:
                    logger.warning(f"❌ Driver {driver or 'auto'} falhou sem sudo:")
                    logger.warning(f"   Código de erro: {result.returncode}")
                    logger.warning(f"   Stderr: {result.stderr.strip()}")
                    if result.stdout.strip():
                        logger.warning(f"   Stdout: {result.stdout.strip()}")
                    
            except subprocess.TimeoutExpired:
                logger.warning(f"❌ Timeout no driver {driver or 'auto'} (normal para 'everywhere' em alguns casos)")
                continue
            except Exception as e:
                logger.warning(f"❌ Erro ao instalar com driver {driver or 'auto'} sem sudo: {e}")
                continue
        
        return False
    
    def _try_add_printer_with_auth(self, name, device_uri, drivers, comment):
        """Tenta adicionar impressora com autenticação visual"""
        for i, driver in enumerate(drivers):
            try:
                logger.info(f"Tentativa {i+1}/{len(drivers)}: Testando driver '{driver}' com auth")
                
                # Verificar se o driver realmente existe
                if driver.startswith('drv:///') and not self._driver_exists(driver):
                    logger.debug(f"Driver {driver} não existe no sistema, pulando")
                    continue
                
                cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri, '-m', driver]
                
                logger.debug(f"Executando comando com auth: {' '.join(cmd)}")
                result = self._execute_with_visual_auth(cmd, f"instalar impressora com driver {driver}")
                
                if result and result.returncode == 0:
                    logger.info(f"✅ Impressora '{name}' instalada com auth usando driver: {driver}")
                    
                    # Configurações adicionais
                    self._apply_printer_settings(name, comment, use_auth=True)
                    return True
                else:
                    if result:
                        logger.warning(f"❌ Driver {driver} falhou com auth:")
                        logger.warning(f"   Código de erro: {result.returncode}")
                        logger.warning(f"   Stderr: {result.stderr.strip()}")
                        logger.warning(f"   Stdout: {result.stdout.strip()}")
                    else:
                        logger.warning(f"❌ Driver {driver} falhou: comando não executado")
                        
            except Exception as e:
                logger.warning(f"❌ Erro ao instalar com driver {driver} com auth: {e}")
                continue
        
        logger.error("❌ Todos os drivers falharam, mesmo com autenticação administrativa")
        
        # Tentar método alternativo: criar impressora sem driver específico
        logger.info("Tentando método alternativo: instalação básica...")
        return self._try_basic_printer_installation(name, device_uri, comment)
    
    def _try_basic_printer_installation(self, name, device_uri, comment):
        """Tenta instalação básica da impressora usando métodos alternativos"""
        try:
            # Método 1: Tentar com comando direto (mais simples)
            if self._try_direct_command_installation(name, device_uri, comment):
                return True
            
            # Método 2: Criar impressora apenas com URI usando AppleScript corrigido
            basic_cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri]
            
            logger.info("Tentando instalação básica sem driver específico...")
            result = self._execute_with_visual_auth(basic_cmd, "criar impressora básica")
            
            if result and result.returncode == 0:
                logger.info("✅ Impressora criada com instalação básica!")
                
                # Tentar adicionar driver genérico depois
                try:
                    add_driver_cmd = ['lpadmin', '-p', name, '-m', 'raw']
                    self._execute_with_visual_auth(add_driver_cmd, "adicionar driver genérico")
                except:
                    pass
                
                # Configurações adicionais
                self._apply_printer_settings(name, comment, use_auth=True)
                return True
            
        except Exception as e:
            logger.error(f"Falha na instalação básica: {e}")
        
        # Método 3: Usar System Preferences (último recurso)
        return self._try_system_preferences_installation(name, device_uri)

    
    def _open_system_preferences_printer(self, name, ip, port):
        """Abre System Preferences para adicionar impressora manualmente"""
        try:
            logger.info("Abrindo System Preferences para instalação manual...")
            
            # Script AppleScript mais robusto para abrir System Preferences
            script = f'''
            tell application "System Preferences"
                activate
                reveal pane "Printers & Scanners"
                delay 2
            end tell
            
            display dialog "Sistema de Impressão não conseguiu instalar automaticamente.\\n\\nPor favor, clique no botão '+' e adicione:\\n\\nNome: {name}\\nEndereço: {ip}\\nPorta: {port}\\nTipo: IPP (Internet Printing Protocol)\\n\\nClique OK quando terminar ou Cancelar para pular." buttons {{"Cancelar", "OK"}} default button "OK" giving up after 90
            '''
            
            result = run_hidden(['osascript', '-e', script], timeout=120)
            
            if result.returncode == 0:
                # Aguardar e verificar se a impressora foi criada
                logger.info("Aguardando instalação manual...")
                
                max_attempts = 18  # 90 segundos
                for attempt in range(max_attempts):
                    time.sleep(5)
                    
                    if self.check_printer_exists(name):
                        logger.info("✅ Impressora criada via instalação manual!")
                        return True
                    
                    # Verificar variações do nome
                    variations = [name.replace('_', ' '), name.replace(' ', '_'), name.lower(), name.upper()]
                    for variation in variations:
                        if self.check_printer_exists(variation):
                            logger.info(f"✅ Impressora criada com nome '{variation}'!")
                            return True
                
                logger.info("Tempo esgotado aguardando instalação manual")
            
        except Exception as e:
            logger.error(f"Erro ao abrir System Preferences: {e}")
        
        return False

    
    def _driver_exists(self, driver):
        """Verifica se um driver específico existe no sistema"""
        if not driver.startswith('drv:///'):
            return True  # Drivers built-in como 'raw', 'everywhere' sempre existem
        
        try:
            # Extrair caminho do driver
            driver_path = driver.replace('drv:///', '')
            
            # Verificar em diretórios padrão
            search_dirs = [
                '/usr/share/cups/model',
                '/usr/share/ppd',
                '/Library/Printers/PPDs/Contents/Resources',
                '/System/Library/Printers/PPDs/Contents/Resources',
            ]
            
            for search_dir in search_dirs:
                full_path = os.path.join(search_dir, driver_path)
                if os.path.exists(full_path):
                    return True
                # Verificar versão comprimida
                if os.path.exists(full_path + '.gz'):
                    return True
            
            return False
            
        except Exception as e:
            logger.debug(f"Erro ao verificar driver {driver}: {e}")
            return True  # Em caso de erro, assumir que existe
    
    def _apply_printer_settings(self, name, comment, use_auth=False):
        """Aplica configurações adicionais à impressora"""
        try:
            settings_commands = []
            
            if comment:
                settings_commands.append(('comentário', ['lpadmin', '-p', name, '-D', comment]))
            
            # Habilitar a impressora
            settings_commands.append(('habilitar', ['cupsenable', name]))
            
            # Aceitar trabalhos
            settings_commands.append(('aceitar trabalhos', ['cupsaccept', name]))
            
            # Tornar disponível para todos os usuários (importante para persistência)
            settings_commands.append(('compartilhar', ['lpadmin', '-p', name, '-o', 'printer-is-shared=true']))
            
            for desc, cmd in settings_commands:
                try:
                    if use_auth and self.auth_available:
                        result = self._execute_with_visual_auth(cmd, desc)
                        success = result and result.returncode == 0
                    else:
                        result = run_hidden(cmd, timeout=10)
                        success = result.returncode == 0
                    
                    if success:
                        logger.debug(f"✅ Configuração '{desc}' aplicada com sucesso")
                    else:
                        # Para algumas configurações, falha não é crítica
                        if desc in ['compartilhar']:
                            logger.debug(f"⚠️ Configuração '{desc}' falhou, mas não é crítica")
                        else:
                            logger.warning(f"❌ Falha ao aplicar configuração '{desc}'")
                            
                except Exception as e:
                    logger.warning(f"❌ Erro ao aplicar configuração '{desc}': {e}")
                    
        except Exception as e:
            logger.warning(f"Erro ao aplicar configurações adicionais: {e}")
    
    def _add_printer_linux(self, name, device_uri, comment=None):
        """Adiciona impressora específicamente no Linux"""
        needs_sudo = os.geteuid() != 0 if hasattr(os, 'geteuid') else True
        
        drivers = [
            'everywhere',  # Driver genérico moderno (CUPS 2.2+)
            'raw',
            'drv:///generic.drv/generic.ppd',
            'textonly.ppd',
            'lsb/usr/cups/generic-postscript-driver.ppd',
        ]
        
        for driver in drivers:
            try:
                cmd = ['lpadmin', '-p', name, '-E', '-v', device_uri, '-m', driver]
                
                if needs_sudo:
                    cmd.insert(0, 'sudo')
                
                logger.debug(f"Tentando instalar no Linux com driver: {driver}")
                result = run_hidden(cmd, timeout=30)
                
                if result.returncode == 0:
                    logger.info(f"Impressora '{name}' instalada no Linux usando driver: {driver}")
                    
                    # Configurações adicionais
                    self._apply_printer_settings_linux(name, comment, needs_sudo)
                    return True
                else:
                    logger.debug(f"Driver {driver} falhou no Linux: {result.stderr}")
            except Exception as e:
                logger.debug(f"Erro ao instalar com driver {driver} no Linux: {e}")
                continue
        
        return False
    
    def _apply_printer_settings_linux(self, name, comment, needs_sudo):
        """Aplica configurações no Linux"""
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
                        logger.debug(f"Configuração '{desc}' aplicada com sucesso no Linux")
                    else:
                        logger.warning(f"Falha ao aplicar configuração '{desc}' no Linux: {result.stderr}")
                except Exception as e:
                    logger.warning(f"Erro ao aplicar configuração '{desc}' no Linux: {e}")
                    
        except Exception as e:
            logger.warning(f"Erro ao aplicar configurações adicionais no Linux: {e}")
    
    def remove_printer(self, name):
        """Remove impressora no Unix - Versão melhorada"""
        if not self.cups_available:
            return False
        
        if self.system == 'Darwin':
            return self._remove_printer_macos(name)
        else:
            return self._remove_printer_linux(name)
    
    def _remove_printer_macos(self, name):
        """Remove impressora no macOS"""
        # Tentar sem sudo primeiro
        try:
            cmd = ['lpadmin', '-x', name]
            result = run_hidden(cmd, timeout=15)
            if result.returncode == 0:
                logger.info(f"Impressora '{name}' removida sem sudo no macOS")
                return True
        except Exception as e:
            logger.debug(f"Remoção sem sudo falhou: {e}")
        
        # Tentar com autenticação visual se necessário
        if self.auth_available or self._request_admin_privileges("remover a impressora"):
            try:
                cmd = ['lpadmin', '-x', name]
                result = self._execute_with_visual_auth(cmd, "remover impressora")
                if result and result.returncode == 0:
                    logger.info(f"Impressora '{name}' removida com auth visual no macOS")
                    return True
                else:
                    logger.warning(f"Falha ao remover impressora com auth: {result.stderr if result else 'Comando falhou'}")
            except Exception as e:
                logger.error(f"Erro ao remover impressora com auth: {e}")
        
        return False
    
    def _remove_printer_linux(self, name):
        """Remove impressora no Linux"""
        needs_sudo = os.geteuid() != 0 if hasattr(os, 'geteuid') else True
        
        cmd = ['lpadmin', '-x', name]
        if needs_sudo:
            cmd.insert(0, 'sudo')
        
        try:
            result = run_hidden(cmd, timeout=15)
            if result.returncode == 0:
                logger.info(f"Impressora '{name}' removida no Linux")
                return True
            else:
                logger.warning(f"Falha ao remover impressora no Linux: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Erro ao remover impressora no Linux: {e}")
            return False
    
    def remove_port(self, port_name):
        """No Unix/CUPS, as portas são gerenciadas automaticamente"""
        pass
    
    def _post_installation_setup(self, name):
        """Configuração pós-instalação para garantir funcionamento"""
        try:
            logger.info("Executando configuração pós-instalação...")
            
            # Aguardar a impressora estar pronta
            max_attempts = 10
            for attempt in range(max_attempts):
                if self.check_printer_exists(name):
                    break
                time.sleep(1)
            
            # Comandos finais de configuração
            final_commands = [
                # Garantir que está habilitada
                (['cupsenable', name], False),
                (['cupsaccept', name], False),
                
                # Configurar opções específicas para funcionamento
                (['lpadmin', '-p', name, '-o', 'printer-error-policy=retry-job'], False),
                (['lpadmin', '-p', name, '-o', 'printer-op-policy=default'], False),
                
                # Teste de conectividade
                (['lpstat', '-p', name], False),
            ]
            
            for cmd, needs_auth in final_commands:
                try:
                    if needs_auth:
                        self._execute_with_visual_auth(cmd, f"configurar {cmd[1]}")
                    else:
                        run_hidden(cmd, timeout=10)
                except:
                    pass  # Não é crítico
            
            # Notificar sistema de mudanças
            self._register_with_macos_system(name)
            
            logger.info("✅ Configuração pós-instalação concluída")
            return True
            
        except Exception as e:
            logger.warning(f"Erro na configuração pós-instalação: {e}")
            return False

    def check_printer_exists(self, name):
        """Verifica se impressora existe - com tratamento de encoding"""
        try:
            # Método 1: lpstat direto
            result = run_hidden(['lpstat', '-p', name], timeout=5)
            if result.returncode == 0:
                # Verificar se o nome está na saída
                if name in result.stdout:
                    return True
            
            # Método 2: listar todas
            result = run_hidden(['lpstat', '-a'], timeout=5)
            if result.returncode == 0 and name in result.stdout:
                return True
            
            # Método 3: Tentar comando diferente
            result = run_hidden(['lpstat', '-v', name], timeout=5)
            if result.returncode == 0:
                return True
                
            return False
            
        except Exception as e:
            logger.debug(f"Erro ao verificar impressora: {e}")
            return False
    
    def check_port_exists(self, port_name):
        """No Unix/CUPS, não é necessário verificar portas separadamente"""
        return True
    
    def _sanitize_printer_name(self, name):
        """
        Limpa o nome da impressora para ser compatível com CUPS
        Remove espaços, acentos e caracteres especiais
        """
        import re
        import unicodedata
        
        # Normalizar caracteres Unicode (remover acentos)
        name = unicodedata.normalize('NFD', name)
        name = ''.join(c for c in name if unicodedata.category(c) != 'Mn')
        
        # Substituir espaços por underscores
        name = re.sub(r'\s+', '_', name)
        
        # Manter apenas caracteres alfanuméricos, underscore e hífen
        name = re.sub(r'[^a-zA-Z0-9_-]', '', name)
        
        # Garantir que não comece com número ou hífen
        if name and (name[0].isdigit() or name[0] == '-'):
            name = 'Impressora_' + name
        
        # Garantir que tenha pelo menos 1 caractere
        if not name:
            name = 'Impressora_LoQQuei'
        
        # Limitar tamanho (CUPS tem limite de 127 caracteres)
        if len(name) > 50:
            name = name[:50]
        
        return name


    def ensure_printer_persistence(self, name):
        """
        Garante que a impressora persista após reinicializações
        Específico para macOS onde impressoras podem desaparecer
        """
        if self.system != 'Darwin':
            return True
        
        try:
            # No macOS, adicionar algumas configurações de persistência
            persistence_commands = [
                # Tornar a impressora compartilhada ajuda na persistência
                ['lpadmin', '-p', name, '-o', 'printer-is-shared=true'],
                # Definir opções específicas que ajudam na persistência
                ['lpadmin', '-p', name, '-o', 'printer-is-accepting-jobs=true'],
                ['lpadmin', '-p', name, '-o', 'printer-state=3'],  # Estado idle
            ]
            
            for cmd in persistence_commands:
                try:
                    if self.auth_available:
                        result = self._execute_with_visual_auth(cmd, "configurar persistência da impressora")
                        if result and result.returncode == 0:
                            logger.debug(f"Comando de persistência executado: {' '.join(cmd)}")
                    else:
                        result = run_hidden(cmd, timeout=10)
                        if result.returncode == 0:
                            logger.debug(f"Comando de persistência executado sem auth: {' '.join(cmd)}")
                except Exception as e:
                    logger.debug(f"Comando de persistência falhou: {e}")
            
            # Salvar configuração do CUPS
            try:
                # Reiniciar CUPS pode ajudar a persistir a configuração
                restart_cmd = ['launchctl', 'stop', 'org.cups.cupsd']
                run_hidden(restart_cmd, timeout=10)
                time.sleep(1)
                restart_cmd = ['launchctl', 'start', 'org.cups.cupsd']
                run_hidden(restart_cmd, timeout=10)
                
                logger.info("Configurações de persistência aplicadas")
                return True
                
            except Exception as e:
                logger.debug(f"Erro ao aplicar configurações de persistência: {e}")
            
            return True
            
        except Exception as e:
            logger.warning(f"Erro ao garantir persistência da impressora: {e}")
            return False
    
    def get_printer_status(self, name):
        """Obtém o status detalhado da impressora"""
        try:
            result = run_hidden(['lpstat', '-p', name, '-l'], timeout=10)
            if result.returncode == 0:
                return {
                    'exists': True,
                    'status': 'online' if 'enabled' in result.stdout.lower() else 'offline',
                    'details': result.stdout.strip()
                }
            else:
                return {
                    'exists': False,
                    'status': 'not_found',
                    'details': None
                }
        except Exception as e:
            return {
                'exists': False,
                'status': 'error',
                'details': str(e)
            }

class VirtualPrinterInstaller:
    """Instalador da impressora virtual cross-platform com suporte multi-usuário"""
    
    PRINTER_NAME = "Impressora_LoQQuei"
    
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
    
    def restore_printer_after_restart(self):
        """
        Restaura a impressora após reinicialização do sistema
        Útil para casos onde a impressora pode ter sido removida ou desabilitada
        """
        logger.info("Verificando e restaurando impressora após possível reinicialização...")
        
        if not self.server_info:
            logger.warning("Não há informações do servidor para restaurar a impressora")
            return False
        
        try:
            # Se a impressora não existe mais, reinstalar
            if not self.is_installed():
                logger.info("Impressora não encontrada após reinicialização, reinstalando...")
                return self.install_with_server_info(self.server_info)
            
            # Se existe mas não está funcionando (especialmente no macOS)
            if self.system == 'Darwin' and hasattr(self.printer_manager, 'get_printer_status'):
                status = self.printer_manager.get_printer_status(self.PRINTER_NAME)
                if status['status'] != 'online':
                    logger.info("Impressora existe mas não está online, tentando reativar...")
                    
                    # Tentar reativar
                    try:
                        if hasattr(self.printer_manager, 'auth_available') and self.printer_manager.auth_available:
                            # Com autenticação
                            enable_cmd = ['cupsenable', self.PRINTER_NAME]
                            accept_cmd = ['cupsaccept', self.PRINTER_NAME]
                            
                            result1 = self.printer_manager._execute_with_visual_auth(enable_cmd, "reativar impressora")
                            result2 = self.printer_manager._execute_with_visual_auth(accept_cmd, "aceitar trabalhos da impressora")
                            
                            if (result1 and result1.returncode == 0) and (result2 and result2.returncode == 0):
                                logger.info("Impressora reativada com sucesso")
                                return True
                        else:
                            # Sem autenticação
                            result1 = run_hidden(['cupsenable', self.PRINTER_NAME], timeout=10)
                            result2 = run_hidden(['cupsaccept', self.PRINTER_NAME], timeout=10)
                            
                            if result1.returncode == 0 and result2.returncode == 0:
                                logger.info("Impressora reativada sem autenticação")
                                return True
                        
                        # Se reativação falhou, reinstalar
                        logger.info("Reativação falhou, reinstalando impressora...")
                        self.uninstall()
                        time.sleep(2)
                        return self.install_with_server_info(self.server_info)
                        
                    except Exception as e:
                        logger.warning(f"Erro ao reativar impressora: {e}")
                        # Tentar reinstalar como último recurso
                        logger.info("Reinstalando impressora como último recurso...")
                        self.uninstall()
                        time.sleep(2)
                        return self.install_with_server_info(self.server_info)
            
            # Se chegou aqui, impressora está funcionando
            logger.info("Impressora está funcionando corretamente")
            
            # Aplicar configurações de persistência se disponível
            if self.system == 'Darwin' and hasattr(self.printer_manager, 'ensure_printer_persistence'):
                self.printer_manager.ensure_printer_persistence(self.PRINTER_NAME)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao restaurar impressora: {e}")
            return False

    def check_and_fix_printer(self):
        """
        Verifica o estado da impressora e corrige problemas se necessário
        Método público para ser chamado periodicamente ou no startup
        """
        return self.restore_printer_after_restart()

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
                        
                        if hasattr(self.printer_manager, '_post_installation_setup'):
                            self.printer_manager._post_installation_setup(self.PRINTER_NAME)
                            
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
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Componente de listagem de impressoras com detalhes aprimorados - Versão com Notificações do Sistema e Scrollbars Personalizadas
"""

import os
import wx
import logging
import threading
import json
from src.models.printer import Printer
from src.utils.resource_manager import ResourceManager
from src.ui.custom_button import create_styled_button
import re
import traceback
import platform

logger = logging.getLogger("PrintManagementSystem.UI.PrinterList")

# Classe para notificações do sistema
class SystemNotification:
    """Classe para gerenciar notificações do sistema operacional - Compatibilidade Universal"""
    
    def __init__(self):
        self.system = platform.system().lower()
        self.windows_version = self._detect_windows_version()
        self.notification_methods = self._detect_available_methods()
        logger.info(f"Sistema detectado: {self.system}, Métodos disponíveis: {list(self.notification_methods.keys())}")
    
    def _detect_windows_version(self):
        """Detecta versão específica do Windows"""
        if self.system != "windows":
            return None
            
        try:
            version = platform.version()
            release = platform.release()
            
            # Detecta se é Windows Server
            is_server = "server" in platform.platform().lower()
            
            # Versões principais
            major_version = int(version.split('.')[0])
            
            return {
                'version': version,
                'release': release,
                'major': major_version,
                'is_server': is_server,
                'is_win7_plus': major_version >= 6,  # Windows 7 = 6.1
                'is_win8_plus': major_version >= 6 and float('.'.join(version.split('.')[:2])) >= 6.2,
                'is_win10_plus': major_version >= 10
            }
        except Exception:
            return {'version': 'unknown', 'major': 0, 'is_server': False, 'is_win7_plus': True, 'is_win8_plus': False, 'is_win10_plus': False}
    
    def _detect_available_methods(self):
        """Detecta métodos de notificação disponíveis para o sistema atual"""
        methods = {}
        
        if self.system == "windows":
            methods.update(self._detect_windows_methods())
        elif self.system == "darwin":
            methods.update(self._detect_macos_methods())
        elif self.system == "linux":
            methods.update(self._detect_linux_methods())
        
        # Método universal sempre disponível
        methods['console'] = True
        
        return methods
    
    def _detect_windows_methods(self):
        """Detecta métodos disponíveis no Windows"""
        methods = {}
        
        # Método 1: plyer (biblioteca universal mais robusta)
        try:
            import plyer
            methods['plyer'] = True
            logger.info("plyer disponível - método preferencial para notificações")
        except ImportError:
            methods['plyer'] = False
        
        # Método 2: win10toast (funciona desde Windows 7, apesar do nome)
        try:
            import win10toast
            methods['win10toast'] = True
            logger.info("win10toast disponível")
        except ImportError:
            methods['win10toast'] = False
        
        # Método 3: PowerShell (Windows 7+)
        if self.windows_version and self.windows_version['is_win7_plus']:
            methods['powershell'] = self._test_powershell()
        
        # Método 4: Windows API Balloon Tips (Windows 7+)
        methods['balloon_tip'] = self._test_balloon_tip()
        
        # Método 5: Windows API MessageBox (sempre disponível)
        methods['messagebox'] = True
        
        return methods
    
    def _detect_macos_methods(self):
        """Detecta métodos disponíveis no macOS"""
        methods = {}
        
        # Método 1: plyer
        try:
            import plyer
            methods['plyer'] = True
        except ImportError:
            methods['plyer'] = False
        
        # Método 2: terminal-notifier
        methods['terminal_notifier'] = self._test_command(['which', 'terminal-notifier'])
        
        # Método 3: osascript (sempre disponível no macOS)
        methods['osascript'] = self._test_command(['osascript', '-e', 'return 1'])
        
        return methods
    
    def _detect_linux_methods(self):
        """Detecta métodos disponíveis no Linux"""
        methods = {}
        
        # Método 1: plyer
        try:
            import plyer
            methods['plyer'] = True
        except ImportError:
            methods['plyer'] = False
        
        # Método 2: notify-send (libnotify)
        methods['notify_send'] = self._test_command(['which', 'notify-send'])
        
        # Método 3: zenity (GNOME)
        methods['zenity'] = self._test_command(['which', 'zenity'])
        
        # Método 4: kdialog (KDE)
        methods['kdialog'] = self._test_command(['which', 'kdialog'])
        
        return methods
    
    def _test_command(self, cmd):
        """Testa se um comando está disponível"""
        try:
            import subprocess
            result = subprocess.run(cmd, capture_output=True, timeout=5)
            return result.returncode == 0
        except Exception:
            return False
    
    def _test_powershell(self):
        """Testa se PowerShell está disponível e funcionando"""
        try:
            import subprocess
            result = subprocess.run(
                ["powershell.exe", "-Command", "echo 'test'"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def _test_balloon_tip(self):
        """Testa se balloon tips estão disponíveis"""
        try:
            import ctypes
            from ctypes import wintypes
            # Apenas verifica se as DLLs necessárias estão presentes
            user32 = ctypes.windll.user32
            shell32 = ctypes.windll.shell32
            return True
        except Exception:
            return False
    
    def show_notification(self, title, message, duration=5, notification_type="info"):
        """
        Exibe uma notificação do sistema com compatibilidade universal
        
        Args:
            title: Título da notificação
            message: Mensagem da notificação
            duration: Duração em segundos
            notification_type: Tipo da notificação (info, success, warning, error)
        """
        # Log da notificação sempre
        log_message = f"[{notification_type.upper()}] {title}: {message}"
        
        if notification_type == "error":
            logger.error(log_message)
        elif notification_type == "warning":
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        # Limita o tamanho para evitar problemas
        title = self._truncate_text(title, 60)
        message = self._truncate_text(message, 200)
        
        # Ordem de preferência por sistema
        success = False
        
        if self.system == "windows":
            success = self._show_windows_notification_universal(title, message, duration, notification_type)
        elif self.system == "darwin":
            success = self._show_macos_notification_universal(title, message, duration, notification_type)
        elif self.system == "linux":
            success = self._show_linux_notification_universal(title, message, duration, notification_type)
        
        if not success:
            logger.warning(f"Todas as tentativas de notificação falharam para: {title}")
            self._show_console_notification(title, message, notification_type)
        
        return success
    
    def _truncate_text(self, text, max_length):
        """Trunca texto se for muito longo"""
        if len(text) > max_length:
            return text[:max_length-3] + "..."
        return text
    
    def _show_windows_notification_universal(self, title, message, duration, notification_type):
        """Exibe notificação no Windows com máxima compatibilidade (Windows 7+)"""
        
        # Ordem de preferência para Windows
        methods_to_try = [
            ('plyer', self._try_plyer_notification),
            ('win10toast', self._try_win10toast_notification),
            ('powershell', self._try_powershell_notification),
            ('balloon_tip', self._try_balloon_tip_notification),
            ('messagebox', self._try_messagebox_notification)
        ]
        
        for method_name, method_func in methods_to_try:
            if self.notification_methods.get(method_name, False):
                try:
                    logger.debug(f"Tentando notificação via {method_name}")
                    if method_func(title, message, duration, notification_type):
                        logger.info(f"Notificação exibida com sucesso via {method_name}")
                        return True
                except Exception as e:
                    logger.debug(f"Falha no método {method_name}: {str(e)}")
                    continue
        
        return False
    
    def _show_macos_notification_universal(self, title, message, duration, notification_type):
        """Exibe notificação no macOS"""
        
        methods_to_try = [
            ('plyer', self._try_plyer_notification),
            ('terminal_notifier', self._try_terminal_notifier_notification),
            ('osascript', self._try_osascript_notification)
        ]
        
        for method_name, method_func in methods_to_try:
            if self.notification_methods.get(method_name, False):
                try:
                    logger.debug(f"Tentando notificação macOS via {method_name}")
                    if method_func(title, message, duration, notification_type):
                        logger.info(f"Notificação macOS exibida via {method_name}")
                        return True
                except Exception as e:
                    logger.debug(f"Falha no método macOS {method_name}: {str(e)}")
                    continue
        
        return False
    
    def _show_linux_notification_universal(self, title, message, duration, notification_type):
        """Exibe notificação no Linux"""
        
        methods_to_try = [
            ('plyer', self._try_plyer_notification),
            ('notify_send', self._try_notify_send_notification),
            ('zenity', self._try_zenity_notification),
            ('kdialog', self._try_kdialog_notification)
        ]
        
        for method_name, method_func in methods_to_try:
            if self.notification_methods.get(method_name, False):
                try:
                    logger.debug(f"Tentando notificação Linux via {method_name}")
                    if method_func(title, message, duration, notification_type):
                        logger.info(f"Notificação Linux exibida via {method_name}")
                        return True
                except Exception as e:
                    logger.debug(f"Falha no método Linux {method_name}: {str(e)}")
                    continue
        
        return False
    
    # =============================================================================
    # MÉTODOS ESPECÍFICOS DE NOTIFICAÇÃO
    # =============================================================================
    
    def _try_plyer_notification(self, title, message, duration, notification_type):
        """Método universal usando plyer (funciona em todos os sistemas)"""
        try:
            from plyer import notification
            
            # Mapeamento de ícones para plyer
            app_icon = None  # plyer detecta automaticamente
            
            # Executa notificação em thread separada
            def show_plyer():
                try:
                    notification.notify(
                        title=title,
                        message=message,
                        app_icon=app_icon,
                        timeout=duration
                    )
                except Exception as e:
                    logger.debug(f"Erro interno do plyer: {str(e)}")
            
            import threading
            thread = threading.Thread(target=show_plyer)
            thread.daemon = True
            thread.start()
            
            return True
            
        except ImportError:
            logger.debug("plyer não está instalado")
            return False
        except Exception as e:
            logger.debug(f"Erro no plyer: {str(e)}")
            return False
    
    # MÉTODOS WINDOWS
    def _try_win10toast_notification(self, title, message, duration, notification_type):
        """Notificação usando win10toast (Windows 7+)"""
        try:
            from win10toast import ToastNotifier
            
            def show_toast():
                try:
                    toaster = ToastNotifier()
                    toaster.show_toast(
                        title,
                        message,
                        icon_path=None,
                        duration=duration,
                        threaded=False
                    )
                except Exception as e:
                    logger.debug(f"Erro interno win10toast: {str(e)}")
            
            import threading
            thread = threading.Thread(target=show_toast)
            thread.daemon = True
            thread.start()
            
            return True
            
        except ImportError:
            return False
        except Exception as e:
            logger.debug(f"Erro win10toast: {str(e)}")
            return False
    
    def _try_powershell_notification(self, title, message, duration, notification_type):
        """Notificação usando PowerShell (Windows 7+)"""
        try:
            import subprocess
            
            # Script PowerShell para criar balloon tip
            ps_script = f'''
            Add-Type -AssemblyName System.Windows.Forms
            try {{
                $notification = New-Object System.Windows.Forms.NotifyIcon
                $notification.Icon = [System.Drawing.SystemIcons]::Information
                
                $balloonIcon = switch ("{notification_type}") {{
                    "error" {{ [System.Windows.Forms.ToolTipIcon]::Error }}
                    "warning" {{ [System.Windows.Forms.ToolTipIcon]::Warning }}
                    default {{ [System.Windows.Forms.ToolTipIcon]::Info }}
                }}
                
                $notification.BalloonTipIcon = $balloonIcon
                $notification.BalloonTipTitle = "{title}"
                $notification.BalloonTipText = "{message}"
                $notification.Visible = $true
                $notification.ShowBalloonTip({duration * 1000})
                
                Start-Sleep -Seconds {duration}
                $notification.Dispose()
            }} catch {{
                Write-Host "Erro na notificação: $_"
            }}
            '''
            
            # Executa PowerShell em background
            def run_powershell():
                try:
                    subprocess.run([
                        "powershell.exe", 
                        "-WindowStyle", "Hidden",
                        "-ExecutionPolicy", "Bypass",
                        "-Command", ps_script
                    ], creationflags=subprocess.CREATE_NO_WINDOW, timeout=duration + 5)
                except Exception as e:
                    logger.debug(f"Erro executando PowerShell: {str(e)}")
            
            import threading
            thread = threading.Thread(target=run_powershell)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro PowerShell: {str(e)}")
            return False
    
    def _try_balloon_tip_notification(self, title, message, duration, notification_type):
        """Notificação usando Windows API diretamente (Windows 7+)"""
        try:
            import ctypes
            from ctypes import wintypes, Structure, c_int, c_uint, c_char_p, c_wchar_p
            
            # Estruturas necessárias para a API
            class NOTIFYICONDATA(Structure):
                _fields_ = [
                    ("cbSize", c_uint),
                    ("hWnd", wintypes.HWND),
                    ("uID", c_uint),
                    ("uFlags", c_uint),
                    ("uCallbackMessage", c_uint),
                    ("hIcon", wintypes.HICON),
                    ("szTip", c_wchar_p),
                    ("dwState", c_uint),
                    ("dwStateMask", c_uint),
                    ("szInfo", c_wchar_p),
                    ("uVersion", c_uint),
                    ("szInfoTitle", c_wchar_p),
                    ("dwInfoFlags", c_uint),
                ]
            
            def show_balloon():
                try:
                    # Constantes
                    NIF_MESSAGE = 0x01
                    NIF_ICON = 0x02
                    NIF_TIP = 0x04
                    NIF_INFO = 0x10
                    NIM_ADD = 0x00
                    NIM_DELETE = 0x02
                    
                    # Ícones baseados no tipo
                    icon_flags = {
                        "info": 0x01,      # NIIF_INFO
                        "warning": 0x02,   # NIIF_WARNING  
                        "error": 0x03,     # NIIF_ERROR
                        "success": 0x01    # NIIF_INFO
                    }
                    
                    shell32 = ctypes.windll.shell32
                    user32 = ctypes.windll.user32
                    
                    # Cria estrutura
                    nid = NOTIFYICONDATA()
                    nid.cbSize = ctypes.sizeof(NOTIFYICONDATA)
                    nid.hWnd = user32.GetConsoleWindow()
                    nid.uID = 1
                    nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP | NIF_INFO
                    nid.szTip = "Print Management System"
                    nid.szInfo = message[:255]  # Limita tamanho
                    nid.szInfoTitle = title[:63]  # Limita tamanho
                    nid.dwInfoFlags = icon_flags.get(notification_type, 0x01)
                    
                    # Adiciona ícone
                    shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))
                    
                    # Aguarda e remove
                    import time
                    time.sleep(duration)
                    shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
                    
                except Exception as e:
                    logger.debug(f"Erro interno balloon tip: {str(e)}")
            
            import threading
            thread = threading.Thread(target=show_balloon)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro balloon tip: {str(e)}")
            return False
    
    def _try_messagebox_notification(self, title, message, duration, notification_type):
        """Último recurso: MessageBox temporário"""
        try:
            import ctypes
            
            # Tipos de ícone
            icon_types = {
                "info": 0x40,      # MB_ICONINFORMATION
                "warning": 0x30,   # MB_ICONWARNING
                "error": 0x10,     # MB_ICONERROR
                "success": 0x40    # MB_ICONINFORMATION
            }
            
            icon = icon_types.get(notification_type, 0x40)
            
            def show_msgbox():
                try:
                    # MessageBox com timeout (só funciona em algumas versões)
                    try:
                        ctypes.windll.user32.MessageBoxTimeoutW(
                            None,
                            message,
                            title,
                            icon | 0x40000,  # MB_TOPMOST
                            0,
                            duration * 1000
                        )
                    except AttributeError:
                        # Fallback para MessageBox normal
                        ctypes.windll.user32.MessageBoxW(
                            None,
                            f"{message}\n\n(Esta janela deve ser fechada manualmente)",
                            title,
                            icon
                        )
                except Exception as e:
                    logger.debug(f"Erro MessageBox: {str(e)}")
            
            import threading
            thread = threading.Thread(target=show_msgbox)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro geral MessageBox: {str(e)}")
            return False
    
    # MÉTODOS MACOS
    def _try_terminal_notifier_notification(self, title, message, duration, notification_type):
        """Notificação usando terminal-notifier (macOS)"""
        try:
            import subprocess
            
            cmd = [
                "terminal-notifier",
                "-title", title,
                "-message", message,
                "-timeout", str(duration)
            ]
            
            # Adiciona som baseado no tipo
            if notification_type == "error":
                cmd.extend(["-sound", "Basso"])
            elif notification_type == "warning":
                cmd.extend(["-sound", "Sosumi"])
            else:
                cmd.extend(["-sound", "default"])
            
            subprocess.run(cmd, capture_output=True, timeout=10)
            return True
            
        except Exception as e:
            logger.debug(f"Erro terminal-notifier: {str(e)}")
            return False
    
    def _try_osascript_notification(self, title, message, duration, notification_type):
        """Notificação usando osascript (macOS nativo)"""
        try:
            import subprocess
            
            # Script AppleScript para notificação
            script = f'display notification "{message}" with title "{title}"'
            
            subprocess.run([
                "osascript", "-e", script
            ], capture_output=True, timeout=10)
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro osascript: {str(e)}")
            return False
    
    # MÉTODOS LINUX
    def _try_notify_send_notification(self, title, message, duration, notification_type):
        """Notificação usando notify-send (Linux libnotify)"""
        try:
            import subprocess
            
            # Ícones baseados no tipo
            icons = {
                "info": "dialog-information",
                "success": "dialog-information",
                "warning": "dialog-warning",
                "error": "dialog-error"
            }
            
            icon = icons.get(notification_type, "dialog-information")
            
            cmd = [
                "notify-send",
                "--expire-time", str(duration * 1000),
                "--icon", icon,
                title,
                message
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=10)
            return True
            
        except Exception as e:
            logger.debug(f"Erro notify-send: {str(e)}")
            return False
    
    def _try_zenity_notification(self, title, message, duration, notification_type):
        """Notificação usando zenity (GNOME)"""
        try:
            import subprocess
            
            # Tipos de zenity
            zenity_types = {
                "info": "--info",
                "success": "--info",
                "warning": "--warning",
                "error": "--error"
            }
            
            zenity_type = zenity_types.get(notification_type, "--info")
            
            cmd = [
                "zenity",
                zenity_type,
                "--title", title,
                "--text", message,
                "--timeout", str(duration)
            ]
            
            subprocess.run(cmd, capture_output=True, timeout=duration + 5)
            return True
            
        except Exception as e:
            logger.debug(f"Erro zenity: {str(e)}")
            return False
    
    def _try_kdialog_notification(self, title, message, duration, notification_type):
        """Notificação usando kdialog (KDE)"""
        try:
            import subprocess
            
            # Tipos do kdialog
            kdialog_types = {
                "info": "--msgbox",
                "success": "--msgbox", 
                "warning": "--sorry",
                "error": "--error"
            }
            
            kdialog_type = kdialog_types.get(notification_type, "--msgbox")
            
            cmd = [
                "kdialog",
                kdialog_type,
                f"{title}\n\n{message}",
                "--title", title
            ]
            
            # kdialog não tem timeout nativo, então executa em background
            def run_kdialog():
                try:
                    process = subprocess.Popen(cmd)
                    import time
                    time.sleep(duration)
                    try:
                        process.terminate()
                    except:
                        pass
                except Exception as e:
                    logger.debug(f"Erro interno kdialog: {str(e)}")
            
            import threading
            thread = threading.Thread(target=run_kdialog)
            thread.daemon = True
            thread.start()
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro kdialog: {str(e)}")
            return False
    
    # MÉTODO CONSOLE (UNIVERSAL)
    def _show_console_notification(self, title, message, notification_type):
        """Exibe notificação no console como último recurso"""
        try:
            # Caracteres Unicode para diferentes tipos
            icons = {
                "info": "ℹ️",
                "success": "✅", 
                "warning": "⚠️",
                "error": "❌"
            }
            
            icon = icons.get(notification_type, "•")
            
            # Cria uma moldura para destacar
            border = "=" * 60
            print(f"\n{border}")
            print(f"{icon} {title.upper()}")
            print(f"{border}")
            print(f"{message}")
            print(f"{border}\n")
            
        except UnicodeError:
            # Fallback para sistemas que não suportam Unicode
            try:
                simple_icons = {
                    "info": "[INFO]",
                    "success": "[OK]", 
                    "warning": "[WARNING]",
                    "error": "[ERROR]"
                }
                
                icon = simple_icons.get(notification_type, "[NOTIFICATION]")
                
                border = "-" * 50
                print(f"\n{border}")
                print(f"{icon} {title}")
                print(f"{border}")
                print(f"{message}")
                print(f"{border}\n")
                
            except Exception:
                # Último recurso absoluto
                logger.info(f"NOTIFICATION: [{notification_type.upper()}] {title} - {message}")
    
    # MÉTODO PARA INSTALAR DEPENDÊNCIAS OPCIONAIS
    def install_optional_dependencies(self):
        """Tenta instalar dependências opcionais para melhorar as notificações"""
        try:
            import subprocess
            import sys
            
            packages_to_try = []
            
            if self.system == "windows":
                # Para Windows, tenta instalar as melhores opções
                if not self.notification_methods.get('plyer', False):
                    packages_to_try.append('plyer')
                if not self.notification_methods.get('win10toast', False):
                    packages_to_try.append('win10toast')
            
            elif self.system in ["darwin", "linux"]:
                # Para macOS e Linux, plyer é geralmente suficiente
                if not self.notification_methods.get('plyer', False):
                    packages_to_try.append('plyer')
            
            for package in packages_to_try:
                try:
                    logger.info(f"Tentando instalar {package} para melhorar notificações...")
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", package],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    
                    if result.returncode == 0:
                        logger.info(f"{package} instalado com sucesso")
                        # Atualiza métodos disponíveis
                        self.notification_methods = self._detect_available_methods()
                    else:
                        logger.warning(f"Falha ao instalar {package}: {result.stderr}")
                        
                except Exception as e:
                    logger.warning(f"Erro ao instalar {package}: {str(e)}")
            
            return len(packages_to_try) > 0
            
        except Exception as e:
            logger.error(f"Erro ao instalar dependências opcionais: {str(e)}")
            return False

class PrinterCardPanel(wx.Panel):
    """Painel de card para exibir uma impressora"""
    
    def __init__(self, parent, printer, on_select=None):
        """
        Inicializa o painel de card
        
        Args:
            parent: Painel pai
            printer: Impressora a ser exibida
            on_select: Callback para seleção (opcional)
        """
        super().__init__(parent, style=wx.BORDER_NONE)
        
        self.printer = printer
        self.on_select = on_select
        
        # Define cor de fundo (cinza escuro)
        self.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        # Eventos para hover e clique
        self.hover = False
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        
        if on_select:
            self.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa a interface do usuário do card"""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone da impressora (esquerda)
        printer_icon_path = ResourceManager.get_image_path("printer.png")
        
        if os.path.exists(printer_icon_path):
            printer_icon = wx.StaticBitmap(
                self,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(32, 32)
            )
            # Adiciona eventos de hover e clique ao ícone
            self._add_child_events(printer_icon)
            main_sizer.Add(printer_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        # Painel de informações (centro)
        info_panel = wx.Panel(self)
        info_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Nome da impressora
        printer_name = wx.StaticText(info_panel, label=self.printer.name)
        printer_name.SetForegroundColour(wx.WHITE)
        printer_name.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        # Adiciona eventos de hover e clique ao nome
        self._add_child_events(printer_name)
        info_sizer.Add(printer_name, 0, wx.BOTTOM, 5)
        
        # Detalhes da impressora
        # Linha 1: MAC e IP
        details_line1 = ""
        if hasattr(self.printer, 'mac_address') and self.printer.mac_address:
            details_line1 = f"MAC: {self.printer.mac_address}"
        
        if hasattr(self.printer, 'ip') and self.printer.ip:
            if details_line1:
                details_line1 += " | "
            details_line1 += f"IP: {self.printer.ip}"
            
        details1 = wx.StaticText(info_panel, label=details_line1 or "Impressora local")
        details1.SetForegroundColour(wx.Colour(180, 180, 180))
        details1.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        # Adiciona eventos de hover e clique aos detalhes
        self._add_child_events(details1)
        info_sizer.Add(details1, 0, wx.BOTTOM, 3)
        
        # Linha 2: Modelo e localização
        details_line2 = ""
        if hasattr(self.printer, 'model') and self.printer.model:
            details_line2 = f"Modelo: {self.printer.model}"
        
        if hasattr(self.printer, 'location') and self.printer.location:
            if details_line2:
                details_line2 += " | "
            details_line2 += f"Local: {self.printer.location}"
            
        if details_line2:
            details2 = wx.StaticText(info_panel, label=details_line2)
            details2.SetForegroundColour(wx.Colour(180, 180, 180))
            details2.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            # Adiciona eventos de hover e clique aos detalhes
            self._add_child_events(details2)
            info_sizer.Add(details2, 0)
        
        # Adiciona eventos ao painel de informações
        self._add_child_events(info_panel)
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Indicador de status (direita)
        status_panel = wx.Panel(self, size=(20, 20))
        status_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        def on_status_paint(event):
            dc = wx.PaintDC(status_panel)
            
            # Determina a cor baseada no status, verificando os atributos de forma segura
            is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
            is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
            
            if is_online and is_ready:
                # Verde se estiver completamente pronta (online e idle)
                color = wx.Colour(40, 167, 69)  # Verde
            elif is_online:
                # Amarelo se estiver online mas não idle
                color = wx.Colour(255, 193, 7)  # Amarelo
            else:
                # Vermelho se não estiver online
                color = wx.Colour(220, 53, 69)  # Vermelho
            
            # Desenha o indicador de status (círculo)
            dc.SetBrush(wx.Brush(color))
            dc.SetPen(wx.Pen(color))
            dc.DrawCircle(10, 10, 6)
        
        status_panel.Bind(wx.EVT_PAINT, on_status_paint)
        # Adiciona eventos ao painel de status
        self._add_child_events(status_panel)
        main_sizer.Add(status_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        
        # Se tem callback de seleção, adiciona um texto de dica
        if self.on_select:
            tip_text = wx.StaticText(self, label="Clique para detalhes")
            tip_text.SetForegroundColour(wx.Colour(180, 180, 180))
            # Adicionar os eventos de hover e clique ao texto de dica
            self._add_child_events(tip_text)
            main_sizer.Add(tip_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        self.SetSizer(main_sizer)
    
    def _add_child_events(self, widget):
        """
        Adiciona eventos de hover e clique a um widget filho
        
        Args:
            widget: Widget ao qual adicionar eventos
        """
        if self.on_select:
            widget.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        
        widget.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        widget.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
        
        # Adicionar recursivamente a todos os filhos
        for child in widget.GetChildren():
            self._add_child_events(child)
    
    def _update_hover_state(self, is_hover):
        """
        Atualiza o estado de hover para todos os elementos do card
        
        Args:
            is_hover: True se estiver em estado de hover, False caso contrário
        """
        self.hover = is_hover
        
        # Atualiza a cor de fundo de todos os painéis filhos
        bg_color = wx.Colour(45, 45, 45) if is_hover else wx.Colour(35, 35, 35)
        self.SetBackgroundColour(bg_color)
        
        # Atualiza a cor de todos os painéis filhos
        for child in self.GetChildren():
            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(bg_color)
        
        self.Refresh()
    
    def on_enter(self, event):
        """Manipula o evento de mouse sobre o card"""
        # Captura o mouse para evitar problemas com leave/enter entre filhos
        if not self.hover:
            self._update_hover_state(True)
            
            # Propaga o evento
            event.Skip()
    
    def on_leave(self, event):
        """Manipula o evento de mouse saindo do card"""
        # Verifica se o mouse ainda está dentro do card (pode estar em um filho)
        screen_pos = wx.GetMousePosition()
        client_pos = self.ScreenToClient(screen_pos)
        
        # Se o mouse saiu realmente do card (e não apenas entrou em um filho)
        if not self.GetClientRect().Contains(client_pos):
            self._update_hover_state(False)
        
        # Propaga o evento
        event.Skip()
    
    def on_click(self, event):
        """Manipula o clique no card"""
        if self.on_select:
            self.on_select(self.printer)
    
    def on_paint(self, event):
        """Redesenha o card com cantos arredondados e efeito de hover"""
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        
        rect = self.GetClientRect()
        
        # Cor de fundo baseada no estado de hover
        if self.hover:
            bg_color = wx.Colour(45, 45, 45)  # Cinza mais claro no hover
        else:
            bg_color = wx.Colour(35, 35, 35)  # Cor normal
        
        # Desenha o fundo com cantos arredondados
        path = gc.CreatePath()
        path.AddRoundedRectangle(0, 0, rect.width, rect.height, 8)
        
        gc.SetBrush(wx.Brush(bg_color))
        gc.SetPen(wx.Pen(wx.Colour(60, 60, 60), 1))  # Borda sutil
        
        gc.DrawPath(path)

class PrinterDetailsDialog(wx.Dialog):
    """Diálogo para exibir detalhes da impressora"""
    
    def __init__(self, parent, printer, api_client):
        """
        Inicializa o diálogo de detalhes
        
        Args:
            parent: Janela pai
            printer: Impressora a ser exibida
            api_client: Cliente da API
        """
        super().__init__(
            parent,
            title=f"Detalhes da Impressora: {printer.name}",
            size=(700, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.printer = printer
        self.api_client = api_client
        self.details_loaded = False
        
        # Cores para temas
        self.colors = {"bg_color": wx.Colour(18, 18, 18), 
                      "panel_bg": wx.Colour(25, 25, 25),
                      "card_bg": wx.Colour(35, 35, 35),
                      "accent_color": wx.Colour(255, 90, 36),
                      "text_color": wx.WHITE,
                      "text_secondary": wx.Colour(180, 180, 180),
                      "border_color": wx.Colour(45, 45, 45),
                      "success_color": wx.Colour(40, 167, 69),
                      "error_color": wx.Colour(220, 53, 69),
                      "warning_color": wx.Colour(255, 193, 7)}
        
        # Aplica o tema ao diálogo
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self._init_ui()
        
        # Centraliza o diálogo
        self.CenterOnParent()
        
        # Carrega os detalhes da impressora
        self._load_printer_details()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Configura o painel principal
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(self.colors["bg_color"])
        
        # Aplica personalização de scrollbar após inicialização
        if wx.Platform == '__WXMSW__':
            try:
                import win32gui
                import win32con
                
                def customize_scrollbar():
                    wx.CallAfter(self._customize_scrollbar_colors)
                
                wx.CallLater(100, customize_scrollbar)
            except ImportError:
                pass
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cabeçalho
        header_panel = wx.Panel(self.panel)
        header_panel.SetBackgroundColour(self.colors["card_bg"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone da impressora
        printer_icon_path = ResourceManager.get_image_path("printer.png")
        
        if os.path.exists(printer_icon_path):
            printer_icon = wx.StaticBitmap(
                header_panel,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(48, 48)
            )
            header_sizer.Add(printer_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 15)
        
        # Informações básicas
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Nome da impressora
        printer_name = wx.StaticText(header_panel, label=self.printer.name)
        printer_name.SetForegroundColour(self.colors["text_color"])
        printer_name.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(printer_name, 0, wx.BOTTOM, 8)
        
        # Modelo
        if self.printer.model:
            model_text = wx.StaticText(header_panel, label=f"Modelo: {self.printer.model}")
            model_text.SetForegroundColour(self.colors["text_secondary"])
            model_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            info_sizer.Add(model_text, 0, wx.BOTTOM, 5)
        
        # Estado
        if self.printer.state:
            state_text = wx.StaticText(header_panel, label=f"Estado: {self.printer.state}")
            state_text.SetForegroundColour(self.colors["text_secondary"])
            state_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            info_sizer.Add(state_text, 0)
        
        header_sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, 15)
        
        # Indicador de status (direita)
        # Determina a cor baseada no status, verificando os atributos de forma segura
        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
        
        if is_online and is_ready:
            # Verde se estiver completamente pronta (online e idle)
            status_color = self.colors["success_color"]
        elif is_online:
            # Amarelo se estiver online mas não idle
            status_color = self.colors["warning_color"]
        else:
            # Vermelho se não estiver online
            status_color = self.colors["error_color"]
        
        # Cria um bitmap para o status
        status_bitmap = wx.Bitmap(20, 20)
        dc = wx.MemoryDC()
        dc.SelectObject(status_bitmap)
        
        # Define fundo transparente
        dc.SetBackground(wx.Brush(self.colors["card_bg"]))
        dc.Clear()
        
        # Desenha o círculo de status
        dc.SetBrush(wx.Brush(status_color))
        dc.SetPen(wx.Pen(status_color))
        dc.DrawCircle(10, 10, 8)
        
        # Finaliza o desenho
        dc.SelectObject(wx.NullBitmap)
        
        # Cria e adiciona o bitmap ao layout
        status_icon = wx.StaticBitmap(header_panel, bitmap=status_bitmap)
        header_sizer.Add(status_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        
        header_panel.SetSizer(header_sizer)
        
        # Adiciona um borda arredondada ao header
        def on_header_paint(event):
            dc = wx.BufferedPaintDC(header_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = header_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in header_panel.GetChildren():
                child.Refresh()
            
        header_panel.Bind(wx.EVT_PAINT, on_header_paint)
        header_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Cria um panel personalizado para abrigar o notebook com tabs estilizadas
        tabs_container = wx.Panel(self.panel)
        tabs_container.SetBackgroundColour(self.colors["bg_color"])
        tabs_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cria um panel para as tabs
        tab_bar = wx.Panel(tabs_container)
        tab_bar.SetBackgroundColour(self.colors["card_bg"])
        tab_bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Define as tabs
        tab_names = ["Resumo", "Conectividade", "Atributos", "Suprimentos", "Diagnóstico"]
        self.tab_buttons = []
        self.tab_panels = []
        
        # Cria os botões das tabs com estilo moderno
        for i, tab_name in enumerate(tab_names):
            tab_button = wx.Panel(tab_bar)
            tab_button.SetBackgroundColour(self.colors["card_bg"])
            tab_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Texto da tab
            tab_text = wx.StaticText(tab_button, label=tab_name)
            tab_text.SetForegroundColour(self.colors["text_color"])
            tab_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            
            tab_button_sizer.Add(tab_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
            tab_button.SetSizer(tab_button_sizer)
            
            # Armazena dados para selecionar a tab
            tab_button.index = i
            tab_button.selected = (i == 0)  # A primeira tab começa selecionada
            
            # Eventos de clique e hover
            def on_tab_click(evt, button=tab_button):
                self._select_tab(button.index)
            
            def on_tab_enter(evt, button=tab_button):
                if not button.selected:
                    button.SetBackgroundColour(wx.Colour(40, 40, 40))
                    button.Refresh()
            
            def on_tab_leave(evt, button=tab_button):
                if not button.selected:
                    button.SetBackgroundColour(self.colors["card_bg"])
                    button.Refresh()
            
            # Vincula eventos ao painel da tab
            tab_button.Bind(wx.EVT_LEFT_DOWN, on_tab_click)
            tab_button.Bind(wx.EVT_ENTER_WINDOW, on_tab_enter)
            tab_button.Bind(wx.EVT_LEAVE_WINDOW, on_tab_leave)
            
            # Vincula eventos ao texto da tab também
            tab_text.Bind(wx.EVT_LEFT_DOWN, on_tab_click)
            tab_text.Bind(wx.EVT_ENTER_WINDOW, on_tab_enter)
            tab_text.Bind(wx.EVT_LEAVE_WINDOW, on_tab_leave)
            
            # Destaca a tab selecionada
            if i == 0:
                tab_button.SetBackgroundColour(self.colors["accent_color"])
                tab_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            tab_bar_sizer.Add(tab_button, 0, wx.RIGHT, 1)
            self.tab_buttons.append(tab_button)
        
        tab_bar.SetSizer(tab_bar_sizer)
        tabs_sizer.Add(tab_bar, 0, wx.EXPAND)
        
        # Cria os painéis de conteúdo
        # Guia de resumo
        self.summary_panel = self._create_tab_panel(tabs_container)
        summary_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.summary_loading_text = wx.StaticText(self.summary_panel, label="Carregando informações da impressora...")
        self.summary_loading_text.SetForegroundColour(self.colors["text_color"])
        summary_sizer.Add(self.summary_loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.summary_panel.SetSizer(summary_sizer)
        
        # Guia de informações de conectividade
        self.connectivity_panel = self._create_tab_panel(tabs_container)
        connectivity_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cria um painel "card" para as informações de conectividade
        connectivity_card = wx.Panel(self.connectivity_panel)
        connectivity_card.SetBackgroundColour(self.colors["card_bg"])
        connectivity_card_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # IP
        if self.printer.ip:
            ip_panel = self._create_info_row(connectivity_card, "IP:", self.printer.ip)
            connectivity_card_sizer.Add(ip_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # MAC Address
        if self.printer.mac_address:
            mac_panel = self._create_info_row(connectivity_card, "MAC Address:", self.printer.mac_address)
            connectivity_card_sizer.Add(mac_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # URI
        if self.printer.uri:
            uri_panel = self._create_info_row(connectivity_card, "URI:", self.printer.uri)
            connectivity_card_sizer.Add(uri_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Status
        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
        is_usable = is_online and is_ready
        
        status_text = "Pronta" if is_usable else "Indisponível"
        status_panel = self._create_info_row(connectivity_card, "Status:", status_text)
        connectivity_card_sizer.Add(status_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Estado
        if self.printer.state:
            state_panel = self._create_info_row(connectivity_card, "Estado:", self.printer.state)
            connectivity_card_sizer.Add(state_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Portas
        if self.printer.attributes and 'ports' in self.printer.attributes:
            ports = ", ".join(str(p) for p in self.printer.attributes['ports'])
            ports_panel = self._create_info_row(connectivity_card, "Portas:", ports)
            connectivity_card_sizer.Add(ports_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        connectivity_card.SetSizer(connectivity_card_sizer)
        
        # Adiciona borda arredondada ao card
        def on_card_paint(event):
            dc = wx.BufferedPaintDC(connectivity_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = connectivity_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in connectivity_card.GetChildren():
                child.Refresh()
        
        connectivity_card.Bind(wx.EVT_PAINT, on_card_paint)
        connectivity_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        connectivity_sizer.Add(connectivity_card, 0, wx.EXPAND | wx.ALL, 10)
        
        # Botão para diagnóstico (somente se tiver IP)
        if self.printer.ip:
            diagnostic_button = create_styled_button(
                self.connectivity_panel,
                "Executar Diagnóstico",
                self.colors["accent_color"],
                self.colors["text_color"],
                wx.Colour(255, 120, 70),
                (-1, 36)
            )
            diagnostic_button.Bind(wx.EVT_BUTTON, self._on_diagnostic)
            
            connectivity_sizer.Add(diagnostic_button, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        
        self.connectivity_panel.SetSizer(connectivity_sizer)
        
        # Guia de atributos
        self.attributes_panel = self._create_tab_panel(tabs_container)
        self.attributes_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.loading_text = wx.StaticText(self.attributes_panel, label="Carregando atributos da impressora...")
        self.loading_text.SetForegroundColour(self.colors["text_color"])
        self.attributes_sizer.Add(self.loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.attributes_panel.SetSizer(self.attributes_sizer)
        
        # Guia de suprimentos
        self.supplies_panel = self._create_tab_panel(tabs_container)
        self.supplies_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.supplies_loading_text = wx.StaticText(self.supplies_panel, label="Carregando informações de suprimentos...")
        self.supplies_loading_text.SetForegroundColour(self.colors["text_color"])
        self.supplies_sizer.Add(self.supplies_loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.supplies_panel.SetSizer(self.supplies_sizer)
        
        # Guia de diagnóstico
        self.diagnostic_panel = self._create_tab_panel(tabs_container)
        self.diagnostic_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Card para as instruções de diagnóstico
        diagnostic_card = wx.Panel(self.diagnostic_panel)
        diagnostic_card.SetBackgroundColour(self.colors["card_bg"])
        diagnostic_card_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de instrução
        diagnostic_text = wx.StaticText(
            diagnostic_card, 
            label="Execute um diagnóstico na guia de Conectividade para verificar o status da impressora."
        )
        diagnostic_text.SetForegroundColour(self.colors["text_color"])
        diagnostic_text.Wrap(500)  # Wrap text para manter uma boa apresentação
        diagnostic_card_sizer.Add(diagnostic_text, 0, wx.ALL | wx.CENTER, 20)
        
        diagnostic_card.SetSizer(diagnostic_card_sizer)
        
        # Adiciona borda arredondada ao card
        def on_diagnostic_card_paint(event):
            dc = wx.BufferedPaintDC(diagnostic_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = diagnostic_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in diagnostic_card.GetChildren():
                child.Refresh()
        
        diagnostic_card.Bind(wx.EVT_PAINT, on_diagnostic_card_paint)
        diagnostic_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.diagnostic_sizer.Add(diagnostic_card, 0, wx.EXPAND | wx.ALL, 15)
        
        self.diagnostic_panel.SetSizer(self.diagnostic_sizer)
        
        # Adiciona os paineis à lista
        self.tab_panels = [
            self.summary_panel,
            self.connectivity_panel,
            self.attributes_panel,
            self.supplies_panel,
            self.diagnostic_panel
        ]
        
        # Mostra apenas o primeiro painel por padrão
        for i, panel in enumerate(self.tab_panels):
            tabs_sizer.Add(panel, 1, wx.EXPAND)
            if i > 0:
                panel.Hide()
        
        tabs_container.SetSizer(tabs_sizer)
        main_sizer.Add(tabs_container, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para atualizar
        self.refresh_button = create_styled_button(
            self.panel,
            "Atualizar Informações",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(255, 120, 70),
            (-1, 36)
        )
        self.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)

        button_sizer.Add(self.refresh_button, 0, wx.RIGHT, 10)

        # Botão para fechar
        close_button = create_styled_button(
            self.panel,
            "Fechar",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (-1, 36)
        )
        close_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL))

        button_sizer.Add(close_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
        
        # Carrega os detalhes da impressora
        self._load_printer_details()
    
    def _customize_scrollbar_colors(self):
        """Personaliza as cores da scrollbar para tema escuro"""
        try:
            if wx.Platform == '__WXMSW__':
                # Tenta aplicar tema escuro via win32
                try:
                    import win32gui
                    import win32con
                    import win32api
                    import ctypes
                    from ctypes import wintypes
                    
                    # Aplica para todos os ScrolledWindows nos tabs
                    scroll_windows = [
                        self.summary_panel,
                        self.connectivity_panel, 
                        self.attributes_panel,
                        self.supplies_panel,
                        self.diagnostic_panel
                    ]
                    
                    for scroll_window in scroll_windows:
                        if hasattr(scroll_window, 'GetHandle'):
                            hwnd = scroll_window.GetHandle()
                            
                            # Tenta habilitar tema escuro no controle
                            # Este é o método mais moderno para Windows 10/11
                            DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                            DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
                            
                            def try_set_dark_mode(attribute):
                                try:
                                    dwmapi = ctypes.windll.dwmapi
                                    value = ctypes.c_int(1)
                                    dwmapi.DwmSetWindowAttribute(
                                        hwnd,
                                        attribute,
                                        ctypes.byref(value),
                                        ctypes.sizeof(value)
                                    )
                                    return True
                                except:
                                    return False
                            
                            # Tenta ambas as versões do atributo
                            if not try_set_dark_mode(DWMWA_USE_IMMERSIVE_DARK_MODE):
                                try_set_dark_mode(DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1)
                            
                            # Método alternativo: força tema escuro via SetWindowTheme
                            try:
                                uxtheme = ctypes.windll.uxtheme
                                uxtheme.SetWindowTheme(hwnd, "DarkMode_Explorer", None)
                            except:
                                pass
                            
                            # Força atualização da janela
                            try:
                                user32 = ctypes.windll.user32
                                user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                                0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
                            except:
                                pass
                        
                except ImportError:
                    # Se win32 não estiver disponível, tenta método alternativo
                    pass
            
            elif wx.Platform == '__WXGTK__':
                # Para GTK, tenta aplicar estilo escuro
                try:
                    import gi
                    gi.require_version('Gtk', '3.0')
                    from gi.repository import Gtk
                    
                    # Aplica tema escuro no GTK
                    settings = Gtk.Settings.get_default()
                    settings.set_property('gtk-application-prefer-dark-theme', True)
                except:
                    pass
            
            elif wx.Platform == '__WXMAC__':
                # Para macOS, o tema escuro é controlado pelo sistema
                # Força refresh dos controles
                scroll_windows = [
                    self.summary_panel,
                    self.connectivity_panel, 
                    self.attributes_panel,
                    self.supplies_panel,
                    self.diagnostic_panel
                ]
                
                for scroll_window in scroll_windows:
                    scroll_window.Refresh()
                
        except Exception as e:
            # Falha silenciosa para não quebrar a aplicação
            pass
        
        # Método adicional: tenta personalizar via CSS no Windows
        if wx.Platform == '__WXMSW__':
            try:
                # Aplica estilo personalizado aos ScrolledWindows
                scroll_windows = [
                    self.summary_panel,
                    self.connectivity_panel, 
                    self.attributes_panel,
                    self.supplies_panel,
                    self.diagnostic_panel
                ]
                
                for scroll_window in scroll_windows:
                    scroll_window.SetBackgroundColour(self.colors["panel_bg"])
                    scroll_window.Refresh()
                    scroll_window.Update()
                
                # Agenda uma segunda tentativa
                wx.CallLater(500, self._apply_scrollbar_theme)
                
            except:
                pass

    def _apply_scrollbar_theme(self):
        """Segunda tentativa de aplicar tema na scrollbar"""
        try:
            if wx.Platform == '__WXMSW__':
                import ctypes
                from ctypes import wintypes
                
                scroll_windows = [
                    self.summary_panel,
                    self.connectivity_panel, 
                    self.attributes_panel,
                    self.supplies_panel,
                    self.diagnostic_panel
                ]
                
                for scroll_window in scroll_windows:
                    if hasattr(scroll_window, 'GetHandle'):
                        hwnd = scroll_window.GetHandle()
                        
                        # Obtém todos os controles filhos (incluindo scrollbars)
                        def enum_child_proc(child_hwnd, lparam):
                            try:
                                # Obtém informações da janela
                                user32 = ctypes.windll.user32
                                
                                # Aplica tema escuro
                                try:
                                    uxtheme = ctypes.windll.uxtheme
                                    uxtheme.SetWindowTheme(child_hwnd, "DarkMode_CFD", None)
                                except:
                                    try:
                                        uxtheme.SetWindowTheme(child_hwnd, "DarkMode_Explorer", None)
                                    except:
                                        pass
                                
                                # Força redraw
                                user32.InvalidateRect(child_hwnd, None, True)
                                user32.UpdateWindow(child_hwnd)
                                
                            except:
                                pass
                            return True
                        
                        # Enumera e aplica tema em todos os filhos
                        enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                        ctypes.windll.user32.EnumChildWindows(hwnd, enum_proc(enum_child_proc), 0)
                
        except Exception as e:
            pass
    
    def _create_tab_panel(self, parent):
        """Cria um painel para uma tab"""
        panel = wx.ScrolledWindow(parent)
        panel.SetBackgroundColour(self.colors["panel_bg"])
        panel.SetScrollRate(0, 10)
        
        # Aplica personalização de scrollbar se no Windows
        if wx.Platform == '__WXMSW__':
            try:
                import win32gui
                import win32con
                
                def customize_panel_scrollbar():
                    wx.CallAfter(self._customize_panel_scrollbar, panel)
                
                wx.CallLater(150, customize_panel_scrollbar)
            except ImportError:
                pass
        
        return panel
    
    def _customize_panel_scrollbar(self, panel):
        """Personaliza scrollbar de um painel específico"""
        try:
            if wx.Platform == '__WXMSW__' and hasattr(panel, 'GetHandle'):
                import ctypes
                from ctypes import wintypes
                
                hwnd = panel.GetHandle()
                
                # Aplica tema escuro
                try:
                    uxtheme = ctypes.windll.uxtheme
                    uxtheme.SetWindowTheme(hwnd, "DarkMode_Explorer", None)
                except:
                    pass
                
                # Força atualização
                try:
                    user32 = ctypes.windll.user32
                    user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                    0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
                except:
                    pass
                    
        except Exception:
            pass
    
    def _select_tab(self, index):
        """Seleciona uma tab pelo índice"""
        # Atualiza os botões das tabs
        for i, button in enumerate(self.tab_buttons):
            if i == index:
                button.selected = True
                button.SetBackgroundColour(self.colors["accent_color"])
                button.GetChildren()[0].SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            else:
                button.selected = False
                button.SetBackgroundColour(self.colors["card_bg"])
                button.GetChildren()[0].SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            button.Refresh()
        
        # Mostra o painel correto
        for i, panel in enumerate(self.tab_panels):
            if i == index:
                panel.Show()
            else:
                panel.Hide()
        
        # Atualiza o layout
        self.panel.Layout()
    
    def _create_info_row(self, parent, label, value):
        """
        Cria uma linha de informação
        
        Args:
            parent: Painel pai
            label: Rótulo
            value: Valor
            
        Returns:
            wx.Panel: Painel com a linha de informação
        """
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(self.colors["card_bg"])
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Rótulo
        label_ctrl = wx.StaticText(panel, label=label)
        label_ctrl.SetForegroundColour(self.colors["text_color"])
        label_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(label_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        # Valor
        value_ctrl = wx.StaticText(panel, label=str(value))
        value_ctrl.SetForegroundColour(self.colors["text_secondary"])
        
        # Se o valor for longo, adiciona um botão para copiar
        if len(str(value)) > 30:
            value_panel = wx.Panel(panel)
            value_panel.SetBackgroundColour(self.colors["card_bg"])
            value_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Trunca o valor para exibição
            display_value = str(value)[:27] + "..."
            value_ctrl = wx.StaticText(value_panel, label=display_value)
            value_ctrl.SetForegroundColour(self.colors["text_secondary"])
            value_sizer.Add(value_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            
            # Botão para copiar
            copy_button = create_styled_button(
                value_panel,
                "Copiar",
                wx.Colour(60, 60, 60),
                self.colors["text_color"],
                wx.Colour(80, 80, 80),
                (70, 26)
            )
            copy_button.Bind(wx.EVT_BUTTON, lambda evt, v=value: self._copy_to_clipboard(v))
            
            value_sizer.Add(copy_button, 0, wx.ALIGN_CENTER_VERTICAL)
            
            value_panel.SetSizer(value_sizer)
            sizer.Add(value_panel, 1, wx.EXPAND)
        else:
            sizer.Add(value_ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        
        panel.SetSizer(sizer)
        return panel
    
    def _copy_to_clipboard(self, text):
        """
        Copia texto para a área de transferência
        
        Args:
            text: Texto a copiar
        """
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(str(text)))
            wx.TheClipboard.Close()
            
            # Feedback visual
            wx.MessageBox("Copiado para a área de transferência", "Informação", wx.OK | wx.ICON_INFORMATION)
    
    def _on_diagnostic(self, event):
        """Executa diagnóstico da impressora"""
        if not self.printer.ip:
            wx.MessageBox("Impressora sem endereço IP. Não é possível executar diagnóstico.", "Aviso", wx.OK | wx.ICON_WARNING)
            return
            
        # Limpa o painel de diagnóstico
        for child in self.diagnostic_panel.GetChildren():
            child.Destroy()
            
        # Adiciona texto de carregamento
        loading_text = wx.StaticText(self.diagnostic_panel, label="Executando diagnóstico, aguarde...")
        loading_text.SetForegroundColour(self.colors["text_color"])
        self.diagnostic_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 20)
        self.diagnostic_panel.Layout()
        
        # Muda para a guia de diagnóstico
        self._select_tab(4)
        
        # Executa o diagnóstico em uma thread
        try:
            from src.utils.printer_diagnostic import PrinterDiagnostic
            
            # Define o callback para atualizar a UI
            def update_diagnostic(message):
                wx.CallAfter(self._update_diagnostic_ui, message)
                
            # Define o callback para finalizar o diagnóstico
            def on_diagnostic_complete(results):
                wx.CallAfter(self._update_diagnostic_results, results)
                
            # Cria e inicia o diagnóstico
            diagnostic = PrinterDiagnostic(self.printer, update_diagnostic)
            diagnostic.run_diagnostics_async(on_diagnostic_complete)
            
        except ImportError:
            wx.MessageBox("Módulo de diagnóstico não disponível.", "Erro", wx.OK | wx.ICON_ERROR)
            loading_text.Destroy()
        except Exception as e:
            wx.MessageBox(f"Erro ao iniciar diagnóstico: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
            loading_text.Destroy()
    
    def _update_diagnostic_ui(self, message):
        """
        Atualiza a interface do diagnóstico
        
        Args:
            message: Mensagem de progresso
        """
        # Cria um texto para a mensagem
        if not message:
            message = "Erro ao executar diagnóstico!"

        message_text = wx.StaticText(self.diagnostic_panel, label=message)
        message_text.SetForegroundColour(self.colors["text_color"])
        self.diagnostic_sizer.Add(message_text, 0, wx.ALL | wx.LEFT, 10)
        self.diagnostic_panel.Layout()
        
        # Scroll para mostrar a mensagem mais recente
        self.diagnostic_panel.Scroll(0, self.diagnostic_panel.GetVirtualSize().GetHeight())
        
    def _update_diagnostic_results(self, results):
        """
        Atualiza a interface com os resultados do diagnóstico
        
        Args:
            results: Resultados do diagnóstico
        """
        # Limpa o painel de diagnóstico
        for child in self.diagnostic_panel.GetChildren():
            child.Destroy()
            
        # Card para os resultados
        results_card = wx.Panel(self.diagnostic_panel)
        results_card.SetBackgroundColour(self.colors["card_bg"])
        results_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Adiciona o resultado geral
        overall = results.get("overall", {})
        success = overall.get("success", False)
        message = overall.get("message", "Diagnóstico concluído")
        
        # Cor baseada no resultado
        color = self.colors["success_color"] if success else self.colors["error_color"]
        
        # Título do resultado
        result_text = wx.StaticText(results_card, label=f"Resultado: {message}")
        result_text.SetForegroundColour(color)
        result_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        results_sizer.Add(result_text, 0, wx.ALL | wx.CENTER, 15)
        
        # Separador
        separator = wx.StaticLine(results_card, style=wx.LI_HORIZONTAL)
        results_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        
        # Adiciona os resultados detalhados de cada teste
        for test_id, test_result in results.items():
            if test_id != "overall":
                test_panel = self._add_test_result_panel(results_card, test_id, test_result)
                results_sizer.Add(test_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        results_card.SetSizer(results_sizer)
        
        # Adiciona borda arredondada ao card
        def on_results_card_paint(event):
            dc = wx.BufferedPaintDC(results_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = results_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in results_card.GetChildren():
                child.Refresh()
        
        results_card.Bind(wx.EVT_PAINT, on_results_card_paint)
        results_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.diagnostic_sizer.Add(results_card, 0, wx.EXPAND | wx.ALL, 15)
        self.diagnostic_panel.Layout()
    
    def _add_test_result_panel(self, parent, test_id, result):
        """
        Adiciona o painel de resultado de um teste
        
        Args:
            parent: Painel pai
            test_id: ID do teste
            result: Resultado do teste
            
        Returns:
            wx.Panel: Painel de resultado
        """
        # Nome do teste formatado
        test_names = {
            "connectivity": "Teste de Conectividade",
            "port_availability": "Portas Disponíveis",
            "ipp": "IPP/Protocolo de Impressão",
            "print_job": "Teste de Envio de Trabalho"
        }
        test_name = test_names.get(test_id, test_id.replace("_", " ").title())
        
        # Cria um painel para o resultado
        test_panel = wx.Panel(parent)
        test_panel.SetBackgroundColour(self.colors["card_bg"])
        test_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título do teste
        success = result.get("success", False)
        status = "Passou" if success else "Falhou"
        title = wx.StaticText(test_panel, label=f"{test_name}: {status}")
        
        # Cor baseada no resultado
        color = self.colors["success_color"] if success else self.colors["error_color"]
        title.SetForegroundColour(color)
        title.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        test_sizer.Add(title, 0, wx.ALL, 5)
        
        # Mensagem do teste
        message = result.get("message", "")
        if message:
            message_text = wx.StaticText(test_panel, label=message)
            message_text.SetForegroundColour(self.colors["text_secondary"])
            test_sizer.Add(message_text, 0, wx.LEFT | wx.BOTTOM, 5)
        
        # Detalhes do teste
        details = result.get("details", "")
        if details:
            details_text = wx.StaticText(test_panel, label=details)
            details_text.SetForegroundColour(self.colors["text_secondary"])
            details_text.Wrap(parent.GetSize().width - 40)  # Wrap text to fit in panel
            test_sizer.Add(details_text, 0, wx.LEFT | wx.BOTTOM, 5)
        
        test_panel.SetSizer(test_sizer)
        return test_panel
    
    def _load_printer_details(self):
        """Carrega os detalhes da impressora"""
        if not self.printer.ip:
            self._update_printer_details(None)
            return
        
        def on_details_loaded(details):
            """Callback quando os detalhes forem carregados"""
            wx.CallAfter(self._update_printer_details, details)
        
        # Carrega os detalhes em uma thread separada
        try:
            from src.utils.printer_discovery import PrinterDiscovery
            
            # Função para carregar detalhes em uma thread
            def load_details_thread():
                try:
                    discovery = PrinterDiscovery()
                    details = discovery.get_printer_details(self.printer.ip)
                    on_details_loaded(details)
                except Exception as e:
                    logger.error(f"Erro ao carregar detalhes: {str(e)}")
                    on_details_loaded(None)
            
            # Inicia a thread
            thread = threading.Thread(target=load_details_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar carregamento de detalhes: {str(e)}")
            self._update_printer_details(None)
    
    def _update_printer_details(self, details):
        """
        Atualiza todos os painéis com os detalhes da impressora
        
        Args:
            details: Detalhes da impressora
        """
        # Check if the dialog or its main panel is being deleted or doesn't exist
        if not self or not hasattr(self, 'panel') or not self.panel or self.IsBeingDeleted():
            logger.warning("PrinterDetailsDialog ou seu painel principal não existe mais ou está sendo deletado. Abortando atualização da UI.")
            return

        if not details:
            # Safely update loading text labels
            if hasattr(self, 'summary_loading_text') and self.summary_loading_text:
                try:
                    if self.summary_loading_text: # Check it hasn't been set to None
                        self.summary_loading_text.SetLabel("Não foi possível carregar os detalhes da impressora.")
                except wx.PyDeadObjectError:
                    self.summary_loading_text = None # Mark as gone
                
            if hasattr(self, 'loading_text') and self.loading_text:
                try:
                    if self.loading_text:
                        self.loading_text.SetLabel("Não foi possível carregar os atributos da impressora.")
                except wx.PyDeadObjectError:
                    self.loading_text = None
                
            if hasattr(self, 'supplies_loading_text') and self.supplies_loading_text:
                try:
                    if self.supplies_loading_text:
                        self.supplies_loading_text.SetLabel("Não foi possível carregar informações de suprimentos.")
                except wx.PyDeadObjectError:
                    self.supplies_loading_text = None
            
            # Ensure layout is refreshed if elements were expected
            if hasattr(self, 'panel') and self.panel:
                try:
                    self.panel.Layout()
                except wx.PyDeadObjectError:
                    pass # Panel is gone
            return
        
        # Atualiza a impressora com os detalhes
        self.printer.update_from_discovery(details) # This should now include 'is_ready' and 'supplies'
        
        # Safely update each panel
        try:
            # Ensure the target panel for summary exists before updating
            if hasattr(self, 'summary_panel') and self.summary_panel:
                 self._update_summary_panel(details)
            else:
                logger.warning("Painel de resumo não encontrado para atualização.")
        except Exception as e:
            logger.error(f"Erro ao atualizar resumo: {str(e)}", exc_info=True)
            
        try:
            if hasattr(self, 'attributes_panel') and self.attributes_panel:
                self._update_attributes_panel(details)
            else:
                logger.warning("Painel de atributos não encontrado para atualização.")
        except Exception as e:
            logger.error(f"Erro ao atualizar atributos: {str(e)}", exc_info=True)
            
        try:
            if hasattr(self, 'supplies_panel') and self.supplies_panel:
                self._update_supplies_panel(details) # This will now show supplies
            else:
                logger.warning("Painel de suprimentos não encontrado para atualização.")
        except Exception as e:
            logger.error(f"Erro ao atualizar suprimentos: {str(e)}", exc_info=True)
        
        try:
            if hasattr(self, 'connectivity_panel') and self.connectivity_panel:
                 self._update_connectivity_status() # This will use the new 'is_ready'
            else:
                logger.warning("Painel de conectividade não encontrado para atualização.")
        except Exception as e:
            logger.error(f"Erro ao atualizar status de conectividade: {str(e)}", exc_info=True)
        
        self.details_loaded = True
        if hasattr(self, 'panel') and self.panel: # Ensure panel exists before layout
            try:
                self.panel.Layout() # Refresh layout after updates
            except wx.PyDeadObjectError:
                logger.warning("Painel principal do PrinterDetailsDialog não existe mais ao tentar fazer layout.")
    
    def _on_refresh(self, event):
        """Manipula o clique no botão de atualizar"""
        # Desabilita o botão durante a atualização
        self.refresh_button.Disable()
        self.refresh_button.SetLabel("Atualizando...")
        
        # Carrega os detalhes novamente
        self._load_printer_details()
        
        # Reabilita o botão
        self.refresh_button.Enable()
        self.refresh_button.SetLabel("Atualizar Informações")
    
    def _update_summary_panel(self, details):
        """
        Atualiza o painel de resumo
        
        Args:
            details: Detalhes da impressora
        """
        if not hasattr(self, 'summary_panel') or not self.summary_panel:
            logger.warning("summary_panel não existe em _update_summary_panel.")
            return

        # Limpa o painel
        if hasattr(self, 'summary_loading_text') and self.summary_loading_text:
            try:
                if self.summary_loading_text: # Explicit check
                    self.summary_loading_text.Destroy()
            except (wx.PyDeadObjectError, Exception): # Catch generic Exception if Destroy fails for other reasons
                pass # Widget might already be gone or in a bad state
            self.summary_loading_text = None # Clear reference
                
        sizer = self.summary_panel.GetSizer()
        if sizer:
            sizer.Clear(delete_windows=True) # delete_windows=True will destroy child windows
        else: # If sizer doesn't exist, can't do much. This case should ideally not happen.
            logger.warning("Sizer do summary_panel não encontrado.")
            # As a fallback, destroy children of the panel directly if no sizer
            for child in self.summary_panel.GetChildren():
                try:
                    child.Destroy()
                except: # pragma: no cover
                    pass

        # Card para o resumo
        summary_card = wx.Panel(self.summary_panel)
        summary_card.SetBackgroundColour(self.colors["card_bg"])
        summary_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título do resumo
        title = wx.StaticText(summary_card, label="RESUMO DA IMPRESSORA")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        summary_sizer.Add(title, 0, wx.ALL, 15)
        
        # Painel para informações em duas colunas
        info_panel = wx.Panel(summary_card)
        info_panel.SetBackgroundColour(self.colors["card_bg"])
        info_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=20)
        info_sizer.AddGrowableCol(1, 1)  # A segunda coluna é expansível
        
        # Adiciona informações básicas
        self._add_summary_item(info_panel, info_sizer, "Nome:", self.printer.name)
        self._add_summary_item(info_panel, info_sizer, "IP:", self.printer.ip or "Desconhecido")
        self._add_summary_item(info_panel, info_sizer, "Modelo:", self.printer.model or "Desconhecido")
        self._add_summary_item(info_panel, info_sizer, "Localização:", self.printer.location or "Desconhecida")
        self._add_summary_item(info_panel, info_sizer, "Status:", self.printer.state or "Desconhecido")
        
        # Informações adicionais
        if 'manufacturer' in details:
            self._add_summary_item(info_panel, info_sizer, "Fabricante:", details['manufacturer'])
        if 'version' in details:
            self._add_summary_item(info_panel, info_sizer, "Versão:", details['version'])
        if 'serial' in details:
            self._add_summary_item(info_panel, info_sizer, "Número de Série:", details['serial'])
        
        # URIs suportadas
        if 'printer-uri-supported' in details:
            uris = details['printer-uri-supported']
            uri_text = ""
            if isinstance(uris, list):
                uri_text = ", ".join(uris)
            else:
                uri_text = str(uris)
            self._add_summary_item(info_panel, info_sizer, "URIs suportadas:", uri_text)
        
        info_panel.SetSizer(info_sizer)
        summary_sizer.Add(info_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        # Adiciona informações de suprimentos se disponíveis
        if 'supplies' in details and details['supplies']:
            supply_title = wx.StaticText(summary_card, label="Informações de Suprimentos")
            supply_title.SetForegroundColour(self.colors["text_color"])
            supply_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            summary_sizer.Add(supply_title, 0, wx.ALL, 15)
            
            supply_panel = wx.Panel(summary_card)
            supply_panel.SetBackgroundColour(self.colors["card_bg"])
            supply_sizer = wx.FlexGridSizer(rows=0, cols=3, vgap=8, hgap=15)
            
            # Cabeçalho
            header_name = wx.StaticText(supply_panel, label="Nome")
            header_name.SetForegroundColour(self.colors["text_secondary"])
            header_name.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            header_type = wx.StaticText(supply_panel, label="Tipo")
            header_type.SetForegroundColour(self.colors["text_secondary"])
            header_type.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            header_level = wx.StaticText(supply_panel, label="Nível")
            header_level.SetForegroundColour(self.colors["text_secondary"])
            header_level.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            supply_sizer.Add(header_name, 0)
            supply_sizer.Add(header_type, 0)
            supply_sizer.Add(header_level, 0)
            
            # Adiciona cada suprimento
            for supply in details['supplies']:
                name_text = wx.StaticText(supply_panel, label=supply['name'])
                name_text.SetForegroundColour(self.colors["text_color"])
                
                type_text = wx.StaticText(supply_panel, label=supply['type'])
                type_text.SetForegroundColour(self.colors["text_color"])
                
                level_text = wx.StaticText(supply_panel, label=f"{supply['level']}%")
                level_text.SetForegroundColour(self.colors["text_color"])
                
                supply_sizer.Add(name_text, 0)
                supply_sizer.Add(type_text, 0)
                supply_sizer.Add(level_text, 0)
            
            supply_panel.SetSizer(supply_sizer)
            summary_sizer.Add(supply_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        summary_card.SetSizer(summary_sizer)
        
        # Adiciona borda arredondada ao card
        def on_summary_card_paint(event):
            dc = wx.BufferedPaintDC(summary_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = summary_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in summary_card.GetChildren():
                child.Refresh()
        
        summary_card.Bind(wx.EVT_PAINT, on_summary_card_paint)
        summary_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.summary_panel.GetSizer().Add(summary_card, 0, wx.EXPAND | wx.ALL, 10)
        self.summary_panel.Layout()
        
        if sizer: # Or self.summary_panel.GetSizer() if re-fetched
            self.summary_panel.Layout()
            self.summary_panel.Refresh()
    
    def _add_summary_item(self, parent, sizer, label, value):
        """
        Adiciona um item ao resumo
        
        Args:
            parent: Painel pai
            sizer: Sizer
            label: Rótulo
            value: Valor
        """
        label_ctrl = wx.StaticText(parent, label=label)
        label_ctrl.SetForegroundColour(self.colors["text_secondary"])
        label_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        value_ctrl = wx.StaticText(parent, label=str(value))
        value_ctrl.SetForegroundColour(self.colors["text_color"])
        
        sizer.Add(label_ctrl, 0, wx.ALIGN_LEFT)
        sizer.Add(value_ctrl, 0, wx.EXPAND)
    
    def _update_attributes_panel(self, details):
        """
        Atualiza o painel de atributos
        
        Args:
            details: Detalhes da impressora
        """
        if not details:
            if hasattr(self, 'loading_text') and self.loading_text:
                try:
                    self.loading_text.SetLabel("Não foi possível carregar os atributos da impressora.")
                except wx.PyDeadObjectError:
                    self.loading_text = None
            return
        
        # Limpa o sizer
        if hasattr(self, 'loading_text') and self.loading_text:
            try:
                self.loading_text.Destroy()
                self.loading_text = None  # Limpa a referência para evitar uso futuro
            except (wx.PyDeadObjectError, Exception):
                # Ignora erros se o widget já estiver destruído
                self.loading_text = None
                
        self.attributes_sizer.Clear()
        
        # Card para os atributos
        attributes_card = wx.Panel(self.attributes_panel)
        attributes_card.SetBackgroundColour(self.colors["card_bg"])
        attributes_sizer = wx.BoxSizer(wx.VERTICAL)

        # Título
        title = wx.StaticText(attributes_card, label="ATRIBUTOS DA IMPRESSORA")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        attributes_sizer.Add(title, 0, wx.ALL, 15)
        
        # Adiciona os atributos
        sorted_attrs = sorted(details.items())
        
        grid_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=20)
        grid_sizer.AddGrowableCol(1, 1)  # A segunda coluna é expansível
        
        for i, (key, value) in enumerate(sorted_attrs):
            # Ignora keys já exibidas em outro lugar
            if key in ["ip", "mac_address", "uri", "ports", "supplies"]:
                continue
                
            # Ignora values muito grandes
            if isinstance(value, (dict, list)) and len(str(value)) > 100:
                # Adiciona uma versão resumida
                if isinstance(value, list):
                    value = f"Lista com {len(value)} itens"
                else:
                    value = f"Objeto com {len(value)} atributos"
            
            # Label
            key_ctrl = wx.StaticText(attributes_card, label=key)
            key_ctrl.SetForegroundColour(self.colors["text_secondary"])
            
            # Valor
            value_ctrl = wx.StaticText(attributes_card, label=str(value))
            value_ctrl.SetForegroundColour(self.colors["text_color"])
            value_ctrl.Wrap(400)  # Wrap text para manter uma boa apresentação
            
            grid_sizer.Add(key_ctrl, 0, wx.ALIGN_LEFT)
            grid_sizer.Add(value_ctrl, 0, wx.EXPAND)
            
        attributes_sizer.Add(grid_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        attributes_card.SetSizer(attributes_sizer)
        
        # Adiciona borda arredondada ao card
        def on_attributes_card_paint(event):
            dc = wx.BufferedPaintDC(attributes_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = attributes_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in attributes_card.GetChildren():
                child.Refresh()
        
        attributes_card.Bind(wx.EVT_PAINT, on_attributes_card_paint)
        attributes_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.attributes_sizer.Add(attributes_card, 0, wx.EXPAND | wx.ALL, 10)
        self.attributes_panel.Layout()
    
    def _update_connectivity_status(self):
        """Atualiza o status na guia de conectividade"""
        # Encontra o painel de status
        for child in self.connectivity_panel.GetChildren():
            if isinstance(child, wx.Panel):
                for grandchild in child.GetChildren():
                    if isinstance(grandchild, wx.Panel):
                        for great_grandchild in grandchild.GetChildren():
                            if isinstance(great_grandchild, wx.StaticText) and great_grandchild.GetLabel() == "Status:":
                                # Encontrou o painel, atualiza o valor
                                for sibling in grandchild.GetChildren():
                                    if isinstance(sibling, wx.StaticText) and sibling != great_grandchild:
                                        # Verifica os atributos da impressora de forma segura
                                        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
                                        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
                                        is_usable = is_online and is_ready
                                        
                                        status_text = "Pronta" if is_usable else "Indisponível"
                                        sibling.SetLabel(status_text)
                                        sibling.SetForegroundColour(
                                            self.colors["success_color"] if is_usable else self.colors["error_color"]
                                        )
                                        grandchild.Layout()
                                        break
                                break
                        break
    
    def _update_supplies_panel(self, details):
        """
        Atualiza o painel de suprimentos
        
        Args:
            details: Detalhes da impressora
        """
        # Limpa o sizer
        if hasattr(self, 'supplies_loading_text') and self.supplies_loading_text:
            try:
                self.supplies_loading_text.Destroy()
                self.supplies_loading_text = None
            except (wx.PyDeadObjectError, Exception):
                self.supplies_loading_text = None
                
        self.supplies_sizer.Clear()

        # Título da seção
        title = wx.StaticText(self.supplies_panel, label="Níveis de Suprimentos")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.supplies_sizer.Add(title, 0, wx.ALL | wx.CENTER, 15)
        
        # Verifica se há informações de suprimentos
        if 'supplies' in details and details['supplies']:
            # Criar um painel de card para os suprimentos
            supplies_card = wx.Panel(self.supplies_panel)
            supplies_card.SetBackgroundColour(self.colors["card_bg"])
            supplies_card_sizer = wx.BoxSizer(wx.VERTICAL)
            
            for supply in details['supplies']:
                supply_panel = wx.Panel(supplies_card)
                supply_panel.SetBackgroundColour(self.colors["card_bg"])
                supply_sizer = wx.BoxSizer(wx.VERTICAL)
                
                # Nome do suprimento
                name = wx.StaticText(supply_panel, label=supply['name'])
                name.SetForegroundColour(self.colors["text_color"])
                name.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                supply_sizer.Add(name, 0, wx.ALL, 5)
                
                # Informações adicionais
                info_text = f"Tipo: {supply['type']} | Cor: {supply.get('color', 'N/A')}"
                info = wx.StaticText(supply_panel, label=info_text)
                info.SetForegroundColour(self.colors["text_secondary"])
                supply_sizer.Add(info, 0, wx.LEFT | wx.BOTTOM, 5)
                
                # Painel para a barra de progresso e percentual
                gauge_panel = wx.Panel(supply_panel)
                gauge_panel.SetBackgroundColour(self.colors["card_bg"])
                gauge_sizer = wx.BoxSizer(wx.HORIZONTAL)
                
                # Nível
                level_text = f"{supply['level']}%"
                level = wx.StaticText(gauge_panel, label=level_text)
                level.SetForegroundColour(self.colors["text_secondary"])
                
                # Determina a cor baseada no nível
                level_value = int(supply['level'])
                if level_value > 50:
                    color = self.colors["success_color"]  # Verde para nível alto
                elif level_value > 15:
                    color = self.colors["warning_color"]  # Amarelo para nível médio
                else:
                    color = self.colors["error_color"]  # Vermelho para nível baixo
                
                # Barra de progresso personalizada - usando bitmap pré-renderizado
                gauge_width = 300
                gauge_height = 18
                
                # Cria um bitmap para a barra de progresso
                progress_bitmap = wx.Bitmap(gauge_width, gauge_height)
                dc = wx.MemoryDC()
                dc.SelectObject(progress_bitmap)
                
                # Desenha o fundo da barra
                dc.SetBackground(wx.Brush(wx.Colour(45, 45, 45)))
                dc.Clear()
                
                # Calcula o comprimento do preenchimento da barra
                fill_width = int((gauge_width * level_value) / 100)
                
                # Desenha o preenchimento da barra
                dc.SetBrush(wx.Brush(color))
                dc.SetPen(wx.Pen(color))
                dc.DrawRectangle(0, 0, fill_width, gauge_height)
                
                # Finaliza o desenho
                dc.SelectObject(wx.NullBitmap)
                
                # Cria e adiciona o bitmap ao layout
                progress_bar = wx.StaticBitmap(gauge_panel, bitmap=progress_bitmap, size=(gauge_width, gauge_height))
                
                gauge_sizer.Add(progress_bar, 0, wx.RIGHT, 10)
                gauge_sizer.Add(level, 0, wx.ALIGN_CENTER_VERTICAL)
                
                gauge_panel.SetSizer(gauge_sizer)
                supply_sizer.Add(gauge_panel, 0, wx.LEFT | wx.BOTTOM, 10)
                
                # Adiciona linha separadora, exceto no último item
                if supply != details['supplies'][-1]:
                    separator = wx.StaticLine(supply_panel)
                    separator.SetForegroundColour(self.colors["border_color"])
                    supply_sizer.Add(separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)
                
                supply_panel.SetSizer(supply_sizer)
                supplies_card_sizer.Add(supply_panel, 0, wx.EXPAND | wx.ALL, 5)
            
            supplies_card.SetSizer(supplies_card_sizer)
            
            # Adiciona borda arredondada ao card de suprimentos
            def on_supplies_card_paint(event):
                dc = wx.BufferedPaintDC(supplies_card)
                gc = wx.GraphicsContext.Create(dc)
                
                rect = supplies_card.GetClientRect()
                
                # Desenha o fundo com cantos arredondados
                path = gc.CreatePath()
                path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
                
                gc.SetBrush(wx.Brush(self.colors["card_bg"]))
                gc.SetPen(wx.Pen(self.colors["border_color"], 1))
                
                gc.DrawPath(path)
                
                # Redesenha os filhos
                for child in supplies_card.GetChildren():
                    child.Refresh()
            
            supplies_card.Bind(wx.EVT_PAINT, on_supplies_card_paint)
            supplies_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
            
            self.supplies_sizer.Add(supplies_card, 0, wx.EXPAND | wx.ALL, 10)
        else:
            # Sem informações de suprimentos
            no_supplies_card = wx.Panel(self.supplies_panel)
            no_supplies_card.SetBackgroundColour(self.colors["card_bg"])
            no_supplies_sizer = wx.BoxSizer(wx.VERTICAL)
            
            no_supplies = wx.StaticText(no_supplies_card, label="Nenhuma informação de suprimentos disponível.")
            no_supplies.SetForegroundColour(self.colors["text_color"])
            no_supplies_sizer.Add(no_supplies, 0, wx.ALL | wx.CENTER, 20)
            
            no_supplies_card.SetSizer(no_supplies_sizer)
            
            # Adiciona borda arredondada ao card
            def on_no_supplies_card_paint(event):
                dc = wx.BufferedPaintDC(no_supplies_card)
                gc = wx.GraphicsContext.Create(dc)
                
                rect = no_supplies_card.GetClientRect()
                
                # Desenha o fundo com cantos arredondados
                path = gc.CreatePath()
                path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
                
                gc.SetBrush(wx.Brush(self.colors["card_bg"]))
                gc.SetPen(wx.Pen(self.colors["border_color"], 1))
                
                gc.DrawPath(path)
                
                # Redesenha os filhos
                for child in no_supplies_card.GetChildren():
                    child.Refresh()
            
            no_supplies_card.Bind(wx.EVT_PAINT, on_no_supplies_card_paint)
            no_supplies_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
            
            self.supplies_sizer.Add(no_supplies_card, 0, wx.EXPAND | wx.ALL, 10)
        
        # Atualiza o layout
        self.supplies_panel.Layout()

class PrinterListPanel(wx.ScrolledWindow):
    """Painel de lista de impressoras moderno com cards"""
    
    def __init__(self, parent, theme_manager, config, api_client, on_update=None):
        """
        Inicializa o painel de listagem de impressoras
        
        Args:
            parent: Pai do painel
            theme_manager: Gerenciador de temas
            config: Configuração da aplicação
            api_client: Cliente da API
            on_update: Callback chamado ao atualizar impressoras
        """
        super().__init__(
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            style=wx.TAB_TRAVERSAL
        )
        
        self.theme_manager = theme_manager
        self.config = config
        self.api_client = api_client
        self.on_update = on_update
        
        self.printers = []
        self.colors = {"bg_color": wx.Colour(18, 18, 18), 
                       "panel_bg": wx.Colour(25, 25, 25),
                       "accent_color": wx.Colour(255, 90, 36),
                       "text_color": wx.WHITE,
                       "text_secondary": wx.Colour(180, 180, 180)}
        
        # Inicializa o sistema de notificações com instalação opcional
        self.notification_system = SystemNotification()
        
        # Tenta instalar dependências opcionais em background se necessário
        if not any(self.notification_system.notification_methods.values()):
            logger.info("Nenhum método de notificação avançado disponível, tentando instalar dependências...")
            import threading
            install_thread = threading.Thread(target=self.notification_system.install_optional_dependencies)
            install_thread.daemon = True
            install_thread.start()
        
        self._init_ui()
        
        # Configura scrolling - valor alterado para ter scroll horizontal e vertical
        self.SetScrollRate(5, 10)

        if wx.Platform == '__WXMSW__':
            try:
                import win32gui
                import win32con
                
                def customize_scrollbar():
                    wx.CallAfter(self._customize_scrollbar_colors)
                
                wx.CallLater(100, customize_scrollbar)
            except ImportError:
                pass
    
    def _customize_scrollbar_colors(self):
        """Personaliza as cores da scrollbar para tema escuro"""
        try:
            if wx.Platform == '__WXMSW__':
                # Tenta aplicar tema escuro via win32
                try:
                    import win32gui
                    import win32con
                    import win32api
                    import ctypes
                    from ctypes import wintypes
                    
                    hwnd = self.GetHandle()
                    
                    # Tenta habilitar tema escuro no controle
                    # Este é o método mais moderno para Windows 10/11
                    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
                    
                    def try_set_dark_mode(attribute):
                        try:
                            dwmapi = ctypes.windll.dwmapi
                            value = ctypes.c_int(1)
                            dwmapi.DwmSetWindowAttribute(
                                hwnd,
                                attribute,
                                ctypes.byref(value),
                                ctypes.sizeof(value)
                            )
                            return True
                        except:
                            return False
                    
                    # Tenta ambas as versões do atributo
                    if not try_set_dark_mode(DWMWA_USE_IMMERSIVE_DARK_MODE):
                        try_set_dark_mode(DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1)
                    
                    # Método alternativo: força tema escuro via SetWindowTheme
                    try:
                        uxtheme = ctypes.windll.uxtheme
                        uxtheme.SetWindowTheme(hwnd, "DarkMode_Explorer", None)
                    except:
                        pass
                    
                    # Força atualização da janela
                    try:
                        user32 = ctypes.windll.user32
                        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                        0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
                    except:
                        pass
                        
                except ImportError:
                    # Se win32 não estiver disponível, tenta método alternativo
                    pass
            
            elif wx.Platform == '__WXGTK__':
                # Para GTK, tenta aplicar estilo escuro
                try:
                    import gi
                    gi.require_version('Gtk', '3.0')
                    from gi.repository import Gtk
                    
                    # Aplica tema escuro no GTK
                    settings = Gtk.Settings.get_default()
                    settings.set_property('gtk-application-prefer-dark-theme', True)
                except:
                    pass
            
            elif wx.Platform == '__WXMAC__':
                # Para macOS, o tema escuro é controlado pelo sistema
                # Força refresh do controle
                self.Refresh()
                
        except Exception as e:
            # Falha silenciosa para não quebrar a aplicação
            pass
        
        # Método adicional: tenta personalizar via CSS no Windows
        if wx.Platform == '__WXMSW__':
            try:
                # Aplica estilo personalizado ao ScrolledWindow
                self.SetBackgroundColour(self.colors["bg_color"])
                
                # Força o refresh para aplicar as mudanças
                self.Refresh()
                self.Update()
                
                # Agenda uma segunda tentativa
                wx.CallLater(500, self._apply_scrollbar_theme)
                
            except:
                pass

    def _apply_scrollbar_theme(self):
        """Segunda tentativa de aplicar tema na scrollbar"""
        try:
            if wx.Platform == '__WXMSW__':
                import ctypes
                from ctypes import wintypes
                
                hwnd = self.GetHandle()
                
                # Obtém todos os controles filhos (incluindo scrollbars)
                def enum_child_proc(child_hwnd, lparam):
                    try:
                        # Obtém informações da janela
                        user32 = ctypes.windll.user32
                        
                        # Aplica tema escuro
                        try:
                            uxtheme = ctypes.windll.uxtheme
                            uxtheme.SetWindowTheme(child_hwnd, "DarkMode_CFD", None)
                        except:
                            try:
                                uxtheme.SetWindowTheme(child_hwnd, "DarkMode_Explorer", None)
                            except:
                                pass
                        
                        # Força redraw
                        user32.InvalidateRect(child_hwnd, None, True)
                        user32.UpdateWindow(child_hwnd)
                        
                    except:
                        pass
                    return True
                
                # Enumera e aplica tema em todos os filhos
                enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                ctypes.windll.user32.EnumChildWindows(hwnd, enum_proc(enum_child_proc), 0)
                
        except Exception as e:
            pass
        
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel de cabeçalho com título e botão
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(self.colors["bg_color"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Impressoras")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(self.colors["text_color"])
        
        # Botão de atualizar impressoras (com servidor)
        self.update_button = create_styled_button(
            header_panel,
            "Atualizar Impressoras",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(255, 120, 70),
            (160, 36)
        )
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update_printers)
        
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        header_sizer.AddStretchSpacer()
        header_sizer.Add(self.update_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        
        header_panel.SetSizer(header_sizer)
        
        # Descrição
        description_panel = wx.Panel(self)
        description_panel.SetBackgroundColour(self.colors["bg_color"])
        description_sizer = wx.BoxSizer(wx.VERTICAL)
        
        description = wx.StaticText(
            description_panel,
            label="Impressoras disponíveis para o sistema. Clique em uma impressora para ver mais detalhes."
        )
        description.SetForegroundColour(self.colors["text_secondary"])
        description.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        description_sizer.Add(description, 0, wx.LEFT | wx.BOTTOM, 20)
        description_panel.SetSizer(description_sizer)
        
        # Painel de conteúdo para os cards
        self.content_panel = wx.Panel(self)
        self.content_panel.SetBackgroundColour(self.colors["bg_color"])
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel para exibir mensagem de "sem impressoras"
        self.empty_panel = wx.Panel(self.content_panel)
        self.empty_panel.SetBackgroundColour(self.colors["bg_color"])
        empty_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Ícone de impressora vazia
        printer_icon_path = ResourceManager.get_image_path("printer.png")
        
        if os.path.exists(printer_icon_path):
            empty_icon = wx.StaticBitmap(
                self.empty_panel,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(64, 64)
            )
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 50)
        
        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhuma impressora encontrada"
        )
        empty_text.SetForegroundColour(self.colors["text_secondary"])
        empty_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        self.empty_panel.SetSizer(empty_sizer)
        
        self.content_sizer.Add(self.empty_panel, 1, wx.EXPAND)
        self.content_panel.SetSizer(self.content_sizer)
        
        # Adiciona ao layout principal
        self.main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        self.main_sizer.Add(description_panel, 0, wx.EXPAND | wx.LEFT, 20)
        self.main_sizer.Add(self.content_panel, 1, wx.EXPAND)
        
        self.SetSizer(self.main_sizer)
        
        self.load_printers()
        
        # Mostra notificação de inicialização para testar o sistema
        self._show_startup_notification()
    
    def load_printers(self):
        """Carrega as impressoras da configuração"""
        try:
            # Limpa os cards existentes
            for child in self.content_panel.GetChildren():
                if isinstance(child, PrinterCardPanel):
                    child.Destroy()
            
            printers_data = self.config.get_printers()
            logger.info(f"Carregadas {len(printers_data)} impressoras da configuração")
            
            if printers_data and len(printers_data) > 0:
                self.printers = []
                for printer_data in printers_data:
                    # Verifica se os dados da impressora são válidos
                    if not isinstance(printer_data, dict):
                        logger.warning(f"Dados de impressora inválidos: {printer_data}")
                        continue
                    
                    # Garante que os campos são válidos antes de criar o objeto
                    if 'name' not in printer_data or printer_data['name'] is None:
                        printer_data['name'] = f"Impressora {printer_data.get('ip', '')}"
                    if 'mac_address' not in printer_data or printer_data['mac_address'] is None:
                        printer_data['mac_address'] = ""
                    if 'ip' not in printer_data or printer_data['ip'] is None:
                        printer_data['ip'] = ""
                    
                    # Cria o objeto Printer
                    printer = Printer(printer_data)
                    self.printers.append(printer)
                
                self.empty_panel.Hide()
                
                # Cria um card para cada impressora
                for printer in self.printers:
                    card = PrinterCardPanel(self.content_panel, printer, self.on_printer_selected)
                    self.content_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            else:
                self.printers = []
                self.empty_panel.Show()
            
            # Ajusta o layout
            self.content_panel.Layout()
            self.Layout()
            
            # Importante para o scrolling funcionar corretamente
            self.FitInside()
            self.Refresh()
            
            logger.info(f"Lista de impressoras carregada com {len(self.printers)} impressoras")
            
        except Exception as e:
            logger.error(f"Erro ao carregar impressoras: {str(e)}")
            
            # Exibe mensagem de erro via notificação
            self.notification_system.show_notification(
                "Erro ao Carregar Impressoras",
                f"Erro: {str(e)}",
                duration=8,
                notification_type="error"
            )
            
            self.content_panel.Layout()
            self.Layout()
    
    def on_update_printers(self, event=None):
        """Atualiza impressoras com o servidor principal - Versão com Notificações do Sistema"""
        try:
            # Desabilita o botão para evitar cliques múltiplos
            self.update_button.Disable()
            self.update_button.SetLabel("Atualizando...")
            wx.GetApp().Yield()
            
            # Notificação de início
            self.notification_system.show_notification(
                "Atualizando Impressoras",
                "Iniciando descoberta de impressoras na rede...",
                duration=3,
                notification_type="info"
            )
            
            # Executa a descoberta em uma thread separada para não travar a UI
            def discovery_thread():
                try:
                    logger.info("Iniciando atualização de impressoras...")
                    
                    # Verifica se o método existe
                    if not hasattr(self.api_client, 'get_printers_with_discovery'):
                        wx.CallAfter(
                            self.notification_system.show_notification,
                            "Erro de Configuração",
                            "Cliente API não possui método de descoberta",
                            duration=6,
                            notification_type="error"
                        )
                        return
                    
                    # Obter impressoras do servidor
                    updated_printers = self.api_client.get_printers_with_discovery()
                    logger.info(f"Método get_printers_with_discovery retornou {len(updated_printers)} impressoras")
                    
                    # Validação e limpeza dos dados
                    validated_printers = self._validate_and_clean_printers(updated_printers)
                    
                    # Atualiza a UI no thread principal
                    if validated_printers:
                        wx.CallAfter(self._update_printers_success, validated_printers)
                    else:
                        wx.CallAfter(self._update_printers_no_results)
                        
                except Exception as e:
                    logger.error(f"Erro ao atualizar impressoras: {str(e)}")
                    logger.error(traceback.format_exc())
                    wx.CallAfter(self._update_printers_error, e)
                finally:
                    # Reabilita o botão no thread principal
                    wx.CallAfter(self._restore_update_button)
            
            # Inicia a thread de descoberta
            thread = threading.Thread(target=discovery_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar atualização de impressoras: {str(e)}")
            self.notification_system.show_notification(
                "Erro Crítico",
                f"Falha ao iniciar processo de atualização: {str(e)}",
                duration=8,
                notification_type="error"
            )
            self._restore_update_button()
    
    def _update_printers_success(self, validated_printers):
        """Processa sucesso na atualização de impressoras"""
        try:
            logger.info(f"Salvando {len(validated_printers)} impressoras validadas no config")
            self.config.set_printers(validated_printers)
            
            # Recarrega a lista na interface
            self.load_printers()
            
            # Chama o callback se existir
            if self.on_update:
                self.on_update(validated_printers)
            
            # Calcula estatísticas
            online_count = sum(1 for p in validated_printers if p.get('is_online', False))
            offline_count = len(validated_printers) - online_count
            
            # Notificação de sucesso com detalhes
            success_message = f"Atualização concluída com sucesso!\n\n{len(validated_printers)} impressoras encontradas\n{online_count} online • {offline_count} offline"
            
            self.notification_system.show_notification(
                "Impressoras Atualizadas",
                success_message,
                duration=6,
                notification_type="success"
            )
            
        except Exception as e:
            logger.error(f"Erro ao processar sucesso da atualização: {str(e)}")
            self.notification_system.show_notification(
                "Erro ao Salvar",
                f"Erro ao salvar impressoras: {str(e)}",
                duration=6,
                notification_type="error"
            )
    
    def _update_printers_no_results(self):
        """Processa caso onde nenhuma impressora foi encontrada"""
        warning_message = (
            "Nenhuma impressora encontrada na rede.\n\n"
            "Possíveis causas:\n"
            "• Impressoras desligadas\n"
            "• Firewall bloqueando descoberta\n"
            "• Impressoras em sub-rede diferente\n"
            "• Problemas de conectividade"
        )
        
        self.notification_system.show_notification(
            "Nenhuma Impressora Encontrada",
            warning_message,
            duration=8,
            notification_type="warning"
        )
    
    def _update_printers_error(self, error):
        """Processa erro na atualização de impressoras"""
        error_str = str(error)
        
        # Determina tipo de erro e mensagem apropriada
        if "ConnectionError" in str(type(error)) or "requests" in error_str.lower():
            error_message = (
                "Erro de conectividade ao atualizar impressoras.\n\n"
                "Verifique:\n"
                "• Conexão com a internet\n"
                "• Configurações de proxy/firewall\n"
                "• Status do servidor"
            )
        elif "timeout" in error_str.lower():
            error_message = (
                "Tempo limite excedido ao descobrir impressoras.\n\n"
                "A rede pode estar lenta ou congestionada.\n"
                "Tente novamente em alguns minutos."
            )
        elif "permission" in error_str.lower() or "admin" in error_str.lower():
            error_message = (
                "Erro de permissões ao descobrir impressoras.\n\n"
                "No Windows, alguns comandos de rede requerem\n"
                "privilégios de administrador.\n\n"
                "Tente executar o programa como administrador."
            )
        else:
            error_message = f"Erro ao atualizar impressoras:\n\n{error_str}"
        
        self.notification_system.show_notification(
            "Erro na Atualização",
            error_message,
            duration=10,
            notification_type="error"
        )
    
    def _restore_update_button(self):
        """Restaura o estado normal do botão de atualizar"""
        self.update_button.Enable()
        self.update_button.SetLabel("Atualizar Impressoras")
    
    def _validate_and_clean_printers(self, printers):
        """
        Valida e limpa dados das impressoras
        
        Args:
            printers: Lista de impressoras para validar
            
        Returns:
            list: Lista de impressoras validadas
        """
        validated_printers = []
        
        if not printers or not isinstance(printers, list):
            logger.warning("Lista de impressoras inválida ou vazia")
            return []
        
        for i, printer_data in enumerate(printers):
            try:
                if not isinstance(printer_data, dict):
                    logger.warning(f"Dados de impressora inválidos no índice {i}: {type(printer_data)}")
                    continue
                
                # Cria uma cópia limpa
                clean_printer = {}
                
                # CORREÇÃO: Preserva o ID da API (não gera local)
                api_id = printer_data.get('id', '')
                if api_id:
                    clean_printer['id'] = str(api_id)
                    logger.debug(f"Impressora {i}: ID da API preservado: {api_id}")
                else:
                    logger.warning(f"Impressora {i}: Sem ID da API - dados: {list(printer_data.keys())}")
                    # Se não tem ID da API, pula esta impressora ou registra como erro
                    continue
                
                # Campos obrigatórios
                clean_printer['name'] = self._clean_string_field(
                    printer_data.get('name') or f"Impressora {printer_data.get('ip', i+1)}"
                )
                
                # MAC Address - tenta várias possibilidades
                mac = (printer_data.get('macAddress') or 
                    printer_data.get('mac_address') or 
                    printer_data.get('MAC') or 
                    "")
                clean_printer['macAddress'] = self._clean_string_field(mac)
                clean_printer['mac_address'] = clean_printer['macAddress']  # Compatibilidade
                
                # Campos opcionais
                clean_printer['ip'] = self._clean_string_field(printer_data.get('ip', ""))
                clean_printer['uri'] = self._clean_string_field(printer_data.get('uri', ""))
                clean_printer['model'] = self._clean_string_field(printer_data.get('model', ""))
                clean_printer['location'] = self._clean_string_field(printer_data.get('location', ""))
                clean_printer['state'] = self._clean_string_field(printer_data.get('state', ""))
                
                # Campos booleanos
                clean_printer['is_online'] = bool(printer_data.get('is_online', False))
                clean_printer['is_ready'] = bool(printer_data.get('is_ready', False))
                
                # Campos de lista/dict
                clean_printer['ports'] = printer_data.get('ports', []) if isinstance(printer_data.get('ports'), list) else []
                clean_printer['attributes'] = printer_data.get('attributes', {}) if isinstance(printer_data.get('attributes'), dict) else {}
                
                # Validação básica
                if not clean_printer['name']:
                    clean_printer['name'] = f"Impressora {clean_printer['id']}"
                
                # Log da impressora processada
                logger.info(f"Impressora validada: {clean_printer['name']} "
                        f"(ID API: {clean_printer['id']}, IP: {clean_printer['ip']}, "
                        f"MAC: {clean_printer['macAddress']}, Online: {clean_printer['is_online']})")
                
                validated_printers.append(clean_printer)
                
            except Exception as e:
                logger.error(f"Erro ao validar impressora no índice {i}: {str(e)}")
                # CORREÇÃO: Não cria fallback sem ID da API
                logger.error(f"Pulando impressora {i} - sem ID da API válido")
                continue
        
        logger.info(f"Validação concluída: {len(validated_printers)} impressoras válidas de {len(printers)} originais")
        return validated_printers

    def _clean_string_field(self, value):
        """
        Limpa e valida campo string
        
        Args:
            value: Valor a ser limpo
            
        Returns:
            str: Valor limpo
        """
        if value is None:
            return ""
        
        # Converte para string se não for
        if not isinstance(value, str):
            try:
                value = str(value)
            except:
                return ""
        
        # Remove caracteres de controle e espaços extras
        cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', value.strip())
        
        return cleaned
    
    def _show_startup_notification(self):
        """Mostra notificação de inicialização e testa o sistema"""
        try:
            # Espera um pouco para a interface carregar
            def delayed_notification():
                import time
                time.sleep(2)  # Aguarda 2 segundos
                
                # Determina quais métodos estão disponíveis
                available_methods = [method for method, available in 
                                   self.notification_system.notification_methods.items() if available]
                
                if available_methods:
                    primary_method = available_methods[0]
                    methods_text = ", ".join(available_methods[:3])  # Mostra até 3 métodos
                    if len(available_methods) > 3:
                        methods_text += "..."
                    
                    wx.CallAfter(
                        self.notification_system.show_notification,
                        "Sistema de Impressão Iniciado",
                        "",
                        duration=4,
                        notification_type="success"
                    )
                else:
                    wx.CallAfter(
                        self.notification_system.show_notification,
                        "Sistema de Impressão Iniciado",
                        f"Usando notificações via console\nSistema: {self.notification_system.system.title()}",
                        duration=4,
                        notification_type="info"
                    )
            
            import threading
            thread = threading.Thread(target=delayed_notification)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.warning(f"Erro ao mostrar notificação de inicialização: {str(e)}")
    
    def get_notification_status(self):
        """Retorna status do sistema de notificações"""
        try:
            available = [method for method, status in 
                        self.notification_system.notification_methods.items() if status]
            return {
                'system': self.notification_system.system,
                'available_methods': available,
                'primary_method': available[0] if available else 'console',
                'total_methods': len(available)
            }
        except Exception:
            return {
                'system': 'unknown',
                'available_methods': ['console'],
                'primary_method': 'console',
                'total_methods': 0
            }

    def on_printer_selected(self, printer):
        """
        Manipula a seleção de uma impressora
        
        Args:
            printer: Impressora selecionada
        """
        try:
            # Notificação discreta ao abrir detalhes
            dialog = PrinterDetailsDialog(self, printer, self.api_client)
            dialog.ShowModal()
            dialog.Destroy()
            
            # Recarrega a lista para refletir quaisquer alterações
            self.load_printers()
            
        except Exception as e:
            logger.error(f"Erro ao exibir detalhes da impressora: {str(e)}")
            self.notification_system.show_notification(
                "Erro ao Abrir Detalhes",
                f"Não foi possível abrir detalhes da impressora: {str(e)}",
                duration=6,
                notification_type="error"
            )
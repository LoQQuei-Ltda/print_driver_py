#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Classe para o ícone na bandeja do sistema
"""

import os
import wx
import logging
from .taskbar_imports import TaskBarIcon, EVT_TASKBAR_LEFT_DCLICK
from src.utils.resource_manager import ResourceManager

logger = logging.getLogger("PrintManagementSystem.UI.TaskBarIcon")

class PrintManagerTaskBarIcon:
    """Wrapper para o ícone na bandeja do sistema"""
    
    def __init__(self, parent, config):
        """
        Inicializa o ícone da bandeja
        
        Args:
            parent: Frame pai
            config: Configuração da aplicação
        """
        self.parent = parent
        self.config = config
        self.icon_impl = None
        
        # Verifica se o ícone da bandeja é suportado
        if TaskBarIcon is None:
            logger.warning("TaskBarIcon não é suportado nesta versão do wxPython")
            return
        
        # CORREÇÃO: Verifica se o sistema tem taskbar disponível
        if not self._check_taskbar_availability():
            logger.warning("Taskbar não está disponível para este usuário")
            return
        
        try:
            # Cria o ícone da bandeja
            self.icon_impl = _PrintManagerTaskBarIconImpl(parent, config)
            logger.info("Ícone na bandeja criado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao criar ícone na bandeja: {str(e)}")

    def _check_taskbar_availability(self):
        """Verifica se a taskbar está disponível"""
        try:
            import platform
            if platform.system() == 'Windows':
                # Verifica se o explorer.exe está rodando
                import psutil
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc.info['name'] and 'explorer.exe' in proc.info['name'].lower():
                            return True
                    except:
                        continue
                return False
            return True
        except:
            return True  
        
    def RemoveIcon(self):
        """Remove o ícone da bandeja"""
        if self.icon_impl:
            try:
                self.icon_impl.RemoveIcon()
                logger.info("Ícone na bandeja removido com sucesso")
            except Exception as e:
                logger.error(f"Erro ao remover ícone da bandeja: {str(e)}")
    
    def Destroy(self):
        """Destrói o ícone da bandeja"""
        if self.icon_impl:
            try:
                self.icon_impl.Destroy()
                logger.info("Ícone na bandeja destruído com sucesso")
            except Exception as e:
                logger.error(f"Erro ao destruir ícone da bandeja: {str(e)}")


class _PrintManagerTaskBarIconImpl(TaskBarIcon):
    """Implementação do ícone na bandeja do sistema"""
    
    def __init__(self, parent, config):
        """
        Inicializa o ícone da bandeja
        
        Args:
            parent: Frame pai
            config: Configuração da aplicação
        """
        super().__init__()
        
        self.parent = parent
        self.config = config
        
        # Carrega o ícone da aplicação
        self._setup_icon()
        
        # Vincula eventos de duplo clique
        if EVT_TASKBAR_LEFT_DCLICK:
            self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
    
    def _setup_icon(self):
        """Configura o ícone da bandeja"""
        icon_path = ResourceManager.get_icon_path("icon.ico")
        
        try:
            if os.path.exists(icon_path):
                self.icon = wx.Icon(icon_path)
                # CORREÇÃO: Verifica se SetIcon foi bem-sucedido
                if not self.SetIcon(self.icon, "Sistema de Gerenciamento de Impressão"):
                    raise Exception("SetIcon falhou")
            else:
                # CORREÇÃO: Cria um ícone mais robusto como fallback
                self._create_fallback_icon()
                
        except Exception as e:
            logger.warning(f"Erro ao definir ícone na bandeja: {str(e)}")
            # Tenta criar um ícone de fallback
            self._create_fallback_icon()

    def _create_fallback_icon(self):
        """Cria um ícone de fallback simples"""
        try:
            # Cria um bitmap 16x16
            icon_bmp = wx.Bitmap(16, 16)
            dc = wx.MemoryDC(icon_bmp)
            dc.SetBackground(wx.Brush(wx.Colour(0, 120, 200)))
            dc.Clear()
            
            # Adiciona um "P" branco
            dc.SetTextForeground(wx.WHITE)
            font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            dc.SetFont(font)
            dc.DrawText("P", 2, 1)
            
            dc.SelectObject(wx.NullBitmap)
            
            self.icon = wx.Icon()
            self.icon.CopyFromBitmap(icon_bmp)
            self.SetIcon(self.icon, "Sistema de Gerenciamento de Impressão")
            logger.info("Ícone de fallback criado")
            
        except Exception as e:
            logger.error(f"Erro ao criar ícone de fallback: {e}")
    
    def CreatePopupMenu(self):
        """
        Cria o menu de contexto para o ícone da bandeja - USANDO A ABORDAGEM QUE FUNCIONOU NO TESTE
        
        Returns:
            wx.Menu: Menu de contexto
        """
        menu = wx.Menu()
        
        try:
            # Item para abrir a aplicação - USANDO LAMBDA COMO NO TESTE QUE FUNCIONOU
            open_item = menu.Append(wx.ID_ANY, "Abrir")
            self.Bind(wx.EVT_MENU, lambda evt: self._action_open(), open_item)
            
            menu.AppendSeparator()
            
            # Item para alternar impressão automática
            auto_print_active = self.config.get("auto_print", False)
            auto_print_label = "Desativar Impressão Automática" if auto_print_active else "Ativar Impressão Automática"
            auto_print_item = menu.Append(wx.ID_ANY, auto_print_label)
            self.Bind(wx.EVT_MENU, lambda evt: self._action_toggle_auto_print(), auto_print_item)
            
            menu.AppendSeparator()
            
            # Item para sair completamente da aplicação - USANDO LAMBDA COMO NO TESTE QUE FUNCIONOU
            exit_item = menu.Append(wx.ID_ANY, "Sair")
            self.Bind(wx.EVT_MENU, lambda evt: self._action_exit(), exit_item)
            
        except Exception as e:
            logger.error(f"Erro ao criar menu de contexto: {str(e)}")
        
        return menu
    
    def on_left_dclick(self, event):
        """Manipula o evento de duplo clique no ícone da bandeja"""
        self._action_open()
    
    def _action_open(self):
        """Ação de abrir a janela - MÉTODO DIRETO COMO NO TESTE QUE FUNCIONOU"""
        if not self.parent:
            return
            
        try:
            # Mostra a janela se estiver oculta
            if not self.parent.IsShown():
                self.parent.Show(True)
            
            # Se estiver minimizada, restaura
            if self.parent.IsIconized():
                self.parent.Iconize(False)
            
            # Traz para frente
            self.parent.Raise()
            
            # Restaura o tamanho e posição salvos
            try:
                size = self.config.get("window_size", None)
                pos = self.config.get("window_pos", None)
                
                if size and isinstance(size, (tuple, list)) and len(size) == 2:
                    self.parent.SetSize(size)
                
                if pos and isinstance(pos, (tuple, list)) and len(pos) == 2:
                    # Verifica se a posição está dentro dos limites da tela
                    display_size = wx.GetDisplaySize()
                    if 0 <= pos[0] < display_size[0] and 0 <= pos[1] < display_size[1]:
                        self.parent.SetPosition(pos)
            except Exception as e:
                logger.warning(f"Erro ao restaurar tamanho/posição da janela: {str(e)}")
                
        except Exception as e:
            logger.error(f"Erro ao abrir a janela principal: {str(e)}")
    
    def _action_toggle_auto_print(self):
        """Ação de alternar impressão automática - MÉTODO DIRETO COMO NO TESTE QUE FUNCIONOU"""
        try:
            current_state = self.config.get("auto_print", False)
            new_state = not current_state
            self.config.set("auto_print", new_state)
            
            # Atualiza o checkbox na interface principal se estiver visível
            if self.parent and hasattr(self.parent, "auto_print_toggle"):
                self.parent.auto_print_toggle.SetValue(new_state)
                
            # Inicia ou para o monitoramento da pasta
            if self.parent:
                if new_state:
                    if hasattr(self.parent, '_start_folder_monitoring'):
                        self.parent._start_folder_monitoring()
                else:
                    if hasattr(self.parent, '_stop_folder_monitoring'):
                        self.parent._stop_folder_monitoring()
        except Exception as e:
            logger.error(f"Erro ao alternar impressão automática: {str(e)}")
    
    def _action_exit(self):
        """Ação de sair - MÉTODO DIRETO COMO NO TESTE QUE FUNCIONOU"""
        try:
            # Primeiro tenta usar o método específico do parent
            if self.parent and hasattr(self.parent, 'exit_application'):
                self.parent.exit_application()
            elif self.parent and hasattr(self.parent, 'Close'):
                self.parent.Close(force=True)
            else:
                # Fallback direto como no teste que funcionou
                wx.GetApp().ExitMainLoop()
                
        except Exception as e:
            logger.error(f"Erro ao sair da aplicação: {str(e)}")
            # Em caso de erro, força o encerramento como no teste que funcionou
            wx.GetApp().ExitMainLoop()
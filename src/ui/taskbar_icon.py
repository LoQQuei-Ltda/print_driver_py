#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Classe para o ícone na bandeja do sistema
"""

import os
import wx
import logging
from .taskbar_imports import TaskBarIcon, EVT_TASKBAR_LEFT_DCLICK

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
        
        try:
            # Cria o ícone da bandeja
            self.icon_impl = _PrintManagerTaskBarIconImpl(parent, config)
            logger.info("Ícone na bandeja criado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao criar ícone na bandeja: {str(e)}")
    
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
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                "src", "ui", "resources", "icon.ico")
        
        try:
            if os.path.exists(icon_path):
                self.icon = wx.Icon(icon_path)
                self.SetIcon(self.icon, "Sistema de Gerenciamento de Impressão")
            else:
                # Cria um ícone vazio como fallback
                icon_bmp = wx.Bitmap(16, 16)
                dc = wx.MemoryDC(icon_bmp)
                dc.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
                dc.Clear()
                dc.SelectObject(wx.NullBitmap)
                
                self.icon = wx.Icon()
                self.icon.CopyFromBitmap(icon_bmp)
                self.SetIcon(self.icon, "Sistema de Gerenciamento de Impressão")
        except Exception as e:
            logger.error(f"Erro ao definir ícone na bandeja: {str(e)}")
            # Ainda assim, continuamos com o objeto criado
            pass
        
        # Vincula eventos
        if EVT_TASKBAR_LEFT_DCLICK:
            self.Bind(EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
    
    def CreatePopupMenu(self):
        """
        Cria o menu de contexto para o ícone da bandeja
        
        Returns:
            wx.Menu: Menu de contexto
        """
        menu = wx.Menu()
        
        try:
            # Item para abrir a aplicação
            open_item = menu.Append(wx.ID_ANY, "Abrir")
            self.Bind(wx.EVT_MENU, self.on_open, open_item)
            
            menu.AppendSeparator()
            
            # Item para alternar impressão automática
            auto_print_active = self.config.get("auto_print", False)
            auto_print_label = "Desativar Impressão Automática" if auto_print_active else "Ativar Impressão Automática"
            auto_print_item = menu.Append(wx.ID_ANY, auto_print_label)
            self.Bind(wx.EVT_MENU, self.on_toggle_auto_print, auto_print_item)
            
            menu.AppendSeparator()
            
            # Item para sair completamente da aplicação
            exit_item = menu.Append(wx.ID_ANY, "Sair")
            self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        except Exception as e:
            logger.error(f"Erro ao criar menu de contexto: {str(e)}")
        
        return menu
    
    def on_left_dclick(self, event):
        """Manipula o evento de duplo clique no ícone da bandeja"""
        self.on_open(event)
    
    def on_open(self, event):
        """Abre a aplicação"""
        if self.parent:
            try:
                self.parent.Show()
                self.parent.Raise()
                
                # Restaura o tamanho e posição salvos
                size = self.config.get("window_size", None)
                pos = self.config.get("window_pos", None)
                
                if size:
                    self.parent.SetSize(size)
                
                if pos:
                    self.parent.SetPosition(pos)
            except Exception as e:
                logger.error(f"Erro ao abrir a janela principal: {str(e)}")
    
    def on_toggle_auto_print(self, event):
        """Alterna o modo de impressão automática"""
        try:
            current_state = self.config.get("auto_print", False)
            self.config.set("auto_print", not current_state)
            
            # Atualiza o checkbox na interface principal se estiver visível
            if self.parent and hasattr(self.parent, "auto_print_toggle"):
                self.parent.auto_print_toggle.SetValue(not current_state)
                
            # Inicia ou para o monitoramento da pasta
            if self.parent:
                if not current_state:
                    self.parent._start_folder_monitoring()
                else:
                    self.parent._stop_folder_monitoring()
        except Exception as e:
            logger.error(f"Erro ao alternar impressão automática: {str(e)}")
    
    def on_exit(self, event):
        """Fecha completamente a aplicação"""
        try:
            if self.parent:
                self.parent.exit_application()
        except Exception as e:
            logger.error(f"Erro ao sair da aplicação: {str(e)}")
            # Em caso de erro, força o encerramento
            wx.GetApp().ExitMainLoop()
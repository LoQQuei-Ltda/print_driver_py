#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tela de login da aplicação
"""

import os
import wx
import logging
from src.api import APIError
from src.utils import AuthError

logger = logging.getLogger("PrintManagementSystem.UI.LoginScreen")

class LoginScreen(wx.Frame):
    """Tela de login da aplicação"""
    
    def __init__(self, parent, auth_manager, theme_manager, on_login_success):
        """
        Inicializa a tela de login
        
        Args:
            parent: Frame pai
            auth_manager: Gerenciador de autenticação
            theme_manager: Gerenciador de temas
            on_login_success: Função chamada quando o login for bem-sucedido
        """
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Login - Sistema de Gerenciamento de Impressão",
            pos=wx.DefaultPosition,
            size=wx.Size(400, 500),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL
        )
        
        self.auth_manager = auth_manager
        self.theme_manager = theme_manager
        self.on_login_success = on_login_success
        
        # Configura o ícone da aplicação
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "ui", "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path))
        
        self._init_ui()
        
        # Centraliza a janela na tela
        self.Centre(wx.BOTH)
        
        # Aplica o tema atual
        self.theme_manager.apply_theme_to_window(self)
        
        # Evita fechar a aplicação quando esta janela for fechada
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        colors = self.theme_manager.get_theme_colors()
        
        # Painel principal
        panel = wx.Panel(self)
        panel.SetBackgroundColour(colors["panel_bg"])
        
        # Layout principal (vertical)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Logo
        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "ui", "resources", "logo.png")
        if os.path.exists(logo_path):
            logo_bitmap = wx.Bitmap(logo_path)
            logo = wx.StaticBitmap(panel, wx.ID_ANY, logo_bitmap, wx.DefaultPosition, wx.Size(100, 100))
        else:
            # Logo como texto se a imagem não existir
            logo = wx.StaticText(panel, wx.ID_ANY, "LoQuei")
            logo.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            logo.SetForegroundColour(colors["accent_color"])
        
        # Título
        title = wx.StaticText(panel, wx.ID_ANY, "Sistema de Gerenciamento de Impressão")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        # Campo de email
        email_label = wx.StaticText(panel, wx.ID_ANY, "Email")
        # Adicione o estilo wx.TE_PROCESS_ENTER para processar eventos de tecla Enter
        self.email_input = wx.TextCtrl(panel, wx.ID_ANY, style=wx.TE_PROCESS_ENTER)
        self.email_input.SetBackgroundColour(colors["input_bg"])
        self.email_input.SetValue("eduardo.sirino@loqquei.com.br") # TODO: Remover
        
        # Campo de senha
        password_label = wx.StaticText(panel, wx.ID_ANY, "Senha")
        # Adicione o estilo wx.TE_PROCESS_ENTER para processar eventos de tecla Enter
        self.password_input = wx.TextCtrl(panel, wx.ID_ANY, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.password_input.SetBackgroundColour(colors["input_bg"])
        self.password_input.SetValue("EdusEdus@747466") # TODO: Remover
        
        # Checkbox "Lembrar-me"
        self.remember_checkbox = wx.CheckBox(panel, wx.ID_ANY, "Lembrar-me")
        
        # Mensagem de erro
        self.error_message = wx.StaticText(panel, wx.ID_ANY, "")
        self.error_message.SetForegroundColour(colors["error_color"])
        self.error_message.Hide()
        
        # Botão de login
        self.login_button = self.theme_manager.get_custom_button(panel, "Entrar", accent=True)
        self.login_button.Bind(wx.EVT_BUTTON, self.on_login)
        
        # Layout
        main_sizer.AddSpacer(30)
        
        # Logo centralizado
        logo_sizer = wx.BoxSizer(wx.HORIZONTAL)
        logo_sizer.Add((0, 0), 1, wx.EXPAND)
        logo_sizer.Add(logo, 0, wx.ALIGN_CENTER)
        logo_sizer.Add((0, 0), 1, wx.EXPAND)
        main_sizer.Add(logo_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.AddSpacer(10)
        
        # Título centralizado
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title_sizer.Add((0, 0), 1, wx.EXPAND)
        title_sizer.Add(title, 0, wx.ALIGN_CENTER)
        title_sizer.Add((0, 0), 1, wx.EXPAND)
        main_sizer.Add(title_sizer, 0, wx.EXPAND | wx.ALL, 5)
        
        main_sizer.AddSpacer(30)
        
        # Formulário
        main_sizer.Add(email_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 20)
        main_sizer.Add(self.email_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        
        main_sizer.AddSpacer(15)
        
        main_sizer.Add(password_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 20)
        main_sizer.Add(self.password_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        
        main_sizer.AddSpacer(15)
        
        # Checkbox
        main_sizer.Add(self.remember_checkbox, 0, wx.LEFT | wx.RIGHT, 20)
        
        main_sizer.AddSpacer(10)
        
        # Mensagem de erro
        main_sizer.Add(self.error_message, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        
        main_sizer.AddSpacer(30)
        
        # Botão de login
        main_sizer.Add(self.login_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        
        main_sizer.AddSpacer(30)
        
        panel.SetSizer(main_sizer)
        
        # Bind do evento de tecla Enter
        self.email_input.Bind(wx.EVT_TEXT_ENTER, self.on_login)
        self.password_input.Bind(wx.EVT_TEXT_ENTER, self.on_login)
    
    def on_login(self, event=None):
        """Processa a tentativa de login"""
        email = self.email_input.GetValue()
        password = self.password_input.GetValue()
        remember_me = self.remember_checkbox.GetValue()
        
        if not email:
            self._show_error("Por favor, informe seu email.")
            return
        
        if not password:
            self._show_error("Por favor, informe sua senha.")
            return
        
        try:
            # Desativa o botão de login enquanto processa
            self.login_button.Disable()
            self.login_button.SetLabel("Entrando...")
            wx.GetApp().Yield()  # Força atualização da UI
            
            # Tenta fazer login
            if self.auth_manager.login(email, password, remember_me):
                self.on_login_success()
            else:
                self._show_error("Falha ao fazer login. Verifique suas credenciais.")
                
        except AuthError as e:
            self._show_error(str(e))
        except APIError as e:
            self._show_error(f"Erro de API: {str(e)}")
        except Exception as e:
            logger.error(f"Erro desconhecido no login: {str(e)}", exc_info=True)
            self._show_error(f"Erro ao fazer login: {str(e)}")
        finally:
            # Reativa o botão de login
            self.login_button.Enable()
            self.login_button.SetLabel("Entrar")
    
    def _show_error(self, message):
        """
        Exibe mensagem de erro
        
        Args:
            message (str): Mensagem de erro
        """
        self.error_message.SetLabel(message)
        self.error_message.Show()
        self.Layout()
    
    def on_close(self, event):
        """
        Manipula o evento de fechamento da janela
        
        Args:
            event: Evento de fechamento
        """
        # Se for a única janela aberta, fecha a aplicação
        if not wx.GetApp().main_screen or not wx.GetApp().main_screen.IsShown():
            wx.GetApp().ExitMainLoop()
        else:
            # Apenas esconde a janela se a tela principal estiver aberta
            self.Hide()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tela de login da aplicação com visual moderno
"""

import os
import wx
import logging
from src.api import APIError
from src.utils import AuthError
from src.utils.resource_manager import ResourceManager

logger = logging.getLogger("PrintManagementSystem.UI.LoginScreen")

class RoundedButton(wx.Button):
    """Botão personalizado com cantos arredondados"""
    
    def __init__(self, parent, id=wx.ID_ANY, label="", pos=wx.DefaultPosition, 
                 size=wx.DefaultSize, style=0, validator=wx.DefaultValidator, 
                 name=wx.ButtonNameStr):
        # Remova qualquer borda nativa que possa interferir com nossa renderização personalizada
        style |= wx.BORDER_NONE
        super().__init__(parent, id, label, pos, size, style, validator, name)
        
        self.SetBackgroundColour(wx.Colour(255, 90, 36))  # Cor laranja
        self.SetForegroundColour(wx.WHITE)
        
        # Eventos de hover
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
        
        # Redesenhar para cantos arredondados
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)  # Evita piscar durante redesenho
    
    def on_enter(self, event):
        """Manipula o evento de mouse sobre o botão"""
        self.SetBackgroundColour(wx.Colour(255, 120, 70))  # Cor de hover
        self.Refresh()
        
    def on_leave(self, event):
        """Manipula o evento de mouse saindo do botão"""
        self.SetBackgroundColour(wx.Colour(255, 90, 36))  # Cor original
        self.Refresh()
    
    def on_paint(self, event):
        """Redesenha o botão com cantos arredondados"""
        # Usamos BufferedPaintDC para evitar flicker
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetParent().GetBackgroundColour()))
        dc.Clear()
        
        rect = self.GetClientRect()
        
        # Desenha o fundo com cantos arredondados
        dc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        dc.SetPen(wx.Pen(self.GetBackgroundColour(), 1))
        
        # Raio para cantos arredondados - aumentado para ser mais perceptível
        radius = 8
        dc.DrawRoundedRectangle(0, 0, rect.width, rect.height, radius)
        
        # Desenha o texto centralizado
        dc.SetFont(self.GetFont())
        dc.SetTextForeground(self.GetForegroundColour())
        
        text = self.GetLabel()
        text_width, text_height = dc.GetTextExtent(text)
        
        x = (rect.width - text_width) // 2
        y = (rect.height - text_height) // 2
        dc.DrawText(text, x, y)

class CustomTextCtrl(wx.Panel):
    """Campo de texto personalizado com cantos arredondados"""
    
    def __init__(self, parent, id=wx.ID_ANY, value="", pos=wx.DefaultPosition,
                 size=wx.DefaultSize, style=0, validator=wx.DefaultValidator,
                 name=wx.TextCtrlNameStr):
        super().__init__(parent, id=id, pos=pos, size=size)
        
        # Define a cor de fundo do painel
        self.SetBackgroundColour(wx.Colour(18, 18, 18))  # Mesmo que o fundo da janela
        
        # Cria o controle de texto real dentro de um painel para controlar seu tamanho e posição
        self.text_ctrl = wx.TextCtrl(self, -1, value=value, pos=(0, 0), style=style|wx.BORDER_NONE)
        self.text_ctrl.SetBackgroundColour(wx.Colour(35, 35, 35))  # Cinza escuro
        self.text_ctrl.SetForegroundColour(wx.WHITE)
        
        # Mantém o estilo original
        self.is_password = bool(style & wx.TE_PASSWORD)
        
        # Garante que o texto esteja centralizado verticalmente
        self.text_ctrl.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        # Eventos para redesenhar o painel com cantos arredondados
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)  # Evita piscar
        
        # Propaga eventos de foco
        self.text_ctrl.Bind(wx.EVT_SET_FOCUS, self.on_focus)
        self.text_ctrl.Bind(wx.EVT_KILL_FOCUS, self.on_blur)
        
        # Estado de foco
        self.has_focus = False
    
    def on_focus(self, event):
        """Manipula o evento de receber foco"""
        self.has_focus = True
        self.Refresh()
        event.Skip()
    
    def on_blur(self, event):
        """Manipula o evento de perder foco"""
        self.has_focus = False
        self.Refresh()
        event.Skip()
    
    def on_size(self, event):
        """Ajusta o tamanho do controle de texto quando o painel é redimensionado"""
        size = self.GetSize()
        # Mantém uma margem de 10px em cada lado para o padding visual
        padding = 10
        self.text_ctrl.SetSize(size.width - 2*padding, size.height - 2*padding)
        self.text_ctrl.SetPosition((padding, padding//2))
        event.Skip()
    
    def on_paint(self, event):
        """Desenha o painel com cantos arredondados"""
        dc = wx.BufferedPaintDC(self)
        dc.SetBackground(wx.Brush(self.GetBackgroundColour()))
        dc.Clear()
        
        rect = self.GetClientRect()
        
        # Cor do fundo do input
        bg_color = wx.Colour(35, 35, 35)
        
        # Cor da borda - mais visível quando o controle tem foco
        if self.has_focus:
            border_color = wx.Colour(60, 60, 60)  # Borda mais clara quando em foco
        else:
            border_color = wx.Colour(45, 45, 45)  # Borda sutil sem foco
        
        # Desenha a borda primeiro
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.SetPen(wx.Pen(border_color, 1))
        
        # Raio para cantos arredondados
        radius = 8  # Aumentado para ser mais perceptível
        dc.DrawRoundedRectangle(0, 0, rect.width, rect.height, radius)
        
        # Agora desenha o fundo
        dc.SetBrush(wx.Brush(bg_color))
        dc.SetPen(wx.Pen(bg_color, 1))
        dc.DrawRoundedRectangle(1, 1, rect.width-2, rect.height-2, radius-1)
    
    # Métodos para atuar como proxy para o wx.TextCtrl interno
    def SetValue(self, value):
        self.text_ctrl.SetValue(value)
    
    def GetValue(self):
        return self.text_ctrl.GetValue()
    
    def SetHint(self, hint):
        self.text_ctrl.SetHint(hint)
    
    def SetFont(self, font):
        self.text_ctrl.SetFont(font)
    
    def Bind(self, event, handler, source=None, id=wx.ID_ANY, id2=wx.ID_ANY):
        if source is None:
            source = self
        if event in [wx.EVT_TEXT, wx.EVT_TEXT_ENTER]:
            self.text_ctrl.Bind(event, handler)
        else:
            super().Bind(event, handler, source, id, id2)
    
    def SetForegroundColour(self, colour):
        self.text_ctrl.SetForegroundColour(colour)

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
        # Usando um estilo de frame padrão para evitar problemas de renderização
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Login - Sistema de Gerenciamento de Impressão",
            pos=wx.DefaultPosition,
            size=wx.Size(420, 600),
            style=wx.DEFAULT_FRAME_STYLE & ~(wx.RESIZE_BORDER | wx.MAXIMIZE_BOX)
        )
        
        self.auth_manager = auth_manager
        self.theme_manager = theme_manager
        self.on_login_success = on_login_success
        
        # Configura o ícone da aplicação
        icon_path = ResourceManager.get_icon_path("icon.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path))
        
        self._init_ui()
        
        # Centraliza a janela na tela
        self.Centre(wx.BOTH)
        
        # Aplica o tema atual: forçando fundo escuro
        self.SetBackgroundColour(wx.Colour(18, 18, 18))
        
        # Evita fechar a aplicação quando esta janela for fechada
        self.Bind(wx.EVT_CLOSE, self.on_close)
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Painel principal com cor de fundo escura
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        
        # Layout principal (vertical)
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Logo como na imagem
        logo_path = ResourceManager.get_image_path("logo.png")
        logo_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        if os.path.exists(logo_path):
            logo_bitmap = wx.Bitmap(logo_path)
            if logo_bitmap.IsOk():
                logo_bitmap = self._scale_bitmap(logo_bitmap, 80, 80)
                logo = wx.StaticBitmap(self.panel, wx.ID_ANY, logo_bitmap)
                logo_sizer.Add(logo, 0, wx.ALL | wx.ALIGN_CENTER, 10)
        
        main_sizer.Add(logo_sizer, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        
        # Título "Bem-vindo!"
        welcome_text = wx.StaticText(self.panel, wx.ID_ANY, "Bem-vindo!")
        welcome_text.SetFont(wx.Font(24, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        welcome_text.SetForegroundColour(wx.WHITE)
        main_sizer.Add(welcome_text, 0, wx.ALIGN_CENTER | wx.TOP, 10)
        
        # Subtítulo
        subtitle_text = wx.StaticText(self.panel, wx.ID_ANY, "Acesse sua conta para gerenciar seus serviços.")
        subtitle_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        subtitle_text.SetForegroundColour(wx.Colour(180, 180, 180))
        main_sizer.Add(subtitle_text, 0, wx.ALIGN_CENTER | wx.TOP | wx.BOTTOM, 15)
        
        # Margens laterais para o formulário
        form_margin = 25
        form_width = 370  # Largura total do formulário
        
        # Formulário de login
        form_panel = wx.Panel(self.panel)
        form_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        form_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Campo de email
        email_label = wx.StaticText(form_panel, wx.ID_ANY, "Email")
        email_label.SetForegroundColour(wx.WHITE)
        email_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        self.email_input = CustomTextCtrl(form_panel, style=wx.TE_PROCESS_ENTER)
        self.email_input.SetMinSize((form_width-2*form_margin, 35))  # 20px de altura como na imagem
        self.email_input.SetHint("Seu email")
        
        # Campo de senha
        password_label = wx.StaticText(form_panel, wx.ID_ANY, "Senha")
        password_label.SetForegroundColour(wx.WHITE)
        password_label.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        self.password_input = CustomTextCtrl(form_panel, style=wx.TE_PASSWORD | wx.TE_PROCESS_ENTER)
        self.password_input.SetMinSize((form_width-2*form_margin, 35))  # 50px de altura como na imagem
        self.password_input.SetHint("••••••••••••")
        
        # Checkbox "Lembrar-me" 
        self.remember_checkbox = wx.CheckBox(form_panel, wx.ID_ANY, "Lembrar-me")
        self.remember_checkbox.SetForegroundColour(wx.WHITE)
        
        # Mensagem de erro
        self.error_message = wx.StaticText(form_panel, wx.ID_ANY, "")
        self.error_message.SetForegroundColour(wx.Colour(220, 53, 69))
        self.error_message.Hide()
        
        # Botão de login
        self.login_button = RoundedButton(form_panel, label="Entrar")
        self.login_button.SetMinSize((form_width-2*form_margin, 50))  # 50px de altura
        self.login_button.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.login_button.Bind(wx.EVT_BUTTON, self.on_login)
        
        # Adiciona elementos ao formulário
        form_sizer.Add(email_label, 0, wx.LEFT | wx.BOTTOM, 8)
        form_sizer.Add(self.email_input, 0, wx.EXPAND | wx.BOTTOM, 15)
        form_sizer.Add(password_label, 0, wx.LEFT | wx.BOTTOM, 8)
        form_sizer.Add(self.password_input, 0, wx.EXPAND | wx.BOTTOM, 15)
        form_sizer.Add(self.remember_checkbox, 0, wx.LEFT | wx.BOTTOM, 15)
        form_sizer.Add(self.error_message, 0, wx.EXPAND | wx.BOTTOM, 15)
        form_sizer.Add(self.login_button, 0, wx.EXPAND | wx.TOP, 10)
        
        form_panel.SetSizer(form_sizer)
        
        # Adiciona o formulário ao layout principal com margens nas laterais
        main_sizer.Add(form_panel, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, form_margin)
        
        # Define o sizer para o painel principal
        self.panel.SetSizer(main_sizer)
        
        # Bind do evento de tecla Enter
        self.email_input.Bind(wx.EVT_TEXT_ENTER, self.on_login)
        self.password_input.Bind(wx.EVT_TEXT_ENTER, self.on_login)
        
        # Preencher com os valores padrão para testes
        self.email_input.SetValue("eduardo.sirino@loqquei.com.br")
        self.password_input.SetValue("EdusEdus@747466")
    
    def _scale_bitmap(self, bitmap, width, height):
        """Redimensiona um bitmap para o tamanho especificado"""
        image = bitmap.ConvertToImage()
        image = image.Scale(width, height, wx.IMAGE_QUALITY_HIGH)
        return wx.Bitmap(image)
    
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
        self.panel.Layout()
    
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
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gerenciador de temas da aplicação
"""

import wx
import logging

logger = logging.getLogger("PrintManagementSystem.Utils.Theme")

class ThemeManager:
    """Gerenciador de temas da aplicação"""
    
    # Cores para o tema escuro
    DARK_THEME = {
        "bg_color": wx.Colour(18, 18, 18),
        "panel_bg": wx.Colour(25, 25, 25),
        "input_bg": wx.Colour(35, 35, 35),
        "text_color": wx.Colour(240, 240, 240),
        "text_secondary": wx.Colour(180, 180, 180),
        "accent_color": wx.Colour(255, 90, 36),
        "accent_hover": wx.Colour(255, 120, 70),
        "border_color": wx.Colour(45, 45, 45),
        "icon_color": wx.Colour(200, 200, 200),
        "btn_text": wx.Colour(255, 255, 255),
        "success_color": wx.Colour(40, 167, 69),
        "error_color": wx.Colour(220, 53, 69),
        "warning_color": wx.Colour(255, 193, 7),
        "info_color": wx.Colour(23, 162, 184),
        "toggle_on": wx.Colour(255, 90, 36),
        "toggle_off": wx.Colour(100, 100, 100),
        "hover_bg": wx.Colour(40, 40, 40),
        "disabled_bg": wx.Colour(70, 70, 70),
        "disabled_text": wx.Colour(150, 150, 150),
    }
    
    # Cores para o tema claro
    LIGHT_THEME = {
        "bg_color": wx.Colour(248, 248, 248),
        "panel_bg": wx.Colour(255, 255, 255),
        "input_bg": wx.Colour(245, 245, 245),
        "text_color": wx.Colour(33, 37, 41),
        "text_secondary": wx.Colour(90, 90, 90),
        "accent_color": wx.Colour(255, 90, 36),
        "accent_hover": wx.Colour(255, 120, 70),
        "border_color": wx.Colour(230, 230, 230),
        "icon_color": wx.Colour(40, 40, 40),
        "btn_text": wx.Colour(255, 255, 255),
        "success_color": wx.Colour(40, 167, 69),
        "error_color": wx.Colour(220, 53, 69),
        "warning_color": wx.Colour(255, 193, 7),
        "info_color": wx.Colour(23, 162, 184),
        "toggle_on": wx.Colour(255, 90, 36),
        "toggle_off": wx.Colour(200, 200, 200),
        "hover_bg": wx.Colour(240, 240, 240),
        "disabled_bg": wx.Colour(200, 200, 200),
        "disabled_text": wx.Colour(120, 120, 120),
    }
    
    def __init__(self, config):
        """
        Inicializa o gerenciador de temas
        
        Args:
            config: Objeto de configuração da aplicação
        """
        self.config = config
        
        # Verifica se o método get_theme existe, caso contrário usa o método get
        if hasattr(config, 'get_theme') and callable(getattr(config, 'get_theme')):
            self.current_theme = config.get_theme()
        else:
            # Se não existe get_theme, tenta usar o método get
            self.current_theme = config.get("theme", "dark")
    
    def get_theme_colors(self):
        """
        Obtém cores do tema atual
        
        Returns:
            dict: Dicionário com cores do tema
        """
        return self.DARK_THEME if self.current_theme == "dark" else self.LIGHT_THEME
    
    def switch_theme(self):
        """
        Alterna entre temas claro e escuro
        
        Returns:
            str: Nome do novo tema ("dark" ou "light")
        """
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.current_theme = new_theme
        
        # Verifica se o método set_theme existe, caso contrário usa o método set
        if hasattr(self.config, 'set_theme') and callable(getattr(self.config, 'set_theme')):
            self.config.set_theme(new_theme)
        else:
            # Se não existe set_theme, tenta usar o método set
            self.config.set("theme", new_theme)
            
        return new_theme
    
    def set_theme(self, theme):
        """
        Define o tema da aplicação
        
        Args:
            theme (str): "dark" ou "light"
            
        Returns:
            bool: True se o tema foi alterado
        """
        if theme in ["dark", "light"] and theme != self.current_theme:
            self.current_theme = theme
            
            # Verifica se o método set_theme existe, caso contrário usa o método set
            if hasattr(self.config, 'set_theme') and callable(getattr(self.config, 'set_theme')):
                self.config.set_theme(theme)
            else:
                # Se não existe set_theme, tenta usar o método set
                self.config.set("theme", theme)
                
            return True
        
        return False
    
    def apply_theme_to_window(self, window):
        """
        Aplica o tema atual à janela
        
        Args:
            window (wx.Window): Janela para aplicar o tema
        """
        colors = self.get_theme_colors()
        
        # Aplica cor de fundo na janela principal
        window.SetBackgroundColour(colors["bg_color"])
        
        # Atualiza todos os controles filhos recursivamente
        self._apply_theme_to_children(window, colors)
        
        # Força redesenho da janela
        window.Refresh()
    
    def _apply_theme_to_children(self, parent, colors):
        """
        Aplica o tema recursivamente aos filhos de um controle
        
        Args:
            parent (wx.Window): Controle pai
            colors (dict): Cores do tema
        """
        for child in parent.GetChildren():
            # Aplica tema baseado no tipo do controle
            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(colors["panel_bg"])
                child.SetForegroundColour(colors["text_color"])
            
            elif isinstance(child, (wx.TextCtrl, wx.ComboBox)):
                child.SetBackgroundColour(colors["input_bg"])
                child.SetForegroundColour(colors["text_color"])
            
            elif isinstance(child, wx.Button):
                if hasattr(child, "is_accent_button") and child.is_accent_button:
                    child.SetBackgroundColour(colors["accent_color"])
                    child.SetForegroundColour(colors["btn_text"])
                else:
                    child.SetBackgroundColour(colors["panel_bg"])
                    child.SetForegroundColour(colors["text_color"])
            
            elif isinstance(child, wx.StaticText):
                child.SetForegroundColour(
                    colors["text_secondary"] if hasattr(child, "is_secondary") and child.is_secondary else colors["text_color"]
                )
            
            elif isinstance(child, wx.CheckBox):
                child.SetForegroundColour(colors["text_color"])
            
            # Recursivamente aplica o tema aos filhos
            if child.GetChildren():
                self._apply_theme_to_children(child, colors)
    
    def get_custom_button(self, parent, label, accent=False, icon=None, size=(-1, -1)):
        """
        Cria um botão personalizado com o tema atual
        
        Args:
            parent (wx.Window): Pai do botão
            label (str): Texto do botão
            accent (bool): Se o botão deve usar cor de destaque
            icon (wx.Bitmap, optional): Ícone do botão
            size (tuple): Tamanho do botão
            
        Returns:
            wx.Button: Botão personalizado
        """
        button = wx.Button(parent, label=label, size=size)
        colors = self.get_theme_colors()
        
        if accent:
            button.SetBackgroundColour(colors["accent_color"])
            button.SetForegroundColour(colors["btn_text"])
            button.is_accent_button = True
            
            # Eventos de hover para botão de destaque
            def on_enter(evt):
                button.SetBackgroundColour(colors["accent_hover"])
                button.Refresh()
                
            def on_leave(evt):
                button.SetBackgroundColour(colors["accent_color"])
                button.Refresh()
            
            button.Bind(wx.EVT_ENTER_WINDOW, on_enter)
            button.Bind(wx.EVT_LEAVE_WINDOW, on_leave)
        else:
            button.SetBackgroundColour(colors["panel_bg"])
            button.SetForegroundColour(colors["text_color"])
            
            # Eventos de hover para botão normal
            def on_enter(evt):
                button.SetBackgroundColour(colors["hover_bg"])
                button.Refresh()
                
            def on_leave(evt):
                button.SetBackgroundColour(colors["panel_bg"])
                button.Refresh()
            
            button.Bind(wx.EVT_ENTER_WINDOW, on_enter)
            button.Bind(wx.EVT_LEAVE_WINDOW, on_leave)
        
        if icon:
            button.SetBitmap(icon)
            button.SetBitmapMargins((5, 0))
        
        return button
    
    def get_theme_bitmap(self, path, size=None):
        """
        Carrega um bitmap com cores ajustadas para o tema atual
        
        Args:
            path (str): Caminho do arquivo de imagem
            size (tuple, optional): Tamanho para redimensionar (width, height)
            
        Returns:
            wx.Bitmap: Bitmap carregado e ajustado
        """
        try:
            bitmap = wx.Bitmap(path)
            
            if size:
                img = bitmap.ConvertToImage()
                img = img.Scale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
                bitmap = wx.Bitmap(img)
            
            return bitmap
        except Exception as e:
            logger.error(f"Erro ao carregar bitmap: {str(e)}")
            # Retorna um bitmap vazio em caso de erro
            return wx.Bitmap(1, 1) if size is None else wx.Bitmap(size[0], size[1])
    
    @property
    def is_dark(self):
        """
        Verifica se o tema atual é escuro
        
        Returns:
            bool: True se o tema atual é escuro
        """
        return self.current_theme == "dark"
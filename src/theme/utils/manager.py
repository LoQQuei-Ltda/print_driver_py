import wx
from src.logger.utils.logger import logger

class ThemeManager:
    """Gerencia o gerenciador de temas"""

    def __init__(self, config_manager):
        self.config_manager = config_manager
        self.current_theme = self.config_manager.config["theme"]

        self.dark_theme = {
            "bg_color": wx.Colour(33, 33, 33),
            "sidebar_color": wx.Colour(25, 25, 25),
            "text_color": wx.Colour(255, 255, 255),
            "accent_color": wx.Colour(255, 87, 34),
            "secondary_text_color": wx.Colour(160, 160, 160),
            "hover_color": wx.Colour(50, 50, 50),
            "border_color": wx.Colour(60, 60, 60),
            "input_bg_color": wx.Colour(45, 45, 45),
            "button_color": wx.Colour(255, 87, 34),
            "button_text_color": wx.Colour(255, 255, 255),
            "disabled_color": wx.Colour(100, 100, 100)
        }

        self.light_theme = {
            "bg_color": wx.Colour(245, 245, 245),
            "sidebar_color": wx.Colour(220, 220, 220),
            "text_color": wx.Colour(33, 33, 33),
            "accent_color": wx.Colour(255, 87, 34),
            "secondary_text_color": wx.Colour(120, 120, 120),
            "hover_color": wx.Colour(230, 230, 230),
            "border_color": wx.Colour(200, 200, 200),
            "input_bg_color": wx.Colour(255, 255, 255),
            "button_color": wx.Colour(255, 87, 34),
            "button_text_color": wx.Colour(255, 255, 255),
            "disabled_color": wx.Colour(180, 180, 180)
        }

    def get_color(self, color_key):
        """Retorna a cor do tema atual"""
        if self.current_theme == "dark":
            return self.dark_theme.get(color_key)
        else:
            return self.light_theme.get(color_key)
        
    def toggle_theme(self):
        """Alterna o tema atual"""
        self.current_theme = "light" if self.current_theme == "dark" else "dark"
        self.config_manager.config["theme"] = self.current_theme
        self.config_manager.save_config()
        logger.info("Tema alternado para %s", self.current_theme)
        return self.current_theme
    
    def set_theme(self, theme):
        """Define o tema atual"""
        if theme in ["light", "dark"]:
            self.current_theme = theme
            self.config_manager.config["theme"] = theme
            self.config_manager.save_config()
            logger.info("Tema definido para %s", theme)
        else:
            logger.error("Tema inválido: %s", theme)

    def apply_theme_to_panel(self, panel):
        """Aplica o tema atual a um painel"""
        panel.SetBackgroundColour(self.get_color("bg_color"))

        for child in panel.GetChildren():
            if isinstance(child, wx.StaticText):
                child.SetForegroundColour(self.get_color("text_color"))

    def apply_theme_to_window(self, window):
        """Aplica o tema atual a janela"""
        self.apply_theme_to_panel(window)

        for child in window.GetChildren():
            if isinstance(child, wx.Panel):
                self.apply_theme_to_panel(child)

        
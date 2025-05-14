"""Tema do aplicativo"""
import logging
import wx

logger = logging.getLogger("PrintManager.Utils.Theme")

class ThemeManager:
    """Gerencia o tema do aplicativo"""

    DARK_THEME = {
        "bg_color": wx.Colour(25, 25, 25),
        "panel_bg": wx.Colour(35, 35, 35),
        "input_bg": wx.Colour(45, 45, 45),
        "text_color": wx.Colour(240, 240, 240),
        "text_secondary": wx.Colour(200, 200, 200),
        "accent_color": wx.Colour(255, 90, 36),
        "accent_hover": wx.Colour(255, 120, 70),
        "border_color": wx.Colour(60, 60, 60),
        "icon_color": wx.Colour(200, 200, 200),
        "btn_text": wx.Colour(255, 255, 255),
        "success_color": wx.Colour(40, 167, 69),
        "error_color": wx.Colour(220, 53, 69),
        "warning_color": wx.Colour(255, 193, 7),
        "info_color": wx.Colour(23, 162, 184),
        "toggle_on": wx.Colour(255, 90, 36),
        "toggle_off": wx.Colour(100, 100, 100),
        "hover_bg": wx.Colour(50, 50, 50),
        "disabled_bg": wx.Colour(70, 70, 70),
        "disabled_text": wx.Colour(150, 150, 150),
    }

    LIGHT_THEME = {
        "bg_color": wx.Colour(240, 240, 240),
        "panel_bg": wx.Colour(250, 250, 250),
        "input_bg": wx.Colour(255, 255, 255),
        "text_color": wx.Colour(33, 37, 41),
        "text_secondary": wx.Colour(90, 90, 90),
        "accent_color": wx.Colour(255, 90, 36),
        "accent_hover": wx.Colour(220, 70, 20),
        "border_color": wx.Colour(222, 226, 230),
        "icon_color": wx.Colour(40, 40, 40),
        "btn_text": wx.Colour(255, 255, 255),
        "success_color": wx.Colour(40, 167, 69),
        "error_color": wx.Colour(220, 53, 69),
        "warning_color": wx.Colour(255, 193, 7),
        "info_color": wx.Colour(23, 162, 184),
        "toggle_on": wx.Colour(255, 90, 36),
        "toggle_off": wx.Colour(200, 200, 200),
        "hover_bg": wx.Colour(230, 230, 230),
        "disabled_bg": wx.Colour(200, 200, 200),
        "disabled_text": wx.Colour(120, 120, 120),
    }

    def __init__(self, config):
        """Inicializa o gerenciador de temas"""
        self.config = config
        self.current_theme = config.get_theme()

    def get_theme_colors(self):
        """Retorna as cores do tema atual"""
        return self.DARK_THEME if self.current_theme == "dark" else self.LIGHT_THEME

    def switch_theme(self):
        """Alterna o tema atual"""
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.current_theme = new_theme
        self.config.set_theme(new_theme)
        return new_theme

    def set_theme(self, theme):
        """Define o tema atual"""
        if theme in ["light", "dark"] and theme != self.current_theme:
            self.current_theme = theme
            self.config.set_theme(theme)
            return True
        return False

    def apply_theme_to_window(self, window):
        """Aplica o tema atual a janela"""
        colors = self.get_theme_colors()

        window.SetBackgroundColour(colors["bg_color"])

        self._apply_theme_to_children(window, colors)

        window.Refresh()

    def _apply_theme_to_children(self, parent, colors):
        """Aplica o tema a um controle filho"""
        for child in parent.GetChildren():
            if isinstance(child, wx.Panel):
                child.SetBackgroundColour(colors["panel_bg"])
                child.SetForegroundColour(colors["text_color"])

            elif isinstance(child, (wx.TextCtrl, wx.ComboBox)):
                child.SetBackgroundColour(colors["input_bg"])
                child.SetForegroundColour(colors["text_color"])

            elif isinstance(child, wx.Button):
                child.SetBackgroundColour(colors["input_bg"])
                child.SetForegroundColour(colors["btn_text"])

            elif isinstance(child, wx.Button):
                if hasattr(child, "is_accent_button") and child.is_accent_button:
                    child.SetBackgroundColour(colors["accent_color"])
                    child.SetForegroundColour(colors["btn_text"])
                else:
                    child.SetBackgroundColour(colors["panel_bg"])
                    child.SetForegroundColour(colors["text_color"])

            elif isinstance(child, wx.StaticText):
                child.SetForegroundColour(
                    colors["text_secondary"] if hasattr(child, "is_secondary") and
                    child.is_secondary else colors["text_color"]
                )

            elif isinstance(child, wx.CheckBox):
                child.SetForegroundColour(colors["text_color"])

            if child.GetChildren():
                self._apply_theme_to_children(child, colors)

    def get_custom_button(self, parent, label, accent=False, icon=None):
        """Retorna um botão customizado"""
        button = wx.Button(parent, label=label)
        colors = self.get_theme_colors()

        if accent:
            button.SetBackgroundColour(colors["accent_color"])
            button.SetForegroundColour(colors["btn_text"])
            button.is_accent_button = True
        else:
            button.SetBackgroundColour(colors["panel_bg"])
            button.SetForegroundColour(colors["text_color"])

        if icon:
            button.SetBitmap(wx.BitmapFromImage(icon))
            button.SetBitmapMargins((5, 0))

        return button

    def get_theme_bitmap(self, path, size=None):
        """Retorna um bitmap customizado"""
        try:
            bitmap = wx.BitmapFromImage(wx.Image(path))
            if size:
                img = bitmap.ConvertToImage()
                img = img.Scale(size[0], size[1], wx.IMAGE_QUALITY_HIGH)
                bitmap = wx.BitmapFromImage(img)

            return bitmap
        except Exception as e:
            logger.error("Erro ao carregar bitmap: %s", e)
            return wx.EmptyImage(1, 1) if size else wx.EmptyImage(size[0], size[1])

    @property
    def is_dark(self):
        """Retorna se o tema atual é escuro"""
        return self.current_theme == "dark"

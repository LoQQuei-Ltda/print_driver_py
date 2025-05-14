"""Tela de login"""
import logging
import os
import wx
from src.api import APIError
from src.utils import AuthError

logger = logging.getLogger("PrintManager.UI.LoginScreen")

class LoginScreen(wx.Frame):
    """Tela de login"""

    def __init__(self, parent, auth_manager, theme_manager, on_login_success):
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Login - Gerenciador de Impressão",
            pos=wx.DefaultPosition,
            size=wx.Size(400, 500),
            style=wx.DEFAULT_FRAME_STYLE
        )

        self.auth_manager = auth_manager
        self.theme_manager = theme_manager
        self.on_login_success = on_login_success

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "ui", "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path, wx.BITMAP_TYPE_ICO))

        self.__init_ui()

        self.Centre(wx.BOTH)

        self.theme_manager.apply_theme_to_window(self)
        
        self.Bind(wx.EVT_CLOSE, self.on_close)

        wx.CallAfter(self._try_auto_login)

    def __init_ui(self):
        """Inicializa a interface gráfica"""
        colors = self.theme_manager.get_theme_colors()

        panel = wx.Panel(self)
        panel.SetBackgroundColour(colors["panel_bg"])

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "ui", "resources", "logo.png")
        if os.path.exists(logo_path):
            logo_bitmap = wx.Bitmap(logo_path)
            logo = wx.StaticBitmap(panel, wx.ID_ANY, logo_bitmap, wx.DefaultPosition, wx.Size(100, 100))

        else:
            logo = wx.StaticText(panel, wx.ID_ANY, "LoQQuei")
            logo.SetFont(wx.Font(20, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            logo.SetForegroundColour(colors["accent_color"])

        title = wx.StaticText(panel, wx.ID_ANY, "Gerenciador de Impressão")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        email_label = wx.StaticText(panel, wx.ID_ANY, "Email:")
        self.email_input = wx.TextCtrl(panel, wx.ID_ANY)
        self.email_input.SetBackgroundColour(colors["input_bg"])

        password_label = wx.StaticText(panel, wx.ID_ANY, "Senha:")
        self.password_input = wx.TextCtrl(panel, wx.ID_ANY, style=wx.TE_PASSWORD)
        self.password_input.SetBackgroundColour(colors["input_bg"])

        self.remember_checkbox = wx.CheckBox(panel, wx.ID_ANY, "Lembrar-me")

        self.error_message = wx.StaticText(panel, wx.ID_ANY, "")
        self.error_message.SetForegroundColour(colors["error_color"])
        self.error_message.hide()

        self.login_button = wx.Button(panel, "Entrar", accent=True)
        self.login_button.bind(wx.EVT_BUTTON, self.on_login)

        main_sizer.AddSpacer(30)

        logo_sizer = wx.BoxSizer(wx.HORIZONTAL)
        logo_sizer.Add((0, 0), 1, wx.EXPAND)
        logo_sizer.Add(logo, 0, wx.ALIGN_CENTER)
        logo_sizer.Add((0, 0), 1, wx.EXPAND)
        main_sizer.Add(logo_sizer, 0, wx.EXPAND | wx.ALL, 5)

        main_sizer.AddSpacer(10)

        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        title_sizer.Add((0, 0), 1, wx.EXPAND)
        title_sizer.Add(title, 0, wx.ALIGN_CENTER)
        title_sizer.Add((0, 0), 1, wx.EXPAND)
        main_sizer.Add(title_sizer, 0, wx.EXPAND | wx.ALL, 5)

        main_sizer.AddSpacer(30)

        main_sizer.Add(email_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 20)
        main_sizer.Add(self.email_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        main_sizer.Add(password_label, 0, wx.LEFT | wx.RIGHT | wx.TOP, 20)
        main_sizer.Add(self.password_input, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(15)

        main_sizer.Add(self.remember_checkbox, 0, wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(10)

        main_sizer.Add(self.error_message, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(30)

        main_sizer.Add(self.login_button, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(30)

        panel.SetSizer(main_sizer)

        self.email_input.Bind(wx.EVT_TEXT, self.on_login)
        self.password_input.Bind(wx.EVT_TEXT, self.on_login)

    def _try_auto_login(self):
        """Tenta fazer login automático"""
        try:
            if self.auth_manager.auto_login():
                self.on_login_success()
        except Exception as e:
            logger.error("Erro ao fazer login automático: %s", e)

    def on_login(self, event = None):
        """Faz login"""
        email = self.email_input.GetValue()
        password = self.password_input.GetValue()
        remember_me = self.remember_checkbox.GetValue()

        if not email:
            self._show_error("Por favor, insira seu email.")
            return

        if not password:
            self._show_error("Por favor, insira sua senha.")
            return

        try:
            self.login_button.Disable()
            self.login_button.SetLabel("Entrando...")

            wx.GetApp().Yield()

            if self.auth_manager.login(email, password, remember_me):
                self.on_login_success()
            else:
                self._show_error("Falha ao fazer login. Verifique suas credenciais.")

        except AuthError as e:
            self._show_error(str(e))

        except APIError as e:
            self._show_error(f"Erro de API: {str(e)}")

        except Exception as e:
            logger.error(f"Erro desconhecido no login: {str(e)}")
            self._show_error(f"Erro ao fazer login: {str(e)}")

        finally:
            self.login_button.Enable()
            self.login_button.SetLabel("Entrar")

    def _show_error(self, message):
        """Mostra uma mensagem de erro"""
        self.error_message.SetLabel(message)
        self.error_message.Show()
        self.Layout()

    def on_close(self):
        """Fecha a janela principal"""
        if not wx.GetApp().main_screen or not wx.GetApp().main_screen.IsShown():
            wx.GetApp().ExitMainLoop()

        else:
            self.Hide()
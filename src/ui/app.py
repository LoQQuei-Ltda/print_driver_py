"""Aplicação principal"""
import logging
import os
import sys
import wx
from src.api import APIClient
from src.utils import AuthManager, ThemeManager
from src.ui.login_screen import LoginScreen
from src.ui.main_screen import MainScreen

logger = logging.getLogger("PrintManager.UI.App")

class PrintManagementApp(wx.App):
    """Aplicação principal"""

    def __init__(self, redirect=False, filename=None):
        """Inicializa a aplicação"""
        self.login_screen = None
        self.main_screen = None
        self.config = None
        self.api_client = None
        self.auth_manager = None
        self.theme_manager = None

        super().__init__(redirect, filename)

    def OnInit(self):
        """Inicializa a aplicação"""
        if not self.config:
            logger.error("Configuração da aplicação não foi definida")
            return False

        api_url = self.config.get("api_url", "https://api.loqquei.com/api/v1")
        self.api_client = APIClient(api_url)

        self.auth_manager = AuthManager(self.config, self.api_client)

        self.theme_manager = ThemeManager(self.config)

        self.login_screen = LoginScreen(
            None,
            self.auth_manager,
            self.theme_manager,
            self.on_login_success
        )

        self.main_screen = None

        self.login_screen.Show()

        self.SetTopWindow(self.login_screen)

        sys._excepthook = sys.excepthook
        sys.excepthook = self.exception_hook

        return True
    
    def exception_hook(self, exc_type, exc_value, exc_traceback):
        """Trata as exceções"""
        logger.error("Exceção: %s", exc_value)
        wx.MessageBox(f"Erro: {str(exc_value)}", "Erro", wx.OK | wx.ICON_ERROR)
        sys._excepthook(exc_type, exc_value, exc_traceback)

    def on_login_success(self):
        """Executa quando o usuário faz login com sucesso"""
        if self.login_screen:
            self.login_screen.Hide()

        if not self.main_screen:
            self.main_screen = MainScreen(
                None, 
                self.auth_manager, 
                self.theme_manager,
                self.api_client,
                self.config,
                self.on_logout
            )

        self.main_screen.Show()

        self.SetTopWindow(self.main_screen)

    def on_logout(self):
        """Executa quando o usuário faz logout"""
        if self.main_screen:
            self.main_screen.Close()
            self.main_screen = None

        if not self.login_screen:
            self.login_screen = LoginScreen(
                None,
                self.auth_manager,
                self.theme_manager,
                self.on_login_success
            )

        self.login_screen.email_input.SetValue("")
        self.login_screen.password_input.SetValue("")

        self.login_screen.Show()
        self.SetTopWindow(self.login_screen)
import os
import json
import platform
from pathlib import Path
from src.logger.utils.logger import logger

class ConfigManager:
    """Gerencia o gerenciador de configurações"""
    def __init__(self):
        self.config_dir = Path.home() / "loqquei" / "print_manager"
        self.config_file = self.config_dir / "config.json"
        self.user_data_file = self.config_dir / "user_data.json"

        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.config = {
            "theme": self._get_system_theme(),
            "auto_print": False,
            "default_printer": None,
            "pdf_storage_path": str(Path.home() / "loqquei" / "print_manager" / "pdf")
        }

        self.user_data = {
            "token": None,
            "user_info": None
        }

        Path(self.config["pdf_storage_path"]).mkdir(parents=True, exist_ok=True)

        self.load_config()
        self.load_user_data()

    def load_config(self):
        """Carrega a configuração do aplicativo"""
        if self.config_file.exists():
            try:
                with open(self.config_file, "r") as f:
                    loaded_config = json.load(f)
                    self.config.update(loaded_config)
            except Exception as e:
                logger.error("Erro ao carregar configuração: %s", e)

    def save_config(self):
        """Salva a configuração do aplicativo"""
        try:
            with open(self.config_file, "w") as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logger.error("Erro ao salvar configuração: %s", e)

    def load_user_data(self):
        """Carrega os dados do usuário"""
        if self.user_data_file.exists():
            try:
                with open(self.user_data_file, "r") as f:
                    loaded_user_data = json.load(f)
                    self.user_data.update(loaded_user_data)
            except Exception as e:
                logger.error("Erro ao carregar dados do usuário: %s", e)

    def save_user_data(self):
        """Salva os dados do usuário"""
        try:
            with open(self.user_data_file, "w") as f:
                json.dump(self.user_data, f, indent=4)
        except Exception as e:
            logger.error("Erro ao salvar dados do usuário: %s", e)

    def set_user_info(self, token, user_info):
        """Define os dados do usuário"""
        self.user_data["token"] = token
        self.user_data["user_info"] = user_info
        self.save_user_data()

    def clear_user_info(self):
        """Limpa os dados do usuário"""
        self.user_data["token"] = None
        self.user_data["user_info"] = None
        self.save_user_data()

    def is_logged_in(self):
        """Verifica se o usuário está logado"""
        return self.user_data["token"] is not None and self.user_data["user_info"] is not None

    def _get_system_theme(self):
        """Obtém a preferência de tema do sistema (claro/escuro)"""
        if platform.system() == "Windows":
            try:
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value == 1 else "dark"
            except Exception:
                return "dark"
        elif platform.system() == "Darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True, text=True
                )
                return "dark" if "Dark" in result.stdout else "light"
            except Exception:
                return "dark"
        else:
            return "dark"
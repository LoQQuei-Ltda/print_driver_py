import os
import json
import logging
import platform

logger = logging.getLogger("PrintManager.Config")

class AppConfig:
    """Configurações do aplicativo"""

    def __init__(self, data_dir):
        """Inicializa configurações"""
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "config", "config.json")
        self.pdf_dir  = os.path.join(data_dir, "pdfs")
        self.temp_dir   = os.path.join(data_dir, "temp")

        self.default_config = {
            "theme": self._get_system_theme(),
            "api_url": "https://api.loqquei.com.br/api/v1",
            "auto_print": False,
            "default_printer": "",
            "user": {
                "email": "",
                "token": "",
                "name": "",
                "remember_me": False
            }
        }

        self.config = self._load_config()

    def _get_system_theme(self):
        """Retorna o tema padrão para a plataforma atual"""
        system = platform.system().lower()

        if system == "windows":
            try:
                import winreg
                key = winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, 
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
                )

                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value == 1 else "dark"
            except Exception as e:
                logger.warning("Erro ao ler tema do Windows: %s", str(e))
                return "dark"

        elif system == "darwin":
            try:
                import subprocess
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True,
                    text=True
                )
                return "dark" if "Dark" in result.stdout else "light"
            except Exception as e:
                logger.warning("Erro ao ler tema do macOS: %s", str(e))
                return "dark"
        
        else:
            try:
                import subprocess
                result = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                    capture_output=True,
                    text=True
                )
                return "dark" if "dark" in result.stdout.lower() else "light"
            except Exception as e:
                logger.warning("Erro ao ler tema do Linux: %s", str(e))
                return "dark"

    def _load_config(self):
        """Carrega configurações do arquivo"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                    for key, value in self.default_config.items():
                        if key not in config:
                            config[key] = value

                    return config
            else:
                return self._save_config(self.default_config)
        except Exception as e:
            logger.error("Erro ao carregar configuração: %s", str(e))
            return self._save_config(self.default_config)

    def _save_config(self, config):
        """Salva configurações no arquivo"""
        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            return config
        except Exception as e:
            logger.error(f"Erro ao salvar configuração: {str(e)}")
            return self.default_config

    def get(self, key, default=None):
        """Obtém um valor de configuração"""
        return self.config.get(key, default)

    def set(self, key, value):
        """Define um valor de configuração"""
        self.config[key] = value
        self._save_config(self.config)

    def get_user(self):
        """Retorna o usuário atual"""
        return self.config.get("user", self.default_config["user"])

    def set_user(self, user):
        """Define o usuário atual"""
        self.config["user"] = user
        self._save_config(self.config)

    def clear_user(self):
        """Limpa dados do usuário atual"""
        self.config["user"] = self.default_config["user"]
        self._save_config(self.config)

    def set_theme(self, theme):
        """Define o tema do aplicativo"""
        if theme in ["light", "dark"]:
            self.config["theme"] = theme
            self._save_config(self.config)
            logger.info(f"Tema definido para {theme}")
            return True
        return False
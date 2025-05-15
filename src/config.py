#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de configuração global da aplicação
"""

import os
import json
import logging
import platform
import wx

logger = logging.getLogger("PrintManagementSystem.Config")

class AppConfig:
    """Classe para gerenciar configurações da aplicação"""

    def __init__(self, data_dir):
        """
        Inicializa a configuração da aplicação
        
        Args:
            data_dir (str): Diretório de dados do usuário
        """
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "config", "config.json")
        self.pdf_dir = os.path.join(data_dir, "pdfs")
        self.temp_dir = os.path.join(data_dir, "temp")

        # Valores padrão
        self.default_config = {
            "theme": self._get_system_theme(),
            "api_url": "https://api.loqquei.com.br/api/v1",
            "auto_print": False,
            "default_printer": "",
            "user": {
                "email": "",
                "token": "",
                "remember_me": False
            }
        }

        # Carrega configurações ou cria se não existir
        self.config = self._load_config()

    def _get_system_theme(self):
        """
        Detecta o tema do sistema operacional
        
        Returns:
            str: "dark" ou "light"
        """
        system = platform.system()

        if system == "Windows":
            try:
                import winreg
                registry = winreg.ConnectRegistry(None, winreg.HKEY_CURRENT_USER)
                key = winreg.OpenKey(registry, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize")
                value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                return "light" if value == 1 else "dark"
            except Exception as e:
                logger.warning(f"Erro ao detectar tema do Windows: {str(e)}")
                return "dark"

        elif system == "Darwin":  # macOS
            try:
                import subprocess
                result = subprocess.run(
                    ["defaults", "read", "-g", "AppleInterfaceStyle"],
                    capture_output=True, text=True
                )
                return "dark" if "Dark" in result.stdout else "light"
            except Exception as e:
                logger.warning(f"Erro ao detectar tema do macOS: {str(e)}")
                return "light"

        else:  # Linux ou outros
            try:
                # Tentativa de detectar o tema para ambientes GNOME
                import subprocess
                result = subprocess.run(
                    ["gsettings", "get", "org.gnome.desktop.interface", "gtk-theme"],
                    capture_output=True, text=True
                )
                return "dark" if "dark" in result.stdout.lower() else "light"
            except Exception as e:
                logger.warning(f"Erro ao detectar tema do Linux: {str(e)}")
                return "dark"

    def _load_config(self):
        """
        Carrega configurações do arquivo ou cria um novo se não existir
        
        Returns:
            dict: Configurações carregadas
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # Garantir que todas as chaves padrão existam
                for key, value in self.default_config.items():
                    if key not in config:
                        config[key] = value
                        
                return config
            else:
                return self._save_config(self.default_config)
        except Exception as e:
            logger.error(f"Erro ao carregar configurações: {str(e)}")
            return self._save_config(self.default_config)

    def _save_config(self, config):
        """
        Salva configurações no arquivo
        
        Args:
            config (dict): Configurações a serem salvas
            
        Returns:
            dict: Configurações salvas
        """

        try:
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            return config
        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {str(e)}")
            return self.default_config

    def get(self, key, default=None):
        """
        Obtém valor de configuração
        
        Args:
            key (str): Chave da configuração
            default: Valor padrão se a chave não existir
            
        Returns:
            Valor da configuração
        """
        return self.config.get(key, default)

    def set(self, key, value):
        """
        Define valor de configuração
        
        Args:
            key (str): Chave da configuração
            value: Valor a ser definido
        """
        self.config[key] = value
        self._save_config(self.config)

    def get_user(self):
        """
        Obtém informações do usuário
        
        Returns:
            dict: Informações do usuário
        """
        return self.config.get("user", self.default_config["user"])

    def set_user(self, user_info):
        """
        Define informações do usuário
        
        Args:
            user_info (dict): Informações do usuário
        """
        self.config["user"] = user_info
        self._save_config(self.config)

    def clear_user(self):
        """Limpa informações do usuário"""
        self.config["user"] = self.default_config["user"]
        self._save_config(self.config)

    def get_theme(self):
        """
        Obtém o tema atual
        
        Returns:
            str: "dark" ou "light"
        """
        return self.config.get("theme", self.default_config["theme"])

    def set_theme(self, theme):
        """
        Define o tema
        
        Args:
            theme (str): "dark" ou "light"
        """
        if theme in ["dark", "light"]:
            self.config["theme"] = theme
            self._save_config(self.config)
            
    def get_printers(self):
        """
        Obtém a lista de impressoras salvas
        
        Returns:
            list: Lista de impressoras
        """
        return self.config.get("printers", [])

    def set_printers(self, printers):
        """
        Define a lista de impressoras
        
        Args:
            printers (list): Lista de impressoras
        """
        self.config["printers"] = printers
        self._save_config(self.config)

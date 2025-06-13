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
import getpass
import appdirs

logger = logging.getLogger("PrintManagementSystem.Config")

class AppConfig:
    """Classe para gerenciar configurações da aplicação"""

    def __init__(self, data_dir):
        # Configuração existente mantida...
        self.data_dir = data_dir
        self.config_file = os.path.join(data_dir, "config", "config.json")
        self.pdf_dir = os.path.join(data_dir, "pdfs")
        self.temp_dir = os.path.join(data_dir, "temp")
        self.system = platform.system()

        # Valores padrão estendidos
        self.default_config = {
            "theme": self._get_system_theme(),
            "api_url": "https://api.loqquei.com.br/api/v1",
            "api_port": 50000,
            "auto_print": False,
            "default_printer": "",
            "user": {
                "email": "",
                "token": "",
                "remember_me": False
            },
            "printers": [],
            "print_jobs": [],
            "print_history": [],
            "multi_user_mode": True,
            "user_directories": {},
            # === NOVA SEÇÃO: Cache de endpoints de impressora ===
            "printer_endpoint_cache": {},
            # === NOVA SEÇÃO: Configurações de performance ===
            "print_performance": {
                "max_parallel_workers": 4,
                "page_timeout": 15,
                "jpg_quality": 85,
                "max_dpi": 200,
                "retry_attempts": 2,
                "batch_processing": True
            }
        }

        self.config = self._load_config()
        self._ensure_directories()

    def get_printer_endpoint_cache(self):
        """Obtém cache de endpoints de impressoras"""
        return self.config.get("printer_endpoint_cache", {})
    
    def set_printer_endpoint_cache(self, cache):
        """Define cache de endpoints de impressoras"""
        self.config["printer_endpoint_cache"] = cache
        self._save_config(self.config)
    
    def get_print_performance_config(self):
        """Obtém configurações de performance"""
        return self.config.get("print_performance", self.default_config["print_performance"])
    
    def set_print_performance_config(self, perf_config):
        """Define configurações de performance"""
        self.config["print_performance"] = perf_config
        self._save_config(self.config)

    def _ensure_directories(self):
        """Garante que os diretórios necessários existam"""
        # Garante que o diretório de PDFs base exista
        os.makedirs(self.pdf_dir, exist_ok=True)
        
        # Se estiver no Windows, verifica diretórios de usuários
        if self.system == 'Windows' and self.get("multi_user_mode", True):
            self._ensure_user_directories()
    
    def _ensure_user_directories(self):
        """Garante que os diretórios de usuários estejam atualizados"""
        try:
            # Diretório Users
            users_dir = os.path.join(os.environ.get('SystemDrive', 'C:'), 'Users')
            
            if os.path.exists(users_dir):
                # Lista de usuários atuais no sistema
                for username in os.listdir(users_dir):
                    user_profile = os.path.join(users_dir, username)
                    
                    # Verifica se é um diretório de usuário válido
                    if os.path.isdir(user_profile) and not username.startswith('.'):
                        # Localização padrão AppData para o usuário
                        app_data = os.path.join(user_profile, 'AppData', 'Local')
                        
                        if os.path.exists(app_data):
                            user_pdf_dir = os.path.join(app_data, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                            
                            # Tenta criar o diretório se não existir
                            try:
                                if not os.path.exists(user_pdf_dir):
                                    os.makedirs(user_pdf_dir, exist_ok=True)
                                
                                # Atualiza o dicionário de diretórios de usuários
                                user_directories = self.get("user_directories", {})
                                user_directories[username] = user_pdf_dir
                                self.set("user_directories", user_directories)
                                
                                logger.debug(f"Diretório para usuário {username}: {user_pdf_dir}")
                            except PermissionError:
                                logger.debug(f"Sem permissão para criar diretório para o usuário {username}")
                            except Exception as e:
                                logger.debug(f"Erro ao processar diretório do usuário {username}: {e}")
        except Exception as e:
            logger.warning(f"Erro ao configurar diretórios de usuários: {e}")
    
    def get_user_pdf_dir(self, username=None):
        """
        Obtém o diretório de PDFs para um usuário específico
        
        Args:
            username (str, optional): Nome do usuário. Se None, usa o usuário atual.
            
        Returns:
            str: Caminho para o diretório de PDFs do usuário
        """
        # Se multi_user_mode estiver desativado, retorna o diretório base
        if not self.get("multi_user_mode", True):
            return self.pdf_dir
        
        # Se não foi especificado um usuário, usa o usuário atual
        if username is None:
            username = getpass.getuser()
        
        # Verifica se existe um diretório configurado para este usuário
        user_directories = self.get("user_directories", {})
        if username in user_directories:
            user_dir = user_directories[username]
            # Verifica se o diretório existe
            if os.path.exists(user_dir) or self._try_create_directory(user_dir):
                return user_dir
        
        # Se estiver no Windows, tenta criar no AppData do usuário
        if self.system == 'Windows':
            user_profile = os.path.join(os.environ.get('SystemDrive', 'C:'), 'Users', username)
            if os.path.exists(user_profile):
                app_data = os.path.join(user_profile, 'AppData', 'Local')
                if os.path.exists(app_data):
                    user_dir = os.path.join(app_data, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                    if self._try_create_directory(user_dir):
                        # Atualiza o dicionário de diretórios de usuários
                        user_directories[username] = user_dir
                        self.set("user_directories", user_directories)
                        return user_dir
        
        # Fallback: cria um subdiretório no diretório base
        user_dir = os.path.join(self.pdf_dir, username)
        if self._try_create_directory(user_dir):
            # Atualiza o dicionário de diretórios de usuários
            user_directories[username] = user_dir
            self.set("user_directories", user_directories)
            return user_dir
        
        # Em último caso, retorna o diretório base
        return self.pdf_dir
    
    def _try_create_directory(self, directory):
        """
        Tenta criar um diretório
        
        Args:
            directory (str): Caminho do diretório a ser criado
            
        Returns:
            bool: True se o diretório existe ou foi criado com sucesso
        """
        try:
            os.makedirs(directory, exist_ok=True)
            return True
        except Exception as e:
            logger.warning(f"Erro ao criar diretório {directory}: {e}")
            return False
    
    def get_all_pdf_directories(self):
        """
        Obtém todos os diretórios de PDFs configurados
        
        Returns:
            list: Lista de caminhos para diretórios de PDFs
        """
        directories = [self.pdf_dir]  # Diretório base sempre incluído
        
        # Adiciona diretórios de usuários
        if self.get("multi_user_mode", True):
            user_directories = self.get("user_directories", {})
            for user_dir in user_directories.values():
                if user_dir not in directories and os.path.exists(user_dir):
                    directories.append(user_dir)
        
        return directories

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
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0
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
                    capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0
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
    
    def get_print_jobs(self):
        """
        Obtém a lista de trabalhos de impressão ativos
        
        Returns:
            list: Lista de trabalhos de impressão
        """
        return self.config.get("print_jobs", [])
    
    def set_print_jobs(self, jobs):
        """
        Define a lista de trabalhos de impressão
        
        Args:
            jobs (list): Lista de trabalhos de impressão
        """
        self.config["print_jobs"] = jobs
        self._save_config(self.config)
    
    def add_print_job(self, job_data):
        """
        Adiciona um trabalho de impressão à lista
        
        Args:
            job_data (dict): Dados do trabalho de impressão
            
        Returns:
            bool: True se adicionado com sucesso
        """
        try:
            jobs = self.get_print_jobs()
            
            # Verifica se o trabalho já existe
            for i, job in enumerate(jobs):
                if job.get("job_id") == job_data.get("job_id"):
                    # Atualiza o trabalho existente
                    jobs[i] = job_data
                    self.set_print_jobs(jobs)
                    return True
            
            # Adiciona novo trabalho
            jobs.append(job_data)
            self.set_print_jobs(jobs)
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar trabalho de impressão: {str(e)}")
            return False
    
    def update_print_job(self, job_id, updates):
        """
        Atualiza um trabalho de impressão existente
        
        Args:
            job_id (str): ID do trabalho
            updates (dict): Atualizações a serem aplicadas
            
        Returns:
            bool: True se atualizado com sucesso
        """
        try:
            jobs = self.get_print_jobs()
            
            for i, job in enumerate(jobs):
                if job.get("job_id") == job_id:
                    # Atualiza apenas os campos fornecidos
                    for key, value in updates.items():
                        job[key] = value
                    
                    jobs[i] = job
                    self.set_print_jobs(jobs)
                    return True
            
            return False  # Trabalho não encontrado
        except Exception as e:
            logger.error(f"Erro ao atualizar trabalho de impressão: {str(e)}")
            return False
    
    def remove_print_job(self, job_id):
        """
        Remove um trabalho de impressão da lista
        
        Args:
            job_id (str): ID do trabalho
            
        Returns:
            bool: True se removido com sucesso
        """
        try:
            jobs = self.get_print_jobs()
            
            for i, job in enumerate(jobs):
                if job.get("job_id") == job_id:
                    # Remove o trabalho
                    job_data = jobs.pop(i)
                    
                    # Adiciona ao histórico se estiver completo ou falhou
                    status = job_data.get("status")
                    if status in ["completed", "failed", "canceled"]:
                        self.add_to_print_history(job_data)
                    
                    self.set_print_jobs(jobs)
                    return True
            
            return False  # Trabalho não encontrado
        except Exception as e:
            logger.error(f"Erro ao remover trabalho de impressão: {str(e)}")
            return False
    
    def get_print_history(self):
        """
        Obtém o histórico de trabalhos de impressão
        
        Returns:
            list: Histórico de trabalhos de impressão
        """
        return self.config.get("print_history", [])
    
    def set_print_history(self, history):
        """
        Define o histórico de trabalhos de impressão
        
        Args:
            history (list): Histórico de trabalhos de impressão
        """
        self.config["print_history"] = history
        self._save_config(self.config)
    
    def add_to_print_history(self, job_data):
        """
        Adiciona um trabalho ao histórico de impressão
        
        Args:
            job_data (dict): Dados do trabalho de impressão
            
        Returns:
            bool: True se adicionado com sucesso
        """
        try:
            history = self.get_print_history()
            
            # Verifica se o trabalho já existe no histórico
            for i, job in enumerate(history):
                if job.get("job_id") == job_data.get("job_id"):
                    # Atualiza o trabalho existente
                    history[i] = job_data
                    self.set_print_history(history)
                    return True
            
            # Adiciona novo trabalho ao histórico
            history.append(job_data)
            
            # Limita o tamanho do histórico (mantém os 100 mais recentes)
            if len(history) > 100:
                history = history[-100:]
                
            self.set_print_history(history)
            return True
        except Exception as e:
            logger.error(f"Erro ao adicionar trabalho ao histórico: {str(e)}")
            return False
    
    def clear_print_history(self):
        """
        Limpa o histórico de trabalhos de impressão
        
        Returns:
            bool: True se limpo com sucesso
        """
        try:
            self.set_print_history([])
            return True
        except Exception as e:
            logger.error(f"Erro ao limpar histórico de impressão: {str(e)}")
            return False
            
    def set_multi_user_mode(self, enabled):
        """
        Define se o modo multi-usuário está ativado
        
        Args:
            enabled (bool): True para ativar, False para desativar
        """
        self.set("multi_user_mode", enabled)
        
        # Se ativado, garante que os diretórios de usuários estejam configurados
        if enabled and self.system == 'Windows':
            self._ensure_user_directories()
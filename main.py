#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sistema de Gerenciamento de Impressão
Aplicação desktop para gerenciamento de impressões, compatível com Windows, Mac e Linux
"""

import os
import sys
import logging
import wx
import appdirs
import time
import platform
from src.ui.app import PrintManagementApp
from src.config import AppConfig

def setup_logging():
    """Configura o sistema de logs da aplicação"""
    log_dir = os.path.join(appdirs.user_data_dir("PrintManagementSystem", "LoQQuei"), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "app.log")
    
    # Remove handlers existentes para evitar duplicação
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Configura o logger com encoding UTF-8 explícito
    try:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formato mais detalhado
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # Configura o logger raiz
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        logger = logging.getLogger("PrintManagementSystem")
        
        # Teste inicial para verificar se o logging está funcionando
        logger.info(f"Sistema de logs configurado com sucesso")
        logger.info(f"Arquivo de log: {log_file}")
        logger.info(f"Diretório de logs existe: {os.path.exists(log_dir)}")
        logger.info(f"Arquivo de log existe: {os.path.exists(log_file)}")
        
        # Force flush para garantir que seja escrito
        file_handler.flush()
        
        return logger
        
    except Exception as e:
        print(f"ERRO ao configurar logging: {e}")
        # Fallback para logging básico
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger("PrintManagementSystem")

def setup_user_data_dir():
    """Configura o diretório de dados do usuário"""
    data_dir = appdirs.user_data_dir("PrintManagementSystem", "LoQQuei")
    os.makedirs(data_dir, exist_ok=True)
    
    # Cria subdiretórios necessários
    pdf_dir = os.path.join(data_dir, "pdfs")
    config_dir = os.path.join(data_dir, "config")
    temp_dir = os.path.join(data_dir, "temp")
    
    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)
    
    return data_dir

def setup_multi_user_directories():
    """
    Configura diretórios para múltiplos usuários em ambientes Windows Server
    """
    # Só executamos isso no Windows
    if platform.system() != 'Windows':
        return
    
    # Diretório Users
    users_dir = os.path.join(os.environ.get('SystemDrive', 'C:'), 'Users')
    
    # Verificar se estamos em um servidor
    is_server = 'server' in platform.release().lower() or 'server' in platform.version().lower()
    
    if os.path.exists(users_dir):
        logger = logging.getLogger("PrintManagementSystem")
        logger.info(f"Verificando diretórios de usuários em: {users_dir}")
        logger.info(f"Sistema operacional: {platform.system()} {platform.release()}")
        logger.info(f"Versão: {platform.version()}")
        logger.info(f"Detectado como servidor: {is_server}")
        
        # Lista todos os usuários
        for username in os.listdir(users_dir):
            user_profile = os.path.join(users_dir, username)
            
            # Verifica se é um diretório de usuário válido
            if os.path.isdir(user_profile) and not username.startswith('.'):
                # Localização padrão AppData para o usuário
                app_data = os.path.join(user_profile, 'AppData', 'Local')
                
                if os.path.exists(app_data):
                    user_pdf_dir = os.path.join(app_data, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                    
                    # Tenta criar o diretório do usuário
                    try:
                        os.makedirs(user_pdf_dir, exist_ok=True)
                        logger.info(f"Diretório criado para usuário {username}: {user_pdf_dir}")
                    except PermissionError:
                        logger.warning(f"Sem permissão para criar diretório para o usuário {username}")
                    except Exception as e:
                        logger.warning(f"Erro ao criar diretório para usuário {username}: {e}")

def main():
    """Função principal da aplicação"""
    try:
        logger = setup_logging()
        logger.info("Iniciando Sistema de Gerenciamento de Impressão")
        
        data_dir = setup_user_data_dir()
        logger.info(f"Diretório de dados configurado: {data_dir}")
        
        # Inicializa a configuração da aplicação
        config = AppConfig(data_dir)
        
        # Configura diretórios para múltiplos usuários (especialmente em servidores)
        if config.get("multi_user_mode", True):
            setup_multi_user_directories()
            
            # Garante que a configuração conheça os diretórios
            if hasattr(config, '_ensure_user_directories'):
                config._ensure_user_directories()
        
        # Cria e inicia a aplicação wxPython passando a configuração diretamente
        app = PrintManagementApp(config)
        
        # Loop personalizado para suportar execução em segundo plano
        app.MainLoop()
        
        logger.info("Aplicação encerrada")
        
    except Exception as e:
        if 'logger' in locals():
            logger.error(f"Erro fatal na aplicação: {str(e)}", exc_info=True)
        else:
            import traceback
            print(f"ERRO FATAL: {str(e)}")
            print(traceback.format_exc())
            
        # Tenta mostrar uma mensagem de erro via wxPython
        try:
            import wx
            if 'app' in locals() and isinstance(app, wx.App):
                wx.MessageBox(f"Erro fatal na aplicação: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
            else:
                app = wx.App(False)
                wx.MessageBox(f"Erro fatal na aplicação: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
        except:
            # Em último caso, mantém o terminal aberto
            input("Pressione ENTER para fechar...")

if __name__ == "__main__":
    main()
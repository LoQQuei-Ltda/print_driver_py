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
import threading
import time
import platform
from src.utils.subprocess_utils import run_hidden
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
    Configura diretórios para múltiplos usuários - VERSÃO OTIMIZADA
    """
    # Só executa no Windows
    if platform.system() != 'Windows':
        return
    
    try:
        # Verificação rápida se é realmente multi-usuário
        result = run_hidden(['query', 'user'], timeout=3)
        if result.returncode != 0:
            return  # Comando falhou, provavelmente não é servidor
        
        lines = result.stdout.strip().split('\n')
        active_sessions = [line for line in lines if 'Active' in line]
        if len(active_sessions) <= 1:
            return  # Apenas uma sessão ativa, não precisa configurar multi-usuário
            
    except:
        return  # Em caso de erro, pula a configuração
    
    logger = logging.getLogger("PrintManagementSystem")
    logger.info("Configurando para ambiente multi-usuário...")
    
    # Diretório Users
    users_dir = os.path.join(os.environ.get('SystemDrive', 'C:'), 'Users')
    
    if os.path.exists(users_dir):
        try:
            # Limita a 5 usuários para evitar demora
            users = [u for u in os.listdir(users_dir)[:5] if not u.startswith('.')]
            
            for username in users:
                user_profile = os.path.join(users_dir, username)
                
                if os.path.isdir(user_profile):
                    app_data = os.path.join(user_profile, 'AppData', 'Local')
                    
                    if os.path.exists(app_data):
                        user_pdf_dir = os.path.join(app_data, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                        
                        try:
                            os.makedirs(user_pdf_dir, exist_ok=True)
                        except:
                            pass  # Falha silenciosa para não interromper
                            
        except Exception as e:
            logger.warning(f"Erro na configuração multi-usuário: {e}")

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
            # EXECUTAR EM THREAD SEPARADA PARA NÃO ATRASAR INICIALIZAÇÃO
            setup_thread = threading.Thread(target=setup_multi_user_directories, daemon=True)
            setup_thread.start()
            
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
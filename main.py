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
from src.ui.app import PrintManagementApp
from src.config import AppConfig

def setup_logging():
    """Configura o sistema de logs da aplicação"""
    log_dir = os.path.join(appdirs.user_data_dir("PrintManagementSystem", "LoQQuei"), "logs")
    os.makedirs(log_dir, exist_ok=True)
    
    log_file = os.path.join(log_dir, "app.log")
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
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

def main():
    """Função principal da aplicação"""
    try:
        logger = setup_logging()
        logger.info("Iniciando Sistema de Gerenciamento de Impressão")
        
        data_dir = setup_user_data_dir()
        logger.info(f"Diretório de dados configurado: {data_dir}")
        
        # Inicializa a configuração da aplicação
        config = AppConfig(data_dir)
        
        # Cria e inicia a aplicação wxPython passando a configuração diretamente
        app = PrintManagementApp(config)
        
        # Inicializa a aplicação
        # app.OnInit()
        
        # Loop personalizado para suportar execução em segundo plano
        while app.keep_running_in_background():
            app.MainLoop()
            # Quando o MainLoop terminar, verificamos se devemos continuar em segundo plano
            time.sleep(0.1)  # Pequena pausa para não consumir CPU
            
            # Processa eventos de UI pendentes
            wx.Yield()
        
        logger.info("Aplicação encerrada")
        
    except Exception as e:
        logger.error(f"Erro fatal na aplicação: {str(e)}", exc_info=True)
        if 'app' in locals() and isinstance(app, wx.App):
            wx.MessageBox(f"Erro fatal na aplicação: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)

if __name__ == "__main__":
    main()
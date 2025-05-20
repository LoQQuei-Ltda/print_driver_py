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
"""Executa toda a aplicação"""
import os
import logging
import wx
import appdirs
from src.ui.app import PrintManagementApp
from src.config import AppConfig

def setup_logging():
    """Configura o sistema de logging para o aplicativo"""
    log_dir = os.path.join(appdirs.user_log_dir("PrintManager"), "logs")
    os.makedirs(log_dir, exist_ok=True)

    log_file = os.path.join(log_dir, "log_print_manager.log")

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("PrintManager")

def setup_user_data_dir():
    """Configura o diretório de dados do usuário"""
    user_data_dir = appdirs.user_data_dir("PrintManager", "Loqquei")
    os.makedirs(user_data_dir, exist_ok=True)

    pdf_dir = os.path.join(user_data_dir, "pdf")
    config_dir = os.path.join(user_data_dir, "config")
    temp_dir = os.path.join(user_data_dir, "temp")

    os.makedirs(pdf_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(temp_dir, exist_ok=True)

    return user_data_dir

def main():
    """Executa o aplicativo principal"""
    try:
        logger = setup_logging()
        logger.info("Iniciando aplicativo")

        data_dir = setup_user_data_dir()
        logger.info("Diretório de dados: %s", data_dir)

        config = AppConfig(data_dir)

        app = PrintManagementApp(0)
        app.config = config

        app.OnInit()

        app.MainLoop()

        logger.info("Aplicação encerrada")
    except Exception as e:
        logger.error(f"Erro fatal na execução: {str(e)}", exc_info=True)
        if 'app' in locals() and isinstance(app, wx.App):
            wx.MessageBox(f"Erro fatal na execução: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)


if __name__ == "__main__":
    main()

""" Executa toda a aplicação """
import os
import sys
import logging
from pathlib import Path

if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys._MEIPASS)
else:
    BASE_DIR = Path(__file__).resolve().parent

sys.path.insert(0, str(BASE_DIR))

from src.logger.utils.logger import setup_logger
from src.main.controllers.main import MainController

def main():
    """Função principal para iniciar a aplicação"""
    logger = setup_logger()
    logger.info("Iniciando aplicativo")

    try:
        app = MainController()
        app.start()
    except Exception as e:
        logger.error("Erro fatal na execução: %s", str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
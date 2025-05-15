import logging
import os
from pathlib import Path

def setup_logger():
    """Configura o sistema de logging para o aplicativo"""
    config_dir = Path.home() / ".loqquei" / "print_manager"
    logs_dir = config_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("PrintManager")

    if not logger.handlers:
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(logs_dir / "log_print_manager.log")
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(file_formatter)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        console_handler.setFormatter(console_formatter)

        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger

logger = setup_logger()

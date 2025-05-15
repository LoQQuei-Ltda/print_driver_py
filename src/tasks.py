#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tarefas agendadas da aplicação
"""

import logging
from src.models.printer import Printer

logger = logging.getLogger("PrintManagementSystem.Tasks")

def update_printers_task(api_client, config):
    """
    Tarefa para atualizar impressoras com o servidor principal
    
    Args:
        api_client: Cliente da API
        config: Configuração da aplicação
    """
    try:
        logger.info("Executando tarefa de atualização de impressoras")
        
        # Obtém as impressoras da API
        printers_data = api_client.get_printers()
        
        # Converte para objetos Printer, sanitiza os dados e converte para dicionários
        printers = []
        for printer_data in printers_data:
            printer = Printer(printer_data)
            
            # Sanitiza os dados antes de converter para dicionário
            # Garante que valores não sejam None
            if printer.name is None:
                printer.name = "Sem nome"
            if printer.mac_address is None:
                printer.mac_address = ""
                
            # Outros campos que podem ser None em to_dict
            printer_dict = printer.to_dict()
            for key in printer_dict:
                if printer_dict[key] is None:
                    printer_dict[key] = ""
            
            printers.append(printer_dict)
        
        # Salva as impressoras no config
        config.set_printers(printers)
        
        logger.info(f"{len(printers)} impressoras atualizadas com sucesso")
        
    except Exception as e:
        logger.error(f"Erro ao atualizar impressoras: {str(e)}")
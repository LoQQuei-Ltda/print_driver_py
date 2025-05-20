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
    Tarefa para atualizar impressoras com o servidor e descobrir detalhes adicionais
    
    Args:
        api_client: Cliente da API
        config: Configuração da aplicação
    """
    try:
        logger.info("Executando tarefa de atualização de impressoras")
        
        # Obtém as impressoras do API com descoberta integrada
        printers_data = []
        
        try:
            # Primeiro tenta o método com descoberta
            if hasattr(api_client, 'get_printers_with_discovery'):
                printers_data = api_client.get_printers_with_discovery()
            else:
                # Fallback para o método padrão
                printers_data = api_client.get_printers()
                
                # Tenta obter informações adicionais se não houver método de descoberta integrado
                from src.utils.printer_discovery import PrinterDiscovery
                discovery = PrinterDiscovery()
                
                # Cria dicionário de impressoras pelo MAC
                printers_by_mac = {}
                for printer in printers_data:
                    mac = printer.get("mac_address", "").lower()
                    if mac:
                        printers_by_mac[mac] = printer
                
                # Descobre impressoras
                discovered = discovery.discover_printers()
                
                # Atualiza impressoras com dados descobertos
                for disc in discovered:
                    mac = disc.get("mac_address", "").lower()
                    if mac and mac in printers_by_mac:
                        printers_by_mac[mac].update({
                            "ip": disc.get("ip", ""),
                            "uri": disc.get("uri", ""),
                            "is_online": True
                        })
                        
                        # Obtém detalhes
                        ip = disc.get("ip")
                        if ip:
                            details = discovery.get_printer_details(ip)
                            if details:
                                printers_by_mac[mac].update({
                                    "model": details.get("printer-make-and-model", ""),
                                    "location": details.get("printer-location", ""),
                                    "state": details.get("printer-state", ""),
                                    "is_ready": "Idle" in details.get("printer-state", ""),
                                    "attributes": details
                                })
                
        except Exception as e:
            logger.error(f"Erro ao obter impressoras: {str(e)}")
            return
        
        # Converte para objetos Printer e sanitiza os dados
        printers = []
        for printer_data in printers_data:
            printer = Printer(printer_data)
            
            # Sanitiza os dados antes de converter para dicionário
            # Garante que valores não sejam None
            if printer.name is None:
                printer.name = "Sem nome"
            if printer.mac_address is None:
                printer.mac_address = ""
            if printer.ip is None:
                printer.ip = ""
            if printer.uri is None:
                printer.uri = ""
                
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

def update_application_task(api_client, config):
    """
    Tarefa para verificar e aplicar atualizações da aplicação
    
    Args:
        api_client: Cliente da API
        config: Configuração da aplicação
    """
    try:
        logger.info("Executando tarefa de verificação de atualizações")
        
        # Verifica se é o momento certo (minuto 0 da hora)
        from datetime import datetime
        now = datetime.now()
        if now.minute != 0:
            logger.debug("Não é o momento para verificar atualizações (minuto != 0)")
            return
        
        # Importa o módulo de atualização
        from src.utils.updater import AppUpdater
        
        # Cria o atualizador e verifica atualizações
        updater = AppUpdater(config, api_client)
        updater.check_and_update(silent=True)
        
    except Exception as e:
        logger.error(f"Erro ao verificar atualizações: {str(e)}")

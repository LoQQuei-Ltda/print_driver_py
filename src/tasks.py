#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tarefas agendadas da aplicação
"""

import asyncio
import logging
from src.models.printer import Printer

logger = logging.getLogger("PrintManagementSystem.Tasks")

HAS_PYSNMP = False
try:
    from pysnmp.hlapi.v3arch.asyncio import *
    from pysnmp.smi.rfc1902 import ObjectIdentity, ObjectType
    HAS_PYSNMP = True
except ImportError:
    logger.error("Biblioteca pysnmp não disponível. Instale com: pip install pysnmp")

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
            logger.info("Não é o momento para verificar atualizações (minuto != 0)")
            return
        
        # Importa o módulo de atualização
        from src.utils.updater import AppUpdater
        
        # Cria o atualizador e verifica atualizações
        updater = AppUpdater(config, api_client)
        updater.check_and_update(silent=True)
        
    except Exception as e:
        logger.error(f"Erro ao verificar atualizações: {str(e)}")

def collect_printer_pages_task(api_client, config):
    """
    Tarefa para coletar páginas impressas de todas as impressoras via SNMP
    e enviar para o servidor.
    
    Args:
        api_client: Cliente da API
        config: Configuração da aplicação
    """
    try:
        from datetime import datetime
        now = datetime.now()
        
        logger.info(f"Iniciando coleta de páginas impressas via SNMP (minuto: {now.minute})")
        
        # Obtém a lista de impressoras da configuração
        printers = config.get_printers()
        
        if not printers:
            logger.info("Nenhuma impressora configurada para coleta de páginas")
            return
        
        # Verifica se pysnmp está disponível
        if not HAS_PYSNMP:
            logger.error("Biblioteca pysnmp não disponível.")
            return
        
        # Coleta páginas de cada impressora
        collected_count = 0
        error_count = 0
        
        for printer in printers:
            try:
                printer_name = printer.get('name', 'Desconhecida')
                printer_ip = printer.get('ip')
                asset_id = printer.get('id')  # ID da impressora na API
                
                # Validações básicas
                if not printer_ip:
                    logger.info(f"Impressora '{printer_name}' sem IP configurado, pulando...")
                    continue
                
                if not asset_id:
                    logger.warning(f"Impressora '{printer_name}' sem ID da API (asset_id), pulando...")
                    continue
                
                logger.info(f"Coletando páginas da impressora '{printer_name}' ({printer_ip})...")
                
                # Tenta obter contagem de páginas via SNMP
                pages_count = asyncio.run(_query_printer_pages_snmp(printer_ip, printer_name))
                
                print("pages_count", pages_count)
                # Se obteve a contagem, envia para a API
                if pages_count is not None and pages_count >= 0:
                    try:
                        success = api_client.send_printer_pages(asset_id, pages_count)
                        
                        if success:
                            collected_count += 1
                            logger.info(f"✓ Páginas da impressora '{printer_name}' enviadas com sucesso: {pages_count}")
                        else:
                            error_count += 1
                            logger.error(f"✗ Falha ao enviar páginas da impressora '{printer_name}' para a API")
                    except Exception as api_error:
                        error_count += 1
                        logger.error(f"✗ Erro ao chamar API para impressora '{printer_name}': {str(api_error)}")
                else:
                    error_count += 1
                    logger.warning(f"✗ Não foi possível obter contagem de páginas da impressora '{printer_name}'")
                
            except Exception as e:
                error_count += 1
                logger.error(f"✗ Erro ao processar impressora '{printer.get('name', 'desconhecida')}': {str(e)}")
        
        # Log resumo da coleta
        total_printers = len([p for p in printers if p.get('ip') and p.get('id')])
        logger.info(f"Coleta de páginas concluída: {collected_count} sucessos, {error_count} erros "
                   f"de {total_printers} impressoras válidas")
        
    except Exception as e:
        logger.error(f"Erro geral na tarefa de coleta de páginas: {str(e)}")


async def _query_printer_pages_snmp(printer_ip, printer_name):
    """
    Consulta páginas impressas via SNMP de uma impressora específica (versão assíncrona)
    """
    if not HAS_PYSNMP:
        logger.error("pysnmp não disponível")
        return None
    
    try:
        # Configurações simples baseadas no código de teste
        community_string = 'public'
        oid = '1.3.6.1.2.1.43.10.2.1.4.1.1'  # Total de páginas impressas
        
        logger.info(f"Consultando SNMP para {printer_name} ({printer_ip})")
        
        # Realiza a consulta SNMP (versão assíncrona com await)
        errorIndication, errorStatus, errorIndex, varBinds = await get_cmd(
            SnmpEngine(),
            CommunityData(community_string),
            await UdpTransportTarget.create((printer_ip, 161)),
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lookupMib=False,
            lexicographicMode=False,
        )
        
        # Resto do código igual...
        if errorIndication:
            logger.info(f"Erro de indicação SNMP para {printer_name}: {errorIndication}")
            return None
        
        if errorStatus:
            logger.info(f"Erro de status SNMP para {printer_name}: {errorStatus.prettyPrint()}")
            return None
        
        if varBinds:
            for varBind in varBinds:
                oid_result, value = varBind
                logger.info(f"Valor SNMP bruto recebido de {printer_name}: {value}")
                
                pages_count = _parse_snmp_value(value, printer_name)
                
                if pages_count is not None and pages_count >= 0:
                    logger.info(f"✓ SNMP sucesso para {printer_name}: {pages_count} páginas")
                    return pages_count
        
        logger.warning(f"Nenhum valor válido obtido via SNMP para {printer_name}")
        return None
        
    except Exception as e:
        logger.error(f"Erro na consulta SNMP para {printer_name}: {str(e)}")
        return None

def _parse_snmp_value(value, printer_name):
    """
    Tenta converter valor SNMP para inteiro
    
    Args:
        value: Valor recebido do SNMP
        printer_name (str): Nome da impressora para logs
        
    Returns:
        int or None: Valor convertido ou None se falhar
    """
    try:
        # Diferentes formas de obter o valor
        value_str = None
        
        if hasattr(value, 'prettyPrint'):
            value_str = value.prettyPrint()
        elif hasattr(value, 'getValue'):
            value_str = str(value.getValue())
        elif hasattr(value, '__int__'):
            return int(value)
        else:
            value_str = str(value)
        
        # Remove espaços e caracteres especiais
        value_str = value_str.strip()
        
        # Tenta converter diretamente
        try:
            pages_count = int(value_str)
            if pages_count >= 0:
                return pages_count
        except ValueError:
            pass
        
        # Tenta extrair números da string (caso tenha formato especial)
        import re
        numbers = re.findall(r'\d+', value_str)
        if numbers:
            pages_count = int(numbers[0])  # Pega o primeiro número encontrado
            if pages_count >= 0:
                logger.info(f"Valor extraído de '{value_str}': {pages_count}")
                return pages_count
        
        logger.info(f"Não foi possível converter valor SNMP '{value_str}' para {printer_name}")
        return None
        
    except Exception as e:
        logger.error(f"Erro ao converter valor SNMP para {printer_name}: {str(e)}")
        return None

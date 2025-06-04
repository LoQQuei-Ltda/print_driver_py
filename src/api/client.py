#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente para comunicação com a API - Versão Corrigida
"""

import json
import logging
import requests
from requests.exceptions import RequestException
import time
import traceback

logger = logging.getLogger("PrintManagementSystem.API.Client")

class APIClient:
    """Cliente para comunicação com a API do sistema"""
    
    def __init__(self, base_url, timeout=10):
        """
        Inicializa o cliente da API
        
        Args:
            base_url (str): URL base da API
            timeout (int): Tempo limite para requisições em segundos
        """
        self.base_url = base_url
        self.timeout = timeout
        self.token = None
    
    def set_token(self, token):
        """
        Define o token de autenticação
        
        Args:
            token (str): Token de autenticação
        """
        self.token = token
    
    def _get_headers(self):
        """
        Obtém os cabeçalhos para requisições
        
        Returns:
            dict: Cabeçalhos HTTP
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        
        return headers
    
    def _make_request(self, method, endpoint, data=None, params=None):
        """
        Realiza uma requisição HTTP para a API
        
        Args:
            method (str): Método HTTP (GET, POST, PUT, DELETE)
            endpoint (str): Endpoint da API
            data (dict, optional): Dados para enviar no corpo da requisição
            params (dict, optional): Parâmetros de consulta
            
        Returns:
            dict: Resposta da API
            
        Raises:
            APIError: Erro na comunicação com a API
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()
        
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            elif method == "PUT":
                response = requests.put(url, headers=headers, json=data, timeout=self.timeout)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, timeout=self.timeout)
            else:
                raise ValueError(f"Método HTTP não suportado: {method}")
            
            response.raise_for_status()
            
            # Verifica se a resposta contém dados
            if response.content:
                try:
                    # Tenta obter o JSON da resposta
                    response_data = response.json()
                    
                    # Se a resposta contém um campo "data", retorna apenas esse campo
                    if "data" in response_data:
                        return response_data["data"]
                    
                    # Caso contrário, retorna o objeto completo
                    return response_data
                except ValueError:
                    # Se não for um JSON válido, retorna o conteúdo em texto
                    return {"message": response.text}
            else:
                # Resposta vazia
                return {}
            
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Erro de conexão na requisição API {method} {url}: {str(e)}")
            raise APIError("Não foi possível conectar ao servidor. Verifique sua conexão com a internet.", 0)
            
        except requests.exceptions.Timeout as e:
            logger.error(f"Tempo limite excedido na requisição API {method} {url}: {str(e)}")
            raise APIError("Tempo limite de conexão excedido. O servidor está demorando para responder.", 408)
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição API {method} {url}: {str(e)}")
            
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                except ValueError:
                    error_message = e.response.text or str(e)
                
                # Mensagens de erro mais amigáveis para códigos de status comuns
                if status_code == 401:
                    error_message = "Não autorizado. Verifique suas credenciais ou faça login novamente."
                elif status_code == 403:
                    error_message = "Acesso negado. Você não tem permissão para acessar este recurso."
                elif status_code == 404:
                    error_message = f"Recurso não encontrado: {endpoint}"
                elif status_code == 500:
                    error_message = "Erro interno do servidor. Tente novamente mais tarde."
            else:
                status_code = 0
                error_message = str(e)
            
            raise APIError(error_message, status_code)
    
    def login(self, email, password):
        """
        Realiza login na API
        
        Args:
            email (str): Email do usuário
            password (str): Senha do usuário
            
        Returns:
            dict: Dados do usuário e token
        """
        data = {
            "email": email,
            "password": password
        }
        
        try:
            response = self._make_request("POST", "/login/desktop", data)
            
            if "token" in response:
                self.set_token(response["token"])

            return response
        except APIError as e:
            if e.status_code == 401:
                raise APIError("Email ou senha inválidos", 401)
            raise
    
    def validate_user(self):
        """
        Verifica se o usuário atual está autenticado
        
        Returns:
            dict: Resultado da validação com campos:
                - is_valid (bool): True se o usuário está autenticado
                - should_logout (bool): True se deve fazer logout (apenas para erro 401)
                - error_code (int): Código de erro se houver
                - error_message (str): Mensagem de erro se houver
        """
        try:
            # Chama o endpoint /desktop/validUser
            self._make_request("GET", "/desktop/validUser")
            return {
                "is_valid": True,
                "should_logout": False,
                "error_code": None,
                "error_message": None
            }
        except APIError as e:
            logger.warning(f"Erro ao validar usuário: {str(e)} (Status: {e.status_code})")
            
            # Apenas força logout se receber erro 401 (não autorizado)
            should_logout = e.status_code == 401
            
            return {
                "is_valid": False,
                "should_logout": should_logout,
                "error_code": e.status_code,
                "error_message": str(e)
            }
        except Exception as e:
            logger.warning(f"Erro inesperado ao validar usuário: {str(e)}")
            
            # Para outros erros (conexão, timeout, etc.), não força logout
            return {
                "is_valid": False,
                "should_logout": False,
                "error_code": 0,
                "error_message": str(e)
            }

    def get_printers(self):
        """
        Obtém lista de impressoras disponíveis
        
        Returns:
            list: Lista de impressoras com nome e mac_address
        """
        try:
            result = self._make_request("GET", "/desktop/printers")
            
            # Verifica se o resultado é uma lista
            if isinstance(result, list):
                logger.info(f"Servidor retornou {len(result)} impressoras")
                return result
            # Se não for uma lista, retorna uma lista vazia
            logger.warning("Servidor não retornou lista de impressoras")
            return []
        except APIError as e:
            # Se recebermos um erro 404, retornamos uma lista vazia
            if e.status_code == 404:
                logger.warning("Endpoint de impressoras não encontrado. Retornando lista vazia.")
                return []
            # Propaga outros erros
            raise
    
    def get_printers_with_discovery(self):
        """
        Obtém lista de impressoras e enriquece com descoberta automática
        Versão melhorada com melhor tratamento de erros e fallbacks
        
        Returns:
            list: Lista de impressoras com informações completas
        """
        logger.info("Iniciando obtenção de impressoras com descoberta automática")
        
        # Primeiro obtém impressoras do servidor
        server_printers = []
        try:
            result = self._make_request("GET", "/desktop/printers")
            
            if isinstance(result, list):
                server_printers = result
                logger.info(f"Servidor retornou {len(server_printers)} impressoras")
            else:
                logger.warning("Servidor não retornou lista válida de impressoras")
        except APIError as e:
            if e.status_code == 404:
                logger.warning("Endpoint de impressoras não encontrado no servidor")
            else:
                logger.warning(f"Erro ao obter impressoras do servidor: {str(e)}")
        except Exception as e:
            logger.warning(f"Erro inesperado ao acessar servidor: {str(e)}")
        
        # Se não conseguiu impressoras do servidor, tenta descoberta local
        if not server_printers:
            logger.info("Nenhuma impressora do servidor, tentando descoberta local completa")
            try:
                from src.utils.printer_discovery import PrinterDiscovery
                
                discovery = PrinterDiscovery()
                discovered_printers = discovery.discover_printers()
                
                if discovered_printers:
                    logger.info(f"Descoberta local encontrou {len(discovered_printers)} impressoras")
                    return self._format_discovered_printers(discovered_printers)
                else:
                    logger.warning("Descoberta local não encontrou impressoras")
                    return []
                    
            except ImportError as e:
                logger.error(f"Módulo de descoberta não disponível: {str(e)}")
                return []
            except Exception as e:
                logger.error(f"Erro na descoberta local: {str(e)}")
                logger.error(traceback.format_exc())
                return []
        
        # Enriquece impressoras do servidor com dados de descoberta
        return self._enrich_server_printers(server_printers)
    
    def _enrich_server_printers(self, server_printers):
        """
        Enriquece impressoras do servidor com dados de descoberta
        
        Args:
            server_printers: Lista de impressoras do servidor
            
        Returns:
            list: Lista de impressoras enriquecidas
        """
        logger.info(f"Enriquecendo {len(server_printers)} impressoras do servidor")
        
        try:
            from src.utils.printer_discovery import PrinterDiscovery
        except ImportError as e:
            logger.error(f"Módulo de descoberta não disponível: {str(e)}")
            return server_printers
        
        try:
            discovery = PrinterDiscovery()
            enriched_printers = []
            
            for printer in server_printers:
                try:
                    enriched_printer = self._enrich_single_printer(printer, discovery)
                    enriched_printers.append(enriched_printer)
                except Exception as e:
                    logger.warning(f"Erro ao enriquecer impressora {printer.get('name', 'desconhecida')}: {str(e)}")
                    # Adiciona a impressora original se falhar
                    enriched_printers.append(printer)
            
            logger.info(f"Enriquecimento concluído: {len(enriched_printers)} impressoras processadas")
            return enriched_printers
            
        except Exception as e:
            logger.error(f"Erro geral no enriquecimento: {str(e)}")
            logger.error(traceback.format_exc())
            return server_printers
    
    def _enrich_single_printer(self, printer, discovery):
        """
        Enriquece uma única impressora com dados de descoberta
        
        Args:
            printer: Dados da impressora do servidor
            discovery: Instância do PrinterDiscovery
            
        Returns:
            dict: Impressora enriquecida
        """
        # Faz uma cópia para não modificar o original
        enriched = printer.copy()
        
        # Normaliza campos
        mac = enriched.get("macAddress") or enriched.get("mac_address", "")
        if not mac:
            logger.warning(f"Impressora '{enriched.get('name', 'sem nome')}' sem MAC address")
            return enriched
        
        # Normaliza o MAC
        normalized_mac = discovery.normalize_mac(mac)
        if not normalized_mac:
            logger.warning(f"MAC inválido para impressora '{enriched.get('name', 'sem nome')}': {mac}")
            return enriched
        
        # Padroniza o campo MAC
        enriched["macAddress"] = normalized_mac
        enriched["mac_address"] = normalized_mac
        
        try:
            # Tenta descobrir o IP para este MAC
            logger.info(f"Buscando IP para MAC {normalized_mac}...")
            
            discovered_info = discovery.discover_printer_by_mac(normalized_mac)
            
            if discovered_info:
                # Atualiza com dados descobertos
                enriched.update({
                    "ip": discovered_info.get("ip", ""),
                    "uri": discovered_info.get("uri", ""),
                    "is_online": True,
                    "ports": discovered_info.get("ports", [])
                })
                
                logger.info(f"IP encontrado para {normalized_mac}: {discovered_info.get('ip')}")
                
                # Se tem IP e porta IPP, tenta obter detalhes
                ip = discovered_info.get("ip")
                if ip and 631 in discovered_info.get("ports", []):
                    try:
                        logger.info(f"Obtendo detalhes IPP para {ip}...")
                        details = discovery.get_printer_details(ip)
                        
                        if details and isinstance(details, dict):
                            # Atualiza com detalhes IPP
                            enriched.update({
                                "model": details.get("printer-make-and-model", ""),
                                "location": details.get("printer-location", ""),
                                "state": details.get("printer-state", ""),
                                "is_ready": "Idle" in details.get("printer-state", ""),
                                "attributes": details
                            })
                            
                            logger.info(f"Detalhes IPP obtidos para {ip}: {details.get('printer-make-and-model', 'modelo desconhecido')}")
                        else:
                            logger.warning(f"Detalhes IPP inválidos para {ip}")
                            
                    except Exception as e:
                        logger.warning(f"Erro ao obter detalhes IPP para {ip}: {str(e)}")
                        
            else:
                logger.warning(f"Não foi possível encontrar IP para MAC {normalized_mac}")
                # Marca como offline se não encontrou
                enriched.update({
                    "ip": "",
                    "is_online": False
                })
                
        except Exception as e:
            logger.error(f"Erro ao descobrir informações para MAC {normalized_mac}: {str(e)}")
            enriched.update({
                "ip": "",
                "is_online": False
            })
        
        return enriched
    
    def _format_discovered_printers(self, discovered_printers):
        """
        Formata impressoras descobertas localmente para o formato esperado
        
        Args:
            discovered_printers: Lista de impressoras descobertas
            
        Returns:
            list: Lista formatada
        """
        formatted_printers = []
        
        for printer in discovered_printers:
            try:
                formatted = {
                    "name": printer.get("name", f"Impressora {printer.get('ip', 'desconhecida')}"),
                    "macAddress": printer.get("mac_address", "desconhecido"),
                    "mac_address": printer.get("mac_address", "desconhecido"),
                    "ip": printer.get("ip", ""),
                    "uri": printer.get("uri", ""),
                    "is_online": printer.get("is_online", True),
                    "ports": printer.get("ports", []),
                    "model": printer.get("model", ""),
                    "location": printer.get("location", ""),
                    "state": printer.get("state", ""),
                    "is_ready": printer.get("is_ready", False),
                    "attributes": printer.get("attributes", {})
                }
                
                formatted_printers.append(formatted)
                
            except Exception as e:
                logger.warning(f"Erro ao formatar impressora descoberta: {str(e)}")
        
        return formatted_printers
        
    def sync_print_job(self, date, file_id, asset_id, pages):
        """
        Sincroniza um trabalho de impressão com o servidor
        
        Args:
            date (str): Data da impressão (formato ISO)
            file_id (str): ID do arquivo/trabalho
            asset_id (str): ID do asset (impressora)
            pages (int): Número de páginas impressas
            
        Returns:
            bool: True se sincronizado com sucesso, False caso contrário
        """
        try:
            data = {
                "date": date,
                "fileId": file_id,
                "assetId": asset_id,
                "pages": pages
            }
            
            logger.info(f"Enviando dados para sincronização: {data}")
            result = self._make_request("POST", "/desktop/printedByUser", data)
            logger.info(f"Trabalho de impressão sincronizado com sucesso: {file_id}")
            logger.info(f"Resposta da API: {result}")
            return True
        except APIError as e:
            logger.error(f"Erro ao sincronizar trabalho de impressão {file_id}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Erro inesperado ao sincronizar trabalho {file_id}: {str(e)}")
            return False

    
class APIError(Exception):
    """Exceção para erros na API"""
    
    def __init__(self, message, status_code=0):
        """
        Inicializa a exceção
        
        Args:
            message (str): Mensagem de erro
            status_code (int): Código de status HTTP
        """
        self.status_code = status_code
        super().__init__(message)
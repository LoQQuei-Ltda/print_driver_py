#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Cliente para comunicação com a API
"""

import json
import logging
import requests
from requests.exceptions import RequestException

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
                print(result)
                return result
            # Se não for uma lista, retorna uma lista vazia
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
        
        Returns:
            list: Lista de impressoras com informações completas
        """
        try:
            # Primeiro obtém impressoras do servidor
            printers = []
            result = self._make_request("GET", "/desktop/printers")
            
            # Verifica se o resultado é uma lista
            if isinstance(result, list):
                printers = result
            
            # Se não conseguir impressoras do servidor, retorna lista vazia
            if not printers:
                logger.warning("Nenhuma impressora retornada pelo servidor")
                return []
                
            # Cria um dicionário com as impressoras pelo MAC address
            printers_by_mac = {}
            for printer in printers:
                mac = printer.get("macAddress", "")
                if mac:
                    mac = mac.lower()
                    printers_by_mac[mac] = printer
            
            # Executa a descoberta automática
            try:
                from src.utils.printer_discovery import PrinterDiscovery
                
                discovery = PrinterDiscovery()
                discovered_printers = discovery.discover_printers()
                
                # Para cada impressora descoberta
                for discovered in discovered_printers:
                    mac = discovered.get("macAddress", "")
                    
                    # Se não tem MAC ou é desconhecido, pula
                    if not mac or mac == "desconhecido":
                        continue

                    mac = mac.lower()
                    
                    # Verifica se existe uma impressora com este MAC
                    if mac in printers_by_mac:
                        # Atualiza a impressora existente com os dados descobertos
                        printers_by_mac[mac].update({
                            "ip": discovered.get("ip", ""),
                            "uri": discovered.get("uri", ""),
                            "is_online": True
                        })
                        
                        # Obtém detalhes adicionais (estado, modelo, etc.)
                        ip = discovered.get("ip")
                        if ip:
                            try:
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
                                logger.warning(f"Erro ao obter detalhes da impressora {ip}: {str(e)}")
                
                logger.info(f"Enriquecidas {len(printers_by_mac)} impressoras com dados de descoberta")
                
            except Exception as e:
                logger.warning(f"Erro na descoberta automática: {str(e)}")
            
            return printers
            
        except APIError as e:
            # Se recebermos um erro 404, retornamos uma lista vazia
            if e.status_code == 404:
                logger.warning("Endpoint de impressoras não encontrado. Retornando lista vazia.")
                return []
            # Propaga outros erros
            raise
        
    def sync_print_job(self, date, file_id, asset_id, pages):
        """
        Sincroniza um trabalho de impressão com o servidor
        
        Args:
            date (str): Data da impressão (formato ISO)
            file_id (str): ID do arquivo/trabalho
            asset_id (str): ID do asset (documento)
            pages (int): Número de páginas impressas
            
        Returns:
            dict: Resposta do servidor
        """
        try:
            data = {
                "date": date,
                "fileId": file_id,
                "assetId": asset_id,
                "pages": pages
            }
            
            result = self._make_request("POST", "/desktop/printedByUser", data)
            logger.info(f"Trabalho de impressão sincronizado: {file_id}")
            return result
        except APIError as e:
            logger.error(f"Erro ao sincronizar trabalho de impressão: {str(e)}")
            raise
    
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
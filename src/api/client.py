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
            
            return response.json() if response.content else {}
            
        except RequestException as e:
            logger.error(f"Erro na requisição API {method} {url}: {str(e)}")
            
            if hasattr(e, 'response') and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                except ValueError:
                    error_message = e.response.text or str(e)
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
                self.set_token(response["data"]["token"])
            return response["data"]
        except APIError as e:
            if e.status_code == 401:
                raise APIError("Email ou senha inválidos", 401)
            raise
    
    def get_printers(self):
        """
        Obtém lista de impressoras disponíveis
        
        Returns:
            list: Lista de impressoras com nome e mac_address
        """
        return self._make_request("GET", "/printers")
    
    def get_user_documents(self):
        """
        Obtém lista de documentos do usuário
        
        Returns:
            list: Lista de documentos com nome, path, tamanho e data
        """
        return self._make_request("GET", "/documents")
    
    def delete_document(self, document_id):
        """
        Exclui um documento
        
        Args:
            document_id (str): ID do documento
        """
        return self._make_request("DELETE", f"/documents/{document_id}")
    
    def print_document(self, document_id, printer_id):
        """
        Envia um documento para impressão
        
        Args:
            document_id (str): ID do documento
            printer_id (str): ID da impressora
        """
        data = {
            "printer_id": printer_id
        }
        
        return self._make_request("POST", f"/documents/{document_id}/print", data)


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
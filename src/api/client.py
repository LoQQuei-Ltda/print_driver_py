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
    
    def get_user_documents(self):
        """
        Obtém lista de documentos do usuário
        
        Returns:
            list: Lista de documentos com nome, path, tamanho e data
        """
        try:
            result = self._make_request("GET", "/documents")
            
            # Verifica se o resultado é uma lista
            if isinstance(result, list):
                return result
            # Se não for uma lista, retorna uma lista vazia
            return []
        except APIError as e:
            # Se recebermos um erro 404, retornamos uma lista vazia
            if e.status_code == 404:
                logger.warning("Endpoint de documentos não encontrado. Retornando lista vazia.")
                return []
            # Propaga outros erros
            raise
    
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
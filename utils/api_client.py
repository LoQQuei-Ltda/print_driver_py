import os
import json
import logging
import time
from typing import Dict, List, Any, Optional
import requests

logger = logging.getLogger("VirtualPrinter.APIClient")

class APIClient:
    """Cliente para comunicação com APIs externas"""
    
    def __init__(self, base_url=None, api_key=None):
        """
        Inicializa o cliente de API
        """
        self.base_url = base_url or "https://api.loqquei.com.br/api/v1"
        self.api_key = api_key
        self.timeout = 10  # segundos
        self.session = requests.Session()
        
        # Configurar headers padrão
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        if self.api_key:
            self.headers["Authorization"] = f"Bearer {self.api_key}"
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        """
        Realiza uma requisição GET
        
        Args:
            endpoint: Endpoint da API
            params: Parâmetros da requisição
            
        Returns:
            Dict: Resposta da API em formato JSON
        """
        url = self._build_url(endpoint)
        try:
            response = self.session.get(
                url,
                params=params,
                headers=self.headers,
                timeout=self.timeout
            )
            return self._process_response(response)
        except requests.RequestException as e:
            logger.error(f"Erro na requisição GET para {url}: {e}")
            return self._error_response(str(e))
    
    def post(self, endpoint: str, data: Dict) -> Dict:
        """
        Realiza uma requisição POST
        
        Args:
            endpoint: Endpoint da API
            data: Dados para envio
            
        Returns:
            Dict: Resposta da API em formato JSON
        """
        url = self._build_url(endpoint)
        try:
            response = self.session.post(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            return self._process_response(response)
        except requests.RequestException as e:
            logger.error(f"Erro na requisição POST para {url}: {e}")
            return self._error_response(str(e))
    
    def put(self, endpoint: str, data: Dict) -> Dict:
        """
        Realiza uma requisição PUT
        
        Args:
            endpoint: Endpoint da API
            data: Dados para envio
            
        Returns:
            Dict: Resposta da API em formato JSON
        """
        url = self._build_url(endpoint)
        try:
            response = self.session.put(
                url,
                json=data,
                headers=self.headers,
                timeout=self.timeout
            )
            return self._process_response(response)
        except requests.RequestException as e:
            logger.error(f"Erro na requisição PUT para {url}: {e}")
            return self._error_response(str(e))
    
    def delete(self, endpoint: str) -> Dict:
        """
        Realiza uma requisição DELETE
        
        Args:
            endpoint: Endpoint da API
            
        Returns:
            Dict: Resposta da API em formato JSON
        """
        url = self._build_url(endpoint)
        try:
            response = self.session.delete(
                url,
                headers=self.headers,
                timeout=self.timeout
            )
            return self._process_response(response)
        except requests.RequestException as e:
            logger.error(f"Erro na requisição DELETE para {url}: {e}")
            return self._error_response(str(e))
    
    def _build_url(self, endpoint: str) -> str:
        """Constrói a URL completa para o endpoint"""
        if endpoint.startswith("http"):
            return endpoint
        
        # Garantir que não haja barras duplicadas
        if endpoint.startswith("/"):
            endpoint = endpoint[1:]
        
        return f"{self.base_url}/{endpoint}"
    
    def _process_response(self, response: requests.Response) -> Dict:
        """
        Processa a resposta da API
        
        Args:
            response: Objeto de resposta da requisição
            
        Returns:
            Dict: Dados da resposta em formato JSON
        """
        try:
            response.raise_for_status()
            return {
                "status": "success",
                "status_code": response.status_code,
                "data": response.json()
            }
        except requests.HTTPError as e:
            logger.error(f"Erro HTTP: {e}")
            error_data = {}
            try:
                error_data = response.json()
            except:
                error_data = {"message": response.text}
            
            return {
                "status": "error",
                "status_code": response.status_code,
                "error": error_data
            }
        except json.JSONDecodeError:
            logger.error(f"Erro ao decodificar resposta JSON: {response.text}")
            return {
                "status": "error",
                "status_code": response.status_code,
                "error": {"message": "Erro ao decodificar resposta JSON"}
            }
    
    def _error_response(self, message: str) -> Dict:
        """Cria uma resposta de erro padrão"""
        return {
            "status": "error",
            "status_code": 0,
            "error": {"message": message}
        }
    
    # Métodos específicos para autenticação
    
    def login(self, username, password):
        """
        Realiza login na API
        """

        

        # Em um cenário real, isso faria uma requisição para a API
        # Para o mockup, retornamos dados simulados
        
        # Simular uma pequena latência
        time.sleep(0.5)
        
        # Dados de autenticação simulados
        mock_auth = {
            'admin': {'password': 'admin123', 'role': 'admin'},
            'usuario': {'password': 'senha123', 'role': 'user'},
            'teste': {'password': 'teste123', 'role': 'user'}
        }
        
        if username in mock_auth and mock_auth[username]['password'] == password:
            # Autenticação bem-sucedida
            user_data = {
                'username': username,
                'email': f"{username}@example.com",
                'id': f"user_{username}",
                'role': mock_auth[username]['role']
            }
            
            token = f"mock_token_{username}_123456789"
            
            # Armazenar token para futuras requisições
            self.headers["Authorization"] = f"Bearer {token}"
            
            return {
                'status': 'success',
                'token': token,
                'user': user_data
            }
        else:
            # Autenticação falhou
            return {
                'status': 'error',
                'message': 'Credenciais inválidas'
            }
    
    def validate_token(self, token):
        """
        Valida um token com a API
        
        Args:
            token: Token a ser validado
            
        Returns:
            Dict: Resposta da validação
        """
        # Em um cenário real, isso faria uma requisição para a API
        # Para o mockup, simulamos uma validação simples
        
        # Simular uma pequena latência
        time.sleep(0.2)
        
        if token and token.startswith("mock_token_") and len(token) > 15:
            # Extrair username do token
            parts = token.split('_')
            if len(parts) >= 3:
                username = parts[2]
                
                # Criar dados simulados do usuário
                user_data = {
                    'username': username,
                    'email': f"{username}@example.com",
                    'id': f"user_{username}",
                    'role': 'admin' if username == 'admin' else 'user'
                }
                
                return {
                    'status': 'success',
                    'valid': True,
                    'user': user_data
                }
        
        return {
            'status': 'error',
            'valid': False,
            'message': 'Token inválido ou expirado'
        }
    
    def logout(self, token):
        """
        Realiza logout na API
        
        Args:
            token: Token a ser invalidado
            
        Returns:
            Dict: Resposta do logout
        """
        # Em um cenário real, isso faria uma requisição para a API
        # Para o mockup, simulamos um logout bem-sucedido
        
        # Remover token do header
        if "Authorization" in self.headers:
            del self.headers["Authorization"]
        
        return {
            'status': 'success',
            'message': 'Logout realizado com sucesso'
        }


# Instância global
_api_client = None

def get_api_client() -> APIClient:
    """Retorna a instância global do cliente de API"""
    global _api_client
    if _api_client is None:
        _api_client = APIClient()
    return _api_client
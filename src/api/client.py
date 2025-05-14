"""
Cliente para comunicação com APIs externas
"""
import logging
import requests
from requests.exceptions import RequestException

logger = logging.getLogger("PrintManager.API.Client")

class APIClient:
    """Cliente para comunicação com APIs externas"""

    def __init__(self, base_url, timeout=10):
        """Inicializa o cliente de API"""
        self.base_url = base_url
        self.timeout = timeout
        self.token = None

    def set_token(self, token):
        """Define o token de autenticação"""
        self.token = token

    def _get_headers(self):
        """Retorna os cabeçalhos de autenticação"""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        return headers

    def _make_request(self, method, endpoint, data=None, params=None):
        """Faz uma requisição HTTP"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = self._get_headers()

        try:
            if method == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            else:
                raise ValueError(f"Método inválido: {method}")

            response.raise_for_status()

            return response.json() if response.content else {}

        except RequestException as e:
            logger.error("Erro na requisição %s %s: %s", method, url, e)

            if hasattr(e, "response") and e.response is not None:
                status_code = e.response.status_code
                try:
                    error_data = e.response.json()
                    error_message = error_data.get('message', str(e))
                except ValueError:
                    error_message = e.response.text or str(e)
            else:
                status_code = 0
                error_message = str(e)

            raise APIError(error_message, status_code) from e

    def login(self, email, password):
        """Faz login na API"""
        data = {
            "email": email,
            "password": password
        }

        try:
            response = self._make_request("POST", "/login/desktop", data)

            if "data" in response and "token" in response:
                self.set_token(response["token"])

            return response
        except APIError as e:
            if e.status_code == 401:
                raise APIError("Email ou senha inválidos", 401) from e
            raise

    def get_printers(self):
        """Retorna a lista de impressoras disponíveis"""
        return self._make_request("GET", "/desktop/printers")


class APIError(Exception):
    """Erro na comunicação com a API"""

    def __init__(self, message, status_code=0):
        """Inicializa o erro"""
        self.status_code = status_code
        super().__init__(message)

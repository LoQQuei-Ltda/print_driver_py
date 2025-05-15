import requests
from src.api.utils.logger import logger

class APIClient:
    """Cliente para requisições HTTP"""

    def __init__(self, base_url="http://10.148.1.8:3000"):
        """Inicializa o cliente"""
        self.base_url = base_url
        self.token = None
        self.session = requests.Session()

    def login(self, email, password):
        """Faz login no servidor"""
        try:
            response = self.session.post(
                f"{self.base_url}/login/desktop",
                json={"email": email, "password": password}
                timeout=10
            )

            response.raise_for_status()
            data = response.json()

            if "token" in data:
                self.token = data["token"]
                self.session.headers.update({"Authorization": f"Bearer {self.token}"})
                logger.info("Login bem sucedido")
                return True, data
            
            logger.warning("Login falhou: token não encontrado")
            return False, "Token não encontrado na resposta"
        except requests.exceptions.RequestException as e:
            logger.error("Erro ao fazer login: %s", str(e))
            return False, str(e)
        
    def get_printers(self):
        """Retorna uma lista de impressoras disponíveis"""
        if not self.token:
            logger.error("Token não encontrado")
            return False, "Token não encontrado"
        
        try:
            response = self.session.get(
                f"{self.base_url}/desktop/printers",
                timeout=10
            )

            response.raise_for_status()
            data = response.json()
            logger.info("Obtidas %s impressoras", len(data))
            return True, data
        except requests.exceptions.RequestException as e:
            logger.error("Erro ao obter impressoras: %s", str(e))
            return False, str(e)
        
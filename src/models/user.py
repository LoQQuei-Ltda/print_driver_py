"""Modelo de usuário"""
import logging

logger = logging.getLogger("PrintManagementSystem.Models.User")

class User:
    """Modelo de usuário do sistema"""
    
    def __init__(self, user_data=None):
        """
        Inicializa o modelo de usuário
        
        Args:
            user_data (dict, optional): Dados do usuário
        """
        user_data = user_data or {}
        
        self.id = user_data.get("id", "")
        self.email = user_data.get("email", "")
        self.name = user_data.get("name", "")
        self.token = user_data.get("token", "")
        
        # Dados adicionais
        self.created_at = user_data.get("created_at", "")
        self.last_login = user_data.get("last_login", "")
        self.preferences = user_data.get("preferences", {})
    
    def to_dict(self):
        """
        Converte o modelo para dicionário
        
        Returns:
            dict: Representação do usuário como dicionário
        """
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "token": self.token,
            "created_at": self.created_at,
            "last_login": self.last_login,
            "preferences": self.preferences
        }
    
    @classmethod
    def from_api_response(cls, api_response):
        """
        Cria um modelo de usuário a partir da resposta da API
        
        Args:
            api_response (dict): Resposta da API
            
        Returns:
            User: Modelo de usuário
        """
        return cls(api_response)
    
    def __str__(self):
        """
        Representação em string do usuário
        
        Returns:
            str: Representação do usuário
        """
        return f"User(id={self.id}, email={self.email}, name={self.name})"
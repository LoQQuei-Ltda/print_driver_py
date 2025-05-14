"""
Módulo para autenticação de usuários
"""
import os
import json
import logging
import base64
from hashlib import sha256

logger = logging.getLogger("PrintManager.Utils.Auth")

class AuthManager:
    """Gerencia autenticação de usuários"""

    def __init__(self, config, api_client):
        """Inicializa o gerenciador de autenticação"""
        self.config = config
        self.api_client = api_client
        self.current_user = None

    def login(self, email, password, remember_me=False):
        """Faz login na API"""
        try:
            response = self.api_client.login(email, password)

            if response and "data" in response and "token" in response:
                self.current_user = {
                    "email": email,
                    "token": response["token"],
                    "remember_me": remember_me,
                    "name": response["data"].get("name", ""),
                    "id": response["data"].get("id", ""),
                    "picture": response["data"].get("picture", "")
                }

                self.config.set_user({
                    "email": email,
                    "token": response["token"] if remember_me else "",
                    "remember_me": remember_me,
                    "name": response["data"].get("name", ""),
                    "id": response["data"].get("id", ""),
                    "picture": response["data"].get("picture", "")
                })

                self.api_client.set_token(response["token"])
                return True

            return False
        except Exception as e:
            logger.error("Erro ao fazer login: %s", e)
            raise AuthError(str(e)) from e

    def logout(self):
        """Encerra sessão atual"""
        try:
            self.current_user = None
            self.api_client.set_token(None)
            self.config.clear_user()
            return True
        except Exception as e:
            logger.error("Erro ao fazer logout: %s", e)
            return False

    def is_authenticated(self):
        """Verifica se há um usuário autenticado"""
        return self.current_user is not None and "token" in self.current_user and self.current_user["token"]

    def auto_login(self):
        """Faz login automático"""
        user_info = self.config.get_user()

        if user_info and user_info.get("remember_me") and user_info.get("token"):
            try:
                self.current_user = user_info
                self.api_client.set_token(user_info["token"])
                return True

            except Exception as e:
                logger.error("Erro ao fazer login automático: %s", e)
                return False

        return False

    def get_current_user(self):
        return self.current_user


class AuthError(Exception):
    """Erro na autenticação"""
    pass

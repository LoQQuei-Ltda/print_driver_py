#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitários de autenticação
"""

import os
import json
import logging
import base64
from hashlib import sha256

logger = logging.getLogger("PrintManagementSystem.Utils.Auth")

class AuthManager:
    """Gerenciador de autenticação de usuário"""
    
    def __init__(self, config, api_client):
        """
        Inicializa o gerenciador de autenticação
        
        Args:
            config: Objeto de configuração da aplicação
            api_client: Cliente da API
        """
        self.config = config
        self.api_client = api_client
        self.current_user = None
    
    def login(self, email, password, remember_me=False):
        """
        Realiza login do usuário
        
        Args:
            email (str): Email do usuário
            password (str): Senha do usuário
            remember_me (bool): Lembrar usuário
            
        Returns:
            bool: True se o login foi bem-sucedido
            
        Raises:
            AuthError: Erro de autenticação
        """
        try:
            user_data = self.api_client.login(email, password)

            if user_data and "token" in user_data:
                self.current_user = {
                    "email": email,
                    "token": user_data["token"],
                    "remember_me": remember_me,
                    "name": user_data["user"].get("name", ""),
                    "picture": user_data["user"].get("picture", ""),
                    "id": user_data["user"].get("id", "")
                }
                
                self.config.set_user({
                    "email": email,
                    "token": user_data["token"] if remember_me else "",
                    "remember_me": remember_me,
                    "name": user_data["user"].get("name", ""),
                    "picture": user_data["user"].get("picture", ""),
                    "id": user_data["user"].get("id", "")
                })
                
                self.api_client.set_token(user_data["token"])
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Erro ao realizar login: {str(e)}")
            raise AuthError(str(e))
    
    def logout(self):
        """
        Realiza logout do usuário
        
        Returns:
            bool: True se o logout foi bem-sucedido
        """
        try:
            self.current_user = None
            self.api_client.set_token(None)
            self.config.clear_user()
            return True
        except Exception as e:
            logger.error(f"Erro ao realizar logout: {str(e)}")
            return False
    
    def is_authenticated(self):
        """
        Verifica se o usuário está autenticado
        
        Returns:
            bool: True se o usuário está autenticado
        """
        return self.current_user is not None and "token" in self.current_user and self.current_user["token"]
    
    def auto_login(self):
        """
        Tenta realizar login automático usando token salvo
        
        Returns:
            bool: True se o login automático foi bem-sucedido
        """
        user_info = self.config.get_user()
        
        if user_info and user_info.get("remember_me") and user_info.get("token"):
            try:
                self.current_user = user_info

                self.api_client.set_token(user_info["token"])
                
                validation_result = self.api_client.validate_user()

                # Verifica se o token é válido
                if validation_result["is_valid"]:
                    logger.info(f"Auto-login bem-sucedido para {user_info.get('email')}")
                    return True
                else:
                    # Token inválido ou outro erro
                    if validation_result["should_logout"]:
                        logger.warning("Token inválido durante auto-login (401)")

                        self.logout()
                        return False
                    else:
                        logger.warning(f"Erro de validação durante auto-login: {validation_result['error_message']} "
                                     f"(Código: {validation_result['error_code']})")
                    
                    return True

            except Exception as e:
                logger.error(f"Erro ao realizar login automático: {str(e)}")
                return False
        
        return False
    
    def get_current_user(self):
        """
        Obtém informações do usuário atual
        
        Returns:
            dict: Informações do usuário ou None se não estiver autenticado
        """
        return self.current_user


class AuthError(Exception):
    """Exceção para erros de autenticação"""
    pass
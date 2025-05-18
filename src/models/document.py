#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modelo de documento
"""

import os
import logging
import datetime

logger = logging.getLogger("PrintManagementSystem.Models.Document")

class Document:
    """Modelo de documento do sistema"""
    
    def __init__(self, document_data=None):
        """
        Inicializa o modelo de documento
        
        Args:
            document_data (dict, optional): Dados do documento
        """
        document_data = document_data or {}
        
        self.id = document_data.get("id", "")
        self.name = document_data.get("name", "")
        self.path = document_data.get("path", "")
        self.size = document_data.get("size", 0)
        self.created_at = document_data.get("created_at", "")
        self.pages = document_data.get("pages", 0)  # Adicionado campo de páginas
    
    def to_dict(self):
        """
        Converte o modelo para dicionário
        
        Returns:
            dict: Representação do documento como dicionário
        """
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "size": self.size,
            "created_at": self.created_at,
            "pages": self.pages  # Adicionado campo de páginas
        }
    
    @classmethod
    def from_api_response(cls, api_response):
        """
        Cria um modelo de documento a partir da resposta da API
        
        Args:
            api_response (dict): Resposta da API
            
        Returns:
            Document: Modelo de documento
        """
        return cls(api_response)
    
    @classmethod
    def from_file(cls, file_path, user_id=None):
        """
        Cria um modelo de documento a partir de um arquivo
        
        Args:
            file_path (str): Caminho do arquivo
            user_id (str, optional): ID do usuário
            
        Returns:
            Document: Modelo de documento
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Arquivo não encontrado: {file_path}")
        
        name = os.path.basename(file_path)
        size = os.path.getsize(file_path)
        created_at = datetime.datetime.fromtimestamp(os.path.getctime(file_path)).isoformat()
        
        # Usa o caminho do arquivo como ID para garantir unicidade
        doc_id = file_path
        
        return cls({
            "id": doc_id,
            "name": name,
            "path": file_path,
            "size": size,
            "created_at": created_at,
            "pages": 0  # Inicialmente 0, será atualizado ao processar o PDF
        })
    
    @property
    def file_exists(self):
        """
        Verifica se o arquivo do documento existe no disco
        
        Returns:
            bool: True se o arquivo existe
        """
        return os.path.exists(self.path) if self.path else False
    
    @property
    def formatted_size(self):
        """
        Retorna o tamanho formatado do documento
        
        Returns:
            str: Tamanho formatado
        """
        try:
            if not self.size:
                return "0 KB"
            
            # Converte para KB, MB ou GB
            if self.size < 1024:
                return f"{self.size} B"
            elif self.size < 1024 * 1024:
                return f"{self.size / 1024:.1f} KB"
            elif self.size < 1024 * 1024 * 1024:
                return f"{self.size / (1024 * 1024):.1f} MB"
            else:
                return f"{self.size / (1024 * 1024 * 1024):.1f} GB"
        except Exception:
            return str(self.size) + " B"
    
    @property
    def formatted_date(self):
        """
        Retorna a data de criação formatada
        
        Returns:
            str: Data formatada
        """
        if not self.created_at:
            return ""
        
        try:
            dt = datetime.datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return self.created_at
    
    def __str__(self):
        """
        Representação em string do documento
        
        Returns:
            str: Representação do documento
        """
        return f"Document(id={self.id}, name={self.name}, size={self.formatted_size}, pages={self.pages})"
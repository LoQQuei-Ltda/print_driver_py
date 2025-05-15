#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modelo de impressora
"""

import logging

logger = logging.getLogger("PrintManagementSystem.Models.Printer")

class Printer:
    """Modelo de impressora do sistema"""
    
    def __init__(self, printer_data=None):
        """
        Inicializa o modelo de impressora
        
        Args:
            printer_data (dict, optional): Dados da impressora
        """
        printer_data = printer_data or {}
        
        self.id = printer_data.get("id", "")
        self.name = printer_data.get("name", "")
        self.mac_address = printer_data.get("mac_address", "")
    
    def to_dict(self):
        """
        Converte o modelo para dicionário
        
        Returns:
            dict: Representação da impressora como dicionário
        """
        return {
            "id": self.id,
            "name": self.name,
            "mac_address": self.mac_address
        }
    
    @classmethod
    def from_api_response(cls, api_response):
        """
        Cria um modelo de impressora a partir da resposta da API
        
        Args:
            api_response (dict): Resposta da API
            
        Returns:
            Printer: Modelo de impressora
        """
        return cls(api_response)
    
    def __str__(self):
        """
        Representação em string da impressora
        
        Returns:
            str: Representação da impressora
        """
        return f"Printer(id={self.id}, name={self.name}, mac_address={self.mac_address})"
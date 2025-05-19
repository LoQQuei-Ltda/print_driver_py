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
        self.system_name = printer_data.get("system_name", "")
        
        # Campos de conectividade
        self.ip = printer_data.get("ip", "")
        self.uri = printer_data.get("uri", "")
        
        # Campos de informações
        self.location = printer_data.get("location", "")
        self.model = printer_data.get("model", "")
        self.state = printer_data.get("state", "")
        
        # Armazena todos os atributos detalhados
        self.attributes = printer_data.get("attributes", {})
        
        # Flags de status
        self.is_ready = printer_data.get("is_ready", False)
        self.is_online = printer_data.get("is_online", False)
    
    def to_dict(self):
        """
        Converte o modelo para dicionário
        
        Returns:
            dict: Representação da impressora como dicionário
        """
        return {
            "id": self.id,
            "name": self.name,
            "mac_address": self.mac_address,
            "system_name": self.system_name,
            "ip": self.ip,
            "uri": self.uri,
            "location": self.location,
            "model": self.model,
            "state": self.state,
            "attributes": self.attributes,
            "is_ready": self.is_ready,
            "is_online": self.is_online
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
    
    @classmethod
    def from_discovery(cls, discovery_data):
        """
        Cria um modelo de impressora a partir de dados de descoberta
        
        Args:
            discovery_data (dict): Dados de descoberta
            
        Returns:
            Printer: Modelo de impressora
        """
        # Valores padrão
        is_ready = False
        is_online = False
        
        # Verifica estado de conectividade
        if discovery_data.get("ip") and discovery_data.get("uri"):
            is_online = True
        
        # Verifica estado operacional
        state = discovery_data.get("printer-state", "")
        if state and "Idle" in state:
            is_ready = True
        
        printer_data = {
            "id": discovery_data.get("ip", ""),  # Usa o IP como ID para impressoras descobertas
            "ip": discovery_data.get("ip", ""),
            "mac_address": discovery_data.get("mac_address", ""),
            "uri": discovery_data.get("uri", ""),
            "name": discovery_data.get("name", discovery_data.get("ip", "Impressora Desconhecida")),
            "location": discovery_data.get("printer-location", ""),
            "model": discovery_data.get("printer-make-and-model", ""),
            "state": discovery_data.get("printer-state", ""),
            "is_ready": is_ready,
            "is_online": is_online,
            # Armazena todos os outros atributos
            "attributes": {k: v for k, v in discovery_data.items() 
                          if k not in ["id", "ip", "mac_address", "uri", "name"]}
        }
        
        return cls(printer_data)
    
    def update_from_discovery(self, discovery_data):
        """
        Atualiza a impressora com dados de descoberta
        
        Args:
            discovery_data (dict): Dados de descoberta
            
        Returns:
            Printer: Self
        """
        self.ip = discovery_data.get("ip", self.ip)
        self.mac_address = discovery_data.get("mac_address", self.mac_address)
        self.uri = discovery_data.get("uri", self.uri)
        
        # Atualiza nome apenas se não estiver definido
        if not self.name or self.name == self.id or self.name == self.ip:
            self.name = discovery_data.get("name", self.name)
        
        self.location = discovery_data.get("printer-location", self.location)
        self.model = discovery_data.get("printer-make-and-model", self.model)
        self.state = discovery_data.get("printer-state", self.state)
        
        # Atualiza flags de status
        if self.ip and self.uri:
            self.is_online = True
        
        if self.state and "Idle" in self.state:
            self.is_ready = True
        
        # Atualiza atributos
        for k, v in discovery_data.items():
            if k not in ["id", "ip", "mac_address", "uri", "name"]:
                self.attributes[k] = v
        
        return self
    
    def __str__(self):
        """
        Representação em string da impressora
        
        Returns:
            str: Representação da impressora
        """
        status = "Pronta" if self.is_online and self.is_ready else "Não disponível"
        return f"Printer(id={self.id}, name={self.name}, ip={self.ip}, mac_address={self.mac_address}, status={status})"
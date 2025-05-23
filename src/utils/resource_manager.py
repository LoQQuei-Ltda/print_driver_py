#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gerenciador de recursos para aplicação empacotada
Resolve caminhos de recursos de forma compatível com PyInstaller
"""

import os
import sys
import logging

logger = logging.getLogger("PrintManagementSystem.Utils.ResourceManager")

class ResourceManager:
    """Gerenciador de recursos para aplicação empacotada"""
    
    _base_path = None
    _resources_path = None
    
    @classmethod
    def get_base_path(cls):
        """
        Obtém o caminho base da aplicação
        
        Returns:
            str: Caminho base da aplicação
        """
        if cls._base_path is None:
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                # Executável empacotado com PyInstaller
                cls._base_path = sys._MEIPASS
                logger.debug(f"Aplicação empacotada detectada. Base path: {cls._base_path}")
            else:
                # Desenvolvimento - vai para a raiz do projeto
                cls._base_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                logger.debug(f"Modo desenvolvimento detectado. Base path: {cls._base_path}")
        
        return cls._base_path
    
    @classmethod
    def get_resources_path(cls):
        """
        Obtém o caminho da pasta de recursos
        
        Returns:
            str: Caminho da pasta de recursos
        """
        if cls._resources_path is None:
            base_path = cls.get_base_path()
            
            if getattr(sys, 'frozen', False):
                # Executável empacotado - recursos estão na pasta 'resources'
                cls._resources_path = os.path.join(base_path, "resources")
            else:
                # Desenvolvimento - recursos estão em 'src/ui/resources'
                cls._resources_path = os.path.join(base_path, "src", "ui", "resources")
            
            logger.debug(f"Resources path: {cls._resources_path}")
        
        return cls._resources_path
    
    @classmethod
    def get_resource_path(cls, resource_name):
        """
        Obtém o caminho completo para um recurso específico
        
        Args:
            resource_name (str): Nome do arquivo de recurso
            
        Returns:
            str: Caminho completo para o recurso ou None se não encontrado
        """
        resources_path = cls.get_resources_path()
        resource_path = os.path.join(resources_path, resource_name)
        
        if os.path.exists(resource_path):
            logger.debug(f"Recurso encontrado: {resource_path}")
            return resource_path
        else:
            logger.warning(f"Recurso não encontrado: {resource_path}")
            
            # Tenta encontrar em subpastas
            for root, dirs, files in os.walk(resources_path):
                if resource_name in files:
                    found_path = os.path.join(root, resource_name)
                    logger.debug(f"Recurso encontrado em subpasta: {found_path}")
                    return found_path
            
            return None
    
    @classmethod
    def get_icon_path(cls, icon_name="icon.ico"):
        """
        Obtém o caminho para um ícone
        
        Args:
            icon_name (str): Nome do arquivo de ícone
            
        Returns:
            str: Caminho para o ícone ou None se não encontrado
        """
        return cls.get_resource_path(icon_name)
    
    @classmethod
    def get_image_path(cls, image_name):
        """
        Obtém o caminho para uma imagem
        
        Args:
            image_name (str): Nome do arquivo de imagem
            
        Returns:
            str: Caminho para a imagem ou None se não encontrado
        """
        return cls.get_resource_path(image_name)
    
    @classmethod
    def list_resources(cls):
        """
        Lista todos os recursos disponíveis
        
        Returns:
            list: Lista de recursos encontrados
        """
        resources = []
        resources_path = cls.get_resources_path()
        
        if os.path.exists(resources_path):
            for root, dirs, files in os.walk(resources_path):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), resources_path)
                    resources.append(rel_path)
        
        logger.debug(f"Recursos encontrados: {resources}")
        return resources
    
    @classmethod
    def verify_resources(cls):
        """
        Verifica se os recursos principais estão disponíveis
        
        Returns:
            dict: Dicionário com status dos recursos
        """
        required_resources = [
            "icon.ico",
            "logo.png",
            "document.png",
            "printer.png",
            "system.png",
            "logout.png",
            "empty_document.png"
        ]
        
        status = {}
        for resource in required_resources:
            path = cls.get_resource_path(resource)
            status[resource] = {
                "found": path is not None,
                "path": path
            }
            
            if path is None:
                logger.warning(f"Recurso obrigatório não encontrado: {resource}")
            else:
                logger.debug(f"Recurso verificado: {resource} -> {path}")
        
        return status

# Funções de conveniência para compatibilidade
def get_resource_path(resource_name):
    """Função de conveniência para obter caminho de recurso"""
    return ResourceManager.get_resource_path(resource_name)

def get_icon_path(icon_name="icon.ico"):
    """Função de conveniência para obter caminho de ícone"""
    return ResourceManager.get_icon_path(icon_name)

def get_image_path(image_name):
    """Função de conveniência para obter caminho de imagem"""
    return ResourceManager.get_image_path(image_name)
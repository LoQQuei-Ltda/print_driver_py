#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Monitor para novos documentos
"""

import os
import logging
from datetime import datetime

from src.utils.file_monitor import FileMonitor

logger = logging.getLogger("PrintManagementSystem.VirtualPrinter.Monitor")

class PrintFolderMonitor:
    """Monitor para novos documentos na pasta de impressão"""
    
    def __init__(self, config, api_client=None, on_new_document=None):
        """
        Inicializa o monitor de pasta
        
        Args:
            config: Configuração da aplicação
            api_client: Cliente da API (opcional)
            on_new_document: Callback chamado quando um novo documento é detectado
        """
        self.config = config
        self.api_client = api_client
        self.on_new_document = on_new_document
        
        self.file_monitor = None
        self.processed_ids = set()
    
    def start(self):
        """
        Inicia o monitoramento da pasta
        
        Returns:
            bool: True se o monitoramento foi iniciado com sucesso
        """
        if self.file_monitor and self.file_monitor.observer and self.file_monitor.observer.is_alive():
            return True
        
        logger.info(f"Iniciando monitoramento da pasta: {self.config.pdf_dir}")
        
        # Cria callback para lidar com novos documentos
        def on_documents_changed(documents):
            if self.on_new_document and documents:
                # Chama o callback para cada documento não visto anteriormente
                for doc in documents:
                    if doc.id not in self.processed_ids:
                        logger.info(f"Novo documento detectado: {doc.name}")
                        
                        # Marca como processado
                        self.processed_ids.add(doc.id)
                        
                        # Aplica impressão automática se configurado
                        self._auto_print_if_enabled(doc)
                        
                        # Chama o callback do usuário
                        self.on_new_document(doc)
        
        # Cria e inicia o monitor de arquivos
        self.file_monitor = FileMonitor(self.config, on_documents_changed)
        self.file_monitor.start()
        
        return True
    
    def stop(self):
        """
        Para o monitoramento da pasta
        
        Returns:
            bool: True se o monitoramento foi parado com sucesso
        """
        if self.file_monitor:
            self.file_monitor.stop()
            return True
        return True
    
    def is_monitoring(self):
        """
        Verifica se o monitoramento está ativo
        
        Returns:
            bool: True se o monitoramento está ativo
        """
        return self.file_monitor and self.file_monitor.observer and self.file_monitor.observer.is_alive()
    
    def _auto_print_if_enabled(self, document):
        """
        Imprime automaticamente o documento se a impressão automática estiver ativada
        
        Args:
            document (Document): Documento a ser impresso
        """
        if not self.config.get("auto_print", False):
            return
        
        default_printer = self.config.get("default_printer", "")
        if not default_printer:
            logger.warning("Impressão automática ativada, mas nenhuma impressora padrão configurada")
            return
        
        try:
            logger.info(f"Enviando {document.name} para impressão automática na impressora {default_printer}")
            
            # Implementação de impressão automática
            from src.utils.printer_utils import PrinterUtils
            PrinterUtils.print_file(document.path, default_printer)
            
            logger.info(f"Documento {document.name} enviado para impressão automática com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao imprimir automaticamente: {str(e)}")
    
    def get_recent_documents(self, limit=50):
        """
        Obtém a lista de documentos recentes
        
        Args:
            limit (int): Limite de documentos a retornar
            
        Returns:
            list: Lista de objetos Document
        """
        if not self.file_monitor:
            return []
        
        # Obtém todos os documentos do monitor
        documents = self.file_monitor.get_documents()
        
        # Ordena por data de criação (mais recente primeiro)
        documents.sort(key=lambda d: d.created_at, reverse=True)
        
        # Retorna apenas os mais recentes
        return documents[:limit]
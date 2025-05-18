#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Monitor de arquivos PDF para o sistema de gerenciamento de impressão
"""

import os
import time
import logging
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.models.document import Document
from src.utils.pdf import PDFUtils

logger = logging.getLogger("PrintManagementSystem.Utils.FileMonitor")

class PDFHandler(FileSystemEventHandler):
    """Manipulador para eventos de arquivos PDF"""
    
    def __init__(self, file_monitor):
        """
        Inicializa o manipulador de PDFs
        
        Args:
            file_monitor: Instância do monitor de arquivos
        """
        super().__init__()
        self.file_monitor = file_monitor
    
    def on_created(self, event):
        """Manipula evento de criação de arquivo"""
        if event.is_directory:
            return
        
        if self._is_pdf_file(event.src_path):
            logger.info(f"Novo arquivo PDF criado: {event.src_path}")
            self.file_monitor.add_document(event.src_path)
    
    def on_deleted(self, event):
        """Manipula evento de exclusão de arquivo"""
        if event.is_directory:
            return
        
        if self._is_pdf_file(event.src_path):
            logger.info(f"Arquivo PDF excluído: {event.src_path}")
            self.file_monitor.remove_document(event.src_path)
    
    def on_modified(self, event):
        """Manipula evento de modificação de arquivo"""
        if event.is_directory:
            return
        
        if self._is_pdf_file(event.src_path):
            logger.info(f"Arquivo PDF modificado: {event.src_path}")
            self.file_monitor.update_document(event.src_path)
    
    def on_moved(self, event):
        """Manipula evento de movimentação de arquivo"""
        if event.is_directory:
            return
        
        # Verifica se o destino é um PDF
        if self._is_pdf_file(event.dest_path):
            logger.info(f"Arquivo PDF movido: {event.src_path} -> {event.dest_path}")
            self.file_monitor.remove_document(event.src_path)
            self.file_monitor.add_document(event.dest_path)
    
    def _is_pdf_file(self, path):
        """Verifica se o arquivo é um PDF"""
        return path.lower().endswith('.pdf')

class FileMonitor:
    """Monitor para arquivos PDF em um diretório"""
    
    def __init__(self, config, on_documents_changed=None):
        """
        Inicializa o monitor de arquivos
        
        Args:
            config: Configuração da aplicação
            on_documents_changed: Callback quando a lista de documentos muda
        """
        self.config = config
        self.on_documents_changed = on_documents_changed
        self.pdf_dir = config.pdf_dir
        self.documents = {}  # Caminho -> Documento
        self.observer = None
        self.lock = threading.Lock()
    
    def start(self):
        """Inicia o monitoramento do diretório"""
        if self.observer and self.observer.is_alive():
            return
        
        logger.info(f"Iniciando monitoramento de arquivos no diretório: {self.pdf_dir}")
        
        # Garante que o diretório existe
        os.makedirs(self.pdf_dir, exist_ok=True)
        
        # Carrega documentos iniciais
        self._load_initial_documents()
        
        # Configura o observador
        event_handler = PDFHandler(self)
        self.observer = Observer()
        self.observer.schedule(event_handler, self.pdf_dir, recursive=False)
        self.observer.start()
    
    def stop(self):
        """Para o monitoramento do diretório"""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
    
    def _load_initial_documents(self):
        """Carrega documentos existentes do diretório"""
        with self.lock:
            self.documents.clear()
            
            try:
                files = os.listdir(self.pdf_dir)
                for filename in files:
                    if filename.lower().endswith('.pdf'):
                        filepath = os.path.join(self.pdf_dir, filename)
                        self._add_document_internal(filepath)
                
                logger.info(f"Carregados {len(self.documents)} documentos iniciais")
                
                # Notifica sobre os documentos iniciais
                if self.on_documents_changed:
                    self.on_documents_changed(list(self.documents.values()))
            
            except Exception as e:
                logger.error(f"Erro ao carregar documentos iniciais: {str(e)}")
    
    def add_document(self, filepath):
        """
        Adiciona um documento ao monitor
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if self._add_document_internal(filepath):
                if self.on_documents_changed:
                    self.on_documents_changed(list(self.documents.values()))
    
    def _add_document_internal(self, filepath):
        """
        Adiciona um documento internamente sem disparar notificações
        
        Args:
            filepath: Caminho para o documento
            
        Returns:
            bool: True se o documento foi adicionado com sucesso
        """
        try:
            # Aguarda brevemente para garantir que o arquivo foi completamente escrito
            time.sleep(0.5)
            
            # Cria documento
            doc = Document.from_file(filepath)
            
            # Obtém a contagem de páginas
            try:
                pdf_info = PDFUtils.get_pdf_info(filepath)
                doc.pages = pdf_info.get("pages", 0)
            except Exception as e:
                logger.warning(f"Erro ao obter informações do PDF {filepath}: {str(e)}")
                doc.pages = 0
            
            # Armazena o documento
            self.documents[filepath] = doc
            return True
        
        except Exception as e:
            logger.error(f"Erro ao adicionar documento {filepath}: {str(e)}")
            return False
    
    def remove_document(self, filepath):
        """
        Remove um documento do monitor
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if filepath in self.documents:
                del self.documents[filepath]
                
                if self.on_documents_changed:
                    self.on_documents_changed(list(self.documents.values()))
    
    def update_document(self, filepath):
        """
        Atualiza um documento no monitor
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if filepath in self.documents:
                if self._add_document_internal(filepath):
                    if self.on_documents_changed:
                        self.on_documents_changed(list(self.documents.values()))
    
    def get_documents(self):
        """
        Obtém todos os documentos
        
        Returns:
            list: Lista de objetos Document
        """
        with self.lock:
            return list(self.documents.values())
    
    def get_document(self, document_id):
        """
        Obtém um documento pelo ID
        
        Args:
            document_id: ID do documento
            
        Returns:
            Document: Objeto Document ou None
        """
        with self.lock:
            for doc in self.documents.values():
                if doc.id == document_id:
                    return doc
            return None
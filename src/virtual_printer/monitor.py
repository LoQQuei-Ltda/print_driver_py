#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Monitor para novos documentos
"""

import os
import time
import logging
import threading
import platform
import re
from pathlib import Path
from datetime import datetime

from src.utils import PDFUtils
from src.models import Document

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
        
        self.pdf_dir = config.pdf_dir
        self.monitoring = False
        self.monitor_thread = None
        self.processed_files = set()
        
        # Garante que o diretório existe
        os.makedirs(self.pdf_dir, exist_ok=True)
    
    def start(self):
        """
        Inicia o monitoramento da pasta
        
        Returns:
            bool: True se o monitoramento foi iniciado com sucesso
        """
        if self.monitoring:
            return True
        
        logger.info(f"Iniciando monitoramento da pasta: {self.pdf_dir}")
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        return True
    
    def stop(self):
        """
        Para o monitoramento da pasta
        
        Returns:
            bool: True se o monitoramento foi parado com sucesso
        """
        if not self.monitoring:
            return True
        
        logger.info("Parando monitoramento da pasta")
        
        self.monitoring = False
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(2.0)  # Aguarda até 2 segundos
        
        return True
    
    def is_monitoring(self):
        """
        Verifica se o monitoramento está ativo
        
        Returns:
            bool: True se o monitoramento está ativo
        """
        return self.monitoring and self.monitor_thread and self.monitor_thread.is_alive()
    
    def _monitor_loop(self):
        """Loop principal de monitoramento"""
        logger.info("Thread de monitoramento iniciada")
        
        while self.monitoring:
            try:
                self._check_for_new_files()
                time.sleep(1.0)  # Verifica a cada segundo
            except Exception as e:
                logger.error(f"Erro no loop de monitoramento: {str(e)}")
                time.sleep(5.0)  # Aguarda mais tempo em caso de erro
        
        logger.info("Thread de monitoramento encerrada")
    
    def _check_for_new_files(self):
        """Verifica se há novos arquivos na pasta"""
        try:
            files = os.listdir(self.pdf_dir)
            
            for filename in files:
                if not filename.lower().endswith(".pdf"):
                    continue
                
                file_path = os.path.join(self.pdf_dir, filename)
                
                # Verifica se já foi processado
                if file_path in self.processed_files:
                    continue
                
                # Verifica se o arquivo está pronto (não está sendo escrito)
                if not self._is_file_ready(file_path):
                    continue
                
                logger.info(f"Novo arquivo PDF detectado: {filename}")
                
                # Processa o arquivo
                self._process_new_file(file_path)
                
                # Adiciona à lista de processados
                self.processed_files.add(file_path)
            
            # Limita o tamanho da lista de arquivos processados
            if len(self.processed_files) > 1000:
                self.processed_files = set(list(self.processed_files)[-1000:])
                
        except Exception as e:
            logger.error(f"Erro ao verificar novos arquivos: {str(e)}")
    
    def _is_file_ready(self, file_path):
        """
        Verifica se um arquivo está pronto para processamento
        
        Args:
            file_path (str): Caminho do arquivo
            
        Returns:
            bool: True se o arquivo está pronto
        """
        try:
            # Tenta abrir o arquivo com acesso exclusivo (Windows)
            # Se conseguir, o arquivo não está sendo escrito
            if platform.system() == 'Windows':
                try:
                    with open(file_path, 'rb', 0) as f:
                        return True
                except:
                    return False
            else:
                # Em sistemas UNIX, verifica se o arquivo não foi modificado recentemente
                mtime = os.path.getmtime(file_path)
                if time.time() - mtime > 1.0:  # arquivo não modificado no último segundo
                    return True
                return False
        except:
            return False
    
    def _process_new_file(self, file_path):
        """
        Processa um novo arquivo
        
        Args:
            file_path (str): Caminho do arquivo
        """
        try:
            # Cria um objeto Document
            doc = Document.from_file(file_path)
            
            # Obtém informações adicionais do PDF
            try:
                pdf_info = PDFUtils.get_pdf_info(file_path)
                doc.metadata = pdf_info.get("metadata", {})
            except Exception as e:
                logger.warning(f"Erro ao obter informações do PDF: {str(e)}")
            
            # Callback se definido
            if self.on_new_document:
                try:
                    self.on_new_document(doc)
                except Exception as e:
                    logger.error(f"Erro ao chamar callback para novo documento: {str(e)}")
            
            # Impressão automática
            self._auto_print_if_enabled(doc)
            
            # Envia para a API se disponível
            if self.api_client:
                self._upload_to_api(doc)
                
        except Exception as e:
            logger.error(f"Erro ao processar novo arquivo: {str(e)}")
    
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
            
            # TODO: Implementar envio para impressão real
            # from src.utils import PrinterUtils
            # PrinterUtils.print_file(document.path, default_printer)
            
        except Exception as e:
            logger.error(f"Erro ao imprimir automaticamente: {str(e)}")
    
    def _upload_to_api(self, document):
        """
        Envia o documento para a API
        
        Args:
            document (Document): Documento a ser enviado
        """
        if not self.api_client:
            return
        
        try:
            # TODO: Implementar envio para API
            # Aqui dependerá da API específica
            pass
            
        except Exception as e:
            logger.error(f"Erro ao enviar documento para API: {str(e)}")
    
    def get_recent_documents(self, limit=50):
        """
        Obtém a lista de documentos recentes
        
        Args:
            limit (int): Limite de documentos a retornar
            
        Returns:
            list: Lista de objetos Document
        """
        documents = []
        
        try:
            # Lista arquivos da pasta
            files = os.listdir(self.pdf_dir)
            
            # Filtra arquivos PDF
            pdf_files = [f for f in files if f.lower().endswith(".pdf")]
            
            # Obtém informações de cada arquivo
            for filename in pdf_files[-limit:]:  # Limita aos mais recentes
                file_path = os.path.join(self.pdf_dir, filename)
                
                try:
                    doc = Document.from_file(file_path)
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Erro ao processar arquivo {filename}: {str(e)}")
            
            # Ordena por data de criação (mais recente primeiro)
            documents.sort(key=lambda d: d.created_at, reverse=True)
            
            return documents[:limit]
            
        except Exception as e:
            logger.error(f"Erro ao obter documentos recentes: {str(e)}")
            return []
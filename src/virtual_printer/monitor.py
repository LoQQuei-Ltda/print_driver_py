#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Monitor integrado para impressora virtual
"""

import os
import logging
from datetime import datetime

from src.utils.file_monitor import FileMonitor
from .printer_server import PrinterServer
from .installer import VirtualPrinterInstaller
from src.utils.subprocess_utils import run_hidden

logger = logging.getLogger("PrintManagementSystem.VirtualPrinter.Monitor")

class VirtualPrinterManager:
    """Gerenciador completo da impressora virtual"""
    
    def __init__(self, config, api_client=None, on_new_document=None):
        """
        Inicializa o gerenciador da impressora virtual
        
        Args:
            config: Configuração da aplicação
            api_client: Cliente da API (opcional)
            on_new_document: Callback chamado quando um novo documento é detectado
        """
        self.config = config
        self.api_client = api_client
        self.on_new_document = on_new_document
        
        # Componentes
        self.printer_server = None
        self.installer = None
        self.file_monitor = None
        
        # Estado
        self.is_running = False
        self.processed_ids = set()
        
        # Inicializar componentes
        self._init_components()
    
    def _init_components(self):
        """Inicializa os componentes da impressora virtual"""
        # Criar servidor de impressão
        self.printer_server = PrinterServer(
            self.config, 
            self._on_server_document_created
        )
        
        # Criar instalador
        self.installer = VirtualPrinterInstaller(self.config)
        
        # Monitor de arquivos (será inicializado quando necessário)
        self.file_monitor = None
    
    def _diagnose_system(self):
        """Diagnostica o sistema e registra informações úteis"""
        import platform
        import ctypes
        
        logger.info("=== DIAGNÓSTICO DO SISTEMA ===")
        logger.info(f"Sistema operacional: {platform.system()} {platform.release()}")
        logger.info(f"Versão: {platform.version()}")
        logger.info(f"Arquitetura: {platform.machine()}")
        logger.info(f"Python: {platform.python_version()}")
        
        if platform.system() == 'Windows':
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                logger.info(f"Executando como administrador: {is_admin}")
            except:
                logger.info("Não foi possível verificar privilégios de administrador")
            
            # Verificar firewall
            try:
                result = run_hidden(
                    ['netsh', 'advfirewall', 'show', 'currentprofile'],
                    timeout=5
                )
                if result.returncode == 0:
                    if 'State                                 ON' in result.stdout:
                        logger.warning("Firewall do Windows está ATIVO - pode bloquear conexões")
                    else:
                        logger.info("Firewall do Windows está desativado")
            except:
                pass
        
        logger.info("=== FIM DO DIAGNÓSTICO ===")

    def _on_server_document_created(self, document):
        """Callback chamado quando o servidor cria um novo documento"""
        try:
            # Marcar como processado
            if document.id not in self.processed_ids:
                self.processed_ids.add(document.id)
                
                logger.info(f"Novo documento criado pela impressora virtual: {document.name}")
                
                # Aplicar impressão automática se configurado
                self._auto_print_if_enabled(document)
                
                # Chamar callback do usuário
                if self.on_new_document:
                    self.on_new_document(document)
        except Exception as e:
            logger.error(f"Erro ao processar documento do servidor: {e}")
    
    def start(self):
        """
        Inicia o sistema completo da impressora virtual
        
        Returns:
            bool: True se foi iniciado com sucesso
        """
        if self.is_running:
            logger.info("Sistema de impressora virtual já está rodando")
            return True
        
        self._diagnose_system()
        
        try:
            # 1. Iniciar servidor de impressão
            logger.info("Iniciando servidor de impressão...")
            if not self.printer_server.start():
                logger.error("Falha ao iniciar servidor de impressão")
                return False
            
            # 2. Instalar impressora virtual
            logger.info("Instalando impressora virtual...")
            server_info = self.printer_server.get_server_info()
            if not self.installer.install_with_server_info(server_info):
                logger.error("Falha ao instalar impressora virtual")
                self.printer_server.stop()
                return False
            
            # 3. Iniciar monitoramento de arquivos
            logger.info("Iniciando monitoramento de arquivos...")
            self._start_file_monitoring()
            
            self.is_running = True
            logger.info("Sistema de impressora virtual iniciado com sucesso")
            
            # Log das informações do servidor
            server_info = self.printer_server.get_server_info()
            logger.info(f"Servidor rodando em {server_info['ip']}:{server_info['port']}")
            logger.info(f"PDFs serão salvos em: {self.config.pdf_dir}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar sistema de impressora virtual: {e}")
            self.stop()
            return False
    
    def stop(self):
        """
        Para o sistema da impressora virtual
        
        Returns:
            bool: True se foi parado com sucesso
        """
        logger.info("Parando sistema de impressora virtual...")
        
        try:
            # Parar monitoramento de arquivos
            if self.file_monitor:
                self.file_monitor.stop()
                self.file_monitor = None
            
            # Parar servidor de impressão
            if self.printer_server:
                self.printer_server.stop()
            
            # Nota: Não removemos a impressora virtual intencionalmente
            # para que ela permaneça disponível mesmo quando a aplicação não está rodando
            
            self.is_running = False
            logger.info("Sistema de impressora virtual parado")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao parar sistema de impressora virtual: {e}")
            return False
    
    def reinstall_printer(self):
        """
        Reinstala a impressora virtual
        
        Returns:
            bool: True se a reinstalação foi bem-sucedida
        """
        logger.info("Reinstalando impressora virtual...")
        
        try:
            if self.installer and self.printer_server:
                server_info = self.printer_server.get_server_info()
                if server_info['running']:
                    return self.installer.reinstall()
                else:
                    logger.error("Servidor não está rodando, não é possível reinstalar")
                    return False
            else:
                logger.error("Componentes não inicializados")
                return False
        except Exception as e:
            logger.error(f"Erro ao reinstalar impressora virtual: {e}")
            return False
    
    def _start_file_monitoring(self):
        """Inicia o monitoramento da pasta de PDFs"""
        try:
            def on_documents_changed(documents):
                if self.on_new_document and documents:
                    for doc in documents:
                        # Só processa documentos que não vieram do servidor
                        if doc.id not in self.processed_ids:
                            logger.info(f"Novo documento detectado no sistema de arquivos: {doc.name}")
                            
                            # Marcar como processado
                            self.processed_ids.add(doc.id)
                            
                            # Aplicar impressão automática se configurado
                            self._auto_print_if_enabled(doc)
                            
                            # Chamar callback do usuário
                            self.on_new_document(doc)
            
            # Criar e iniciar o monitor de arquivos
            self.file_monitor = FileMonitor(self.config, on_documents_changed)
            self.file_monitor.start()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar monitoramento de arquivos: {e}")
    
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
            
            from src.utils.printer_utils import PrinterUtils
            PrinterUtils.print_file(document.path, default_printer)
            
            logger.info(f"Documento {document.name} enviado para impressão automática com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao imprimir automaticamente: {str(e)}")
    
    def get_status(self):
        """
        Obtém o status do sistema
        
        Returns:
            dict: Status dos componentes
        """
        status = {
            'running': self.is_running,
            'printer_installed': False,
            'server_running': False,
            'server_info': None,
            'monitoring_active': False
        }
        
        try:
            # Status da impressora
            if self.installer:
                status['printer_installed'] = self.installer.is_installed()
            
            # Status do servidor
            if self.printer_server:
                server_info = self.printer_server.get_server_info()
                status['server_running'] = server_info['running']
                status['server_info'] = server_info
            
            # Status do monitoramento
            if self.file_monitor:
                status['monitoring_active'] = (
                    self.file_monitor.observer and 
                    self.file_monitor.observer.is_alive()
                )
            
        except Exception as e:
            logger.error(f"Erro ao obter status: {e}")
        
        return status
    
    def get_recent_documents(self, limit=50):
        """
        Obtém a lista de documentos recentes
        
        Args:
            limit (int): Limite de documentos a retornar
            
        Returns:
            list: Lista de objetos Document
        """
        try:
            if not self.file_monitor:
                # Se o monitor não está ativo, cria um temporário para obter documentos
                from src.utils.file_monitor import FileMonitor
                temp_monitor = FileMonitor(self.config)
                temp_monitor._load_initial_documents()
                documents = temp_monitor.get_documents()
            else:
                documents = self.file_monitor.get_documents()
            
            # Ordena por data de criação (mais recente primeiro)
            documents.sort(key=lambda d: d.created_at, reverse=True)
            
            return documents[:limit]
        except Exception as e:
            logger.error(f"Erro ao obter documentos recentes: {e}")
            return []

# Para compatibilidade com código existente
class PrintFolderMonitor(VirtualPrinterManager):
    """Alias para compatibilidade com código existente"""
    
    def __init__(self, config, api_client=None, on_new_document=None):
        super().__init__(config, api_client, on_new_document)
        logger.warning("PrintFolderMonitor é deprecated. Use VirtualPrinterManager em vez disso.")
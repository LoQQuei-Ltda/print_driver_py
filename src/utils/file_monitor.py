#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Monitor de arquivos PDF para o sistema de gerenciamento de impressão
"""

import os
import time
import logging
import threading
import platform
import appdirs
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
        self.base_pdf_dir = config.pdf_dir
        self.documents = {}  # Caminho -> Documento
        self.observers = []  # Lista de observadores para múltiplos diretórios
        self._main_observer = None  # Observador principal para compatibilidade
        self.lock = threading.Lock()
        self.system = platform.system()
        
        # Lista de diretórios a monitorar
        self.pdf_dirs = self._get_pdf_directories()
        
        logger.info(f"Base de diretórios PDF configurada: {self.base_pdf_dir}")
        logger.info(f"Diretórios a monitorar: {len(self.pdf_dirs)}")
    
    # Propriedade para compatibilidade com código existente
    @property
    def observer(self):
        """
        Propriedade de compatibilidade para código existente que espera um único observador
        
        Returns:
            Observer: O primeiro observador na lista ou None se não houver observadores
        """
        if self._main_observer:
            return self._main_observer
        
        if self.observers and len(self.observers) > 0:
            return self.observers[0]
        
        return None
    
    def _get_pdf_directories(self):
        """
        Obtém a lista de diretórios de PDF a serem monitorados
        
        Returns:
            list: Lista de diretórios
        """
        # Sempre incluir o diretório base de PDFs
        directories = [self.base_pdf_dir]
        
        # Se estiver no Windows, adiciona os diretórios de usuários específicos
        if self.system == 'Windows':
            try:
                # Diretório Users
                users_dir = os.path.join(os.environ.get('SystemDrive', 'C:'), 'Users')
                
                if os.path.exists(users_dir):
                    # Lista todos os usuários
                    for username in os.listdir(users_dir):
                        user_profile = os.path.join(users_dir, username)
                        
                        # Verifica se é um diretório de usuário válido (ignora .Default, Public, etc.)
                        if os.path.isdir(user_profile) and not username.startswith('.') and username not in ['Public', 'Default', 'Default User', 'All Users', 'desktop.ini']:
                            # Localização padrão AppData para o usuário
                            app_data = os.path.join(user_profile, 'AppData', 'Local')
                            
                            if os.path.exists(app_data):
                                user_pdf_dir = os.path.join(app_data, 'PrintManagementSystem', 'LoQQuei', 'pdfs')
                                
                                # Adiciona se o diretório existir
                                if os.path.exists(user_pdf_dir):
                                    # Só adiciona se não for o mesmo que o diretório base
                                    if os.path.normpath(user_pdf_dir) != os.path.normpath(self.base_pdf_dir):
                                        directories.append(user_pdf_dir)
                                        logger.info(f"Monitorando diretório do usuário {username}: {user_pdf_dir}")
                                else:
                                    # Tenta criar o diretório, se tiver permissão
                                    try:
                                        os.makedirs(user_pdf_dir, exist_ok=True)
                                        directories.append(user_pdf_dir)
                                        logger.info(f"Criado e monitorando diretório do usuário {username}: {user_pdf_dir}")
                                    except (PermissionError, OSError):
                                        # Ignora se não puder criar o diretório
                                        pass
            except Exception as e:
                logger.warning(f"Erro ao listar diretórios de usuários: {e}")
        
        # Garantir que não há duplicatas
        unique_directories = []
        for directory in directories:
            normalized_path = os.path.normpath(directory)
            if normalized_path not in [os.path.normpath(d) for d in unique_directories]:
                unique_directories.append(normalized_path)
        
        logger.info(f"Total de diretórios a monitorar: {len(unique_directories)}")
        return unique_directories
    
    def start(self):
        """Inicia o monitoramento dos diretórios"""
        if self.observers:
            logger.info("Monitor de arquivos já está ativo")
            return
        
        # Garante que estamos monitorando todos os diretórios possíveis
        self.pdf_dirs = self._get_pdf_directories()
        
        logger.info(f"Iniciando monitoramento de arquivos em {len(self.pdf_dirs)} diretórios")
        
        # Carrega documentos iniciais
        self._load_initial_documents()
        
        # Configura os observadores para cada diretório
        for i, pdf_dir in enumerate(self.pdf_dirs):
            try:
                # Garante que o diretório existe
                os.makedirs(pdf_dir, exist_ok=True)
                
                # Configura o observador
                event_handler = PDFHandler(self)
                observer = Observer()
                observer.schedule(event_handler, pdf_dir, recursive=False)
                observer.start()
                
                # Armazena o observador
                self.observers.append(observer)
                
                # Se for o primeiro observador, salva como principal para compatibilidade
                if i == 0:
                    self._main_observer = observer
                
                logger.info(f"Monitoramento iniciado para: {pdf_dir}")
                
            except Exception as e:
                logger.error(f"Erro ao iniciar monitoramento para {pdf_dir}: {str(e)}")
        
        # Verifica se pelo menos um observador foi iniciado
        if not self.observers:
            logger.warning("Nenhum observador foi iniciado! Monitoramento de arquivos não está funcionando.")
        else:
            logger.info(f"{len(self.observers)} observadores iniciados com sucesso.")
    
    def stop(self):
        """Para o monitoramento dos diretórios"""
        logger.info("Parando monitoramento de arquivos")
        
        for observer in self.observers:
            if observer.is_alive():
                observer.stop()
                observer.join()
        
        self.observers = []
        self._main_observer = None
    
    def _load_initial_documents(self):
        """Carrega documentos existentes de todos os diretórios monitorados"""
        with self.lock:
            self.documents.clear()
            
            # Garante que estamos monitorando todos os diretórios possíveis
            self.pdf_dirs = self._get_pdf_directories()
            
            for pdf_dir in self.pdf_dirs:
                try:
                    if os.path.exists(pdf_dir):
                        files = os.listdir(pdf_dir)
                        for filename in files:
                            if filename.lower().endswith('.pdf'):
                                filepath = os.path.join(pdf_dir, filename)
                                self._add_document_internal(filepath)
                        logger.info(f"Carregados documentos do diretório: {pdf_dir}")
                except Exception as e:
                    logger.error(f"Erro ao carregar documentos de {pdf_dir}: {str(e)}")
            
            logger.info(f"Total de documentos carregados: {len(self.documents)}")
            
            # Notifica sobre os documentos iniciais
            if self.on_documents_changed:
                self.on_documents_changed(list(self.documents.values()))
    
    def add_document(self, filepath):
        """
        Adiciona um documento ao monitor
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if self._add_document_internal(filepath):
                document = self.documents.get(filepath)
                auto_print_enabled = self.config.get("auto_print", False)

                if document and auto_print_enabled:
                    self._process_auto_print(document)
                elif document and not auto_print_enabled:
                    # Se auto-impressão não estiver ativada, mostra a tela de documentos
                    self._show_documents_screen()
            
    def _show_documents_screen(self):
        """Mostra a tela de documentos quando auto-impressão não está ativa"""
        import wx
        
        def show_documents():
            try:
                # Obtém todas as janelas abertas
                for window in wx.GetTopLevelWindows():
                    # Verifica se é a janela principal (MainScreen)
                    if hasattr(window, 'on_show_documents'):
                        # Mostra a janela se estiver oculta
                        if not window.IsShown():
                            window.Show(True)
                        
                        # Se estiver minimizada, restaura
                        if window.IsIconized():
                            window.Iconize(False)
                        
                        # Traz para frente
                        window.Raise()
                        
                        # Muda para a tela de documentos
                        window.on_show_documents()
                        break
                        
            except Exception as e:
                logger.error(f"Erro ao mostrar tela de documentos: {str(e)}")
        
        # Executa na thread principal da UI
        wx.CallAfter(show_documents)
    
    def process_existing_documents(self):
        """Processa todos os documentos existentes para auto-impressão"""
        if not self.config.get("auto_print", False):
            return
        
        with self.lock:
            for document in self.documents.values():
                self._process_auto_print(document)
        
        logger.info(f"Auto-impressão: Processados {len(self.documents)} documentos existentes")

    def _process_auto_print(self, document):
        """
        Processa a impressão automática de um documento
        
        Args:
            document: Documento a ser impresso
        
        Returns:
            bool: True se a impressão foi iniciada
        """
        if not self.config.get("auto_print", False):
            return False
        
        try:
            # Obtém a impressora padrão
            default_printer_name = self.config.get("default_printer", "")
            if not default_printer_name:
                logger.warning("Auto-impressão: Nenhuma impressora padrão configurada")
                return False
            
            # Obtém a lista de impressoras
            printers = self.config.get_printers()
            if not printers:
                logger.warning("Auto-impressão: Nenhuma impressora configurada")
                return False
            
            # Encontra a impressora padrão
            printer = None
            for p in printers:
                if p.get('name') == default_printer_name:
                    from src.models.printer import Printer
                    printer = Printer(p)
                    break
            
            if not printer:
                logger.warning(f"Auto-impressão: Impressora padrão '{default_printer_name}' não encontrada")
                return False
            
            # Obtém as opções de impressão
            options_dict = self.config.get("auto_print_options", {})
            
            from src.utils.print_system import PrintOptions, ColorMode, Duplex, Quality
            
            # Converte as opções para objetos
            options = PrintOptions()
            
            # Modo de cor
            color_mode = options_dict.get("color_mode", "auto")
            if color_mode == "color":
                options.color_mode = ColorMode.COLORIDO
            elif color_mode == "monochrome":
                options.color_mode = ColorMode.MONOCROMO
            else:
                options.color_mode = ColorMode.AUTO
            
            # Duplex
            duplex = options_dict.get("duplex", "one-sided")
            if duplex == "two-sided-long-edge":
                options.duplex = Duplex.DUPLEX_LONGO
            elif duplex == "two-sided-short-edge":
                options.duplex = Duplex.DUPLEX_CURTO
            else:
                options.duplex = Duplex.SIMPLES
            
            # Qualidade
            quality = options_dict.get("quality", 4)
            if quality == 3:
                options.quality = Quality.RASCUNHO
            elif quality == 5:
                options.quality = Quality.ALTA
            else:
                options.quality = Quality.NORMAL
            
            # Orientação
            orientation = options_dict.get("orientation", "portrait")
            options.orientation = orientation
            
            # Cópias
            options.copies = options_dict.get("copies", 1)
            
            # Inicializa o sistema de impressão
            from src.utils.print_system import PrintSystem
            print_system = PrintSystem(self.config)
            
            # Configura o trabalho de impressão
            import time
            from datetime import datetime
            from src.utils.print_system import IPPPrinter, PrintJobInfo
            
            # Cria um ID único para o trabalho
            job_id = f"auto_{int(time.time())}_{document.id}"
            
            # Cria objeto de informações do trabalho
            job_info = PrintJobInfo(
                job_id=job_id,
                document_path=document.path,
                document_name=document.name,
                printer_name=printer.name,
                printer_id=getattr(printer, 'id', printer.name),
                printer_ip=getattr(printer, 'ip', ''),
                options=options,
                start_time=datetime.now(),
                status="pending"
            )
            
            # Cria instância da impressora
            printer_ip = getattr(printer, 'ip', '')
            if not printer_ip:
                logger.error(f"Auto-impressão: A impressora '{printer.name}' não possui um endereço IP configurado")
                return False
            
            printer_instance = IPPPrinter(
                printer_ip=printer_ip,
                port=631
            )
            
            # Adiciona o trabalho à fila
            print_queue_manager = print_system.print_queue_manager
            print_queue_manager.add_job(
                job_info,
                printer_instance,
                None  # Sem callback para notificação
            )
            
            logger.info(f"Auto-impressão: Documento '{document.name}' enviado para impressão")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar auto-impressão: {e}")
            return False
        
    def set_auto_print(self, enabled):
        """
        Define se a auto-impressão está ativada
        
        Args:
            enabled (bool): True para ativar, False para desativar
        """
        self.config.set("auto_print", enabled)
        
        # Se foi ativado, processa documentos existentes
        if enabled:
            self.process_existing_documents()

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
            
            # Notifica sobre a alteração
            if self.on_documents_changed:
                self.on_documents_changed(list(self.documents.values()))
                
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
            
    def refresh_directories(self):
        """
        Atualiza a lista de diretórios monitorados e reinicia o monitoramento
        """
        logger.info("Atualizando diretórios monitorados")
        
        # Para todos os observadores atuais
        self.stop()
        
        # Atualiza a lista de diretórios
        self.pdf_dirs = self._get_pdf_directories()
        
        # Reinicia o monitoramento
        self.start()
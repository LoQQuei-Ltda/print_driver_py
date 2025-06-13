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
import hashlib
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from src.models.document import Document
from src.utils.pdf import PDFUtils

logger = logging.getLogger("PrintManagementSystem.Utils.FileMonitor")

class PDFHandler(FileSystemEventHandler):
    """Manipulador para eventos de arquivos PDF - VERSÃO CORRIGIDA"""
    
    def __init__(self, file_monitor):
        """
        Inicializa o manipulador de PDFs
        
        Args:
            file_monitor: Instância do monitor de arquivos
        """
        super().__init__()
        self.file_monitor = file_monitor
        # CORREÇÃO: Adiciona debounce para evitar múltiplos eventos
        self.pending_events = {}
        self.event_lock = threading.Lock()
    
    def on_created(self, event):
        """Manipula evento de criação de arquivo com debounce"""
        if event.is_directory:
            return
        
        if self._is_pdf_file(event.src_path):
            logger.info(f"Novo arquivo PDF criado: {event.src_path}")
            self._debounce_event('created', event.src_path)
    
    def on_deleted(self, event):
        """Manipula evento de exclusão de arquivo"""
        if event.is_directory:
            return
        
        if self._is_pdf_file(event.src_path):
            logger.info(f"Arquivo PDF excluído: {event.src_path}")
            # Cancelar eventos pendentes para este arquivo
            self._cancel_pending_events(event.src_path)
            self.file_monitor.remove_document(event.src_path)
    
    def on_modified(self, event):
        """Manipula evento de modificação de arquivo com debounce"""
        if event.is_directory:
            return
        
        if self._is_pdf_file(event.src_path):
            logger.info(f"Arquivo PDF modificado: {event.src_path}")
            self._debounce_event('modified', event.src_path)
    
    def on_moved(self, event):
        """Manipula evento de movimentação de arquivo"""
        if event.is_directory:
            return
        
        # Verifica se o destino é um PDF
        if self._is_pdf_file(event.dest_path):
            logger.info(f"Arquivo PDF movido: {event.src_path} -> {event.dest_path}")
            self._cancel_pending_events(event.src_path)
            self.file_monitor.remove_document(event.src_path)
            self._debounce_event('created', event.dest_path)
    
    def _debounce_event(self, event_type, file_path):
        """
        Implementa debounce para evitar múltiplos eventos para o mesmo arquivo
        
        Args:
            event_type: Tipo do evento ('created' ou 'modified')
            file_path: Caminho do arquivo
        """
        with self.event_lock:
            current_time = time.time()
            
            # Chave única para o arquivo e tipo de evento
            event_key = f"{event_type}:{file_path}"
            
            # Cancelar timer anterior se existir
            if event_key in self.pending_events:
                self.pending_events[event_key].cancel()
            
            # Criar novo timer
            timer = threading.Timer(
                2.0,  # Aguarda 2 segundos antes de processar
                self._process_debounced_event,
                args=[event_type, file_path, event_key]
            )
            
            self.pending_events[event_key] = timer
            timer.start()
    
    def _process_debounced_event(self, event_type, file_path, event_key):
        """Processa o evento após o debounce"""
        try:
            with self.event_lock:
                # Remove da lista de eventos pendentes
                if event_key in self.pending_events:
                    del self.pending_events[event_key]
            
            # Verifica se o arquivo ainda existe (pode ter sido deletado)
            if not os.path.exists(file_path):
                logger.debug(f"Arquivo {file_path} não existe mais, ignorando evento {event_type}")
                return
            
            # Processa o evento baseado no tipo
            if event_type == 'created':
                self.file_monitor.add_document(file_path)
            elif event_type == 'modified':
                self.file_monitor.update_document(file_path)
                
        except Exception as e:
            logger.error(f"Erro ao processar evento {event_type} para {file_path}: {e}")
    
    def _cancel_pending_events(self, file_path):
        """Cancela todos os eventos pendentes para um arquivo"""
        with self.event_lock:
            keys_to_remove = []
            for event_key in self.pending_events:
                if file_path in event_key:
                    self.pending_events[event_key].cancel()
                    keys_to_remove.append(event_key)
            
            for key in keys_to_remove:
                del self.pending_events[key]
    
    def _is_pdf_file(self, path):
        """Verifica se o arquivo é um PDF"""
        return path.lower().endswith('.pdf')

_GLOBAL_OBSERVERS = {}  # path -> observer
_GLOBAL_OBSERVERS_LOCK = threading.Lock()

class FileMonitor:
    """Monitor para arquivos PDF em um diretório"""
    
    def __init__(self, config, on_documents_changed=None):
        """
        Inicializa o monitor de arquivos - VERSÃO CORRIGIDA PARA MACOS
        """
        self.config = config
        self.on_documents_changed = on_documents_changed
        self.base_pdf_dir = config.pdf_dir
        self.documents = {}  # Caminho -> Documento
        self.observers = []  # Lista de observadores para múltiplos diretórios
        self._main_observer = None  # Observador principal para compatibilidade
        self.lock = threading.Lock()
        self.system = platform.system()
        
        # CORREÇÃO MACOS: Controles específicos para evitar observadores duplicados
        self._is_monitoring = False
        self._monitored_paths = set()  # Conjunto de caminhos já monitorados
        self._startup_lock = threading.Lock()  # Lock específico para startup
        
        # Lista de diretórios a monitorar
        self.pdf_dirs = self._get_pdf_directories()
        
        # CORREÇÃO: Adiciona controle de processamento de auto-impressão
        self.auto_print_processed = {}  # arquivo -> timestamp do último processamento
        self.auto_print_lock = threading.Lock()

        self.file_hashes = {}
        self.hash_lock = threading.Lock()
        
        logger.info(f"Base de diretórios PDF configurada: {self.base_pdf_dir}")
        logger.info(f"Diretórios a monitorar: {len(self.pdf_dirs)}")

        self._is_monitoring = False
        self._last_file_state = {}
        
        logger.info(f"FileMonitor inicializado para macOS")
    
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
    
    def _get_file_hash(self, filepath):
        """
        Calcula o hash do arquivo para detectar duplicatas reais
        
        Args:
            filepath: Caminho do arquivo
            
        Returns:
            str: Hash MD5 do arquivo ou None em caso de erro
        """
        try:
            with open(filepath, 'rb') as f:
                # Lê apenas os primeiros 4KB para eficiência
                content = f.read(4096)
                return hashlib.md5(content).hexdigest()
        except Exception as e:
            logger.debug(f"Erro ao calcular hash de {filepath}: {e}")
            return None

    def _is_duplicate_file(self, filepath):
        """
        Verifica se o arquivo é uma duplicata baseado no hash - VERSÃO MODIFICADA
        Agora permite arquivos com mesmo conteúdo se tiverem nomes diferentes
        
        Args:
            filepath: Caminho do arquivo
            
        Returns:
            bool: True se for duplicata
        """
        with self.hash_lock:
            file_hash = self._get_file_hash(filepath)
            if not file_hash:
                return False
            
            filename = os.path.basename(filepath)
            
            # Verifica se já existe um arquivo com o mesmo hash E mesmo nome
            for existing_path, existing_hash in self.file_hashes.items():
                if existing_hash == file_hash and existing_path != filepath:
                    existing_filename = os.path.basename(existing_path)
                    
                    # Se o arquivo existente ainda existe E tem o mesmo nome
                    if os.path.exists(existing_path) and existing_filename == filename:
                        # Verifica se são realmente o mesmo arquivo (mesmo timestamp e tamanho)
                        try:
                            stat1 = os.stat(filepath)
                            stat2 = os.stat(existing_path)
                            
                            # Se têm o mesmo tamanho e foram modificados com menos de 2 segundos de diferença
                            if (stat1.st_size == stat2.st_size and 
                                abs(stat1.st_mtime - stat2.st_mtime) < 2):
                                logger.info(f"Arquivo duplicado detectado: {filepath} (duplicata exata de {existing_path})")
                                return True
                        except Exception as e:
                            logger.debug(f"Erro ao comparar arquivos: {e}")
                            continue
                    else:
                        # Remove hash de arquivo que não existe mais
                        if not os.path.exists(existing_path):
                            del self.file_hashes[existing_path]
            
            # Adiciona o hash do arquivo atual
            self.file_hashes[filepath] = file_hash
            return False

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
        """Inicia o monitoramento - VERSÃO DEFINITIVA SEM DUPLICAÇÃO"""
        global _GLOBAL_OBSERVERS, _GLOBAL_OBSERVERS_LOCK
        
        with _GLOBAL_OBSERVERS_LOCK:
            if hasattr(self, '_is_monitoring') and self._is_monitoring:
                logger.info("Monitor de arquivos já está ativo para esta instância")
                return
            
            # Carrega documentos iniciais primeiro
            self._load_initial_documents()
            
            # Atualiza diretórios
            self.pdf_dirs = self._get_pdf_directories()
            logger.info(f"Iniciando monitoramento de arquivos em {len(self.pdf_dirs)} diretórios")
            
            successfully_started = 0
            
            for pdf_dir in self.pdf_dirs:
                try:
                    # Normaliza o caminho
                    normalized_path = os.path.normpath(os.path.abspath(pdf_dir))
                    
                    # Verifica se já existe observador global para este caminho
                    if normalized_path in _GLOBAL_OBSERVERS:
                        existing_observer = _GLOBAL_OBSERVERS[normalized_path]
                        if existing_observer and existing_observer.is_alive():
                            logger.info(f"Reutilizando observador existente para: {pdf_dir}")
                            self.observers.append(existing_observer)
                            if not self._main_observer:
                                self._main_observer = existing_observer
                            successfully_started += 1
                            continue
                        else:
                            # Remove observador morto
                            del _GLOBAL_OBSERVERS[normalized_path]
                    
                    # Cria novo observador apenas se não existir
                    os.makedirs(pdf_dir, exist_ok=True)
                    
                    event_handler = PDFHandler(self)
                    observer = Observer()
                    observer.schedule(event_handler, pdf_dir, recursive=False)
                    observer.start()
                    
                    # Armazena globalmente e localmente
                    _GLOBAL_OBSERVERS[normalized_path] = observer
                    self.observers.append(observer)
                    
                    if not self._main_observer:
                        self._main_observer = observer
                    
                    successfully_started += 1
                    logger.info(f"Novo observador criado para: {pdf_dir}")
                    
                except RuntimeError as re:
                    if "already scheduled" in str(re).lower():
                        logger.warning(f"Diretório {pdf_dir} já monitorado (ignorado): {str(re)}")
                        continue
                    else:
                        logger.error(f"Erro RuntimeError: {str(re)}")
                        continue
                except Exception as e:
                    logger.error(f"Erro ao iniciar monitoramento para {pdf_dir}: {str(e)}")
                    continue
            
            # Marca como ativo
            self._is_monitoring = True
            
            # Inicia verificação periódica como fallback
            self._start_periodic_check()
            
            if successfully_started > 0:
                logger.info(f"{successfully_started} observadores ativos (reutilizados + novos)")
            else:
                logger.warning("Nenhum observador ativo - usando apenas verificação periódica")
    
    def _start_periodic_check(self):
        """Inicia verificação periódica como fallback"""
        if hasattr(self, '_periodic_timer'):
            return
        
        def periodic_check():
            if hasattr(self, '_is_monitoring') and self._is_monitoring:
                try:
                    # Verifica mudanças nos arquivos a cada 3 segundos
                    self._check_file_changes()
                    
                    # Agenda próxima verificação
                    if hasattr(self, '_is_monitoring') and self._is_monitoring:
                        self._periodic_timer = threading.Timer(3.0, periodic_check)
                        self._periodic_timer.daemon = True
                        self._periodic_timer.start()
                except Exception as e:
                    logger.debug(f"Erro na verificação periódica: {str(e)}")
        
        self._periodic_timer = threading.Timer(3.0, periodic_check)
        self._periodic_timer.daemon = True
        self._periodic_timer.start()
        logger.info("Verificação periódica de arquivos iniciada")

    def _check_file_changes(self):
        """Verifica mudanças nos arquivos manualmente"""
        try:
            current_files = {}
            
            # Escaneia todos os diretórios
            for pdf_dir in self.pdf_dirs:
                if os.path.exists(pdf_dir):
                    for filename in os.listdir(pdf_dir):
                        if filename.lower().endswith('.pdf'):
                            filepath = os.path.join(pdf_dir, filename)
                            try:
                                stat = os.stat(filepath)
                                current_files[filepath] = {
                                    'mtime': stat.st_mtime,
                                    'size': stat.st_size
                                }
                            except:
                                continue
            
            # Compara com estado anterior
            if not hasattr(self, '_last_file_state'):
                self._last_file_state = current_files
                return
            
            # Detecta novos arquivos
            for filepath in current_files:
                if filepath not in self._last_file_state:
                    logger.info(f"Novo arquivo detectado (verificação manual): {filepath}")
                    self.add_document(filepath)
            
            # Detecta arquivos removidos
            for filepath in self._last_file_state:
                if filepath not in current_files:
                    logger.info(f"Arquivo removido detectado (verificação manual): {filepath}")
                    self.remove_document(filepath)
            
            # Detecta arquivos modificados
            for filepath in current_files:
                if filepath in self._last_file_state:
                    old_state = self._last_file_state[filepath]
                    new_state = current_files[filepath]
                    if (old_state['mtime'] != new_state['mtime'] or 
                        old_state['size'] != new_state['size']):
                        logger.info(f"Arquivo modificado detectado (verificação manual): {filepath}")
                        self.update_document(filepath)
            
            # Atualiza estado
            self._last_file_state = current_files
            
        except Exception as e:
            logger.debug(f"Erro na verificação manual: {str(e)}")

    def _start_observer_for_directory(self, pdf_dir):
        """
        Inicia um observador para um diretório específico
        
        Args:
            pdf_dir: Diretório para monitorar
            
        Returns:
            bool: True se o observador foi iniciado com sucesso
        """
        try:
            # Normaliza o caminho
            normalized_path = os.path.normpath(os.path.abspath(pdf_dir))
            
            # Verifica se já está sendo monitorado
            if normalized_path in self._monitored_paths:
                logger.info(f"Diretório {pdf_dir} já está sendo monitorado, pulando...")
                return False
            
            # Garante que o diretório existe
            os.makedirs(pdf_dir, exist_ok=True)
            
            # Cria o observador
            event_handler = PDFHandler(self)
            observer = Observer()
            
            # CORREÇÃO MACOS: Try/catch específico para FSEvents com cleanup
            try:
                observer.schedule(event_handler, pdf_dir, recursive=False)
                observer.start()
                
                # Se chegou aqui, foi bem sucedido
                self.observers.append(observer)
                self._monitored_paths.add(normalized_path)
                
                # Se for o primeiro observador, salva como principal
                if not self._main_observer:
                    self._main_observer = observer
                
                logger.info(f"Monitoramento iniciado para: {pdf_dir}")
                return True
                
            except RuntimeError as re:
                if "already scheduled" in str(re).lower():
                    logger.warning(f"Diretório {pdf_dir} já está sendo monitorado: {str(re)}")
                    # Para o observador que falhou
                    try:
                        observer.stop()
                        observer.join(timeout=1.0)
                    except:
                        pass
                    return False
                else:
                    logger.error(f"Erro RuntimeError ao monitorar {pdf_dir}: {str(re)}")
                    try:
                        observer.stop()
                        observer.join(timeout=1.0)
                    except:
                        pass
                    return False
                    
        except Exception as e:
            logger.error(f"Erro ao iniciar monitoramento para {pdf_dir}: {str(e)}")
            return False

    def stop(self):
        """Para o monitoramento com cleanup global"""
        global _GLOBAL_OBSERVERS, _GLOBAL_OBSERVERS_LOCK
        
        logger.info("Parando monitoramento de arquivos")
        
        # Para timer periódico
        if hasattr(self, '_periodic_timer'):
            try:
                self._periodic_timer.cancel()
                delattr(self, '_periodic_timer')
            except:
                pass
        
        # Para observadores locais (mas não os globais se estão sendo usados por outras instâncias)
        with _GLOBAL_OBSERVERS_LOCK:
            for observer in self.observers:
                try:
                    # Verifica se este observador ainda está em uso globalmente
                    is_global = any(obs == observer for obs in _GLOBAL_OBSERVERS.values())
                    
                    if not is_global and observer.is_alive():
                        observer.stop()
                        observer.join(timeout=1.0)
                except Exception as e:
                    logger.debug(f"Erro ao parar observador: {str(e)}")
        
        self.observers = []
        self._main_observer = None
        self._is_monitoring = False
    
    def _stop_internal(self):
        """Para todos os observadores internamente"""
        logger.info("Parando monitoramento de arquivos")
        
        for observer in self.observers:
            try:
                if observer.is_alive():
                    observer.stop()
                    observer.join(timeout=2.0)  # Timeout para evitar travamento
            except Exception as e:
                logger.warning(f"Erro ao parar observador: {str(e)}")
        
        self.observers = []
        self._main_observer = None
        self._monitored_paths.clear()

    def force_refresh_documents(self):
        """Força refresh completo dos documentos"""
        try:
            # Recarrega documentos do sistema de arquivos
            self._load_initial_documents()
            
            # Força verificação manual
            if hasattr(self, '_check_file_changes'):
                self._check_file_changes()
            
            # Notifica UI
            if self.on_documents_changed:
                self._safe_ui_callback(lambda: self.on_documents_changed(list(self.documents.values())))
            
            logger.info("Refresh forçado dos documentos concluído")
            
        except Exception as e:
            logger.error(f"Erro no refresh forçado: {str(e)}")

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
        Adiciona um documento ao monitor - VERSÃO CORRIGIDA PARA MACOS
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if self._is_duplicate_file(filepath):
                logger.info(f"Arquivo duplicado ignorado: {filepath}")
                return
            
            if self._add_document_internal(filepath):
                document = self.documents.get(filepath)
                auto_print_enabled = self.config.get("auto_print", False)

                if document and auto_print_enabled:
                    # Verifica se já foi processado recentemente
                    if self._should_process_auto_print(filepath):
                        self._process_auto_print(document)
                    else:
                        logger.debug(f"Auto-impressão: Arquivo {filepath} já foi processado recentemente, ignorando")
                elif document and not auto_print_enabled:
                    # CORREÇÃO MACOS: Força mostrar tela de documentos
                    self._show_documents_screen_enhanced()
    
    def _should_process_auto_print(self, filepath):
        """
        Verifica se um arquivo deve ser processado para auto-impressão
        Evita processamento duplicado em um curto período de tempo
        
        Args:
            filepath: Caminho do arquivo
            
        Returns:
            bool: True se deve processar, False caso contrário
        """
        import time
        
        with self.auto_print_lock:
            current_time = time.time()
            last_processed = self.auto_print_processed.get(filepath, 0)
            
            # CORREÇÃO: Aumenta o tempo de debounce para 15 segundos
            if current_time - last_processed < 15:
                return False
            
            # Marca como processado agora
            self.auto_print_processed[filepath] = current_time
            
            # Limpa entradas antigas (mais de 1 hora)
            old_entries = [path for path, timestamp in self.auto_print_processed.items() 
                        if current_time - timestamp > 3600]
            for path in old_entries:
                del self.auto_print_processed[path]
            
            return True

    def _force_all_document_lists_refresh(self):
        """Força refresh de todas as listas de documentos abertas"""
        try:
            import wx
            
            # Procura por todas as instâncias de DocumentListPanel
            for window in wx.GetTopLevelWindows():
                # Verifica se tem document_list_panel
                if hasattr(window, 'document_list_panel'):
                    panel = window.document_list_panel
                    if hasattr(panel, 'load_documents'):
                        wx.CallAfter(panel.load_documents)
                
                # Verifica se a própria janela é um DocumentListPanel
                if hasattr(window, 'load_documents') and 'DocumentList' in window.__class__.__name__:
                    wx.CallAfter(window.load_documents)
            
            # Procura recursivamente em painéis filhos
            def find_document_panels(parent):
                for child in parent.GetChildren():
                    if hasattr(child, 'load_documents') and 'DocumentList' in child.__class__.__name__:
                        wx.CallAfter(child.load_documents)
                    elif hasattr(child, 'GetChildren'):
                        find_document_panels(child)
            
            for window in wx.GetTopLevelWindows():
                find_document_panels(window)
                
        except Exception as e:
            logger.debug(f"Erro ao forçar refresh: {str(e)}")

    def _show_documents_screen_enhanced(self):
        """Mostra a tela de documentos - VERSÃO MELHORADA PARA MACOS"""
        import wx
        
        def show_documents():
            try:
                app = wx.GetApp()
                main_window = None
                
                # Procura a janela principal
                for window in wx.GetTopLevelWindows():
                    if hasattr(window, 'on_show_documents'):
                        main_window = window
                        break
                
                if not main_window:
                    logger.warning("Janela principal não encontrada")
                    return
                
                # CORREÇÃO MACOS: Sequência específica para mostrar janela
                if main_window.IsIconized():
                    main_window.Iconize(False)
                
                if not main_window.IsShown():
                    main_window.Show(True)
                
                # Força foco (macOS específico)
                main_window.Raise()
                main_window.RequestUserAttention()
                
                # Muda para tela de documentos
                main_window.on_show_documents()
                
                # CORREÇÃO MACOS: Força refresh múltiplas vezes
                wx.CallLater(50, self._force_all_document_lists_refresh)
                wx.CallLater(150, self._force_all_document_lists_refresh)
                wx.CallLater(300, self._force_all_document_lists_refresh)
                
            except Exception as e:
                logger.error(f"Erro ao mostrar tela de documentos: {str(e)}")
        
        # Executa na thread principal
        wx.CallAfter(show_documents)

    def _show_documents_screen(self):
        """Mostra a tela de documentos quando auto-impressão não está ativa - VERSÃO CORRIGIDA PARA MACOS"""
        import wx
        
        def show_documents():
            try:
                # CORREÇÃO MACOS: Força refresh antes de mostrar
                self._force_document_list_refresh()
                
                # Obtém todas as janelas abertas
                for window in wx.GetTopLevelWindows():
                    # Verifica se é a janela principal (MainScreen)
                    if hasattr(window, 'on_show_documents'):
                        # CORREÇÃO MACOS: Sequência específica para macOS
                        if window.IsIconized():
                            window.Iconize(False)
                        
                        if not window.IsShown():
                            window.Show(True)
                        
                        # CORREÇÃO MACOS: Força foco no macOS
                        window.Raise()
                        window.RequestUserAttention()
                        
                        # Muda para a tela de documentos
                        window.on_show_documents()
                        
                        # CORREÇÃO MACOS: Força refresh adicional após mostrar
                        wx.CallLater(100, self._force_document_list_refresh)
                        break
                        
            except Exception as e:
                logger.error(f"Erro ao mostrar tela de documentos: {str(e)}")
        
        # CORREÇÃO MACOS: Executa na thread principal da UI
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
            timestamp = int(time.time() * 1000)
            file_hash = self._get_file_hash(document.path) or "unknown"
            job_id = f"auto_{timestamp}_{file_hash[:8]}_{document.id}"
            
            # CORREÇÃO: Usa printer.id diretamente como na impressão manual
            job_info = PrintJobInfo(
                job_id=job_id,
                document_path=document.path,
                document_name=document.name,
                printer_name=printer.name,
                printer_id=printer.id,  # CORREÇÃO: Usa o ID da API diretamente
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
            
            # CORREÇÃO: Adiciona use_https=False como na impressão manual
            printer_instance = IPPPrinter(
                printer_ip=printer_ip,
                port=631,
                use_https=False  # Deixa detectar automaticamente
            )
            
            # CORREÇÃO: Adiciona callback para tratar adequadamente o resultado
            def auto_print_callback(job_id, status, data):
                """Callback para auto-impressão"""
                try:
                    if status == "complete":
                        logger.info(f"Auto-impressão concluída com sucesso: {job_info.document_name}")
                        logger.info(f"Páginas processadas: {data.get('successful_pages', 0)}/{data.get('total_pages', 0)}")
                    elif status == "canceled":
                        logger.warning(f"Auto-impressão cancelada: {job_info.document_name}")
                    elif status == "error":
                        error_msg = data.get("error", "Erro desconhecido") if isinstance(data, dict) else str(data)
                        logger.error(f"Erro na auto-impressão de '{job_info.document_name}': {error_msg}")
                    elif status == "progress":
                        # Log de progresso mais silencioso para auto-impressão
                        logger.debug(f"Auto-impressão progresso: {data}")
                except Exception as e:
                    logger.error(f"Erro no callback de auto-impressão: {e}")
            
            # Adiciona o trabalho à fila
            print_queue_manager = print_system.print_queue_manager
            print_queue_manager.add_job(
                job_info,
                printer_instance,
                auto_print_callback  # CORREÇÃO: Agora tem callback
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
        Adiciona um documento internamente sem disparar notificações - VERSÃO CORRIGIDA PARA MACOS
        
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
            
            # CORREÇÃO MACOS: Garante que o callback seja executado na thread principal da UI
            if self.on_documents_changed:
                self._safe_ui_callback(lambda: self.on_documents_changed(list(self.documents.values())))
                
            return True
        
        except Exception as e:
            logger.error(f"Erro ao adicionar documento {filepath}: {str(e)}")
            return False
    
    def _safe_ui_callback(self, callback):
        """Executa callback na UI de forma segura e robusta"""
        try:
            import wx
            
            def safe_execution():
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Erro no callback da UI: {str(e)}")
            
            # Verifica se wx está disponível e executa
            if wx.GetApp():
                wx.CallAfter(safe_execution)
            else:
                # Fallback: executa diretamente
                safe_execution()
                
        except Exception as e:
            logger.error(f"Erro ao agendar callback da UI: {str(e)}")

    def _force_document_list_refresh(self):
        """
        Força o refresh da lista de documentos se a tela estiver visível - ESPECÍFICO PARA MACOS
        """
        try:
            import wx
            
            # Procura por janelas abertas que tenham DocumentListPanel
            for window in wx.GetTopLevelWindows():
                if hasattr(window, 'document_list_panel'):
                    # Força o reload dos documentos
                    if hasattr(window.document_list_panel, 'load_documents'):
                        wx.CallAfter(window.document_list_panel.load_documents)
                    break
                    
        except Exception as e:
            logger.debug(f"Erro ao forçar refresh da lista: {str(e)}")

    def remove_document(self, filepath):
        """
        Remove um documento do monitor - VERSÃO CORRIGIDA PARA MACOS
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if filepath in self.documents:
                del self.documents[filepath]
                
                # CORREÇÃO: Remove também do controle de auto-impressão
                with self.auto_print_lock:
                    if filepath in self.auto_print_processed:
                        del self.auto_print_processed[filepath]
                
                # CORREÇÃO: Remove também do controle de hash
                with self.hash_lock:
                    if filepath in self.file_hashes:
                        del self.file_hashes[filepath]
                
                # CORREÇÃO MACOS: Usa callback seguro
                if self.on_documents_changed:
                    self._safe_ui_callback(lambda: self.on_documents_changed(list(self.documents.values())))

    
    def update_document(self, filepath):
        """
        Atualiza um documento no monitor - VERSÃO CORRIGIDA PARA MACOS
        
        Args:
            filepath: Caminho para o documento
        """
        with self.lock:
            if filepath in self.documents:
                if self._add_document_internal(filepath):
                    if self.on_documents_changed:
                        self._safe_ui_callback(lambda: self.on_documents_changed(list(self.documents.values())))

    
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
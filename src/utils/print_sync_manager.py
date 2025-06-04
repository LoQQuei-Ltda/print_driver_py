#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gerenciador de sincronização de trabalhos de impressão
"""

import logging
import threading
import time
from datetime import datetime, timedelta
import uuid

logger = logging.getLogger("PrintManagementSystem.Utils.PrintSyncManager")

class PrintSyncManager:
    """
    Gerenciador de sincronização de trabalhos de impressão com o servidor
    
    Esta classe é responsável por sincronizar os trabalhos de impressão com o
    servidor principal, garantindo que todos os trabalhos sejam enviados e
    gerenciando a limpeza de trabalhos antigos.
    """
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Retorna a instância singleton"""
        if cls._instance is None:
            cls._instance = PrintSyncManager()
        return cls._instance
    
    def __init__(self):
        """Inicializa o gerenciador de sincronização"""
        self.config = None
        self.api_client = None
        self.lock = threading.Lock()
        self.is_syncing = False
        self.sync_thread = None
    
    def initialize(self, config, api_client):
        """
        Inicializa o gerenciador com configuração e cliente API
        
        Args:
            config: Objeto de configuração
            api_client: Cliente da API
        """
        self.config = config
        self.api_client = api_client
    
    def sync_print_jobs(self, on_complete=None):
        """
        Sincroniza todos os trabalhos de impressão concluídos
        
        Args:
            on_complete: Callback a ser chamado após a sincronização
            
        Returns:
            bool: True se a sincronização foi iniciada
        """
        with self.lock:
            if self.is_syncing:
                logger.info("Sincronização já em andamento, ignorando nova solicitação")
                return False
            
            if not self.config or not self.api_client:
                logger.error("Gerenciador não inicializado")
                return False
            
            # Verifica se consegue acessar o histórico
            try:
                print_history = self.config.get("print_jobs", [])
                logger.debug(f"Verificação inicial: encontrados {len(print_history)} trabalhos no histórico")
            except Exception as e:
                logger.error(f"Erro ao acessar histórico: {e}")
                return False
                
            self.is_syncing = True
        
        # Inicia a sincronização em uma thread separada
        self.sync_thread = threading.Thread(
            target=self._sync_thread,
            args=(on_complete,),
            daemon=True
        )
        self.sync_thread.start()
        
        return True
    
    def _sync_thread(self, on_complete=None):
        """
        Thread de sincronização
        
        Args:
            on_complete: Callback a ser chamado após a sincronização
        """
        try:
            logger.info("Iniciando sincronização de trabalhos de impressão")
            
            # Obtém o histórico de impressão
            print_history = self.config.get("print_jobs", [])
            
            # Log do histórico para debug
            logger.debug(f"Histórico encontrado: {len(print_history)} trabalhos")
            for idx, job in enumerate(print_history):
                job_id = job.get('job_id', 'N/A')
                printer_id = job.get('printer_id', 'N/A')
                status = job.get('status', 'N/A')
                synced = job.get('synced', False)
                logger.info(f"Trabalho {idx+1}: ID={job_id}, Printer_ID={printer_id}, Status={status}, Synced={synced}")
                
                # CORREÇÃO: Log todos os campos disponíveis para debug
                if printer_id == 'N/A' or not printer_id:
                    logger.warning(f"Trabalho {job_id} sem printer_id! Campos disponíveis: {list(job.keys())}")
            
            # Filtra apenas os trabalhos concluídos e não sincronizados
            jobs_to_sync = [
                job for job in print_history
                if job.get("status") == "completed" and not job.get("synced", False)
            ]
            
            logger.info(f"Encontrados {len(jobs_to_sync)} trabalhos para sincronizar")
            
            if not jobs_to_sync:
                logger.info("Nenhum trabalho para sincronizar")
                self.is_syncing = False
                if on_complete:
                    on_complete(True)
                return
            
            # Sincroniza cada trabalho
            sync_success_count = 0
            sync_error_count = 0
            
            for job in jobs_to_sync:
                try:
                    # Mapeia os campos do histórico para os campos da API
                    job_id = job.get("job_id", "")
                    file_id = job_id  # job_id é usado como file_id (ID único do trabalho)
                    asset_id = job.get("printer_id", "")  # printer_id é o asset_id da API
                    completed_at = job.get("end_time")
                    pages = job.get("completed_pages", 0)
                    
                    logger.info(f"=== Processando trabalho para sincronização ===")
                    logger.info(f"Job ID: {job_id}")
                    logger.info(f"File ID (job_id): {file_id}")
                    logger.info(f"Asset ID (printer_id da API): {asset_id}")
                    logger.info(f"Data conclusão: {completed_at}")
                    logger.info(f"Páginas: {pages}")
                    
                    # Validações obrigatórias
                    if not job_id:
                        logger.warning(f"Trabalho sem job_id válido, pulando...")
                        job["synced"] = True
                        job["sync_error"] = "Job ID inválido"
                        sync_error_count += 1
                        continue
                    
                    if not asset_id:
                        logger.error(f"ERRO CRÍTICO: Trabalho {job_id} sem printer_id (asset_id)!")
                        logger.error(f"Este printer_id deveria vir da API. Campos do trabalho: {list(job.keys())}")
                        logger.error(f"Valores dos campos: {job}")
                        job["synced"] = True
                        job["sync_error"] = "Printer ID da API não encontrado"
                        sync_error_count += 1
                        continue
                    
                    if not completed_at:
                        logger.warning(f"Trabalho {job_id} sem data de conclusão (end_time)")
                        job["synced"] = True
                        job["sync_error"] = "Data de conclusão não encontrada"
                        sync_error_count += 1
                        continue
                    
                    if pages <= 0:
                        logger.warning(f"Trabalho {job_id} sem páginas válidas (completed_pages: {pages})")
                        job["synced"] = True
                        job["sync_error"] = "Número de páginas inválido"
                        sync_error_count += 1
                        continue
                    
                    logger.info(f"✓ Trabalho {job_id} válido para sincronização com printer_id da API: {asset_id}")
                    
                    # Sincroniza com o servidor
                    success = self.api_client.sync_print_job(
                        date=completed_at,
                        file_id=file_id,
                        asset_id=asset_id,
                        pages=int(pages)
                    )
                    
                    if success:
                        # Marca o trabalho como sincronizado
                        job["synced"] = True
                        job["synced_at"] = datetime.now().isoformat()
                        if "sync_error" in job:
                            del job["sync_error"]
                        
                        sync_success_count += 1
                        logger.info(f"✓ Trabalho {job_id} sincronizado com sucesso usando printer_id: {asset_id}")
                    else:
                        logger.error(f"✗ Falha na sincronização do trabalho {job_id}")
                        job["sync_error"] = "Falha na chamada da API"
                        sync_error_count += 1
                    
                except Exception as e:
                    logger.error(f"✗ Erro ao sincronizar trabalho {job.get('job_id')}: {str(e)}")
                    job["sync_error"] = str(e)
                    sync_error_count += 1
            
            # Salva o histórico atualizado
            self.config.set("print_jobs", print_history)
            
            logger.info(f"Sincronização concluída: {sync_success_count} sucessos, {sync_error_count} erros")
            
        except Exception as e:
            logger.error(f"Erro na thread de sincronização: {str(e)}")
            if on_complete:
                on_complete(False)
            return
        finally:
            self.is_syncing = False
            if on_complete:
                on_complete(True)

    
    # def _cleanup_old_jobs(self):
    #     """Limpa trabalhos antigos (mais de 72 horas)"""
    #     try:
    #         # Obtém o histórico - CORRIGIDO: usa a mesma chave que PrintQueueManager
    #         print_history = self.config.get("print_jobs", [])
            
    #         # Filtra apenas os trabalhos com mais de 72 horas
    #         now = datetime.now()
    #         cutoff = now - timedelta(hours=72)
            
    #         # Novos trabalhos (mantem apenas os recentes)
    #         new_history = []
            
    #         for job in print_history:
    #             try:
    #                 # Obtém a data de conclusão ou criação
    #                 job_date_str = job.get("end_time") or job.get("completed_at") or job.get("start_time") or job.get("created_at")
                    
    #                 if not job_date_str:
    #                     # Se não tiver data, mantém o trabalho (não sabemos quando foi criado)
    #                     new_history.append(job)
    #                     continue
                    
    #                 # Converte para datetime
    #                 job_date = datetime.fromisoformat(job_date_str.replace("Z", "+00:00"))
                    
    #                 # Verifica se o trabalho é recente
    #                 if job_date > cutoff:
    #                     new_history.append(job)
    #                 else:
    #                     logger.info(f"Removendo trabalho antigo: {job.get('job_id')} ({job_date_str})")
    #             except Exception as e:
    #                 # Se houver erro ao processar a data, mantém o trabalho
    #                 logger.error(f"Erro ao processar data do trabalho: {str(e)}")
    #                 new_history.append(job)
            
    #         # Atualiza o histórico - CORRIGIDO: usa a mesma chave que PrintQueueManager
    #         if len(new_history) != len(print_history):
    #             logger.info(f"Removidos {len(print_history) - len(new_history)} trabalhos antigos")
    #             self.config.set("print_jobs", new_history)
            
    #     except Exception as e:
    #         logger.error(f"Erro ao limpar trabalhos antigos: {str(e)}")
    
    def sync_and_wait(self, timeout=30):
        """
        Inicia a sincronização e aguarda a conclusão
        
        Args:
            timeout: Tempo máximo de espera em segundos
            
        Returns:
            bool: True se a sincronização foi concluída com sucesso
        """
        if self.is_syncing:
            logger.info("Sincronização já em andamento")
            return False
        
        sync_complete = threading.Event()
        sync_result = [False]  # Lista para armazenar o resultado
        
        def on_sync_complete(success):
            sync_result[0] = success
            sync_complete.set()
        
        # Inicia a sincronização
        if not self.sync_print_jobs(on_sync_complete):
            logger.error("Falha ao iniciar sincronização")
            return False
        
        # Aguarda a conclusão
        if not sync_complete.wait(timeout):
            logger.warning(f"Timeout na sincronização após {timeout} segundos")
            return False
        
        # Retorna o resultado
        return sync_result[0]
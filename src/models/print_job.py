#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modelo para trabalhos de impressão - VERSÃO CORRIGIDA
"""

import os
import uuid
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any

class PrintJobStatus(Enum):
    """Status possíveis para um trabalho de impressão"""
    PENDING = "pending"     # Aguardando processamento
    PROCESSING = "processing"  # Sendo processado
    COMPLETED = "completed"    # Concluído com sucesso
    FAILED = "failed"       # Falhou
    CANCELED = "canceled"   # Cancelado pelo usuário

@dataclass
class PrintJob:
    """Modelo de trabalho de impressão"""
    
    job_id: str
    document_path: str
    document_name: str
    printer_name: str
    printer_id: str
    printer_ip: str
    status: PrintJobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_pages: int = 0
    completed_pages: int = 0
    options: Dict[str, Any] = None
    error_message: Optional[str] = None
    
    @classmethod
    def create(cls, document_path, document_name, printer_name, printer_id, printer_ip, options=None):
        """
        Cria um novo trabalho de impressão
        
        Args:
            document_path: Caminho do documento
            document_name: Nome do documento
            printer_name: Nome da impressora
            printer_id: ID da impressora
            printer_ip: IP da impressora
            options: Opções de impressão
            
        Returns:
            PrintJob: Novo trabalho de impressão
        """
        job_id = f"job_{str(uuid.uuid4())[:8]}"
        
        return cls(
            job_id=job_id,
            document_path=document_path,
            document_name=document_name,
            printer_name=printer_name,
            printer_id=printer_id,
            printer_ip=printer_ip,
            status=PrintJobStatus.PENDING,
            created_at=datetime.now(),
            options=options or {}
        )
    
    def to_dict(self):
        """Converte para dicionário para armazenamento - VERSÃO CORRIGIDA"""
        return {
            "job_id": self.job_id,
            "document_path": self.document_path,
            "document_name": self.document_name,
            "printer_name": self.printer_name,
            "printer_id": self.printer_id,
            "printer_ip": self.printer_ip,
            "status": self.status.value,
            # === CORREÇÃO: Salva em ambos os formatos para compatibilidade ===
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            # Formato antigo para compatibilidade
            "start_time": self.created_at.isoformat() if self.created_at else None,
            "end_time": self.completed_at.isoformat() if self.completed_at else None,
            "total_pages": self.total_pages,
            "completed_pages": self.completed_pages,
            "options": self.options,
            "error_message": self.error_message
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Cria um trabalho de impressão a partir de um dicionário - VERSÃO CORRIGIDA
        
        Args:
            data: Dicionário com dados do trabalho
            
        Returns:
            PrintJob: Trabalho de impressão
        """
        # === CORREÇÃO: Mapeia corretamente os campos de data do config ===
        
        # Para created_at: usa 'created_at' primeiro, depois 'start_time'
        created_at = None
        date_field = data.get("created_at") or data.get("start_time")
        if date_field:
            try:
                created_at = datetime.fromisoformat(date_field)
            except (ValueError, TypeError):
                created_at = datetime(2024, 1, 1, 0, 0, 0)
        else:
            created_at = datetime(2024, 1, 1, 0, 0, 0)
        
        # Para started_at: usa 'started_at' primeiro, depois 'start_time' se status é processing/completed/failed/canceled
        started_at = None
        started_field = data.get("started_at") or data.get("start_time")
        status_str = data.get("status", "pending")
        if started_field and status_str in ["processing", "completed", "failed", "canceled"]:
            try:
                started_at = datetime.fromisoformat(started_field)
            except (ValueError, TypeError):
                started_at = None
        
        # Para completed_at: usa 'completed_at' primeiro, depois 'end_time' se status é completed/failed/canceled
        completed_at = None
        completed_field = data.get("completed_at") or data.get("end_time")
        if completed_field and status_str in ["completed", "failed", "canceled"]:
            try:
                completed_at = datetime.fromisoformat(completed_field)
            except (ValueError, TypeError):
                completed_at = None
        
        # Converte string de status para enum
        status_str = data.get("status", "pending")
        status = None
        for status_enum in PrintJobStatus:
            if status_enum.value == status_str:
                status = status_enum
                break
        
        if not status:
            status = PrintJobStatus.PENDING
        
        return cls(
            job_id=data.get("job_id", ""),
            document_path=data.get("document_path", ""),
            document_name=data.get("document_name", ""),
            printer_name=data.get("printer_name", ""),
            printer_id=data.get("printer_id", ""),
            printer_ip=data.get("printer_ip", ""),
            status=status,
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            total_pages=data.get("total_pages", 0),
            completed_pages=data.get("completed_pages", 0),
            options=data.get("options", {}),
            error_message=data.get("error_message")
        )
    
    def is_active(self):
        """Verifica se o trabalho está ativo (pendente ou em processamento)"""
        return self.status in [PrintJobStatus.PENDING, PrintJobStatus.PROCESSING]
    
    def set_processing(self):
        """Define o trabalho como em processamento"""
        self.status = PrintJobStatus.PROCESSING
        self.started_at = datetime.now()
    
    def set_completed(self, total_pages, completed_pages):
        """Define o trabalho como concluído"""
        self.status = PrintJobStatus.COMPLETED
        self.completed_at = datetime.now()
        self.total_pages = total_pages
        self.completed_pages = completed_pages
    
    def set_failed(self, error_message):
        """Define o trabalho como falho"""
        self.status = PrintJobStatus.FAILED
        self.completed_at = datetime.now()
        self.error_message = error_message
    
    def set_canceled(self):
        """Define o trabalho como cancelado"""
        self.status = PrintJobStatus.CANCELED
        self.completed_at = datetime.now()
    
    def get_progress_percentage(self):
        """Obtém o percentual de progresso"""
        if self.total_pages <= 0:
            return 0
        
        return int((self.completed_pages / self.total_pages) * 100)
    
    def get_elapsed_time(self):
        """Obtém o tempo decorrido em segundos"""
        if not self.started_at:
            return 0
        
        end_time = self.completed_at if self.completed_at else datetime.now()
        return (end_time - self.started_at).total_seconds()
    
    def get_formatted_elapsed_time(self):
        """Obtém o tempo decorrido formatado"""
        seconds = self.get_elapsed_time()
        
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds / 60)
            seconds = int(seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(seconds / 3600)
            minutes = int((seconds % 3600) / 60)
            return f"{hours}h {minutes}m"
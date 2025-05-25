#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Servidor API para o sistema de gerenciamento de impressão

Este módulo implementa um servidor HTTP que expõe uma API REST para interagir
com o sistema de gerenciamento de impressão. Ele permite listar documentos e impressoras,
enviar documentos para impressão e monitorar a fila de impressão.
"""

import os
import json
import uuid
import logging
import shutil
import socket
import threading
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.serving import make_server

# Importa os módulos do sistema de gerenciamento de impressão
from src.models.document import Document
from src.models.printer import Printer
from src.config import AppConfig
from src.utils.file_monitor import FileMonitor
from src.utils.print_system import PrintSystem, PrintOptions, ColorMode, Duplex, Quality, PrintQueueManager
from src.utils.pdf import PDFUtils

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PrintManagementSystem.API")

class PrintServerAPI:
    """Classe que implementa o servidor API para o sistema de gerenciamento de impressão"""
    
    def __init__(self, app_config):
        """
        Inicializa o servidor API
        
        Args:
            app_config: Configuração da aplicação
        """
        self.app_config = app_config
        self.flask_app = Flask(__name__)
        CORS(self.flask_app)  # Permite requisições de origem cruzada
        
        # Diretório PDF é o mesmo usado pelo file_monitor
        self.pdf_dir = app_config.pdf_dir
        os.makedirs(self.pdf_dir, exist_ok=True)
        logger.info(f"Usando diretório de documentos: {self.pdf_dir}")
        
        # Inicializa o monitor de arquivos para detectar alterações
        self.file_monitor = FileMonitor(app_config)
        
        # Inicializa o sistema de impressão
        self.print_system = PrintSystem(app_config)
        
        # Servidor HTTP
        self.server = None
        self.is_running = False
        self.server_thread = None
        self.port = None
        
        # Configura as rotas da API
        self._configure_routes()
    
    def _configure_routes(self):
        """Configura as rotas da API"""
        # Status
        self.flask_app.add_url_rule('/api/status', 'get_status', self.get_status, methods=['GET'])
        
        # Documentos
        self.flask_app.add_url_rule('/api/documents', 'list_documents', self.list_documents, methods=['GET'])
        self.flask_app.add_url_rule('/api/documents', 'upload_document', self.upload_document, methods=['POST'])
        self.flask_app.add_url_rule('/api/documents/<document_id>', 'get_document', self.get_document, methods=['GET'])
        self.flask_app.add_url_rule('/api/documents/<document_id>/download', 'download_document', self.download_document, methods=['GET'])
        self.flask_app.add_url_rule('/api/documents/<document_id>', 'delete_document', self.delete_document, methods=['DELETE'])
        
        # Impressoras
        self.flask_app.add_url_rule('/api/printers', 'list_printers', self.list_printers, methods=['GET'])
        self.flask_app.add_url_rule('/api/printers/<printer_id>', 'get_printer', self.get_printer, methods=['GET'])
        
        # Impressão
        self.flask_app.add_url_rule('/api/print', 'print_document', self.print_document, methods=['POST'])
        self.flask_app.add_url_rule('/api/print/queue', 'get_print_queue', self.get_print_queue, methods=['GET'])
        self.flask_app.add_url_rule('/api/print/job/<job_id>', 'get_print_job', self.get_print_job, methods=['GET'])
        self.flask_app.add_url_rule('/api/print/cancel/<job_id>', 'cancel_print_job', self.cancel_print_job, methods=['POST'])
    
    def get_documents(self):
        """
        Obtém a lista de documentos disponíveis
        
        Returns:
            list: Lista de documentos
        """
        try:
            # Usa o file_monitor para obter documentos, garantindo consistência com a aplicação
            if hasattr(self.file_monitor, '_load_initial_documents'):
                self.file_monitor._load_initial_documents()
            return self.file_monitor.get_documents()
        except Exception as e:
            logger.error(f"Erro ao obter documentos: {e}")
            
            # Fallback: lista documentos diretamente do diretório
            documents = []
            try:
                for filename in os.listdir(self.pdf_dir):
                    if filename.lower().endswith(".pdf"):
                        file_path = os.path.join(self.pdf_dir, filename)
                        document = Document.from_file(file_path)
                        
                        # Adiciona contagem de páginas
                        try:
                            pdf_info = PDFUtils.get_pdf_info(file_path)
                            document.pages = pdf_info.get("pages", 0)
                        except Exception as pdf_err:
                            logger.warning(f"Erro ao obter informações do PDF {file_path}: {pdf_err}")
                        
                        documents.append(document)
                return documents
            except Exception as dir_err:
                logger.error(f"Erro ao listar diretório: {dir_err}")
                return []
    
    # Rotas da API
    def get_status(self):
        """Retorna o status do servidor"""
        return jsonify({
            "status": "online",
            "timestamp": datetime.now().isoformat(),
            "port": self.port
        })
    
    def list_documents(self):
        """Lista todos os documentos disponíveis para impressão"""
        try:
            documents = self.get_documents()
            return jsonify({
                "success": True,
                "documents": [doc.to_dict() for doc in documents]
            })
        except Exception as e:
            logger.error(f"Erro ao listar documentos: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def upload_document(self):
        """Recebe um documento para impressão"""
        try:
            if 'file' not in request.files:
                return jsonify({
                    "success": False,
                    "error": "Nenhum arquivo enviado"
                }), 400
            
            file = request.files['file']
            if file.filename == '':
                return jsonify({
                    "success": False,
                    "error": "Nome de arquivo vazio"
                }), 400
            
            # Garante que o arquivo é um PDF
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({
                    "success": False,
                    "error": "Apenas arquivos PDF são aceitos"
                }), 400
            
            # Gera um nome único para o arquivo
            unique_filename = f"{uuid.uuid4()}_{file.filename}"
            file_path = os.path.join(self.pdf_dir, unique_filename)
            
            # Salva o arquivo
            file.save(file_path)
            
            # Cria o documento
            document = Document.from_file(file_path)
            
            # Adiciona contagem de páginas
            try:
                pdf_info = PDFUtils.get_pdf_info(file_path)
                document.pages = pdf_info.get("pages", 0)
            except Exception as pdf_err:
                logger.warning(f"Erro ao obter informações do PDF {file_path}: {pdf_err}")
            
            # Notifica o monitor de arquivos (apenas se estiver ativo)
            try:
                if hasattr(self.file_monitor, 'add_document'):
                    self.file_monitor.add_document(file_path)
            except Exception as fm_err:
                logger.warning(f"Erro ao notificar monitor de arquivos: {fm_err}")
            
            return jsonify({
                "success": True,
                "document": document.to_dict(),
                "message": "Documento recebido com sucesso"
            })
        except Exception as e:
            logger.error(f"Erro ao receber documento: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def get_document(self, document_id):
        """Obtém um documento específico"""
        try:
            documents = self.get_documents()
            document = None
            
            for doc in documents:
                if doc.id == document_id:
                    document = doc
                    break
            
            if not document:
                return jsonify({
                    "success": False,
                    "error": f"Documento não encontrado: {document_id}"
                }), 404
            
            return jsonify({
                "success": True,
                "document": document.to_dict()
            })
        except Exception as e:
            logger.error(f"Erro ao obter documento: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def download_document(self, document_id):
        """Baixa um documento específico"""
        try:
            documents = self.get_documents()
            document = None
            
            for doc in documents:
                if doc.id == document_id:
                    document = doc
                    break
            
            if not document:
                return jsonify({
                    "success": False,
                    "error": f"Documento não encontrado: {document_id}"
                }), 404
            
            return send_from_directory(
                os.path.dirname(document.path),
                os.path.basename(document.path),
                as_attachment=True,
                download_name=document.name
            )
        except Exception as e:
            logger.error(f"Erro ao baixar documento: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def delete_document(self, document_id):
        """Exclui um documento"""
        try:
            documents = self.get_documents()
            document = None
            
            for doc in documents:
                if doc.id == document_id:
                    document = doc
                    break
            
            if not document:
                return jsonify({
                    "success": False,
                    "error": f"Documento não encontrado: {document_id}"
                }), 404
            
            # Exclui o arquivo
            if os.path.exists(document.path):
                os.remove(document.path)
                
                # Notifica o monitor de arquivos (apenas se estiver ativo)
                try:
                    if hasattr(self.file_monitor, 'remove_document'):
                        self.file_monitor.remove_document(document.path)
                except Exception as fm_err:
                    logger.warning(f"Erro ao notificar monitor de arquivos sobre exclusão: {fm_err}")
                    
                return jsonify({
                    "success": True,
                    "message": f"Documento excluído: {document.name}"
                })
            else:
                return jsonify({
                    "success": False,
                    "error": f"Arquivo não encontrado: {document.path}"
                }), 404
        except Exception as e:
            logger.error(f"Erro ao excluir documento: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def list_printers(self):
        """Lista todas as impressoras disponíveis"""
        try:
            # Obtém as impressoras da configuração
            printers_data = self.app_config.get_printers()
            
            # Converte para objetos Printer
            printers = [Printer(printer_data) for printer_data in printers_data]
            
            return jsonify({
                "success": True,
                "printers": [printer.to_dict() for printer in printers]
            })
        except Exception as e:
            logger.error(f"Erro ao listar impressoras: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def get_printer(self, printer_id):
        """Obtém uma impressora específica"""
        try:
            printers_data = self.app_config.get_printers()
            printer_data = None
            
            for p_data in printers_data:
                if p_data.get('id') == printer_id:
                    printer_data = p_data
                    break
            
            if not printer_data:
                return jsonify({
                    "success": False,
                    "error": f"Impressora não encontrada: {printer_id}"
                }), 404
            
            printer = Printer(printer_data)
            
            return jsonify({
                "success": True,
                "printer": printer.to_dict()
            })
        except Exception as e:
            logger.error(f"Erro ao obter impressora: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def print_document(self):
        """Inicia a impressão de um documento"""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    "success": False,
                    "error": "Dados não fornecidos"
                }), 400
            
            # Valida os dados necessários
            required_fields = ['document_id', 'printer_id']
            for field in required_fields:
                if field not in data:
                    return jsonify({
                        "success": False,
                        "error": f"Campo obrigatório ausente: {field}"
                    }), 400
            
            # Obtém o documento
            document_id = data['document_id']
            documents = self.get_documents()
            document = None
            
            for doc in documents:
                if doc.id == document_id:
                    document = doc
                    break
            
            if not document:
                return jsonify({
                    "success": False,
                    "error": f"Documento não encontrado: {document_id}"
                }), 404
            
            # Obtém a impressora
            printer_id = data['printer_id']
            printers_data = self.app_config.get_printers()
            printer_data = None
            
            for p_data in printers_data:
                if p_data.get('id') == printer_id:
                    printer_data = p_data
                    break
            
            if not printer_data:
                return jsonify({
                    "success": False,
                    "error": f"Impressora não encontrada: {printer_id}"
                }), 404
            
            printer = Printer(printer_data)
            
            # Configura as opções de impressão
            options = PrintOptions()
            
            if 'color_mode' in data:
                color_mode = data['color_mode']
                if color_mode == "color":
                    options.color_mode = ColorMode.COLORIDO
                elif color_mode == "monochrome":
                    options.color_mode = ColorMode.MONOCROMO
                else:
                    options.color_mode = ColorMode.AUTO
            
            if 'duplex' in data:
                duplex = data['duplex']
                if duplex == "two-sided-long-edge":
                    options.duplex = Duplex.DUPLEX_LONGO
                elif duplex == "two-sided-short-edge":
                    options.duplex = Duplex.DUPLEX_CURTO
                else:
                    options.duplex = Duplex.SIMPLES
            
            if 'quality' in data:
                quality = data['quality']
                if quality == "draft":
                    options.quality = Quality.RASCUNHO
                elif quality == "high":
                    options.quality = Quality.ALTA
                else:
                    options.quality = Quality.NORMAL
            
            if 'copies' in data:
                options.copies = int(data['copies'])
            
            if 'orientation' in data:
                options.orientation = data['orientation']
            
            if 'paper_size' in data:
                options.paper_size = data['paper_size']
            
            if 'dpi' in data:
                options.dpi = int(data['dpi'])
            
            # Cria um ID único para o trabalho
            job_id = f"job_{int(datetime.now().timestamp())}_{document.id}"
            
            # Cria instância da impressora IPP
            from src.utils.print_system import IPPPrinter
            printer_ip = printer.ip
            if not printer_ip:
                return jsonify({
                    "success": False,
                    "error": f"A impressora não possui um endereço IP configurado: {printer.name}"
                }), 400
            
            printer_instance = IPPPrinter(
                printer_ip=printer_ip,
                port=631
            )
            
            # Cria objeto de informações do trabalho
            from src.utils.print_system import PrintJobInfo
            job_info = PrintJobInfo(
                job_id=job_id,
                document_path=document.path,
                document_name=document.name,
                printer_name=printer.name,
                printer_id=printer.id,
                printer_ip=printer.ip,
                options=options,
                start_time=datetime.now(),
                status="pending"
            )
            
            # Define o callback para atualização de progresso
            def print_callback(job_id, status, data):
                """Callback para atualização de progresso de impressão"""
                logger.info(f"Progresso de impressão: {job_id}, {status}, {data}")
            
            # Adiciona o trabalho à fila
            queue_manager = PrintQueueManager.get_instance()
            queue_manager.set_config(self.app_config)
            queue_manager.add_job(
                job_info,
                printer_instance,
                print_callback
            )
            
            return jsonify({
                "success": True,
                "job_id": job_id,
                "message": "Trabalho de impressão adicionado à fila"
            })
        except Exception as e:
            logger.error(f"Erro ao iniciar impressão: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def get_print_queue(self):
        """Obtém a fila de impressão atual"""
        try:
            queue_manager = PrintQueueManager.get_instance()
            queue_manager.set_config(self.app_config)
            
            # Obtém o histórico de trabalhos
            job_history = queue_manager.get_job_history()
            
            # Obtém o trabalho atual em processamento
            current_job = queue_manager.get_current_job()
            current_job_info = None
            
            if current_job:
                current_job_info = current_job["info"].to_dict()
            
            return jsonify({
                "success": True,
                "queue_size": queue_manager.get_queue_size(),
                "current_job": current_job_info,
                "job_history": job_history
            })
        except Exception as e:
            logger.error(f"Erro ao obter fila de impressão: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def get_print_job(self, job_id):
        """Obtém informações de um trabalho de impressão específico"""
        try:
            queue_manager = PrintQueueManager.get_instance()
            queue_manager.set_config(self.app_config)
            
            # Obtém o histórico de trabalhos
            job_history = queue_manager.get_job_history()
            
            # Procura o trabalho pelo ID
            for job in job_history:
                if job.get("job_id") == job_id:
                    return jsonify({
                        "success": True,
                        "job": job
                    })
            
            return jsonify({
                "success": False,
                "error": f"Trabalho não encontrado: {job_id}"
            }), 404
        except Exception as e:
            logger.error(f"Erro ao obter trabalho: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def cancel_print_job(self, job_id):
        """Cancela um trabalho de impressão"""
        try:
            queue_manager = PrintQueueManager.get_instance()
            queue_manager.set_config(self.app_config)
            
            # Obtém o histórico de trabalhos
            job_history = queue_manager.get_job_history()
            
            # Procura o trabalho pelo ID
            job_found = False
            for job in job_history:
                if job.get("job_id") == job_id:
                    job_found = True
                    
                    # Verifica se já está concluído ou cancelado
                    status = job.get("status")
                    if status in ["completed", "canceled"]:
                        return jsonify({
                            "success": False,
                            "error": f"Trabalho já {status}"
                        }), 400
                    
                    # Atualiza o status para cancelado
                    job["status"] = "canceled"
                    if "end_time" not in job or not job["end_time"]:
                        job["end_time"] = datetime.now().isoformat()
                    
                    # Atualiza o histórico
                    queue_manager._update_history(job)
                    
                    return jsonify({
                        "success": True,
                        "message": f"Trabalho cancelado: {job_id}"
                    })
            
            if not job_found:
                return jsonify({
                    "success": False,
                    "error": f"Trabalho não encontrado: {job_id}"
                }), 404
        except Exception as e:
            logger.error(f"Erro ao cancelar trabalho: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    def start(self, initial_port=50000, max_attempts=100):
        """
        Inicia o servidor na porta especificada ou na próxima disponível
        
        Args:
            initial_port (int): Porta inicial para tentar
            max_attempts (int): Número máximo de tentativas de porta
            
        Returns:
            int: Porta em que o servidor foi iniciado ou None se falhou
        """
        if self.is_running:
            logger.warning("Servidor já está em execução")
            return self.port
        
        # Inicia o monitor de arquivos
        self.file_monitor.start()
        
        # Inicia o gerenciador de fila de impressão
        queue_manager = PrintQueueManager.get_instance()
        queue_manager.set_config(self.app_config)
        queue_manager.start()
        
        # Procura por uma porta disponível
        port = self._find_available_port(initial_port, max_attempts)
        
        if port is None:
            logger.error("Não foi possível encontrar uma porta disponível")
            return None
        
        self.port = port
        
        # Salva a porta na configuração
        self.app_config.set("api_port", port)
        
        # Cria o servidor HTTP
        self.server = make_server('0.0.0.0', port, self.flask_app)
        self.is_running = True
        
        # Inicia o servidor em uma thread separada
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        
        logger.info(f"Servidor API iniciado na porta {port}")
        logger.info(f"Pasta de documentos: {self.pdf_dir}")
        
        return port
    
    def stop(self):
        """Para o servidor"""
        if not self.is_running:
            return
        
        logger.info("Parando servidor API...")
        
        try:
            # Para o servidor HTTP
            if self.server:
                self.server.shutdown()
                self.server = None
            
            # Para o monitor de arquivos
            if self.file_monitor:
                self.file_monitor.stop()
            
            # Para o sistema de impressão
            if self.print_system:
                self.print_system.shutdown()
            
            self.is_running = False
            self.server_thread = None
            
            logger.info("Servidor API parado com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao parar servidor API: {e}")
    
    def _is_port_in_use(self, port):
        """
        Verifica se uma porta está em uso
        
        Args:
            port (int): Porta a verificar
            
        Returns:
            bool: True se a porta estiver em uso
        """
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(('localhost', port)) == 0
    
    def _find_available_port(self, initial_port, max_attempts):
        """
        Encontra uma porta disponível
        
        Args:
            initial_port (int): Porta inicial para tentar
            max_attempts (int): Número máximo de tentativas
            
        Returns:
            int: Porta disponível ou None se não encontrou
        """
        port = initial_port
        
        for _ in range(max_attempts):
            if not self._is_port_in_use(port):
                return port
            port += 1
        
        return None

def start_server(app_config, initial_port=50000):
    """
    Inicia o servidor API
    
    Args:
        app_config: Configuração da aplicação
        initial_port (int): Porta inicial para tentar
        
    Returns:
        PrintServerAPI: Instância do servidor ou None se falhou
    """
    try:
        # Cria o servidor
        server = PrintServerAPI(app_config)
        
        # Inicia o servidor
        port = server.start(initial_port)
        
        if port is None:
            logger.error("Falha ao iniciar servidor API")
            return None
        
        logger.info(f"Servidor API iniciado com sucesso na porta {port}")
        return server
        
    except Exception as e:
        logger.error(f"Erro ao iniciar servidor API: {e}")
        return None
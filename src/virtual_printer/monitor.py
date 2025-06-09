#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Monitor integrado para impressora virtual
"""

import os
import logging
import ctypes
import psutil
import socket
import subprocess
import time
from datetime import datetime
import platform

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
        
        # Sistema
        self.system = platform.system()
        
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
        """Diagnostica o sistema e registra informações detalhadas"""
               
        logger.info("=" * 50)
        logger.info("=== DIAGNÓSTICO COMPLETO DO SISTEMA ===")
        logger.info("=" * 50)
        
        # === INFORMAÇÕES BÁSICAS DO SISTEMA ===
        logger.info("\n[SISTEMA OPERACIONAL]")
        logger.info(f"Sistema: {platform.system()} {platform.release()}")
        logger.info(f"Versão: {platform.version()}")
        logger.info(f"Arquitetura: {platform.machine()}")
        logger.info(f"Processador: {platform.processor()}")
        logger.info(f"Nome da máquina: {platform.node()}")
        logger.info(f"Python: {platform.python_version()}")
        logger.info(f"Data/Hora atual: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # === INFORMAÇÕES DE HARDWARE ===
        try:
            logger.info("\n[HARDWARE]")
            # CPU
            cpu_count = psutil.cpu_count(logical=False)
            cpu_count_logical = psutil.cpu_count(logical=True)
            cpu_freq = psutil.cpu_freq()
            logger.info(f"CPU físicos: {cpu_count}")
            logger.info(f"CPU lógicos: {cpu_count_logical}")
            if cpu_freq:
                logger.info(f"Frequência CPU: {cpu_freq.current:.2f} MHz (max: {cpu_freq.max:.2f})")
            
            # Uso atual da CPU
            cpu_percent = psutil.cpu_percent(interval=1)
            logger.info(f"Uso atual da CPU: {cpu_percent}%")
            
            # Memória
            memory = psutil.virtual_memory()
            logger.info(f"Memória total: {memory.total / (1024**3):.2f} GB")
            logger.info(f"Memória disponível: {memory.available / (1024**3):.2f} GB")
            logger.info(f"Uso de memória: {memory.percent}%")
            
            # Disco
            logger.info("\n[ARMAZENAMENTO]")
            for partition in psutil.disk_partitions():
                try:
                    partition_usage = psutil.disk_usage(partition.mountpoint)
                    logger.info(f"Disco {partition.device}: {partition_usage.total / (1024**3):.2f} GB total, "
                            f"{partition_usage.free / (1024**3):.2f} GB livre ({partition_usage.percent}% usado)")
                except PermissionError:
                    logger.info(f"Disco {partition.device}: Sem permissão para acessar")
        except Exception as e:
            logger.error(f"Erro ao obter informações de hardware: {e}")
        
        # === INFORMAÇÕES DE REDE ===
        try:
            logger.info("\n[REDE]")
            # Interfaces de rede
            interfaces = psutil.net_if_addrs()
            for interface_name, interface_addresses in interfaces.items():
                logger.info(f"Interface: {interface_name}")
                for address in interface_addresses:
                    if address.family == socket.AF_INET:
                        logger.info(f"  IPv4: {address.address}")
                    elif address.family == socket.AF_INET6:
                        logger.info(f"  IPv6: {address.address}")
                    elif address.family == psutil.AF_LINK:
                        logger.info(f"  MAC: {address.address}")
            
            # Estatísticas de rede
            net_io = psutil.net_io_counters()
            logger.info(f"Bytes enviados: {net_io.bytes_sent / (1024**2):.2f} MB")
            logger.info(f"Bytes recebidos: {net_io.bytes_recv / (1024**2):.2f} MB")
            
            # Conexões ativas
            connections = psutil.net_connections()
            active_connections = [conn for conn in connections if conn.status == 'ESTABLISHED']
            logger.info(f"Conexões ativas: {len(active_connections)}")
            
        except Exception as e:
            logger.error(f"Erro ao obter informações de rede: {e}")
        
        # === INFORMAÇÕES ESPECÍFICAS DO WINDOWS ===
        if platform.system() == 'Windows':
            logger.info("\n[WINDOWS]")
            
            # Privilégios de administrador
            try:
                is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
                logger.info(f"Executando como administrador: {is_admin}")
            except:
                logger.info("Não foi possível verificar privilégios de administrador")
            
            # Versão detalhada do Windows
            try:
                result = run_hidden(['wmic', 'os', 'get', 'Caption,Version,BuildNumber'], timeout=10)
                if result.returncode == 0:
                    logger.info("Versão detalhada do Windows:")
                    for line in result.stdout.strip().split('\n')[1:]:
                        if line.strip():
                            logger.info(f"  {line.strip()}")
            except:
                pass
            
            # Informações do computador
            try:
                result = run_hidden(['wmic', 'computersystem', 'get', 'Manufacturer,Model,TotalPhysicalMemory'], timeout=10)
                if result.returncode == 0:
                    logger.info("Informações do computador:")
                    for line in result.stdout.strip().split('\n')[1:]:
                        if line.strip():
                            logger.info(f"  {line.strip()}")
            except:
                pass
            
            # Firewall
            try:
                result = run_hidden(['netsh', 'advfirewall', 'show', 'currentprofile'], timeout=5)
                if result.returncode == 0:
                    if 'State                                 ON' in result.stdout:
                        logger.warning("Firewall do Windows está ATIVO - pode bloquear conexões")
                    else:
                        logger.info("Firewall do Windows está desativado")
            except:
                pass
            
            # Windows Defender
            try:
                result = run_hidden(['powershell', '-Command', 'Get-MpComputerStatus | Select-Object AntivirusEnabled,RealTimeProtectionEnabled'], timeout=10)
                if result.returncode == 0:
                    logger.info("Status do Windows Defender:")
                    logger.info(f"  {result.stdout.strip()}")
            except:
                pass
            
            # Serviços importantes
            try:
                important_services = ['Themes', 'AudioSrv', 'Spooler', 'BITS', 'EventLog']
                for service_name in important_services:
                    result = run_hidden(['sc', 'query', service_name], timeout=5)
                    if result.returncode == 0:
                        if 'RUNNING' in result.stdout:
                            logger.info(f"Serviço {service_name}: ATIVO")
                        else:
                            logger.warning(f"Serviço {service_name}: INATIVO")
            except:
                pass
            
            # Configurações de energia
            try:
                result = run_hidden(['powercfg', '/query'], timeout=10)
                if result.returncode == 0:
                    lines = result.stdout.split('\n')
                    for line in lines[:10]:  # Primeiras 10 linhas
                        if 'Power Scheme GUID' in line or 'GUID' in line:
                            logger.info(f"Energia: {line.strip()}")
            except:
                pass
                
        # === CONFIGURAÇÕES DE REDE AVANÇADAS ===
        try:
            logger.info("\n[CONFIGURAÇÕES DE REDE]")
            
            # DNS
            if platform.system() == 'Windows':
                result = run_hidden(['nslookup', 'google.com'], timeout=10)
                if result.returncode == 0:
                    dns_lines = [line for line in result.stdout.split('\n') if 'Server:' in line]
                    for line in dns_lines:
                        logger.info(f"DNS: {line.strip()}")
            
            # Gateway padrão
            if platform.system() == 'Windows':
                result = run_hidden(['ipconfig'], timeout=10)
                if result.returncode == 0:
                    gateway_lines = [line for line in result.stdout.split('\n') if 'Gateway' in line and ':' in line]
                    for line in gateway_lines:
                        logger.info(f"Gateway: {line.strip()}")
            
            # Teste de conectividade
            try:
                response_time = subprocess.run(['ping', '-n', '1', 'google.com'], 
                                            capture_output=True, text=True, timeout=5)
                if response_time.returncode == 0:
                    logger.info("Conectividade com internet: OK")
                else:
                    logger.warning("Conectividade com internet: FALHA")
            except:
                logger.warning("Não foi possível testar conectividade")
                
        except Exception as e:
            logger.error(f"Erro ao obter configurações de rede: {e}")
        
        # === VARIÁVEIS DE AMBIENTE IMPORTANTES ===
        try:
            logger.info("\n[VARIÁVEIS DE AMBIENTE]")
            important_env_vars = ['PATH', 'TEMP', 'USERNAME', 'COMPUTERNAME', 'PROCESSOR_ARCHITECTURE']
            for var in important_env_vars:
                value = os.environ.get(var, 'Não definida')
                if var == 'PATH':
                    logger.info(f"{var}: {len(value.split(';'))} entradas")
                else:
                    logger.info(f"{var}: {value}")
        except Exception as e:
            logger.error(f"Erro ao obter variáveis de ambiente: {e}")
        
        # === TEMPO DE ATIVIDADE ===
        try:
            logger.info("\n[SISTEMA]")
            boot_time = psutil.boot_time()
            boot_time_formatted = datetime.fromtimestamp(boot_time).strftime('%Y-%m-%d %H:%M:%S')
            uptime_seconds = time.time() - boot_time
            uptime_hours = uptime_seconds / 3600
            logger.info(f"Último boot: {boot_time_formatted}")
            logger.info(f"Tempo ativo: {uptime_hours:.1f} horas")
        except Exception as e:
            logger.error(f"Erro ao obter tempo de atividade: {e}")
        
        logger.info("=" * 50)
        logger.info("=== FIM DO DIAGNÓSTICO COMPLETO ===")
        logger.info("=" * 50)

    def _on_server_document_created(self, document):
        """Callback chamado quando o servidor cria um novo documento"""
        try:
            # Marcar como processado
            if document.id not in self.processed_ids:
                self.processed_ids.add(document.id)
                
                logger.info(f"Novo documento criado pela impressora virtual: {document.name}")
                logger.info(f"Caminho do documento: {document.path}")
                
                # Verificar se o arquivo realmente existe
                if not os.path.exists(document.path):
                    logger.warning(f"O arquivo do documento não foi encontrado no caminho: {document.path}")
                    return
                
                # Atualizar o monitor de arquivos para garantir que o diretório esteja sendo monitorado
                if self.file_monitor:
                    # Se o diretório do documento não estiver na lista de diretórios monitorados
                    document_dir = os.path.dirname(document.path)
                    monitored_dirs = getattr(self.file_monitor, 'pdf_dirs', [])
                    
                    if document_dir not in monitored_dirs:
                        logger.info(f"Atualizando monitoramento para incluir: {document_dir}")
                        self.refresh_pdf_directories()
                
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
            logger.info(f"PDFs serão salvos para cada usuário conforme configurado")
            
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
        """Inicia o monitoramento das pastas de PDFs para todos os usuários"""
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
            
            # Verificar se o monitoramento foi iniciado com sucesso
            if hasattr(self.file_monitor, 'observers') and self.file_monitor.observers:
                logger.info(f"Monitoramento de arquivos iniciado com {len(self.file_monitor.observers)} observadores")
            else:
                logger.warning("Monitoramento de arquivos pode não estar funcionando corretamente")
            
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
                # Compatibilidade com o código existente
                if hasattr(self.file_monitor, 'observer') and self.file_monitor.observer:
                    status['monitoring_active'] = self.file_monitor.observer.is_alive()
                # Novo código com múltiplos observadores
                elif hasattr(self.file_monitor, 'observers'):
                    status['monitoring_active'] = any(
                        observer.is_alive() for observer in self.file_monitor.observers
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
    
    def refresh_pdf_directories(self):
        """
        Atualiza a lista de diretórios monitorados
        """
        if self.file_monitor:
            # Verifica se o método refresh_directories existe no file_monitor
            if hasattr(self.file_monitor, 'refresh_directories'):
                logger.info("Atualizando diretórios de PDF monitorados")
                self.file_monitor.refresh_directories()
                
                # Verificar se a atualização foi bem-sucedida
                if hasattr(self.file_monitor, 'observers'):
                    logger.info(f"Monitoramento atualizado: {len(self.file_monitor.observers)} observadores ativos")
                else:
                    logger.warning("A atualização pode não ter sido bem-sucedida")
            else:
                # Reinicia o monitor para atualizar diretórios (compatibilidade)
                logger.info("Reiniciando monitor de arquivos para atualizar diretórios")
                self.file_monitor.stop()
                self.file_monitor.start()

# Para compatibilidade com código existente
class PrintFolderMonitor(VirtualPrinterManager):
    """Alias para compatibilidade com código existente"""
    
    def __init__(self, config, api_client=None, on_new_document=None):
        super().__init__(config, api_client, on_new_document)
        logger.warning("PrintFolderMonitor é deprecated. Use VirtualPrinterManager em vez disso.")
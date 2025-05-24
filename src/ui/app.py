#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Classe principal da aplicação wxPython
"""

import os
import wx
import logging
import sys
from src.api import APIClient
from src.utils import AuthManager, ThemeManager
from src.ui.login_screen import LoginScreen
from src.ui.main_screen import MainScreen
from src.virtual_printer.monitor import VirtualPrinterManager
from src.utils.print_system import PrintSystem, PrintQueueManager

logger = logging.getLogger("PrintManagementSystem.UI.App")

class PrintManagementApp(wx.App):
    """Classe principal da aplicação"""
    
    def __init__(self, config=None, redirect=False, filename=None):
        """
        Inicializa a classe da aplicação
        
        Args:
            config: Configuração da aplicação
            redirect (bool): Redirecionar saída padrão
            filename (str): Nome do arquivo para redirecionar saída
        """
        self.config = config
        self.login_screen = None
        self.main_screen = None
        self.api_client = None
        self.auth_manager = None
        self.theme_manager = None
        self.scheduler = None
        self.virtual_printer_manager = None
        
        # Flag para controlar se estamos em segundo plano
        self.running_in_background = False
        
        # Configura tratamento de exceções não capturadas
        sys.excepthook = self._handle_uncaught_exception
        
        # Chama o construtor da classe pai
        super().__init__(redirect, filename)
    
    def _handle_uncaught_exception(self, exc_type, exc_value, exc_traceback):
        """
        Manipula exceções não capturadas
        
        Args:
            exc_type: Tipo da exceção
            exc_value: Valor da exceção
            exc_traceback: Traceback da exceção
        """
        # Registra a exceção no log
        logger.error("Exceção não tratada", exc_info=(exc_type, exc_value, exc_traceback))
        
        # Exibe mensagem para o usuário
        if self and wx.GetApp():
            wx.MessageBox(f"Ocorreu um erro inesperado: {str(exc_value)}", "Erro", wx.OK | wx.ICON_ERROR)
        
        # Chama o manipulador padrão de exceções
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
    
    def _validate_user_task(self, api_client, app_instance):
        """Tarefa de validação de usuário"""
        try:
            logger.debug("Executando validação de usuário...")
            
            if not api_client.token:
                logger.debug("Nenhum token encontrado, pulando validação")
                return
            
            result = api_client.validate_user()
            
            if result["is_valid"]:
                logger.debug("Usuário válido")
                return
            
            if result["should_logout"]:
                logger.warning(f"Token inválido (401), fazendo logout automático")
                
                def do_logout():
                    try:
                        if app_instance.auth_manager:
                            app_instance.auth_manager.logout()
                        
                        if hasattr(app_instance, 'on_logout'):
                            app_instance.on_logout()
                            
                    except Exception as e:
                        logger.error(f"Erro ao fazer logout automático: {e}")
                
                wx.CallAfter(do_logout)
            else:
                logger.debug(f"Erro na validação (não crítico): {result['error_message']} "
                            f"(Código: {result['error_code']})")
                
        except Exception as e:
            logger.error(f"Erro inesperado na tarefa de validação: {e}")

    def OnInit(self):
        """
        Inicializa a aplicação
        
        Returns:
            bool: True se a inicialização foi bem-sucedida
        """
        try:
            # Verifica se a configuração foi definida
            if not self.config:
                logger.error("Configuração da aplicação não foi definida")
                return False
            
            # Configura o cliente de API
            api_url = self.config.get("api_url", "https://api.loqquei.com.br/api/v1")
            self.api_client = APIClient(api_url)
            
            # Configura o gerenciador de autenticação
            self.auth_manager = AuthManager(self.config, self.api_client)
            
            # Configura o gerenciador de temas
            self.theme_manager = ThemeManager(self.config)
            
            # Inicializa sistema de impressora virtual
            self._init_virtual_printer()
            
            # Configura o agendador de tarefas
            from src.utils import TaskScheduler
            from src.tasks import update_printers_task, update_application_task
            
            self.scheduler = TaskScheduler()
            self.scheduler.add_task(
                "update_printers",
                update_printers_task,
                3600,  # Atualiza a cada hora
                args=(self.api_client, self.config)
            )

            self.scheduler.add_task(
                "check_updates",
                update_application_task,
                60, # Atualiza a cada minuto
                args=(self.api_client, self.config)
            )

            self.scheduler.add_task(
                "validate_user",
                lambda: self._validate_user_task(self.api_client, self),
                60,  # 1 minuto
                args=()
            )

            self.scheduler.start()
            
            from src.utils import AppUpdater
            updater = AppUpdater(self.config, self.api_client)
            updater.check_and_update(silent=True)

            # Auto login
            if self.auth_manager.auto_login():
                logger.info("Auto-login bem-sucedido")
                self.login_screen = None
                self.on_login_success()
                return True

            # Cria a tela de login
            self.login_screen = LoginScreen(
                None,
                self.auth_manager,
                self.theme_manager,
                self.on_login_success
            )
            
            # Configura o frame principal (inicialmente None)
            self.main_screen = None
            
            # Exibe a tela de login
            self.login_screen.Show()
            
            # Define a tela de login como frame principal
            self.SetTopWindow(self.login_screen)
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao inicializar aplicação: {str(e)}", exc_info=True)
            wx.MessageBox(f"Erro ao inicializar aplicação: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
            return False
    
    def _init_virtual_printer(self):
        """Inicializa o sistema de impressora virtual"""
        try:
            logger.info("Inicializando sistema de impressora virtual...")
            
            # Criar gerenciador da impressora virtual
            self.virtual_printer_manager = VirtualPrinterManager(
                self.config,
                self.api_client,
                self._on_virtual_printer_document
            )
            
            # Iniciar sistema de impressora virtual
            if self.virtual_printer_manager.start():
                logger.info("Sistema de impressora virtual iniciado com sucesso")
                
                # Log do status
                status = self.virtual_printer_manager.get_status()
                logger.info(f"Status da impressora virtual: {status}")
            else:
                logger.error("Falha ao iniciar sistema de impressora virtual")
                # Continua a aplicação mesmo se a impressora virtual falhar
                
        except Exception as e:
            logger.error(f"Erro ao inicializar impressora virtual: {str(e)}")
    
    def _init_print_system(self):
        """Inicializa o sistema de impressão"""
        try:
            # Inicializa o gerenciador de fila
            print_queue_manager = PrintQueueManager.get_instance()
            print_queue_manager.set_config(self.config)
            print_queue_manager.start()
            
            # Cria o sistema de impressão
            self.print_system = PrintSystem(self.config)
            
            logger.info("Sistema de impressão inicializado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar sistema de impressão: {str(e)}")

    def _on_virtual_printer_document(self, document):
        """
        Callback chamado quando um novo documento é criado pela impressora virtual
        
        Args:
            document: Documento criado
        """
        try:
            logger.info(f"Novo documento da impressora virtual: {document.name}")
            
            # Se a tela principal estiver ativa, atualiza a lista de documentos
            if self.main_screen and self.main_screen.IsShown():
                wx.CallAfter(self.main_screen.load_documents)
                
        except Exception as e:
            logger.error(f"Erro ao processar documento da impressora virtual: {e}")
    
    def on_login_success(self):
        """Callback chamado quando o login é bem-sucedido"""
        try:
            # Esconde a tela de login
            if self.login_screen:
                self.login_screen.Hide()
            
            # Cria e exibe a tela principal se ainda não existir
            if not self.main_screen:
                self.main_screen = MainScreen(
                    None,
                    self.auth_manager,
                    self.theme_manager,
                    self.api_client,
                    self.config,
                    self.on_logout
                )
            
            # Exibe a tela principal
            self.main_screen.Show()
            
            # Restaura o tamanho e posição salvos
            size = self.config.get("window_size", None)
            pos = self.config.get("window_pos", None)
            
            if size:
                self.main_screen.SetSize(size)
            
            if pos:
                self.main_screen.SetPosition(pos)
            
            # Define a tela principal como frame principal
            self.SetTopWindow(self.main_screen)
            
            # Reseta a flag de segundo plano
            self.running_in_background = False
            
        except Exception as e:
            logger.error(f"Erro ao processar login bem-sucedido: {str(e)}", exc_info=True)
            wx.MessageBox(f"Erro ao abrir tela principal: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
    
    def on_logout(self):
        """Callback chamado quando o usuário faz logout"""
        try:
            # Esconde a tela principal
            if self.main_screen:
                self.main_screen.Hide()
            
            # Cria uma nova tela de login se não existir
            if not self.login_screen:
                self.login_screen = LoginScreen(
                    None,
                    self.auth_manager,
                    self.theme_manager,
                    self.on_login_success
                )
            
            # Limpa campos da tela de login
            self.login_screen.email_input.SetValue("")
            self.login_screen.password_input.SetValue("")
            
            # Exibe a tela de login
            self.login_screen.Show()
            
            # Define a tela de login como frame principal
            self.SetTopWindow(self.login_screen)
            
        except Exception as e:
            logger.error(f"Erro ao processar logout: {str(e)}", exc_info=True)
            wx.MessageBox(f"Erro ao retornar à tela de login: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
    
    def keep_running_in_background(self):
        """
        Mantém a aplicação rodando em segundo plano
        
        Returns:
            bool: True se a aplicação deve continuar rodando
        """
        # Se não estiver rodando em segundo plano e não houver janelas visíveis
        if (not self.running_in_background and 
            ((self.login_screen and not self.login_screen.IsShown()) or not self.login_screen) and
            ((self.main_screen and not self.main_screen.IsShown()) or not self.main_screen)):
            
            self.running_in_background = True
            return True
        
        # Se estiver rodando em segundo plano
        if self.running_in_background:
            return True
        
        # Se houver alguma janela visível
        return ((self.login_screen and self.login_screen.IsShown()) or 
                (self.main_screen and self.main_screen.IsShown()))
    
    def SetTopWindow(self, window):
        """
        Define a janela principal da aplicação
        
        Args:
            window: Janela principal
        """
        super().SetTopWindow(window)
    
    def OnExit(self):
        """Chamado quando a aplicação está sendo encerrada"""
        try:
            # Para o agendador
            if self.scheduler:
                self.scheduler.stop()
            
            # Para o sistema de impressora virtual (mas não remove a impressora)
            if self.virtual_printer_manager:
                self.virtual_printer_manager.stop()
            
            logger.info("Aplicação encerrada")
            
        except Exception as e:
            logger.error(f"Erro ao encerrar aplicação: {e}")
        
        return super().OnExit()
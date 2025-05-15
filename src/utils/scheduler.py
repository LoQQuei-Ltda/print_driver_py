#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Gerenciador de tarefas agendadas
"""

import threading
import time
import logging
from datetime import datetime

logger = logging.getLogger("PrintManagementSystem.Utils.Scheduler")

class Task:
    """Representação de uma tarefa agendada"""
    
    def __init__(self, name, function, interval, args=None, kwargs=None):
        """
        Inicializa uma tarefa
        
        Args:
            name (str): Nome da tarefa
            function (callable): Função a ser executada
            interval (int): Intervalo em segundos
            args (tuple, optional): Argumentos posicionais
            kwargs (dict, optional): Argumentos nomeados
        """
        self.name = name
        self.function = function
        self.interval = interval
        self.args = args or ()
        self.kwargs = kwargs or {}
        self.last_run = None
        self.next_run = None
        self.running = False
        self.is_enabled = True
    
    def run(self):
        """Executa a tarefa"""
        if not self.is_enabled:
            return
        
        try:
            self.running = True
            self.last_run = datetime.now()
            self.function(*self.args, **self.kwargs)
        except Exception as e:
            logger.error(f"Erro ao executar tarefa {self.name}: {str(e)}")
        finally:
            self.running = False
            self.next_run = datetime.now().timestamp() + self.interval
    
    def should_run(self):
        """
        Verifica se a tarefa deve ser executada
        
        Returns:
            bool: True se a tarefa deve ser executada
        """
        if not self.is_enabled or self.running:
            return False
        
        if self.next_run is None:
            return True
        
        return datetime.now().timestamp() >= self.next_run
    
    def enable(self):
        """Habilita a tarefa"""
        self.is_enabled = True
    
    def disable(self):
        """Desabilita a tarefa"""
        self.is_enabled = False


class TaskScheduler:
    """Gerenciador de tarefas agendadas"""
    
    def __init__(self):
        """Inicializa o agendador de tarefas"""
        self.tasks = {}
        self.running = False
        self.thread = None
    
    def add_task(self, name, function, interval, args=None, kwargs=None):
        """
        Adiciona uma tarefa
        
        Args:
            name (str): Nome da tarefa
            function (callable): Função a ser executada
            interval (int): Intervalo em segundos
            args (tuple, optional): Argumentos posicionais
            kwargs (dict, optional): Argumentos nomeados
            
        Returns:
            Task: Tarefa criada
        """
        task = Task(name, function, interval, args, kwargs)
        self.tasks[name] = task
        return task
    
    def remove_task(self, name):
        """
        Remove uma tarefa
        
        Args:
            name (str): Nome da tarefa
            
        Returns:
            bool: True se a tarefa foi removida
        """
        if name in self.tasks:
            del self.tasks[name]
            return True
        return False
    
    def start(self):
        """
        Inicia o agendador de tarefas
        
        Returns:
            bool: True se o agendador foi iniciado
        """
        if self.running:
            return True
        
        logger.info("Iniciando agendador de tarefas")
        
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
        return True
    
    def stop(self):
        """
        Para o agendador de tarefas
        
        Returns:
            bool: True se o agendador foi parado
        """
        if not self.running:
            return True
        
        logger.info("Parando agendador de tarefas")
        
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(2.0)
        
        return True
    
    def is_running(self):
        """
        Verifica se o agendador está em execução
        
        Returns:
            bool: True se o agendador está em execução
        """
        return self.running and self.thread and self.thread.is_alive()
    
    def _run_loop(self):
        """Loop principal do agendador"""
        logger.info("Thread do agendador iniciada")
        
        while self.running:
            try:
                for name, task in list(self.tasks.items()):
                    if task.should_run():
                        threading.Thread(target=task.run, daemon=True).start()
                
                time.sleep(1.0)  # Verifica a cada segundo
            except Exception as e:
                logger.error(f"Erro no loop do agendador: {str(e)}")
                time.sleep(5.0)
        
        logger.info("Thread do agendador encerrada")
    
    def get_task(self, name):
        """
        Obtém uma tarefa pelo nome
        
        Args:
            name (str): Nome da tarefa
            
        Returns:
            Task: Tarefa encontrada ou None
        """
        return self.tasks.get(name)
    
    def enable_task(self, name):
        """
        Habilita uma tarefa
        
        Args:
            name (str): Nome da tarefa
            
        Returns:
            bool: True se a tarefa foi habilitada
        """
        task = self.get_task(name)
        if task:
            task.enable()
            return True
        return False
    
    def disable_task(self, name):
        """
        Desabilita uma tarefa
        
        Args:
            name (str): Nome da tarefa
            
        Returns:
            bool: True se a tarefa foi desabilitada
        """
        task = self.get_task(name)
        if task:
            task.disable()
            return True
        return False
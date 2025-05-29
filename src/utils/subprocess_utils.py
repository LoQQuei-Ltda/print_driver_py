#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitários para subprocess que evitam janelas de terminal
"""

import subprocess
import platform
import logging
import os

logger = logging.getLogger(__name__)

class SubprocessUtils:
    """Utilitários para execução de subprocess sem janelas visíveis"""
    
    @staticmethod
    def get_creation_flags():
        """Retorna as flags adequadas para evitar janelas no Windows"""
        if platform.system() == 'Windows':
            return subprocess.CREATE_NO_WINDOW
        return 0
    
    @staticmethod
    def get_startupinfo():
        """Retorna startupinfo para Windows que oculta janelas"""
        if platform.system() == 'Windows':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            return startupinfo
        return None
    
    @staticmethod
    def run_hidden(cmd, **kwargs):
        """Executa comando sem mostrar janela"""
        creation_flags = SubprocessUtils.get_creation_flags()
        startupinfo = SubprocessUtils.get_startupinfo()
        
        # Adiciona as flags de ocultação
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | creation_flags
        if startupinfo:
            kwargs['startupinfo'] = startupinfo
        
        # Define padrões seguros
        kwargs.setdefault('capture_output', True)
        kwargs.setdefault('text', True)
        
        try:
            return subprocess.run(cmd, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao executar comando {cmd}: {e}")
            raise
    
    @staticmethod
    def popen_hidden(cmd, **kwargs):
        """Cria processo sem mostrar janela"""
        creation_flags = SubprocessUtils.get_creation_flags()
        startupinfo = SubprocessUtils.get_startupinfo()
        
        # Adiciona as flags de ocultação
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | creation_flags
        if startupinfo:
            kwargs['startupinfo'] = startupinfo
        
        try:
            return subprocess.Popen(cmd, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao criar processo {cmd}: {e}")
            raise
    
    @staticmethod
    def check_output_hidden(cmd, **kwargs):
        """Executa comando e retorna output sem mostrar janela"""
        creation_flags = SubprocessUtils.get_creation_flags()
        startupinfo = SubprocessUtils.get_startupinfo()
        
        # Adiciona as flags de ocultação
        kwargs['creationflags'] = kwargs.get('creationflags', 0) | creation_flags
        if startupinfo:
            kwargs['startupinfo'] = startupinfo
        
        try:
            return subprocess.check_output(cmd, **kwargs)
        except Exception as e:
            logger.error(f"Erro ao executar comando {cmd}: {e}")
            raise

# Funções de conveniência
def run_hidden(cmd, **kwargs):
    """Função de conveniência para execução oculta"""
    return SubprocessUtils.run_hidden(cmd, **kwargs)

def popen_hidden(cmd, **kwargs):
    """Função de conveniência para Popen oculto"""
    return SubprocessUtils.popen_hidden(cmd, **kwargs)

def check_output_hidden(cmd, **kwargs):
    """Função de conveniência para check_output oculto"""
    return SubprocessUtils.check_output_hidden(cmd, **kwargs)
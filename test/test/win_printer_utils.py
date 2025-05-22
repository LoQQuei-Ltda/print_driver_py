#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitários para gerenciar impressoras no Windows
"""
import subprocess
import typing
import os
import sys

class WindowsPrinters:
    """Classe para gerenciar impressoras no Windows"""

    def __init__(self):
        """Inicializa com os drivers disponíveis para impressoras"""
        # Lista de drivers comuns em ordem de preferência
        self.postscript_printer_drivers = [
            'Microsoft Print To PDF',
            'Microsoft XPS Document Writer',
            'HP Universal Printing PS',
            'HP Color LaserJet 2800 Series PS',
            'Generic / Text Only'
        ]
        # Encontrar um driver disponível
        self.default_postscript_printer_driver = self.find_available_driver()

    def find_available_driver(self):
        """Encontra um driver de impressora disponível no sistema"""
        # Listar drivers disponíveis
        try:
            output = subprocess.check_output([
                'powershell',
                '-command',
                'Get-PrinterDriver | Select-Object Name | Format-Table -HideTableHeaders'
            ], universal_newlines=True)
            
            available_drivers = [line.strip() for line in output.splitlines() if line.strip()]
            
            # Primeiro verifica se os drivers que preferimos estão disponíveis
            for driver in self.postscript_printer_drivers:
                if driver in available_drivers:
                    print(f"Usando driver: {driver}")
                    return driver
            
            # Se nenhum dos nossos drivers preferidos estiver disponível, use o primeiro disponível
            if available_drivers:
                print(f"Usando driver alternativo: {available_drivers[0]}")
                return available_drivers[0]
            
            # Se nenhum driver for encontrado (improvável)
            print("AVISO: Nenhum driver de impressora encontrado! Usando driver padrão.")
            return 'Microsoft Print To PDF'
            
        except Exception as e:
            print(f"Erro ao listar drivers disponíveis: {e}")
            print("Usando driver padrão como fallback.")
            return 'Microsoft Print To PDF'

    def remove_port(self, printer_port_name):
        """Remove uma porta de impressora"""
        cmd = ['cscript',
               r'c:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
               '-d', '-r', printer_port_name]
        print("Removendo porta de impressora...")
        try:
            with subprocess.Popen(cmd,
                stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao remover porta: {e}")

    def remove_printer(self, name):
        """Remove uma impressora instalada"""
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/dl', '/n', name]
        print(f"Removendo impressora: {name}")
        try:
            with subprocess.Popen(cmd,
                stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao remover impressora: {e}")

    def make_printer_default(self, name):
        """Define uma impressora como padrão"""
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/y', '/n', name]
        try:
            with subprocess.Popen(cmd,
                stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao definir impressora padrão: {e}")

    def set_printer_comment(self, name: str, comment: str) -> None:
        """Adiciona um comentário à impressora"""
        comment = comment.replace('"', '\\"').replace('\n', '\\n')
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/Xs',
               '/n', name,
               'comment', comment]
        try:
            with subprocess.Popen(
                cmd, stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao definir comentário: {e}")

    def add_printer(self,
        name: str,
        host: str = '127.0.0.1', port: typing.Union[int, str] = 9101,
        printer_port_name: typing.Optional[str] = None,
        make_default: bool = False,
        comment: typing.Optional[str] = None
        ) -> None:
        """Adiciona uma nova impressora ao sistema"""
        port = str(port)
        
        # Criar a porta da impressora
        if printer_port_name is None:
            printer_port_name = f"{host}:{port}"
        
        cmd = ['cscript',
               r'c:\Windows\System32\Printing_Admin_Scripts\en-US\prnport.vbs',
               '-md', '-a', '-o', 'raw',
               '-r', printer_port_name,
               '-h', host, '-n', port]
        
        print(f"Criando porta de impressora: {printer_port_name}")
        try:
            with subprocess.Popen(cmd,
                stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao criar porta: {e}")
            return
        
        # Verificar se driver existe
        if not self.default_postscript_printer_driver:
            print("ERRO: Nenhum driver de impressora compatível encontrado.")
            return
        
        # Criar a impressora com o driver disponível
        cmd = ['rundll32', 'printui.dll,PrintUIEntry', '/if',
               '/b', name,
               '/r', printer_port_name,
               '/m', self.default_postscript_printer_driver,
               '/Z']
        
        print(f"Criando impressora: {name} com driver: {self.default_postscript_printer_driver}")
        try:
            with subprocess.Popen(cmd,
                stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao criar impressora: {e}")
            return
        
        # Definir como impressora padrão se necessário
        if make_default:
            self.make_printer_default(name)
        
        # Definir comentário se fornecido
        if comment is not None:
            self.set_printer_comment(name, comment)

        print(f"Impressora {name} instalada com sucesso!")

    def print_test_page(self, name: str) -> None:
        """Envia uma página de teste para a impressora"""
        cmd = ['rundll32',
               'printui.dll,PrintUIEntry',
               '/k',
               '/n', name]
        
        try:
            with subprocess.Popen(cmd,
                stdin=None, stderr=subprocess.STDOUT, stdout=subprocess.PIPE,
                shell=True) as po:
                stdout, _ = po.communicate()
            if stdout:
                print(stdout.decode('utf-8', errors='ignore'))
        except Exception as e:
            print(f"Erro ao imprimir página de teste: {e}")

if __name__ == '__main__':
    print("Este módulo não deve ser executado diretamente.")
    print("Use o pdf_printer.py para instalar a impressora virtual.")
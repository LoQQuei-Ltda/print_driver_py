#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utilitários para gerenciar impressoras em sistemas Unix (Linux/macOS)
Usando CUPS (Common Unix Printing System)
"""
import subprocess
import os
import platform
import time

class UnixPrinters:
    """Classe para gerenciar impressoras Unix usando CUPS"""

    def __init__(self):
        """Inicializa verificando se CUPS está disponível"""
        self.system = platform.system()
        self.cups_available = self._check_cups_availability()
        
        if not self.cups_available:
            self._install_cups_suggestions()

    def _check_cups_availability(self):
        """Verifica se CUPS está instalado e acessível"""
        try:
            # Verificar se lpadmin está disponível
            result = subprocess.run(['which', 'lpadmin'], 
                                 capture_output=True, text=True)
            if result.returncode != 0:
                print("CUPS não encontrado no sistema.")
                return False
            
            # Verificar se lpstat está disponível
            result = subprocess.run(['which', 'lpstat'], 
                                 capture_output=True, text=True)
            if result.returncode != 0:
                print("Utilitários CUPS incompletos.")
                return False
            
            # Tentar acessar o serviço CUPS
            try:
                result = subprocess.run(['lpstat', '-r'], 
                                     capture_output=True, text=True, timeout=5)
                if "not ready" in result.stdout.lower():
                    print("Serviço CUPS não está rodando.")
                    self._start_cups_service()
            except subprocess.TimeoutExpired:
                print("CUPS não responde adequadamente.")
                return False
            
            return True
            
        except Exception as e:
            print(f"Erro ao verificar CUPS: {e}")
            return False

    def _start_cups_service(self):
        """Tenta iniciar o serviço CUPS"""
        print("Tentando iniciar o serviço CUPS...")
        
        if self.system == 'Linux':
            # Comandos para diferentes distribuições Linux
            service_commands = [
                ['sudo', 'systemctl', 'start', 'cups'],
                ['sudo', 'service', 'cups', 'start'],
                ['sudo', '/etc/init.d/cups', 'start']
            ]
        elif self.system == 'Darwin':  # macOS
            service_commands = [
                ['sudo', 'launchctl', 'load', '/System/Library/LaunchDaemons/org.cups.cupsd.plist'],
                ['sudo', 'brew', 'services', 'start', 'cups']  # Se instalado via Homebrew
            ]
        else:
            service_commands = []
        
        for cmd in service_commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                if result.returncode == 0:
                    print("Serviço CUPS iniciado com sucesso.")
                    time.sleep(2)  # Aguardar o serviço inicializar
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        print("Não foi possível iniciar o serviço CUPS automaticamente.")
        return False

    def _install_cups_suggestions(self):
        """Fornece sugestões para instalar CUPS"""
        print("\n" + "="*50)
        print("CUPS NÃO ENCONTRADO")
        print("="*50)
        
        if self.system == 'Linux':
            print("Para instalar CUPS no Linux, use um dos comandos abaixo:")
            print("\nUbuntu/Debian:")
            print("  sudo apt-get update")
            print("  sudo apt-get install cups cups-client")
            print("\nCentOS/RHEL/Fedora:")
            print("  sudo yum install cups cups-client")
            print("  # ou")
            print("  sudo dnf install cups cups-client")
            print("\nArch Linux:")
            print("  sudo pacman -S cups")
            
        elif self.system == 'Darwin':  # macOS
            print("No macOS, CUPS geralmente está pré-instalado.")
            print("Se não estiver funcionando, tente:")
            print("\nCom Homebrew:")
            print("  brew install cups")
            print("\nOu verifique se o serviço está rodando:")
            print("  sudo launchctl load /System/Library/LaunchDaemons/org.cups.cupsd.plist")
        
        print("\nApós instalar, reinicie este programa.")
        print("="*50 + "\n")

    def add_printer(self, name, host='127.0.0.1', port=9100, 
                   printer_port_name=None, make_default=False, comment=None):
        """Adiciona uma nova impressora usando CUPS"""
        if not self.cups_available:
            print("ERRO: CUPS não está disponível. Não é possível adicionar impressora.")
            return False

        device_uri = f"socket://{host}:{port}"
        
        # Comando base para adicionar impressora
        cmd = [
            'lpadmin',
            '-p', name,           # Nome da impressora
            '-E',                 # Habilitar e aceitar trabalhos
            '-v', device_uri      # URI do dispositivo
        ]
        
        # Adicionar privilégios sudo se necessário
        if os.geteuid() != 0:  # Se não for root
            cmd.insert(0, 'sudo')
        
        # Tentar diferentes drivers em ordem de preferência
        drivers = [
            'raw',                                    # Driver raw (sem processamento)
            'drv:///generic.drv/generic.ppd',        # Driver genérico
            'lsb/usr/cupsfilters/generic-postscript-driver.ppd',  # PostScript genérico
            'textonly.ppd'                           # Somente texto
        ]
        
        success = False
        for driver in drivers:
            try:
                current_cmd = cmd + ['-m', driver]
                print(f"Tentando instalar com driver: {driver}")
                
                result = subprocess.run(current_cmd, capture_output=True, 
                                     text=True, timeout=30)
                
                if result.returncode == 0:
                    print(f"Impressora '{name}' instalada com sucesso usando driver: {driver}")
                    success = True
                    break
                else:
                    print(f"Falha com driver {driver}: {result.stderr.strip()}")
                    
            except subprocess.TimeoutExpired:
                print(f"Timeout ao instalar com driver: {driver}")
                continue
            except Exception as e:
                print(f"Erro ao instalar com driver {driver}: {e}")
                continue
        
        if not success:
            print("Erro: Não foi possível instalar a impressora com nenhum driver disponível.")
            return False
        
        # Configurações adicionais se a instalação foi bem-sucedida
        try:
            # Definir comentário/descrição se fornecido
            if comment:
                cmd_comment = ['lpadmin', '-p', name, '-D', comment]
                if os.geteuid() != 0:
                    cmd_comment.insert(0, 'sudo')
                subprocess.run(cmd_comment, capture_output=True, timeout=10)
            
            # Definir como impressora padrão se solicitado
            if make_default:
                self.make_printer_default(name)
            
            # Habilitar compartilhamento (opcional)
            cmd_share = ['lpadmin', '-p', name, '-o', 'printer-is-shared=true']
            if os.geteuid() != 0:
                cmd_share.insert(0, 'sudo')
            subprocess.run(cmd_share, capture_output=True, timeout=10)
            
        except Exception as e:
            print(f"Aviso: Erro ao aplicar configurações adicionais: {e}")
        
        return True

    def remove_printer(self, name):
        """Remove uma impressora"""
        if not self.cups_available:
            print("ERRO: CUPS não está disponível.")
            return False
        
        cmd = ['lpadmin', '-x', name]
        if os.geteuid() != 0:
            cmd.insert(0, 'sudo')
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print(f"Impressora '{name}' removida com sucesso.")
                return True
            else:
                print(f"Erro ao remover impressora: {result.stderr.strip()}")
                return False
        except Exception as e:
            print(f"Erro ao remover impressora: {e}")
            return False

    def make_printer_default(self, name):
        """Define uma impressora como padrão"""
        cmd = ['lpadmin', '-d', name]
        if os.geteuid() != 0:
            cmd.insert(0, 'sudo')
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if result.returncode == 0:
                print(f"Impressora '{name}' definida como padrão.")
                return True
            else:
                print(f"Erro ao definir impressora padrão: {result.stderr.strip()}")
                return False
        except Exception as e:
            print(f"Erro ao definir impressora padrão: {e}")
            return False

    def list_printers(self):
        """Lista todas as impressoras instaladas"""
        if not self.cups_available:
            print("ERRO: CUPS não está disponível.")
            return []
        
        try:
            result = subprocess.run(['lpstat', '-p'], capture_output=True, 
                                 text=True, timeout=10)
            if result.returncode == 0:
                printers = []
                for line in result.stdout.splitlines():
                    if line.startswith('printer '):
                        # Extrair nome da impressora
                        parts = line.split()
                        if len(parts) >= 2:
                            printer_name = parts[1]
                            printers.append(printer_name)
                return printers
            else:
                print(f"Erro ao listar impressoras: {result.stderr.strip()}")
                return []
        except Exception as e:
            print(f"Erro ao listar impressoras: {e}")
            return []

    def printer_exists(self, name):
        """Verifica se uma impressora existe"""
        printers = self.list_printers()
        return name in printers

    def get_printer_status(self, name):
        """Obtém o status de uma impressora"""
        if not self.cups_available:
            return None
        
        try:
            result = subprocess.run(['lpstat', '-p', name], capture_output=True, 
                                 text=True, timeout=10)
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                return None
        except Exception as e:
            print(f"Erro ao obter status da impressora: {e}")
            return None

    def test_printer(self, name):
        """Envia uma página de teste para a impressora"""
        if not self.cups_available:
            print("ERRO: CUPS não está disponível.")
            return False
        
        # Criar arquivo de teste temporário
        test_content = f"""
Teste de Impressão
==================

Impressora: {name}
Data/Hora: {time.strftime('%d/%m/%Y %H:%M:%S')}
Sistema: {self.system}

Esta é uma página de teste para verificar se a impressora
está funcionando corretamente.

Se você está vendo este texto, a impressão foi bem-sucedida!
"""
        
        try:
            # Usar echo e pipe para enviar conteúdo de teste
            cmd = ['echo', test_content]
            lp_cmd = ['lp', '-d', name]
            
            echo_process = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            lp_process = subprocess.Popen(lp_cmd, stdin=echo_process.stdout, 
                                        capture_output=True, text=True)
            echo_process.stdout.close()
            
            output, error = lp_process.communicate(timeout=15)
            
            if lp_process.returncode == 0:
                print(f"Página de teste enviada para '{name}' com sucesso.")
                return True
            else:
                print(f"Erro ao enviar página de teste: {error.strip()}")
                return False
                
        except Exception as e:
            print(f"Erro ao enviar página de teste: {e}")
            return False

    def get_cups_status(self):
        """Verifica o status geral do CUPS"""
        if not self.cups_available:
            return "CUPS não disponível"
        
        try:
            result = subprocess.run(['lpstat', '-r'], capture_output=True, 
                                 text=True, timeout=10)
            return result.stdout.strip()
        except Exception as e:
            return f"Erro ao verificar status: {e}"

    def restart_cups(self):
        """Reinicia o serviço CUPS"""
        print("Reiniciando serviço CUPS...")
        
        if self.system == 'Linux':
            commands = [
                ['sudo', 'systemctl', 'restart', 'cups'],
                ['sudo', 'service', 'cups', 'restart'],
                ['sudo', '/etc/init.d/cups', 'restart']
            ]
        elif self.system == 'Darwin':  # macOS
            commands = [
                ['sudo', 'launchctl', 'unload', '/System/Library/LaunchDaemons/org.cups.cupsd.plist'],
                ['sudo', 'launchctl', 'load', '/System/Library/LaunchDaemons/org.cups.cupsd.plist']
            ]
        else:
            return False
        
        for cmd in commands:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                if result.returncode == 0:
                    print("Serviço CUPS reiniciado com sucesso.")
                    time.sleep(3)  # Aguardar reinicialização
                    return True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                continue
        
        print("Erro: Não foi possível reiniciar o CUPS.")
        return False

if __name__ == '__main__':
    # Teste básico das funcionalidades
    print("Testando utilitários Unix de impressão...")
    
    cups = UnixPrinters()
    
    if cups.cups_available:
        print("CUPS está disponível!")
        print("Status do CUPS:", cups.get_cups_status())
        print("Impressoras instaladas:", cups.list_printers())
    else:
        print("CUPS não está disponível. Verifique a instalação.")
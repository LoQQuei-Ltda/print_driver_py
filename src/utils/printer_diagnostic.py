#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Utilitário para diagnóstico de impressoras
"""

import logging
import time
import os
import sys
import subprocess
import socket
import tempfile
import threading

logger = logging.getLogger("PrintManagementSystem.Utils.PrinterDiagnostic")

class PrinterDiagnostic:
    """Classe para diagnóstico e teste de impressoras"""
    
    def __init__(self, printer, callback=None):
        """
        Inicializa o diagnóstico de impressora
        
        Args:
            printer: Objeto Printer para diagnosticar
            callback: Callback opcional para atualizar progresso
        """
        self.printer = printer
        self.callback = callback
        self.results = {}
        
    def run_diagnostics(self):
        """
        Executa todos os diagnósticos disponíveis
        
        Returns:
            dict: Resultados dos diagnósticos
        """
        self.results = {}
        
        # Lista de testes a executar
        tests = [
            ("connectivity", "Teste de Conectividade", self._test_connectivity),
            ("port_availability", "Portas Disponíveis", self._test_ports),
            ("ipp", "IPP/Protocolo de Impressão", self._test_ipp),
            ("print_job", "Teste de Envio de Trabalho", self._test_print_job)
        ]
        
        # Executa cada teste
        for test_id, test_name, test_func in tests:
            if self.callback:
                self.callback(f"Executando {test_name}...")
                
            try:
                result = test_func()
                self.results[test_id] = result
                
                if self.callback:
                    status = "Passou" if result.get("success", False) else "Falhou"
                    self.callback(f"{test_name}: {status} - {result.get('message', '')}")
            except Exception as e:
                logger.error(f"Erro ao executar teste {test_id}: {str(e)}")
                self.results[test_id] = {
                    "success": False,
                    "message": f"Erro inesperado: {str(e)}",
                    "details": str(e)
                }
                
                if self.callback:
                    self.callback(f"{test_name}: Falhou - {str(e)}")
        
        # Determina o status geral
        self.results["overall"] = self._get_overall_status()
        
        if self.callback:
            status = "Operacional" if self.results["overall"]["success"] else "Não Operacional"
            self.callback(f"Diagnóstico Concluído: Impressora {status}")
            
        return self.results
    
    def _test_connectivity(self):
        """
        Testa a conectividade básica com a impressora
        
        Returns:
            dict: Resultado do teste
        """
        if not self.printer.ip:
            return {
                "success": False,
                "message": "IP não configurado",
                "details": "A impressora não possui um endereço IP configurado."
            }
        
        # Tenta fazer ping na impressora
        ping_result = self._ping_host(self.printer.ip)
        
        if ping_result:
            return {
                "success": True,
                "message": f"Conectividade confirmada ({self.printer.ip})",
                "details": f"Ping bem-sucedido para {self.printer.ip}"
            }
        else:
            # Se o ping falhar, tenta conectar em alguma porta
            for port in [631, 9100, 80]:
                if self._check_port(self.printer.ip, port):
                    return {
                        "success": True,
                        "message": f"Porta {port} aberta em {self.printer.ip}",
                        "details": f"Não foi possível fazer ping, mas a porta {port} está acessível."
                    }
            
            # Se tudo falhar
            return {
                "success": False,
                "message": "Falha na conectividade",
                "details": f"Não foi possível conectar com a impressora em {self.printer.ip}."
            }
    
    def _test_ports(self):
        """
        Testa as portas comuns de impressoras
        
        Returns:
            dict: Resultado do teste
        """
        if not self.printer.ip:
            return {
                "success": False,
                "message": "IP não configurado",
                "details": "A impressora não possui um endereço IP configurado."
            }
        
        open_ports = []
        
        # Lista de portas comuns a verificar
        ports_to_check = [631, 9100, 80, 443, 515, 22, 23]
        
        # Verifica cada porta
        for port in ports_to_check:
            if self._check_port(self.printer.ip, port):
                open_ports.append(port)
        
        if open_ports:
            return {
                "success": True,
                "message": f"Portas abertas: {', '.join(map(str, open_ports))}",
                "details": f"A impressora tem as seguintes portas abertas: {open_ports}",
                "open_ports": open_ports
            }
        else:
            return {
                "success": False,
                "message": "Nenhuma porta comum de impressora aberta",
                "details": "Não foi encontrada nenhuma porta de serviço aberta."
            }
    
    def _test_ipp(self):
        """
        Testa o protocolo IPP (Internet Printing Protocol)
        
        Returns:
            dict: Resultado do teste
        """
        if not self.printer.ip:
            return {
                "success": False,
                "message": "IP não configurado",
                "details": "A impressora não possui um endereço IP configurado."
            }
        
        # Verifica se a porta 631 (IPP) está aberta
        if not self._check_port(self.printer.ip, 631):
            return {
                "success": False,
                "message": "Porta IPP (631) não está acessível",
                "details": "A porta padrão do IPP (631) não está acessível."
            }
        
        # Tenta usar pyipp para obter detalhes
        try:
            from src.utils.printer_discovery import PrinterDiscovery
            discovery = PrinterDiscovery()
            
            # Obtém detalhes da impressora
            printer_details = discovery.get_printer_details(self.printer.ip)
            
            if printer_details:
                return {
                    "success": True,
                    "message": "Protocolo IPP disponível",
                    "details": f"Estado: {printer_details.get('printer-state', 'Desconhecido')}",
                    "printer_details": printer_details
                }
            else:
                return {
                    "success": False,
                    "message": "Não foi possível obter detalhes IPP",
                    "details": "A impressora não respondeu corretamente a consultas IPP."
                }
        except Exception as e:
            return {
                "success": False,
                "message": "Falha ao acessar via IPP",
                "details": f"Erro: {str(e)}"
            }
    
    def _test_print_job(self):
        """
        Testa o envio de um pequeno trabalho de impressão
        
        Returns:
            dict: Resultado do teste
        """
        if not self.printer.ip:
            return {
                "success": False,
                "message": "IP não configurado",
                "details": "A impressora não possui um endereço IP configurado."
            }
        
        # Verifica se URI está disponível
        if not self.printer.uri:
            return {
                "success": False,
                "message": "URI não disponível",
                "details": "A impressora não possui URI configurado para envio de trabalhos."
            }
        
        # Verifica se temos um teste de RAW Socket
        if self.printer.uri.startswith("socket://") or "9100" in self.printer.uri:
            return self._test_raw_print()
        
        # Verifica se temos um teste de IPP
        if self.printer.uri.startswith("ipp://"):
            # Não implementamos aqui, mas retornamos sucesso se o teste IPP já passou
            if "ipp" in self.results and self.results["ipp"].get("success", False):
                return {
                    "success": True, 
                    "message": "Assumindo capacidade de impressão IPP",
                    "details": "O protocolo IPP está operacional, o que indica que a impressora deve aceitar trabalhos."
                }
            
            return {
                "success": False,
                "message": "Teste de impressão IPP não implementado",
                "details": "Este teste ainda não está disponível."
            }
        
        # Caso contrário, não sabemos como testar
        return {
            "success": False,
            "message": "Protocolo de impressão desconhecido",
            "details": f"Não é possível testar o URI {self.printer.uri}"
        }
    
    def _test_raw_print(self):
        """
        Testa envio de dados RAW para a impressora
        
        Returns:
            dict: Resultado do teste
        """
        try:
            # Extrai o IP e porta do URI
            uri = self.printer.uri.replace("socket://", "")
            if ":" in uri:
                ip, port_str = uri.split(":")
                port = int(port_str)
            else:
                ip = uri
                port = 9100
            
            # Cria uma conexão socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((ip, port))
            
            # Envia uma pequena sequência de teste
            # Apenas retorna o status da impressora, não imprime nada
            data = b"\x1B%-12345X@PJL INFO STATUS\r\n\x1B%-12345X"
            sock.sendall(data)
            
            # Tenta receber alguma resposta (nem todas impressoras respondem)
            try:
                sock.settimeout(1)
                response = sock.recv(1024)
                sock.close()
                
                return {
                    "success": True,
                    "message": "Teste de impressão bem-sucedido",
                    "details": f"A impressora aceitou o comando de teste. Resposta: {response.decode('utf-8', errors='ignore')}"
                }
            except socket.timeout:
                sock.close()
                
                # Ainda consideramos sucesso, pois muitas impressoras não respondem
                return {
                    "success": True,
                    "message": "Comando enviado, sem resposta",
                    "details": "A impressora aceitou o comando, mas não retornou resposta."
                }
        except Exception as e:
            return {
                "success": False,
                "message": "Falha no teste de impressão",
                "details": f"Erro: {str(e)}"
            }
    
    def _get_overall_status(self):
        """
        Determina o status geral da impressora
        
        Returns:
            dict: Status geral
        """
        # Verifica os testes críticos: conectividade e portas
        if (not self.results.get("connectivity", {}).get("success", False) or
            not self.results.get("port_availability", {}).get("success", False)):
            return {
                "success": False,
                "message": "Impressora não está acessível",
                "details": "Falha na conectividade básica com a impressora."
            }
        
        # Verifica o protocolo de impressão
        if not (self.results.get("ipp", {}).get("success", False) or
               self.results.get("print_job", {}).get("success", False)):
            return {
                "success": False,
                "message": "Protocolo de impressão não disponível",
                "details": "A impressora está online, mas o protocolo de impressão não está funcionando."
            }
        
        # Tudo parece bom
        return {
            "success": True,
            "message": "Impressora operacional",
            "details": "Todos os testes passaram ou testes suficientes indicam que a impressora está funcional."
        }
    
    def _ping_host(self, ip, timeout=1):
        """
        Faz ping em um host
        
        Args:
            ip: Endereço IP
            timeout: Tempo limite em segundos
            
        Returns:
            bool: True se o ping foi bem-sucedido
        """
        try:
            # Comando de ping depende do sistema operacional
            if sys.platform.startswith("win"):
                # Windows
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
            else:
                # Linux/macOS
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
            
            # Executa o comando
            result = subprocess.run(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                timeout=timeout + 1,
                creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0
            )
            
            # Retorna True se o comando foi bem-sucedido
            return result.returncode == 0
            
        except Exception as e:
            logger.warning(f"Erro ao executar ping: {str(e)}")
            return False
    
    def _check_port(self, ip, port, timeout=1):
        """
        Verifica se uma porta está aberta
        
        Args:
            ip: Endereço IP
            port: Número da porta
            timeout: Tempo limite em segundos
            
        Returns:
            bool: True se a porta está aberta
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            logger.warning(f"Erro ao verificar porta {port}: {str(e)}")
            return False
    
    def run_diagnostics_async(self, callback=None):
        """
        Executa diagnósticos em uma thread separada
        
        Args:
            callback: Função a ser chamada com os resultados
            
        Returns:
            bool: True se o diagnóstico foi iniciado
        """
        if callback is None:
            callback = self.callback
            
        # Define uma função para executar na thread
        def run_thread():
            results = self.run_diagnostics()
            if callback:
                callback(results)
        
        # Inicia a thread
        thread = threading.Thread(target=run_thread)
        thread.daemon = True
        thread.start()
        
        return True
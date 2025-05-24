#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Teste do sistema de impressão integrado
"""

import os
import sys
import unittest
import tempfile
import shutil
import time
from datetime import datetime

# Adiciona o diretório raiz ao path para importação
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import AppConfig
from src.utils.print_system import PrintSystem, PrintOptions, ColorMode, Duplex, Quality, IPPPrinter
from src.models.document import Document
from src.models.printer import Printer
from src.models.print_job import PrintJob, PrintJobStatus

class MockDocument:
    """Documento de teste"""
    
    def __init__(self, name, path, size=1024, pages=1):
        self.id = "doc_test_123"
        self.name = name
        self.path = path
        self.size = size
        self.formatted_size = f"{size / 1024:.1f} KB"
        self.pages = pages
        self.created_at = datetime.now().isoformat()

class TestPrintSystem(unittest.TestCase):
    """Testes do sistema de impressão"""
    
    def setUp(self):
        """Configuração dos testes"""
        # Cria diretório temporário para os testes
        self.test_dir = tempfile.mkdtemp()
        
        # Cria PDF de teste
        self.test_pdf_path = os.path.join(self.test_dir, "test_document.pdf")
        self._create_test_pdf()
        
        # Cria configuração
        self.config = AppConfig(self.test_dir)
        
        # Configura impressoras de teste
        self.printers = [
            {
                "id": "printer1",
                "name": "Impressora de Teste 1",
                "ip": "192.168.1.100",
                "mac_address": "00:11:22:33:44:55",
                "model": "HP LaserJet Test",
                "location": "Sala de Testes"
            },
            {
                "id": "printer2",
                "name": "Impressora de Teste 2",
                "ip": "192.168.1.101",
                "mac_address": "55:44:33:22:11:00",
                "model": "Epson Test",
                "location": "Recepção"
            }
        ]
        
        # Salva as impressoras na configuração
        self.config.set_printers(self.printers)
        
        # Cria documento de teste
        self.document = MockDocument("Documento de Teste", self.test_pdf_path)
        
        # Cria impressora de teste
        self.printer = Printer(self.printers[0])
    
    def tearDown(self):
        """Limpeza após os testes"""
        # Remove o diretório temporário
        shutil.rmtree(self.test_dir)
    
    def _create_test_pdf(self):
        """Cria um arquivo PDF de teste simples"""
        # Conteúdo mínimo para um PDF válido
        pdf_content = b'''%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000102 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
174
%%EOF'''
        
        # Escreve o conteúdo no arquivo
        with open(self.test_pdf_path, 'wb') as f:
            f.write(pdf_content)
    
    def test_create_print_options(self):
        """Testa a criação de opções de impressão"""
        options = PrintOptions()
        
        # Verifica valores padrão
        self.assertEqual(options.color_mode, ColorMode.AUTO)
        self.assertEqual(options.duplex, Duplex.SIMPLES)
        self.assertEqual(options.quality, Quality.NORMAL)
        self.assertEqual(options.copies, 1)
        self.assertEqual(options.orientation, "portrait")
        
        # Testa configurações personalizadas
        options.color_mode = ColorMode.COLORIDO
        options.duplex = Duplex.DUPLEX_LONGO
        options.quality = Quality.ALTA
        options.copies = 2
        options.orientation = "landscape"
        
        self.assertEqual(options.color_mode, ColorMode.COLORIDO)
        self.assertEqual(options.duplex, Duplex.DUPLEX_LONGO)
        self.assertEqual(options.quality, Quality.ALTA)
        self.assertEqual(options.copies, 2)
        self.assertEqual(options.orientation, "landscape")
    
    def test_create_print_job(self):
        """Testa a criação de trabalho de impressão"""
        job = PrintJob.create(
            document_path=self.test_pdf_path,
            document_name="Documento de Teste",
            printer_name="Impressora de Teste",
            printer_id="printer1",
            printer_ip="192.168.1.100"
        )
        
        # Verifica os atributos básicos
        self.assertIsNotNone(job.job_id)
        self.assertEqual(job.document_path, self.test_pdf_path)
        self.assertEqual(job.document_name, "Documento de Teste")
        self.assertEqual(job.printer_name, "Impressora de Teste")
        self.assertEqual(job.printer_id, "printer1")
        self.assertEqual(job.printer_ip, "192.168.1.100")
        self.assertEqual(job.status, PrintJobStatus.PENDING)
        
        # Testa alterações de status
        job.set_processing()
        self.assertEqual(job.status, PrintJobStatus.PROCESSING)
        self.assertIsNotNone(job.started_at)
        
        job.set_completed(10, 10)
        self.assertEqual(job.status, PrintJobStatus.COMPLETED)
        self.assertEqual(job.total_pages, 10)
        self.assertEqual(job.completed_pages, 10)
        self.assertIsNotNone(job.completed_at)
        
        # Testa conversão para dicionário
        job_dict = job.to_dict()
        self.assertIsInstance(job_dict, dict)
        self.assertEqual(job_dict["job_id"], job.job_id)
        self.assertEqual(job_dict["status"], job.status.value)
        
        # Testa criação a partir de dicionário
        job2 = PrintJob.from_dict(job_dict)
        self.assertEqual(job2.job_id, job.job_id)
        self.assertEqual(job2.status, job.status)
    
    def test_config_print_jobs(self):
        """Testa o armazenamento de trabalhos de impressão na configuração"""
        # Cria um trabalho de teste
        job = PrintJob.create(
            document_path=self.test_pdf_path,
            document_name="Documento de Teste",
            printer_name="Impressora de Teste",
            printer_id="printer1",
            printer_ip="192.168.1.100"
        )
        
        # Converte para dicionário
        job_dict = job.to_dict()
        
        # Adiciona à configuração
        self.config.add_print_job(job_dict)
        
        # Verifica se foi adicionado
        jobs = self.config.get_print_jobs()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["job_id"], job.job_id)
        
        # Atualiza o trabalho
        job.set_processing()
        self.config.update_print_job(job.job_id, {"status": job.status.value})
        
        # Verifica se foi atualizado
        jobs = self.config.get_print_jobs()
        self.assertEqual(jobs[0]["status"], "processing")
        
        # Conclui o trabalho
        job.set_completed(5, 5)
        job_dict = job.to_dict()
        self.config.add_print_job(job_dict)
        
        # Remove o trabalho
        self.config.remove_print_job(job.job_id)
        
        # Verifica se foi removido da lista ativa
        jobs = self.config.get_print_jobs()
        self.assertEqual(len(jobs), 0)
        
        # Verifica se foi adicionado ao histórico
        history = self.config.get_print_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["job_id"], job.job_id)
        
        # Limpa o histórico
        self.config.clear_print_history()
        history = self.config.get_print_history()
        self.assertEqual(len(history), 0)

class TestIPPPrinter(unittest.TestCase):
    """Teste simulado da impressora IPP"""
    
    def setUp(self):
        """Configuração dos testes"""
        # Cria um mock para a classe IPPPrinter que não tentará conectar a nenhum servidor real
        self.original_send_ipp_request = IPPPrinter._send_ipp_request
        
        # Substitui o método por um mock
        IPPPrinter._send_ipp_request = lambda self, url, attributes, document_data: (
            True, {"job_id": 12345, "method": "pdf", "http_status": 200, "ipp_status": "0x0001"}
        )
        
        # Cria diretório temporário para os testes
        self.test_dir = tempfile.mkdtemp()
        
        # Cria PDF de teste
        self.test_pdf_path = os.path.join(self.test_dir, "test_document.pdf")
        
        # Conteúdo mínimo para um PDF válido
        pdf_content = b'''%PDF-1.0
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj
3 0 obj<</Type/Page/MediaBox[0 0 595 842]/Resources<<>>>>endobj
xref
0 4
0000000000 65535 f
0000000010 00000 n
0000000053 00000 n
0000000102 00000 n
trailer<</Size 4/Root 1 0 R>>
startxref
174
%%EOF'''
        
        # Escreve o conteúdo no arquivo
        with open(self.test_pdf_path, 'wb') as f:
            f.write(pdf_content)
    
    def tearDown(self):
        """Limpeza após os testes"""
        # Restaura o método original
        IPPPrinter._send_ipp_request = self.original_send_ipp_request
        
        # Remove o diretório temporário
        shutil.rmtree(self.test_dir)
    
    def test_print_file(self):
        """Testa a impressão de arquivo"""
        # Cria uma instância da impressora
        printer = IPPPrinter("192.168.1.100")
        
        # Cria opções de impressão
        options = PrintOptions()
        options.color_mode = ColorMode.COLORIDO
        options.duplex = Duplex.DUPLEX_LONGO
        
        # Tenta "imprimir" o arquivo
        success, result = printer.print_file(self.test_pdf_path, options, "Teste de Impressão")
        
        # Verifica o resultado
        self.assertTrue(success)
        self.assertEqual(result["job_id"], 12345)
        self.assertEqual(result["method"], "pdf")

# Função para executar os testes
def run_tests():
    """Executa os testes unitários"""
    # Cria e executa o teste
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestPrintSystem))
    suite.addTest(unittest.makeSuite(TestIPPPrinter))
    
    runner = unittest.TextTestRunner(verbosity=2)
    return runner.run(suite)

if __name__ == "__main__":
    run_tests()
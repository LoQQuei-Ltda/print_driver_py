"""
Utilitários para manipulação de PDF
"""

import os
import shutil
import logging
import tempfile
from pypdf import PdfReader, PdfWriter

logger = logging.getLogger("PrintManagementSystem.Utils.PDF")

class PDFUtils:
    """Utilitários para manipulação de arquivos PDF"""
    
    @staticmethod
    def get_pdf_info(pdf_path):
        """
        Obtém informações do arquivo PDF
        
        Args:
            pdf_path (str): Caminho do arquivo PDF
            
        Returns:
            dict: Informações do PDF
            
        Raises:
            FileNotFoundError: Se o arquivo não for encontrado
            ValueError: Se o arquivo não for um PDF válido
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")
        
        try:
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                
                # Obtém informações básicas
                info = {
                    "pages": len(reader.pages),
                    "encrypted": reader.is_encrypted,
                    "metadata": {}
                }
                
                # Obtém metadados
                if reader.metadata:
                    metadata = reader.metadata
                    for key in metadata:
                        if key.startswith('/'):
                            clean_key = key[1:]  # Remove a barra inicial
                            info["metadata"][clean_key] = str(metadata[key])
                
                # Obtém tamanho das páginas (primeira página como referência)
                if len(reader.pages) > 0:
                    page = reader.pages[0]
                    if '/MediaBox' in page:
                        media_box = page['/MediaBox']
                        info["width"] = float(media_box[2])
                        info["height"] = float(media_box[3])
                
                return info
                
        except Exception as e:
            logger.error(f"Erro ao obter informações do PDF: {str(e)}")
            raise ValueError(f"Erro ao processar o PDF: {str(e)}")
    
    @staticmethod
    def split_pdf(pdf_path, output_dir=None):
        """
        Divide um arquivo PDF em páginas individuais
        
        Args:
            pdf_path (str): Caminho do arquivo PDF
            output_dir (str, optional): Diretório para salvar as páginas
            
        Returns:
            list: Lista de caminhos dos arquivos gerados
            
        Raises:
            FileNotFoundError: Se o arquivo não for encontrado
            ValueError: Se o arquivo não for um PDF válido
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")
        
        if not output_dir:
            output_dir = tempfile.mkdtemp()
        else:
            os.makedirs(output_dir, exist_ok=True)
        
        try:
            with open(pdf_path, 'rb') as f:
                reader = PdfReader(f)
                
                output_files = []
                
                base_name = os.path.splitext(os.path.basename(pdf_path))[0]
                
                for i, page in enumerate(reader.pages):
                    output_file = os.path.join(output_dir, f"{base_name}_page_{i+1}.pdf")
                    
                    writer = PdfWriter()
                    writer.add_page(page)
                    
                    with open(output_file, 'wb') as out_f:
                        writer.write(out_f)
                    
                    output_files.append(output_file)
                
                return output_files
                
        except Exception as e:
            logger.error(f"Erro ao dividir PDF: {str(e)}")
            raise ValueError(f"Erro ao processar o PDF: {str(e)}")
    
    @staticmethod
    def merge_pdfs(pdf_paths, output_path):
        """
        Mescla vários arquivos PDF em um único arquivo
        
        Args:
            pdf_paths (list): Lista de caminhos de arquivos PDF
            output_path (str): Caminho do arquivo PDF de saída
            
        Returns:
            str: Caminho do arquivo PDF mesclado
            
        Raises:
            FileNotFoundError: Se algum arquivo não for encontrado
            ValueError: Se algum arquivo não for um PDF válido
        """
        if not pdf_paths:
            raise ValueError("Lista de arquivos PDF vazia")
        
        for path in pdf_paths:
            if not os.path.exists(path):
                raise FileNotFoundError(f"Arquivo PDF não encontrado: {path}")
        
        try:
            writer = PdfWriter()
            
            for path in pdf_paths:
                with open(path, 'rb') as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        writer.add_page(page)
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(output_path, 'wb') as f:
                writer.write(f)
            
            return output_path
                
        except Exception as e:
            logger.error(f"Erro ao mesclar PDFs: {str(e)}")
            raise ValueError(f"Erro ao processar os PDFs: {str(e)}")
    
    @staticmethod
    def copy_pdf_to_directory(pdf_path, dest_dir, new_name=None):
        """
        Copia um arquivo PDF para um diretório
        
        Args:
            pdf_path (str): Caminho do arquivo PDF
            dest_dir (str): Diretório de destino
            new_name (str, optional): Novo nome para o arquivo
            
        Returns:
            str: Caminho do arquivo copiado
            
        Raises:
            FileNotFoundError: Se o arquivo não for encontrado
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"Arquivo PDF não encontrado: {pdf_path}")
        
        os.makedirs(dest_dir, exist_ok=True)
        
        if new_name:
            dest_path = os.path.join(dest_dir, new_name)
            if not dest_path.lower().endswith('.pdf'):
                dest_path += '.pdf'
        else:
            dest_path = os.path.join(dest_dir, os.path.basename(pdf_path))
        
        try:
            shutil.copy2(pdf_path, dest_path)
            return dest_path
        except Exception as e:
            logger.error(f"Erro ao copiar PDF: {str(e)}")
            raise IOError(f"Erro ao copiar o arquivo: {str(e)}")
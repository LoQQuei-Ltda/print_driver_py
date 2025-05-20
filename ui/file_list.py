"""
Componente para exibição e gerenciamento de arquivos PDF
"""
import os
import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QPushButton, QMessageBox, QMenu, QDialog,
    QFileDialog, QSplitter, QComboBox, QFrame
)
from PySide6.QtCore import Qt, Signal, Slot, QSize, QUrl
from PySide6.QtGui import QIcon, QDesktopServices, QDesktopServices

from core.pdf_monitor import PDFMonitor, PDFFile
from core.printer_manager import PrinterManager

logger = logging.getLogger("VirtualPrinter.FileList")

class FileList(QWidget):
    """Widget para exibição e gerenciamento de arquivos PDF"""
    
    file_selected = Signal(str)  # Sinal emitido quando um arquivo é selecionado
    
    def __init__(self, pdf_monitor, printer_manager, parent=None):
        """Inicializa o widget de lista de arquivos"""
        super().__init__(parent)
        self.pdf_monitor = pdf_monitor
        self.printer_manager = printer_manager
        
        self._setup_ui()
        
        # Registrar para eventos de novos arquivos
        self.pdf_monitor.register_new_file_callback(self._on_new_file)
    
    def _setup_ui(self):
        """Configura a interface de usuário"""
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Título
        title_layout = QHBoxLayout()
        
        title_label = QLabel("Arquivos Impressos")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        title_layout.addWidget(title_label)
        
        self.file_count_label = QLabel("(0 arquivos)")
        title_layout.addWidget(self.file_count_label)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)
        
        # Divisor entre lista e visualizador (futuro)
        splitter = QSplitter(Qt.Horizontal)
        
        # Lista de arquivos
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        files_layout.setContentsMargins(0, 0, 0, 0)
        
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.SingleSelection)
        self.files_list.itemClicked.connect(self._on_file_clicked)
        self.files_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_list.customContextMenuRequested.connect(self._show_context_menu)
        self.files_list.itemDoubleClicked.connect(self._on_open_file)
        files_layout.addWidget(self.files_list)
        
        splitter.addWidget(files_widget)
        
        # Placeholder para visualizador de PDF (futuro)
        preview_widget = QFrame()
        preview_widget.setFrameShape(QFrame.StyledPanel)
        preview_layout = QVBoxLayout(preview_widget)
        
        preview_label = QLabel("Visualização não disponível")
        preview_label.setAlignment(Qt.AlignCenter)
        preview_layout.addWidget(preview_label)
        
        splitter.addWidget(preview_widget)
        
        # Definir proporções iniciais do splitter
        splitter.setSizes([200, 0])  # Inicialmente, não mostrar o visualizador
        
        layout.addWidget(splitter)
        
        # Botões de ação
        actions_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Abrir")
        self.print_button = QPushButton("Imprimir")
        self.delete_button = QPushButton("Excluir")
        
        self.open_button.clicked.connect(self._on_open_file)
        self.print_button.clicked.connect(self._on_print_file)
        self.delete_button.clicked.connect(self._on_delete_file)
        
        # Desabilitar botões inicialmente
        self.open_button.setEnabled(False)
        self.print_button.setEnabled(False)
        self.delete_button.setEnabled(False)
        
        actions_layout.addWidget(self.open_button)
        actions_layout.addWidget(self.print_button)
        actions_layout.addWidget(self.delete_button)
        
        # Botão de atualização no canto direito
        actions_layout.addStretch()
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self.refresh_files)
        actions_layout.addWidget(self.refresh_button)
        
        layout.addLayout(actions_layout)
        
        # Carregar dados iniciais
        self.refresh_files()
    
    def refresh_files(self):
        """Atualiza a lista de arquivos PDF"""
        # Salvar o item selecionado atual
        current_item = self.files_list.currentItem()
        current_path = current_item.data(Qt.UserRole) if current_item else None
        
        # Limpar a lista
        self.files_list.clear()
        
        # Obter arquivos atualizados
        pdf_files = self.pdf_monitor.refresh_files()
        
        # Atualizar contador
        self.file_count_label.setText(f"({len(pdf_files)} arquivo{'s' if len(pdf_files) != 1 else ''})")
        
        # Preencher a lista
        for pdf_file in pdf_files:
            item = FileListItem(pdf_file)
            self.files_list.addItem(item)
            
            # Restaurar seleção
            if current_path and str(pdf_file.path) == current_path:
                self.files_list.setCurrentItem(item)
        
        # Atualizar estado dos botões
        has_selection = self.files_list.currentItem() is not None
        self.open_button.setEnabled(has_selection)
        self.print_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
    
    def _on_file_clicked(self, item):
        """Manipula o clique em um arquivo na lista"""
        if item:
            file_path = item.data(Qt.UserRole)
            self.file_selected.emit(file_path)
            
            # Habilitar botões
            self.open_button.setEnabled(True)
            self.print_button.setEnabled(True)
            self.delete_button.setEnabled(True)
    
    def _show_context_menu(self, position):
        """Exibe o menu de contexto para a lista de arquivos"""
        item = self.files_list.itemAt(position)
        if not item:
            return
        
        context_menu = QMenu(self)
        
        open_action = context_menu.addAction("Abrir")
        print_action = context_menu.addAction("Imprimir")
        save_as_action = context_menu.addAction("Salvar Como...")
        context_menu.addSeparator()
        delete_action = context_menu.addAction("Excluir")
        
        action = context_menu.exec(self.files_list.mapToGlobal(position))
        
        if action == open_action:
            self._on_open_file()
        elif action == print_action:
            self._on_print_file()
        elif action == save_as_action:
            self._on_save_as()
        elif action == delete_action:
            self._on_delete_file()
    
    def _on_open_file(self):
        """Abre o arquivo PDF selecionado"""
        item = self.files_list.currentItem()
        if not item:
            return
        
        file_path = item.data(Qt.UserRole)
        
        # Usar o visualizador padrão do sistema
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        logger.info(f"Arquivo aberto: {os.path.basename(file_path)}")
    
    def _on_print_file(self):
        """Imprime o arquivo PDF selecionado"""
        item = self.files_list.currentItem()
        if not item:
            return
        
        file_path = item.data(Qt.UserRole)
        
        # Diálogo para selecionar impressora
        dialog = PrinterSelectDialog(self.printer_manager, self)
        if dialog.exec():
            printer_id = dialog.get_selected_printer()
            if self.printer_manager.print_file(file_path, printer_id):
                logger.info(f"Arquivo enviado para impressão: {os.path.basename(file_path)}")
                QMessageBox.information(self, "Impressão", "Arquivo enviado para impressão com sucesso.")
            else:
                logger.error(f"Erro ao imprimir arquivo: {os.path.basename(file_path)}")
                QMessageBox.critical(self, "Erro de Impressão", 
                                     "Não foi possível enviar o arquivo para impressão.")
    
    def _on_save_as(self):
        """Salva o arquivo PDF com outro nome/local"""
        item = self.files_list.currentItem()
        if not item:
            return
        
        source_path = item.data(Qt.UserRole)
        file_name = os.path.basename(source_path)
        
        # Diálogo para selecionar destino
        target_path, _ = QFileDialog.getSaveFileName(
            self, "Salvar Arquivo Como", file_name, "Arquivos PDF (*.pdf)"
        )
        
        if not target_path:
            return
        
        try:
            shutil.copy2(source_path, target_path)
            logger.info(f"Arquivo salvo como: {target_path}")
            QMessageBox.information(self, "Arquivo Salvo", 
                                    f"Arquivo salvo com sucesso como:\n{target_path}")
        except Exception as e:
            logger.error(f"Erro ao salvar arquivo: {e}")
            QMessageBox.critical(self, "Erro ao Salvar", 
                                f"Não foi possível salvar o arquivo:\n{str(e)}")
    
    def _on_delete_file(self):
        """Exclui o arquivo PDF selecionado"""
        item = self.files_list.currentItem()
        if not item:
            return
        
        file_path = item.data(Qt.UserRole)
        file_name = item.text()
        
        # Confirmação
        reply = QMessageBox.question(
            self, "Confirmar Exclusão", 
            f"Tem certeza que deseja excluir o arquivo '{file_name}'?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            if self.pdf_monitor.delete_file(file_path):
                row = self.files_list.row(item)
                self.files_list.takeItem(row)
                
                # Atualizar contador
                count = self.files_list.count()
                self.file_count_label.setText(f"({count} arquivo{'s' if count != 1 else ''})")
                
                # Desabilitar botões se não houver mais seleção
                if self.files_list.currentItem() is None:
                    self.open_button.setEnabled(False)
                    self.print_button.setEnabled(False)
                    self.delete_button.setEnabled(False)
                
                logger.info(f"Arquivo excluído: {file_name}")
            else:
                logger.error(f"Erro ao excluir arquivo: {file_name}")
                QMessageBox.critical(self, "Erro ao Excluir", 
                                     "Não foi possível excluir o arquivo.")
    
    def _on_new_file(self, file_path):
        """Chamado quando um novo arquivo PDF é detectado"""
        self.refresh_files()
        
        # Selecionar o novo arquivo
        for i in range(self.files_list.count()):
            item = self.files_list.item(i)
            if item.data(Qt.UserRole) == file_path:
                self.files_list.setCurrentItem(item)
                break


class FileListItem(QListWidgetItem):
    """Item personalizado para a lista de arquivos"""
    
    def __init__(self, pdf_file):
        """Inicializa o item de arquivo"""
        super().__init__(pdf_file.name)
        
        # Definir dados do item
        self.setData(Qt.UserRole, str(pdf_file.path))
        
        # Configurar dica de ferramenta
        self.setToolTip(
            f"Nome: {pdf_file.name}\n"
            f"Tamanho: {pdf_file.size_str}\n"
            f"Criado em: {pdf_file.created_time_str}"
        )


class PrinterSelectDialog(QDialog):
    """Diálogo para selecionar impressora"""
    
    def __init__(self, printer_manager, parent=None):
        """Inicializa o diálogo de seleção de impressora"""
        super().__init__(parent)
        self.printer_manager = printer_manager
        
        self.setWindowTitle("Selecionar Impressora")
        self.setMinimumWidth(300)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura a interface de usuário"""
        layout = QVBoxLayout(self)
        
        # Label
        label = QLabel("Selecione a impressora para envio:")
        layout.addWidget(label)
        
        # Combobox de impressoras
        self.printer_combo = QComboBox()
        layout.addWidget(self.printer_combo)
        
        # Preencher combo
        for printer in self.printer_manager.get_printers():
            self.printer_combo.addItem(printer.name, printer.id)
        
        # Selecionar a impressora padrão, se houver
        if self.printer_manager.selected_printer:
            index = self.printer_combo.findData(self.printer_manager.selected_printer.id)
            if index >= 0:
                self.printer_combo.setCurrentIndex(index)
        
        # Botões
        button_layout = QHBoxLayout()
        
        self.cancel_button = QPushButton("Cancelar")
        self.print_button = QPushButton("Imprimir")
        self.print_button.setDefault(True)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.print_button)
        
        layout.addLayout(button_layout)
        
        # Conectar eventos
        self.print_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
    
    def get_selected_printer(self):
        """Retorna o ID da impressora selecionada"""
        return self.printer_combo.currentData()
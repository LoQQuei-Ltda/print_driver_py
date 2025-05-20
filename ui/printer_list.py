"""
Componente para exibição e gerenciamento de impressoras
"""
import logging
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, 
    QListWidgetItem, QPushButton, QComboBox, QCheckBox,
    QMessageBox, QMenu, QDialog, QFormLayout, QLineEdit
)
from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QIcon, QColor

from core.printer_manager import PrinterManager
from utils.api_client import get_api_client

logger = logging.getLogger("VirtualPrinter.PrinterList")

class PrinterList(QWidget):
    """Widget para exibição e gerenciamento de impressoras"""
    
    printer_selected = Signal(str)  # Sinal emitido quando uma impressora é selecionada
    
    def __init__(self, printer_manager, parent=None):
        """Inicializa o widget de lista de impressoras"""
        super().__init__(parent)
        self.printer_manager = printer_manager
        self.api_client = get_api_client()
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura a interface de usuário"""
        # Layout principal
        layout = QVBoxLayout(self)
        
        # Título
        title_label = QLabel("Impressoras Disponíveis")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        
        # Lista de impressoras
        self.printers_list = QListWidget()
        self.printers_list.setSelectionMode(QListWidget.SingleSelection)
        self.printers_list.itemClicked.connect(self._on_printer_clicked)
        self.printers_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.printers_list.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.printers_list)
        
        # Botões
        button_layout = QHBoxLayout()
        
        self.refresh_button = QPushButton("Atualizar")
        self.refresh_button.clicked.connect(self.refresh_printers)
        
        self.details_button = QPushButton("Detalhes")
        self.details_button.clicked.connect(self._show_printer_details)
        self.details_button.setEnabled(False)
        
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.details_button)
        button_layout.addStretch()
        
        layout.addLayout(button_layout)
        
        # Configuração de impressão automática
        auto_layout = QHBoxLayout()
        
        self.auto_print_check = QCheckBox("Impressão automática")
        self.auto_print_check.stateChanged.connect(self._on_auto_print_changed)
        
        self.printer_combo = QComboBox()
        self.printer_combo.setMinimumWidth(200)
        self.printer_combo.currentIndexChanged.connect(self._on_selected_printer_changed)
        
        auto_layout.addWidget(self.auto_print_check)
        auto_layout.addWidget(self.printer_combo)
        auto_layout.addStretch()
        
        layout.addLayout(auto_layout)
        
        # Carregar dados iniciais
        self.refresh_printers()
    
    def refresh_printers(self):
        """Atualiza a lista de impressoras"""
        # Limpar listas
        self.printers_list.clear()
        self.printer_combo.clear()
        
        # Obter impressoras atualizadas
        printers = self.printer_manager.refresh_printers()
        
        # Preencher lista de impressoras
        for printer in printers:
            item = PrinterListItem(printer)
            self.printers_list.addItem(item)
            
            # Adicionar ao combobox
            self.printer_combo.addItem(printer.name, printer.id)
        
        # Configurar estado de impressão automática
        self.auto_print_check.setChecked(self.printer_manager.auto_print_enabled)
        
        # Selecionar impressora atual
        if self.printer_manager.selected_printer:
            index = self.printer_combo.findData(self.printer_manager.selected_printer.id)
            if index >= 0:
                self.printer_combo.setCurrentIndex(index)
    
    def _on_printer_clicked(self, item):
        """Manipula o clique em uma impressora na lista"""
        if item:
            printer_id = item.printer.id
            self.printer_selected.emit(printer_id)
            self.details_button.setEnabled(True)
    
    def _show_context_menu(self, position):
        """Exibe o menu de contexto para a lista de impressoras"""
        item = self.printers_list.itemAt(position)
        if not item:
            return
        
        context_menu = QMenu(self)
        
        details_action = context_menu.addAction("Detalhes")
        set_default_action = context_menu.addAction("Definir como Padrão")
        
        action = context_menu.exec(self.printers_list.mapToGlobal(position))
        
        if action == details_action:
            self._show_printer_details()
        elif action == set_default_action:
            self._set_as_default_printer(item)
    
    def _show_printer_details(self):
        """Exibe detalhes da impressora selecionada"""
        item = self.printers_list.currentItem()
        if not item:
            return
        
        printer = item.printer
        
        # Em um cenário real, obter status atualizado da API
        try:
            printer_status = self.api_client.get_printer_status(printer.id)
        except Exception as e:
            logger.error(f"Erro ao obter status da impressora: {e}")
            printer_status = {"status": "unknown"}
        
        # Criar diálogo para exibir detalhes
        dialog = PrinterDetailsDialog(printer, printer_status, self)
        dialog.exec()
    
    def _set_as_default_printer(self, item):
        """Define a impressora como padrão para impressão automática"""
        printer = item.printer
        self.printer_manager.set_selected_printer(printer.id)
        
        # Atualizar a interface
        index = self.printer_combo.findData(printer.id)
        if index >= 0:
            self.printer_combo.setCurrentIndex(index)
    
    def _on_auto_print_changed(self, state):
        """Trata mudança no estado da impressão automática"""
        enabled = state == Qt.Checked
        self.printer_manager.set_auto_print(enabled)
        self.printer_combo.setEnabled(enabled)
    
    def _on_selected_printer_changed(self, index):
        """Trata mudança na impressora selecionada"""
        if index < 0:
            return
        
        printer_id = self.printer_combo.itemData(index)
        self.printer_manager.set_selected_printer(printer_id)


class PrinterListItem(QListWidgetItem):
    """Item personalizado para a lista de impressoras"""
    
    def __init__(self, printer):
        """Inicializa o item de impressora"""
        super().__init__(printer.name)
        self.printer = printer
        
        # Definir dados do item
        self.setData(Qt.UserRole, printer.id)
        
        # Configurar dica de ferramenta
        self.setToolTip(
            f"ID: {printer.id}\n"
            f"MAC: {printer.mac_address}\n"
            f"IP: {printer.ip_address or 'N/A'}\n"
            f"Local: {printer.location or 'N/A'}"
        )
        
        # Definir ícone baseado no status (se disponível)
        if hasattr(printer, 'is_online'):
            if printer.is_online:
                self.setForeground(QColor("green"))
            else:
                self.setForeground(QColor("red"))


class PrinterDetailsDialog(QDialog):
    """Diálogo para exibir detalhes da impressora"""
    
    def __init__(self, printer, status, parent=None):
        """Inicializa o diálogo de detalhes"""
        super().__init__(parent)
        self.printer = printer
        self.status = status
        
        self.setWindowTitle(f"Detalhes da Impressora: {printer.name}")
        self.setMinimumWidth(400)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Configura a interface do diálogo"""
        layout = QVBoxLayout(self)
        
        # Formulário de detalhes
        form_layout = QFormLayout()
        
        # Informações básicas
        form_layout.addRow("Nome:", QLabel(self.printer.name))
        form_layout.addRow("ID:", QLabel(self.printer.id))
        form_layout.addRow("Endereço MAC:", QLabel(self.printer.mac_address))
        
        if self.printer.ip_address:
            form_layout.addRow("Endereço IP:", QLabel(self.printer.ip_address))
        
        if self.printer.location:
            form_layout.addRow("Localização:", QLabel(self.printer.location))
        
        # Informações de status
        status_color = QColor("green") if self.status.get("status") == "online" else QColor("red")
        status_label = QLabel(self.status.get("status", "Desconhecido").capitalize())
        status_label.setStyleSheet(f"color: {status_color.name()};")
        form_layout.addRow("Status:", status_label)
        
        if "jobs_pending" in self.status:
            form_layout.addRow("Trabalhos pendentes:", QLabel(str(self.status["jobs_pending"])))
        
        if "last_activity" in self.status:
            form_layout.addRow("Última atividade:", QLabel(self.status["last_activity"]))
        
        if "toner_level" in self.status:
            toner_level = self.status["toner_level"]
            toner_label = QLabel(f"{toner_level}%")
            if toner_level < 10:
                toner_label.setStyleSheet("color: red;")
            elif toner_level < 30:
                toner_label.setStyleSheet("color: orange;")
            form_layout.addRow("Nível de toner:", toner_label)
        
        layout.addLayout(form_layout)
        
        # Botão de fechar
        close_button = QPushButton("Fechar")
        close_button.clicked.connect(self.accept)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
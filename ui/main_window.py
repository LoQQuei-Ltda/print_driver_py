"""
Janela principal da aplicação
"""
import os
import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QLabel, QPushButton, QListWidget, QListWidgetItem, QComboBox,
    QCheckBox, QMessageBox, QMenu, QFileDialog, QSplitter,
    QStatusBar, QToolBar, QDialog, QSizePolicy, QLineEdit, QGroupBox
)
from PySide6.QtGui import QAction
from PySide6.QtCore import Qt, QSize, Signal, Slot, QTimer, QUrl
from PySide6.QtGui import QIcon, QPixmap, QFont, QDesktopServices

from core.auth import get_auth_instance
from core.printer_manager import PrinterManager
from core.pdf_monitor import PDFMonitor

logger = logging.getLogger("VirtualPrinter.MainWindow")

class MainWindow(QMainWindow):
    """Janela principal da aplicação"""
    
    def __init__(self, printer_manager, pdf_monitor, parent=None):
        """Inicializa a janela principal"""
        super().__init__(parent)
        self.auth = get_auth_instance()
        self.printer_manager = printer_manager
        self.pdf_monitor = pdf_monitor
        
        # Configurar a janela
        self.setWindowTitle("Impressora Virtual")
        self.setMinimumSize(800, 600)
        
        # Configurar status bar
        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Pronto")
        
        # Criar interface
        self._setup_ui()
        
        # Registrar para eventos de novos arquivos
        self.pdf_monitor.register_new_file_callback(self._on_new_file)
        
        # Iniciar timer para atualização da lista de impressoras
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_data)
        self.refresh_timer.start(60000)  # Atualiza a cada minuto
    
    def _setup_ui(self):
        """Configura a interface de usuário"""
        # Widget central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout principal
        main_layout = QVBoxLayout(central_widget)
        
        # Barra de ferramentas
        self._create_toolbar()
        
        # Tabs para diferentes seções
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Tab de arquivos
        self._create_files_tab()
        
        # Tab de impressoras
        self._create_printers_tab()
        
        # Tab de configurações
        self._create_settings_tab()
        
        # Inicializar dados
        self._refresh_data()
    
    def _create_toolbar(self):
        """Cria a barra de ferramentas"""
        toolbar = QToolBar("Barra de Ferramentas")
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(toolbar)
        
        # Ação de atualização
        refresh_action = QAction("Atualizar", self)
        refresh_action.setStatusTip("Atualizar listas de arquivos e impressoras")
        refresh_action.triggered.connect(self._refresh_data)
        toolbar.addAction(refresh_action)
        
        toolbar.addSeparator()
        
        # Informações do usuário
        username = self.auth.get_current_user()["username"]
        user_label = QLabel(f"Usuário: {username}")
        user_label.setStyleSheet("margin-left: 10px; font-weight: bold;")
        toolbar.addWidget(user_label)
        
        # Espaçador flexível
        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Expanding, 
            QSizePolicy.Preferred
        )
        toolbar.addWidget(spacer)
        
        # Ação de logout
        logout_action = QAction("Sair", self)
        logout_action.setStatusTip("Encerrar sessão")
        logout_action.triggered.connect(self._on_logout)
        toolbar.addAction(logout_action)
    
    def _create_files_tab(self):
        """Cria a tab de arquivos PDF"""
        files_widget = QWidget()
        files_layout = QVBoxLayout(files_widget)
        
        # Título
        title_label = QLabel("Arquivos Impressos")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        files_layout.addWidget(title_label)
        
        # Lista de arquivos
        self.files_list = QListWidget()
        self.files_list.setSelectionMode(QListWidget.SingleSelection)
        self.files_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.files_list.customContextMenuRequested.connect(self._on_file_context_menu)
        files_layout.addWidget(self.files_list)
        
        # Botões de ação
        actions_layout = QHBoxLayout()
        
        self.open_button = QPushButton("Abrir")
        self.print_button = QPushButton("Imprimir")
        self.delete_button = QPushButton("Excluir")
        
        self.open_button.clicked.connect(self._on_open_file)
        self.print_button.clicked.connect(self._on_print_file)
        self.delete_button.clicked.connect(self._on_delete_file)
        
        actions_layout.addWidget(self.open_button)
        actions_layout.addWidget(self.print_button)
        actions_layout.addWidget(self.delete_button)
        
        files_layout.addLayout(actions_layout)
        
        # Adicionar à tab
        self.tabs.addTab(files_widget, "Arquivos")
    
    def _create_printers_tab(self):
        """Cria a tab de impressoras"""
        printers_widget = QWidget()
        printers_layout = QVBoxLayout(printers_widget)
        
        # Título
        title_label = QLabel("Impressoras Disponíveis")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        printers_layout.addWidget(title_label)
        
        # Lista de impressoras
        self.printers_list = QListWidget()
        self.printers_list.setSelectionMode(QListWidget.SingleSelection)
        printers_layout.addWidget(self.printers_list)
        
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
        
        printers_layout.addLayout(auto_layout)
        
        # Adicionar à tab
        self.tabs.addTab(printers_widget, "Impressoras")
    
    def _create_settings_tab(self):
        """Cria a tab de configurações"""
        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)
        
        # Título
        title_label = QLabel("Configurações")
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        settings_layout.addWidget(title_label)
        
        # Diretório de saída
        output_dir_layout = QHBoxLayout()
        output_dir_label = QLabel("Diretório de arquivos:")
        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setReadOnly(True)
        self.output_dir_edit.setText(str(self.pdf_monitor.output_dir))
        self.output_dir_button = QPushButton("Alterar")
        self.output_dir_button.clicked.connect(self._on_change_output_dir)
        
        output_dir_layout.addWidget(output_dir_label)
        output_dir_layout.addWidget(self.output_dir_edit)
        output_dir_layout.addWidget(self.output_dir_button)
        
        settings_layout.addLayout(output_dir_layout)
        
        # Informações do usuário
        user_group = QGroupBox("Informações do Usuário")
        user_layout = QVBoxLayout(user_group)
        
        user = self.auth.get_current_user()
        
        username_label = QLabel(f"Nome de usuário: {user['username']}")
        email_label = QLabel(f"Email: {user.get('email', 'Não informado')}")
        
        user_layout.addWidget(username_label)
        user_layout.addWidget(email_label)
        
        settings_layout.addWidget(user_group)
        
        # Espaçador
        settings_layout.addStretch()
        
        # Adicionar à tab
        self.tabs.addTab(settings_widget, "Configurações")
    
    def _refresh_data(self):
        """Atualiza os dados exibidos na interface"""
        # Atualizar lista de arquivos
        self._update_files_list()
        
        # Atualizar lista de impressoras
        self._update_printers_list()
        
        # Atualizar status
        self.status_bar.showMessage("Dados atualizados")
    
    def _update_files_list(self):
        """Atualiza a lista de arquivos PDF"""
        # Salvar o item selecionado atual
        current_item = self.files_list.currentItem()
        current_path = current_item.data(Qt.UserRole) if current_item else None
        
        # Limpar a lista
        self.files_list.clear()
        
        # Obter arquivos atualizados
        pdf_files = self.pdf_monitor.refresh_files()
        
        # Preencher a lista
        for pdf_file in pdf_files:
            item = QListWidgetItem(pdf_file.name)
            item.setData(Qt.UserRole, str(pdf_file.path))
            item.setToolTip(f"Tamanho: {pdf_file.size_str}\nCriado em: {pdf_file.created_time_str}")
            self.files_list.addItem(item)
            
            # Restaurar seleção
            if current_path and str(pdf_file.path) == current_path:
                self.files_list.setCurrentItem(item)
    
    def _update_printers_list(self):
        """Atualiza a lista de impressoras"""
        # Limpar listas
        self.printers_list.clear()
        self.printer_combo.clear()
        
        # Obter impressoras atualizadas
        printers = self.printer_manager.refresh_printers()
        
        # Preencher lista de impressoras
        for printer in printers:
            item = QListWidgetItem(printer.name)
            item.setData(Qt.UserRole, printer.id)
            item.setToolTip(f"MAC: {printer.mac_address}\nIP: {printer.ip_address}\nLocal: {printer.location}")
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
    
    def _on_file_context_menu(self, position):
        """Exibe o menu de contexto para a lista de arquivos"""
        item = self.files_list.itemAt(position)
        if not item:
            return
        
        context_menu = QMenu(self)
        
        open_action = context_menu.addAction("Abrir")
        print_action = context_menu.addAction("Imprimir")
        context_menu.addSeparator()
        delete_action = context_menu.addAction("Excluir")
        
        action = context_menu.exec(self.files_list.mapToGlobal(position))
        
        if action == open_action:
            self._on_open_file()
        elif action == print_action:
            self._on_print_file()
        elif action == delete_action:
            self._on_delete_file()
    
    def _on_open_file(self):
        """Abre o arquivo PDF selecionado"""
        item = self.files_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Nenhum Arquivo", "Selecione um arquivo para abrir.")
            return
        
        file_path = item.data(Qt.UserRole)
        
        # Usar o visualizador padrão do sistema
        QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        self.status_bar.showMessage(f"Arquivo aberto: {os.path.basename(file_path)}")
    
    def _on_print_file(self):
        """Imprime o arquivo PDF selecionado"""
        item = self.files_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Nenhum Arquivo", 
                                "Selecione um arquivo para imprimir.")
            return
        
        file_path = item.data(Qt.UserRole)
        
        # Diálogo para selecionar impressora
        dialog = PrinterSelectDialog(self.printer_manager, self)
        if dialog.exec():
            printer_id = dialog.get_selected_printer()
            if self.printer_manager.print_file(file_path, printer_id):
                self.status_bar.showMessage("Arquivo enviado para impressão")
            else:
                QMessageBox.critical(self, "Erro de Impressão", 
                                     "Não foi possível enviar o arquivo para impressão.")
    
    def _on_delete_file(self):
        """Exclui o arquivo PDF selecionado"""
        item = self.files_list.currentItem()
        if not item:
            QMessageBox.warning(self, "Nenhum Arquivo", 
                                "Selecione um arquivo para excluir.")
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
                self.status_bar.showMessage(f"Arquivo excluído: {file_name}")
            else:
                QMessageBox.critical(self, "Erro ao Excluir", 
                                     "Não foi possível excluir o arquivo.")
    
    def _on_auto_print_changed(self, state):
        """Trata mudança no estado da impressão automática"""
        enabled = state == Qt.Checked
        self.printer_manager.set_auto_print(enabled)
        self.printer_combo.setEnabled(enabled)
        
        if enabled:
            self.status_bar.showMessage("Impressão automática ativada")
        else:
            self.status_bar.showMessage("Impressão automática desativada")
    
    def _on_selected_printer_changed(self, index):
        """Trata mudança na impressora selecionada"""
        if index < 0:
            return
        
        printer_id = self.printer_combo.itemData(index)
        self.printer_manager.set_selected_printer(printer_id)
        
        printer = self.printer_manager.get_printer_by_id(printer_id)
        if printer:
            self.status_bar.showMessage(f"Impressora padrão definida: {printer.name}")
    
    def _on_change_output_dir(self):
        """Altera o diretório de saída dos PDFs"""
        current_dir = self.pdf_monitor.output_dir
        new_dir = QFileDialog.getExistingDirectory(
            self, "Selecionar Diretório de Saída", 
            str(current_dir)
        )
        
        if new_dir:
            # TODO: Implementar a mudança de diretório
            QMessageBox.information(
                self, "Funcionalidade Não Implementada",
                "A mudança de diretório será implementada em versão futura."
            )
            self.status_bar.showMessage(f"Diretório de saída: {current_dir}")
    
    def _on_new_file(self, file_path):
        """Chamado quando um novo arquivo PDF é detectado"""
        self._update_files_list()
        
        file_name = os.path.basename(file_path)
        self.status_bar.showMessage(f"Novo arquivo criado: {file_name}")
        
        # Verificar se impressão automática está ativada
        if self.printer_manager.auto_print_enabled and self.printer_manager.selected_printer:
            printer = self.printer_manager.selected_printer
            if self.printer_manager.print_file(file_path):
                self.status_bar.showMessage(
                    f"Arquivo enviado automaticamente para {printer.name}"
                )
    
    def _on_logout(self):
        """Encerra a sessão do usuário"""
        self.auth.logout()
        self.close()
        # Em um cenário real, isso poderia reiniciar a aplicação ou abrir o diálogo de login


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
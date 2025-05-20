"""
Diálogo de login para autenticar o usuário
"""
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QMessageBox, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, QSettings
from PySide6.QtGui import QPixmap, QIcon

from core.auth import get_auth_instance

logger = logging.getLogger("VirtualPrinter.LoginDialog")

class LoginDialog(QDialog):
    """Diálogo para login de usuários"""
    
    def __init__(self, parent=None):
        """Inicializa o diálogo de login"""
        super().__init__(parent)
        self.auth = get_auth_instance()
        self.settings = QSettings("VirtualPrinterApp", "VirtualPrinter")
        
        self.setWindowTitle("Login - Impressora Virtual")
        self.setMinimumWidth(350)
        self.setWindowIcon(QIcon("ui/resources/icon.png"))
        
        self._setup_ui()
        self._load_saved_username()
    
    def _setup_ui(self):
        """Configura a interface de usuário"""
        layout = QVBoxLayout(self)
        
        # Título
        title_label = QLabel("Impressora Virtual")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Subtítulo
        subtitle_label = QLabel("Faça login para continuar")
        subtitle_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle_label)
        
        # Campo de usuário
        layout.addSpacing(20)
        user_layout = QVBoxLayout()
        user_label = QLabel("Usuário:")
        self.user_edit = QLineEdit()
        self.user_edit.setPlaceholderText("Digite seu nome de usuário")
        user_layout.addWidget(user_label)
        user_layout.addWidget(self.user_edit)
        layout.addLayout(user_layout)
        
        # Campo de senha
        layout.addSpacing(10)
        pass_layout = QVBoxLayout()
        pass_label = QLabel("Senha:")
        self.pass_edit = QLineEdit()
        self.pass_edit.setPlaceholderText("Digite sua senha")
        self.pass_edit.setEchoMode(QLineEdit.Password)
        pass_layout.addWidget(pass_label)
        pass_layout.addWidget(self.pass_edit)
        layout.addLayout(pass_layout)
        
        # Lembrar usuário
        layout.addSpacing(10)
        self.remember_check = QCheckBox("Lembrar usuário")
        layout.addWidget(self.remember_check)
        
        # Botões
        layout.addSpacing(20)
        button_layout = QHBoxLayout()
        
        # Espaçador flexível
        spacer = QLabel("")
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        button_layout.addWidget(spacer)
        
        self.login_button = QPushButton("Login")
        self.login_button.setDefault(True)
        
        button_layout.addWidget(self.login_button)
        
        layout.addLayout(button_layout)
        
        # Nota de direitos autorais
        layout.addSpacing(20)
        copyright_label = QLabel("© 2023 Virtual Printer. Todos os direitos reservados.")
        copyright_label.setStyleSheet("font-size: 10px; color: gray;")
        copyright_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(copyright_label)
        
        # Conectar eventos
        self.login_button.clicked.connect(self._on_login)
        
        # Conectar Enter no campo de senha para fazer login
        self.pass_edit.returnPressed.connect(self._on_login)
        
        # Autofocus no campo de usuário
        self.user_edit.setFocus()
    
    def _load_saved_username(self):
        """Carrega o nome de usuário salvo, se disponível"""
        saved_username = self.settings.value("login/username", "")
        remember_user = self.settings.value("login/remember", False, type=bool)
        
        if saved_username and remember_user:
            self.user_edit.setText(saved_username)
            self.remember_check.setChecked(True)
            self.pass_edit.setFocus()
    
    def _save_username(self, username):
        """Salva o nome de usuário para logins futuros"""
        if self.remember_check.isChecked():
            self.settings.setValue("login/username", username)
            self.settings.setValue("login/remember", True)
        else:
            self.settings.setValue("login/username", "")
            self.settings.setValue("login/remember", False)
    
    def _on_login(self):
        """Tenta fazer login com as credenciais fornecidas"""
        username = self.user_edit.text().strip()
        password = self.pass_edit.text()
        
        if not username or not password:
            QMessageBox.warning(self, "Dados Incompletos", "Por favor, preencha o usuário e senha.")
            return
        
        self.login_button.setEnabled(False)
        self.login_button.setText("Verificando...")
        self.repaint()  # Forçar atualização da UI
        
        if self.auth.login(username, password):
            self._save_username(username)
            self.accept()
        else:
            QMessageBox.critical(self, "Erro de Login", "Usuário ou senha incorretos.")
            self.pass_edit.clear()
            self.pass_edit.setFocus()
            
            self.login_button.setEnabled(True)
            self.login_button.setText("Login")
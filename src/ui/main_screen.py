#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tela principal moderna da aplicação
"""

import os
import wx
import logging
import threading
import time
from io import BytesIO
from wx.adv import TaskBarIcon
from src.models.document import Document
from src.models.printer import Printer

logger = logging.getLogger("PrintManagementSystem.UI.MainScreen")

class CardPanel(wx.Panel):
    """Painel de card para exibir um item com botões de ação"""
    
    def __init__(self, parent, document, on_print, on_delete):
        """
        Inicializa o painel de card
        
        Args:
            parent: Painel pai
            document: Documento a ser exibido
            on_print: Callback para impressão
            on_delete: Callback para exclusão
        """
        super().__init__(parent, style=wx.BORDER_NONE)
        
        self.document = document
        self.on_print = on_print
        self.on_delete = on_delete
        
        # Define cor de fundo (cinza escuro)
        self.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        # Eventos para hover
        self.hover = False
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa a interface do usuário do card"""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone do documento (esquerda)
        doc_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "src", "ui", "resources", "document.png"
        )
        
        if os.path.exists(doc_icon_path):
            doc_icon = wx.StaticBitmap(
                self,
                bitmap=wx.Bitmap(doc_icon_path),
                size=(32, 32)
            )
            main_sizer.Add(doc_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        # Painel de informações (centro)
        info_panel = wx.Panel(self)
        info_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Nome do documento
        doc_name = wx.StaticText(info_panel, label=self.document.name)
        doc_name.SetForegroundColour(wx.WHITE)
        doc_name.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(doc_name, 0, wx.BOTTOM, 5)
        
        # Detalhes do documento
        details_text = f"{self.document.formatted_date} · {self.document.formatted_size}"
        if hasattr(self.document, "pages") and self.document.pages > 0:
            details_text += f" · {self.document.pages} páginas"
            
        details = wx.StaticText(info_panel, label=details_text)
        details.SetForegroundColour(wx.Colour(180, 180, 180))
        details.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        info_sizer.Add(details, 0)
        
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Painel de ações (direita)
        actions_panel = wx.Panel(self)
        actions_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        actions_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão de impressão
        self.print_button = self._create_action_button(
            actions_panel, 
            "Imprimir", 
            wx.Colour(255, 90, 36), 
            self._on_print_click
        )
        actions_sizer.Add(self.print_button, 0, wx.RIGHT, 10)
        
        # Botão de exclusão
        self.delete_button = self._create_action_button(
            actions_panel, 
            "Excluir", 
            wx.Colour(60, 60, 60), 
            self._on_delete_click
        )
        actions_sizer.Add(self.delete_button, 0)
        
        actions_panel.SetSizer(actions_sizer)
        main_sizer.Add(actions_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
    
    def _create_action_button(self, parent, label, color, handler):
        """
        Cria um botão de ação
        
        Args:
            parent: Painel pai
            label: Texto do botão
            color: Cor de fundo do botão
            handler: Função de tratamento de clique
            
        Returns:
            wx.Button: Botão criado
        """
        button = wx.Button(parent, label=label, size=(90, 36))
        button.SetBackgroundColour(color)
        button.SetForegroundColour(wx.WHITE)
        button.Bind(wx.EVT_BUTTON, handler)
        
        # Eventos de hover para o botão
        def on_btn_enter(evt):
            if color == wx.Colour(255, 90, 36):  # Laranja
                button.SetBackgroundColour(wx.Colour(255, 120, 70))
            else:
                button.SetBackgroundColour(wx.Colour(80, 80, 80))
            button.Refresh()
        
        def on_btn_leave(evt):
            button.SetBackgroundColour(color)
            button.Refresh()
        
        button.Bind(wx.EVT_ENTER_WINDOW, on_btn_enter)
        button.Bind(wx.EVT_LEAVE_WINDOW, on_btn_leave)
        
        return button
    
    def _on_print_click(self, event):
        """Manipula o clique no botão de impressão"""
        if self.on_print:
            self.on_print(self.document)
    
    def _on_delete_click(self, event):
        """Manipula o clique no botão de exclusão"""
        if self.on_delete:
            self.on_delete(self.document)
    
    def on_enter(self, event):
        """Manipula o evento de mouse sobre o card"""
        self.hover = True
        self.Refresh()
    
    def on_leave(self, event):
        """Manipula o evento de mouse saindo do card"""
        self.hover = False
        self.Refresh()
    
    def on_paint(self, event):
        """Redesenha o card com cantos arredondados e efeito de hover"""
        dc = wx.BufferedPaintDC(self)
        gc = wx.GraphicsContext.Create(dc)
        
        rect = self.GetClientRect()
        
        # Cor de fundo baseada no estado de hover
        if self.hover:
            bg_color = wx.Colour(45, 45, 45)  # Cinza mais claro no hover
        else:
            bg_color = wx.Colour(35, 35, 35)  # Cor normal
        
        # Desenha o fundo com cantos arredondados
        path = gc.CreatePath()
        path.AddRoundedRectangle(0, 0, rect.width, rect.height, 8)
        
        gc.SetBrush(wx.Brush(bg_color))
        gc.SetPen(wx.Pen(wx.Colour(60, 60, 60), 1))  # Borda sutil
        
        gc.DrawPath(path)

class DocumentsPanel(wx.ScrolledWindow):
    """Painel de lista de documentos com cards"""
    
    def __init__(self, parent, theme_manager):
        """
        Inicializa o painel de documentos
        
        Args:
            parent: Painel pai
            theme_manager: Gerenciador de temas
        """
        super().__init__(parent, style=wx.BORDER_NONE)
        
        self.theme_manager = theme_manager
        self.documents = []
        
        # Define cor de fundo
        self.SetBackgroundColour(wx.Colour(18, 18, 18))
        
        # Inicializa a interface
        self._init_ui()
        
        # Configura scrolling
        self.SetScrollRate(0, 10)
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel de cabeçalho com título e botão de atualizar
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Arquivos para Impressão")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(wx.WHITE)
        
        self.refresh_button = wx.Button(header_panel, label="Atualizar", size=(120, 36))
        self.refresh_button.SetBackgroundColour(wx.Colour(60, 60, 60))
        self.refresh_button.SetForegroundColour(wx.WHITE)
        
        # Eventos de hover para o botão
        def on_refresh_enter(evt):
            self.refresh_button.SetBackgroundColour(wx.Colour(80, 80, 80))
            self.refresh_button.Refresh()
        
        def on_refresh_leave(evt):
            self.refresh_button.SetBackgroundColour(wx.Colour(60, 60, 60))
            self.refresh_button.Refresh()
        
        self.refresh_button.Bind(wx.EVT_ENTER_WINDOW, on_refresh_enter)
        self.refresh_button.Bind(wx.EVT_LEAVE_WINDOW, on_refresh_leave)
        
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        header_sizer.AddStretchSpacer()
        header_sizer.Add(self.refresh_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        
        header_panel.SetSizer(header_sizer)
        
        # Painel de conteúdo para os cards
        self.content_panel = wx.Panel(self)
        self.content_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel para exibir mensagem de "sem documentos"
        self.empty_panel = wx.Panel(self.content_panel)
        self.empty_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        empty_sizer = wx.BoxSizer(wx.VERTICAL)
        
        empty_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "src", "ui", "resources", "empty_document.png"
        )
        
        if os.path.exists(empty_icon_path):
            empty_icon = wx.StaticBitmap(
                self.empty_panel,
                bitmap=wx.Bitmap(empty_icon_path),
                size=(64, 64)
            )
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 50)
        
        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhum documento encontrado para impressão"
        )
        empty_text.SetForegroundColour(wx.Colour(180, 180, 180))
        empty_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        self.empty_panel.SetSizer(empty_sizer)
        
        self.content_sizer.Add(self.empty_panel, 1, wx.EXPAND)
        self.content_panel.SetSizer(self.content_sizer)
        
        # Adiciona ao layout principal
        self.main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        self.main_sizer.Add(self.content_panel, 1, wx.EXPAND)
        
        self.SetSizer(self.main_sizer)
    
    def set_documents(self, documents, on_print, on_delete):
        """
        Define a lista de documentos e atualiza a interface
        
        Args:
            documents: Lista de documentos
            on_print: Callback para impressão
            on_delete: Callback para exclusão
        """
        self.documents = documents
        
        # Remove os cards existentes
        for child in self.content_panel.GetChildren():
            if isinstance(child, CardPanel):
                child.Destroy()
        
        # Atualiza a visualização
        if documents and len(documents) > 0:
            self.empty_panel.Hide()
            
            # Cria um card para cada documento
            for doc in documents:
                card = CardPanel(self.content_panel, doc, on_print, on_delete)
                self.content_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        else:
            self.empty_panel.Show()
        
        # Ajusta o layout
        self.content_panel.Layout()
        self.Layout()
        self.Refresh()

class MainScreen(wx.Frame):
    """Tela principal da aplicação"""
    
    def __init__(self, parent, auth_manager, theme_manager, api_client, config, on_logout):
        """
        Inicializa a tela principal
        
        Args:
            parent: Frame pai
            auth_manager: Gerenciador de autenticação
            theme_manager: Gerenciador de temas
            api_client: Cliente da API
            config: Configuração da aplicação
            on_logout: Callback chamado quando o usuário faz logout
        """
        # Verifica se há tamanho e posição salvos
        size = config.get("window_size", wx.Size(900, 700))
        pos = config.get("window_pos", wx.DefaultPosition)
        
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Gerenciamento de Impressão",
            pos=pos,
            size=size,
            style=wx.DEFAULT_FRAME_STYLE
        )
        
        self.auth_manager = auth_manager
        self.theme_manager = theme_manager
        self.api_client = api_client
        self.config = config
        self.on_logout_callback = on_logout
        
        # Lista de documentos e impressoras
        self.documents = []
        self.printers = []
        
        # Configura o ícone da aplicação
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                "src", "ui", "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path))
        
        # Inicializa a interface
        self._init_ui()
        
        # Centraliza a janela na tela se não houver posição salva
        if pos == wx.DefaultPosition:
            self.Centre(wx.BOTH)
        
        # Define fundo escuro para toda a aplicação
        self.SetBackgroundColour(wx.Colour(18, 18, 18))
        
        # Bind do evento de fechamento da janela
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Bind do evento de redimensionamento da janela
        self.Bind(wx.EVT_SIZE, self.on_size)
        
        # Bind do evento de movimento da janela
        self.Bind(wx.EVT_MOVE, self.on_move)
        
        # Cria e configura o ícone da bandeja
        self.taskbar_icon = None
        self._setup_taskbar_icon()
        
        # Inicia o monitoramento da pasta se a impressão automática estiver ativada
        if self.config.get("auto_print", False):
            self._start_folder_monitoring()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Painel principal
        self.main_panel = wx.Panel(self)
        self.main_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        
        # Layout principal (horizontal: menu lateral + conteúdo)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Painel de menu lateral
        self.sidebar_panel = wx.Panel(self.main_panel)
        self.sidebar_panel.SetBackgroundColour(wx.Colour(25, 25, 25))
        sidebar_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Informações do usuário no topo do menu lateral
        user_panel = wx.Panel(self.sidebar_panel)
        user_panel.SetBackgroundColour(wx.Colour(25, 25, 25))
        user_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Avatar do usuário (círculo com inicial)
        user_info = self.auth_manager.get_current_user()
        user_name = user_info.get("name", user_info.get("email", "Usuário"))
        user_initial = user_name[0].upper() if user_name else "U"

        user_picture = user_info.get("picture", "")
        
        avatar_size = 40
        avatar_panel = wx.Panel(user_panel, size=(avatar_size, avatar_size))
        avatar_panel.SetBackgroundColour(wx.Colour(255, 90, 36))  # Laranja
        
        def on_avatar_paint(event):
            dc = wx.PaintDC(avatar_panel)
            
            # Draw the circular background first
            dc.SetBrush(wx.Brush(wx.Colour(255, 90, 36)))
            dc.SetPen(wx.Pen(wx.Colour(255, 90, 36)))
            dc.DrawCircle(int(avatar_size/2), int(avatar_size/2), int(avatar_size/2))
            
            # Draw the initial
            dc.SetTextForeground(wx.WHITE)
            font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            dc.SetFont(font)
            text_width, text_height = dc.GetTextExtent(user_initial)
            dc.DrawText(user_initial, int((avatar_size - text_width) / 2), int((avatar_size - text_height) / 2))

        avatar_panel.Bind(wx.EVT_PAINT, on_avatar_paint)
        
        # Nome do usuário
        user_name_text = wx.StaticText(user_panel, label=user_name)
        user_name_text.SetForegroundColour(wx.WHITE)
        user_name_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        user_sizer.Add(avatar_panel, 0, wx.ALL, 10)
        user_sizer.Add(user_name_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
        user_panel.SetSizer(user_sizer)
        
        sidebar_sizer.Add(user_panel, 0, wx.EXPAND | wx.ALL, 10)
        sidebar_sizer.Add(wx.StaticLine(self.sidebar_panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Menu itens
        menu_items = [
            {"label": "Documentos", "icon": "document.png", "handler": self.on_show_documents},
            {"label": "Impressoras", "icon": "printer.png", "handler": self.on_show_printers},
        ]
        
        # Criar os botões do menu
        self.menu_buttons = []
        for i, item in enumerate(menu_items):
            # Criar o painel do botão
            item_panel = wx.Panel(self.sidebar_panel)
            item_panel.SetBackgroundColour(wx.Colour(25, 25, 25))
            item_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Carregar ícone se existir
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                    "src", "ui", "resources", item.get("icon", ""))
            
            if os.path.exists(icon_path):
                icon = wx.Bitmap(icon_path)
                icon_bitmap = wx.StaticBitmap(item_panel, wx.ID_ANY, icon)
                item_sizer.Add(icon_bitmap, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
            
            # Texto do item
            item_text = wx.StaticText(item_panel, wx.ID_ANY, item["label"])
            item_text.SetForegroundColour(wx.WHITE)
            item_sizer.Add(item_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
            
            item_panel.SetSizer(item_sizer)
            
            # Eventos do item
            item_panel.Bind(wx.EVT_LEFT_DOWN, item["handler"])
            
            # Marcar como selecionado o primeiro item (Documentos)
            if i == 0:
                item_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
                self.selected_menu = item_panel
            
            # Eventos de hover
            def on_enter(evt, panel=item_panel):
                if panel != self.selected_menu:
                    panel.SetBackgroundColour(wx.Colour(35, 35, 35))
                    panel.Refresh()
            
            def on_leave(evt, panel=item_panel):
                if panel != self.selected_menu:
                    panel.SetBackgroundColour(wx.Colour(25, 25, 25))
                    panel.Refresh()
            
            item_panel.Bind(wx.EVT_ENTER_WINDOW, on_enter)
            item_panel.Bind(wx.EVT_LEAVE_WINDOW, on_leave)
            
            sidebar_sizer.Add(item_panel, 0, wx.EXPAND | wx.TOP, 5)
            self.menu_buttons.append(item_panel)
        
        # Espaçador para empurrar o botão de logout para o fim
        sidebar_sizer.Add((0, 0), 1, wx.EXPAND)
        
        # Botão de logout
        logout_panel = wx.Panel(self.sidebar_panel)
        logout_panel.SetBackgroundColour(wx.Colour(25, 25, 25))
        logout_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone de logout
        logout_icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                       "src", "ui", "resources", "logout.png")
        
        if os.path.exists(logout_icon_path):
            logout_icon = wx.Bitmap(logout_icon_path)
            logout_bitmap = wx.StaticBitmap(logout_panel, wx.ID_ANY, logout_icon)
            logout_sizer.Add(logout_bitmap, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        # Texto do logout
        logout_text = wx.StaticText(logout_panel, wx.ID_ANY, "Sair")
        logout_text.SetForegroundColour(wx.WHITE)
        logout_sizer.Add(logout_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
        
        logout_panel.SetSizer(logout_sizer)
        
        # Eventos de hover
        def on_logout_enter(evt):
            logout_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
            logout_panel.Refresh()
        
        def on_logout_leave(evt):
            logout_panel.SetBackgroundColour(wx.Colour(25, 25, 25))
            logout_panel.Refresh()
        
        logout_panel.Bind(wx.EVT_ENTER_WINDOW, on_logout_enter)
        logout_panel.Bind(wx.EVT_LEAVE_WINDOW, on_logout_leave)
        logout_panel.Bind(wx.EVT_LEFT_DOWN, self.on_logout)
        
        sidebar_sizer.Add(logout_panel, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 20)
        
        self.sidebar_panel.SetSizer(sidebar_sizer)
        
        # Painel de conteúdo
        self.content_panel = wx.Panel(self.main_panel)
        self.content_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cria o painel de documentos
        self.documents_panel = DocumentsPanel(self.content_panel, self.theme_manager)
        self.documents_panel.refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh_documents)
        
        # Cria o painel de impressoras (inicialmente oculto)
        self.printers_panel = wx.Panel(self.content_panel)
        self.printers_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        self.printers_panel.Hide()
        
        # Cria o painel de configurações (inicialmente oculto)
        self.settings_panel = wx.Panel(self.content_panel)
        self.settings_panel.SetBackgroundColour(wx.Colour(18, 18, 18))
        self.settings_panel.Hide()
        
        self.content_sizer.Add(self.documents_panel, 1, wx.EXPAND)
        self.content_sizer.Add(self.printers_panel, 1, wx.EXPAND)
        self.content_sizer.Add(self.settings_panel, 1, wx.EXPAND)
        
        self.content_panel.SetSizer(self.content_sizer)
        
        # Adiciona os painéis ao layout principal
        main_sizer.Add(self.sidebar_panel, 0, wx.EXPAND)
        main_sizer.Add(self.content_panel, 1, wx.EXPAND)
        
        self.main_panel.SetSizer(main_sizer)
        
        # Carrega lista de documentos
        self.load_documents()
    
    def _setup_taskbar_icon(self):
        """Configura o ícone da bandeja do sistema"""
        try:
            self.taskbar_icon = TaskBarIcon()
            
            # Carrega o ícone da aplicação
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                    "src", "ui", "resources", "icon.ico")
            
            if os.path.exists(icon_path):
                icon = wx.Icon(icon_path)
                self.taskbar_icon.SetIcon(icon, "Sistema de Gerenciamento de Impressão")
            
            # Define menu de contexto
            def create_popup_menu():
                menu = wx.Menu()
                
                # Item para abrir a aplicação
                open_item = menu.Append(wx.ID_ANY, "Abrir")
                self.Bind(wx.EVT_MENU, self.on_open_from_tray, open_item)
                
                menu.AppendSeparator()
                
                # Item para sair
                exit_item = menu.Append(wx.ID_ANY, "Sair")
                self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
                
                return menu
            
            self.taskbar_icon.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, 
                               lambda evt: self.taskbar_icon.PopupMenu(create_popup_menu()))
            self.taskbar_icon.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_open_from_tray)
            
        except Exception as e:
            logger.error(f"Erro ao criar ícone na bandeja: {str(e)}")
            self.taskbar_icon = None
    
    def on_show_documents(self, event=None):
        """Mostra o painel de documentos"""
        # Destaca o botão selecionado
        for button in self.menu_buttons:
            button.SetBackgroundColour(wx.Colour(25, 25, 25))
        
        self.menu_buttons[0].SetBackgroundColour(wx.Colour(35, 35, 35))
        self.selected_menu = self.menu_buttons[0]
        
        # Mostra o painel correto
        self.documents_panel.Show()
        self.printers_panel.Hide()
        self.settings_panel.Hide()
        
        # Carrega os documentos
        self.load_documents()
        
        # Atualiza o layout
        self.content_panel.Layout()
    
    def on_show_printers(self, event=None):
        """Mostra o painel de impressoras"""
        # Destaca o botão selecionado
        for button in self.menu_buttons:
            button.SetBackgroundColour(wx.Colour(25, 25, 25))
        
        self.menu_buttons[1].SetBackgroundColour(wx.Colour(35, 35, 35))
        self.selected_menu = self.menu_buttons[1]
        
        # Mostra o painel correto
        self.documents_panel.Hide()
        self.printers_panel.Show()
        self.settings_panel.Hide()
        
        # Atualiza o layout
        self.content_panel.Layout()
    
    def on_show_settings(self, event=None):
        """Mostra o painel de configurações"""
        # Destaca o botão selecionado
        for button in self.menu_buttons:
            button.SetBackgroundColour(wx.Colour(25, 25, 25))
        
        self.menu_buttons[2].SetBackgroundColour(wx.Colour(35, 35, 35))
        self.selected_menu = self.menu_buttons[2]
        
        # Mostra o painel correto
        self.documents_panel.Hide()
        self.printers_panel.Hide()
        self.settings_panel.Show()
        
        # Atualiza o layout
        self.content_panel.Layout()
    
    def on_logout(self, event=None):
        """Processa o logout do usuário e volta para a tela de login"""
        if self.auth_manager.logout():
            # Salva o tamanho e posição da janela
            self._save_window_geometry()
            
            # Para o monitoramento de pastas se estiver ativo
            self._stop_folder_monitoring()
            
            # Esconde a janela em vez de destruí-la
            self.Hide()
            
            # Chama o callback para voltar à tela de login
            if self.on_logout_callback:
                self.on_logout_callback()
    
    def on_refresh_documents(self, event=None):
        """Atualiza a lista de documentos"""
        self.load_documents()
    
    def load_documents(self):
        """Carrega a lista de documentos"""
        try:
            # Verifica se o monitor de arquivos está inicializado e ativo
            if not hasattr(self, 'file_monitor') or not self.file_monitor.observer or not self.file_monitor.observer.is_alive():
                from src.utils.file_monitor import FileMonitor
                self.file_monitor = FileMonitor(self.config, self.on_documents_changed)
                self.file_monitor.start()
                
            # Obtém documentos do monitor de arquivos
            self.documents = self.file_monitor.get_documents()
            
            # Atualiza o painel de documentos
            self.documents_panel.set_documents(
                self.documents,
                self.on_print_document,
                self.on_delete_document
            )
            
        except Exception as e:
            logger.error(f"Erro ao carregar documentos: {str(e)}")
            # Exibir mensagem de erro
            wx.MessageBox(f"Erro ao carregar documentos: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
    
    def on_documents_changed(self, documents):
        """
        Callback chamado quando a lista de documentos é alterada
        
        Args:
            documents (list): Lista de documentos
        """
        self.documents = documents
        
        # Atualiza a UI se estiver visível
        if self.IsShown() and self.documents_panel.IsShown():
            # Usa CallAfter para garantir que a atualização da UI aconteça na thread principal
            wx.CallAfter(self.load_documents)
    
    def on_print_document(self, document):
        """
        Imprime um documento
        
        Args:
            document: Documento a ser impresso
        """
        # Verifica se temos impressoras carregadas
        if not self.printers:
            try:
                # Tenta carregar as impressoras do sistema
                from src.utils.printer_utils import PrinterUtils
                system_printers = PrinterUtils.get_system_printers()
                
                if not system_printers:
                    # Se não houver impressoras do sistema, tenta carregar do config
                    self.printers = [Printer(printer_data) for printer_data in self.config.get_printers()]
                else:
                    # Converte impressoras do sistema para nosso modelo
                    self.printers = [Printer({
                        "id": p.get("id"),
                        "name": p.get("name"),
                        "system_name": p.get("system_name", p.get("name")),
                        "mac_address": p.get("mac_address", "")
                    }) for p in system_printers]
                    
            except Exception as e:
                logger.error(f"Erro ao carregar impressoras: {str(e)}")
                wx.MessageBox("Não foi possível carregar a lista de impressoras. " + 
                            "Por favor, atualize as impressoras primeiro.",
                            "Erro", wx.OK | wx.ICON_ERROR)
                return
        
        if not self.printers:
            wx.MessageBox("Nenhuma impressora disponível.",
                        "Informação", wx.OK | wx.ICON_INFORMATION)
            return
        
        # Cria a caixa de diálogo para escolher impressora
        choices = [printer.name for printer in self.printers]
        
        dialog = wx.SingleChoiceDialog(
            self,
            "Escolha a impressora para enviar o documento:",
            "Imprimir Documento",
            choices
        )
        
        if dialog.ShowModal() == wx.ID_OK:
            selected_index = dialog.GetSelection()
            printer = self.printers[selected_index]
            
            try:
                # Imprime diretamente usando PrinterUtils
                from src.utils.printer_utils import PrinterUtils
                PrinterUtils.print_file(document.path, getattr(printer, 'system_name', printer.name))
                wx.MessageBox(f"Documento '{document.name}' enviado para '{printer.name}'.",
                            "Impressão", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                logger.error(f"Erro ao imprimir documento: {str(e)}")
                wx.MessageBox(f"Erro ao imprimir documento: {str(e)}",
                            "Erro", wx.OK | wx.ICON_ERROR)
        
        dialog.Destroy()
    
    def on_delete_document(self, document):
        """
        Exclui um documento
        
        Args:
            document: Documento a ser excluído
        """
        # Confirma a exclusão
        dlg = wx.MessageDialog(
            self,
            f"Tem certeza que deseja excluir o documento '{document.name}'?",
            "Confirmar Exclusão",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            try:
                # Exclui o arquivo
                os.remove(document.path)
                
                # Atualiza a lista
                self.load_documents()
                
                wx.MessageBox(f"Documento '{document.name}' excluído com sucesso.",
                            "Exclusão", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                logger.error(f"Erro ao excluir documento: {str(e)}")
                wx.MessageBox(f"Erro ao excluir documento: {str(e)}",
                            "Erro", wx.OK | wx.ICON_ERROR)
        
        dlg.Destroy()
    
    def on_open_from_tray(self, event):
        """Abre a aplicação a partir da bandeja do sistema"""
        self.Show()
        self.Raise()
        
        # Restaura o tamanho e posição salvos
        size = self.config.get("window_size", None)
        pos = self.config.get("window_pos", None)
        
        if size:
            self.SetSize(size)
        else:
            self.SetSize((800, 600))
        
        if pos:
            self.SetPosition(pos)
    
    def on_exit(self, event):
        """Fecha completamente a aplicação"""
        # Salva o tamanho e posição da janela
        self._save_window_geometry()
        
        # Para o monitoramento de pastas se estiver ativo
        self._stop_folder_monitoring()
        
        # Remove o ícone da bandeja
        if self.taskbar_icon:
            self.taskbar_icon.RemoveIcon()
            self.taskbar_icon.Destroy()
            self.taskbar_icon = None
        
        # Destrói a janela principal
        self.Destroy()
        
        # Encerra a aplicação
        wx.GetApp().ExitMainLoop()
    
    def _start_folder_monitoring(self):
        """Inicia o monitoramento da pasta de PDFs"""
        if not hasattr(self, 'monitoring_active') or not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitor_folder, daemon=True)
            self.monitoring_thread.start()
    
    def _stop_folder_monitoring(self):
        """Para o monitoramento da pasta de PDFs"""
        self.monitoring_active = False
    
    def _monitor_folder(self):
        """Função executada em thread para monitorar a pasta de PDFs"""
        # Implementação do monitoramento de pastas
        pass
    
    def on_size(self, event):
        """Manipula o evento de redimensionamento da janela"""
        if not self.IsMaximized() and not self.IsIconized():
            # Salva o novo tamanho
            width, height = self.GetSize()
            self.config.set("window_size", (width, height))
        event.Skip()
    
    def on_move(self, event):
        """Manipula o evento de movimento da janela"""
        if not self.IsMaximized() and not self.IsIconized():
            # Salva a nova posição
            x, y = self.GetPosition()
            self.config.set("window_pos", (x, y))
        event.Skip()
    
    def _save_window_geometry(self):
        """Salva o tamanho e posição da janela nas configurações do usuário"""
        if not self.IsMaximized() and not self.IsIconized():
            width, height = self.GetSize()
            self.config.set("window_size", (width, height))
            
            x, y = self.GetPosition()
            self.config.set("window_pos", (x, y))
    
    def on_close(self, event):
        """
        Manipula o evento de fechamento da janela
        
        Args:
            event: Evento de fechamento
        """
        # Salva o tamanho e posição da janela
        self._save_window_geometry()
        
        # Esconde a janela em vez de fechá-la
        self.Hide()
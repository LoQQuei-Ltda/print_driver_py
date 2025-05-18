#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tela principal da aplicação
"""
import os
import wx
import logging
import requests
import threading
import time
from io import BytesIO
from wx.adv import TaskBarIcon
from src.models.document import Document
from src.models.printer import Printer
from src.ui.taskbar_icon import PrintManagerTaskBarIcon

logger = logging.getLogger("PrintManagementSystem.UI.MainScreen")

class PrintManagerTaskBarIcon(TaskBarIcon):
    """Ícone da bandeja do sistema"""
    
    def __init__(self, parent, config):
        """
        Inicializa o ícone da bandeja
        
        Args:
            parent: Frame pai
            config: Configuração da aplicação
        """
        super().__init__()
        
        self.parent = parent
        self.config = config
        
        # Carrega o ícone da aplicação
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                "src", "ui", "resources", "icon.ico")
        
        if os.path.exists(icon_path):
            self.icon = wx.Icon(icon_path)
            self.SetIcon(self.icon, "Sistema de Gerenciamento de Impressão")
        else:
            # Cria um ícone vazio como fallback
            self.icon = wx.Icon(wx.Bitmap(16, 16))
            self.SetIcon(self.icon, "Sistema de Gerenciamento de Impressão")
        
        # Vincula eventos
        self.Bind(wx.adv.EVT_TASKBAR_LEFT_DCLICK, self.on_left_dclick)
        
    def CreatePopupMenu(self):
        """
        Cria o menu de contexto para o ícone da bandeja
        
        Returns:
            wx.Menu: Menu de contexto
        """
        menu = wx.Menu()
        
        # Item para abrir a aplicação
        open_item = menu.Append(wx.ID_ANY, "Abrir")
        self.Bind(wx.EVT_MENU, self.on_open, open_item)
        
        menu.AppendSeparator()
        
        # Item para alternar impressão automática
        auto_print_active = self.config.get("auto_print", False)
        auto_print_label = "Desativar Impressão Automática" if auto_print_active else "Ativar Impressão Automática"
        auto_print_item = menu.Append(wx.ID_ANY, auto_print_label)
        self.Bind(wx.EVT_MENU, self.on_toggle_auto_print, auto_print_item)
        
        menu.AppendSeparator()
        
        # Item para sair completamente da aplicação
        exit_item = menu.Append(wx.ID_ANY, "Sair")
        self.Bind(wx.EVT_MENU, self.on_exit, exit_item)
        
        return menu
    
    def on_left_dclick(self, event):
        """Manipula o evento de duplo clique no ícone da bandeja"""
        self.on_open(event)
    
    def on_open(self, event):
        """Abre a aplicação"""
        if self.parent:
            self.parent.Show()
            self.parent.Raise()
            
            # Restaura o tamanho e posição salvos
            size = self.config.get("window_size", None)
            pos = self.config.get("window_pos", None)
            
            if size:
                self.parent.SetSize(size)
            else:
                self.parent.SetSize((560, 720))
            
            if pos:
                self.parent.SetPosition(pos)
    
    def on_toggle_auto_print(self, event):
        """Alterna o modo de impressão automática"""
        current_state = self.config.get("auto_print", False)
        self.config.set("auto_print", not current_state)
        
        # Atualiza o checkbox na interface principal se estiver visível
        if self.parent and hasattr(self.parent, "auto_print_toggle"):
            self.parent.auto_print_toggle.SetValue(not current_state)
            
        # Inicia ou para o monitoramento da pasta
        if not current_state:
            self.parent._start_folder_monitoring()
        else:
            self.parent._stop_folder_monitoring()
    
    def on_exit(self, event):
        """Fecha completamente a aplicação"""
        if self.parent:
            self.parent.exit_application()


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
        size = config.get("window_size", wx.Size(1024, 768))
        pos = config.get("window_pos", wx.DefaultPosition)
        
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Gerenciamento de Impressão",
            pos=pos,
            size=size,
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL
        )
        
        self.auth_manager = auth_manager
        self.theme_manager = theme_manager
        self.api_client = api_client
        self.config = config
        self.on_logout_callback = on_logout
        self.taskbar_icon = None
        
        # Lista de documentos e impressoras
        self.documents = []
        self.printers = []
        
        # Flag para controlar o monitoramento da pasta
        self.monitoring_active = False
        
        # Configura o ícone da aplicação
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                "src", "ui", "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path))
        
        # Inicializa a interface
        self.__init_ui()
        
        # Centraliza a janela na tela se não houver posição salva
        if pos == wx.DefaultPosition:
            self.Centre(wx.BOTH)
        
        # Aplica o tema atual
        self.theme_manager.apply_theme_to_window(self)
        
        # Bind do evento de fechamento da janela
        self.Bind(wx.EVT_CLOSE, self.on_close)
        
        # Bind do evento de redimensionamento da janela
        self.Bind(wx.EVT_SIZE, self.on_size)
        
        # Bind do evento de movimento da janela
        self.Bind(wx.EVT_MOVE, self.on_move)
        
        # Cria e configura o ícone da bandeja - IMPORTANTE: isso é feito aqui, não no on_close
        self.taskbar_icon = PrintManagerTaskBarIcon(self, self.config)
        
        # Inicia o monitoramento da pasta se a impressão automática estiver ativada
        if self.config.get("auto_print", False):
            self._start_folder_monitoring()
    
    def __init_ui(self):
        """Inicializa a interface do usuário"""
        colors = self.theme_manager.get_theme_colors()
        
        # Painel principal
        self.main_panel = wx.Panel(self)
        self.main_panel.SetBackgroundColour(colors["bg_color"])
        
        # Layout principal (horizontal: menu lateral + conteúdo)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Painel de menu lateral
        self.sidebar_panel = wx.Panel(self.main_panel)
        self.sidebar_panel.SetBackgroundColour(colors["panel_bg"])
        sidebar_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Informações do usuário no topo do menu lateral
        user_panel = wx.Panel(self.sidebar_panel)
        user_panel.SetBackgroundColour(colors["panel_bg"])
        user_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Avatar do usuário (círculo com inicial)
        user_info = self.auth_manager.get_current_user()
        user_name = user_info.get("name", user_info.get("email", "Usuário"))
        user_initial = user_name[0].upper() if user_name else "U"

        user_picture = user_info.get("picture", "")
        
        avatar_size = 40
        avatar_panel = wx.Panel(user_panel, size=(avatar_size, avatar_size))
        avatar_panel.SetBackgroundColour(colors["accent_color"])
        
        def on_avatar_paint(event):
            dc = wx.PaintDC(avatar_panel)
            
            # Draw the circular background first
            dc.SetBrush(wx.Brush(colors["accent_color"]))
            dc.SetPen(wx.Pen(colors["accent_color"]))
            dc.DrawCircle(int(avatar_size/2), int(avatar_size/2), int(avatar_size/2))
            
            user_picture_ok = False
            if user_picture:
                try:
                    response = requests.get(user_picture)
                    response.raise_for_status()
                    
                    # Create an image from the response content
                    image_stream = BytesIO(response.content)
                    
                    # Use wx.ImageFromStream instead of direct construction
                    img = wx.Image(image_stream)
                    
                    if img.IsOk():
                        # Resize the image to fit the avatar circle
                        img = img.Scale(avatar_size, avatar_size)
                        avatar_bitmap = wx.Bitmap(img)
                        
                        # Create a memory DC for compositing
                        memDC = wx.MemoryDC()
                        memDC.SelectObject(wx.Bitmap(avatar_size, avatar_size))
                        
                        # Fill with transparent background
                        memDC.SetBackground(wx.Brush(wx.Colour(0, 0, 0, 0)))
                        memDC.Clear()
                        
                        # Draw the circle first
                        memDC.SetBrush(wx.Brush(colors["accent_color"]))
                        memDC.SetPen(wx.Pen(colors["accent_color"]))
                        memDC.DrawCircle(int(avatar_size/2), int(avatar_size/2), int(avatar_size/2))
                        
                        # Then draw the image
                        memDC.SetClippingRegion(0, 0, avatar_size, avatar_size)
                        memDC.DrawBitmap(avatar_bitmap, 0, 0)
                        
                        # Now draw the result to our actual DC
                        result_bitmap = memDC.GetAsBitmap()
                        memDC.SelectObject(wx.NullBitmap)
                        
                        dc.DrawBitmap(result_bitmap, 0, 0)
                        user_picture_ok = True
                    else:
                        print("Erro ao carregar a imagem.")
                except requests.exceptions.RequestException as e:
                    print(f"Erro ao baixar a imagem: {e}")
                except Exception as e:
                    print(f"Erro ao processar a imagem: {e}")
                    
            # If no picture or failed to load, draw the initial
            if not user_picture_ok:
                dc.SetTextForeground(wx.WHITE)
                font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
                dc.SetFont(font)
                text_width, text_height = dc.GetTextExtent(user_initial)
                dc.DrawText(user_initial, int((avatar_size - text_width) / 2), int((avatar_size - text_height) / 2))


        avatar_panel.Bind(wx.EVT_PAINT, on_avatar_paint)
        
        # Nome do usuário
        user_name_text = wx.StaticText(user_panel, label=user_name)
        user_name_text.SetForegroundColour(colors["text_color"])
        user_name_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        user_sizer.Add(avatar_panel, 0, wx.ALL, 5)
        user_sizer.Add(user_name_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
        user_panel.SetSizer(user_sizer)
        
        sidebar_sizer.Add(user_panel, 0, wx.EXPAND | wx.ALL, 10)
        sidebar_sizer.Add(wx.StaticLine(self.sidebar_panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Menu itens
        menu_items = [
            {"label": "Documentos", "icon": "document.png", "handler": self.on_show_documents},
            {"label": "Impressoras", "icon": "system.png", "handler": self.on_show_printers},
        ]
        
        # Criar os botões do menu
        self.menu_buttons = []
        for item in menu_items:
            # Criar o painel do botão
            item_panel = wx.Panel(self.sidebar_panel)
            item_panel.SetBackgroundColour(colors["panel_bg"])
            item_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Carregar ícone se existir
            icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                                    "src", "ui", "resources", item.get("icon", ""))
            
            if os.path.exists(icon_path):
                icon = wx.Bitmap(icon_path)
                icon_bitmap = wx.StaticBitmap(item_panel, wx.ID_ANY, icon)
                item_sizer.Add(icon_bitmap, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)
            
            # Texto do item
            item_text = wx.StaticText(item_panel, wx.ID_ANY, item["label"])
            item_text.SetForegroundColour(colors["text_color"])
            item_sizer.Add(item_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
            
            item_panel.SetSizer(item_sizer)
            
            # Eventos do item
            item_panel.Bind(wx.EVT_LEFT_DOWN, item["handler"])
            
            # Eventos de hover
            def on_enter(evt, panel=item_panel):
                panel.SetBackgroundColour(colors["hover_bg"])
                panel.Refresh()
            
            def on_leave(evt, panel=item_panel):
                panel.SetBackgroundColour(colors["panel_bg"])
                panel.Refresh()
            
            item_panel.Bind(wx.EVT_ENTER_WINDOW, on_enter)
            item_panel.Bind(wx.EVT_LEAVE_WINDOW, on_leave)
            
            sidebar_sizer.Add(item_panel, 0, wx.EXPAND | wx.TOP, 5)
            self.menu_buttons.append(item_panel)
        
        sidebar_sizer.Add(wx.StaticLine(self.sidebar_panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP, 10)
        
        # Toggle de impressão automática
        auto_print_panel = wx.Panel(self.sidebar_panel)
        auto_print_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        auto_print_text = wx.StaticText(auto_print_panel, label="Impressão Automática")
        auto_print_text.SetForegroundColour(colors["text_color"])
        
        # Alterna entre usar checkbox ou toggle button dependendo da plataforma
        if wx.Platform == '__WXMSW__':  # Windows
            self.auto_print_toggle = wx.CheckBox(auto_print_panel, label="")
        else:  # macOS, Linux ou outros
            self.auto_print_toggle = wx.ToggleButton(auto_print_panel, label="", size=(40, 20))
        
        self.auto_print_toggle.SetValue(self.config.get("auto_print", False))
        
        def on_toggle(event):
            is_on = event.GetEventObject().GetValue()
            self.config.set("auto_print", is_on)
            
            if is_on:
                self._start_folder_monitoring()
            else:
                self._stop_folder_monitoring()
            
            # Atualiza o status visual do toggle
            if not isinstance(self.auto_print_toggle, wx.CheckBox):
                self._update_toggle_appearance()
        
        self.auto_print_toggle.Bind(wx.EVT_CHECKBOX if isinstance(self.auto_print_toggle, wx.CheckBox) 
                                  else wx.EVT_TOGGLEBUTTON, on_toggle)
        
        auto_print_sizer.Add(auto_print_text, 0, wx.ALIGN_CENTER_VERTICAL)
        auto_print_sizer.Add((0, 0), 1, wx.EXPAND)  # Espaçador flexível
        auto_print_sizer.Add(self.auto_print_toggle, 0, wx.ALIGN_CENTER_VERTICAL)
        
        auto_print_panel.SetSizer(auto_print_sizer)
        sidebar_sizer.Add(auto_print_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Opções adicionais
        additional_items = [
            {"label": "Atualizar impressoras com o servidor principal", "handler": self.on_update_printers},
            {"label": "Configurações manuais das impressoras", "handler": self.on_show_printer_config}
        ]
        
        for item in additional_items:
            item_panel = wx.Panel(self.sidebar_panel)
            item_panel.SetBackgroundColour(colors["panel_bg"])
            item_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            item_text = wx.StaticText(item_panel, wx.ID_ANY, item["label"])
            item_text.SetForegroundColour(colors["text_color"])
            item_sizer.Add(item_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
            
            item_panel.SetSizer(item_sizer)
            
            item_panel.Bind(wx.EVT_LEFT_DOWN, item["handler"])
            
            # Eventos de hover
            def on_enter(evt, panel=item_panel):
                panel.SetBackgroundColour(colors["hover_bg"])
                panel.Refresh()
            
            def on_leave(evt, panel=item_panel):
                panel.SetBackgroundColour(colors["panel_bg"])
                panel.Refresh()
            
            item_panel.Bind(wx.EVT_ENTER_WINDOW, on_enter)
            item_panel.Bind(wx.EVT_LEAVE_WINDOW, on_leave)
            
            sidebar_sizer.Add(item_panel, 0, wx.EXPAND | wx.TOP, 5)
        
        # Espaçador para empurrar o botão de logout para o fim
        sidebar_sizer.Add((0, 0), 1, wx.EXPAND)
        
        # Botão de logout
        logout_button = wx.Button(self.sidebar_panel, label="Sair")
        logout_button.Bind(wx.EVT_BUTTON, self.on_logout)
        sidebar_sizer.Add(logout_button, 0, wx.EXPAND | wx.ALL, 10)
        
        self.sidebar_panel.SetSizer(sidebar_sizer)
        
        # Painel de conteúdo
        self.content_panel = wx.Panel(self.main_panel)
        self.content_panel.SetBackgroundColour(colors["bg_color"])
        
        # Layout do conteúdo
        content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título do conteúdo
        title_panel = wx.Panel(self.content_panel)
        title_panel.SetBackgroundColour(colors["bg_color"])
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        self.content_title = wx.StaticText(title_panel, label="Arquivos para Impressão")
        self.content_title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.content_title.SetForegroundColour(colors["text_color"])
        
        # Botão de refresh
        refresh_button = self.theme_manager.get_custom_button(title_panel, "Atualizar")
        refresh_button.Bind(wx.EVT_BUTTON, self.on_refresh)
        
        title_sizer.Add(self.content_title, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        title_sizer.Add((0, 0), 1, wx.EXPAND)  # Espaçador flexível
        title_sizer.Add(refresh_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 10)
        
        title_panel.SetSizer(title_sizer)
        
        # Mensagem quando não há arquivos
        self.no_files_panel = wx.Panel(self.content_panel)
        self.no_files_panel.SetBackgroundColour(colors["panel_bg"])
        no_files_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Ícone de documento vazio
        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                               "src", "ui", "resources", "empty_document.png")
        
        if os.path.exists(icon_path):
            empty_icon = wx.StaticBitmap(
                self.no_files_panel,
                bitmap=wx.Bitmap(icon_path),
                size=(64, 64)
            )
            no_files_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 50)
        
        no_files_text = wx.StaticText(self.no_files_panel, label="Nenhum arquivo encontrado para impressão.")
        no_files_text.SetForegroundColour(colors["text_secondary"])
        no_files_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        no_files_sizer.Add(no_files_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        self.no_files_panel.SetSizer(no_files_sizer)
        
        # Lista de documentos
        self.files_list = wx.ListCtrl(self.content_panel, style=wx.LC_REPORT)
        self.files_list.InsertColumn(0, "Nome", width=300)
        self.files_list.InsertColumn(1, "Data", width=150)
        self.files_list.InsertColumn(2, "Tamanho", width=100)
        self.files_list.InsertColumn(3, "Páginas", width=80)
        
        # Adiciona menu de contexto à lista de arquivos
        self.files_list.Bind(wx.EVT_RIGHT_DOWN, self.on_file_right_click)
        
        # Adiciona elementos ao layout do conteúdo
        content_sizer.Add(title_panel, 0, wx.EXPAND)
        content_sizer.Add(self.no_files_panel, 1, wx.EXPAND)
        content_sizer.Add(self.files_list, 1, wx.EXPAND)
        
        # Esconde a lista inicialmente
        self.files_list.Hide()
        
        self.content_panel.SetSizer(content_sizer)
        
        # Adiciona os painéis ao layout principal
        main_sizer.Add(self.sidebar_panel, 0, wx.EXPAND)
        main_sizer.Add(self.content_panel, 1, wx.EXPAND)
        
        self.main_panel.SetSizer(main_sizer)
        
        # Carrega lista de arquivos
        self.on_show_documents()
    
    def _update_toggle_appearance(self):
        """Atualiza a aparência do toggle switch baseado no estado"""
        if isinstance(self.auto_print_toggle, wx.CheckBox):
            return
        
        colors = self.theme_manager.get_theme_colors()
        is_on = self.auto_print_toggle.GetValue()
        
        if is_on:
            self.auto_print_toggle.SetBackgroundColour(colors["toggle_on"])
            self.auto_print_toggle.SetLabel("ON")
        else:
            self.auto_print_toggle.SetBackgroundColour(colors["toggle_off"])
            self.auto_print_toggle.SetLabel("OFF")
    
    def on_show_documents(self, event=None):
        """Mostra a tela de documentos"""
        self.content_title.SetLabel("Arquivos para Impressão")
        
        # Atualiza o texto do botão de refresh
        if hasattr(self, 'refresh_button'):
            self.refresh_button.SetLabel("Atualizar")
        
        # Esconde o painel de impressoras se existir
        if hasattr(self, 'printer_list_panel'):
            self.printer_list_panel.Hide()
            
        # Recarrega os documentos
        self.load_documents()
    
    def on_show_printers(self, event=None):
        """Mostra a tela de impressoras"""
        self.content_title.SetLabel("Impressoras")
        
        # Atualiza o texto do botão de refresh
        if hasattr(self, 'refresh_button'):
            self.refresh_button.SetLabel("Atualizar Impressoras")
        
        # Esconde a lista de documentos e a mensagem de nenhum arquivo
        self.files_list.Hide()
        self.no_files_panel.Hide()
        
        # Mostra o painel de impressoras
        if not hasattr(self, 'printer_list_panel'):
            from src.ui.printer_list import PrinterListPanel
            self.printer_list_panel = PrinterListPanel(
                self.content_panel,
                self.theme_manager,
                self.config,
                self.api_client,
                self.on_printers_updated
            )
            self.content_panel.GetSizer().Add(self.printer_list_panel, 1, wx.EXPAND)
        
        self.printer_list_panel.Show()
        self.printer_list_panel.load_printers()
        
        # Atualiza o layout
        self.content_panel.Layout()
    
    def on_printers_updated(self, printers):
        """
        Callback chamado quando as impressoras são atualizadas
        
        Args:
            printers (list): Lista de impressoras
        """
        # Atualiza a lista local de impressoras
        self.printers = printers
    
    def on_update_printers(self, event=None):
        """Atualiza as impressoras com o servidor principal"""
        try:
            # Mostra um indicador de progresso
            busy = wx.BusyInfo("Atualizando impressoras do servidor. Aguarde...", parent=self)
            wx.GetApp().Yield()
            
            # Obtém as impressoras da API
            printers_data = self.api_client.get_printers()
            
            # Converte para objetos Printer e depois para dicionários
            printers = [Printer(printer_data).to_dict() for printer_data in printers_data]
            
            # Salva as impressoras no config
            self.config.set_printers(printers)
            
            # Recarrega a lista
            self.load_printers()
            
            # Chama o callback se existir
            if self.on_update:
                self.on_update(printers)
            
            # Remove o indicador de progresso
            del busy
            
            # Mostra mensagem de sucesso
            wx.MessageBox(f"{len(printers)} impressoras atualizadas com sucesso!", 
                         "Informação", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            logger.error(f"Erro ao atualizar impressoras: {str(e)}")
            wx.MessageBox(f"Erro ao atualizar impressoras: {str(e)}", 
                         "Erro", wx.OK | wx.ICON_ERROR)
    
    def on_show_printer_config(self, event=None):
        """Mostra configurações manuais das impressoras"""
        self.content_title.SetLabel("Configurações manuais das impressoras")
        
        # Esconde a lista de documentos e a mensagem de nenhum arquivo
        self.files_list.Hide()
        self.no_files_panel.Hide()
        
        # TODO: Implementar painel de configurações de impressoras
        
        # Atualiza o layout
        self.content_panel.Layout()
    
    def on_refresh(self, event=None):
        """Atualiza o conteúdo da tela atual"""
        current_title = self.content_title.GetLabel()
        
        if current_title == "Arquivos para Impressão":
            # Estamos na tela de documentos
            self.load_documents()
        elif current_title == "Impressoras":
            # Estamos na tela de impressoras
            if hasattr(self, 'printer_list_panel'):
                self.printer_list_panel.on_update_printers()
        else:
            # Outra tela
            wx.MessageBox("Funcionalidade não implementada para esta tela.", 
                         "Informação", wx.OK | wx.ICON_INFORMATION)
    
    def load_documents(self):
        """Carrega a lista de documentos localmente do sistema de arquivos"""
        # Limpa a lista atual
        self.files_list.DeleteAllItems()
        
        try:
            # Adiciona item de carregamento
            self.files_list.InsertItem(0, "Carregando...")
            wx.GetApp().Yield()
            
            # Verifica se o monitor de arquivos está inicializado e ativo
            if not hasattr(self, 'file_monitor') or not self.file_monitor.observer or not self.file_monitor.observer.is_alive():
                from src.utils.file_monitor import FileMonitor
                self.file_monitor = FileMonitor(self.config, self.on_documents_changed)
                self.file_monitor.start()
                
            # Obtém documentos do monitor de arquivos
            self.documents = self.file_monitor.get_documents()
            
            # Limpa o item de carregamento
            self.files_list.DeleteAllItems()
            
            if self.documents:
                # Esconde a mensagem de nenhum arquivo
                self.no_files_panel.Hide()
                self.files_list.Show()
                
                # Adiciona documentos à lista
                for i, doc in enumerate(self.documents):
                    self.files_list.InsertItem(i, doc.name)
                    self.files_list.SetItem(i, 1, doc.formatted_date)
                    self.files_list.SetItem(i, 2, doc.formatted_size)
                    
                    # Adiciona contagem de páginas
                    pages = str(doc.pages) if hasattr(doc, "pages") and doc.pages > 0 else "?"
                    self.files_list.SetItem(i, 3, pages)
            else:
                # Mostra a mensagem de nenhum arquivo
                self.no_files_panel.Show()
                self.files_list.Hide()
        
        except Exception as e:
            # Captura específica para erros
            logger.error(f"Erro ao carregar documentos: {str(e)}")
            self.files_list.DeleteAllItems()
            self.files_list.Show()
            self.no_files_panel.Hide()
            
            # Adiciona mensagem de erro à lista
            self.files_list.InsertItem(0, f"Erro ao carregar documentos: {str(e)}")
            self.files_list.SetItem(0, 1, "")
            self.files_list.SetItem(0, 2, "")
            self.files_list.SetItem(0, 3, "")
        
        # Atualiza o layout
        self.content_panel.Layout()
    
    def on_documents_changed(self, documents):
        """
        Callback chamado quando a lista de documentos é alterada
        
        Args:
            documents (list): Lista de documentos
        """
        self.documents = documents
        
        # Atualiza a UI se estivermos na tela de documentos
        if self.content_title.GetLabel() == "Arquivos para Impressão" and self.IsShown():
            # Usa CallAfter para garantir que a atualização da UI aconteça na thread principal
            wx.CallAfter(self.load_documents)

    def on_file_right_click(self, event):
        """Manipula o clique com o botão direito na lista de arquivos"""
        # Obtém o item clicado
        pos = event.GetPosition()
        item, flags = self.files_list.HitTest(pos)
        
        if item != -1:
            # Obtém o documento correspondente
            if item < len(self.documents):
                document = self.documents[item]
                
                # Cria um menu de contexto
                menu = wx.Menu()
                
                # Adiciona itens ao menu
                print_item = menu.Append(wx.ID_ANY, "Imprimir")
                delete_item = menu.Append(wx.ID_ANY, "Excluir")
                
                # Vincula eventos aos itens
                self.Bind(wx.EVT_MENU, lambda e: self.on_print_document(document), print_item)
                self.Bind(wx.EVT_MENU, lambda e: self.on_delete_document(document), delete_item)
                
                # Exibe o menu
                self.PopupMenu(menu)
                menu.Destroy()
    
    def on_print_document(self, document):
        """
        Imprime o documento selecionado diretamente do sistema de arquivos
        
        Args:
            document (Document): Documento a ser impresso
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
        Exclui o documento selecionado do sistema de arquivos
        
        Args:
            document (Document): Documento a ser excluído
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
                
                # O monitor de arquivos tratará de remover da lista
                wx.MessageBox(f"Documento '{document.name}' excluído com sucesso.",
                            "Exclusão", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                logger.error(f"Erro ao excluir documento: {str(e)}")
                wx.MessageBox(f"Erro ao excluir documento: {str(e)}",
                            "Erro", wx.OK | wx.ICON_ERROR)
        
        dlg.Destroy()
    
    def stop_file_monitor(self):
        """Para o monitor de arquivos"""
        if hasattr(self, 'file_monitor'):
            self.file_monitor.stop()
            
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
    
    def on_size(self, event):
        """Manipula o evento de redimensionamento da janela"""
        if not self.IsMaximized() and not self.IsIconized():
            # Salva o novo tamanho
            height, width = self.GetSize()
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

    
    def exit_application(self):
        """Fecha completamente a aplicação"""
        # Salva o tamanho e posição da janela
        self._save_window_geometry()
        
        # Para o monitoramento de pastas se estiver ativo
        self._stop_folder_monitoring()
        
        # Para o agendador de tarefas
        if self.scheduler:
            self.scheduler.stop()
        
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
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitor_folder, daemon=True)
            self.monitoring_thread.start()
    
    def _stop_folder_monitoring(self):
        """Para o monitoramento da pasta de PDFs"""
        self.monitoring_active = False
    
    def _monitor_folder(self):
        """Função executada em thread para monitorar a pasta de PDFs"""
        pdf_dir = self.config.pdf_dir
        processed_files = set()
        
        while self.monitoring_active:
            try:
                # Verifica se há novos arquivos
                for filename in os.listdir(pdf_dir):
                    if filename.endswith(".pdf") and filename not in processed_files:
                        file_path = os.path.join(pdf_dir, filename)
                        
                        # Verifica se o arquivo está completamente escrito
                        if self._is_file_ready(file_path):
                            logger.info(f"Novo arquivo encontrado para impressão automática: {filename}")
                            
                            # Processa o novo arquivo
                            # (aqui seria chamada a função de impressão automática)
                            
                            # Marca como processado
                            processed_files.add(filename)
                            
                            # Atualiza a lista de documentos se a janela estiver visível
                            if self.IsShown() and self.content_title.GetLabel() == "Arquivos para Impressão":
                                wx.CallAfter(self.load_documents)
                
                # Aguarda antes da próxima verificação
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Erro ao monitorar pasta: {str(e)}")
                time.sleep(5)  # Aguarda mais tempo em caso de erro
    
    def _is_file_ready(self, file_path):
        """
        Verifica se um arquivo está pronto para processamento
        
        Args:
            file_path (str): Caminho do arquivo
            
        Returns:
            bool: True se o arquivo está pronto
        """
        try:
            # Tenta abrir o arquivo com acesso exclusivo (Windows)
            # Se conseguir, o arquivo não está sendo escrito
            if os.name == 'nt':
                try:
                    with open(file_path, 'rb', 0) as f:
                        return True
                except:
                    return False
            else:
                # Em sistemas UNIX, verifica se o arquivo não foi modificado recentemente
                mtime = os.path.getmtime(file_path)
                if time.time() - mtime > 1.0:  # arquivo não modificado no último segundo
                    return True
                return False
        except:
            return False
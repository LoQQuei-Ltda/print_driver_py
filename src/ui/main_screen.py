"""Tela principal"""
import logging
import os
import wx
import threading
import time
from src.api.client import APIError
from src.utils.auth import AuthError
from src.ui.document_list import DocumentListPanel


logger = logging.getLogger("PrintManager.UI.MainScreen")

class MainScreen(wx.Frame):

    def __init__(self, parent, auth_manager, theme_manager, api_client, config, on_logout):
        """Inicializa a tela principal"""
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Gerenciador de Impressão",
            pos=wx.DefaultPosition,
            size=wx.Size(1024, 768),
            style=wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL
        )

        self.auth_manager = auth_manager
        self.theme_manager = theme_manager
        self.api_client = api_client
        self.config = config
        self.on_logout = on_logout

        self.monitoring_active = False

        icon_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "ui", "resources", "icon.ico")
        if os.path.exists(icon_path):
            self.SetIcon(wx.Icon(icon_path))

        self.__init_ui()

        self.Centre(wx.BOTH)

        self.theme_manager.apply_theme_to_window(self)

        self._load_data()

        if self.config.get("auto_print", False):
            self._start_folder_monitoring()

        self.Bind(wx.EVT_CLOSE, self.on_close)

    def __init_ui(self):
        """Inicializa a interface gráfica"""
        colors = self.theme_manager.get_theme_colors()

        self.main_panel = wx.Panel(self)
        self.main_panel.SetBackgroundColour(colors["bg_color"])

        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.sidebar_panel = wx.Panel(self.main_panel)
        self.sidebar_panel.SetBackgroundColour(colors["panel_bg"])
        sidebar_sizer = wx.BoxSizer(wx.VERTICAL)

        user_panel = wx.Panel(self.sidebar_panel)
        user_panel.SetBackgroundColour(colors["panel_bg"])
        user_sizer = wx.BoxSizer(wx.HORIZONTAL)

        user_info = self.auth_manager.get_current_user()
        user_name = user_info.get("name", user_info.get("email", "Usuário"))
        user_initial = user_name[0].upper() if user_name else "U"

        avatar_size = 40
        avatar_panel = wx.Panel(user_panel, size(avatar_size, avatar_size))
        avatar_panel.SetBackgroundColour(colors["accent_color"])

        def on_avatar_paint(event):
            dc = wx.PaintDC(avatar_panel)
            dc.SetBrush(wx.Brush(colors["accent_color"]))
            dc.SetPen(wx.Pen(colors["accent_color"]))
            dc.DrawCircle(avatar_size/2, avatar_size/2, avatar_size/2)

            dc.SetTextForeground(wx.WHITE)
            font = wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)
            dc.SetFont(font)

            text_width, text_height = dc.GetTextExtent(user_initial)
            dc.DrawText(user_initial, (avatar_size - text_width) / 2, (avatar_size - text_height) / 2)

        avatar_panel.Bind(wx.EVT_PAINT, on_avatar_paint)

        user_name_text = wx.StaticText(user_panel, label=user_name)
        user_name_text.SetForegroundColour(colors["text_color"])
        user_name_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        user_sizer.Add(avatar_panel, 0, wx.ALL, 5)
        user_sizer.Add(user_name_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)
        user_panel.SetSizer(user_sizer)

        sidebar_sizer.Add(user_panel, 0, wx.EXPAND | wx.ALL, 10)
        sidebar_sizer.Add(wx.StaticLine(self.sidebar_panel), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)

        def create_menu_item(label, icon=None, callback=None):
            item_panel = wx.Panel(self.sidebar_panel)
            item_panel.SetBackgroundColour(colors["panel_bg"])
            item_sizer = wx.BoxSizer(wx.HORIZONTAL)

            if icon:
                icon_bitmap = wx.StaticBitmap(item_panel, bitmap=icon)
                item_sizer.Add(icon_bitmap, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 5)

            item_text = wx.StaticText(item_panel, label=label)
            item_text.SetForegroundColour(colors["text_color"])
            item_sizer.Add(item_text, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)

            item_panel.SetSizer(item_sizer)

            if callback:
                item_panel.Bind(wx.EVT_LEFT_DOWN, callback)
                item_text.Bind(wx.EVT_RIGHT_DOWN, callback)
                if icon:
                    icon_bitmap.Bind(wx.EVT_RIGHT_DOWN, callback)

            def on_enter(event):
                item_panel.SetBackgroundColour(colors["hover_bg"])
                item_panel.Refresh()

            def on_leave(event):
                item_panel.SetBackgroundColour(colors["panel_bg"])
                item_panel.Refresh()

            item_panel.Bind(wx.EVT_ENTER_WINDOW, on_enter)
            item_panel.Bind(wx.EVT_LEAVE_WINDOW, on_leave)

            return item_panel
        
        doc_icon = self.theme_manager.get_theme_bitmap(
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "src", "ui", "resources", "document.png"),
            (20, 20)
        )

        self.menu_items = []

        documents_item = create_menu_item("Documentos", doc_icon, self._show_documents)
        self.menu_items.append(documents_item)
        sidebar_sizer.Add(documents_item, 0, wx.EXPAND | wx.TOP, 10)

        system_item = create_menu_item("Sistema", None, self._show_system)
        self.menu_items.append(system_item)
        sidebar_sizer.Add(system_item, 0, wx.EXPAND | wx.TOP, 5)

        self.auto_print_panel = wx.Panel(self.sidebar_panel)
        auto_print_sizer = wx.BoxSizer(wx.HORIZONTAL)

        auto_print_label = wx.StaticText(self.auto_print_panel, label="Impressão automática")
        auto_print_label.SetForegroundColour(colors["text_color"])

        self.auto_print_toggle = wx.ToggleButton(self.auto_print_panel, label="", size=(40, 20))
        self.auto_print_toggle.SetValue(self.config.get("auto_print", False))

        def on_toggle(event):
            is_on = event.GetEventObject().GetValue()
            self.config.set("auto_print", is_on)

            if is_on:
                self._start_folder_monitoring()
            else:
                self._stop_folder_monitoring()

            self._update_toggle_appearence()
        
        self.auto_print_toggle.Bind(wx.EVT_TOGGLEBUTTON, on_toggle)

        auto_print_sizer.Add(auto_print_label, 0, wx.ALIGN_CENTER_VERTICAL)
        auto_print_sizer.Add((0, 0), 1, wx.EXPAND)
        auto_print_sizer.Add(self.auto_print_toggle, 0, wx.ALIGN_CENTER_VERTICAL)

        self.auto_print_panel.SetSizer(auto_print_sizer)

        sidebar_sizer.Add(self.auto_print_panel, 0, wx.EXPAND | wx.ALL, 10)

        printer_config_item = create_menu_item("Configurações manuais das impressoras", None, self._show_printer_config)
        self.menu_items.append(printer_config_item)
        sidebar_sizer.Add(printer_config_item, 0, wx.EXPAND | wx.TOP, 5)

        update_printers_item = create_menu_item("Atualizar impressoras com o servidor principal", None, self._update_printers)
        self.menu_items.append(update_printers_item)
        sidebar_sizer.Add(update_printers_item, 0, wx.EXPAND | wx.TOP, 5)

        sidebar_sizer.Add((0, 0), 1, wx.EXPAND)

        logout_button = self.theme_manager.get_custom_button(self.sidebar_panel, "Sair")
        logout_button.bind(wx.EVT_BUTTON, self._logout)

        sidebar_sizer.Add(logout_button, 0, wx.EXPAND | wx.ALL, 10)

        self.sidebar_panel.SetSizer(sidebar_sizer)

        self.content_panel = wx.Panel(self.main_panel)
        self.content_panel.SetBackgroundColour(colors["bg_color"])

        self.content_sizer = wx.BoxSizer(wx.VERTICAL)

        self.title_panel = wx.Panel(self.content_panel)
        self.title_panel.SetBackgroundColour(colors["bg_color"])
        title_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self.content_title = wx.StaticText(self.title_panel, label="Arquivos para Impressão")
        self.content_title.SetForegroundColour(colors["text_color"])
        self.content_title.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))

        title_sizer.Add(self.content_title, 0, wx.ALIGN_CENTER_VERTICAL)
        title_sizer.Add((0, 0), 1, wx.EXPAND)

        refresh_button = self.theme_manager.get_custom_button(self.title_panel, "Atualizar")
        refresh_button.Bind(wx.EVT_BUTTON, self._load_data)

        theme_button = self.theme_manager.get_custom_button(
            self.title_panel,
            "Tema " + ("Claro" if self.theme_manager.is_dark else "Escuro"),
        )
        theme_button.Bind(wx.EVT_BUTTON, self._toggle_theme)

        title_sizer.Add(theme_button, 0, wx.RIGHT, 10)
        title_sizer.Add(refresh_button, 0, wx.RIGHT, 10)

        self.title_panel.SetSizer(title_sizer)

        self.document_list = DocumentListPanel(
            self.content_panel,
            self.theme_manager,
            self.api_client,
            self.on_document_print,
            self.on_document_delete
        )

        self.content_sizer.Add(self.title_panel, 0, wx.EXPAND | wx.ALL, 10)
        self.content_sizer.Add(self.document_list, 0, wx.EXPAND | wx.ALL, 10) 

        self.content_panel.SetSizer(self.content_sizer)

        main_sizer.Add(self.sidebar_panel, 0, wx.EXPAND)
        main_sizer.Add(self.content_panel, 1, wx.EXPAND)

        self.main_panel.SetSizer(main_sizer)

        self._update_toggle_appearence()

        self._show_documents()

    def _update_toggle_appearence(self):
        """Atualiza a aparência do botão de impressão automática"""
        colors = self.theme_manager.get_theme_colors()
        is_on = self.auto_print_toggle.GetValue()
        
        if is_on:
            self.auto_print_toggle.SetBackgroundColour(colors["toggle_on"])
            self.auto_print_toggle.SetLabel("Ativo")

        else:
            self.auto_print_toggle.SetBackgroundColour(colors["toggle_off"])
            self.auto_print_toggle.SetLabel("Desativado")

    def _load_data(self):
        """Carrega os dados da lista de documentos"""
        try:
            self.document_list.load_documents()
        except APIError as e:
            logger.error("Erro ao carregar dados da lista de documentos: %s", e)
            wx.MessageBox(f"Erro ao carregar dados da lista de documentos: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            logger.error("Erro ao carregar dados da lista de documentos: %s", e)
            wx.MessageBox(f"Erro ao carregar dados da lista de documentos: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)

    def _show_documents(self):
        """Mostra a lista de documentos"""
        self.content_title.SetLabel("Arquivos para Impressão")
        self.document_list.Show()
        self._load_data()
        self.content_panel.Layout()

    def _show_system(self):
        """Mostra a lista de impressoras"""
        self.content_title.SetLabel("Impressoras")
        self.document_list.Hide()
        self.content_panel.Layout()

    def _show_printer_config(self):
        """Mostra a tela de configuração das impressoras"""
        self.content_title.SetLabel("Configurações manuais das impressoras")
        self.document_list.Hide()
        self.content_panel.Layout()

    def _update_printers(self):
        """Atualiza as impressoras com o servidor principal"""
        try:
            self.api_client.update_printers()
            wx.MessageBox("Impressoras atualizadas com sucesso", "Atualização", wx.OK | wx.ICON_INFORMATION)
        except APIError as e:
            logger.error("Erro ao atualizar impressoras: %s", e)
            wx.MessageBox(f"Erro ao atualizar impressoras: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
        except Exception as e:
            logger.error("Erro ao atualizar impressoras: %s", e)
            wx.MessageBox(f"Erro ao atualizar impressoras: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)

    def _toggle_theme(self, event=None):
        """Alterna o tema atual"""
        new_theme = self.theme_manager.switch_theme()

        event.GetEventObject().SetLabel("Tema " + ("Claro" if new_theme == "dark" else "Escuro"))

        self.theme_manager.apply_theme_to_window(self)

        self._update_toggle_appearence()

    def _logout(self):
        """Faz logout"""
        try:
            if self.auth_manager.logout():
                self._stop_folder_monitoring()

                if self.on_logout:
                    self.on_logout()
        except Exception as e:
            logger.error("Erro ao fazer logout: %s", e)
            wx.MessageBox(f"Erro ao fazer logout: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)

    def _start_folder_monitoring(self):
        """Inicia o monitoramento de pastas"""
        if not self.monitoring_active:
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self._monitor_folder, daemon=True)
            self.monitoring_thread.start()

    def _stop_folder_monitoring(self):
        """Para o monitoramento de pastas"""
        self.monitoring_active = False

    def _monitor_folder(self):
        """Monitora a pasta de impressão"""
        pdf_dir = self.config.get("pdf_dir")
        processed_files = set()

        while self.monitoring_active:
            try:
                for filename in os.listdir(pdf_dir):
                    if filename.endswith(".pdf") and filename not in processed_files:
                        file_path = os.path.join(pdf_dir, filename)

                        if self._is_file_ready(file_path):
                            logger.info("Arquivo %s está pronto para impressão", filename)
                            
                            # TODO: fazer lógica para ver se precisa imprimir automaticamente
                            self._auto_print_file(file_path, filename)

                            processed_files.add(filename)

                if len(processed_files) > 1000:
                    processed_files = set(list(processed_files)[:1000])

                time.sleep(1)
            except Exception as e:
                logger.error("Erro ao monitorar pasta de impressão: %s", e)
                time.sleep(3)

    def _is_file_ready(self, file_path):
        """Verifica se o arquivo está pronto para impressão"""
        try:
            if os.name == 'nt':
                with open(file_path, 'rb', 0) as f:
                    return True
            else:
                mtime = os.path.getmtime(file_path)
                if time.time() - mtime > 1.0:
                    return True
                return False
        except:
            return False
        
    def _auto_print_file(self, file_path, filename):
        """Imprime automaticamente o arquivo"""
        default_printer = self.config.get("default_printer", "")

        if default_printer:
            # TODO: fazer lógica para imprimir automaticamente
            logger.info("Imprimindo arquivo %s com impressora %s", filename, default_printer)

        else:
            logger.info("Imprimindo arquivo %s com impressora automática", filename)

    def on_document_print(self, document_id, printer_id):
        """Executa a impressão de um documento"""
        try:
            # TODO: fazer lógica para imprimir automaticamente
            wx.MessageBox(f"Imprimindo documento {document_id} com impressora {printer_id}", "Impressão", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            logger.error("Erro ao imprimir documento: %s", e)
            wx.MessageBox(f"Erro ao imprimir documento: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)

    def on_document_delete(self, document_id):
        """Deleta um documento"""
        try:
            wx.MessageBox(f"Deletando documento {document_id}", "Deletar", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            logger.error("Erro ao deletar documento: %s", e)
            wx.MessageBox(f"Erro ao deletar documento: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)

    def on_close(self, event):
        """Fecha a janela principal"""
        self._stop_folder_monitoring()

        event.Skip()

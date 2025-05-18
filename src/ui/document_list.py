import logging
import os
import wx
import datetime
from src.api.client import APIError

logger = logging.getLogger("PrintManager.UI.DocumentList")

class DocumentListPanel(wx.Panel):

    def __init__(self, parent, theme_manager, api_client, on_print, on_delete):
        super().__init__(
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            style=wx.TAB_TRAVERSAL
        )

        self.theme_manager = theme_manager
        self.api_client = api_client
        self.on_print = on_print
        self.on_delete = on_delete

        self.documents = []

        self.colors = self.theme_manager.get_theme_colors()

        self._init_ui()

    def _init_ui(self):
        """Inicializa a interface gráfica"""
        self.SetBackgroundColour(self.colors["panel_bg"])

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.document_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE
        )

        # Ajusta as colunas para incluir a página
        self.document_list.InsertColumn(0, "Nome", width=300)
        self.document_list.InsertColumn(1, "Data", width=150)
        self.document_list.InsertColumn(2, "Tamanho", width=100)
        self.document_list.InsertColumn(3, "Páginas", width=80)  # Nova coluna para páginas
        self.document_list.InsertColumn(4, "Ações", width=200)

        self.document_list.SetBackgroundColour(self.colors["panel_bg"])
        self.document_list.SetForegroundColour(self.colors["text_color"])

        self.document_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_document_selected)

        self.empty_panel = wx.Panel(self)
        self.empty_panel.SetBackgroundColour(self.colors["panel_bg"])
        empty_sizer = wx.BoxSizer(wx.VERTICAL)

        document_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "src", "ui", "resources", "empty_document.png"
        )

        if os.path.exists(document_icon_path):
            empty_icon = wx.StaticBitmap(
                self.empty_panel,
                bitmap=wx.Bitmap(document_icon_path),
                size=(64, 64)
            )
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 30)

        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhum documento encontrado para impressão"
        )
        empty_text.SetForegroundColour(self.colors["text_secondary"])
        empty_text.SetFont(wx.Font(
            12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        ))

        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 15)
        self.empty_panel.SetSizer(empty_sizer)

        main_sizer.Add(self.document_list, 1, wx.EXPAND)
        main_sizer.Add(self.empty_panel, 1, wx.EXPAND)

        self.empty_panel.Hide()

        self.SetSizer(main_sizer)

        self.load_documents()

    def load_documents(self):
        """Carrega os documentos disponíveis para impressão diretamente do sistema de arquivos"""
        try:
            self.document_list.DeleteAllItems()
            self.document_list.InsertItem(0, "Carregando...")
            wx.GetApp().Yield()

            # Tenta obter documentos do monitor de arquivos da tela principal se estiver disponível
            app = wx.GetApp()
            self.documents = []
            
            if hasattr(app, 'main_screen') and hasattr(app.main_screen, 'file_monitor'):
                self.documents = app.main_screen.file_monitor.get_documents()
            else:
                # Caso não tenha acesso ao monitor principal, cria um monitor temporário
                from src.utils.file_monitor import FileMonitor
                file_monitor = FileMonitor(app.config)
                file_monitor._load_initial_documents()
                self.documents = file_monitor.get_documents()

            self.document_list.DeleteAllItems()

            if self.documents and len(self.documents) > 0:
                for i, doc in enumerate(self.documents):
                    date_str = self._format_date(doc.created_at)
                    size_str = self._format_size(doc.size)
                    pages_str = str(doc.pages) if hasattr(doc, "pages") and doc.pages > 0 else "?"

                    index = self.document_list.InsertItem(i, doc.name)
                    self.document_list.SetItem(index, 1, date_str)
                    self.document_list.SetItem(index, 2, size_str)
                    self.document_list.SetItem(index, 3, pages_str)  # Exibe contagem de páginas
                    
                    self._create_action_buttons(doc, index)

                self.document_list.Show()
                self.empty_panel.Hide()

            else:
                self.document_list.Hide()
                self.empty_panel.Show()

        except Exception as e:
            logger.error("Erro ao carregar documentos: %s", e)
            self.document_list.DeleteAllItems()
            self.document_list.InsertItem(0, "Erro ao carregar documentos")

    def _create_action_buttons(self, document, index):
        """
        Cria os botões de ações para um documento
        
        Args:
            document (Document): Documento para o qual criar botões
            index (int): Índice na lista
        """
        rect = self.document_list.GetItemRect(index, wx.LIST_RECT_BOUNDS)
        col_rect = self.document_list.GetSubItemRect(index, 4)  # Coluna de ações é agora a 4

        panel = wx.Panel(self.document_list, size=(col_rect.width, rect.height))
        panel.SetBackgroundColour(self.colors["panel_bg"])

        sizer = wx.BoxSizer(wx.HORIZONTAL)

        print_button = self.theme_manager.get_custom_button(panel, "Imprimir", accent=True)
        print_button.SetMinSize((100, 30))

        # Manter referência ao documento atual para os callbacks
        current_document = document

        def on_print(event):
            self.on_print(current_document)

        print_button.Bind(wx.EVT_BUTTON, on_print)

        delete_button = self.theme_manager.get_custom_button(panel, "Excluir")
        delete_button.SetMinSize((80, 30))

        def on_delete(event):
            dialog = wx.MessageDialog(
                self,
                "Tem certeza que deseja excluir o documento?",
                "Confirmar exclusão",
                wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
            )

            if dialog.ShowModal() == wx.ID_YES:
                self.on_delete(current_document)

            dialog.Destroy()

        delete_button.Bind(wx.EVT_BUTTON, on_delete)

        sizer.Add(print_button, 0, wx.RIGHT, 5)
        sizer.Add(delete_button, 0)

        panel.SetSizer(sizer)

        window_rect = self.document_list.GetRect()
        panel.SetPosition(wx.Point(col_rect.x, rect.y))

    def on_document_selected(self, event):
        """Executa quando um item é selecionado"""
        self.document_list.Select(event.GetIndex(), False)

    def _format_date(self, date_str):
        """Formata a data"""
        try:
            if not date_str:
                return ""
            
            dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception as e:
            logger.error("Erro ao formatar data: %s", e)
            return date_str
        
    def _format_size(self, size_bytes):
        """Formata o tamanho"""
        try:
            if not size_bytes:
                return "0 KB"
            
            if size_bytes < 1024:
                return f"{size_bytes} B"
            elif size_bytes < 1024 * 1024:
                return f"{size_bytes / 1024:.2f} KB"
            elif size_bytes < 1024 * 1024 * 1024:
                return f"{size_bytes / (1024 * 1024):.2f} MB"
            else:
                return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
        except Exception as e:
            logger.error("Erro ao formatar tamanho: %s", e)
            return str(size_bytes) + " B"
#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Componente de listagem de documentos moderno - VERSÃO CORRIGIDA
"""

import logging
import os
import wx
import datetime
from src.api.client import APIError
from src.utils.resource_manager import ResourceManager
from src.ui.print_dialog import select_printer_and_print

logger = logging.getLogger("PrintManager.UI.DocumentList")

class DocumentCardPanel(wx.Panel):
    """Painel de card para exibir um documento com botões de ação"""
    
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
        self.doc_name_widget = None
        self._is_destroyed = False  # Flag para controlar se foi destruído
        self._pending_timers = []   # Lista de timers pendentes
        
        # Define cor de fundo (cinza escuro)
        self.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        # Eventos para hover
        self.hover = False
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        
        # Bind do destroy para limpar timers
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)
        
        self._init_ui()
    
    def _on_destroy(self, event):
        """Chamado quando o widget está sendo destruído"""
        self._is_destroyed = True
        # Cancela todos os timers pendentes
        for timer in self._pending_timers:
            try:
                timer.Stop()
            except:
                pass
        self._pending_timers.clear()
        event.Skip()
    
    def _safe_call_later(self, milliseconds, func):
        """Versão segura do CallLater que cancela automaticamente se destruído"""
        if self._is_destroyed:
            return
            
        def safe_wrapper():
            if not self._is_destroyed and self:
                try:
                    func()
                except RuntimeError:
                    # Widget foi destruído
                    pass
        
        timer = wx.CallLater(milliseconds, safe_wrapper)
        self._pending_timers.append(timer)
        return timer
    
    def _init_ui(self):
        """Inicializa a interface do usuário do card"""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone do documento (esquerda)
        doc_icon_path = ResourceManager.get_image_path("document.png")
        
        if os.path.exists(doc_icon_path):
            doc_icon = wx.StaticBitmap(
                self,
                bitmap=wx.Bitmap(doc_icon_path),
                size=(32, 32)
            )
            main_sizer.Add(doc_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        # Painel de informações (centro)
        self.info_panel = wx.Panel(self)
        self.info_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        info_sizer = wx.BoxSizer(wx.VERTICAL)

        # Define a fonte do nome
        self.name_font = wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD)

        # Inicialmente cria com nome completo
        self.doc_name_widget = wx.StaticText(self.info_panel, label=self.document.name)
        self.doc_name_widget.SetForegroundColour(wx.WHITE)
        self.doc_name_widget.SetFont(self.name_font)
        
        # Adiciona tooltip com nome completo
        self.doc_name_widget.SetToolTip(self.document.name)
        
        info_sizer.Add(self.doc_name_widget, 0, wx.BOTTOM, 5)
        
        # Detalhes do documento
        details_text = f"{self._format_date(self.document.created_at)} · {self.document.formatted_size}"
        if hasattr(self.document, "pages") and self.document.pages > 0:
            details_text += f" · {self.document.pages} páginas"
            
        details = wx.StaticText(self.info_panel, label=details_text)
        details.SetForegroundColour(wx.Colour(180, 180, 180))
        details.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        info_sizer.Add(details, 0)
        
        self.info_panel.SetSizer(info_sizer)
        main_sizer.Add(self.info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
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
        
        # Bind de eventos de resize
        self.Bind(wx.EVT_SIZE, self._on_size)
        
        # Força o layout inicial e depois ajusta o nome
        self.Layout()
        self._safe_call_later(100, self._adjust_document_name)
    
    def _on_size(self, event):
        """Manipula eventos de redimensionamento"""
        if not self._is_destroyed:
            self._safe_call_later(50, self._adjust_document_name)
        event.Skip()
    
    def _adjust_document_name(self):
        """Ajusta o nome do documento baseado no tamanho disponível"""
        if self._is_destroyed or not self.doc_name_widget:
            return
            
        try:
            # Calcula a largura disponível
            total_width = self.GetSize().width
            if total_width <= 0:
                return
                
            # Subtrai: ícone (52px) + botões (200px) + margens (40px)
            available_width = max(150, total_width - 292)
            
            # Função de truncamento
            def truncate_text(text, max_width, font):
                if max_width <= 0:
                    return text
                    
                bmp = wx.Bitmap(1, 1)
                dc = wx.MemoryDC(bmp)
                dc.SetFont(font)
                
                text_width = dc.GetTextExtent(text)[0]
                if text_width <= max_width:
                    return text
                
                ellipsis_width = dc.GetTextExtent("...")[0]
                for i in range(len(text), 0, -1):
                    sub_text = text[:i]
                    width = dc.GetTextExtent(sub_text)[0]
                    if width + ellipsis_width <= max_width:
                        return sub_text + "..."
                return "..."
            
            # Aplica o truncamento
            truncated_name = truncate_text(self.document.name, available_width, self.name_font)
            
            # Atualiza apenas se necessário
            if self.doc_name_widget.GetLabel() != truncated_name:
                self.doc_name_widget.SetLabel(truncated_name)
                self.info_panel.Layout()
                
        except RuntimeError:
            # Widget foi destruído durante a execução
            self._is_destroyed = True
    
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
    
    def _format_date(self, date_str):
        """Formata a data"""
        try:
            if not date_str:
                return ""
            
            dt = datetime.datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception as e:
            logger.error(f"Erro ao formatar data: {str(e)}")
            return date_str

class DocumentListPanel(wx.ScrolledWindow):
    """Painel de lista de documentos moderna com cards"""
    
    def __init__(self, parent, theme_manager, api_client, on_print, on_delete):
        super().__init__(
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            size=wx.DefaultSize,
            style=wx.TAB_TRAVERSAL
        )

        self.theme_manager = theme_manager
        self.api_client = api_client
        self.on_print = on_print
        self.on_delete = on_delete

        self.documents = []
        self.document_cards = []  # Mantém referência aos cards criados
        self.colors = {"bg_color": wx.Colour(18, 18, 18), 
                    "panel_bg": wx.Colour(25, 25, 25),
                    "accent_color": wx.Colour(255, 90, 36),
                    "text_color": wx.WHITE,
                    "text_secondary": wx.Colour(180, 180, 180)}

        self._init_ui()
        
        self.SetScrollRate(0, 10)

    def _init_ui(self):
        """Inicializa a interface gráfica"""
        self.SetBackgroundColour(self.colors["bg_color"])

        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel de cabeçalho com título e botão de atualizar
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(self.colors["bg_color"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Arquivos para Impressão")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(self.colors["text_color"])
        
        self.refresh_button = wx.Button(header_panel, label="Atualizar", size=(120, 36))
        self.refresh_button.SetBackgroundColour(wx.Colour(60, 60, 60))
        self.refresh_button.SetForegroundColour(self.colors["text_color"])
        self.refresh_button.Bind(wx.EVT_BUTTON, self.load_documents)
        
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
        self.content_panel.SetBackgroundColour(self.colors["bg_color"])
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel para exibir mensagem de "sem documentos"
        self.empty_panel = wx.Panel(self.content_panel)
        self.empty_panel.SetBackgroundColour(self.colors["bg_color"])
        empty_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Ícone de documento vazio
        document_icon_path = ResourceManager.get_image_path("empty_document.png")

        if os.path.exists(document_icon_path):
            empty_icon = wx.StaticBitmap(
                self.empty_panel,
                bitmap=wx.Bitmap(document_icon_path),
                size=(64, 64)
            )
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 50)

        # Texto para quando não há documentos
        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhum documento encontrado para impressão"
        )
        empty_text.SetForegroundColour(self.colors["text_secondary"])
        empty_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        self.empty_panel.SetSizer(empty_sizer)
        
        self.content_sizer.Add(self.empty_panel, 1, wx.EXPAND)
        self.content_panel.SetSizer(self.content_sizer)
        
        # Adiciona ao layout principal
        self.main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        self.main_sizer.Add(self.content_panel, 1, wx.EXPAND)
        
        self.SetSizer(self.main_sizer)

        self.load_documents()

    def _clear_existing_cards(self):
        """Limpa os cards existentes de forma segura"""
        # Primeiro marca todos os cards como destruídos
        for card in self.document_cards:
            if card and not card._is_destroyed:
                card._is_destroyed = True
        
        # Limpa a lista
        self.document_cards.clear()
        
        # Remove os widgets do painel
        for child in self.content_panel.GetChildren():
            if isinstance(child, DocumentCardPanel):
                child.Destroy()

    def load_documents(self, event=None):
        """Carrega os documentos disponíveis para impressão diretamente do sistema de arquivos"""
        try:
            # Limpa os cards existentes de forma segura
            self._clear_existing_cards()
            
            # Adiciona um indicador de carregamento
            loading_text = wx.StaticText(self.content_panel, label="Carregando documentos...")
            loading_text.SetForegroundColour(self.colors["text_color"])
            self.content_sizer.Insert(0, loading_text, 0, wx.ALIGN_CENTER | wx.ALL, 20)
            self.content_panel.Layout()
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

            # Remove o indicador de carregamento
            loading_text.Destroy()

            # Atualiza a visualização
            if self.documents and len(self.documents) > 0:
                self.empty_panel.Hide()
                
                # Cria um card para cada documento
                for doc in self.documents:
                    card = DocumentCardPanel(self.content_panel, doc, self.on_print, self.on_delete)
                    self.document_cards.append(card)  # Mantém referência
                    self.content_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            else:
                self.empty_panel.Show()
            
            # Ajusta o layout
            self.content_panel.Layout()
            self.Layout()
            
            self.FitInside()
            self.Refresh()

        except Exception as e:
            logger.error("Erro ao carregar documentos: %s", e)
            
            # Exibe mensagem de erro
            error_text = wx.StaticText(self.content_panel, label=f"Erro ao carregar documentos: {str(e)}")
            error_text.SetForegroundColour(wx.Colour(220, 53, 69))  # Vermelho
            self.content_sizer.Add(error_text, 0, wx.ALIGN_CENTER | wx.ALL, 20)
            
            self.content_panel.Layout()
            self.Layout()
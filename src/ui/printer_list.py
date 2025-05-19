#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Componente de listagem de impressoras moderno
"""

import os
import wx
import logging
from src.models.printer import Printer

logger = logging.getLogger("PrintManagementSystem.UI.PrinterList")

class PrinterCardPanel(wx.Panel):
    """Painel de card para exibir uma impressora"""
    
    def __init__(self, parent, printer, on_select=None):
        """
        Inicializa o painel de card
        
        Args:
            parent: Painel pai
            printer: Impressora a ser exibida
            on_select: Callback para seleção (opcional)
        """
        super().__init__(parent, style=wx.BORDER_NONE)
        
        self.printer = printer
        self.on_select = on_select
        
        # Define cor de fundo (cinza escuro)
        self.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        # Eventos para hover e clique
        self.hover = False
        self.Bind(wx.EVT_ENTER_WINDOW, self.on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self.on_leave)
        self.Bind(wx.EVT_PAINT, self.on_paint)
        
        if on_select:
            self.Bind(wx.EVT_LEFT_DOWN, self.on_click)
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa a interface do usuário do card"""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone da impressora (esquerda)
        printer_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "src", "ui", "resources", "printer.png"
        )
        
        if os.path.exists(printer_icon_path):
            printer_icon = wx.StaticBitmap(
                self,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(32, 32)
            )
            main_sizer.Add(printer_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        # Painel de informações (centro)
        info_panel = wx.Panel(self)
        info_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Nome da impressora
        printer_name = wx.StaticText(info_panel, label=self.printer.name)
        printer_name.SetForegroundColour(wx.WHITE)
        printer_name.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(printer_name, 0, wx.BOTTOM, 5)
        
        # Detalhes da impressora
        details_text = f"Endereço MAC: {self.printer.mac_address}" if self.printer.mac_address else "Impressora local"
        details = wx.StaticText(info_panel, label=details_text)
        details.SetForegroundColour(wx.Colour(180, 180, 180))
        details.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        info_sizer.Add(details, 0)
        
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Indicador de status (direita)
        status_panel = wx.Panel(self, size=(20, 20))
        status_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        def on_status_paint(event):
            dc = wx.PaintDC(status_panel)
            
            # Desenha o indicador de status (círculo verde)
            dc.SetBrush(wx.Brush(wx.Colour(40, 167, 69)))  # Verde
            dc.SetPen(wx.Pen(wx.Colour(40, 167, 69)))
            dc.DrawCircle(10, 10, 6)
        
        status_panel.Bind(wx.EVT_PAINT, on_status_paint)
        main_sizer.Add(status_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        
        self.SetSizer(main_sizer)
    
    def on_enter(self, event):
        """Manipula o evento de mouse sobre o card"""
        self.hover = True
        self.Refresh()
    
    def on_leave(self, event):
        """Manipula o evento de mouse saindo do card"""
        self.hover = False
        self.Refresh()
    
    def on_click(self, event):
        """Manipula o clique no card"""
        if self.on_select:
            self.on_select(self.printer)
    
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

class PrinterListPanel(wx.ScrolledWindow):
    """Painel de lista de impressoras moderno com cards"""
    
    def __init__(self, parent, theme_manager, config, api_client, on_update=None):
        """
        Inicializa o painel de listagem de impressoras
        
        Args:
            parent: Pai do painel
            theme_manager: Gerenciador de temas
            config: Configuração da aplicação
            api_client: Cliente da API
            on_update: Callback chamado ao atualizar impressoras
        """
        super().__init__(
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            style=wx.TAB_TRAVERSAL
        )
        
        self.theme_manager = theme_manager
        self.config = config
        self.api_client = api_client
        self.on_update = on_update
        
        self.printers = []
        self.colors = {"bg_color": wx.Colour(18, 18, 18), 
                       "panel_bg": wx.Colour(25, 25, 25),
                       "accent_color": wx.Colour(255, 90, 36),
                       "text_color": wx.WHITE,
                       "text_secondary": wx.Colour(180, 180, 180)}
        
        self._init_ui()
        
        # Configura scrolling
        self.SetScrollRate(0, 10)
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel de cabeçalho com título e botão de atualizar
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(self.colors["bg_color"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Impressoras")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(self.colors["text_color"])
        
        self.update_button = wx.Button(header_panel, label="Atualizar Impressoras", size=(180, 36))
        self.update_button.SetBackgroundColour(wx.Colour(60, 60, 60))
        self.update_button.SetForegroundColour(self.colors["text_color"])
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update_printers)
        
        # Eventos de hover para o botão
        def on_update_enter(evt):
            self.update_button.SetBackgroundColour(wx.Colour(80, 80, 80))
            self.update_button.Refresh()
        
        def on_update_leave(evt):
            self.update_button.SetBackgroundColour(wx.Colour(60, 60, 60))
            self.update_button.Refresh()
        
        self.update_button.Bind(wx.EVT_ENTER_WINDOW, on_update_enter)
        self.update_button.Bind(wx.EVT_LEAVE_WINDOW, on_update_leave)
        
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        header_sizer.AddStretchSpacer()
        header_sizer.Add(self.update_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        
        header_panel.SetSizer(header_sizer)
        
        # Descrição
        description_panel = wx.Panel(self)
        description_panel.SetBackgroundColour(self.colors["bg_color"])
        description_sizer = wx.BoxSizer(wx.VERTICAL)
        
        description = wx.StaticText(
            description_panel,
            label="Impressoras disponíveis para o sistema. Clique em 'Atualizar' para sincronizar com o servidor."
        )
        description.SetForegroundColour(self.colors["text_secondary"])
        description.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        description_sizer.Add(description, 0, wx.LEFT | wx.BOTTOM, 20)
        description_panel.SetSizer(description_sizer)
        
        # Painel de conteúdo para os cards
        self.content_panel = wx.Panel(self)
        self.content_panel.SetBackgroundColour(self.colors["bg_color"])
        self.content_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel para exibir mensagem de "sem impressoras"
        self.empty_panel = wx.Panel(self.content_panel)
        self.empty_panel.SetBackgroundColour(self.colors["bg_color"])
        empty_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Ícone de impressora vazia
        printer_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "src", "ui", "resources", "printer.png"
        )
        
        if os.path.exists(printer_icon_path):
            empty_icon = wx.StaticBitmap(
                self.empty_panel,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(64, 64)
            )
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 50)
        
        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhuma impressora encontrada"
        )
        empty_text.SetForegroundColour(self.colors["text_secondary"])
        empty_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        self.empty_panel.SetSizer(empty_sizer)
        
        self.content_sizer.Add(self.empty_panel, 1, wx.EXPAND)
        self.content_panel.SetSizer(self.content_sizer)
        
        # Adiciona ao layout principal
        self.main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        self.main_sizer.Add(description_panel, 0, wx.EXPAND | wx.LEFT, 20)
        self.main_sizer.Add(self.content_panel, 1, wx.EXPAND)
        
        self.SetSizer(self.main_sizer)
        
        self.load_printers()
    
    def load_printers(self):
        """Carrega as impressoras da configuração"""
        try:
            # Limpa os cards existentes
            for child in self.content_panel.GetChildren():
                if isinstance(child, PrinterCardPanel):
                    child.Destroy()
            
            # Adiciona um indicador de carregamento
            loading_text = wx.StaticText(self.content_panel, label="Carregando impressoras...")
            loading_text.SetForegroundColour(self.colors["text_color"])
            self.content_sizer.Insert(0, loading_text, 0, wx.ALIGN_CENTER | wx.ALL, 20)
            self.content_panel.Layout()
            wx.GetApp().Yield()
            
            printers_data = self.config.get_printers()
            
            # Remove o indicador de carregamento
            loading_text.Destroy()
            
            if printers_data and len(printers_data) > 0:
                self.printers = [Printer(printer_data) for printer_data in printers_data]
                self.empty_panel.Hide()
                
                # Cria um card para cada impressora
                for printer in self.printers:
                    card = PrinterCardPanel(self.content_panel, printer)
                    self.content_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            else:
                self.printers = []
                self.empty_panel.Show()
            
            # Ajusta o layout
            self.content_panel.Layout()
            self.Layout()
            self.Refresh()
            
        except Exception as e:
            logger.error(f"Erro ao carregar impressoras: {str(e)}")
            
            # Exibe mensagem de erro
            error_text = wx.StaticText(self.content_panel, label=f"Erro ao carregar impressoras: {str(e)}")
            error_text.SetForegroundColour(wx.Colour(220, 53, 69))  # Vermelho
            self.content_sizer.Add(error_text, 0, wx.ALIGN_CENTER | wx.ALL, 20)
            
            self.content_panel.Layout()
            self.Layout()
    
    def on_update_printers(self, event=None):
        """Atualiza impressoras com o servidor principal"""
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
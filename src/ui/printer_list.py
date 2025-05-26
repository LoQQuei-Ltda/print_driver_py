#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Componente de listagem de impressoras com detalhes aprimorados
"""

import os
import wx
import logging
import threading
import json
from src.models.printer import Printer
from src.utils.resource_manager import ResourceManager
from src.ui.custom_button import create_styled_button

logger = logging.getLogger("PrintManagementSystem.UI.PrinterList")

def apply_dark_scrollbar_style(window):
    """Aplica estilo escuro nas barras de scroll"""
    try:
        if wx.Platform == '__WXMSW__':
            import ctypes
            hwnd = window.GetHandle()
            # Define cor escura para scrollbar
            ctypes.windll.user32.SetClassLongPtrW(
                hwnd, -10,
                ctypes.windll.gdi32.CreateSolidBrush(0x2D2D2D)
            )
        window.Refresh()
    except:
        pass
    
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
        printer_icon_path = ResourceManager.get_image_path("printer.png")
        
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
        # Linha 1: MAC e IP
        details_line1 = ""
        if hasattr(self.printer, 'mac_address') and self.printer.mac_address:
            details_line1 = f"MAC: {self.printer.mac_address}"
        
        if hasattr(self.printer, 'ip') and self.printer.ip:
            if details_line1:
                details_line1 += " | "
            details_line1 += f"IP: {self.printer.ip}"
            
        details1 = wx.StaticText(info_panel, label=details_line1 or "Impressora local")
        details1.SetForegroundColour(wx.Colour(180, 180, 180))
        details1.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        info_sizer.Add(details1, 0, wx.BOTTOM, 3)
        
        # Linha 2: Modelo e localização
        details_line2 = ""
        if hasattr(self.printer, 'model') and self.printer.model:
            details_line2 = f"Modelo: {self.printer.model}"
        
        if hasattr(self.printer, 'location') and self.printer.location:
            if details_line2:
                details_line2 += " | "
            details_line2 += f"Local: {self.printer.location}"
            
        if details_line2:
            details2 = wx.StaticText(info_panel, label=details_line2)
            details2.SetForegroundColour(wx.Colour(180, 180, 180))
            details2.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            info_sizer.Add(details2, 0)
        
        info_panel.SetSizer(info_sizer)
        main_sizer.Add(info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Indicador de status (direita)
        status_panel = wx.Panel(self, size=(20, 20))
        status_panel.SetBackgroundColour(wx.Colour(35, 35, 35))
        
        def on_status_paint(event):
            dc = wx.PaintDC(status_panel)
            
            # Determina a cor baseada no status, verificando os atributos de forma segura
            is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
            is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
            
            if is_online and is_ready:
                # Verde se estiver completamente pronta (online e idle)
                color = wx.Colour(40, 167, 69)  # Verde
            elif is_online:
                # Amarelo se estiver online mas não idle
                color = wx.Colour(255, 193, 7)  # Amarelo
            else:
                # Vermelho se não estiver online
                color = wx.Colour(220, 53, 69)  # Vermelho
            
            # Desenha o indicador de status (círculo)
            dc.SetBrush(wx.Brush(color))
            dc.SetPen(wx.Pen(color))
            dc.DrawCircle(10, 10, 6)
        
        status_panel.Bind(wx.EVT_PAINT, on_status_paint)
        main_sizer.Add(status_panel, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        
        # Se tem callback de seleção, adiciona um texto de dica
        if self.on_select:
            tip_text = wx.StaticText(self, label="Clique para detalhes")
            tip_text.SetForegroundColour(wx.Colour(180, 180, 180))
            main_sizer.Add(tip_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
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

class PrinterDetailsDialog(wx.Dialog):
    """Diálogo para exibir detalhes da impressora"""
    
    def __init__(self, parent, printer, api_client):
        """
        Inicializa o diálogo de detalhes
        
        Args:
            parent: Janela pai
            printer: Impressora a ser exibida
            api_client: Cliente da API
        """
        super().__init__(
            parent,
            title=f"Detalhes da Impressora: {printer.name}",
            size=(700, 600),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.printer = printer
        self.api_client = api_client
        self.details_loaded = False
        
        # Cores para temas
        self.colors = {"bg_color": wx.Colour(18, 18, 18), 
                      "panel_bg": wx.Colour(25, 25, 25),
                      "card_bg": wx.Colour(35, 35, 35),
                      "accent_color": wx.Colour(255, 90, 36),
                      "text_color": wx.WHITE,
                      "text_secondary": wx.Colour(180, 180, 180),
                      "border_color": wx.Colour(45, 45, 45),
                      "success_color": wx.Colour(40, 167, 69),
                      "error_color": wx.Colour(220, 53, 69),
                      "warning_color": wx.Colour(255, 193, 7)}
        
        # Aplica o tema ao diálogo
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self._init_ui()
        
        # Centraliza o diálogo
        self.CenterOnParent()
        
        # Carrega os detalhes da impressora
        self._load_printer_details()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Configura o painel principal
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(self.colors["bg_color"])
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cabeçalho
        header_panel = wx.Panel(self.panel)
        header_panel.SetBackgroundColour(self.colors["card_bg"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone da impressora
        printer_icon_path = ResourceManager.get_image_path("printer.png")
        
        if os.path.exists(printer_icon_path):
            printer_icon = wx.StaticBitmap(
                header_panel,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(48, 48)
            )
            header_sizer.Add(printer_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 15)
        
        # Informações básicas
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Nome da impressora
        printer_name = wx.StaticText(header_panel, label=self.printer.name)
        printer_name.SetForegroundColour(self.colors["text_color"])
        printer_name.SetFont(wx.Font(16, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(printer_name, 0, wx.BOTTOM, 8)
        
        # Modelo
        if self.printer.model:
            model_text = wx.StaticText(header_panel, label=f"Modelo: {self.printer.model}")
            model_text.SetForegroundColour(self.colors["text_secondary"])
            model_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            info_sizer.Add(model_text, 0, wx.BOTTOM, 5)
        
        # Estado
        if self.printer.state:
            state_text = wx.StaticText(header_panel, label=f"Estado: {self.printer.state}")
            state_text.SetForegroundColour(self.colors["text_secondary"])
            state_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            info_sizer.Add(state_text, 0)
        
        header_sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, 15)
        
        # Indicador de status (direita)
        # Determina a cor baseada no status, verificando os atributos de forma segura
        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
        
        if is_online and is_ready:
            # Verde se estiver completamente pronta (online e idle)
            status_color = self.colors["success_color"]
        elif is_online:
            # Amarelo se estiver online mas não idle
            status_color = self.colors["warning_color"]
        else:
            # Vermelho se não estiver online
            status_color = self.colors["error_color"]
        
        # Cria um bitmap para o status
        status_bitmap = wx.Bitmap(20, 20)
        dc = wx.MemoryDC()
        dc.SelectObject(status_bitmap)
        
        # Define fundo transparente
        dc.SetBackground(wx.Brush(self.colors["card_bg"]))
        dc.Clear()
        
        # Desenha o círculo de status
        dc.SetBrush(wx.Brush(status_color))
        dc.SetPen(wx.Pen(status_color))
        dc.DrawCircle(10, 10, 8)
        
        # Finaliza o desenho
        dc.SelectObject(wx.NullBitmap)
        
        # Cria e adiciona o bitmap ao layout
        status_icon = wx.StaticBitmap(header_panel, bitmap=status_bitmap)
        header_sizer.Add(status_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 15)
        
        header_panel.SetSizer(header_sizer)
        
        # Adiciona um borda arredondada ao header
        def on_header_paint(event):
            dc = wx.BufferedPaintDC(header_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = header_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in header_panel.GetChildren():
                child.Refresh()
            
        header_panel.Bind(wx.EVT_PAINT, on_header_paint)
        header_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Cria um panel personalizado para abrigar o notebook com tabs estilizadas
        tabs_container = wx.Panel(self.panel)
        tabs_container.SetBackgroundColour(self.colors["bg_color"])
        tabs_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cria um panel para as tabs
        tab_bar = wx.Panel(tabs_container)
        tab_bar.SetBackgroundColour(self.colors["card_bg"])
        tab_bar_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Define as tabs
        tab_names = ["Resumo", "Conectividade", "Atributos", "Suprimentos", "Diagnóstico"]
        self.tab_buttons = []
        self.tab_panels = []
        
        # Cria os botões das tabs com estilo moderno
        for i, tab_name in enumerate(tab_names):
            tab_button = wx.Panel(tab_bar)
            tab_button.SetBackgroundColour(self.colors["card_bg"])
            tab_button_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Texto da tab
            tab_text = wx.StaticText(tab_button, label=tab_name)
            tab_text.SetForegroundColour(self.colors["text_color"])
            tab_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            
            tab_button_sizer.Add(tab_text, 0, wx.ALL | wx.ALIGN_CENTER, 10)
            tab_button.SetSizer(tab_button_sizer)
            
            # Armazena dados para selecionar a tab
            tab_button.index = i
            tab_button.selected = (i == 0)  # A primeira tab começa selecionada
            
            # Eventos de clique e hover
            def on_tab_click(evt, button=tab_button):
                self._select_tab(button.index)
            
            def on_tab_enter(evt, button=tab_button):
                if not button.selected:
                    button.SetBackgroundColour(wx.Colour(40, 40, 40))
                    button.Refresh()
            
            def on_tab_leave(evt, button=tab_button):
                if not button.selected:
                    button.SetBackgroundColour(self.colors["card_bg"])
                    button.Refresh()
            
            tab_button.Bind(wx.EVT_LEFT_DOWN, on_tab_click)
            tab_button.Bind(wx.EVT_ENTER_WINDOW, on_tab_enter)
            tab_button.Bind(wx.EVT_LEAVE_WINDOW, on_tab_leave)
            
            # Destaca a tab selecionada
            if i == 0:
                tab_button.SetBackgroundColour(self.colors["accent_color"])
                tab_text.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            tab_bar_sizer.Add(tab_button, 0, wx.RIGHT, 1)
            self.tab_buttons.append(tab_button)
        
        tab_bar.SetSizer(tab_bar_sizer)
        tabs_sizer.Add(tab_bar, 0, wx.EXPAND)
        
        # Cria os painéis de conteúdo
        # Guia de resumo
        self.summary_panel = self._create_tab_panel(tabs_container)
        summary_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.summary_loading_text = wx.StaticText(self.summary_panel, label="Carregando informações da impressora...")
        self.summary_loading_text.SetForegroundColour(self.colors["text_color"])
        summary_sizer.Add(self.summary_loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.summary_panel.SetSizer(summary_sizer)
        
        # Guia de informações de conectividade
        self.connectivity_panel = self._create_tab_panel(tabs_container)
        connectivity_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cria um painel "card" para as informações de conectividade
        connectivity_card = wx.Panel(self.connectivity_panel)
        connectivity_card.SetBackgroundColour(self.colors["card_bg"])
        connectivity_card_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # IP
        if self.printer.ip:
            ip_panel = self._create_info_row(connectivity_card, "IP:", self.printer.ip)
            connectivity_card_sizer.Add(ip_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # MAC Address
        if self.printer.mac_address:
            mac_panel = self._create_info_row(connectivity_card, "MAC Address:", self.printer.mac_address)
            connectivity_card_sizer.Add(mac_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # URI
        if self.printer.uri:
            uri_panel = self._create_info_row(connectivity_card, "URI:", self.printer.uri)
            connectivity_card_sizer.Add(uri_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Status
        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
        is_usable = is_online and is_ready
        
        status_text = "Pronta" if is_usable else "Indisponível"
        status_panel = self._create_info_row(connectivity_card, "Status:", status_text)
        connectivity_card_sizer.Add(status_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Estado
        if self.printer.state:
            state_panel = self._create_info_row(connectivity_card, "Estado:", self.printer.state)
            connectivity_card_sizer.Add(state_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Portas
        if self.printer.attributes and 'ports' in self.printer.attributes:
            ports = ", ".join(str(p) for p in self.printer.attributes['ports'])
            ports_panel = self._create_info_row(connectivity_card, "Portas:", ports)
            connectivity_card_sizer.Add(ports_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        connectivity_card.SetSizer(connectivity_card_sizer)
        
        # Adiciona borda arredondada ao card
        def on_card_paint(event):
            dc = wx.BufferedPaintDC(connectivity_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = connectivity_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in connectivity_card.GetChildren():
                child.Refresh()
        
        connectivity_card.Bind(wx.EVT_PAINT, on_card_paint)
        connectivity_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        connectivity_sizer.Add(connectivity_card, 0, wx.EXPAND | wx.ALL, 10)
        
        # Botão para diagnóstico (somente se tiver IP)
        if self.printer.ip:
            diagnostic_button = create_styled_button(
                self.connectivity_panel,
                "Executar Diagnóstico",
                self.colors["accent_color"],
                self.colors["text_color"],
                wx.Colour(255, 120, 70),
                (-1, 36)
            )
            diagnostic_button.Bind(wx.EVT_BUTTON, self._on_diagnostic)
            
            connectivity_sizer.Add(diagnostic_button, 0, wx.ALIGN_CENTER | wx.ALL, 15)
        
        self.connectivity_panel.SetSizer(connectivity_sizer)
        
        # Guia de atributos
        self.attributes_panel = self._create_tab_panel(tabs_container)
        self.attributes_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.loading_text = wx.StaticText(self.attributes_panel, label="Carregando atributos da impressora...")
        self.loading_text.SetForegroundColour(self.colors["text_color"])
        self.attributes_sizer.Add(self.loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.attributes_panel.SetSizer(self.attributes_sizer)
        
        # Guia de suprimentos
        self.supplies_panel = self._create_tab_panel(tabs_container)
        self.supplies_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.supplies_loading_text = wx.StaticText(self.supplies_panel, label="Carregando informações de suprimentos...")
        self.supplies_loading_text.SetForegroundColour(self.colors["text_color"])
        self.supplies_sizer.Add(self.supplies_loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.supplies_panel.SetSizer(self.supplies_sizer)
        
        # Guia de diagnóstico
        self.diagnostic_panel = self._create_tab_panel(tabs_container)
        self.diagnostic_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Card para as instruções de diagnóstico
        diagnostic_card = wx.Panel(self.diagnostic_panel)
        diagnostic_card.SetBackgroundColour(self.colors["card_bg"])
        diagnostic_card_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de instrução
        diagnostic_text = wx.StaticText(
            diagnostic_card, 
            label="Execute um diagnóstico na guia de Conectividade para verificar o status da impressora."
        )
        diagnostic_text.SetForegroundColour(self.colors["text_color"])
        diagnostic_text.Wrap(500)  # Wrap text para manter uma boa apresentação
        diagnostic_card_sizer.Add(diagnostic_text, 0, wx.ALL | wx.CENTER, 20)
        
        diagnostic_card.SetSizer(diagnostic_card_sizer)
        
        # Adiciona borda arredondada ao card
        def on_diagnostic_card_paint(event):
            dc = wx.BufferedPaintDC(diagnostic_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = diagnostic_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in diagnostic_card.GetChildren():
                child.Refresh()
        
        diagnostic_card.Bind(wx.EVT_PAINT, on_diagnostic_card_paint)
        diagnostic_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.diagnostic_sizer.Add(diagnostic_card, 0, wx.EXPAND | wx.ALL, 15)
        
        self.diagnostic_panel.SetSizer(self.diagnostic_sizer)
        
        # Adiciona os paineis à lista
        self.tab_panels = [
            self.summary_panel,
            self.connectivity_panel,
            self.attributes_panel,
            self.supplies_panel,
            self.diagnostic_panel
        ]
        
        # Mostra apenas o primeiro painel por padrão
        for i, panel in enumerate(self.tab_panels):
            tabs_sizer.Add(panel, 1, wx.EXPAND)
            if i > 0:
                panel.Hide()
        
        tabs_container.SetSizer(tabs_sizer)
        main_sizer.Add(tabs_container, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para atualizar
        self.refresh_button = create_styled_button(
            self.panel,
            "Atualizar Informações",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(255, 120, 70),
            (-1, 36)
        )
        self.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)

        button_sizer.Add(self.refresh_button, 0, wx.RIGHT, 10)

        # Botão para fechar
        close_button = create_styled_button(
            self.panel,
            "Fechar",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (-1, 36)
        )
        close_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL))

        button_sizer.Add(close_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
        
        # Carrega os detalhes da impressora
        self._load_printer_details()
    
    def _create_tab_panel(self, parent):
        """Cria um painel para uma tab"""
        panel = wx.ScrolledWindow(parent)
        panel.SetBackgroundColour(self.colors["panel_bg"])
        panel.SetScrollRate(0, 10)
        return panel
    
    def _select_tab(self, index):
        """Seleciona uma tab pelo índice"""
        # Atualiza os botões das tabs
        for i, button in enumerate(self.tab_buttons):
            if i == index:
                button.selected = True
                button.SetBackgroundColour(self.colors["accent_color"])
                button.GetChildren()[0].SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            else:
                button.selected = False
                button.SetBackgroundColour(self.colors["card_bg"])
                button.GetChildren()[0].SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
            button.Refresh()
        
        # Mostra o painel correto
        for i, panel in enumerate(self.tab_panels):
            if i == index:
                panel.Show()
            else:
                panel.Hide()
        
        # Atualiza o layout
        self.panel.Layout()
    
    def _create_info_row(self, parent, label, value):
        """
        Cria uma linha de informação
        
        Args:
            parent: Painel pai
            label: Rótulo
            value: Valor
            
        Returns:
            wx.Panel: Painel com a linha de informação
        """
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(self.colors["card_bg"])
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Rótulo
        label_ctrl = wx.StaticText(panel, label=label)
        label_ctrl.SetForegroundColour(self.colors["text_color"])
        label_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        sizer.Add(label_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        # Valor
        value_ctrl = wx.StaticText(panel, label=str(value))
        value_ctrl.SetForegroundColour(self.colors["text_secondary"])
        
        # Se o valor for longo, adiciona um botão para copiar
        if len(str(value)) > 30:
            value_panel = wx.Panel(panel)
            value_panel.SetBackgroundColour(self.colors["card_bg"])
            value_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Trunca o valor para exibição
            display_value = str(value)[:27] + "..."
            value_ctrl = wx.StaticText(value_panel, label=display_value)
            value_ctrl.SetForegroundColour(self.colors["text_secondary"])
            value_sizer.Add(value_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            
            # Botão para copiar
            copy_button = create_styled_button(
                value_panel,
                "Copiar",
                wx.Colour(60, 60, 60),
                self.colors["text_color"],
                wx.Colour(80, 80, 80),
                (70, 26)
            )
            copy_button.Bind(wx.EVT_BUTTON, lambda evt, v=value: self._copy_to_clipboard(v))
            
            value_sizer.Add(copy_button, 0, wx.ALIGN_CENTER_VERTICAL)
            
            value_panel.SetSizer(value_sizer)
            sizer.Add(value_panel, 1, wx.EXPAND)
        else:
            sizer.Add(value_ctrl, 1, wx.ALIGN_CENTER_VERTICAL)
        
        panel.SetSizer(sizer)
        return panel
    
    def _copy_to_clipboard(self, text):
        """
        Copia texto para a área de transferência
        
        Args:
            text: Texto a copiar
        """
        if wx.TheClipboard.Open():
            wx.TheClipboard.SetData(wx.TextDataObject(str(text)))
            wx.TheClipboard.Close()
            
            # Feedback visual
            wx.MessageBox("Copiado para a área de transferência", "Informação", wx.OK | wx.ICON_INFORMATION)
    
    def _on_diagnostic(self, event):
        """Executa diagnóstico da impressora"""
        if not self.printer.ip:
            wx.MessageBox("Impressora sem endereço IP. Não é possível executar diagnóstico.", "Aviso", wx.OK | wx.ICON_WARNING)
            return
            
        # Limpa o painel de diagnóstico
        for child in self.diagnostic_panel.GetChildren():
            child.Destroy()
            
        # Adiciona texto de carregamento
        loading_text = wx.StaticText(self.diagnostic_panel, label="Executando diagnóstico, aguarde...")
        loading_text.SetForegroundColour(self.colors["text_color"])
        self.diagnostic_sizer.Add(loading_text, 0, wx.ALL | wx.CENTER, 20)
        self.diagnostic_panel.Layout()
        
        # Muda para a guia de diagnóstico
        self._select_tab(4)
        
        # Executa o diagnóstico em uma thread
        try:
            from src.utils.printer_diagnostic import PrinterDiagnostic
            
            # Define o callback para atualizar a UI
            def update_diagnostic(message):
                wx.CallAfter(self._update_diagnostic_ui, message)
                
            # Define o callback para finalizar o diagnóstico
            def on_diagnostic_complete(results):
                wx.CallAfter(self._update_diagnostic_results, results)
                
            # Cria e inicia o diagnóstico
            diagnostic = PrinterDiagnostic(self.printer, update_diagnostic)
            diagnostic.run_diagnostics_async(on_diagnostic_complete)
            
        except ImportError:
            wx.MessageBox("Módulo de diagnóstico não disponível.", "Erro", wx.OK | wx.ICON_ERROR)
            loading_text.Destroy()
        except Exception as e:
            wx.MessageBox(f"Erro ao iniciar diagnóstico: {str(e)}", "Erro", wx.OK | wx.ICON_ERROR)
            loading_text.Destroy()
    
    def _update_diagnostic_ui(self, message):
        """
        Atualiza a interface do diagnóstico
        
        Args:
            message: Mensagem de progresso
        """
        # Cria um texto para a mensagem
        if not message:
            message = "Erro ao executar diagnóstico!"

        message_text = wx.StaticText(self.diagnostic_panel, label=message)
        message_text.SetForegroundColour(self.colors["text_color"])
        self.diagnostic_sizer.Add(message_text, 0, wx.ALL | wx.LEFT, 10)
        self.diagnostic_panel.Layout()
        
        # Scroll para mostrar a mensagem mais recente
        self.diagnostic_panel.Scroll(0, self.diagnostic_panel.GetVirtualSize().GetHeight())
        
    def _update_diagnostic_results(self, results):
        """
        Atualiza a interface com os resultados do diagnóstico
        
        Args:
            results: Resultados do diagnóstico
        """
        # Limpa o painel de diagnóstico
        for child in self.diagnostic_panel.GetChildren():
            child.Destroy()
            
        # Card para os resultados
        results_card = wx.Panel(self.diagnostic_panel)
        results_card.SetBackgroundColour(self.colors["card_bg"])
        results_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Adiciona o resultado geral
        overall = results.get("overall", {})
        success = overall.get("success", False)
        message = overall.get("message", "Diagnóstico concluído")
        
        # Cor baseada no resultado
        color = self.colors["success_color"] if success else self.colors["error_color"]
        
        # Título do resultado
        result_text = wx.StaticText(results_card, label=f"Resultado: {message}")
        result_text.SetForegroundColour(color)
        result_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        results_sizer.Add(result_text, 0, wx.ALL | wx.CENTER, 15)
        
        # Separador
        separator = wx.StaticLine(results_card, style=wx.LI_HORIZONTAL)
        results_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 15)
        
        # Adiciona os resultados detalhados de cada teste
        for test_id, test_result in results.items():
            if test_id != "overall":
                test_panel = self._add_test_result_panel(results_card, test_id, test_result)
                results_sizer.Add(test_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        results_card.SetSizer(results_sizer)
        
        # Adiciona borda arredondada ao card
        def on_results_card_paint(event):
            dc = wx.BufferedPaintDC(results_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = results_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in results_card.GetChildren():
                child.Refresh()
        
        results_card.Bind(wx.EVT_PAINT, on_results_card_paint)
        results_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.diagnostic_sizer.Add(results_card, 0, wx.EXPAND | wx.ALL, 15)
        self.diagnostic_panel.Layout()
    
    def _add_test_result_panel(self, parent, test_id, result):
        """
        Adiciona o painel de resultado de um teste
        
        Args:
            parent: Painel pai
            test_id: ID do teste
            result: Resultado do teste
            
        Returns:
            wx.Panel: Painel de resultado
        """
        # Nome do teste formatado
        test_names = {
            "connectivity": "Teste de Conectividade",
            "port_availability": "Portas Disponíveis",
            "ipp": "IPP/Protocolo de Impressão",
            "print_job": "Teste de Envio de Trabalho"
        }
        test_name = test_names.get(test_id, test_id.replace("_", " ").title())
        
        # Cria um painel para o resultado
        test_panel = wx.Panel(parent)
        test_panel.SetBackgroundColour(self.colors["card_bg"])
        test_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título do teste
        success = result.get("success", False)
        status = "Passou" if success else "Falhou"
        title = wx.StaticText(test_panel, label=f"{test_name}: {status}")
        
        # Cor baseada no resultado
        color = self.colors["success_color"] if success else self.colors["error_color"]
        title.SetForegroundColour(color)
        title.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        test_sizer.Add(title, 0, wx.ALL, 5)
        
        # Mensagem do teste
        message = result.get("message", "")
        if message:
            message_text = wx.StaticText(test_panel, label=message)
            message_text.SetForegroundColour(self.colors["text_secondary"])
            test_sizer.Add(message_text, 0, wx.LEFT | wx.BOTTOM, 5)
        
        # Detalhes do teste
        details = result.get("details", "")
        if details:
            details_text = wx.StaticText(test_panel, label=details)
            details_text.SetForegroundColour(self.colors["text_secondary"])
            details_text.Wrap(parent.GetSize().width - 40)  # Wrap text to fit in panel
            test_sizer.Add(details_text, 0, wx.LEFT | wx.BOTTOM, 5)
        
        test_panel.SetSizer(test_sizer)
        return test_panel
    
    def _load_printer_details(self):
        """Carrega os detalhes da impressora"""
        if not self.printer.ip:
            self._update_printer_details(None)
            return
        
        def on_details_loaded(details):
            """Callback quando os detalhes forem carregados"""
            wx.CallAfter(self._update_printer_details, details)
        
        # Carrega os detalhes em uma thread separada
        try:
            from src.utils.printer_discovery import PrinterDiscovery
            
            # Função para carregar detalhes em uma thread
            def load_details_thread():
                try:
                    discovery = PrinterDiscovery()
                    details = discovery.get_printer_details(self.printer.ip)
                    on_details_loaded(details)
                except Exception as e:
                    logger.error(f"Erro ao carregar detalhes: {str(e)}")
                    on_details_loaded(None)
            
            # Inicia a thread
            thread = threading.Thread(target=load_details_thread)
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            logger.error(f"Erro ao iniciar carregamento de detalhes: {str(e)}")
            self._update_printer_details(None)
    
    def _update_printer_details(self, details):
        """
        Atualiza todos os painéis com os detalhes da impressora
        
        Args:
            details: Detalhes da impressora
        """
        if not details:
            if hasattr(self, 'summary_loading_text') and self.summary_loading_text:
                try:
                    self.summary_loading_text.SetLabel("Não foi possível carregar os detalhes da impressora.")
                except wx.PyDeadObjectError:
                    self.summary_loading_text = None
                
            if hasattr(self, 'loading_text') and self.loading_text:
                try:
                    self.loading_text.SetLabel("Não foi possível carregar os atributos da impressora.")
                except wx.PyDeadObjectError:
                    self.loading_text = None
                
            if hasattr(self, 'supplies_loading_text') and self.supplies_loading_text:
                try:
                    self.supplies_loading_text.SetLabel("Não foi possível carregar informações de suprimentos.")
                except wx.PyDeadObjectError:
                    self.supplies_loading_text = None
            return
        
        # Atualiza a impressora com os detalhes
        self.printer.update_from_discovery(details)
        
        # Atualiza cada painel - garante que apenas um será executado por vez
        try:
            self._update_summary_panel(details)
        except Exception as e:
            logger.error(f"Erro ao atualizar resumo: {str(e)}")
            
        try:
            self._update_attributes_panel(details)
        except Exception as e:
            logger.error(f"Erro ao atualizar atributos: {str(e)}")
            
        try:
            self._update_supplies_panel(details)
        except Exception as e:
            logger.error(f"Erro ao atualizar suprimentos: {str(e)}")
        
        # Atualiza o estado de conectividade
        try:
            self._update_connectivity_status()
        except Exception as e:
            logger.error(f"Erro ao atualizar status de conectividade: {str(e)}")
        
        self.details_loaded = True
    
    def _on_refresh(self, event):
        """Manipula o clique no botão de atualizar"""
        # Desabilita o botão durante a atualização
        self.refresh_button.Disable()
        self.refresh_button.SetLabel("Atualizando...")
        
        # Carrega os detalhes novamente
        self._load_printer_details()
        
        # Reabilita o botão
        self.refresh_button.Enable()
        self.refresh_button.SetLabel("Atualizar Informações")
    
    def _update_summary_panel(self, details):
        """
        Atualiza o painel de resumo
        
        Args:
            details: Detalhes da impressora
        """
        # Limpa o painel
        if hasattr(self, 'summary_loading_text') and self.summary_loading_text:
            try:
                self.summary_loading_text.Destroy()
                self.summary_loading_text = None
            except (wx.PyDeadObjectError, Exception):
                self.summary_loading_text = None
                
        self.summary_panel.GetSizer().Clear()

        # Card para o resumo
        summary_card = wx.Panel(self.summary_panel)
        summary_card.SetBackgroundColour(self.colors["card_bg"])
        summary_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título do resumo
        title = wx.StaticText(summary_card, label="RESUMO DA IMPRESSORA")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        summary_sizer.Add(title, 0, wx.ALL, 15)
        
        # Painel para informações em duas colunas
        info_panel = wx.Panel(summary_card)
        info_panel.SetBackgroundColour(self.colors["card_bg"])
        info_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=20)
        info_sizer.AddGrowableCol(1, 1)  # A segunda coluna é expansível
        
        # Adiciona informações básicas
        self._add_summary_item(info_panel, info_sizer, "Nome:", self.printer.name)
        self._add_summary_item(info_panel, info_sizer, "IP:", self.printer.ip or "Desconhecido")
        self._add_summary_item(info_panel, info_sizer, "Modelo:", self.printer.model or "Desconhecido")
        self._add_summary_item(info_panel, info_sizer, "Localização:", self.printer.location or "Desconhecida")
        self._add_summary_item(info_panel, info_sizer, "Status:", self.printer.state or "Desconhecido")
        
        # Informações adicionais
        if 'manufacturer' in details:
            self._add_summary_item(info_panel, info_sizer, "Fabricante:", details['manufacturer'])
        if 'version' in details:
            self._add_summary_item(info_panel, info_sizer, "Versão:", details['version'])
        if 'serial' in details:
            self._add_summary_item(info_panel, info_sizer, "Número de Série:", details['serial'])
        
        # URIs suportadas
        if 'printer-uri-supported' in details:
            uris = details['printer-uri-supported']
            uri_text = ""
            if isinstance(uris, list):
                uri_text = ", ".join(uris)
            else:
                uri_text = str(uris)
            self._add_summary_item(info_panel, info_sizer, "URIs suportadas:", uri_text)
        
        info_panel.SetSizer(info_sizer)
        summary_sizer.Add(info_panel, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        # Adiciona informações de suprimentos se disponíveis
        if 'supplies' in details and details['supplies']:
            supply_title = wx.StaticText(summary_card, label="Informações de Suprimentos")
            supply_title.SetForegroundColour(self.colors["text_color"])
            supply_title.SetFont(wx.Font(11, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            summary_sizer.Add(supply_title, 0, wx.ALL, 15)
            
            supply_panel = wx.Panel(summary_card)
            supply_panel.SetBackgroundColour(self.colors["card_bg"])
            supply_sizer = wx.FlexGridSizer(rows=0, cols=3, vgap=8, hgap=15)
            
            # Cabeçalho
            header_name = wx.StaticText(supply_panel, label="Nome")
            header_name.SetForegroundColour(self.colors["text_secondary"])
            header_name.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            header_type = wx.StaticText(supply_panel, label="Tipo")
            header_type.SetForegroundColour(self.colors["text_secondary"])
            header_type.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            header_level = wx.StaticText(supply_panel, label="Nível")
            header_level.SetForegroundColour(self.colors["text_secondary"])
            header_level.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            
            supply_sizer.Add(header_name, 0)
            supply_sizer.Add(header_type, 0)
            supply_sizer.Add(header_level, 0)
            
            # Adiciona cada suprimento
            for supply in details['supplies']:
                name_text = wx.StaticText(supply_panel, label=supply['name'])
                name_text.SetForegroundColour(self.colors["text_color"])
                
                type_text = wx.StaticText(supply_panel, label=supply['type'])
                type_text.SetForegroundColour(self.colors["text_color"])
                
                level_text = wx.StaticText(supply_panel, label=f"{supply['level']}%")
                level_text.SetForegroundColour(self.colors["text_color"])
                
                supply_sizer.Add(name_text, 0)
                supply_sizer.Add(type_text, 0)
                supply_sizer.Add(level_text, 0)
            
            supply_panel.SetSizer(supply_sizer)
            summary_sizer.Add(supply_panel, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        
        summary_card.SetSizer(summary_sizer)
        
        # Adiciona borda arredondada ao card
        def on_summary_card_paint(event):
            dc = wx.BufferedPaintDC(summary_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = summary_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in summary_card.GetChildren():
                child.Refresh()
        
        summary_card.Bind(wx.EVT_PAINT, on_summary_card_paint)
        summary_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.summary_panel.GetSizer().Add(summary_card, 0, wx.EXPAND | wx.ALL, 10)
        self.summary_panel.Layout()
    
    def _add_summary_item(self, parent, sizer, label, value):
        """
        Adiciona um item ao resumo
        
        Args:
            parent: Painel pai
            sizer: Sizer
            label: Rótulo
            value: Valor
        """
        label_ctrl = wx.StaticText(parent, label=label)
        label_ctrl.SetForegroundColour(self.colors["text_secondary"])
        label_ctrl.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        value_ctrl = wx.StaticText(parent, label=str(value))
        value_ctrl.SetForegroundColour(self.colors["text_color"])
        
        sizer.Add(label_ctrl, 0, wx.ALIGN_LEFT)
        sizer.Add(value_ctrl, 0, wx.EXPAND)
    
    def _update_attributes_panel(self, details):
        """
        Atualiza o painel de atributos
        
        Args:
            details: Detalhes da impressora
        """
        if not details:
            if hasattr(self, 'loading_text') and self.loading_text:
                try:
                    self.loading_text.SetLabel("Não foi possível carregar os atributos da impressora.")
                except wx.PyDeadObjectError:
                    self.loading_text = None
            return
        
        # Limpa o sizer
        if hasattr(self, 'loading_text') and self.loading_text:
            try:
                self.loading_text.Destroy()
                self.loading_text = None  # Limpa a referência para evitar uso futuro
            except (wx.PyDeadObjectError, Exception):
                # Ignora erros se o widget já estiver destruído
                self.loading_text = None
                
        self.attributes_sizer.Clear()
        
        # Card para os atributos
        attributes_card = wx.Panel(self.attributes_panel)
        attributes_card.SetBackgroundColour(self.colors["card_bg"])
        attributes_sizer = wx.BoxSizer(wx.VERTICAL)

        # Título
        title = wx.StaticText(attributes_card, label="ATRIBUTOS DA IMPRESSORA")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        attributes_sizer.Add(title, 0, wx.ALL, 15)
        
        # Adiciona os atributos
        sorted_attrs = sorted(details.items())
        
        grid_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=20)
        grid_sizer.AddGrowableCol(1, 1)  # A segunda coluna é expansível
        
        for i, (key, value) in enumerate(sorted_attrs):
            # Ignora keys já exibidas em outro lugar
            if key in ["ip", "mac_address", "uri", "ports", "supplies"]:
                continue
                
            # Ignora values muito grandes
            if isinstance(value, (dict, list)) and len(str(value)) > 100:
                # Adiciona uma versão resumida
                if isinstance(value, list):
                    value = f"Lista com {len(value)} itens"
                else:
                    value = f"Objeto com {len(value)} atributos"
            
            # Label
            key_ctrl = wx.StaticText(attributes_card, label=key)
            key_ctrl.SetForegroundColour(self.colors["text_secondary"])
            
            # Valor
            value_ctrl = wx.StaticText(attributes_card, label=str(value))
            value_ctrl.SetForegroundColour(self.colors["text_color"])
            value_ctrl.Wrap(400)  # Wrap text para manter uma boa apresentação
            
            grid_sizer.Add(key_ctrl, 0, wx.ALIGN_LEFT)
            grid_sizer.Add(value_ctrl, 0, wx.EXPAND)
            
        attributes_sizer.Add(grid_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 15)
        attributes_card.SetSizer(attributes_sizer)
        
        # Adiciona borda arredondada ao card
        def on_attributes_card_paint(event):
            dc = wx.BufferedPaintDC(attributes_card)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = attributes_card.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in attributes_card.GetChildren():
                child.Refresh()
        
        attributes_card.Bind(wx.EVT_PAINT, on_attributes_card_paint)
        attributes_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        self.attributes_sizer.Add(attributes_card, 0, wx.EXPAND | wx.ALL, 10)
        self.attributes_panel.Layout()
    
    def _update_connectivity_status(self):
        """Atualiza o status na guia de conectividade"""
        # Encontra o painel de status
        for child in self.connectivity_panel.GetChildren():
            if isinstance(child, wx.Panel):
                for grandchild in child.GetChildren():
                    if isinstance(grandchild, wx.Panel):
                        for great_grandchild in grandchild.GetChildren():
                            if isinstance(great_grandchild, wx.StaticText) and great_grandchild.GetLabel() == "Status:":
                                # Encontrou o painel, atualiza o valor
                                for sibling in grandchild.GetChildren():
                                    if isinstance(sibling, wx.StaticText) and sibling != great_grandchild:
                                        # Verifica os atributos da impressora de forma segura
                                        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
                                        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
                                        is_usable = is_online and is_ready
                                        
                                        status_text = "Pronta" if is_usable else "Indisponível"
                                        sibling.SetLabel(status_text)
                                        sibling.SetForegroundColour(
                                            self.colors["success_color"] if is_usable else self.colors["error_color"]
                                        )
                                        grandchild.Layout()
                                        break
                                break
                        break
    
    def _update_supplies_panel(self, details):
        """
        Atualiza o painel de suprimentos
        
        Args:
            details: Detalhes da impressora
        """
        # Limpa o sizer
        if hasattr(self, 'supplies_loading_text') and self.supplies_loading_text:
            try:
                self.supplies_loading_text.Destroy()
                self.supplies_loading_text = None
            except (wx.PyDeadObjectError, Exception):
                self.supplies_loading_text = None
                
        self.supplies_sizer.Clear()

        # Título da seção
        title = wx.StaticText(self.supplies_panel, label="Níveis de Suprimentos")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.supplies_sizer.Add(title, 0, wx.ALL | wx.CENTER, 15)
        
        # Verifica se há informações de suprimentos
        if 'supplies' in details and details['supplies']:
            # Criar um painel de card para os suprimentos
            supplies_card = wx.Panel(self.supplies_panel)
            supplies_card.SetBackgroundColour(self.colors["card_bg"])
            supplies_card_sizer = wx.BoxSizer(wx.VERTICAL)
            
            for supply in details['supplies']:
                supply_panel = wx.Panel(supplies_card)
                supply_panel.SetBackgroundColour(self.colors["card_bg"])
                supply_sizer = wx.BoxSizer(wx.VERTICAL)
                
                # Nome do suprimento
                name = wx.StaticText(supply_panel, label=supply['name'])
                name.SetForegroundColour(self.colors["text_color"])
                name.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
                supply_sizer.Add(name, 0, wx.ALL, 5)
                
                # Informações adicionais
                info_text = f"Tipo: {supply['type']} | Cor: {supply.get('color', 'N/A')}"
                info = wx.StaticText(supply_panel, label=info_text)
                info.SetForegroundColour(self.colors["text_secondary"])
                supply_sizer.Add(info, 0, wx.LEFT | wx.BOTTOM, 5)
                
                # Painel para a barra de progresso e percentual
                gauge_panel = wx.Panel(supply_panel)
                gauge_panel.SetBackgroundColour(self.colors["card_bg"])
                gauge_sizer = wx.BoxSizer(wx.HORIZONTAL)
                
                # Nível
                level_text = f"{supply['level']}%"
                level = wx.StaticText(gauge_panel, label=level_text)
                level.SetForegroundColour(self.colors["text_secondary"])
                
                # Determina a cor baseada no nível
                level_value = int(supply['level'])
                if level_value > 50:
                    color = self.colors["success_color"]  # Verde para nível alto
                elif level_value > 15:
                    color = self.colors["warning_color"]  # Amarelo para nível médio
                else:
                    color = self.colors["error_color"]  # Vermelho para nível baixo
                
                # Barra de progresso personalizada - usando bitmap pré-renderizado
                gauge_width = 300
                gauge_height = 18
                
                # Cria um bitmap para a barra de progresso
                progress_bitmap = wx.Bitmap(gauge_width, gauge_height)
                dc = wx.MemoryDC()
                dc.SelectObject(progress_bitmap)
                
                # Desenha o fundo da barra
                dc.SetBackground(wx.Brush(wx.Colour(45, 45, 45)))
                dc.Clear()
                
                # Calcula o comprimento do preenchimento da barra
                fill_width = int((gauge_width * level_value) / 100)
                
                # Desenha o preenchimento da barra
                dc.SetBrush(wx.Brush(color))
                dc.SetPen(wx.Pen(color))
                dc.DrawRectangle(0, 0, fill_width, gauge_height)
                
                # Finaliza o desenho
                dc.SelectObject(wx.NullBitmap)
                
                # Cria e adiciona o bitmap ao layout
                progress_bar = wx.StaticBitmap(gauge_panel, bitmap=progress_bitmap, size=(gauge_width, gauge_height))
                
                gauge_sizer.Add(progress_bar, 0, wx.RIGHT, 10)
                gauge_sizer.Add(level, 0, wx.ALIGN_CENTER_VERTICAL)
                
                gauge_panel.SetSizer(gauge_sizer)
                supply_sizer.Add(gauge_panel, 0, wx.LEFT | wx.BOTTOM, 10)
                
                # Adiciona linha separadora, exceto no último item
                if supply != details['supplies'][-1]:
                    separator = wx.StaticLine(supply_panel)
                    separator.SetForegroundColour(self.colors["border_color"])
                    supply_sizer.Add(separator, 0, wx.EXPAND | wx.TOP | wx.BOTTOM, 10)
                
                supply_panel.SetSizer(supply_sizer)
                supplies_card_sizer.Add(supply_panel, 0, wx.EXPAND | wx.ALL, 5)
            
            supplies_card.SetSizer(supplies_card_sizer)
            
            # Adiciona borda arredondada ao card de suprimentos
            def on_supplies_card_paint(event):
                dc = wx.BufferedPaintDC(supplies_card)
                gc = wx.GraphicsContext.Create(dc)
                
                rect = supplies_card.GetClientRect()
                
                # Desenha o fundo com cantos arredondados
                path = gc.CreatePath()
                path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
                
                gc.SetBrush(wx.Brush(self.colors["card_bg"]))
                gc.SetPen(wx.Pen(self.colors["border_color"], 1))
                
                gc.DrawPath(path)
                
                # Redesenha os filhos
                for child in supplies_card.GetChildren():
                    child.Refresh()
            
            supplies_card.Bind(wx.EVT_PAINT, on_supplies_card_paint)
            supplies_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
            
            self.supplies_sizer.Add(supplies_card, 0, wx.EXPAND | wx.ALL, 10)
        else:
            # Sem informações de suprimentos
            no_supplies_card = wx.Panel(self.supplies_panel)
            no_supplies_card.SetBackgroundColour(self.colors["card_bg"])
            no_supplies_sizer = wx.BoxSizer(wx.VERTICAL)
            
            no_supplies = wx.StaticText(no_supplies_card, label="Nenhuma informação de suprimentos disponível.")
            no_supplies.SetForegroundColour(self.colors["text_color"])
            no_supplies_sizer.Add(no_supplies, 0, wx.ALL | wx.CENTER, 20)
            
            no_supplies_card.SetSizer(no_supplies_sizer)
            
            # Adiciona borda arredondada ao card
            def on_no_supplies_card_paint(event):
                dc = wx.BufferedPaintDC(no_supplies_card)
                gc = wx.GraphicsContext.Create(dc)
                
                rect = no_supplies_card.GetClientRect()
                
                # Desenha o fundo com cantos arredondados
                path = gc.CreatePath()
                path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
                
                gc.SetBrush(wx.Brush(self.colors["card_bg"]))
                gc.SetPen(wx.Pen(self.colors["border_color"], 1))
                
                gc.DrawPath(path)
                
                # Redesenha os filhos
                for child in no_supplies_card.GetChildren():
                    child.Refresh()
            
            no_supplies_card.Bind(wx.EVT_PAINT, on_no_supplies_card_paint)
            no_supplies_card.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
            
            self.supplies_sizer.Add(no_supplies_card, 0, wx.EXPAND | wx.ALL, 10)
        
        # Atualiza o layout
        self.supplies_panel.Layout()

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

        apply_dark_scrollbar_style(self)
        
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
        
        # Configura scrolling - valor alterado para ter scroll horizontal e vertical
        self.SetScrollRate(5, 10)
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel de cabeçalho com título e botão
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(self.colors["bg_color"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Impressoras")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(self.colors["text_color"])
        
        # Botão de atualizar impressoras (com servidor)
        self.update_button = create_styled_button(
            header_panel,
            "Atualizar Impressoras",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(255, 120, 70),
            (160, 36)
        )
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update_printers)
        
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
            label="Impressoras disponíveis para o sistema. Clique em uma impressora para ver mais detalhes."
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
        printer_icon_path = ResourceManager.get_image_path("printer.png")
        
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
            logger.info(f"Carregadas {len(printers_data)} impressoras da configuração")
            
            # Remove o indicador de carregamento
            loading_text.Destroy()
            
            if printers_data and len(printers_data) > 0:
                self.printers = []
                for printer_data in printers_data:
                    # Verifica se os dados da impressora são válidos
                    if not isinstance(printer_data, dict):
                        logger.warning(f"Dados de impressora inválidos: {printer_data}")
                        continue
                    
                    # Garante que os campos são válidos antes de criar o objeto
                    if 'name' not in printer_data or printer_data['name'] is None:
                        printer_data['name'] = f"Impressora {printer_data.get('ip', '')}"
                    if 'mac_address' not in printer_data or printer_data['mac_address'] is None:
                        printer_data['mac_address'] = ""
                    if 'ip' not in printer_data or printer_data['ip'] is None:
                        printer_data['ip'] = ""
                    
                    # Cria o objeto Printer
                    printer = Printer(printer_data)
                    self.printers.append(printer)
                
                self.empty_panel.Hide()
                
                # Cria um card para cada impressora
                for printer in self.printers:
                    card = PrinterCardPanel(self.content_panel, printer, self.on_printer_selected)
                    self.content_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
            else:
                self.printers = []
                self.empty_panel.Show()
            
            # Ajusta o layout
            self.content_panel.Layout()
            self.Layout()
            
            # Importante para o scrolling funcionar corretamente
            self.FitInside()
            self.Refresh()
            
            logger.info(f"Lista de impressoras carregada com {len(self.printers)} impressoras")
            
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
            busy = wx.BusyInfo("Atualizando impressoras do servidor e descobrindo informações na rede. Aguarde...", parent=self)
            wx.GetApp().Yield()
            
            # Primeiro, obtemos as impressoras do servidor
            if not hasattr(self.api_client, 'get_printers'):
                wx.MessageBox("Cliente API não possui método get_printers", "Erro", wx.OK | wx.ICON_ERROR)
                return
                
            # Obtém as impressoras do servidor
            logger.info("Obtendo impressoras do servidor")
            server_printers = self.api_client.get_printers()
            logger.info(f"Obtidas {len(server_printers)} impressoras do servidor")
            
            # Se não houver impressoras, mostra mensagem
            if not server_printers:
                wx.MessageBox("Nenhuma impressora retornada pelo servidor", 
                            "Aviso", wx.OK | wx.ICON_WARNING)
                return
                
            # Inicializa a classe de descoberta
            try:
                from src.utils.printer_discovery import PrinterDiscovery
                discovery = PrinterDiscovery()
            except Exception as e:
                logger.error(f"Erro ao inicializar descoberta: {str(e)}")
                wx.MessageBox(f"Erro ao inicializar módulo de descoberta: {str(e)}", 
                            "Erro", wx.OK | wx.ICON_ERROR)
                return
                
            # Para cada impressora do servidor, buscamos o IP pelo MAC
            updated_printers = []
            for server_printer in server_printers:
                mac = server_printer.get("mac_address", "")
                if not mac:
                    logger.warning(f"Impressora sem MAC: {server_printer.get('name', 'Sem nome')}")
                    updated_printers.append(server_printer)
                    continue
                    
                logger.info(f"Buscando impressora com MAC: {mac}")
                
                # Busca específica pelo MAC
                printer_info = discovery.discover_printer_by_mac(mac)
                
                if printer_info:
                    # Encontramos o IP para este MAC
                    ip = printer_info.get("ip", "")
                    logger.info(f"MAC {mac} tem IP {ip}")
                    
                    # Atualiza a impressora do servidor com os dados encontrados
                    server_printer["ip"] = ip
                    server_printer["uri"] = printer_info.get("uri", "")
                    server_printer["is_online"] = True
                    
                    # Se for uma impressora IPP (porta 631), buscamos mais detalhes
                    if 631 in printer_info.get("ports", []):
                        try:
                            logger.info(f"Obtendo detalhes da impressora {ip}")
                            details = discovery.get_printer_details(ip)
                            if details:
                                # Atualiza com os detalhes
                                server_printer.update({
                                    "model": details.get("printer-make-and-model", ""),
                                    "location": details.get("printer-location", ""),
                                    "state": details.get("printer-state", ""),
                                    "is_ready": "Idle" in details.get("printer-state", ""),
                                    "attributes": details
                                })
                                logger.info(f"Detalhes obtidos para {ip}: {details.get('printer-make-and-model', 'Desconhecido')}")
                        except Exception as e:
                            logger.error(f"Erro ao obter detalhes da impressora {ip}: {str(e)}")
                else:
                    logger.warning(f"Não foi possível encontrar IP para MAC: {mac}")
                    
                # Adiciona a impressora à lista
                updated_printers.append(server_printer)
            
            # Sanitiza os dados antes de salvar
            printer_dicts = []
            for printer_data in updated_printers:
                try:
                    # Verifica se os campos principais existem
                    if 'name' not in printer_data or not printer_data['name']:
                        printer_data['name'] = f"Impressora {printer_data.get('mac_address', 'Desconhecida')}"
                    if 'mac_address' not in printer_data:
                        printer_data['mac_address'] = ""
                    if 'ip' not in printer_data:
                        printer_data['ip'] = ""
                    
                    # Substitui None por string vazia
                    for key in printer_data:
                        if printer_data[key] is None:
                            printer_data[key] = ""
                    
                    # Log das informações finais
                    logger.info(f"Impressora final: Nome={printer_data['name']}, "
                            f"IP={printer_data.get('ip', 'Não encontrado')}, "
                            f"MAC={printer_data.get('mac_address', 'Não encontrado')}")
                    
                    # Cria objeto Printer e converte para dicionário
                    printer = Printer(printer_data)
                    printer_dict = printer.to_dict()
                    
                    # Verifica novamente se há campos None
                    for key in printer_dict:
                        if printer_dict[key] is None:
                            printer_dict[key] = ""
                    
                    printer_dicts.append(printer_dict)
                except Exception as e:
                    logger.error(f"Erro ao processar impressora: {str(e)}")
            
            # Salva as impressoras no config
            logger.info(f"Salvando {len(printer_dicts)} impressoras no config")
            self.config.set_printers(printer_dicts)
            
            # Recarrega a lista
            self.load_printers()
            
            # Chama o callback se existir
            if self.on_update:
                self.on_update(printer_dicts)
            
            # Remove o indicador de progresso
            del busy
            
            # Mostra mensagem de sucesso
            wx.MessageBox(f"{len(printer_dicts)} impressoras atualizadas com sucesso!", 
                        "Informação", wx.OK | wx.ICON_INFORMATION)
        except Exception as e:
            logger.error(f"Erro ao atualizar impressoras: {str(e)}")
            wx.MessageBox(f"Erro ao atualizar impressoras: {str(e)}", 
                        "Erro", wx.OK | wx.ICON_ERROR)
    
    def on_printer_selected(self, printer):
        """
        Manipula a seleção de uma impressora
        
        Args:
            printer: Impressora selecionada
        """
        try:
            # Cria e exibe o diálogo de detalhes
            dialog = PrinterDetailsDialog(self, printer, self.api_client)
            dialog.ShowModal()
            dialog.Destroy()
            
            # Recarrega a lista para refletir quaisquer alterações
            self.load_printers()
            
        except Exception as e:
            logger.error(f"Erro ao exibir detalhes da impressora: {str(e)}")
            wx.MessageBox(f"Erro ao exibir detalhes da impressora: {str(e)}", 
                         "Erro", wx.OK | wx.ICON_ERROR)
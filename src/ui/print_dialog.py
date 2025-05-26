#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Módulo de diálogos de impressão integrados
"""

import os
import wx
import logging
import uuid
from datetime import datetime
from src.ui.custom_button import create_styled_button

from src.utils.print_system import PrintSystem, PrintOptions, ColorMode, Duplex, Quality

logger = logging.getLogger("PrintManagementSystem.UI.PrintDialog")

class SelectPrinterDialog(wx.Dialog):
    """Diálogo para seleção de impressora com detalhes e status"""
    
    def __init__(self, parent, printers, document, config):
        """
        Inicializa o diálogo de seleção de impressora
        
        Args:
            parent: Janela pai
            printers: Lista de impressoras disponíveis
            document: Documento a ser impresso
            config: Configuração do sistema
        """
        super().__init__(
            parent,
            title=f"Selecionar Impressora",
            size=(600, 450),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.printers = printers
        self.document = document
        self.config = config
        self.selected_printer = None
        
        # Cores para temas
        self.colors = {
            "bg_color": wx.Colour(18, 18, 18), 
            "panel_bg": wx.Colour(25, 25, 25),
            "card_bg": wx.Colour(35, 35, 35),
            "accent_color": wx.Colour(255, 90, 36),
            "text_color": wx.WHITE,
            "text_secondary": wx.Colour(180, 180, 180),
            "border_color": wx.Colour(45, 45, 45),
            "success_color": wx.Colour(40, 167, 69),
            "error_color": wx.Colour(220, 53, 69)
        }
        
        # Aplica o tema ao diálogo
        self.SetBackgroundColour(self.colors["bg_color"])
        
        self._init_ui()
        
        # Centraliza o diálogo
        self.CenterOnParent()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Configura o painel principal
        self.panel = wx.Panel(self)
        self.panel.SetBackgroundColour(self.colors["bg_color"])
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Cabeçalho com informações do documento
        header_panel = self._create_header_panel()
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Lista de impressoras
        printer_list_panel = self._create_printer_list_panel()
        main_sizer.Add(printer_list_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para cancelar
        cancel_button = create_styled_button(
            self.panel,
            "Cancelar",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (-1, 36)
        )
        cancel_button.SetId(wx.ID_CANCEL)

        # Botão para selecionar
        self.select_button = create_styled_button(
            self.panel,
            "Selecionar",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(255, 120, 70),
            (-1, 36)
        )
        self.select_button.SetId(wx.ID_OK)
        self.select_button.Disable()  # Desabilitado até que uma impressora seja selecionada
        
        button_sizer.Add(cancel_button, 0, wx.RIGHT, 10)
        button_sizer.Add(self.select_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
        
        # Bind do evento de OK
        self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
    
    def _create_header_panel(self):
        """Cria o painel de cabeçalho com informações do documento"""
        header_panel = wx.Panel(self.panel)
        header_panel.SetBackgroundColour(self.colors["card_bg"])
        header_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(header_panel, label="Selecione uma impressora")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        header_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(header_panel)
        header_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Informações do documento
        info_panel = wx.Panel(header_panel)
        info_panel.SetBackgroundColour(self.colors["card_bg"])
        info_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=5, hgap=10)
        info_sizer.AddGrowableCol(1, 1)
        
        # Documento
        doc_label = wx.StaticText(info_panel, label="Documento:")
        doc_label.SetForegroundColour(self.colors["text_secondary"])
        doc_value = wx.StaticText(info_panel, label=self.document.name)
        doc_value.SetForegroundColour(self.colors["text_color"])
        
        # Tamanho do arquivo
        size_label = wx.StaticText(info_panel, label="Tamanho:")
        size_label.SetForegroundColour(self.colors["text_secondary"])
        size_value = wx.StaticText(info_panel, label=self.document.formatted_size)
        size_value.SetForegroundColour(self.colors["text_color"])
        
        # Páginas
        if hasattr(self.document, 'pages') and self.document.pages > 0:
            pages_label = wx.StaticText(info_panel, label="Páginas:")
            pages_label.SetForegroundColour(self.colors["text_secondary"])
            pages_value = wx.StaticText(info_panel, label=str(self.document.pages))
            pages_value.SetForegroundColour(self.colors["text_color"])
            
            info_sizer.Add(pages_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            info_sizer.Add(pages_value, 0, wx.EXPAND)
        
        # Adiciona os itens ao sizer
        info_sizer.Add(doc_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(doc_value, 0, wx.EXPAND)
        info_sizer.Add(size_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        info_sizer.Add(size_value, 0, wx.EXPAND)
        
        info_panel.SetSizer(info_sizer)
        header_sizer.Add(info_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        header_panel.SetSizer(header_sizer)
        
        # Adiciona borda arredondada ao card
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
        
        return header_panel
    
    def _create_printer_list_panel(self):
        """Cria o painel com a lista de impressoras"""
        list_panel = wx.Panel(self.panel)
        list_panel.SetBackgroundColour(self.colors["card_bg"])
        list_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(list_panel, label="Impressoras disponíveis")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        list_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(list_panel)
        list_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Lista de impressoras
        self.printer_listbox = wx.ListCtrl(
            list_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE
        )
        
        self.printer_listbox.SetBackgroundColour(self.colors["card_bg"])
        self.printer_listbox.SetForegroundColour(self.colors["text_color"])
        
        # Adiciona colunas
        self.printer_listbox.InsertColumn(0, "Nome", width=200)
        self.printer_listbox.InsertColumn(1, "IP", width=120)
        self.printer_listbox.InsertColumn(2, "Status", width=100)
        self.printer_listbox.InsertColumn(3, "Local", width=150)
        
        # Preenche com as impressoras
        for i, printer in enumerate(self.printers):
            index = self.printer_listbox.InsertItem(i, printer.name)
            
            # IP
            ip = getattr(printer, 'ip', '')
            self.printer_listbox.SetItem(index, 1, ip)
            
            # Status
            is_online = getattr(printer, 'is_online', False) 
            is_ready = getattr(printer, 'is_ready', False)
            
            if is_online and is_ready:
                status = "Pronta"
            elif is_online:
                status = "Online"
            else:
                status = "Offline"
                
            self.printer_listbox.SetItem(index, 2, status)
            
            # Local
            location = getattr(printer, 'location', '')
            self.printer_listbox.SetItem(index, 3, location)
        
        # Bind do evento de seleção
        self.printer_listbox.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_printer_selected)
        self.printer_listbox.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_printer_deselected)
        
        list_sizer.Add(self.printer_listbox, 1, wx.EXPAND | wx.ALL, 10)
        
        list_panel.SetSizer(list_sizer)
        
        # Adiciona borda arredondada ao card
        def on_list_paint(event):
            dc = wx.BufferedPaintDC(list_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = list_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in list_panel.GetChildren():
                child.Refresh()
        
        list_panel.Bind(wx.EVT_PAINT, on_list_paint)
        list_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        return list_panel
    
    def on_printer_selected(self, event):
        """Manipula o evento de seleção de impressora"""
        index = event.GetIndex()
        self.selected_printer = self.printers[index]
        
        # Habilita o botão de seleção
        self.select_button.Enable()
    
    def on_printer_deselected(self, event):
        """Manipula o evento de deseleção de impressora"""
        self.selected_printer = None
        
        # Desabilita o botão de seleção
        self.select_button.Disable()
    
    def on_ok(self, event):
        """Manipula o evento de OK (selecionar)"""
        if self.selected_printer:
            # Verifica se a impressora tem IP
            if not hasattr(self.selected_printer, 'ip') or not self.selected_printer.ip:
                wx.MessageBox(
                    f"A impressora '{self.selected_printer.name}' não possui um endereço IP configurado.",
                    "Erro",
                    wx.OK | wx.ICON_ERROR
                )
                return
            
            event.Skip()  # Continua o processamento do evento
        else:
            wx.MessageBox(
                "Selecione uma impressora para continuar.",
                "Aviso",
                wx.OK | wx.ICON_WARNING
            )
    
    def get_selected_printer(self):
        """Retorna a impressora selecionada"""
        return self.selected_printer

def select_printer_and_print(parent, document, config):
    """
    Seleciona uma impressora e imprime um documento
    
    Args:
        parent: Janela pai
        document: Documento a ser impresso
        config: Configuração do sistema
        
    Returns:
        bool: True se o documento foi enviado para impressão
    """
    try:
        # Inicializa o sistema de impressão
        print_system = PrintSystem(config)
        
        # Obtém a lista de impressoras
        printers_data = config.get_printers()
        
        if not printers_data:
            wx.MessageBox(
                "Nenhuma impressora configurada. Configure impressoras na aba Impressoras.",
                "Informação",
                wx.OK | wx.ICON_INFORMATION
            )
            return False
        
        # Converte para objetos Printer
        from src.models.printer import Printer
        printers = [Printer(printer_data) for printer_data in printers_data]
        
        # Exibe o diálogo de seleção de impressora
        select_dialog = SelectPrinterDialog(parent, printers, document, config)
        result = select_dialog.ShowModal()
        
        if result != wx.ID_OK:
            select_dialog.Destroy()
            return False  # Usuário cancelou
        
        # Obtém a impressora selecionada
        printer = select_dialog.get_selected_printer()
        select_dialog.Destroy()
        
        if not printer:
            return False  # Não deveria acontecer, mas por segurança
        
        # Imprime o documento
        return print_system.print_document(parent, document, printer)
        
    except Exception as e:
        logger.error(f"Erro ao imprimir documento: {e}")
        wx.MessageBox(
            f"Erro ao imprimir documento: {e}",
            "Erro",
            wx.OK | wx.ICON_ERROR
        )
        return False
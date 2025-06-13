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
    
    def _is_epson_l3250(self, printer):
        """Verifica se a impressora é uma Epson L3250 (sem suporte de impressão)"""
        if not printer:
            return False
        
        # Verifica no nome da impressora
        name = getattr(printer, 'name', '') or ''
        if 'l3250' in name.lower() or 'l-3250' in name.lower():
            return True
        
        # Verifica no modelo
        model = getattr(printer, 'model', '') or ''
        if 'l3250' in model.lower() or 'l-3250' in model.lower():
            return True
        
        # Verifica no atributo printer-make-and-model (IPP)
        make_model = getattr(printer, 'printer-make-and-model', '') or ''
        if 'l3250' in make_model.lower() or 'l-3250' in make_model.lower():
            return True
        
        return False

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
        
        # Container para cabeçalho com scroll
        header_container = wx.Panel(list_panel)
        header_container.SetBackgroundColour(self.colors["panel_bg"])
        header_container_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # ScrolledWindow para o cabeçalho
        self.header_scroll = wx.ScrolledWindow(header_container, style=wx.HSCROLL)
        self.header_scroll.SetBackgroundColour(self.colors["panel_bg"])
        self.header_scroll.SetScrollRate(10, 0)  # Apenas scroll horizontal
        self.header_scroll.ShowScrollbars(wx.SHOW_SB_NEVER, wx.SHOW_SB_NEVER)  # Esconde as scrollbars do header
        
        # Painel do cabeçalho dentro do ScrolledWindow
        header_table_panel = wx.Panel(self.header_scroll)
        header_table_panel.SetBackgroundColour(self.colors["panel_bg"])
        header_table_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Define as larguras das colunas
        self.column_widths = [200, 120, 100, 150]
        column_labels = ["Nome", "IP", "Status", "Local"]
        
        # Cria os cabeçalhos customizados
        self.header_labels = []  # Armazena referências para os labels
        for i, (label, width) in enumerate(zip(column_labels, self.column_widths)):
            header_label = wx.StaticText(header_table_panel, label=label, size=(width, 30))
            header_label.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            header_label.SetForegroundColour(self.colors["text_color"])
            header_label.SetBackgroundColour(self.colors["panel_bg"])
            
            # Adiciona uma borda sutil
            def on_header_paint(event, ctrl=header_label, col_index=i):
                dc = wx.PaintDC(ctrl)
                dc.SetBackground(wx.Brush(self.colors["panel_bg"]))
                dc.Clear()
                
                # Desenha o texto
                dc.SetTextForeground(self.colors["text_color"])
                dc.SetFont(ctrl.GetFont())
                text_size = dc.GetTextExtent(ctrl.GetLabel())
                rect = ctrl.GetClientRect()
                
                # Centraliza o texto verticalmente
                y = (rect.height - text_size.height) // 2
                dc.DrawText(ctrl.GetLabel(), 8, y)
                
                # Desenha borda inferior
                dc.SetPen(wx.Pen(self.colors["border_color"], 1))
                dc.DrawLine(0, rect.height - 1, rect.width, rect.height - 1)
                
                # Desenha borda direita (exceto no último)
                if col_index < len(column_labels) - 1:
                    dc.DrawLine(rect.width - 1, 0, rect.width - 1, rect.height)
            
            header_label.Bind(wx.EVT_PAINT, on_header_paint)
            header_label.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
            
            header_table_sizer.Add(header_label, 0, wx.EXPAND)
            self.header_labels.append(header_label)
        
        header_table_panel.SetSizer(header_table_sizer)
        
        # Calcula o tamanho total do cabeçalho
        total_width = sum(self.column_widths)
        header_table_panel.SetSize((total_width, 30))
        
        # Configura o ScrolledWindow
        self.header_scroll.SetVirtualSize((total_width, 30))
        
        header_container_sizer.Add(self.header_scroll, 1, wx.EXPAND)
        header_container.SetSizer(header_container_sizer)
        
        list_sizer.Add(header_container, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Lista de impressoras sem cabeçalho nativo
        self.printer_listbox = wx.ListCtrl(
            list_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.LC_NO_HEADER | wx.BORDER_NONE
        )
        
        self.printer_listbox.SetBackgroundColour(self.colors["card_bg"])
        self.printer_listbox.SetForegroundColour(self.colors["text_color"])
        
        # Adiciona eventos para sincronização de scroll horizontal
        self.printer_listbox.Bind(wx.EVT_SCROLLWIN, self._on_list_scroll)
        self.printer_listbox.Bind(wx.EVT_SIZE, self._on_list_size)
        
        # Personaliza a scrollbar
        if wx.Platform == '__WXMSW__':
            try:
                import win32gui
                import win32con
                
                def customize_scrollbar():
                    wx.CallAfter(self._customize_scrollbar_colors)
                
                wx.CallLater(100, customize_scrollbar)
            except ImportError:
                pass  # win32gui não disponível
        
        # Adiciona colunas com larguras específicas
        for i, (label, width) in enumerate(zip(column_labels, self.column_widths)):
            self.printer_listbox.InsertColumn(i, label, width=width)
        
        # Preenche com as impressoras
        for i, printer in enumerate(self.printers):
            index = self.printer_listbox.InsertItem(i, printer.name)
            
            # IP
            ip = getattr(printer, 'ip', '')
            self.printer_listbox.SetItem(index, 1, ip)
            
            # Status
            if self._is_epson_l3250(printer):
                status = "Sem suporte"
            else:
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
            
            # Define cor de fundo baseada no status
            if self._is_epson_l3250(printer):
                self.printer_listbox.SetItemBackgroundColour(index, wx.Colour(50, 50, 50))  # Cinza escuro
            else:
                self.printer_listbox.SetItemBackgroundColour(index, self.colors["card_bg"])

        
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
    
    def _on_list_scroll(self, event):
        """Sincroniza o scroll do cabeçalho com o scroll da lista"""
        try:
            # Processa o evento original primeiro
            event.Skip()
            
            # Aguarda um pouco para o scroll ser processado
            wx.CallAfter(self._sync_header_scroll)
            
        except Exception as e:
            logger.error(f"Erro ao sincronizar scroll: {str(e)}")

    def _on_list_size(self, event):
        """Gerencia o redimensionamento da lista"""
        try:
            event.Skip()
            # Sincroniza o cabeçalho após redimensionamento
            wx.CallAfter(self._sync_header_scroll)
        except Exception as e:
            logger.error(f"Erro ao gerenciar redimensionamento: {str(e)}")

    def _sync_header_scroll(self):
        """Sincroniza a posição de scroll do cabeçalho com a lista"""
        try:
            if not hasattr(self, 'header_scroll'):
                return
                
            # Obtém a posição de scroll horizontal atual da lista
            list_scroll_pos = self.printer_listbox.GetScrollPos(wx.HORIZONTAL)
            
            # Converte a posição do scroll da lista (em pixels) para a posição do ScrolledWindow
            # O ScrolledWindow usa unidades de scroll (scroll_rate = 10)
            header_scroll_pos = list_scroll_pos // 10
            
            # Obtém a posição atual do cabeçalho para evitar scroll desnecessário
            current_header_pos = self.header_scroll.GetViewStart()[0]
            
            # Aplica o scroll apenas se a posição for diferente
            if current_header_pos != header_scroll_pos:
                self.header_scroll.Scroll(header_scroll_pos, 0)
                    
        except Exception as e:
            logger.error(f"Erro ao sincronizar scroll do cabeçalho: {str(e)}")

    def _customize_scrollbar_colors(self):
        """Personaliza as cores da scrollbar para tema escuro"""
        try:
            if wx.Platform == '__WXMSW__':
                # Tenta aplicar tema escuro via win32
                try:
                    import win32gui
                    import win32con
                    import win32api
                    import ctypes
                    from ctypes import wintypes
                    
                    hwnd = self.printer_listbox.GetHandle()
                    
                    # Tenta habilitar tema escuro no controle
                    # Este é o método mais moderno para Windows 10/11
                    DWMWA_USE_IMMERSIVE_DARK_MODE = 20
                    DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1 = 19
                    
                    def try_set_dark_mode(attribute):
                        try:
                            dwmapi = ctypes.windll.dwmapi
                            value = ctypes.c_int(1)
                            dwmapi.DwmSetWindowAttribute(
                                hwnd,
                                attribute,
                                ctypes.byref(value),
                                ctypes.sizeof(value)
                            )
                            return True
                        except:
                            return False
                    
                    # Tenta ambas as versões do atributo
                    if not try_set_dark_mode(DWMWA_USE_IMMERSIVE_DARK_MODE):
                        try_set_dark_mode(DWMWA_USE_IMMERSIVE_DARK_MODE_BEFORE_20H1)
                    
                    # Método alternativo: força tema escuro via SetWindowTheme
                    try:
                        uxtheme = ctypes.windll.uxtheme
                        uxtheme.SetWindowTheme(hwnd, "DarkMode_Explorer", None)
                    except:
                        pass
                    
                    # Força atualização da janela
                    try:
                        user32 = ctypes.windll.user32
                        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 
                                        0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
                    except:
                        pass
                        
                except ImportError:
                    # Se win32 não estiver disponível, tenta método alternativo
                    pass
            
            elif wx.Platform == '__WXGTK__':
                # Para GTK, tenta aplicar estilo escuro
                try:
                    import gi
                    gi.require_version('Gtk', '3.0')
                    from gi.repository import Gtk
                    
                    # Aplica tema escuro no GTK
                    settings = Gtk.Settings.get_default()
                    settings.set_property('gtk-application-prefer-dark-theme', True)
                except:
                    pass
            
            elif wx.Platform == '__WXMAC__':
                # Para macOS, o tema escuro é controlado pelo sistema
                # Força refresh do controle
                self.printer_listbox.Refresh()
                
        except Exception as e:
            # Falha silenciosa para não quebrar a aplicação
            pass
        
        # Método adicional: tenta personalizar via CSS no Windows
        if wx.Platform == '__WXMSW__':
            try:
                # Aplica estilo personalizado ao ListCtrl
                self.printer_listbox.SetBackgroundColour(self.colors["card_bg"])
                
                # Força o refresh para aplicar as mudanças
                self.printer_listbox.Refresh()
                self.printer_listbox.Update()
                
                # Agenda uma segunda tentativa
                wx.CallLater(500, self._apply_scrollbar_theme)
                
            except:
                pass

    def _apply_scrollbar_theme(self):
        """Segunda tentativa de aplicar tema na scrollbar"""
        try:
            if wx.Platform == '__WXMSW__':
                import ctypes
                from ctypes import wintypes
                
                hwnd = self.printer_listbox.GetHandle()
                
                # Obtém todos os controles filhos (incluindo scrollbars)
                def enum_child_proc(child_hwnd, lparam):
                    try:
                        # Obtém informações da janela
                        user32 = ctypes.windll.user32
                        
                        # Aplica tema escuro
                        try:
                            uxtheme = ctypes.windll.uxtheme
                            uxtheme.SetWindowTheme(child_hwnd, "DarkMode_CFD", None)
                        except:
                            try:
                                uxtheme.SetWindowTheme(child_hwnd, "DarkMode_Explorer", None)
                            except:
                                pass
                        
                        # Força redraw
                        user32.InvalidateRect(child_hwnd, None, True)
                        user32.UpdateWindow(child_hwnd)
                        
                    except:
                        pass
                    return True
                
                # Enumera e aplica tema em todos os filhos
                enum_proc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
                ctypes.windll.user32.EnumChildWindows(hwnd, enum_proc(enum_child_proc), 0)
                
        except Exception as e:
            pass
        
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
            # Verifica se é Epson L3250 (sem suporte)
            if self._is_epson_l3250(self.selected_printer):
                wx.MessageBox(
                    f"A impressora '{self.selected_printer.name}' é uma Epson L3250 e não possui suporte de impressão neste sistema.",
                    "Impressora sem suporte",
                    wx.OK | wx.ICON_WARNING
                )
                return
            
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
        # Função helper local
        def _is_epson_l3250_local(printer):
            if not printer:
                return False
            
            name = getattr(printer, 'name', '') or ''
            if 'l3250' in name.lower() or 'l-3250' in name.lower():
                return True
            
            model = getattr(printer, 'model', '') or ''
            if 'l3250' in model.lower() or 'l-3250' in model.lower():
                return True
            
            make_model = getattr(printer, 'printer-make-and-model', '') or ''
            if 'l3250' in make_model.lower() or 'l-3250' in make_model.lower():
                return True
            
            return False
        
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
        
        # Verificação adicional para Epson L3250
        if _is_epson_l3250_local(printer):
            wx.MessageBox(
                f"A impressora '{printer.name}' é uma Epson L3250 e não possui suporte de impressão neste sistema.",
                "Impressora sem suporte",
                wx.OK | wx.ICON_WARNING
            )
            return False
        
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
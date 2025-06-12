#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Painel de configuração de auto-impressão com layout corrigido - Dropdowns nativos
"""

import wx
import logging
from src.utils.print_system import PrintOptions, ColorMode, Duplex, Quality
from src.ui.custom_button import create_styled_button

logger = logging.getLogger("PrintManagementSystem.UI.AutoPrintConfig")

class StyledChoice(wx.Choice):
    """wx.Choice com estilização customizada para tema escuro"""
    
    def __init__(self, parent, choices, colors, size=(250, 35)):
        super().__init__(parent, choices=choices, size=size, style=wx.BORDER_NONE)
        
        # Aplica cores para tema escuro
        self.SetBackgroundColour(wx.Colour(45, 45, 45))
        self.SetForegroundColour(colors["text_color"])
        
        # Define fonte
        font = wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL)
        self.SetFont(font)

class CustomSpinCtrl(wx.Panel):
    """SpinCtrl completamente customizado"""
    
    def __init__(self, parent, min_val, max_val, initial, colors, size=(250, 35)):
        super().__init__(parent, size=size)
        
        self.min_val = min_val
        self.max_val = max_val
        self.current_val = initial
        self.colors = colors
        
        self.SetBackgroundColour(wx.Colour(45, 45, 45))
        self.SetMinSize(size)
        
        # Layout
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Campo de texto
        self.text_ctrl = wx.TextCtrl(self, value=str(initial), style=wx.BORDER_NONE | wx.TE_CENTER)
        self.text_ctrl.SetBackgroundColour(wx.Colour(45, 45, 45))
        self.text_ctrl.SetForegroundColour(colors["text_color"])
        
        # Painel de botões
        btn_panel = wx.Panel(self, size=(20, -1))
        btn_panel.SetBackgroundColour(wx.Colour(45, 45, 45))
                
        # Layout principal
        main_sizer.Add(self.text_ctrl, 1, wx.EXPAND | wx.ALL, 2)
        main_sizer.Add(btn_panel, 0, wx.EXPAND | wx.RIGHT, 2)
        self.SetSizer(main_sizer)
        
        self.text_ctrl.Bind(wx.EVT_TEXT, self.on_text_change)
        
        # Paint event
        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
    
    def on_paint(self, event):
        """Desenha borda"""
        dc = wx.BufferedPaintDC(self)
        dc.Clear()
        
        rect = self.GetClientRect()
        dc.SetBrush(wx.Brush(self.GetBackgroundColour()))
        dc.SetPen(wx.Pen(wx.Colour(60, 60, 60), 1))
        dc.DrawRoundedRectangle(0, 0, rect.width, rect.height, 4)
    
    def on_text_change(self, event):
        """Valida entrada de texto"""
        try:
            val = int(self.text_ctrl.GetValue())
            if self.min_val <= val <= self.max_val:
                self.current_val = val
            else:
                self.text_ctrl.SetValue(str(self.current_val))
        except ValueError:
            self.text_ctrl.SetValue(str(self.current_val))
    
    def GetValue(self):
        return self.current_val
    
    def SetValue(self, val):
        if self.min_val <= val <= self.max_val:
            self.current_val = val
            self.text_ctrl.SetValue(str(val))

class AutoPrintConfigPanel(wx.ScrolledWindow):
    """Painel com rolagem para configurar a impressão automática"""
    
    def __init__(self, parent, config, theme_manager=None):
        """
        Inicializa o painel de configuração de auto-impressão
        
        Args:
            parent: Painel pai
            config: Configuração do sistema
            theme_manager: Gerenciador de temas (opcional)
        """
        super().__init__(parent, style=wx.BORDER_NONE)
        
        self.config = config
        self.theme_manager = theme_manager
        
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
            "error_color": wx.Colour(220, 53, 69),
            "warning_color": wx.Colour(255, 193, 7)
        }
        
        # Aplica o tema ao painel
        self.SetBackgroundColour(self.colors["bg_color"])
        
        # Carrega as configurações existentes
        self.auto_print_enabled = self.config.get("auto_print", False)
        self.default_printer = self.config.get("default_printer", "")
        self.auto_print_options = self.config.get("auto_print_options", {})
        
        # Container principal para o conteúdo
        self.main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.SetSizer(self.main_sizer)
        
        # Inicializa a UI
        self._init_ui()
        
        if wx.Platform == '__WXMSW__':
            try:
                import win32gui
                import win32con
                
                def customize_scrollbar():
                    wx.CallAfter(self._customize_scrollbar_colors)
                
                wx.CallLater(100, customize_scrollbar)
            except ImportError:
                pass  # win32gui não disponível

        # Carrega os valores salvos
        self._load_saved_values()
        
        # Configura a rolagem
        self.SetScrollRate(0, 20)
        
        # Força um layout inicial para calcular o tamanho necessário
        self.Layout()
        
        # Ajusta o tamanho virtual para acomodar todo o conteúdo
        self.FitInside()
    
    def _is_epson_l3250(self, printer):
        """Verifica se a impressora é uma Epson L3250 (sem suporte de impressão)"""
        if not printer:
            return False
        
        # Verifica no nome da impressora
        name = printer.get('name', '') or ''
        if 'l3250' in name.lower() or 'l-3250' in name.lower():
            return True
        
        # Verifica no modelo
        model = printer.get('model', '') or ''
        if 'l3250' in model.lower() or 'l-3250' in model.lower():
            return True
        
        # Verifica no atributo printer-make-and-model (IPP)
        make_model = printer.get('printer-make-and-model', '') or ''
        if 'l3250' in make_model.lower() or 'l-3250' in make_model.lower():
            return True
        
        return False
    
    def _filter_valid_printers(self, printers):
        """Filtra impressoras válidas (com IP e com suporte)"""
        if not printers:
            return []
        
        valid_printers = []
        for printer in printers:
            # Verifica se tem IP
            ip = printer.get('ip', '')
            if not ip or ip.strip() == '':
                continue
            
            # Verifica se não é Epson L3250
            if self._is_epson_l3250(printer):
                continue
            
            valid_printers.append(printer)
        
        return valid_printers

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
                    
                    hwnd = self.GetHandle()
                    
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
                self.Refresh()
                
        except Exception as e:
            # Falha silenciosa para não quebrar a aplicação
            pass
        
        # Método adicional: tenta personalizar via CSS no Windows
        if wx.Platform == '__WXMSW__':
            try:
                # Aplica estilo personalizado ao ScrolledWindow
                self.SetBackgroundColour(self.colors["bg_color"])
                
                # Força o refresh para aplicar as mudanças
                self.Refresh()
                self.Update()
                
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
                
                hwnd = self.GetHandle()
                
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
        
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        # Limpa o sizer principal
        self.main_sizer.Clear(True)
        
        # Painel de cabeçalho com título
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(self.colors["bg_color"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Configurações de Auto-Impressão")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(self.colors["text_color"])
        
        header_sizer.Add(title, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        
        header_panel.SetSizer(header_sizer)
        
        # Descrição
        description_panel = wx.Panel(self)
        description_panel.SetBackgroundColour(self.colors["bg_color"])
        description_sizer = wx.BoxSizer(wx.VERTICAL)
        
        description = wx.StaticText(
            description_panel,
            label="Configure a impressão automática para enviar documentos à impressora sem intervenção manual."
        )
        description.SetForegroundColour(self.colors["text_secondary"])
        description.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        description_sizer.Add(description, 0, wx.LEFT | wx.BOTTOM, 20)
        description_panel.SetSizer(description_sizer)
        
        # Card de ativação
        activation_panel = self._create_activation_card()
        
        # Card de configurações
        settings_panel = self._create_settings_card()
        
        # Botões de ação
        action_panel = wx.Panel(self)
        action_panel.SetBackgroundColour(self.colors["bg_color"])
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para atualizar impressoras
        self.update_printers_button = create_styled_button(
            action_panel,
            "Atualizar Impressoras",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (180, 36)
        )
        self.update_printers_button.Bind(wx.EVT_BUTTON, self.on_update_printers)
        action_sizer.Add(self.update_printers_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        
        # Botão para salvar
        self.save_button = create_styled_button(
            action_panel,
            "Salvar Configurações",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(255, 120, 70),
            (180, 36)
        )
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save)
        
        action_sizer.Add(self.save_button, 0, wx.ALIGN_CENTER_VERTICAL)
        
        action_panel.SetSizer(action_sizer)
        
        # Adiciona todos os componentes ao layout principal
        self.main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        self.main_sizer.Add(description_panel, 0, wx.EXPAND | wx.LEFT, 20)
        self.main_sizer.Add(activation_panel, 0, wx.EXPAND | wx.ALL, 10)
        self.main_sizer.Add(settings_panel, 0, wx.EXPAND | wx.ALL, 10)
        self.main_sizer.Add(action_panel, 0, wx.EXPAND | wx.ALL, 10)
    
    def _create_activation_card(self):
        """Cria o card de ativação da auto-impressão"""
        activation_panel = wx.Panel(self)
        activation_panel.SetBackgroundColour(self.colors["card_bg"])
        activation_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(activation_panel, label="Ativar Auto-Impressão")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        activation_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(activation_panel)
        activation_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Checkbox para ativar/desativar
        toggle_panel = wx.Panel(activation_panel)
        toggle_panel.SetBackgroundColour(self.colors["card_bg"])
        toggle_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Descrição do toggle
        toggle_text = wx.StaticText(
            toggle_panel,
            label="Imprimir arquivos automaticamente quando detectados"
        )
        toggle_text.SetForegroundColour(self.colors["text_color"])
        
        self.auto_print_checkbox = wx.CheckBox(toggle_panel, label="")
        self.auto_print_checkbox.SetValue(self.auto_print_enabled)
        self.auto_print_checkbox.SetBackgroundColour(self.colors["card_bg"])
        self.auto_print_checkbox.SetForegroundColour(self.colors["text_color"])

        # Evento de hover para o checkbox
        def on_checkbox_enter(evt):
            toggle_panel.SetBackgroundColour(wx.Colour(40, 40, 40))
            toggle_panel.Refresh()

        def on_checkbox_leave(evt):
            toggle_panel.SetBackgroundColour(self.colors["card_bg"])
            toggle_panel.Refresh()

        self.auto_print_checkbox.Bind(wx.EVT_ENTER_WINDOW, on_checkbox_enter)
        self.auto_print_checkbox.Bind(wx.EVT_LEAVE_WINDOW, on_checkbox_leave)
        toggle_text.Bind(wx.EVT_ENTER_WINDOW, on_checkbox_enter)
        toggle_text.Bind(wx.EVT_LEAVE_WINDOW, on_checkbox_leave)
        
        toggle_sizer.Add(toggle_text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        toggle_sizer.Add(self.auto_print_checkbox, 0, wx.ALIGN_CENTER_VERTICAL)
        
        toggle_panel.SetSizer(toggle_sizer)
        activation_sizer.Add(toggle_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Aviso sobre a funcionalidade
        warning_text = wx.StaticText(
            activation_panel,
            label="Ao ativar, os novos documentos PDF serão enviados automaticamente para a impressora configurada."
        )
        warning_text.SetForegroundColour(self.colors["warning_color"])
        warning_text.Wrap(500)  # Quebra linhas longas
        
        activation_sizer.Add(warning_text, 0, wx.EXPAND | wx.ALL, 10)
        
        activation_panel.SetSizer(activation_sizer)
        
        # Adiciona borda arredondada ao card
        def on_activation_paint(event):
            dc = wx.BufferedPaintDC(activation_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = activation_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in activation_panel.GetChildren():
                child.Refresh()
        
        activation_panel.Bind(wx.EVT_PAINT, on_activation_paint)
        activation_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        return activation_panel
    
    def _create_settings_card(self):
        """Cria o card de configurações da auto-impressão"""
        settings_panel = wx.Panel(self)
        settings_panel.SetBackgroundColour(self.colors["card_bg"])
        settings_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(settings_panel, label="Configurações de Impressão Padrão")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        settings_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(settings_panel)
        settings_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Painel de configurações
        config_panel = wx.Panel(settings_panel)
        config_panel.SetBackgroundColour(self.colors["card_bg"])
        config_sizer = wx.FlexGridSizer(rows=0, cols=2, vgap=15, hgap=20)
        config_sizer.AddGrowableCol(1, 1)
        
        # Largura fixa para todos os controles
        dropdown_width = 250
        
        # Impressora padrão
        printer_label = wx.StaticText(config_panel, label="Impressora padrão:")
        printer_label.SetForegroundColour(self.colors["text_color"])
        
        # Obtém lista de impressoras
        printers = self.config.get_printers()
        valid_printers = self._filter_valid_printers(printers)
        printer_names = [p.get('name', '') for p in valid_printers] if valid_printers else []
        
        # Se não tiver impressoras, adiciona uma mensagem
        if not printer_names:
            printer_names = ["Nenhuma impressora encontrada"]

        # Dropdown nativo com estilização
        self.printer_choice = StyledChoice(config_panel, printer_names, self.colors, (dropdown_width, 35))
        if printer_names:
            # Seleciona a impressora padrão se existir
            default_idx = 0
            for i, name in enumerate(printer_names):
                if name == self.default_printer:
                    default_idx = i
                    break
            self.printer_choice.SetSelection(default_idx)

        config_sizer.Add(printer_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.printer_choice, 0, wx.EXPAND)

        # Modo de cor
        color_label = wx.StaticText(config_panel, label="Modo de cor:")
        color_label.SetForegroundColour(self.colors["text_color"])

        color_choices = ["Automático", "Colorido", "Preto e branco"]
        self.color_choice = StyledChoice(config_panel, color_choices, self.colors, (dropdown_width, 35))
        self.color_choice.SetSelection(0)  # Automático

        config_sizer.Add(color_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.color_choice, 0, wx.EXPAND)

        # Duplex
        duplex_label = wx.StaticText(config_panel, label="Impressão frente e verso:")
        duplex_label.SetForegroundColour(self.colors["text_color"])

        duplex_choices = ["Somente frente", "Frente e verso (borda longa)", "Frente e verso (borda curta)"]
        self.duplex_choice = StyledChoice(config_panel, duplex_choices, self.colors, (dropdown_width, 35))
        self.duplex_choice.SetSelection(0)  # Somente frente

        config_sizer.Add(duplex_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.duplex_choice, 0, wx.EXPAND)

        # Qualidade
        quality_label = wx.StaticText(config_panel, label="Qualidade:")
        quality_label.SetForegroundColour(self.colors["text_color"])

        quality_choices = ["Rascunho", "Normal", "Alta"]
        self.quality_choice = StyledChoice(config_panel, quality_choices, self.colors, (dropdown_width, 35))
        self.quality_choice.SetSelection(1)  # Normal

        config_sizer.Add(quality_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.quality_choice, 0, wx.EXPAND)

        # Orientação
        orientation_label = wx.StaticText(config_panel, label="Orientação:")
        orientation_label.SetForegroundColour(self.colors["text_color"])

        orientation_choices = ["Retrato", "Paisagem"]
        self.orientation_choice = StyledChoice(config_panel, orientation_choices, self.colors, (dropdown_width, 35))
        self.orientation_choice.SetSelection(0)  # Retrato

        config_sizer.Add(orientation_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.orientation_choice, 0, wx.EXPAND)

        # Cópias
        copies_label = wx.StaticText(config_panel, label="Número de cópias:")
        copies_label.SetForegroundColour(self.colors["text_color"])

        self.copies_spin = CustomSpinCtrl(config_panel, 1, 99, 1, self.colors, (dropdown_width, 25))

        config_sizer.Add(copies_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.copies_spin, 0, wx.EXPAND)
        
        config_panel.SetSizer(config_sizer)
        settings_sizer.Add(config_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        settings_panel.SetSizer(settings_sizer)
        
        # Adiciona borda arredondada ao card
        def on_settings_paint(event):
            dc = wx.BufferedPaintDC(settings_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = settings_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in settings_panel.GetChildren():
                child.Refresh()
        
        settings_panel.Bind(wx.EVT_PAINT, on_settings_paint)
        settings_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        return settings_panel
    
    def _load_saved_values(self):
        """Carrega os valores salvos nas configurações"""
        # Carrega status de auto-impressão
        self.auto_print_checkbox.SetValue(self.auto_print_enabled)
        
        # Carrega impressora padrã
        printers = self.config.get_printers()
        valid_printers = self._filter_valid_printers(printers)
        printer_names = [p.get('name', '') for p in valid_printers]
        
        if printer_names and self.default_printer:
            for i, name in enumerate(printer_names):
                if name == self.default_printer:
                    self.printer_choice.SetSelection(i)
                    break
            else:
                # Se a impressora padrão não está na lista válida, limpa a seleção
                if printer_names and printer_names[0] != "Nenhuma impressora válida encontrada":
                    self.printer_choice.SetSelection(0)
                    self.default_printer = printer_names[0]
                else:
                    self.default_printer = ""
        
        # Carrega opções de impressão
        if self.auto_print_options:
            # Modo de cor
            color_mode = self.auto_print_options.get("color_mode", "auto")
            if color_mode == "color":
                self.color_choice.SetSelection(1)
            elif color_mode == "monochrome":
                self.color_choice.SetSelection(2)
            else:
                self.color_choice.SetSelection(0)
            
            # Duplex
            duplex = self.auto_print_options.get("duplex", "one-sided")
            if duplex == "two-sided-long-edge":
                self.duplex_choice.SetSelection(1)
            elif duplex == "two-sided-short-edge":
                self.duplex_choice.SetSelection(2)
            else:
                self.duplex_choice.SetSelection(0)
            
            # Qualidade
            quality = self.auto_print_options.get("quality", 4)
            if quality == 3:
                self.quality_choice.SetSelection(0)
            elif quality == 5:
                self.quality_choice.SetSelection(2)
            else:
                self.quality_choice.SetSelection(1)
            
            # Orientação
            orientation = self.auto_print_options.get("orientation", "portrait")
            if orientation == "landscape":
                self.orientation_choice.SetSelection(1)
            else:
                self.orientation_choice.SetSelection(0)
            
            # Cópias
            copies = self.auto_print_options.get("copies", 1)
            self.copies_spin.SetValue(copies)
    
    def on_update_printers(self, event):
        """Atualiza a lista de impressoras disponíveis"""
        try:
            # Mostra diálogo de progresso
            busy = wx.BusyInfo("Atualizando impressoras, aguarde...", parent=self)
            
            # Verifica se há uma instância do PrinterListPanel para usar seu método
            app = wx.GetApp()
            if hasattr(app, 'main_screen') and hasattr(app.main_screen, 'printer_list'):
                printer_list = app.main_screen.printer_list
                printer_list.on_update_printers()
            else:
                # Tenta usar diretamente o API client
                from src.utils.printer_discovery import PrinterDiscovery
                from src.models.printer import Printer
                
                discovery = PrinterDiscovery()
                discovered_printers = discovery.discover_printers()
                
                if discovered_printers:
                    # Converte para o formato esperado
                    printer_dicts = []
                    for printer_data in discovered_printers:
                        try:
                            # Cria objeto Printer e converte para dicionário
                            printer = Printer(printer_data)
                            printer_dict = printer.to_dict()
                            printer_dicts.append(printer_dict)
                        except Exception as e:
                            logger.error(f"Erro ao processar impressora: {str(e)}")
                    
                    # Salva as impressoras no config
                    self.config.set_printers(printer_dicts)
                else:
                    # Remove o diálogo de progresso
                    del busy
                    
                    wx.MessageBox("Nenhuma impressora encontrada na rede. Verifique sua conexão.", 
                            "Aviso", wx.OK | wx.ICON_WARNING)
                    return
            
            # Salva as configurações atuais antes de recriar a UI
            self._save_current_values()
            
            # Remove o diálogo de progresso
            del busy
            
            # Recria toda a UI para garantir que os dropdowns sejam atualizados
            self._init_ui()
            self._load_saved_values()
            
            # Atualiza o layout
            self.Layout()
            self.FitInside()
            
            # Verifica quantas impressoras válidas foram encontradas
            printers = self.config.get_printers()
            valid_printers = self._filter_valid_printers(printers)
            
            if valid_printers:
                wx.MessageBox(f"Lista de impressoras atualizada com sucesso!\n\n"
                            f"{len(valid_printers)} impressoras válidas encontradas "
                            f"(com IP e suporte de impressão).", 
                        "Informação", wx.OK | wx.ICON_INFORMATION)
            else:
                wx.MessageBox("Nenhuma impressora válida encontrada.\n\n"
                            "Impressoras sem IP ou modelo Epson L3250 não são "
                            "suportadas para auto-impressão.", 
                        "Aviso", wx.OK | wx.ICON_WARNING)
            
        except Exception as e:
            logger.error(f"Erro ao atualizar impressoras: {str(e)}")
            wx.MessageBox(f"Erro ao atualizar impressoras: {str(e)}", 
                    "Erro", wx.OK | wx.ICON_ERROR)
    
    def _save_current_values(self):
        """Salva os valores atuais nas variáveis de instância"""
        self.auto_print_enabled = self.auto_print_checkbox.GetValue()
        
        # Salva a impressora selecionada
        printer_index = self.printer_choice.GetSelection()
        printers = self.config.get_printers()
        valid_printers = self._filter_valid_printers(printers)
        
        if printer_index != wx.NOT_FOUND and valid_printers and printer_index < len(valid_printers):
            selected_printer = valid_printers[printer_index]
            self.default_printer = selected_printer.get('name', '')
        else:
            self.default_printer = ""  # Limpa se não há seleção válida
        
        # Salva as opções de impressão
        # Modo de cor
        color_idx = self.color_choice.GetSelection()
        if color_idx == 1:  # Colorido
            self.auto_print_options["color_mode"] = "color"
        elif color_idx == 2:  # Preto e branco
            self.auto_print_options["color_mode"] = "monochrome"
        else:  # Automático
            self.auto_print_options["color_mode"] = "auto"
        
        # Duplex
        duplex_idx = self.duplex_choice.GetSelection()
        if duplex_idx == 1:  # Borda longa
            self.auto_print_options["duplex"] = "two-sided-long-edge"
        elif duplex_idx == 2:  # Borda curta
            self.auto_print_options["duplex"] = "two-sided-short-edge"
        else:  # Simples
            self.auto_print_options["duplex"] = "one-sided"
        
        # Qualidade
        quality_idx = self.quality_choice.GetSelection()
        if quality_idx == 0:  # Rascunho
            self.auto_print_options["quality"] = 3
        elif quality_idx == 2:  # Alta
            self.auto_print_options["quality"] = 5
        else:  # Normal
            self.auto_print_options["quality"] = 4
        
        # Orientação
        orientation_idx = self.orientation_choice.GetSelection()
        self.auto_print_options["orientation"] = "landscape" if orientation_idx == 1 else "portrait"
        
        # Cópias
        self.auto_print_options["copies"] = self.copies_spin.GetValue()
    
    def on_save(self, event):
        """Salva as configurações"""
        # Função helper local
        def _is_epson_l3250_local(printer_name):
            if not printer_name:
                return False
            return 'l3250' in printer_name.lower() or 'l-3250' in printer_name.lower()
        
        # Salva os valores nas variáveis de instância
        self._save_current_values()
        
        # Verifica se há impressoras
        printers = self.config.get_printers()
        if not printers and self.auto_print_enabled:
            wx.MessageBox(
                "Não há impressoras disponíveis. A auto-impressão não funcionará sem impressoras configuradas.",
                "Aviso",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        # Verifica se a impressora padrão é Epson L3250
        if self.auto_print_enabled and self.default_printer and _is_epson_l3250_local(self.default_printer):
            wx.MessageBox(
                "A impressora padrão selecionada é uma Epson L3250, que não possui suporte de impressão neste sistema. "
                "Por favor, selecione uma impressora diferente para auto-impressão.",
                "Impressora sem suporte",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        # Salva na configuração
        self.config.set("auto_print", self.auto_print_enabled)
        self.config.set("default_printer", self.default_printer)
        self.config.set("auto_print_options", self.auto_print_options)
        
        # Notifica o usuário
        wx.MessageBox(
            "Configurações de auto-impressão salvas com sucesso.",
            "Sucesso",
            wx.OK | wx.ICON_INFORMATION
        )
        
        # Atualiza o tamanho virtual após salvar
        self.FitInside()
        
        # Notifica o sistema sobre a mudança na auto-impressão (se necessário)
        try:
            app = wx.GetApp()
            if hasattr(app, 'main_screen') and hasattr(app.main_screen, 'file_monitor'):
                app.main_screen.file_monitor.set_auto_print(self.auto_print_enabled)
                logger.info(f"Auto-impressão {'ativada' if self.auto_print_enabled else 'desativada'}")
        except Exception as e:
            logger.error(f"Erro ao atualizar status de auto-impressão: {e}")
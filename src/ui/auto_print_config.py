#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Painel de configuração de auto-impressão
"""

import wx
import logging
from src.utils.print_system import PrintOptions, ColorMode, Duplex, Quality

logger = logging.getLogger("PrintManagementSystem.UI.AutoPrintConfig")

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
        
        self._init_ui()
        
        # Carrega os valores salvos
        self._load_saved_values()
        
        # Configura a rolagem
        self.SetScrollRate(0, 20)
        
        # Força um layout inicial para calcular o tamanho necessário
        self.Layout()
        
        # Ajusta o tamanho virtual para acomodar todo o conteúdo
        self.FitInside()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
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
        
        # Botão para salvar
        self.save_button = wx.Button(action_panel, label="Salvar Configurações", size=(180, 36))
        self.save_button.SetBackgroundColour(self.colors["accent_color"])
        self.save_button.SetForegroundColour(self.colors["text_color"])
        self.save_button.Bind(wx.EVT_BUTTON, self.on_save)
        
        # Eventos de hover para o botão
        def on_save_enter(evt):
            self.save_button.SetBackgroundColour(wx.Colour(255, 120, 70))
            self.save_button.Refresh()
        
        def on_save_leave(evt):
            self.save_button.SetBackgroundColour(self.colors["accent_color"])
            self.save_button.Refresh()
        
        self.save_button.Bind(wx.EVT_ENTER_WINDOW, on_save_enter)
        self.save_button.Bind(wx.EVT_LEAVE_WINDOW, on_save_leave)
        
        action_sizer.Add(self.save_button, 0, wx.ALIGN_CENTER_VERTICAL)
        
        action_panel.SetSizer(action_sizer)
        
        # Adiciona todos os componentes ao layout principal
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        main_sizer.Add(description_panel, 0, wx.EXPAND | wx.LEFT, 20)
        main_sizer.Add(activation_panel, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(settings_panel, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(action_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        self.SetSizer(main_sizer)
    
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
        
        # Impressora padrão
        printer_label = wx.StaticText(config_panel, label="Impressora padrão:")
        printer_label.SetForegroundColour(self.colors["text_color"])
        
        # Obtém lista de impressoras
        printers = self.config.get_printers()
        printer_names = [p.get('name', '') for p in printers] if printers else []
        
        self.printer_choice = wx.Choice(config_panel, choices=printer_names)
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
        self.color_choice = wx.Choice(config_panel, choices=color_choices)
        self.color_choice.SetSelection(0)  # Automático
        
        config_sizer.Add(color_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.color_choice, 0, wx.EXPAND)
        
        # Duplex
        duplex_label = wx.StaticText(config_panel, label="Impressão frente e verso:")
        duplex_label.SetForegroundColour(self.colors["text_color"])
        
        duplex_choices = ["Somente frente", "Frente e verso (borda longa)", "Frente e verso (borda curta)"]
        self.duplex_choice = wx.Choice(config_panel, choices=duplex_choices)
        self.duplex_choice.SetSelection(0)  # Somente frente
        
        config_sizer.Add(duplex_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.duplex_choice, 0, wx.EXPAND)
        
        # Qualidade
        quality_label = wx.StaticText(config_panel, label="Qualidade:")
        quality_label.SetForegroundColour(self.colors["text_color"])
        
        quality_choices = ["Rascunho", "Normal", "Alta"]
        self.quality_choice = wx.Choice(config_panel, choices=quality_choices)
        self.quality_choice.SetSelection(1)  # Normal
        
        config_sizer.Add(quality_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.quality_choice, 0, wx.EXPAND)
        
        # Orientação
        orientation_label = wx.StaticText(config_panel, label="Orientação:")
        orientation_label.SetForegroundColour(self.colors["text_color"])
        
        orientation_choices = ["Retrato", "Paisagem"]
        self.orientation_choice = wx.Choice(config_panel, choices=orientation_choices)
        self.orientation_choice.SetSelection(0)  # Retrato
        
        config_sizer.Add(orientation_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        config_sizer.Add(self.orientation_choice, 0, wx.EXPAND)
        
        # Cópias
        copies_label = wx.StaticText(config_panel, label="Número de cópias:")
        copies_label.SetForegroundColour(self.colors["text_color"])
        
        self.copies_spin = wx.SpinCtrl(config_panel, min=1, max=99, initial=1)
        
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
        
        # Carrega impressora padrão
        printers = self.config.get_printers()
        printer_names = [p.get('name', '') for p in printers] if printers else []
        
        if printer_names and self.default_printer:
            for i, name in enumerate(printer_names):
                if name == self.default_printer:
                    self.printer_choice.SetSelection(i)
                    break
        
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
    
    def on_save(self, event):
        """Salva as configurações"""
        # Obtém os valores atuais
        auto_print_enabled = self.auto_print_checkbox.GetValue()
        
        # Obtém a impressora selecionada
        printer_index = self.printer_choice.GetSelection()
        printers = self.config.get_printers()
        
        if printer_index == wx.NOT_FOUND or not printers:
            wx.MessageBox(
                "Selecione uma impressora válida para a auto-impressão.",
                "Aviso",
                wx.OK | wx.ICON_WARNING
            )
            return
        
        selected_printer = printers[printer_index]
        default_printer = selected_printer.get('name', '')
        
        # Constrói as opções de impressão
        options = {}
        
        # Modo de cor
        color_idx = self.color_choice.GetSelection()
        if color_idx == 1:  # Colorido
            options["color_mode"] = "color"
        elif color_idx == 2:  # Preto e branco
            options["color_mode"] = "monochrome"
        else:  # Automático
            options["color_mode"] = "auto"
        
        # Duplex
        duplex_idx = self.duplex_choice.GetSelection()
        if duplex_idx == 1:  # Borda longa
            options["duplex"] = "two-sided-long-edge"
        elif duplex_idx == 2:  # Borda curta
            options["duplex"] = "two-sided-short-edge"
        else:  # Simples
            options["duplex"] = "one-sided"
        
        # Qualidade
        quality_idx = self.quality_choice.GetSelection()
        if quality_idx == 0:  # Rascunho
            options["quality"] = 3
        elif quality_idx == 2:  # Alta
            options["quality"] = 5
        else:  # Normal
            options["quality"] = 4
        
        # Orientação
        orientation_idx = self.orientation_choice.GetSelection()
        options["orientation"] = "landscape" if orientation_idx == 1 else "portrait"
        
        # Cópias
        options["copies"] = self.copies_spin.GetValue()
        
        # Salva na configuração
        self.config.set("auto_print", auto_print_enabled)
        self.config.set("default_printer", default_printer)
        self.config.set("auto_print_options", options)
        
        # Atualiza os valores locais
        self.auto_print_enabled = auto_print_enabled
        self.default_printer = default_printer
        self.auto_print_options = options
        
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
                app.main_screen.file_monitor.set_auto_print(auto_print_enabled)
                logger.info(f"Auto-impressão {'ativada' if auto_print_enabled else 'desativada'}")
        except Exception as e:
            logger.error(f"Erro ao atualizar status de auto-impressão: {e}")
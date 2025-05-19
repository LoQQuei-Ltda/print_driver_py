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
                      "accent_color": wx.Colour(255, 90, 36),
                      "text_color": wx.WHITE,
                      "text_secondary": wx.Colour(180, 180, 180)}
        
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
        header_panel.SetBackgroundColour(self.colors["panel_bg"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Ícone da impressora
        printer_icon_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
            "src", "ui", "resources", "printer.png"
        )
        
        if os.path.exists(printer_icon_path):
            printer_icon = wx.StaticBitmap(
                header_panel,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(48, 48)
            )
            header_sizer.Add(printer_icon, 0, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 10)
        
        # Informações básicas
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Nome da impressora
        printer_name = wx.StaticText(header_panel, label=self.printer.name)
        printer_name.SetForegroundColour(self.colors["text_color"])
        printer_name.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(printer_name, 0, wx.BOTTOM, 5)
        
        # Modelo
        if self.printer.model:
            model_text = wx.StaticText(header_panel, label=f"Modelo: {self.printer.model}")
            model_text.SetForegroundColour(self.colors["text_secondary"])
            info_sizer.Add(model_text, 0, wx.BOTTOM, 3)
        
        # Estado
        if self.printer.state:
            state_text = wx.StaticText(header_panel, label=f"Estado: {self.printer.state}")
            state_text.SetForegroundColour(self.colors["text_secondary"])
            info_sizer.Add(state_text, 0)
        
        header_sizer.Add(info_sizer, 1, wx.EXPAND | wx.ALL, 10)
        header_panel.SetSizer(header_sizer)
        
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(self.panel, style=wx.LI_HORIZONTAL)
        main_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Notebook para categorias de informações
        self.notebook = wx.Notebook(self.panel)
        self.notebook.SetBackgroundColour(self.colors["panel_bg"])
        
        # Guia de resumo
        self.summary_panel = wx.ScrolledWindow(self.notebook)
        self.summary_panel.SetBackgroundColour(self.colors["panel_bg"])
        self.summary_panel.SetScrollRate(0, 10)
        summary_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.summary_loading_text = wx.StaticText(self.summary_panel, label="Carregando informações da impressora...")
        self.summary_loading_text.SetForegroundColour(self.colors["text_color"])
        summary_sizer.Add(self.summary_loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.summary_panel.SetSizer(summary_sizer)
        
        # Guia de informações de conectividade
        self.connectivity_panel = wx.Panel(self.notebook)
        self.connectivity_panel.SetBackgroundColour(self.colors["panel_bg"])
        connectivity_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # IP
        if self.printer.ip:
            ip_panel = self._create_info_row(self.connectivity_panel, "IP:", self.printer.ip)
            connectivity_sizer.Add(ip_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # MAC Address
        if self.printer.mac_address:
            mac_panel = self._create_info_row(self.connectivity_panel, "MAC Address:", self.printer.mac_address)
            connectivity_sizer.Add(mac_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # URI
        if self.printer.uri:
            uri_panel = self._create_info_row(self.connectivity_panel, "URI:", self.printer.uri)
            connectivity_sizer.Add(uri_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Status
        is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
        is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
        is_usable = is_online and is_ready
        
        status_text = "Pronta" if is_usable else "Indisponível"
        status_panel = self._create_info_row(self.connectivity_panel, "Status:", status_text)
        connectivity_sizer.Add(status_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Estado
        if self.printer.state:
            state_panel = self._create_info_row(self.connectivity_panel, "Estado:", self.printer.state)
            connectivity_sizer.Add(state_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Portas
        if self.printer.attributes and 'ports' in self.printer.attributes:
            ports = ", ".join(str(p) for p in self.printer.attributes['ports'])
            ports_panel = self._create_info_row(self.connectivity_panel, "Portas:", ports)
            connectivity_sizer.Add(ports_panel, 0, wx.EXPAND | wx.ALL, 5)
        
        # Botão para diagnóstico (somente se tiver IP)
        if self.printer.ip:
            diagnostic_button = wx.Button(self.connectivity_panel, label="Executar Diagnóstico")
            diagnostic_button.Bind(wx.EVT_BUTTON, self._on_diagnostic)
            connectivity_sizer.Add(diagnostic_button, 0, wx.ALIGN_CENTER | wx.ALL, 10)
        
        self.connectivity_panel.SetSizer(connectivity_sizer)
        
        # Guia de atributos
        self.attributes_panel = wx.ScrolledWindow(self.notebook)
        self.attributes_panel.SetBackgroundColour(self.colors["panel_bg"])
        self.attributes_panel.SetScrollRate(0, 10)
        self.attributes_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.loading_text = wx.StaticText(self.attributes_panel, label="Carregando atributos da impressora...")
        self.loading_text.SetForegroundColour(self.colors["text_color"])
        self.attributes_sizer.Add(self.loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.attributes_panel.SetSizer(self.attributes_sizer)
        
        # Guia de suprimentos
        self.supplies_panel = wx.ScrolledWindow(self.notebook)
        self.supplies_panel.SetBackgroundColour(self.colors["panel_bg"])
        self.supplies_panel.SetScrollRate(0, 10)
        self.supplies_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de carregamento
        self.supplies_loading_text = wx.StaticText(self.supplies_panel, label="Carregando informações de suprimentos...")
        self.supplies_loading_text.SetForegroundColour(self.colors["text_color"])
        self.supplies_sizer.Add(self.supplies_loading_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.supplies_panel.SetSizer(self.supplies_sizer)
        
        # Guia de diagnóstico
        self.diagnostic_panel = wx.ScrolledWindow(self.notebook)
        self.diagnostic_panel.SetBackgroundColour(self.colors["panel_bg"])
        self.diagnostic_panel.SetScrollRate(0, 10)
        self.diagnostic_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Texto de instrução
        diagnostic_text = wx.StaticText(
            self.diagnostic_panel, 
            label="Execute um diagnóstico na guia de Conectividade para verificar o status da impressora."
        )
        diagnostic_text.SetForegroundColour(self.colors["text_color"])
        self.diagnostic_sizer.Add(diagnostic_text, 0, wx.ALL | wx.CENTER, 20)
        
        self.diagnostic_panel.SetSizer(self.diagnostic_sizer)
        
        # Adiciona as guias ao notebook
        self.notebook.AddPage(self.summary_panel, "Resumo")
        self.notebook.AddPage(self.connectivity_panel, "Conectividade")
        self.notebook.AddPage(self.attributes_panel, "Atributos")
        self.notebook.AddPage(self.supplies_panel, "Suprimentos")
        self.notebook.AddPage(self.diagnostic_panel, "Diagnóstico")
        
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para atualizar
        self.refresh_button = wx.Button(self.panel, label="Atualizar Informações")
        self.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)
        button_sizer.Add(self.refresh_button, 0, wx.RIGHT, 10)
        
        # Botão para fechar
        close_button = wx.Button(self.panel, label="Fechar")
        close_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CANCEL))
        button_sizer.Add(close_button, 0)
        
        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
    
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
        panel.SetBackgroundColour(self.colors["panel_bg"])
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
            value_panel.SetBackgroundColour(self.colors["panel_bg"])
            value_sizer = wx.BoxSizer(wx.HORIZONTAL)
            
            # Trunca o valor para exibição
            display_value = str(value)[:27] + "..."
            value_ctrl = wx.StaticText(value_panel, label=display_value)
            value_ctrl.SetForegroundColour(self.colors["text_secondary"])
            value_sizer.Add(value_ctrl, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
            
            # Botão para copiar
            copy_button = wx.Button(value_panel, label="Copiar", size=(60, 25))
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
        self.notebook.SetSelection(4)
        
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
            
        # Adiciona o resultado geral
        overall = results.get("overall", {})
        success = overall.get("success", False)
        message = overall.get("message", "Diagnóstico concluído")
        
        # Cor baseada no resultado
        color = wx.Colour(40, 167, 69) if success else wx.Colour(220, 53, 69)
        
        # Título do resultado
        result_text = wx.StaticText(self.diagnostic_panel, label=f"Resultado: {message}")
        result_text.SetForegroundColour(color)
        result_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.diagnostic_sizer.Add(result_text, 0, wx.ALL | wx.CENTER, 10)
        
        # Separador
        separator = wx.StaticLine(self.diagnostic_panel, style=wx.LI_HORIZONTAL)
        self.diagnostic_sizer.Add(separator, 0, wx.EXPAND | wx.ALL, 10)
        
        # Adiciona os resultados detalhados de cada teste
        for test_id, test_result in results.items():
            if test_id != "overall":
                self._add_test_result(test_id, test_result)
        
        self.diagnostic_panel.Layout()
        
    def _add_test_result(self, test_id, result):
        """
        Adiciona o resultado de um teste ao painel de diagnóstico
        
        Args:
            test_id: ID do teste
            result: Resultado do teste
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
        test_panel = wx.Panel(self.diagnostic_panel)
        test_panel.SetBackgroundColour(self.colors["panel_bg"])
        test_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título do teste
        success = result.get("success", False)
        status = "Passou" if success else "Falhou"
        title = wx.StaticText(test_panel, label=f"{test_name}: {status}")
        
        # Cor baseada no resultado
        color = wx.Colour(40, 167, 69) if success else wx.Colour(220, 53, 69)
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
            details_text.Wrap(self.diagnostic_panel.GetSize().width - 40)  # Wrap text to fit in panel
            test_sizer.Add(details_text, 0, wx.LEFT | wx.BOTTOM, 5)
        
        test_panel.SetSizer(test_sizer)
        self.diagnostic_sizer.Add(test_panel, 0, wx.EXPAND | wx.ALL, 5)
    
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
            self.summary_loading_text.SetLabel("Não foi possível carregar os detalhes da impressora.")
            self.loading_text.SetLabel("Não foi possível carregar os atributos da impressora.")
            self.supplies_loading_text.SetLabel("Não foi possível carregar informações de suprimentos.")
            return
        
        # Atualiza a impressora com os detalhes
        self.printer.update_from_discovery(details)
        
        # Atualiza cada painel
        self._update_summary_panel(details)
        self._update_attributes_panel(details)
        self._update_supplies_panel(details)
        
        # Atualiza o estado de conectividade
        self._update_connectivity_status()
        
        self.details_loaded = True
    
    def _update_summary_panel(self, details):
        """
        Atualiza o painel de resumo
        
        Args:
            details: Detalhes da impressora
        """
        # Limpa o painel
        self.summary_loading_text.Destroy()
        self.summary_panel.GetSizer().Clear()
        
        # Cria um estilo de texto para título
        title_style = wx.TextAttr()
        title_style.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title_style.SetTextColour(self.colors["text_color"])
        
        # Cria um estilo de texto para conteúdo
        content_style = wx.TextAttr()
        content_style.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        content_style.SetTextColour(self.colors["text_secondary"])
        
        # Cria um controle de texto com formatação
        text_ctrl = wx.TextCtrl(
            self.summary_panel,
            style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_NONE
        )
        text_ctrl.SetBackgroundColour(self.colors["panel_bg"])
        
        # Cabeçalho de resumo
        text_ctrl.SetDefaultStyle(title_style)
        text_ctrl.AppendText("RESUMO DA IMPRESSORA: " + self.printer.name + "\n")
        text_ctrl.AppendText("=" * 50 + "\n")
        
        # Informações básicas
        text_ctrl.SetDefaultStyle(content_style)
        text_ctrl.AppendText(f"IP: {self.printer.ip or 'Desconhecido'}\n")
        text_ctrl.AppendText(f"Modelo: {self.printer.model or 'Desconhecido'}\n")
        text_ctrl.AppendText(f"Localização: {self.printer.location or 'Desconhecida'}\n")
        text_ctrl.AppendText(f"Status: {self.printer.state or 'Desconhecido'}\n")
        
        # Informações adicionais
        if 'manufacturer' in details:
            text_ctrl.AppendText(f"Fabricante: {details['manufacturer']}\n")
        if 'version' in details:
            text_ctrl.AppendText(f"Versão: {details['version']}\n")
        if 'serial' in details:
            text_ctrl.AppendText(f"Número de Série: {details['serial']}\n")
        
        # URIs suportadas
        if 'printer-uri-supported' in details:
            uris = details['printer-uri-supported']
            if isinstance(uris, list):
                text_ctrl.AppendText(f"URIs suportadas: {uris}\n")
            else:
                text_ctrl.AppendText(f"URIs suportadas: [{uris}]\n")
        
        # Adiciona informações de suprimentos se disponíveis
        if 'supplies' in details and details['supplies']:
            text_ctrl.AppendText("\nInformações de Suprimentos:\n")
            for supply in details['supplies']:
                text_ctrl.AppendText(f"  {supply['name']}: {supply['level']}% (Tipo: {supply['type']}, Cor: {supply.get('color', 'N/A')})\n")
        
        text_ctrl.AppendText("=" * 50 + "\n")
        
        # Ajusta o tamanho do controle de texto
        self.summary_panel.GetSizer().Add(text_ctrl, 1, wx.EXPAND | wx.ALL, 10)
        self.summary_panel.Layout()
    
    def _update_attributes_panel(self, details):
        """
        Atualiza o painel de atributos
        
        Args:
            details: Detalhes da impressora
        """
        if not details:
            self.loading_text.SetLabel("Não foi possível carregar os atributos da impressora.")
            return
        
        # Limpa o sizer
        self.loading_text.Destroy()
        self.attributes_sizer.Clear()
        
        # Adiciona os atributos
        sorted_attrs = sorted(details.items())
        
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
                    
            # Adiciona a linha
            row = self._create_info_row(self.attributes_panel, f"{key}:", value)
            self.attributes_sizer.Add(row, 0, wx.EXPAND | wx.ALL, 3)
            
            # Alterna cor de fundo para melhor legibilidade
            if i % 2 == 0:
                row.SetBackgroundColour(self.colors["panel_bg"])
            else:
                row.SetBackgroundColour(wx.Colour(30, 30, 30))
        
        # Atualiza o layout
        self.attributes_panel.Layout()
    
    def _update_supplies_panel(self, details):
        """
        Atualiza o painel de suprimentos
        
        Args:
            details: Detalhes da impressora
        """
        # Limpa o sizer
        self.supplies_loading_text.Destroy()
        self.supplies_sizer.Clear()
        
        # Verifica se há informações de suprimentos
        if 'supplies' in details and details['supplies']:
            for supply in details['supplies']:
                supply_panel = wx.Panel(self.supplies_panel)
                supply_panel.SetBackgroundColour(self.colors["panel_bg"])
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
                
                # Barra de progresso
                gauge = wx.Gauge(supply_panel, range=100, size=(-1, 20))
                gauge.SetValue(int(supply['level']))
                supply_sizer.Add(gauge, 0, wx.EXPAND | wx.ALL, 5)
                
                # Nível
                level_text = f"Nível: {supply['level']}%"
                level = wx.StaticText(supply_panel, label=level_text)
                level.SetForegroundColour(self.colors["text_secondary"])
                supply_sizer.Add(level, 0, wx.LEFT | wx.BOTTOM, 5)
                
                supply_panel.SetSizer(supply_sizer)
                self.supplies_sizer.Add(supply_panel, 0, wx.EXPAND | wx.ALL, 10)
        else:
            # Sem informações de suprimentos
            no_supplies = wx.StaticText(self.supplies_panel, label="Nenhuma informação de suprimentos disponível.")
            no_supplies.SetForegroundColour(self.colors["text_color"])
            self.supplies_sizer.Add(no_supplies, 0, wx.ALL | wx.CENTER, 20)
        
        # Atualiza o layout
        self.supplies_panel.Layout()
    
    def _update_connectivity_status(self):
        """Atualiza o status na guia de conectividade"""
        # Encontra o painel de status
        for child in self.connectivity_panel.GetChildren():
            if isinstance(child, wx.Panel):
                for grandchild in child.GetChildren():
                    if isinstance(grandchild, wx.StaticText) and grandchild.GetLabel() == "Status:":
                        # Encontrou o painel, atualiza o valor
                        for sibling in child.GetChildren():
                            if isinstance(sibling, wx.StaticText) and sibling != grandchild:
                                # Verifica os atributos da impressora de forma segura
                                is_online = hasattr(self.printer, 'is_online') and self.printer.is_online
                                is_ready = hasattr(self.printer, 'is_ready') and self.printer.is_ready
                                is_usable = is_online and is_ready
                                
                                status_text = "Pronta" if is_usable else "Indisponível"
                                sibling.SetLabel(status_text)
                                sibling.SetForegroundColour(wx.Colour(40, 167, 69) if is_usable else wx.Colour(220, 53, 69))
                                child.Layout()
                                break
                        break
    
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
        self.update_button = wx.Button(header_panel, label="Atualizar Impressoras", size=(160, 36))
        self.update_button.SetBackgroundColour(self.colors["accent_color"])
        self.update_button.SetForegroundColour(self.colors["text_color"])
        self.update_button.Bind(wx.EVT_BUTTON, self.on_update_printers)
        
        # Eventos de hover para o botão
        def on_update_enter(evt):
            self.update_button.SetBackgroundColour(wx.Colour(255, 120, 70))
            self.update_button.Refresh()
        
        def on_update_leave(evt):
            self.update_button.SetBackgroundColour(self.colors["accent_color"])
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
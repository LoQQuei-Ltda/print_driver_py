#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Painel de fila de impressão
"""

import os
import wx
import logging
from datetime import datetime
from src.ui.custom_button import create_styled_button

from src.models.print_job import PrintJob, PrintJobStatus
from src.utils.print_system import PrintQueueManager

logger = logging.getLogger("PrintManagementSystem.UI.PrintQueuePanel")

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

class PrintQueuePanel(wx.Panel):
    """Painel para exibir e gerenciar a fila de impressão"""
    
    def __init__(self, parent, config):
        """
        Inicializa o painel de fila de impressão
        
        Args:
            parent: Painel pai
            config: Configuração do sistema
        """
        super().__init__(parent, style=wx.TAB_TRAVERSAL)

        apply_dark_scrollbar_style(self)
        
        self.config = config
        self.print_queue_manager = PrintQueueManager.get_instance()
        self.print_queue_manager.set_config(config)
        self.jobs = []
        
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
        
        self._init_ui()
        
        # Configura um timer para atualização periódica
        self.update_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.update_timer)
        self.update_timer.Start(2000)  # Atualiza a cada 2 segundos
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel de cabeçalho com título e botão de atualizar
        header_panel = wx.Panel(self)
        header_panel.SetBackgroundColour(self.colors["bg_color"])
        header_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        title = wx.StaticText(header_panel, label="Fila de Impressão")
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        title.SetForegroundColour(self.colors["text_color"])
        
        # self.refresh_button = wx.Button(header_panel, label="Atualizar", size=(120, 36))

        self.refresh_button = create_styled_button(
            header_panel,
            "Atualizar",
            self.colors["accent_color"],
            self.colors["text_color"],
            wx.Colour(60, 60, 60),
            (120, 36)
        )
        self.refresh_button.Bind(wx.EVT_BUTTON, self.load_jobs)

        header_sizer.Add(title, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 20)
        header_sizer.AddStretchSpacer()
        header_sizer.Add(self.refresh_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 20)
        
        header_panel.SetSizer(header_sizer)
        
        # Descrição
        description_panel = wx.Panel(self)
        description_panel.SetBackgroundColour(self.colors["bg_color"])
        description_sizer = wx.BoxSizer(wx.VERTICAL)
        
        description = wx.StaticText(
            description_panel,
            label="Acompanhe e gerencie os trabalhos de impressão."
        )
        description.SetForegroundColour(self.colors["text_secondary"])
        description.SetFont(wx.Font(9, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        description_sizer.Add(description, 0, wx.LEFT | wx.BOTTOM, 20)
        description_panel.SetSizer(description_sizer)
        
        # Lista de trabalhos
        list_panel = wx.Panel(self)
        list_panel.SetBackgroundColour(self.colors["card_bg"])
        list_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Lista em formato de tabela com estilo customizado
        self.job_list = wx.ListCtrl(
            list_panel,
            style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SIMPLE
        )

        self.job_list.SetBackgroundColour(self.colors["card_bg"])
        self.job_list.SetForegroundColour(self.colors["text_color"])

        # Personaliza as cores das linhas
        self.job_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_list_item_focus)

        # Estiliza o cabeçalho da lista
        if hasattr(self.job_list, 'GetMainWindow'):
            main_window = self.job_list.GetMainWindow()
            if main_window:
                main_window.SetBackgroundColour(self.colors["panel_bg"])
        
        # Adiciona colunas
        self.job_list.InsertColumn(0, "ID", width=80)
        self.job_list.InsertColumn(1, "Documento", width=200)
        self.job_list.InsertColumn(2, "Impressora", width=150)
        self.job_list.InsertColumn(3, "Status", width=100)
        self.job_list.InsertColumn(4, "Progresso", width=100)
        self.job_list.InsertColumn(5, "Data", width=150)
        
        list_sizer.Add(self.job_list, 1, wx.EXPAND | wx.ALL, 10)
        
        # Painel de botões de ação
        action_panel = wx.Panel(list_panel)
        action_panel.SetBackgroundColour(self.colors["card_bg"])
        action_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para cancelar trabalho
        self.cancel_button = create_styled_button(
            action_panel, 
            "Cancelar Trabalho", 
            wx.Colour(220, 53, 69),
            self.colors["text_color"],
            wx.Colour(240, 73, 89),
            (150, 36)
        )
        self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel_job)
        self.cancel_button.Disable()  # Inicialmente desabilitado

        # Botão para ver detalhes
        self.details_button = create_styled_button(
            action_panel,
            "Ver Detalhes",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (150, 36)
        )
        self.details_button.Bind(wx.EVT_BUTTON, self.on_view_details)
        self.details_button.Disable()  # Inicialmente desabilitado
        
        action_sizer.Add(self.cancel_button, 0, wx.RIGHT, 10)
        action_sizer.Add(self.details_button, 0)
        
        action_panel.SetSizer(action_sizer)
        list_sizer.Add(action_panel, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        list_panel.SetSizer(list_sizer)
        
        # Painel para exibir mensagem de "sem trabalhos"
        self.empty_panel = wx.Panel(self)
        self.empty_panel.SetBackgroundColour(self.colors["bg_color"])
        empty_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Ícone de impressora vazia
        printer_icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 
                                      "ui", "resources", "printer.png")
        
        if os.path.exists(printer_icon_path):
            empty_icon = wx.StaticBitmap(
                self.empty_panel,
                bitmap=wx.Bitmap(printer_icon_path),
                size=(64, 64)
            )
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 50)
        
        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhum trabalho de impressão encontrado"
        )
        empty_text.SetForegroundColour(self.colors["text_secondary"])
        empty_text.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        
        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 20)
        self.empty_panel.SetSizer(empty_sizer)
        
        # Adiciona ao layout principal
        main_sizer.Add(header_panel, 0, wx.EXPAND | wx.BOTTOM, 20)
        main_sizer.Add(description_panel, 0, wx.EXPAND | wx.LEFT, 20)
        main_sizer.Add(list_panel, 1, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(self.empty_panel, 1, wx.EXPAND)
        
        self.SetSizer(main_sizer)
        
        # Bind do evento de seleção da lista
        self.job_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_job_selected)
        self.job_list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self.on_job_deselected)
        
        # Carrega os trabalhos
        self.load_jobs()
    
    def load_jobs(self, event=None):
        """Carrega a lista de trabalhos de impressão"""
        try:
            # Obtém o histórico de trabalhos
            job_history = self.print_queue_manager.get_job_history()
            
            # Converte para objetos PrintJob
            self.jobs = []
            for job_data in job_history:
                job = PrintJob.from_dict(job_data)
                self.jobs.append(job)
            
            # Limpa a lista
            self.job_list.DeleteAllItems()
            
            # Preenche com os trabalhos
            for i, job in enumerate(self.jobs):
                index = self.job_list.InsertItem(i, job.job_id[:8])
                
                # Documento
                self.job_list.SetItem(index, 1, job.document_name)
                
                # Impressora
                self.job_list.SetItem(index, 2, job.printer_name)
                
                # Status
                status_text = self._get_status_text(job.status)
                self.job_list.SetItem(index, 3, status_text)
                
                # Progresso
                if job.total_pages > 0:
                    progress_text = f"{job.completed_pages}/{job.total_pages}"
                else:
                    progress_text = "N/A"
                self.job_list.SetItem(index, 4, progress_text)
                
                # Data
                if job.completed_at:
                    date_text = job.completed_at.strftime("%d/%m/%Y %H:%M")
                elif job.started_at:
                    date_text = job.started_at.strftime("%d/%m/%Y %H:%M")
                elif job.created_at:
                    date_text = job.created_at.strftime("%d/%m/%Y %H:%M")
                else:
                    date_text = "Data desconhecida"

                self.job_list.SetItem(index, 5, date_text)
                
                # Define cores baseadas no status
                item_color = self._get_status_color(job.status)
                self.job_list.SetItemTextColour(index, item_color)
            
            # Exibe a mensagem de vazio se não houver trabalhos
            if not self.jobs:
                self.empty_panel.Show()
                self.job_list.GetParent().Hide()
            else:
                self.empty_panel.Hide()
                self.job_list.GetParent().Show()
            
            # Atualiza o layout
            self.Layout()
            
        except Exception as e:
            logger.error(f"Erro ao carregar trabalhos de impressão: {str(e)}")
            wx.MessageBox(
                f"Erro ao carregar trabalhos de impressão: {str(e)}",
                "Erro",
                wx.OK | wx.ICON_ERROR
            )
    
    def _on_list_item_focus(self, event):
        """Personaliza a cor de seleção dos itens da lista"""
        # Chama o handler original primeiro
        self.on_job_selected(event)
        
        # Personaliza cores de seleção
        selected_idx = event.GetIndex()
        if selected_idx >= 0:
            # Define cor de fundo para item selecionado
            self.job_list.SetItemBackgroundColour(selected_idx, wx.Colour(45, 45, 45))
            self.job_list.SetItemTextColour(selected_idx, self.colors["accent_color"])

    def _get_status_text(self, status):
        """Obtém o texto do status"""
        if status == PrintJobStatus.PENDING:
            return "Pendente"
        elif status == PrintJobStatus.PROCESSING:
            return "Processando"
        elif status == PrintJobStatus.COMPLETED:
            return "Concluído"
        elif status == PrintJobStatus.FAILED:
            return "Falha"
        elif status == PrintJobStatus.CANCELED:
            return "Cancelado"
        else:
            return "Desconhecido"
    
    def _get_status_color(self, status):
        """Obtém a cor baseada no status"""
        if status == PrintJobStatus.PENDING:
            return self.colors["text_secondary"]
        elif status == PrintJobStatus.PROCESSING:
            return self.colors["warning_color"]
        elif status == PrintJobStatus.COMPLETED:
            return self.colors["success_color"]
        elif status == PrintJobStatus.FAILED:
            return self.colors["error_color"]
        elif status == PrintJobStatus.CANCELED:
            return self.colors["text_secondary"]
        else:
            return self.colors["text_color"]
    
    def on_job_selected(self, event):
        """Manipula o evento de seleção de trabalho"""
        # Habilita os botões
        self.cancel_button.Enable()
        self.details_button.Enable()
    
    def on_job_deselected(self, event):
        """Manipula o evento de deseleção de trabalho"""
        # Desabilita os botões
        self.cancel_button.Disable()
        self.details_button.Disable()
    
    def on_cancel_job(self, event):
        """Manipula o evento de cancelar trabalho"""
        # Obtém o índice selecionado
        index = self.job_list.GetFirstSelected()
        if index == -1:
            return
        
        # Obtém o trabalho
        job = self.jobs[index]
        
        # Confirma o cancelamento
        dlg = wx.MessageDialog(
            self,
            f"Tem certeza que deseja cancelar o trabalho '{job.document_name}'?",
            "Confirmar Cancelamento",
            wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
        )
        
        if dlg.ShowModal() == wx.ID_YES:
            # Cancela o trabalho
            job.set_canceled()
            
            # Atualiza o histórico
            job_dict = job.to_dict()
            self.print_queue_manager._update_history(job_dict)
            
            # Atualiza a lista
            self.load_jobs()
        
        dlg.Destroy()
    
    def on_view_details(self, event):
        """Manipula o evento de ver detalhes"""
        # Obtém o índice selecionado
        index = self.job_list.GetFirstSelected()
        if index == -1:
            return
        
        # Obtém o trabalho
        job = self.jobs[index]
        
        # Exibe diálogo com detalhes
        details_dialog = PrintJobDetailsDialog(self, job)
        details_dialog.ShowModal()
        details_dialog.Destroy()
    
    def on_timer(self, event):
        """Manipula o evento do timer"""
        # Recarrega os trabalhos para atualizar o status
        self.load_jobs()

class PrintJobDetailsDialog(wx.Dialog):
    """Diálogo para exibir detalhes de um trabalho de impressão"""
    
    def __init__(self, parent, job):
        """
        Inicializa o diálogo de detalhes
        
        Args:
            parent: Janela pai
            job: Trabalho de impressão
        """
        super().__init__(
            parent,
            title="Detalhes do Trabalho de Impressão",
            size=(500, 500),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER
        )
        
        self.job = job
        
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
        
        # Card de informações básicas
        info_panel = wx.Panel(self.panel)
        info_panel.SetBackgroundColour(self.colors["card_bg"])
        info_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Título
        title = wx.StaticText(info_panel, label=f"Trabalho: {self.job.document_name}")
        title.SetForegroundColour(self.colors["text_color"])
        title.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        info_sizer.Add(title, 0, wx.ALL, 10)
        
        # Separador
        separator = wx.StaticLine(info_panel)
        info_sizer.Add(separator, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        
        # Status
        status_panel = wx.Panel(info_panel)
        status_panel.SetBackgroundColour(self.colors["card_bg"])
        status_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        status_label = wx.StaticText(status_panel, label="Status:")
        status_label.SetForegroundColour(self.colors["text_secondary"])
        
        status_text = self._get_status_text(self.job.status)
        status_value = wx.StaticText(status_panel, label=status_text)
        status_value.SetForegroundColour(self._get_status_color(self.job.status))
        status_value.SetFont(wx.Font(10, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        
        status_sizer.Add(status_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        status_sizer.Add(status_value, 0, wx.ALIGN_CENTER_VERTICAL)
        
        status_panel.SetSizer(status_sizer)
        info_sizer.Add(status_panel, 0, wx.ALL, 10)
        
        # Detalhes em grid
        details_grid = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=20)
        details_grid.AddGrowableCol(1, 1)
        
        # ID do trabalho
        job_id_label = wx.StaticText(info_panel, label="ID do trabalho:")
        job_id_label.SetForegroundColour(self.colors["text_secondary"])
        job_id_value = wx.StaticText(info_panel, label=self.job.job_id)
        job_id_value.SetForegroundColour(self.colors["text_color"])
        
        details_grid.Add(job_id_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_grid.Add(job_id_value, 0, wx.EXPAND)
        
        # Impressora
        printer_label = wx.StaticText(info_panel, label="Impressora:")
        printer_label.SetForegroundColour(self.colors["text_secondary"])
        printer_value = wx.StaticText(info_panel, label=self.job.printer_name)
        printer_value.SetForegroundColour(self.colors["text_color"])
        
        details_grid.Add(printer_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_grid.Add(printer_value, 0, wx.EXPAND)
        
        # IP da impressora
        ip_label = wx.StaticText(info_panel, label="IP da impressora:")
        ip_label.SetForegroundColour(self.colors["text_secondary"])
        ip_value = wx.StaticText(info_panel, label=self.job.printer_ip)
        ip_value.SetForegroundColour(self.colors["text_color"])
        
        details_grid.Add(ip_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_grid.Add(ip_value, 0, wx.EXPAND)
        
        # Progresso
        progress_label = wx.StaticText(info_panel, label="Progresso:")
        progress_label.SetForegroundColour(self.colors["text_secondary"])
        
        if self.job.total_pages > 0:
            progress_text = f"{self.job.completed_pages}/{self.job.total_pages} páginas ({self.job.get_progress_percentage()}%)"
        else:
            progress_text = "N/A"
            
        progress_value = wx.StaticText(info_panel, label=progress_text)
        progress_value.SetForegroundColour(self.colors["text_color"])
        
        details_grid.Add(progress_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_grid.Add(progress_value, 0, wx.EXPAND)
        
        # Data de criação
        created_label = wx.StaticText(info_panel, label="Data de criação:")
        created_label.SetForegroundColour(self.colors["text_secondary"])
        created_value = wx.StaticText(info_panel, label=self.job.created_at.strftime("%d/%m/%Y %H:%M:%S"))
        created_value.SetForegroundColour(self.colors["text_color"])
        
        details_grid.Add(created_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
        details_grid.Add(created_value, 0, wx.EXPAND)
        
        # Data de início
        if self.job.started_at:
            started_label = wx.StaticText(info_panel, label="Data de início:")
            started_label.SetForegroundColour(self.colors["text_secondary"])
            started_value = wx.StaticText(info_panel, label=self.job.started_at.strftime("%d/%m/%Y %H:%M:%S"))
            started_value.SetForegroundColour(self.colors["text_color"])
            
            details_grid.Add(started_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            details_grid.Add(started_value, 0, wx.EXPAND)
        
        # Data de conclusão
        if self.job.completed_at:
            completed_label = wx.StaticText(info_panel, label="Data de conclusão:")
            completed_label.SetForegroundColour(self.colors["text_secondary"])
            completed_value = wx.StaticText(info_panel, label=self.job.completed_at.strftime("%d/%m/%Y %H:%M:%S"))
            completed_value.SetForegroundColour(self.colors["text_color"])
            
            details_grid.Add(completed_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            details_grid.Add(completed_value, 0, wx.EXPAND)
        
        # Tempo decorrido
        if self.job.started_at:
            elapsed_label = wx.StaticText(info_panel, label="Tempo decorrido:")
            elapsed_label.SetForegroundColour(self.colors["text_secondary"])
            elapsed_value = wx.StaticText(info_panel, label=self.job.get_formatted_elapsed_time())
            elapsed_value.SetForegroundColour(self.colors["text_color"])
            
            details_grid.Add(elapsed_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
            details_grid.Add(elapsed_value, 0, wx.EXPAND)
        
        # Mensagem de erro
        if self.job.error_message:
            error_label = wx.StaticText(info_panel, label="Erro:")
            error_label.SetForegroundColour(self.colors["text_secondary"])
            error_value = wx.StaticText(info_panel, label=self.job.error_message)
            error_value.SetForegroundColour(self.colors["error_color"])
            error_value.Wrap(300)  # Quebra linhas longas
            
            details_grid.Add(error_label, 0, wx.ALIGN_RIGHT | wx.TOP)
            details_grid.Add(error_value, 0, wx.EXPAND)
        
        info_sizer.Add(details_grid, 0, wx.EXPAND | wx.ALL, 10)
        
        # Opções de impressão
        if self.job.options:
            # Separador
            separator2 = wx.StaticLine(info_panel)
            info_sizer.Add(separator2, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
            
            # Título da seção
            options_title = wx.StaticText(info_panel, label="Opções de Impressão")
            options_title.SetForegroundColour(self.colors["text_color"])
            options_title.SetFont(wx.Font(12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
            info_sizer.Add(options_title, 0, wx.ALL, 10)
            
            # Grid de opções
            options_grid = wx.FlexGridSizer(rows=0, cols=2, vgap=10, hgap=20)
            options_grid.AddGrowableCol(1, 1)
            
            for key, value in self.job.options.items():
                # Ignora valores None
                if value is None:
                    continue
                    
                # Formata o nome da opção
                option_name = key.replace("_", " ").title()
                
                option_label = wx.StaticText(info_panel, label=f"{option_name}:")
                option_label.SetForegroundColour(self.colors["text_secondary"])
                
                # Formata o valor dependendo do tipo
                if isinstance(value, dict):
                    value_str = ", ".join(f"{k}: {v}" for k, v in value.items())
                elif isinstance(value, list):
                    value_str = ", ".join(str(v) for v in value)
                else:
                    value_str = str(value)
                
                option_value = wx.StaticText(info_panel, label=value_str)
                option_value.SetForegroundColour(self.colors["text_color"])
                
                options_grid.Add(option_label, 0, wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL)
                options_grid.Add(option_value, 0, wx.EXPAND)
            
            info_sizer.Add(options_grid, 0, wx.EXPAND | wx.ALL, 10)
        
        info_panel.SetSizer(info_sizer)
        
        # Adiciona borda arredondada ao card
        def on_info_paint(event):
            dc = wx.BufferedPaintDC(info_panel)
            gc = wx.GraphicsContext.Create(dc)
            
            rect = info_panel.GetClientRect()
            
            # Desenha o fundo com cantos arredondados
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 10)
            
            gc.SetBrush(wx.Brush(self.colors["card_bg"]))
            gc.SetPen(wx.Pen(self.colors["border_color"], 1))
            
            gc.DrawPath(path)
            
            # Redesenha os filhos
            for child in info_panel.GetChildren():
                child.Refresh()
        
        info_panel.Bind(wx.EVT_PAINT, on_info_paint)
        info_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
        
        main_sizer.Add(info_panel, 1, wx.EXPAND | wx.ALL, 10)
        
        # Botões
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        
        # Botão para fechar
        close_button = create_styled_button(
            self.panel,
            "Fechar",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (-1, 36)
        )
        close_button.SetId(wx.ID_CLOSE)
        close_button.Bind(wx.EVT_BUTTON, lambda evt: self.EndModal(wx.ID_CLOSE))

        button_sizer.Add(close_button, 0)

        main_sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
        
        self.panel.SetSizer(main_sizer)
    
    def _get_status_text(self, status):
        """Obtém o texto do status"""
        if status == PrintJobStatus.PENDING:
            return "Pendente"
        elif status == PrintJobStatus.PROCESSING:
            return "Processando"
        elif status == PrintJobStatus.COMPLETED:
            return "Concluído"
        elif status == PrintJobStatus.FAILED:
            return "Falha"
        elif status == PrintJobStatus.CANCELED:
            return "Cancelado"
        else:
            return "Desconhecido"
    
    def _get_status_color(self, status):
        """Obtém a cor baseada no status"""
        if status == PrintJobStatus.PENDING:
            return self.colors["text_secondary"]
        elif status == PrintJobStatus.PROCESSING:
            return self.colors["warning_color"]
        elif status == PrintJobStatus.COMPLETED:
            return self.colors["success_color"]
        elif status == PrintJobStatus.FAILED:
            return self.colors["error_color"]
        elif status == PrintJobStatus.CANCELED:
            return self.colors["text_secondary"]
        else:
            return self.colors["text_color"]
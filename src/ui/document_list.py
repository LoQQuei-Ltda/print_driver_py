#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Componente de listagem de documentos moderno
"""

import logging
import os
import wx
import datetime
from src.api.client import APIError
from src.utils.resource_manager import ResourceManager
from src.ui.print_dialog import select_printer_and_print
from src.ui.custom_button import create_styled_button

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
        self._adjust_document_name()
        wx.CallLater(100, self._adjust_document_name)
    
    def _on_size(self, event):
        """Manipula eventos de redimensionamento"""
        if not self._is_destroyed:
            # Chama imediatamente E agenda para depois garantir que seja aplicado
            self._adjust_document_name()
            wx.CallLater(50, self._adjust_document_name)
        event.Skip()

    def _adjust_document_name(self):
        """Ajusta o nome do documento baseado no tamanho disponível - VERSÃO CORRIGIDA PARA MACOS"""
        if self._is_destroyed or not self.doc_name_widget:
            return
            
        try:
            # CORREÇÃO MACOS: Verifica se o widget ainda existe
            if not self.doc_name_widget or not self.doc_name_widget.GetParent():
                return
                
            # Calcula a largura disponível
            total_width = self.GetSize().width
            if total_width <= 0:
                # Tenta obter tamanho do parent se o próprio widget ainda não tem tamanho definido
                if self.GetParent():
                    parent_size = self.GetParent().GetSize()
                    total_width = parent_size.width - 40  # 40px para margens
                if total_width <= 0:
                    total_width = 400  # Valor padrão se ainda não conseguir determinar
                
            # Subtrai: ícone (52px) + botões (200px) + margens (40px)
            available_width = max(150, total_width - 292)
            
            # Função de truncamento
            def truncate_text(text, max_width, font):
                if max_width <= 0:
                    return text
                    
                # CORREÇÃO MACOS: Cria bitmap temporário menor
                bmp = wx.Bitmap(10, 10)
                dc = wx.MemoryDC(bmp)
                dc.SetFont(font)
                
                try:
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
                finally:
                    # CORREÇÃO MACOS: Garante limpeza do DC
                    dc.SelectObject(wx.NullBitmap)
            
            # Aplica o truncamento
            truncated_name = truncate_text(self.document.name, available_width, self.name_font)
            
            # Atualiza apenas se necessário
            current_label = self.doc_name_widget.GetLabel()
            if current_label != truncated_name:
                self.doc_name_widget.SetLabel(truncated_name)
                # CORREÇÃO MACOS: Força layout do painel info
                if self.info_panel and not getattr(self.info_panel, '_is_destroyed', False):
                    self.info_panel.Layout()
                    
        except RuntimeError:
            # Widget foi destruído durante a execução
            self._is_destroyed = True
        except Exception as e:
            logger.debug(f"Erro ao ajustar nome do documento: {str(e)}")
    
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
        # Define cor de hover baseada na cor principal
        if color == wx.Colour(255, 90, 36):  # Laranja
            hover_color = wx.Colour(255, 120, 70)
        else:
            hover_color = wx.Colour(80, 80, 80)
        
        button = create_styled_button(
            parent, 
            label, 
            color, 
            wx.WHITE, 
            hover_color, 
            (90, 36)
        )
        button.Bind(wx.EVT_BUTTON, handler)
        
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
        
        self.refresh_button = create_styled_button(
            header_panel,
            "Atualizar",
            wx.Colour(60, 60, 60),
            self.colors["text_color"],
            wx.Colour(80, 80, 80),
            (120, 36)
        )
        self.refresh_button.Bind(wx.EVT_BUTTON, self.load_documents)
        
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
        """Limpa cards existentes de forma mais robusta"""
        try:
            # Marca todos como destruídos primeiro
            for card in self.document_cards:
                if card:
                    card._is_destroyed = True
            
            # Limpa lista
            self.document_cards.clear()
            
            # Remove widgets do painel
            children_to_remove = []
            for child in self.content_panel.GetChildren():
                if isinstance(child, DocumentCardPanel):
                    children_to_remove.append(child)
            
            for child in children_to_remove:
                try:
                    child.Destroy()
                except:
                    pass
            
            # Força layout após remoção
            self.content_panel.Layout()
            
            logger.debug("Cards existentes limpos com sucesso")
            
        except Exception as e:
            logger.error(f"Erro ao limpar cards: {str(e)}")

    def _adjust_all_cards_safe(self):
        """Ajusta todos os cards com verificações de segurança"""
        try:
            for i, card in enumerate(self.document_cards):
                try:
                    if (card and 
                        hasattr(card, '_adjust_document_name') and 
                        not getattr(card, '_is_destroyed', False)):
                        card._adjust_document_name()
                except RuntimeError:
                    logger.debug(f"Card {i} foi destruído durante ajuste")
                except Exception as e:
                    logger.debug(f"Erro ao ajustar card {i}: {str(e)}")
            
            # Agenda ajustes adicionais
            wx.CallLater(100, self._final_adjustment)
            wx.CallLater(250, self._final_adjustment)
            
        except Exception as e:
            logger.debug(f"Erro em _adjust_all_cards_safe: {str(e)}")

    def _final_adjustment(self):
        """Ajuste final dos cards"""
        try:
            if not getattr(self, '_is_destroyed', False):
                for card in self.document_cards:
                    if (card and 
                        hasattr(card, '_adjust_document_name') and 
                        not getattr(card, '_is_destroyed', False)):
                        try:
                            card._adjust_document_name()
                        except:
                            pass
                self.Refresh()
        except:
            pass
    
    def _adjust_all_cards_final(self):
        """Ajuste final de todos os cards"""
        try:
            count = 0
            for card in self.document_cards:
                try:
                    if (card and hasattr(card, '_adjust_document_name') and 
                        not getattr(card, '_is_destroyed', False)):
                        card._adjust_document_name()
                        count += 1
                except Exception as e:
                    logger.debug(f"Erro ao ajustar card: {str(e)}")
            
            logger.info(f"Ajustados {count} cards de {len(self.document_cards)}")
            
            # Refresh final
            self.Refresh()
            
        except Exception as e:
            logger.debug(f"Erro no ajuste final: {str(e)}")

    def load_documents(self, event=None):
        """Carrega documentos - VERSÃO SIMPLIFICADA E ROBUSTA"""
        try:
            logger.info("=== INICIANDO CARREGAMENTO DE DOCUMENTOS ===")
            
            # Limpa interface atual
            self._clear_existing_cards()
            
            # Mostra indicador de carregamento
            loading_text = wx.StaticText(self.content_panel, label="Carregando documentos...")
            loading_text.SetForegroundColour(self.colors["text_color"])
            self.content_sizer.Insert(0, loading_text, 0, wx.ALIGN_CENTER | wx.ALL, 20)
            self.content_panel.Layout()
            self.Update()

            # FORÇA refresh do file monitor
            app = wx.GetApp()
            self.documents = []
            
            if hasattr(app, 'main_screen') and hasattr(app.main_screen, 'file_monitor'):
                file_monitor = app.main_screen.file_monitor
                
                # FORÇA refresh completo
                file_monitor.force_refresh_documents()
                self.documents = file_monitor.get_documents()
                
                logger.info(f"Documentos carregados do monitor principal: {len(self.documents)}")
            else:
                # Fallback: cria monitor temporário
                from src.utils.file_monitor import FileMonitor
                file_monitor = FileMonitor(app.config)
                file_monitor._load_initial_documents()
                self.documents = file_monitor.get_documents()
                logger.info(f"Documentos carregados de monitor temporário: {len(self.documents)}")

            # Remove loading
            loading_text.Destroy()

            # Constrói interface
            if self.documents:
                logger.info(f"Construindo interface para {len(self.documents)} documentos")
                self.empty_panel.Hide()
                
                for i, doc in enumerate(self.documents):
                    try:
                        card = DocumentCardPanel(self.content_panel, doc, self.on_print, self.on_delete)
                        self.document_cards.append(card)
                        self.content_sizer.Add(card, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
                        logger.debug(f"Card {i+1}/{len(self.documents)} criado: {doc.name}")
                    except Exception as e:
                        logger.error(f"Erro ao criar card {i+1}: {str(e)}")
            else:
                logger.info("Nenhum documento encontrado - exibindo painel vazio")
                self.empty_panel.Show()
            
            # Finaliza layout
            self.content_panel.Layout()
            self.Layout()
            self.FitInside()
            self.Refresh()
            
            # Ajusta cards após um delay
            wx.CallLater(100, self._adjust_all_cards_final)
            
            logger.info(f"=== CARREGAMENTO CONCLUÍDO: {len(self.documents)} documentos ===")

        except Exception as e:
            logger.error(f"ERRO CRÍTICO no carregamento: {str(e)}")
            import traceback
            logger.error(f"Traceback completo:\n{traceback.format_exc()}")
            
            # Cleanup
            try:
                loading_text.Destroy()
            except:
                pass
            
            # Mostra erro
            error_text = wx.StaticText(self.content_panel, label=f"Erro ao carregar: {str(e)}")
            error_text.SetForegroundColour(wx.Colour(220, 53, 69))
            self.content_sizer.Add(error_text, 0, wx.ALIGN_CENTER | wx.ALL, 20)
            self.content_panel.Layout()
            
    def _force_adjust_all_cards(self):
        """Força o ajuste de nomes em todos os cards após o layout estar completo - VERSÃO CORRIGIDA PARA MACOS"""
        try:
            for card in self.document_cards:
                if (hasattr(card, '_adjust_document_name') and 
                    not getattr(card, '_is_destroyed', False) and 
                    card):
                    try:
                        card._adjust_document_name()
                    except RuntimeError:
                        # Card foi destruído durante a execução
                        pass
            
            # CORREÇÃO MACOS: Força refresh final
            if not getattr(self, '_is_destroyed', False):
                self.Refresh()
                
        except Exception as e:
            logger.debug(f"Erro ao ajustar cards: {str(e)}")


#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Componente de listagem de impressoras
"""

import os
import wx
import logging
from src.models.printer import Printer

logger = logging.getLogger("PrintManagementSystem.UI.PrinterList")

class PrinterListPanel(wx.Panel):
    """Painel para listagem de impressoras"""
    
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
        # Chama o construtor da classe pai com apenas os argumentos que ele espera
        wx.Panel.__init__(
            self,
            parent,
            id=wx.ID_ANY,
            pos=wx.DefaultPosition,
            style=wx.TAB_TRAVERSAL
        )
        
        # Inicializa os atributos da classe
        self.theme_manager = theme_manager
        self.config = config
        self.api_client = api_client
        self.on_update = on_update
        
        self.printers = []
        
        self.colors = self.theme_manager.get_theme_colors()
        
        self._init_ui()
    
    def _init_ui(self):
        """Inicializa a interface do usuário"""
        self.SetBackgroundColour(self.colors["panel_bg"])
        
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        
        # Painel superior com botão de atualização
        top_panel = wx.Panel(self)
        top_panel.SetBackgroundColour(self.colors["panel_bg"])
        top_sizer = wx.BoxSizer(wx.HORIZONTAL)
                
        top_panel.SetSizer(top_sizer)
        
        # Lista de impressoras
        self.printer_list = wx.ListCtrl(
            self,
            style=wx.LC_REPORT | wx.BORDER_NONE
        )
        
        self.printer_list.InsertColumn(0, "Nome", width=200)
        self.printer_list.InsertColumn(1, "Status", width=100)
        self.printer_list.InsertColumn(2, "Local", width=150)
        self.printer_list.InsertColumn(3, "Endereço", width=150)
        
        self.printer_list.SetBackgroundColour(self.colors["panel_bg"])
        self.printer_list.SetForegroundColour(self.colors["text_color"])
        
        # Painel para quando não há impressoras
        self.empty_panel = wx.Panel(self)
        self.empty_panel.SetBackgroundColour(self.colors["panel_bg"])
        empty_sizer = wx.BoxSizer(wx.VERTICAL)
        
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
            empty_sizer.Add(empty_icon, 0, wx.ALIGN_CENTER | wx.TOP, 30)
        
        empty_text = wx.StaticText(
            self.empty_panel,
            label="Nenhuma impressora encontrada"
        )
        empty_text.SetForegroundColour(self.colors["text_secondary"])
        empty_text.SetFont(wx.Font(
            12, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL
        ))
        
        empty_sizer.Add(empty_text, 0, wx.ALIGN_CENTER | wx.TOP, 15)
        
        self.empty_panel.SetSizer(empty_sizer)
        
        main_sizer.Add(top_panel, 0, wx.EXPAND)
        main_sizer.Add(self.printer_list, 1, wx.EXPAND)
        main_sizer.Add(self.empty_panel, 1, wx.EXPAND)
        
        self.SetSizer(main_sizer)
        
        self.empty_panel.Hide()
        
        self.load_printers()
    
    def load_printers(self):
        """Carrega as impressoras da configuração"""
        try:
            self.printer_list.DeleteAllItems()
            
            printers_data = self.config.get_printers()
            
            if printers_data and len(printers_data) > 0:
                self.printers = printers_data
                
                for i, printer in enumerate(self.printers):
                    name = str(printer.get("name", "Sem nome") or "Sem nome")
                    status = str(printer.get("status", "Desconhecido") or "Desconhecido")
                    location = str(printer.get("location", "") or "")
                    
                    ip = printer.get("ip_address")
                    mac = printer.get("mac_address")
                    address = ""
                    if ip:
                        address = str(ip)
                    elif mac:
                        address = str(mac)
                    
                    index = self.printer_list.InsertItem(i, name)
                    
                    self.printer_list.SetItem(index, 1, status)
                    self.printer_list.SetItem(index, 2, location)
                    self.printer_list.SetItem(index, 3, address)
                
                self.printer_list.Show()
                self.empty_panel.Hide()
            else:
                self.printers = []
                self.printer_list.Hide()
                self.empty_panel.Show()
            
            self.Layout()
            
        except Exception as e:
            logger.error(f"Erro ao carregar impressoras: {str(e)}")
            self.printer_list.DeleteAllItems()
            self.printer_list.Hide()
            self.empty_panel.Show()
    
    def on_update_printers(self, event=None):
        """Atualiza impressoras com o servidor principal"""
        if hasattr(self, 'printer_list_panel'):
            self.printer_list_panel.on_update_printers(event)
        else:
            try:
                busy = wx.BusyInfo("Atualizando impressoras. Aguarde...", parent=self)
                wx.GetApp().Yield()
                
                printers_data = self.api_client.get_printers()
                
                printers = []
                for printer_data in printers_data:
                    printer = Printer(printer_data)
                    
                    if printer.name is None:
                        printer.name = "Sem nome"
                    if printer.mac_address is None:
                        printer.mac_address = ""
                        
                    printer_dict = printer.to_dict()
                    for key in printer_dict:
                        if printer_dict[key] is None:
                            printer_dict[key] = ""
                    
                    printers.append(printer_dict)
                
                self.config.set_printers(printers)
                
                self.printers = printers
                
                del busy
                
                wx.MessageBox(f"{len(self.printers)} impressoras atualizadas com sucesso!", 
                            "Informação", wx.OK | wx.ICON_INFORMATION)
            except Exception as e:
                logger.error(f"Erro ao atualizar impressoras: {str(e)}")
                wx.MessageBox(f"Erro ao atualizar impressoras: {str(e)}", 
                            "Erro", wx.OK | wx.ICON_ERROR)

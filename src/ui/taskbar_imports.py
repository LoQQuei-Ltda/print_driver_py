#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Garantir que os imports para o ícone da bandeja estejam corretos
"""

try:
    # Verifica se o módulo wx.adv está disponível
    import wx.adv
    TaskBarIcon = wx.adv.TaskBarIcon
    EVT_TASKBAR_LEFT_DCLICK = wx.adv.EVT_TASKBAR_LEFT_DCLICK
except ImportError:
    # Fallback para versões mais antigas do wxPython
    try:
        import wx
        TaskBarIcon = wx.TaskBarIcon
        EVT_TASKBAR_LEFT_DCLICK = wx.EVT_TASKBAR_LEFT_DCLICK
    except (ImportError, AttributeError):
        # Se não conseguir importar, define como None para evitar erros
        TaskBarIcon = None
        EVT_TASKBAR_LEFT_DCLICK = None
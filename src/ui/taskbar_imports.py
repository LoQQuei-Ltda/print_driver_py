#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Garantir que os imports para o ícone da bandeja estejam corretos
"""

import logging

logger = logging.getLogger("PrintManagementSystem.UI.TaskBarImports")

# Inicializa as variáveis
TaskBarIcon = None
EVT_TASKBAR_LEFT_DCLICK = None

try:
    # Primeiro tenta a abordagem moderna (wxPython 4.x)
    import wx.adv
    TaskBarIcon = wx.adv.TaskBarIcon
    EVT_TASKBAR_LEFT_DCLICK = wx.adv.EVT_TASKBAR_LEFT_DCLICK
    logger.debug("TaskBarIcon importado de wx.adv (wxPython 4.x)")
    
except ImportError:
    # Fallback para versões mais antigas do wxPython (3.x)
    try:
        import wx
        if hasattr(wx, 'TaskBarIcon'):
            TaskBarIcon = wx.TaskBarIcon
            logger.debug("TaskBarIcon importado de wx (wxPython 3.x)")
        else:
            logger.warning("wx.TaskBarIcon não encontrado")
            
        if hasattr(wx, 'EVT_TASKBAR_LEFT_DCLICK'):
            EVT_TASKBAR_LEFT_DCLICK = wx.EVT_TASKBAR_LEFT_DCLICK
            logger.debug("EVT_TASKBAR_LEFT_DCLICK importado de wx")
        else:
            logger.warning("wx.EVT_TASKBAR_LEFT_DCLICK não encontrado")
            
    except (ImportError, AttributeError) as e:
        logger.error(f"Erro ao importar TaskBarIcon: {str(e)}")
        # Se não conseguir importar, define como None para evitar erros
        TaskBarIcon = None
        EVT_TASKBAR_LEFT_DCLICK = None

# Verificação final e log
if TaskBarIcon is None:
    logger.warning("TaskBarIcon não está disponível - funcionalidade da bandeja será desabilitada")
else:
    logger.info("TaskBarIcon importado com sucesso")

if EVT_TASKBAR_LEFT_DCLICK is None:
    logger.warning("EVT_TASKBAR_LEFT_DCLICK não está disponível - duplo clique na bandeja será desabilitado")
else:
    logger.debug("EVT_TASKBAR_LEFT_DCLICK importado com sucesso")
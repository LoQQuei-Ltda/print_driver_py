import wx

def create_styled_button(parent, label, bg_color, text_color, hover_color, size=(-1, -1)):
    """
    Cria um botão com estilo personalizado e hover suave
    
    Args:
        parent: Widget pai
        label: Texto do botão
        bg_color: Cor de fundo normal
        text_color: Cor do texto
        hover_color: Cor de hover
        size: Tamanho do botão
    
    Returns:
        wx.Button: Botão estilizado
    """
    button = wx.Button(parent, label=label, size=size, style=wx.BORDER_NONE)
    button.SetBackgroundColour(bg_color)
    button.SetForegroundColour(text_color)
    
    # Eventos de hover mais suaves
    def on_enter(evt):
        button.SetBackgroundColour(hover_color)
        button.Refresh()
    
    def on_leave(evt):
        button.SetBackgroundColour(bg_color)
        button.Refresh()
    
    # Custom paint para bordas arredondadas
    def on_paint(evt):
        dc = wx.BufferedPaintDC(button)
        dc.SetBackground(wx.Brush(parent.GetBackgroundColour()))
        dc.Clear()
        
        rect = button.GetClientRect()
        
        # Desenha fundo com bordas arredondadas
        gc = wx.GraphicsContext.Create(dc)
        if gc:
            path = gc.CreatePath()
            path.AddRoundedRectangle(0, 0, rect.width, rect.height, 6)
            
            gc.SetBrush(wx.Brush(button.GetBackgroundColour()))
            gc.SetPen(wx.Pen(button.GetBackgroundColour(), 1))
            gc.DrawPath(path)
            
            # Desenha o texto centralizado
            dc.SetFont(button.GetFont())
            dc.SetTextForeground(button.GetForegroundColour())
            
            text = button.GetLabel()
            text_width, text_height = dc.GetTextExtent(text)
            
            x = (rect.width - text_width) // 2
            y = (rect.height - text_height) // 2
            dc.DrawText(text, x, y)
    
    button.Bind(wx.EVT_ENTER_WINDOW, on_enter)
    button.Bind(wx.EVT_LEAVE_WINDOW, on_leave)
    button.Bind(wx.EVT_PAINT, on_paint)
    button.Bind(wx.EVT_ERASE_BACKGROUND, lambda evt: None)
    
    return button
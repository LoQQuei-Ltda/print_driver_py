import wx
from src.utils.theme import ThemeManager

def test_dark_theme_colors():
    # Expected colors for the dark theme
    expected_colors = {
        "bg_color": wx.Colour(25, 25, 25),
        "panel_bg": wx.Colour(35, 35, 35),
        "input_bg": wx.Colour(45, 45, 45),
        "text_color": wx.Colour(240, 240, 240),
        "text_secondary": wx.Colour(200, 200, 200),
        "accent_color": wx.Colour(255, 90, 36),
        "accent_hover": wx.Colour(255, 120, 70),
        "border_color": wx.Colour(60, 60, 60),
        "icon_color": wx.Colour(200, 200, 200),
        "btn_text": wx.Colour(255, 255, 255),
        "success_color": wx.Colour(40, 167, 69),
    }

    # Check that the expected keys and values are in DARK_THEME
    for key, value in expected_colors.items():
        assert ThemeManager.DARK_THEME[key] == value
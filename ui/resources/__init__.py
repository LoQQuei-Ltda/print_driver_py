"""
Este arquivo garante que o diretório de recursos exista
e cria um ícone básico para a aplicação
"""
import os
from pathlib import Path
import base64

# Criar diretório resources se não existir
resources_dir = Path(__file__).parent
if not resources_dir.exists():
    resources_dir.mkdir(parents=True, exist_ok=True)

# Ícone básico para a aplicação (um ícone SVG simples representando uma impressora)
icon_svg = """
<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="6 9 6 2 18 2 18 9"></polyline>
  <path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"></path>
  <rect x="6" y="14" width="12" height="8"></rect>
</svg>
"""

# Salvar ícone SVG
icon_path = resources_dir / "icon.svg"
if not icon_path.exists():
    with open(icon_path, 'w') as f:
        f.write(icon_svg)

# PNG básico para ícone da aplicação
# Criar ícone PNG a partir do SVG usando base64 (ícone simples incorporado)
icon_png_base64 = """
iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAAACXBIWXMAAAsTAAALEwEAmpwYAAAFUmlUWHRYTUw6Y29tLmFkb2JlLnhtcAAAAAAAPD94cGFja2V0IGJlZ2luPSLvu78iIGlkPSJXNU0wTXBDZWhpSHpyZVN6TlRjemtjOWQiPz4gPHg6eG1wbWV0YSB4bWxuczp4PSJhZG9iZTpuczptZXRhLyIgeDp4bXB0az0iQWRvYmUgWE1QIENvcmUgNS42LWMxNDIgNzkuMTYwOTI0LCAyMDE3LzA3LzEzLTAxOjA2OjM5ICAgICAgICAiPiA8cmRmOlJERiB4bWxuczpyZGY9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkvMDIvMjItcmRmLXN5bnRheC1ucyMiPiA8cmRmOkRlc2NyaXB0aW9uIHJkZjphYm91dD0iIiB4bWxuczp4bXA9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC8iIHhtbG5zOmRjPSJodHRwOi8vcHVybC5vcmcvZGMvZWxlbWVudHMvMS4xLyIgeG1sbnM6cGhvdG9zaG9wPSJodHRwOi8vbnMuYWRvYmUuY29tL3Bob3Rvc2hvcC8xLjAvIiB4bWxuczp4bXBNTT0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL21tLyIgeG1sbnM6c3RFdnQ9Imh0dHA6Ly9ucy5hZG9iZS5jb20veGFwLzEuMC9zVHlwZS9SZXNvdXJjZUV2ZW50IyIgeG1wOkNyZWF0b3JUb29sPSJBZG9iZSBQaG90b3Nob3AgQ0MgKFdpbmRvd3MpIiB4bXA6Q3JlYXRlRGF0ZT0iMjAyMy0wNS0wMVQxMjo0OTozMSswMzowMCIgeG1wOk1vZGlmeURhdGU9IjIwMjMtMDUtMDFUMTI6NTA6MTErMDM6MDAiIHhtcDpNZXRhZGF0YURhdGU9IjIwMjMtMDUtMDFUMTI6NTA6MTErMDM6MDAiIGRjOmZvcm1hdD0iaW1hZ2UvcG5nIiBwaG90b3Nob3A6Q29sb3JNb2RlPSIzIiBwaG90b3Nob3A6SUNDUHJvZmlsZT0ic1JHQiBJRUM2MTk2Ni0yLjEiIHhtcE1NOkluc3RhbmNlSUQ9InhtcC5paWQ6MDA0OTI1NTM5NmI4MTFlZDlh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
"""

# Salvar ícone PNG
icon_png_path = resources_dir / "icon.png"
if not icon_png_path.exists():
    try:
        # Remover cabeçalhos e quebras de linha da string base64
        cleaned_base64 = icon_png_base64.strip().replace('\n', '')
        png_data = base64.b64decode(cleaned_base64)
        
        with open(icon_png_path, 'wb') as f:
            f.write(png_data)
    except Exception as e:
        print(f"Erro ao criar ícone PNG: {e}")
        # Criar um arquivo vazio como fallback
        with open(icon_png_path, 'wb') as f:
            f.write(b'')
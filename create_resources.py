#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para criar ícones e recursos visuais necessários para a aplicação
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

def create_resources_directory():
    """Cria o diretório de recursos se não existir"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    resources_dir = os.path.join(base_dir, "src", "ui", "resources")
    
    if not os.path.exists(resources_dir):
        os.makedirs(resources_dir)
        print(f"Diretório de recursos criado: {resources_dir}")
    
    return resources_dir

def create_icon(resources_dir, filename, size=(32, 32), color=(255, 90, 36)):
    """
    Cria um ícone simples
    
    Args:
        resources_dir (str): Diretório para salvar o ícone
        filename (str): Nome do arquivo de ícone
        size (tuple): Tamanho do ícone (largura, altura)
        color (tuple): Cor RGB do ícone
    """
    icon_path = os.path.join(resources_dir, filename)
    
    # Verifica se o ícone já existe
    if os.path.exists(icon_path):
        print(f"Ícone já existe: {icon_path}")
        return
    
    # Cria uma imagem com fundo transparente
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Desenha um círculo no centro da imagem
    center = (size[0] // 2, size[1] // 2)
    radius = min(size) // 2 - 2
    draw.ellipse(
        [
            (center[0] - radius, center[1] - radius),
            (center[0] + radius, center[1] + radius)
        ],
        fill=color
    )
    
    # Salva a imagem
    if filename.endswith(".ico"):
        # Salva como ícone
        image.save(icon_path, format="ICO")
    else:
        # Salva como PNG
        image.save(icon_path, format="PNG")
    
    print(f"Ícone criado: {icon_path}")

def create_document_icon(resources_dir, filename="document.png", size=(32, 32)):
    """
    Cria um ícone de documento
    
    Args:
        resources_dir (str): Diretório para salvar o ícone
        filename (str): Nome do arquivo de ícone
        size (tuple): Tamanho do ícone (largura, altura)
    """
    icon_path = os.path.join(resources_dir, filename)
    
    # Verifica se o ícone já existe
    if os.path.exists(icon_path):
        print(f"Ícone já existe: {icon_path}")
        return
    
    # Cria uma imagem com fundo transparente
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Desenha um documento
    margin = 4
    doc_width = size[0] - 2 * margin
    doc_height = size[1] - 2 * margin
    color = (200, 200, 200)
    
    # Forma básica do documento
    draw.rectangle(
        [
            (margin, margin),
            (margin + doc_width, margin + doc_height)
        ],
        fill=color
    )
    
    # Linhas horizontais para simular texto
    line_color = (150, 150, 150)
    line_margin = 6
    line_height = 2
    line_spacing = 4
    
    for y in range(line_margin, size[1] - line_margin, line_height + line_spacing):
        draw.rectangle(
            [
                (line_margin, y),
                (size[0] - line_margin, y + line_height)
            ],
            fill=line_color
        )
    
    # Salva a imagem
    image.save(icon_path, format="PNG")
    print(f"Ícone de documento criado: {icon_path}")

def create_empty_document_icon(resources_dir, filename="empty_document.png", size=(64, 64)):
    """
    Cria um ícone de documento vazio
    
    Args:
        resources_dir (str): Diretório para salvar o ícone
        filename (str): Nome do arquivo de ícone
        size (tuple): Tamanho do ícone (largura, altura)
    """
    icon_path = os.path.join(resources_dir, filename)
    
    # Verifica se o ícone já existe
    if os.path.exists(icon_path):
        print(f"Ícone já existe: {icon_path}")
        return
    
    # Cria uma imagem com fundo transparente
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Desenha um documento
    margin = 8
    doc_width = size[0] - 2 * margin
    doc_height = size[1] - 2 * margin
    color = (150, 150, 150, 100)  # Cinza semitransparente
    
    # Forma básica do documento
    draw.rectangle(
        [
            (margin, margin),
            (margin + doc_width, margin + doc_height)
        ],
        fill=color,
        outline=(120, 120, 120, 150),
        width=2
    )
    
    # Salva a imagem
    image.save(icon_path, format="PNG")
    print(f"Ícone de documento vazio criado: {icon_path}")

def create_system_icon(resources_dir, filename="system.png", size=(32, 32)):
    """
    Cria um ícone de sistema (engrenagem)
    
    Args:
        resources_dir (str): Diretório para salvar o ícone
        filename (str): Nome do arquivo de ícone
        size (tuple): Tamanho do ícone (largura, altura)
    """
    icon_path = os.path.join(resources_dir, filename)
    
    # Verifica se o ícone já existe
    if os.path.exists(icon_path):
        print(f"Ícone já existe: {icon_path}")
        return
    
    # Cria uma imagem com fundo transparente
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    
    # Desenha uma engrenagem simplificada
    center = (size[0] // 2, size[1] // 2)
    outer_radius = min(size) // 2 - 2
    inner_radius = outer_radius * 0.6
    color = (200, 200, 200)
    
    # Desenha o círculo central
    draw.ellipse(
        [
            (center[0] - inner_radius, center[1] - inner_radius),
            (center[0] + inner_radius, center[1] + inner_radius)
        ],
        fill=color
    )
    
    # Desenha 8 "dentes" ao redor
    import math
    num_teeth = 8
    tooth_width = math.pi / 16
    
    for i in range(num_teeth):
        angle = 2 * math.pi * i / num_teeth
        
        # Calcula pontos para um "dente"
        x1 = center[0] + inner_radius * math.cos(angle - tooth_width)
        y1 = center[1] + inner_radius * math.sin(angle - tooth_width)
        
        x2 = center[0] + outer_radius * math.cos(angle)
        y2 = center[1] + outer_radius * math.sin(angle)
        
        x3 = center[0] + inner_radius * math.cos(angle + tooth_width)
        y3 = center[1] + inner_radius * math.sin(angle + tooth_width)
        
        # Desenha o "dente"
        draw.polygon([(x1, y1), (x2, y2), (x3, y3)], fill=color)
    
    # Salva a imagem
    image.save(icon_path, format="PNG")
    print(f"Ícone de sistema criado: {icon_path}")

def main():
    """Função principal"""
    try:
        # Cria o diretório de recursos
        resources_dir = create_resources_directory()
        
        # Cria os ícones
        create_icon(resources_dir, "icon.ico")
        create_icon(resources_dir, "logo.png", size=(64, 64))
        create_document_icon(resources_dir)
        create_empty_document_icon(resources_dir)
        create_system_icon(resources_dir)
        
        print("Todos os recursos foram criados com sucesso!")
        
    except Exception as e:
        print(f"Erro ao criar recursos: {str(e)}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
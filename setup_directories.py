#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Script para criar estrutura de diretórios e arquivos necessários
"""

import os
import sys
import shutil
import logging

def create_directory_structure():
    """Cria a estrutura de diretórios necessária"""
    # Diretório raiz (onde este script está)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Estrutura de diretórios a criar
    directories = [
        os.path.join(base_dir, "src", "ui", "resources"),
        os.path.join(base_dir, "data"),
        os.path.join(base_dir, "data", "config"),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Diretório criado/verificado: {directory}")
    
    # Cria um arquivo de ícone padrão se não existir
    icon_path = os.path.join(base_dir, "src", "ui", "resources", "icon.ico")
    if not os.path.exists(icon_path):
        # Cria um arquivo de ícone vazio para evitar erros
        with open(icon_path, 'wb') as f:
            # Bytes mínimos para um arquivo .ico válido (1x1 pixel)
            f.write(b'\x00\x00\x01\x00\x01\x00\x01\x01\x00\x00\x01\x00\x08\x00\x00\x00\x00\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        print(f"Arquivo de ícone padrão criado: {icon_path}")
    
    # Cria um arquivo de logo padrão se não existir
    logo_path = os.path.join(base_dir, "src", "ui", "resources", "logo.png")
    if not os.path.exists(logo_path):
        # Cria um arquivo PNG vazio para evitar erros
        with open(logo_path, 'wb') as f:
            # Bytes mínimos para um arquivo .png válido (1x1 pixel)
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82')
        print(f"Arquivo de logo padrão criado: {logo_path}")

if __name__ == "__main__":
    try:
        create_directory_structure()
        print("Estrutura de diretórios criada com sucesso.")
    except Exception as e:
        print(f"Erro ao criar estrutura de diretórios: {str(e)}")
        sys.exit(1)
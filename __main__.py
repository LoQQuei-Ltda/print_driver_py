#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Ponto de entrada para pacotes zip e executáveis
"""

import os
import sys

# Adiciona o diretório atual ao path para que as importações funcionem
dir_path = os.path.dirname(os.path.realpath(__file__))
if dir_path not in sys.path:
    sys.path.insert(0, dir_path)

# Importa a função principal
from main import main

# Executa a aplicação
if __name__ == "__main__":
    main()
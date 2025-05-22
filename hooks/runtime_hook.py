
import sys
import os

# Adiciona o diretório do executável ao PATH do Python
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)
    
# Força importação de módulos críticos
try:
    import pyipp
    import pyipp.client
    import pyipp.enums
    import pyipp.exceptions
    import aiohttp
    import asyncio
    import ssl
    import certifi
except Exception as e:
    print(f"Erro ao importar módulos no runtime hook: {e}")


import sys
import os

# Adiciona o diretório do executável ao PATH do Python
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)
    
    # Adiciona pasta de recursos ao sys.path para facilitar localização
    resources_path = os.path.join(sys._MEIPASS, 'resources')
    if os.path.exists(resources_path):
        sys.path.insert(0, resources_path)
    
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

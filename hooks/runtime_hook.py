
import sys
import os

# Adiciona o diretório do executável ao PATH do Python
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)
    
    # Adiciona pasta de recursos ao sys.path para facilitar localização
    resources_path = os.path.join(sys._MEIPASS, 'resources')
    if os.path.exists(resources_path):
        sys.path.insert(0, resources_path)

# Configurações específicas do macOS
import platform
if platform.system() == 'Darwin':
    # Corrige problemas com SSL no macOS
    import ssl
    import certifi
    ssl._create_default_https_context = ssl._create_unverified_context
    
    # Configura variáveis de ambiente para macOS
    os.environ['SSL_CERT_FILE'] = certifi.where()

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
    import zeroconf
    import pysnmp
    import netifaces
    import requests
except Exception as e:
    print(f"Erro ao importar módulos no runtime hook: {e}")

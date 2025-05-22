from PyInstaller.utils.hooks import collect_all, collect_submodules

# Coleta todos os módulos relacionados ao pyipp
datas, binaries, hiddenimports = collect_all('pyipp')

# Adiciona submódulos específicos
hiddenimports += collect_submodules('pyipp')

# Adiciona dependências conhecidas do pyipp
hiddenimports += [
    'aiohttp',
    'aiohttp.client',
    'aiohttp.client_exceptions',
    'yarl',
    'multidict',
    'async_timeout',
    'asyncio',
    'ssl',
    'socket',
    'json',
    'logging',
    'urllib.parse',
    'datetime',
    'enum',
    'typing',
]

"""Setup para o projeto - VERSÃO CORRIGIDA COMPLETA"""
import os
import sys
import platform
import shutil
from setuptools import setup, find_packages, Command

class PyInstallerCommand(Command):
    description = "Build executable with PyInstaller"
    user_options = []
    
    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass
    
    def run(self):
        # Garante que todas as dependências estão instaladas
        self._ensure_dependencies()
        
        # Importa PyInstaller
        import PyInstaller.__main__
        
        # Cria um arquivo spec personalizado
        spec_content = self._create_spec_file()
        spec_file = "PrintManagementSystem.spec"
        
        with open(spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        # Limpa build anterior
        if os.path.exists('build'):
            shutil.rmtree('build')
        if os.path.exists('dist'):
            shutil.rmtree('dist')
        
        # Executa o PyInstaller
        PyInstaller.__main__.run([spec_file, '--clean', '--noconfirm'])
        
        # Move o executável para o local esperado pelo Inno Setup
        if os.path.exists('dist/PrintManagementSystem.exe'):
            os.makedirs('build/exe', exist_ok=True)
            shutil.move('dist/PrintManagementSystem.exe', 'build/exe/PrintManagementSystem.exe')
            print("Executável criado com sucesso em: build/exe/PrintManagementSystem.exe")
    
    def _ensure_dependencies(self):
        """Garante que todas as dependências estão instaladas"""
        import subprocess
        deps = ['pyipp', 'aiohttp', 'wxPython', 'pypdf', 'watchdog', 'pyyaml', 'requests']
        
        for dep in deps:
            try:
                __import__(dep.replace('wxPython', 'wx'))
                print(f"✓ {dep} já está instalado")
            except ImportError:
                print(f"Instalando {dep}...")
                subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)
    
    def _create_spec_file(self):
        """Cria um arquivo .spec otimizado"""
        icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.ico"))
        
        # Cria runtime hook para garantir que pyipp seja encontrado
        runtime_hook_content = '''
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
'''
        
        # Cria o arquivo de runtime hook
        os.makedirs('hooks', exist_ok=True)
        with open('hooks/runtime_hook.py', 'w', encoding='utf-8') as f:
            f.write(runtime_hook_content)
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# Coleta TODOS os dados e binários dos módulos críticos
pyipp_datas, pyipp_binaries, pyipp_hiddenimports = collect_all('pyipp')
aiohttp_datas, aiohttp_binaries, aiohttp_hiddenimports = collect_all('aiohttp')
wx_datas, wx_binaries, wx_hiddenimports = collect_all('wx')

# Dados da aplicação
app_datas = [
    (os.path.join("src", "ui", "resources"), os.path.join("resources")),
]

# Combina todos os dados
all_datas = app_datas + pyipp_datas + aiohttp_datas + wx_datas

# Combina todos os binários
all_binaries = pyipp_binaries + aiohttp_binaries + wx_binaries

# Hidden imports completos
all_hiddenimports = [
    # Módulos principais
    'wx', 'wx._core', 'wx._adv', 'wx._html', 'wx._xml',
    'requests', 'pypdf', 'appdirs', 'yaml', 'watchdog',
    'watchdog.observers', 'watchdog.events',
    
    # pyipp e suas dependências
    'pyipp', 'pyipp.client', 'pyipp.enums', 'pyipp.exceptions',
    'pyipp.models', 'pyipp.serializer', 'pyipp.constants',
    
    # aiohttp e dependências
    'aiohttp', 'aiohttp.client', 'aiohttp.connector',
    'aiohttp.client_exceptions', 'aiohttp.hdrs',
    'yarl', 'multidict', 'async_timeout', 'attrs',
    'charset_normalizer', 'idna', 'certifi',
    
    # Módulos de sistema
    'asyncio', 'asyncio.base_events', 'asyncio.events',
    'asyncio.futures', 'asyncio.locks', 'asyncio.protocols',
    'asyncio.streams', 'asyncio.tasks', 'asyncio.transports',
    'ssl', 'socket', 'threading', 'queue', 'json',
    'logging', 'datetime', 'time', 'os', 'sys',
    
    # Codecs necessários
    'encodings', 'encodings.utf_8', 'encodings.ascii',
    'encodings.latin_1', 'encodings.cp1252',
]

# Adiciona todos os submódulos do pyipp
all_hiddenimports.extend(collect_submodules('pyipp'))
all_hiddenimports.extend(collect_submodules('aiohttp'))

# Remove duplicatas
all_hiddenimports = list(set(all_hiddenimports + pyipp_hiddenimports + aiohttp_hiddenimports + wx_hiddenimports))

# Adiciona imports específicos do Windows
if sys.platform == "win32":
    all_hiddenimports.extend([
        'win32api', 'win32con', 'win32print', 'win32gui',
        'win32com', 'pythoncom', 'winsound'
    ])

a = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=['hooks'],
    hooksconfig={{}},
    runtime_hooks=['hooks/runtime_hook.py'],
    excludes=['tkinter', 'matplotlib', 'numpy', 'pandas'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

# Remove módulos desnecessários para reduzir tamanho
a.exclude_datas = [
    ('tcl', 'tcl'), ('tk', 'tk'), ('mpl-data', 'matplotlib'),
    ('docutils', 'docutils'), ('pydoc_data', 'pydoc_data')
]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PrintManagementSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # FALSE para aplicação GUI sem console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path}',
    version_file=None,
    uac_admin=True,  # Requer privilégios de admin
)
'''
        return spec_content

# Configuração do projeto
APP_NAME = "PrintManagementSystem"
APP_AUTHOR = "LoQQuei"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Sistema de Gerenciamento de Impressão"

# Dependências
install_requires = [
    "wxPython>=4.2.0",
    "requests>=2.31.0",
    "pypdf>=3.1.0",
    "appdirs>=1.4.4",
    "pyyaml>=6.0.1",
    "pillow>=10.0.1",
    "watchdog>=3.0.0",
    "pyipp>=0.11.0",
    "aiohttp>=3.8.0",
    "pyinstaller>=5.0.0",
]

# Adiciona dependências específicas do Windows
if platform.system() == "Windows":
    install_requires.extend(["pywin32>=300"])

setup(
    name=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author=APP_AUTHOR,
    author_email="contato@loqquei.com.br",
    url="https://loqquei.com.br",
    packages=find_packages(),
    install_requires=install_requires,
    include_package_data=True,
    entry_points={
        "console_scripts": [
            f"{APP_NAME.lower()}=main:main",
        ],
    },
    cmdclass={
        'build_exe': PyInstallerCommand,
    },
    python_requires=">=3.8",
)
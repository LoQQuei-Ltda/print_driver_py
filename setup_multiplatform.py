"""Setup para o projeto - VERSÃO MULTIPLATAFORMA"""
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
        
        # Determina parâmetros específicos da plataforma
        system = platform.system().lower()
        
        # Cria um arquivo spec personalizado para a plataforma atual
        spec_content = self._create_spec_file(system)
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
        
        # Move o executável para o local esperado pelos scripts de instalação
        os.makedirs('build/exe', exist_ok=True)
        
        if system == "windows":
            if os.path.exists('dist/PrintManagementSystem.exe'):
                shutil.move('dist/PrintManagementSystem.exe', 'build/exe/PrintManagementSystem.exe')
        elif system == "darwin":  # macOS
            if os.path.exists('dist/PrintManagementSystem.app'):
                shutil.copytree('dist/PrintManagementSystem.app', 'build/exe/PrintManagementSystem.app')
        else:  # Linux
            if os.path.exists('dist/PrintManagementSystem'):
                shutil.move('dist/PrintManagementSystem', 'build/exe/PrintManagementSystem')
        
        # Copia recursos manualmente
        self._copy_resources()
            
        print(f"✓ Executável criado com sucesso para {system.upper()}!")
    
    def _copy_resources(self):
        """Copia recursos manualmente para garantir que estejam disponíveis"""
        resources_src = os.path.join("src", "ui", "resources")
        system = platform.system().lower()
        
        if system == "windows" or system == "linux":
            resources_dst = os.path.join("build", "exe", "resources")
        elif system == "darwin":  # macOS
            resources_dst = os.path.join("build", "exe", "PrintManagementSystem.app", "Contents", "Resources")
        
        if os.path.exists(resources_src):
            if os.path.exists(resources_dst):
                shutil.rmtree(resources_dst)
            shutil.copytree(resources_src, resources_dst)
            print(f"✓ Recursos copiados para: {resources_dst}")
        else:
            print(f"⚠ Pasta de recursos não encontrada: {resources_src}")
    
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
    
    def _create_spec_file(self, system):
        """Cria um arquivo .spec otimizado para a plataforma específica"""
        # Determina o ícone para cada plataforma
        icon_path = "NONE"
        if system == "windows":
            icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.ico"))
        elif system == "darwin":  # macOS
            icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.icns"))
        elif system == "linux":
            icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.png"))
        
        if not os.path.exists(icon_path):
            icon_path = "NONE"
        else:
            icon_path = icon_path.replace('\\', '/')
        
        # Cria runtime hook para garantir que módulos sejam encontrados
        runtime_hook_content = '''
import sys
import os

# Adiciona o diretório do executável ao PATH do Python
if hasattr(sys, '_MEIPASS'):
    sys.path.insert(0, sys._MEIPASS)
    
    # Adiciona pasta de recursos ao sys.path para facilitar localização
    if sys.platform == 'darwin':  # macOS
        resources_path = os.path.join(sys._MEIPASS, 'Resources')
    else:
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
    import zeroconf
    import pysnmp
    import netifaces
    import requests
except Exception as e:
    print(f"Erro ao importar módulos no runtime hook: {e}")
'''
        
        # Cria o arquivo de runtime hook
        os.makedirs('hooks', exist_ok=True)
        with open('hooks/runtime_hook.py', 'w', encoding='utf-8') as f:
            f.write(runtime_hook_content)
        
        # Configurações específicas por plataforma
        platform_specific = ""
        
        if system == "windows":
            platform_specific = '''
# Adiciona imports específicos do Windows
all_hiddenimports.extend([
    'win32api', 'win32con', 'win32print', 'win32gui',
    'win32com', 'pythoncom', 'winsound'
])

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
    uac_admin=False,  # Não requer privilégios de admin
)
'''
        elif system == "darwin":  # macOS
            platform_specific = '''
# Configurações específicas para macOS
app = BUNDLE(
    exe,
    name='PrintManagementSystem.app',
    icon='{icon_path}',
    bundle_identifier='br.com.loqquei.printmanagementsystem',
    info_plist={{
        'CFBundleShortVersionString': '2.0.1',
        'CFBundleVersion': '2.0.1',
        'NSHighResolutionCapable': True,
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'LSMinimumSystemVersion': '10.12.0',  # macOS Sierra
        'CFBundleName': 'Gerenciamento de Impressão LoQQuei',
        'CFBundleDisplayName': 'Gerenciamento de Impressão LoQQuei',
        'CFBundleGetInfoString': 'Sistema de Gerenciamento de Impressão da LoQQuei',
        'CFBundleDocumentTypes': [],
        'NSHumanReadableCopyright': 'Copyright © 2025 LoQQuei'
    }}
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PrintManagementSystem',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path}',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PrintManagementSystem',
)
'''
        else:  # Linux
            platform_specific = '''
# Configurações específicas para Linux
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
    console=False,  # Sem console para aplicação GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path}'
)
'''
        
        # Substitui o placeholder do ícone
        platform_specific = platform_specific.replace('{icon_path}', icon_path)
        
        # Conteúdo base do arquivo spec
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# Coleta TODOS os dados e binários dos módulos críticos
pyipp_datas, pyipp_binaries, pyipp_hiddenimports = collect_all('pyipp')
aiohttp_datas, aiohttp_binaries, aiohttp_hiddenimports = collect_all('aiohttp')
wx_datas, wx_binaries, wx_hiddenimports = collect_all('wx')

# IMPORTANTE: Dados da aplicação - incluindo TODOS os recursos
app_datas = []

# Adiciona recursos se existirem
resources_path = os.path.join("src", "ui", "resources")
if os.path.exists(resources_path):
    # Coleta TODOS os arquivos da pasta resources recursivamente
    for root, dirs, files in os.walk(resources_path):
        for file in files:
            src_file = os.path.join(root, file)
            # Calcula o caminho relativo dentro de resources
            rel_path = os.path.relpath(src_file, resources_path)
            dst_path = os.path.join("resources", rel_path).replace("\\\\", "/")
            app_datas.append((src_file, os.path.dirname(dst_path) if os.path.dirname(dst_path) else "resources"))
    print(f"Incluindo {{len(app_datas)}} arquivos de recursos")

# Adiciona outros dados da aplicação
config_files = ["config.yaml", "settings.ini", "app.conf"]
for config_file in config_files:
    if os.path.exists(config_file):
        app_datas.append((config_file, "."))

# Combina todos os dados
all_datas = app_datas + pyipp_datas + aiohttp_datas + wx_datas

# Combina todos os binários
all_binaries = pyipp_binaries + aiohttp_binaries + wx_binaries

# Hidden imports completos
all_hiddenimports = [
    # Módulos principais
    'wx', 'wx._core', 'wx._adv', 'wx._html', 'wx._xml',
    'requests', 'pypdf', 'appdirs', 'yaml', 'watchdog',
    'watchdog.observers', 'watchdog.events', 'flask', 'flask_cors',
    
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

    'zeroconf', 'zeroconf._utils', 'zeroconf._services',
    'pysnmp', 'pysnmp.hlapi', 'pysnmp.smi',
    'netifaces', 'requests', 'urllib3',
    'certifi', 'charset_normalizer', 
]

# Adiciona todos os submódulos do pyipp
all_hiddenimports.extend(collect_submodules('pyipp'))
all_hiddenimports.extend(collect_submodules('aiohttp'))

# Remove duplicatas
all_hiddenimports = list(set(all_hiddenimports + pyipp_hiddenimports + aiohttp_hiddenimports + wx_hiddenimports))

{platform_specific if system != "darwin" else ""}

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

{platform_specific if system == "darwin" else ""}
'''
        
        return spec_content

# Configuração do projeto
APP_NAME = "PrintManagementSystem"
APP_AUTHOR = "LoQQuei"
APP_VERSION = "2.0.1"
APP_DESCRIPTION = "Sistema de Gerenciamento de Impressão"

# Dependências comuns para todas as plataformas
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
    "flask>=3.1.1",
    'flask_cors>=6.0.0',
    "pyinstaller>=5.0.0",
    "python-nmap>=0.7.1",
    "pysnmp>=7.1.20",
    "netifaces>=0.11.0",
    "wsdiscovery>=2.1.2",
    "zeroconf>=0.147.0",
]

# Adiciona dependências específicas da plataforma
system = platform.system().lower()
if system == "windows":
    install_requires.extend(["pywin32>=300"])
elif system == "darwin":  # macOS
    install_requires.extend(["dmgbuild>=1.6.0"])
elif system == "linux":
    install_requires.extend(["stdeb>=0.10.0"])

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
"""Setup para o projeto - VERSÃO MULTIPLATAFORMA CORRIGIDA"""
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
        
        # Move o executável para o local esperado
        self._move_executable()
        
    def _move_executable(self):
        """Move o executável para a pasta build/exe de acordo com a plataforma"""
        system = platform.system().lower()
        
        os.makedirs('build/exe', exist_ok=True)
        
        if system == "windows":
            src = 'dist/PrintManagementSystem.exe'
            dst = 'build/exe/PrintManagementSystem.exe'
            if os.path.exists(src):
                shutil.move(src, dst)
                print(f"✓ Executável Windows criado: {dst}")
        
        elif system == "darwin":  # macOS
            src = 'dist/PrintManagementSystem.app'
            dst = 'build/exe/PrintManagementSystem.app'
            if os.path.exists(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.move(src, dst)
                print(f"✓ Aplicação macOS criada: {dst}")
        
        else:  # Linux
            src = 'dist/PrintManagementSystem'
            dst = 'build/exe/PrintManagementSystem'
            if os.path.exists(src):
                shutil.move(src, dst)
                # Garante que o arquivo seja executável no Linux
                os.chmod(dst, 0o755)
                print(f"✓ Executável Linux criado: {dst}")
        
        # Copia recursos manualmente se existirem
        self._copy_resources()
    
    def _copy_resources(self):
        """Copia recursos manualmente para garantir que estejam disponíveis"""
        resources_src = os.path.join("src", "ui", "resources")
        resources_dst = os.path.join("build", "exe", "resources")
        
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
        
        # Dependências básicas
        deps = ['pyipp', 'aiohttp', 'wxPython', 'pypdf', 'watchdog', 'pyyaml', 'requests', 'zeroconf', 'pysnmp', 'netifaces', 'flask', 'flask_cors']
        
        # Dependências específicas por plataforma
        system = platform.system().lower()
        if system == "windows":
            deps.append('pywin32')
        elif system == "darwin":  # macOS
            # No macOS, algumas dependências podem ter nomes diferentes
            pass
        
        for dep in deps:
            try:
                # Trata casos especiais de importação
                import_name = dep
                if dep == 'wxPython':
                    import_name = 'wx'
                elif dep == 'pyyaml':
                    import_name = 'yaml'
                elif dep == 'pypdf':
                    import_name = 'pypdf'
                
                __import__(import_name)
                print(f"✓ {dep} já está instalado")
            except ImportError:
                print(f"Instalando {dep}...")
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install', dep], check=True)
                    print(f"✓ {dep} instalado com sucesso")
                except subprocess.CalledProcessError as e:
                    print(f"❌ Erro ao instalar {dep}: {e}")
    
    def _create_spec_file(self):
        """Cria um arquivo .spec otimizado para multiplataforma"""
        system = platform.system().lower()
        
        # Configuração do ícone por plataforma
        if system == "windows":
            icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.ico"))
        elif system == "darwin":  # macOS
            icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.icns"))
        else:  # Linux
            icon_path = os.path.abspath(os.path.join("src", "ui", "resources", "icon.png"))
        
        if not os.path.exists(icon_path):
            icon_path = "NONE"
        else:
            # Normaliza o caminho para evitar problemas com barras
            icon_path = icon_path.replace('\\', '/')
        
        # Cria runtime hook para garantir que pyipp seja encontrado
        runtime_hook_content = '''
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
'''
        
        # Cria o arquivo de runtime hook
        os.makedirs('hooks', exist_ok=True)
        with open('hooks/runtime_hook.py', 'w', encoding='utf-8') as f:
            f.write(runtime_hook_content)
        
        # Configurações específicas por plataforma
        console_mode = "False"  # GUI app por padrão
        windowed_mode = ""
        
        if system == "darwin":  # macOS
            windowed_mode = """
# Configurações específicas para macOS
app = BUNDLE(exe,
             name='PrintManagementSystem.app',
             icon='{icon_path}',
             bundle_identifier='com.loqquei.printmanagement',
             version='{version}',
             info_plist={{
                 'CFBundleName': 'Gerenciamento de Impressão LoQQuei',
                 'CFBundleDisplayName': 'Gerenciamento de Impressão',
                 'CFBundleShortVersionString': '{version}',
                 'CFBundleVersion': '{version}',
                 'LSMinimumSystemVersion': '10.13.0',
                 'NSHighResolutionCapable': True,
                 'NSRequiresAquaSystemAppearance': False,
             }})
""".format(icon_path=icon_path, version="2.0.2")
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import os
import sys
import platform
from PyInstaller.utils.hooks import collect_all, collect_submodules, collect_data_files

block_cipher = None

# Detecta a plataforma atual
current_platform = platform.system().lower()

# Coleta TODOS os dados e binários dos módulos críticos
pyipp_datas, pyipp_binaries, pyipp_hiddenimports = collect_all('pyipp')
aiohttp_datas, aiohttp_binaries, aiohttp_hiddenimports = collect_all('aiohttp')

# Coleta dados do wxPython de forma mais robusta
try:
    wx_datas, wx_binaries, wx_hiddenimports = collect_all('wx')
except Exception as e:
    print(f"Aviso: Erro ao coletar dados do wx: {{e}}")
    wx_datas, wx_binaries, wx_hiddenimports = [], [], []

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

# Adiciona certificados SSL para HTTPS (importante para macOS)
try:
    import certifi
    cert_file = certifi.where()
    if os.path.exists(cert_file):
        app_datas.append((cert_file, "certifi"))
        print("✓ Certificados SSL incluídos")
except ImportError:
    print("⚠ certifi não encontrado - HTTPS pode não funcionar")

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
    'zeroconf', 'zeroconf._utils', 'zeroconf._services',
    'pysnmp', 'pysnmp.hlapi', 'pysnmp.smi',
    'netifaces', 'requests', 'urllib3',
    'certifi', 'charset_normalizer', 
    
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
    
    # Módulos específicos para cada plataforma
]

# Adiciona todos os submódulos do pyipp
all_hiddenimports.extend(collect_submodules('pyipp'))
all_hiddenimports.extend(collect_submodules('aiohttp'))

# Adiciona imports específicos por plataforma
if current_platform == "windows":
    all_hiddenimports.extend([
        'win32api', 'win32con', 'win32print', 'win32gui',
        'win32com', 'pythoncom', 'winsound'
    ])
elif current_platform == "darwin":  # macOS
    all_hiddenimports.extend([
        'Foundation', 'AppKit', 'Cocoa', 'objc',
        'CoreFoundation', 'SystemConfiguration'
    ])
elif current_platform == "linux":
    all_hiddenimports.extend([
        'gi', 'gi.repository', 'gi.repository.Gtk',
        'dbus', 'dbus.mainloop', 'dbus.mainloop.glib'
    ])

# Remove duplicatas
all_hiddenimports = list(set(all_hiddenimports + pyipp_hiddenimports + aiohttp_hiddenimports + wx_hiddenimports))

# Módulos a excluir para reduzir tamanho
excludes = ['tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'jupyter']

# Exclusões específicas por plataforma
if current_platform == "darwin":
    # No macOS, podemos excluir alguns módulos do Windows
    excludes.extend(['win32api', 'win32con', 'win32print', 'win32gui'])
elif current_platform == "windows":
    # No Windows, podemos excluir alguns módulos do macOS/Linux
    excludes.extend(['Foundation', 'AppKit', 'Cocoa', 'gi'])
elif current_platform == "linux":
    # No Linux, podemos excluir módulos específicos do Windows/macOS
    excludes.extend(['win32api', 'Foundation', 'AppKit'])

a = Analysis(
    ['main.py'],
    pathex=[os.getcwd()],
    binaries=all_binaries,
    datas=all_datas,
    hiddenimports=all_hiddenimports,
    hookspath=['hooks'],
    hooksconfig={{}},
    runtime_hooks=['hooks/runtime_hook.py'],
    excludes=excludes,
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
    upx=False,  # UPX pode causar problemas no macOS
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # FALSE para aplicação GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path}',
    version_file=None,
    uac_admin=False,  # Não requer privilégios de admin
)

{windowed_mode}
'''
        return spec_content

# Configuração do projeto
APP_NAME = "PrintManagementSystem"
APP_AUTHOR = "LoQQuei"
APP_VERSION = "2.0.2"
APP_DESCRIPTION = "Sistema de Gerenciamento de Impressão"

# Dependências básicas
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
    "certifi>=2023.7.22",  # Importante para HTTPS no macOS
    "python-nmap>=0.7.1",
    "pysnmp>=7.1.20",
    "netifaces>=0.11.0",
    "wsdiscovery>=2.1.2",
    "zeroconf>=0.147.0",
]

# Adiciona dependências específicas por plataforma
system = platform.system().lower()
if system == "windows":
    install_requires.extend(["pywin32>=300"])
elif system == "darwin":  # macOS
    # Dependências específicas do macOS se necessário
    install_requires.extend(["pyobjc-core>=9.0", "pyobjc-framework-Cocoa>=9.0"])
elif system == "linux":
    # Dependências específicas do Linux se necessário
    pass

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
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business",
        "Topic :: Printing",
    ],
)
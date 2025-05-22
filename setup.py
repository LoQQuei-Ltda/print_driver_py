"""Setup para o projeto - VERSÃO CORRIGIDA"""
import os
import sys
import platform
import importlib.util
from setuptools import setup, find_packages, Command

class PyInstallerCommand(Command):
    description = "Build executable with PyInstaller"
    user_options = []
    
    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass
    
    def run(self):
        # Garante que o pyipp está instalado antes de construir
        self._ensure_pyipp_installed()
        
        # Importa PyInstaller
        import PyInstaller.__main__
        
        # Caminho para o ícone da aplicação
        icon_path = os.path.join("src", "ui", "resources", "icon.ico")
        
        # Cria um arquivo spec personalizado para melhor controle
        spec_content = self._create_spec_file()
        spec_file = "print_management_system.spec"
        
        with open(spec_file, 'w', encoding='utf-8') as f:
            f.write(spec_content)
        
        # Argumentos do PyInstaller usando o spec file
        pyinstaller_args = [
            spec_file,
            '--clean',
            '--noconfirm'
        ]
        
        # Executa o PyInstaller
        PyInstaller.__main__.run(pyinstaller_args)
        
        print("PyInstaller completed successfully.")
    
    def _ensure_pyipp_installed(self):
        """Garante que pyipp está instalado"""
        try:
            import pyipp
            print("Módulo pyipp já está instalado.")
            return True
        except ImportError:
            print("Instalando módulo pyipp...")
            try:
                import subprocess
                import sys
                result = subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyipp'], 
                                      capture_output=True, text=True, check=True)
                print("pyipp instalado com sucesso.")
                return True
            except Exception as e:
                print(f"ERRO: Não foi possível instalar pyipp: {e}")
                return False
    
    def _create_spec_file(self):
        """Cria um arquivo .spec personalizado para o PyInstaller"""
        icon_path = os.path.join("src", "ui", "resources", "icon.ico")
        
        spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
import os
import platform

block_cipher = None

# Detecta dados adicionais
datas = []
if os.path.exists(os.path.join("src", "ui", "resources")):
    datas.append((os.path.join("src", "ui", "resources"), os.path.join("src", "ui", "resources")))

# Hidden imports específicos
hiddenimports = [
    'wx',
    'wx._core',
    'wx._adv',
    'wx._html',
    'wx._xml',
    'requests',
    'pypdf',
    'appdirs',
    'yaml',
    'watchdog',
    'watchdog.observers',
    'watchdog.events',
    'pyipp',
    'pyipp.client',
    'pyipp.enums',
    'pyipp.exceptions',
    'aiohttp',
    'aiohttp.client',
    'yarl',
    'multidict',
    'async_timeout',
    'charset_normalizer',
    'idna',
    'urllib3',
    'certifi',
    'ssl',
    'socket',
    'asyncio',
    'concurrent.futures',
    'threading',
    'queue',
    'json',
    'logging',
    'datetime',
    'time',
    'os',
    'sys',
    'platform',
    'pathlib'
]

# Adiciona imports específicos da plataforma
if platform.system() == "Windows":
    hiddenimports.extend([
        'win32api',
        'win32con',
        'win32print',
        'win32gui',
        'winsound'
    ])
elif platform.system() == "Linux":
    hiddenimports.extend([
        'cups',
        'gi',
        'gi.repository',
        'gi.repository.Gtk'
    ])

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{APP_NAME}',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Mantenha True para debug, mude para False na versão final
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='{icon_path if os.path.exists(icon_path) else ""}',
)
'''
        return spec_content

# Resto do setup.py permanece igual...
APP_NAME = "PrintManagementSystem"
APP_AUTHOR = "LoQQuei"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Sistema de Gerenciamento de Impressão"

# Verifica o sistema operacional
WINDOWS = platform.system() == "Windows"
MAC = platform.system() == "Darwin"
LINUX = platform.system() == "Linux"

# Pacotes específicos para cada plataforma
platform_specific_requires = []

if WINDOWS:
    platform_specific_requires.extend([
        "pywin32>=307",
        "pywin32-ctypes>=0.2.0",
    ])
elif MAC:
    platform_specific_requires.extend([
        "pyobjc-core>=9.0",
        "pyobjc-framework-Cocoa>=9.0",
    ])
elif LINUX:
    platform_specific_requires.extend([
        "python-cups>=2.0.1",
        "pycups>=2.0.1",
    ])

# Dependências básicas (comum a todas plataformas)
basic_requires = [
    "wxPython>=4.2.0",
    "requests>=2.31.0",
    "pypdf>=5.5.0",
    "appdirs>=1.4.4",
    "pyyaml>=6.0.1",
    "pillow>=10.0.1",
    "watchdog>=2.3.0",
    "pyipp>=0.11.0",
    "pyinstaller>=5.0.0",
    "aiohttp>=3.8.0",  # Dependência do pyipp
]

# Configuração principal
setup(
    name=APP_NAME,
    version=APP_VERSION,
    description=APP_DESCRIPTION,
    author=APP_AUTHOR,
    author_email="contato@loqquei.com.br",
    url="https://loqquei.com.br",
    packages=find_packages(),
    install_requires=basic_requires + platform_specific_requires,
    include_package_data=True,
    entry_points={
        "console_scripts": [
            f"{APP_NAME.lower()}=main:main",
        ],
    },
    cmdclass={
        'bdist_pyinstaller': PyInstallerCommand,
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: X11 Applications",
        "Environment :: Win32 (MS Windows)",
        "Environment :: MacOS X",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: MIT License",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: POSIX :: Linux",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Office/Business",
    ],
    python_requires=">=3.8",
)
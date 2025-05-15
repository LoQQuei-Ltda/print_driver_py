"""Setup para o projeto"""
import os
import sys
import platform
from setuptools import setup, find_packages

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
        "pywin32>=306",
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
    "PyPDF2>=3.0.1",
    "appdirs>=1.4.4",
    "pyyaml>=6.0.1",
    "pillow>=10.0.1",
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

# Script para criar executáveis com PyInstaller (se instalado)
if 'bdist_pyinstaller' in sys.argv:
    try:
        import PyInstaller.__main__
        
        # Remove o argumento para evitar erro no setup
        sys.argv.remove('bdist_pyinstaller')
        
        # Caminho para o ícone da aplicação
        icon_path = os.path.join("src", "ui", "resources", "icon.ico")
        
        # Argumentos do PyInstaller
        pyinstaller_args = [
            '--name=%s' % APP_NAME,
            '--onefile',
            '--windowed',
            '--add-data=%s;%s' % ('src/ui/resources', 'src/ui/resources'),
            f'--icon={icon_path}' if os.path.exists(icon_path) else '',
            '--hidden-import=wx',
            '--hidden-import=requests',
            '--hidden-import=PyPDF2',
            '--hidden-import=appdirs',
            '--hidden-import=yaml',
            '--clean',
            'main.py',
        ]
        
        # Remove argumentos vazios
        pyinstaller_args = [arg for arg in pyinstaller_args if arg]
        
        # Executa o PyInstaller
        PyInstaller.__main__.run(pyinstaller_args)
        
        print("PyInstaller completed successfully.")
        
    except ImportError:
        print("PyInstaller not found. Please install it with 'pip install pyinstaller'.")
        sys.exit(1)
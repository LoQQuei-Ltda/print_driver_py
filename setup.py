"""Setup para o projeto"""
import os
import sys
import platform
import importlib.util
from setuptools import setup, find_packages, Command

# Classe melhorada para o comando personalizado
class PyInstallerCommand(Command):
    description = "Build executable with PyInstaller"
    user_options = []
    
    def initialize_options(self):
        pass
    
    def finalize_options(self):
        pass
    
    def run(self):
        # Verifica e tenta instalar pyipp se necessário
        try:
            import pyipp
            print("Módulo pyipp já está instalado.")
        except ImportError:
            print("Instalando módulo pyipp...")
            try:
                from pip._internal import main as pip_main
                pip_main(['install', 'pyipp'])
                print("pyipp instalado com sucesso.")
            except Exception as e:
                print(f"Aviso: Não foi possível instalar pyipp: {e}")
                print("O executável será criado sem suporte completo a este módulo.")
        
        # Importa PyInstaller após ter tentado instalar dependências
        import PyInstaller.__main__
        
        # Caminho para o ícone da aplicação
        icon_path = os.path.join("src", "ui", "resources", "icon.ico")
        
        # Verifica se pyipp está disponível para decidir se inclui como hidden import
        has_pyipp = importlib.util.find_spec("pyipp") is not None
        
        # Base de argumentos do PyInstaller
        pyinstaller_args = [
            f'--name={APP_NAME}',
            '--onefile',
            '--console',  # Use --console para ver erros durante desenvolvimento
            f'--add-data={os.path.join("src", "ui", "resources")}{os.pathsep}{os.path.join("src", "ui", "resources")}',
            f'--icon={icon_path}' if os.path.exists(icon_path) else '',
            '--hidden-import=wx',
            '--hidden-import=requests',
            '--hidden-import=pypdf',
            '--hidden-import=appdirs',
            '--hidden-import=yaml',
            '--hidden-import=watchdog',
            '--clean',
        ]
        
        # Adiciona pyipp como hidden import apenas se disponível
        if has_pyipp:
            pyinstaller_args.append('--hidden-import=pyipp')
            print("Incluindo suporte para pyipp no executável.")
        else:
            print("AVISO: pyipp não disponível. Funcionalidade de descoberta de impressoras será limitada.")
            
            # Modifica o arquivo de descoberta de impressoras para lidar com ausência do pyipp
            self._patch_printer_discovery()
        
        # Adiciona o arquivo principal
        pyinstaller_args.append('main.py')
        
        # Remove argumentos vazios
        pyinstaller_args = [arg for arg in pyinstaller_args if arg]
        
        # Executa o PyInstaller
        PyInstaller.__main__.run(pyinstaller_args)
        
        print("PyInstaller completed successfully.")
    
    def _patch_printer_discovery(self):
        """Modifica o arquivo de descoberta de impressoras para lidar com ausência do pyipp"""
        discovery_file = os.path.join('src', 'utils', 'printer_discovery.py')
        
        try:
            # Verifica se o arquivo existe
            if not os.path.exists(discovery_file):
                print(f"Arquivo {discovery_file} não encontrado.")
                return
            
            # Lê o conteúdo do arquivo
            with open(discovery_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Verifica se já existe o código para lidar com ausência do pyipp
            if "DummyIPP" in content or "DummyModule" in content:
                print("Arquivo já modificado para suportar ausência do pyipp.")
                return
            
            # Adiciona código no início do arquivo após os imports
            import_block = """
# Configurações para o IPP
try:
    import pyipp
    HAS_PYIPP = True
except ImportError:
    HAS_PYIPP = False
    logger.warning("Módulo pyipp não encontrado. Criando implementação alternativa.")
    
    # Classe fictícia para simular pyipp quando não está disponível
    class DummyIPP:
        def __init__(self, host=None, port=None, tls=False):
            self.host = host
            self.port = port
            self.tls = tls
            self.url_path = ""
            
        async def printer(self):
            return {"printer-state": "Indisponível (pyipp não instalado)"}
    
    # Cria um substituto para o módulo pyipp
    class DummyModule:
        def __init__(self):
            self.IPP = DummyIPP
    
    # Atribui o módulo fictício à variável pyipp
    pyipp = DummyModule()
"""
            
            # Encontra a posição após as importações
            lines = content.split('\n')
            import_end_idx = 0
            
            for i, line in enumerate(lines):
                if line.startswith('import') or line.startswith('from'):
                    import_end_idx = max(import_end_idx, i)
            
            # Insere o bloco após as importações
            lines.insert(import_end_idx + 1, import_block)
            
            # Escreve o arquivo modificado
            with open(discovery_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
            
            print(f"Arquivo {discovery_file} modificado com sucesso para suportar ausência do pyipp.")
        
        except Exception as e:
            print(f"Erro ao modificar arquivo de descoberta de impressoras: {e}")

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
    "pypdf>=5.5.0",
    "appdirs>=1.4.4",
    "pyyaml>=6.0.1",
    "pillow>=10.0.1",
    "watchdog>=2.3.0",
    "pyipp>=0.11.0",
    "pyinstaller>=5.0.0",  # Adicionando PyInstaller como dependência
]

# Verifica e tenta instalar as dependências principais
try:
    # Tentar importar pyipp para ver se já está instalado
    import pyipp
    print("pyipp já está instalado no sistema.")
except ImportError:
    print("Aviso: pyipp não está instalado. Tentando instalar...")
    try:
        from pip._internal import main as pip_main
        pip_main(['install', 'pyipp'])
        print("pyipp instalado com sucesso.")
    except Exception as e:
        print(f"Aviso: Não foi possível instalar pyipp automaticamente: {e}")
        print("Algumas funcionalidades de descoberta de impressora podem ser limitadas.")

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
        'bdist_pyinstaller': PyInstallerCommand,  # Registra o comando personalizado
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
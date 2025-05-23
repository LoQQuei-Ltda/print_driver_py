"""
Script de Build Automatizado para o Sistema de Gerenciamento de Impressão
Garante que o executável seja criado corretamente antes do Inno Setup
"""
import os
import sys
import shutil
import subprocess
import platform

def print_header(text):
    """Imprime cabeçalho formatado"""
    print("\n" + "="*60)
    print(f" {text}")
    print("="*60 + "\n")

def check_python_version():
    """Verifica se a versão do Python é compatível"""
    print_header("Verificando versão do Python")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ ERRO: Python 3.8 ou superior é necessário!")
        return False
    
    print("✓ Versão do Python compatível")
    return True

def install_dependencies():
    """Instala todas as dependências necessárias"""
    print_header("Instalando dependências")
    
    # Lista de dependências críticas
    dependencies = [
        "pyinstaller>=5.0.0",
        "wxPython>=4.2.0",
        "pyipp>=0.11.0",
        "aiohttp>=3.8.0",
        "requests>=2.31.0",
        "pypdf>=3.1.0",
        "watchdog>=3.0.0",
        "pyyaml>=6.0.1",
        "appdirs>=1.4.4",
        "pillow>=10.0.1"
    ]
    
    if platform.system() == "Windows":
        dependencies.append("pywin32>=300")
    
    for dep in dependencies:
        print(f"Instalando {dep}...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", dep], 
                         check=True, capture_output=True)
            print(f"✓ {dep} instalado com sucesso")
        except subprocess.CalledProcessError as e:
            print(f"❌ Erro ao instalar {dep}: {e}")
            return False
    
    return True

def create_test_import_script():
    """Cria script para testar imports no executável"""
    test_script = '''
# Script de teste de imports
import sys
print(f"Python: {sys.version}")
print(f"Executável: {sys.executable}")
print("-" * 50)

modules_to_test = [
    "wx", "pyipp", "aiohttp", "requests", "pypdf", 
    "watchdog", "yaml", "appdirs", "PIL"
]

if sys.platform == "win32":
    modules_to_test.extend(["win32api", "win32print"])

for module in modules_to_test:
    try:
        __import__(module)
        print(f"✓ {module} importado com sucesso")
    except ImportError as e:
        print(f"❌ Erro ao importar {module}: {e}")

# Testa pyipp especificamente
try:
    import pyipp
    print(f"\\n✓ pyipp versão: {pyipp.__version__ if hasattr(pyipp, '__version__') else 'desconhecida'}")
    from pyipp import Client
    print("✓ pyipp.Client disponível")
except Exception as e:
    print(f"❌ Erro com pyipp: {e}")

input("\\nPressione ENTER para sair...")
'''
    
    with open('test_imports.py', 'w', encoding='utf-8') as f:
        f.write(test_script)
    
    print("✓ Script de teste criado: test_imports.py")

def build_executable():
    """Constrói o executável usando PyInstaller"""
    print_header("Construindo executável")
    
    # Limpa builds anteriores
    for folder in ['build', 'dist', '__pycache__']:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"✓ Pasta {folder} removida")
    
    # Executa o setup.py com o comando customizado
    print("\nExecutando PyInstaller...")
    try:
        subprocess.run([sys.executable, "setup.py", "build_exe"], check=True)
        
        # Verifica se o executável foi criado
        exe_path = "build/exe/PrintManagementSystem.exe"
        if os.path.exists(exe_path):
            size_mb = os.path.getsize(exe_path) / (1024 * 1024)
            print(f"\n✓ Executável criado com sucesso!")
            print(f"  Caminho: {exe_path}")
            print(f"  Tamanho: {size_mb:.2f} MB")
            return True
        else:
            print("\n❌ Executável não foi criado!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro ao executar PyInstaller: {e}")
        return False

def test_executable():
    """Testa o executável gerado"""
    print_header("Testando executável")
    
    exe_path = "build/exe/PrintManagementSystem.exe"
    if not os.path.exists(exe_path):
        print("❌ Executável não encontrado!")
        return False
    
    # Copia o script de teste para a pasta do executável
    test_exe_dir = "build/exe"
    shutil.copy("test_imports.py", os.path.join(test_exe_dir, "test_imports.py"))
    
    print("Execute o seguinte comando para testar os imports:")
    print(f"\n  {exe_path} test_imports.py\n")
    
    response = input("Deseja executar o teste agora? (s/n): ")
    if response.lower() == 's':
        subprocess.run([exe_path, "test_imports.py"], cwd=test_exe_dir)
    
    return True

def build_installer():
    """Constrói o instalador usando Inno Setup"""
    print_header("Construindo instalador")
    
    # Procura pelo Inno Setup
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe"
    ]
    
    iscc_exe = None
    for path in inno_paths:
        if os.path.exists(path):
            iscc_exe = path
            break
    
    if not iscc_exe:
        print("❌ Inno Setup não encontrado!")
        print("Por favor, instale o Inno Setup de: https://jrsoftware.org/isdl.php")
        return False
    
    print(f"✓ Inno Setup encontrado: {iscc_exe}")
    
    # Executa o Inno Setup
    try:
        subprocess.run([iscc_exe, "installer.iss"], check=True)
        
        # Verifica se o instalador foi criado
        installer_path = "Output/Instalador_Gerenciamento_LoQQuei_V1.0.0.exe"
        if os.path.exists(installer_path):
            size_mb = os.path.getsize(installer_path) / (1024 * 1024)
            print(f"\n✓ Instalador criado com sucesso!")
            print(f"  Caminho: {installer_path}")
            print(f"  Tamanho: {size_mb:.2f} MB")
            return True
        else:
            print("\n❌ Instalador não foi criado!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro ao executar Inno Setup: {e}")
        return False

def main():
    """Função principal"""
    print_header("Build do Sistema de Gerenciamento de Impressão")
    
    # Verifica Python
    if not check_python_version():
        return 1
    
    # Instala dependências
    if not install_dependencies():
        print("\n❌ Falha ao instalar dependências!")
        return 1
    
    # Cria script de teste
    create_test_import_script()
    
    # Constrói executável
    if not build_executable():
        print("\n❌ Falha ao construir executável!")
        return 1
    
    # Testa executável
    test_executable()
    
    # Pergunta se deve construir o instalador
    response = input("\nDeseja construir o instalador? (s/n): ")
    if response.lower() == 's':
        if build_installer():
            print("\n✓ Build completo com sucesso!")
            print("\nPróximos passos:")
            print("1. Teste o instalador em uma máquina limpa")
            print("2. Verifique se todas as funcionalidades estão operacionais")
            print("3. Distribua o instalador aos usuários")
        else:
            print("\n❌ Falha ao construir instalador!")
            return 1
    
    print("\n✓ Processo concluído!")
    return 0

if __name__ == "__main__":
    sys.exit(main())

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
    print(f"\n✓ pyipp versão: {pyipp.__version__ if hasattr(pyipp, '__version__') else 'desconhecida'}")
    from pyipp import Client
    print("✓ pyipp.Client disponível")
except Exception as e:
    print(f"❌ Erro com pyipp: {e}")

input("\nPressione ENTER para sair...")

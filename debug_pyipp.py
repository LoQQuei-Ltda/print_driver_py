"""
Script de debug para identificar problemas com pyipp no executável
Adicione este código no início do seu main.py para debug
"""
import sys
import os
import traceback

def debug_pyipp_import():
    """Debug detalhado da importação do pyipp"""
    print("="*60)
    print("DEBUG: Informações do Sistema")
    print("="*60)
    print(f"Python: {sys.version}")
    print(f"Executável: {sys.executable}")
    print(f"Frozen: {getattr(sys, 'frozen', False)}")
    
    if hasattr(sys, '_MEIPASS'):
        print(f"PyInstaller _MEIPASS: {sys._MEIPASS}")
        print("\nArquivos em _MEIPASS:")
        try:
            for item in os.listdir(sys._MEIPASS)[:20]:  # Lista primeiros 20 arquivos
                print(f"  - {item}")
        except Exception as e:
            print(f"  Erro ao listar: {e}")
    
    print(f"\nsys.path:")
    for p in sys.path:
        print(f"  - {p}")
    
    print("\n" + "="*60)
    print("DEBUG: Tentando importar pyipp")
    print("="*60)
    
    # Tenta diferentes formas de importar
    imports_to_try = [
        ("import pyipp", lambda: __import__('pyipp')),
        ("from pyipp import Client", lambda: __import__('pyipp.client', fromlist=['Client'])),
        ("import aiohttp", lambda: __import__('aiohttp')),
        ("import asyncio", lambda: __import__('asyncio')),
        ("import ssl", lambda: __import__('ssl')),
        ("import certifi", lambda: __import__('certifi'))
    ]
    
    for import_str, import_func in imports_to_try:
        try:
            module = import_func()
            print(f"✓ {import_str} - OK")
            
            # Informações adicionais para pyipp
            if 'pyipp' in import_str and hasattr(module, '__file__'):
                print(f"  Local: {module.__file__}")
                if hasattr(module, '__version__'):
                    print(f"  Versão: {module.__version__}")
                    
        except Exception as e:
            print(f"❌ {import_str} - ERRO:")
            print(f"  {type(e).__name__}: {str(e)}")
            traceback.print_exc()
    
    print("\n" + "="*60)

def safe_import_pyipp():
    """Importação segura do pyipp com fallback"""
    try:
        import pyipp
        return pyipp, None
    except ImportError as e:
        # Tenta adicionar caminhos alternativos
        if hasattr(sys, '_MEIPASS'):
            # No executável PyInstaller
            possible_paths = [
                os.path.join(sys._MEIPASS, 'pyipp'),
                os.path.join(sys._MEIPASS, 'site-packages', 'pyipp'),
                sys._MEIPASS
            ]
            
            for path in possible_paths:
                if path not in sys.path:
                    sys.path.insert(0, path)
            
            # Tenta novamente
            try:
                import pyipp
                return pyipp, None
            except ImportError:
                pass
        
        return None, str(e)

# Função para ser chamada no início do main.py
def initialize_pyipp_debug():
    """Inicializa debug do pyipp"""
    if getattr(sys, 'frozen', False):
        # Apenas em executáveis
        debug_pyipp_import()
        
        pyipp, error = safe_import_pyipp()
        if pyipp:
            print("\n✓ pyipp importado com sucesso após debug!")
            return pyipp
        else:
            print(f"\n❌ Falha ao importar pyipp: {error}")
            print("\nPressione ENTER para continuar...")
            input()
            return None
    else:
        # Em desenvolvimento, importa normalmente
        import pyipp
        return pyipp

# Exemplo de uso no main.py:
"""
# No início do main.py, adicione:
if getattr(sys, 'frozen', False):
    from debug_pyipp import initialize_pyipp_debug
    pyipp = initialize_pyipp_debug()
    if not pyipp:
        # Tratar erro - talvez desabilitar funcionalidades IPP
        print("Funcionalidades IPP não disponíveis")
else:
    import pyipp
"""
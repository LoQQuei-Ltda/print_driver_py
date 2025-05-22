"""
Wrapper para o main.py com tratamento robusto de imports
Renomeie seu main.py atual para main_original.py e use este como main.py
"""
import sys
import os
import logging

# Configuração de logging
logging.basicConfig(
    level=logging.DEBUG if getattr(sys, 'frozen', False) else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def setup_frozen_imports():
    """Configura imports para executável PyInstaller"""
    if hasattr(sys, '_MEIPASS'):
        # Adiciona caminhos do PyInstaller
        meipass = sys._MEIPASS
        possible_paths = [
            meipass,
            os.path.join(meipass, 'lib'),
            os.path.join(meipass, 'site-packages'),
        ]
        
        for path in possible_paths:
            if os.path.exists(path) and path not in sys.path:
                sys.path.insert(0, path)
                logger.debug(f"Adicionado ao sys.path: {path}")

def safe_import(module_name, package_name=None):
    """Importa módulo com tratamento de erro"""
    try:
        if package_name:
            module = __import__(module_name, fromlist=[package_name])
            return getattr(module, package_name)
        else:
            return __import__(module_name)
    except ImportError as e:
        logger.error(f"Falha ao importar {module_name}: {e}")
        return None

def initialize_application():
    """Inicializa a aplicação com imports seguros"""
    logger.info("Iniciando aplicação...")
    
    # Configura ambiente se for executável
    if getattr(sys, 'frozen', False):
        logger.info("Executando como executável compilado")
        setup_frozen_imports()
    
    # Imports críticos com fallback
    modules = {}
    
    # wxPython (essencial)
    wx = safe_import('wx')
    if not wx:
        import tkinter.messagebox as mb
        mb.showerror("Erro Fatal", "wxPython não está disponível. A aplicação não pode continuar.")
        sys.exit(1)
    modules['wx'] = wx
    
    # pyipp (opcional - desabilita funcionalidades se não disponível)
    pyipp = safe_import('pyipp')
    if not pyipp:
        logger.warning("pyipp não disponível - funcionalidades IPP desabilitadas")
        # Cria mock do pyipp para evitar erros
        class MockPyipp:
            class Client:
                def __init__(self, *args, **kwargs):
                    raise NotImplementedError("IPP não disponível nesta instalação")
        modules['pyipp'] = MockPyipp()
    else:
        modules['pyipp'] = pyipp
    
    # Outros módulos opcionais
    optional_modules = [
        'requests',
        'pypdf',
        'watchdog',
        'yaml',
        'PIL'
    ]
    
    for mod in optional_modules:
        imported = safe_import(mod)
        if imported:
            modules[mod] = imported
            logger.info(f"✓ {mod} carregado")
        else:
            logger.warning(f"✗ {mod} não disponível")
    
    return modules

def main():
    """Função principal com tratamento de erros"""
    try:
        # Inicializa módulos
        modules = initialize_application()
        
        # Injeta módulos no namespace global para compatibilidade
        for name, module in modules.items():
            globals()[name] = module
        
        # Importa e executa o main original
        try:
            # Tenta importar main_original
            import main_original
            
            # Se tem função main, executa
            if hasattr(main_original, 'main'):
                main_original.main()
            # Se não, assume que o código executa direto
            
        except ImportError:
            logger.error("main_original.py não encontrado!")
            if modules.get('wx'):
                app = modules['wx'].App()
                modules['wx'].MessageBox(
                    "Arquivo main_original.py não encontrado.\n"
                    "Renomeie seu main.py original para main_original.py",
                    "Erro de Configuração",
                    modules['wx'].OK | modules['wx'].ICON_ERROR
                )
                app.MainLoop()
            
    except Exception as e:
        logger.exception("Erro fatal na aplicação")
        
        # Tenta mostrar erro com wx se disponível
        try:
            import wx
            app = wx.App()
            wx.MessageBox(
                f"Erro fatal: {str(e)}\n\nVerifique os logs para mais detalhes.",
                "Erro",
                wx.OK | wx.ICON_ERROR
            )
        except:
            # Fallback para print
            print(f"ERRO FATAL: {e}")
            import traceback
            traceback.print_exc()
            input("Pressione ENTER para sair...")

if __name__ == "__main__":
    main()
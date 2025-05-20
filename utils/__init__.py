"""
Módulo de inicialização para utilitários
"""
# Inicialização do pacote utils
import platform
import logging

logger = logging.getLogger("VirtualPrinter.Utils")

# Constantes de sistema
SYSTEM = platform.system().lower()
if SYSTEM == "darwin":
    SYSTEM = "macos"

# Funções de utilidade geral
def get_app_version():
    """Retorna a versão atual da aplicação"""
    return "1.0.0"

def get_platform():
    """Retorna o nome da plataforma normalizado"""
    return SYSTEM

def is_platform(name):
    """Verifica se a plataforma atual corresponde ao nome especificado"""
    if isinstance(name, str):
        return SYSTEM == name.lower()
    elif isinstance(name, (list, tuple)):
        return SYSTEM in [n.lower() for n in name]
    return False

# Inicializações adicionais para utils
def init_utils():
    """Inicializa utilitários"""
    logger.info(f"Inicializando utilitários para plataforma: {SYSTEM}")
    
    # Inicializar componentes específicos da plataforma
    
    return True

# As importações foram movidas para o final para evitar importações circulares
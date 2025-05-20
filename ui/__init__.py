"""
Módulo de inicialização para interface de usuário
"""
# Inicializar o pacote ui
from pathlib import Path

# Definir caminho de recursos
RESOURCES_DIR = Path(__file__).parent / "resources"

# Verificar e criar diretório de recursos se não existir
if not RESOURCES_DIR.exists():
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

# Inicializações adicionais para UI
def init_ui():
    """Inicializa recursos e configurações globais da UI"""
    # Verificar arquivos de recursos necessários
    
    # Inicializar recursos, temas, etc.
    
    return True

# As importações foram movidas para o final para evitar importações circulares
# e serão importadas somente quando explicitamente chamadas de outros módulos
#!/bin/bash

# Script de instalação para Linux/macOS
# Sistema de Gerenciamento de Impressão - LoQQuei

set -e  # Para no primeiro erro

APP_NAME="Sistema de Gerenciamento de Impressão"
APP_DIR="/opt/printmanagementsystem"
DESKTOP_FILE="/usr/share/applications/printmanagementsystem.desktop"
AUTOSTART_FILE="$HOME/.config/autostart/printmanagementsystem.desktop"

echo "=== Instalador do $APP_NAME ==="
echo

# Verifica se está rodando como root
if [[ $EUID -eq 0 ]]; then
    INSTALL_MODE="system"
    echo "Instalação do sistema (requer sudo)"
else
    INSTALL_MODE="user"
    APP_DIR="$HOME/.local/share/printmanagementsystem"
    DESKTOP_FILE="$HOME/.local/share/applications/printmanagementsystem.desktop"
    echo "Instalação do usuário"
fi

# Detecta o sistema operacional
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
    echo "Sistema: Linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
    echo "Sistema: macOS"
else
    echo "Sistema operacional não suportado: $OSTYPE"
    exit 1
fi

# Função para verificar se comando existe
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Verifica e instala Python
echo "Verificando Python..."
if ! command_exists python3; then
    echo "Python3 não encontrado. Instalando..."
    
    if [[ "$OS" == "linux" ]]; then
        # Detecta distribuição Linux
        if command_exists apt-get; then
            # Debian/Ubuntu
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-dev python3-venv
            sudo apt-get install -y build-essential libgtk-3-dev libwebkit2gtk-4.0-dev
        elif command_exists yum; then
            # Red Hat/CentOS/Fedora
            sudo yum install -y python3 python3-pip python3-devel
            sudo yum groupinstall -y "Development Tools"
            sudo yum install -y gtk3-devel webkit2gtk3-devel
        elif command_exists pacman; then
            # Arch Linux
            sudo pacman -S --noconfirm python python-pip gtk3 webkit2gtk
        else
            echo "Distribuição Linux não suportada. Instale Python3 manualmente."
            exit 1
        fi
    elif [[ "$OS" == "macos" ]]; then
        # macOS
        if command_exists brew; then
            brew install python3
        else
            echo "Homebrew não encontrado. Instalando..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            brew install python3
        fi
    fi
else
    echo "Python3 encontrado: $(python3 --version)"
fi

# Verifica pip
echo "Verificando pip..."
if ! command_exists pip3; then
    echo "pip3 não encontrado. Instalando..."
    python3 -m ensurepip --default-pip
fi

# Atualiza pip
echo "Atualizando pip..."
python3 -m pip install --upgrade pip

# Cria diretório da aplicação
echo "Criando diretório da aplicação: $APP_DIR"
if [[ "$INSTALL_MODE" == "system" ]]; then
    sudo mkdir -p "$APP_DIR"
    sudo chown $USER:$USER "$APP_DIR"
else
    mkdir -p "$APP_DIR"
fi

# Copia arquivos da aplicação
echo "Copiando arquivos da aplicação..."
cp -r src/ "$APP_DIR/"
cp main.py "$APP_DIR/"
cp requirements.txt "$APP_DIR/"

# Cria ambiente virtual
echo "Criando ambiente virtual..."
python3 -m venv "$APP_DIR/venv"

# Ativa ambiente virtual e instala dependências
echo "Instalando dependências..."
source "$APP_DIR/venv/bin/activate"
pip install --upgrade pip setuptools wheel

# Instala dependências específicas por plataforma
if [[ "$OS" == "linux" ]]; then
    # Instala dependências do sistema para Linux
    if command_exists apt-get; then
        sudo apt-get install -y libcups2-dev
    elif command_exists yum; then
        sudo yum install -y cups-devel
    elif command_exists pacman; then
        sudo pacman -S --noconfirm cups
    fi
fi

# Instala dependências Python
pip install -r "$APP_DIR/requirements.txt"

# Cria script de execução
echo "Criando script de execução..."
cat > "$APP_DIR/run.sh" << 'EOF'
#!/bin/bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$APP_DIR/venv/bin/activate"
python "$APP_DIR/main.py"
EOF

chmod +x "$APP_DIR/run.sh"

# Cria arquivo .desktop
echo "Criando entrada no menu..."
mkdir -p "$(dirname "$DESKTOP_FILE")"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Name=$APP_NAME
Comment=Sistema de gerenciamento de impressão
Exec=$APP_DIR/run.sh
Icon=$APP_DIR/src/ui/resources/icon.png
Terminal=false
Type=Application
Categories=Office;Utility;
StartupNotify=true
EOF

# Cria autostart
echo "Configurando inicialização automática..."
mkdir -p "$(dirname "$AUTOSTART_FILE")"
cp "$DESKTOP_FILE" "$AUTOSTART_FILE"

# Torna executável
if [[ "$INSTALL_MODE" == "system" ]]; then
    sudo chmod 644 "$DESKTOP_FILE"
fi
chmod 644 "$AUTOSTART_FILE"

# Atualiza base de dados do desktop
if command_exists update-desktop-database; then
    if [[ "$INSTALL_MODE" == "system" ]]; then
        sudo update-desktop-database /usr/share/applications
    else
        update-desktop-database "$HOME/.local/share/applications"
    fi
fi

echo
echo "=== Instalação concluída! ==="
echo "O $APP_NAME foi instalado em: $APP_DIR"
echo "Entrada criada no menu de aplicações"
echo "Configurado para iniciar automaticamente"
echo
echo "Para executar manualmente: $APP_DIR/run.sh"
echo "Para desinstalar, execute: $APP_DIR/uninstall.sh"

# Cria script de desinstalação
cat > "$APP_DIR/uninstall.sh" << EOF
#!/bin/bash
echo "Desinstalando $APP_NAME..."
rm -rf "$APP_DIR"
rm -f "$DESKTOP_FILE"
rm -f "$AUTOSTART_FILE"
echo "Desinstalação concluída!"
EOF

chmod +x "$APP_DIR/uninstall.sh"

echo
read -p "Deseja executar a aplicação agora? (s/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Ss]$ ]]; then
    "$APP_DIR/run.sh" &
    echo "Aplicação iniciada!"
fi
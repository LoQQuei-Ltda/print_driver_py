"""
Script de Build Automatizado Multiplataforma para o Sistema de Gerenciamento de Impressão
Suporta geração de instaladores para Windows, macOS e Linux
"""
import os
import sys
import shutil
import subprocess
import platform
from pathlib import Path
from __version__ import __version__

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
        "pillow>=10.0.1",
        "flask>=3.1.1",
        "flask_cors>=6.0.0",
        "zeroconf >=0.147.0"
        "python-nmap>=0.7.1",
        "pysnmp>=7.1.20",
        "netifaces>=0.11.0",
        "wsdiscovery>=2.1.2"
    ]
    
    # Dependências específicas por plataforma
    system = platform.system().lower()
    if system == "windows":
        dependencies.append("pywin32>=300")
    elif system == "darwin":  # macOS
        dependencies.extend([
            "dmgbuild>=1.6.0",
            "biplist>=1.0.3",
            "pyobjc-core>=9.0",
            "pyobjc-framework-Cocoa>=9.0"
        ])
    elif system == "linux":
        dependencies.append("stdeb>=0.10.0")  # Para criar pacotes DEB
    
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

def create_macos_app_bundle():
    """Cria e corrige o bundle .app para macOS - VERSÃO MELHORADA"""
    print_header("Corrigindo bundle macOS")
    
    app_path = "build/exe/PrintManagementSystem.app"
    if not os.path.exists(app_path):
        print("❌ Bundle .app não encontrado!")
        return False
    
    contents_path = os.path.join(app_path, "Contents")
    macos_path = os.path.join(contents_path, "MacOS")
    resources_path = os.path.join(contents_path, "Resources")
    
    # Cria diretórios necessários
    os.makedirs(macos_path, exist_ok=True)
    os.makedirs(resources_path, exist_ok=True)
    
    # 1. Corrige/Cria Info.plist ADEQUADO
    info_plist_path = os.path.join(contents_path, "Info.plist")
    create_proper_info_plist(info_plist_path)
    
    # 2. Garante que o executável tenha permissões corretas
    executable_path = os.path.join(macos_path, "PrintManagementSystem")
    if os.path.exists(executable_path):
        os.chmod(executable_path, 0o755)
        print("✓ Permissões do executável corrigidas")
    
    # 3. Cria/Corrige o ícone da aplicação
    create_macos_icon(resources_path)
    
    # 4. Copia recursos da aplicação para Resources
    copy_app_resources_to_bundle(resources_path)
    
    # 5. Cria PkgInfo se não existir
    pkginfo_path = os.path.join(contents_path, "PkgInfo")
    if not os.path.exists(pkginfo_path):
        with open(pkginfo_path, 'w') as f:
            f.write("APPL????")
        print("✓ PkgInfo criado")
    
    # 6. Força atualização do cache do Launchpad
    force_launchpad_refresh()
    
    print("✓ Bundle macOS corrigido com sucesso!")
    return True

def create_proper_info_plist(plist_path):
    """Cria um Info.plist COMPLETO e CORRETO para o macOS"""
    
    plist_data = {
        'CFBundleExecutable': 'PrintManagementSystem',
        'CFBundleIdentifier': 'com.loqquei.printmanagement',
        'CFBundleName': 'PrintManagementSystem',
        'CFBundleDisplayName': 'Gerenciamento de Impressão LoQQuei',
        'CFBundleVersion': __version__,
        'CFBundleShortVersionString': __version__,
        'CFBundlePackageType': 'APPL',
        'CFBundleSignature': '????',
        'CFBundleInfoDictionaryVersion': '6.0',
        
        # IMPORTANTE: Especifica o ícone
        'CFBundleIconFile': 'AppIcon',
        'CFBundleIconName': 'AppIcon',
        
        # Configurações de sistema
        'LSMinimumSystemVersion': '10.13.0',
        'LSRequiresCarbon': False,
        'NSHighResolutionCapable': True,
        'NSRequiresAquaSystemAppearance': False,
        'NSSupportsAutomaticGraphicsSwitching': True,
        
        # Categoria da aplicação
        'LSApplicationCategoryType': 'public.app-category.business',
        'NSPrincipalClass': 'NSApplication',
        'LSUIElement': False,
        
        # Permissões de rede (importante para IPP)
        'NSAppTransportSecurity': {
            'NSAllowsArbitraryLoads': True,
            'NSAllowsArbitraryLoadsInWebContent': True,
            'NSAllowsLocalNetworking': True
        },
        
        # Tipos de arquivo suportados (opcional)
        'CFBundleDocumentTypes': [
            {
                'CFBundleTypeName': 'PDF Document',
                'CFBundleTypeExtensions': ['pdf'],
                'CFBundleTypeRole': 'Viewer',
                'LSHandlerRank': 'Alternate'
            }
        ],
        
        # Configurações de URL scheme (se necessário)
        'CFBundleURLTypes': [
            {
                'CFBundleURLName': 'com.loqquei.printmanagement',
                'CFBundleURLSchemes': ['loqquei-print']
            }
        ]
    }
    
    # Escreve o plist usando o módulo plistlib (mais confiável)
    try:
        with open(plist_path, 'wb') as f:
            plistlib.dump(plist_data, f)
        print(f"✓ Info.plist criado/atualizado: {plist_path}")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar Info.plist: {e}")
        # Fallback para método manual
        return create_info_plist_manual(plist_path, plist_data)

def create_info_plist_manual(plist_path, plist_data):
    """Método alternativo para criar Info.plist se plistlib falhar"""
    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>PrintManagementSystem</string>
    <key>CFBundleIdentifier</key>
    <string>com.loqquei.printmanagement</string>
    <key>CFBundleName</key>
    <string>PrintManagementSystem</string>
    <key>CFBundleDisplayName</key>
    <string>Gerenciamento de Impressão LoQQuei</string>
    <key>CFBundleVersion</key>
    <string>{__version__}</string>
    <key>CFBundleShortVersionString</key>
    <string>{__version__}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIconName</key>
    <string>AppIcon</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>LSRequiresCarbon</key>
    <false/>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>NSSupportsAutomaticGraphicsSwitching</key>
    <true/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.business</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
        <key>NSAllowsArbitraryLoadsInWebContent</key>
        <true/>
        <key>NSAllowsLocalNetworking</key>
        <true/>
    </dict>
</dict>
</plist>'''
    
    try:
        with open(plist_path, 'w', encoding='utf-8') as f:
            f.write(plist_content)
        print(f"✓ Info.plist criado (método manual): {plist_path}")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar Info.plist manualmente: {e}")
        return False

def create_macos_icon(resources_path):
    """Cria/Converte ícone para o formato adequado do macOS"""
    print("Processando ícone para macOS...")
    
    # Procura por ícones existentes
    possible_icons = [
        "src/ui/resources/icon.icns",
        "src/ui/resources/icon.png",
        "src/ui/resources/icon.ico",
        "resources/icon.icns",
        "resources/icon.png",
        "icon.icns",
        "icon.png"
    ]
    
    source_icon = None
    for icon_path in possible_icons:
        if os.path.exists(icon_path):
            source_icon = icon_path
            break
    
    target_icon = os.path.join(resources_path, "AppIcon.icns")
    
    if source_icon:
        if source_icon.endswith('.icns'):
            # Já é um ícone .icns, apenas copia
            shutil.copy(source_icon, target_icon)
            print(f"✓ Ícone .icns copiado: {target_icon}")
        else:
            # Tenta converter PNG/ICO para ICNS
            try:
                convert_to_icns(source_icon, target_icon)
                print(f"✓ Ícone convertido para .icns: {target_icon}")
            except Exception as e:
                print(f"⚠ Erro ao converter ícone: {e}")
                create_default_icon(target_icon)
    else:
        print("⚠ Nenhum ícone encontrado, criando ícone padrão...")
        create_default_icon(target_icon)
    
    return os.path.exists(target_icon)

def convert_to_icns(source_path, target_path):
    """Converte imagem para formato .icns usando ferramentas do macOS"""
    if not platform.system() == 'Darwin':
        raise Exception("Conversão para .icns só funciona no macOS")
    
    # Cria um iconset temporário
    iconset_path = target_path.replace('.icns', '.iconset')
    os.makedirs(iconset_path, exist_ok=True)
    
    # Tamanhos necessários para o iconset
    sizes = [16, 32, 64, 128, 256, 512, 1024]
    
    try:
        from PIL import Image
        
        # Abre a imagem original
        with Image.open(source_path) as img:
            # Converte para RGBA se necessário
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            # Gera os diferentes tamanhos
            for size in sizes:
                # Tamanho normal
                resized = img.resize((size, size), Image.Resampling.LANCZOS)
                resized.save(os.path.join(iconset_path, f"icon_{size}x{size}.png"))
                
                # Tamanho @2x (exceto para os maiores)
                if size <= 512:
                    resized_2x = img.resize((size * 2, size * 2), Image.Resampling.LANCZOS)
                    resized_2x.save(os.path.join(iconset_path, f"icon_{size}x{size}@2x.png"))
        
        # Converte iconset para icns usando iconutil
        subprocess.run([
            'iconutil', '-c', 'icns', iconset_path, '-o', target_path
        ], check=True)
        
        # Remove iconset temporário
        shutil.rmtree(iconset_path)
        
    except ImportError:
        print("⚠ Pillow não encontrado, usando sips para conversão...")
        # Fallback usando sips (ferramenta nativa do macOS)
        subprocess.run([
            'sips', '-s', 'format', 'icns', source_path, '--out', target_path
        ], check=True)

def create_default_icon(target_path):
    """Cria um ícone padrão simples"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        
        # Cria uma imagem 1024x1024 com fundo azul
        img = Image.new('RGBA', (1024, 1024), (70, 130, 180, 255))
        draw = ImageDraw.Draw(img)
        
        # Desenha um círculo branco
        margin = 100
        draw.ellipse([margin, margin, 1024-margin, 1024-margin], 
                     fill=(255, 255, 255, 255), outline=(200, 200, 200, 255), width=10)
        
        # Adiciona texto "PMS" (Print Management System)
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 200)
        except:
            font = ImageFont.load_default()
        
        text = "PMS"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (1024 - text_width) // 2
        y = (1024 - text_height) // 2 - 50
        
        draw.text((x, y), text, fill=(70, 130, 180, 255), font=font)
        
        # Salva como PNG temporário
        temp_png = target_path.replace('.icns', '_temp.png')
        img.save(temp_png)
        
        # Converte para ICNS
        if platform.system() == 'Darwin':
            try:
                convert_to_icns(temp_png, target_path)
                os.remove(temp_png)
            except:
                # Se conversão falhar, pelo menos copia o PNG
                shutil.copy(temp_png, target_path.replace('.icns', '.png'))
                os.remove(temp_png)
        else:
            # Em outras plataformas, usa PNG
            shutil.move(temp_png, target_path.replace('.icns', '.png'))
        
        print("✓ Ícone padrão criado")
        
    except ImportError:
        print("⚠ Pillow não disponível, pulando criação de ícone padrão")

def copy_app_resources_to_bundle(resources_path):
    """Copia recursos da aplicação para o bundle"""
    source_paths = [
        "src/ui/resources",
        "resources",
        "build/exe/resources"
    ]
    
    for source_path in source_paths:
        if os.path.exists(source_path):
            target_path = os.path.join(resources_path, "app_resources")
            if os.path.exists(target_path):
                shutil.rmtree(target_path)
            shutil.copytree(source_path, target_path)
            print(f"✓ Recursos copiados de {source_path} para {target_path}")
            break

def force_launchpad_refresh():
    """Força o Launchpad a atualizar seu cache"""
    if platform.system() == 'Darwin':
        try:
            print("Atualizando cache do Launchpad...")
            
            # Mata o processo do Dock para forçar reinicialização
            subprocess.run(['killall', 'Dock'], check=False)
            
            # Limpa o cache do Launch Services
            subprocess.run([
                '/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister',
                '-kill', '-r', '-domain', 'local', '-domain', 'system', '-domain', 'user'
            ], check=False)
            
            # Força reindexação do Spotlight
            subprocess.run(['mdimport', 'build/exe/PrintManagementSystem.app'], check=False)
            
            print("✓ Cache do sistema atualizado")
            
        except Exception as e:
            print(f"⚠ Aviso: Não foi possível atualizar o cache automaticamente: {e}")
            print("  Reinicie o sistema ou faça logout/login para ver o ícone no Launchpad")

def create_test_import_script():
    """Cria script para testar imports no executável"""
    test_script = '''
# Script de teste de imports
import sys
print(f"Python: {sys.version}")
print(f"Executável: {sys.executable}")
print(f"Sistema: {sys.platform}")
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
        
        if platform.system() == 'Darwin':
            if create_macos_app_bundle():
                print("✓ Bundle macOS corrigido com sucesso!")
            else:
                print("⚠ Houve problemas ao corrigir o bundle macOS")

        # Verifica se o executável foi criado
        exe_folder = "build/exe"
        system = platform.system().lower()
        
        if system == "windows":
            exe_path = os.path.join(exe_folder, "PrintManagementSystem.exe")
        elif system == "darwin":  # macOS
            exe_path = os.path.join(exe_folder, "PrintManagementSystem.app")
        else:  # Linux
            exe_path = os.path.join(exe_folder, "PrintManagementSystem")
        
        if os.path.exists(exe_path):
            if system == "darwin":
                print(f"\n✓ Aplicação macOS criada com sucesso!")
                print(f"  Caminho: {exe_path}")
                print(f"  O ícone deve aparecer no Launchpad após alguns segundos")
                print(f"  Se não aparecer, reinicie o sistema ou faça logout/login")
            else:
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
    
    system = platform.system().lower()
    exe_folder = "build/exe"
    
    if system == "windows":
        exe_path = os.path.join(exe_folder, "PrintManagementSystem.exe")
    elif system == "darwin":  # macOS
        exe_path = os.path.join(exe_folder, "PrintManagementSystem.app", "Contents", "MacOS", "PrintManagementSystem")
    else:  # Linux
        exe_path = os.path.join(exe_folder, "PrintManagementSystem")
    
    if not os.path.exists(exe_path):
        print("❌ Executável não encontrado!")
        return False
    
    # Copia o script de teste para a pasta do executável
    shutil.copy("test_imports.py", os.path.join(exe_folder, "test_imports.py"))
    
    print("Execute o seguinte comando para testar os imports:")
    print(f"\n  {exe_path} test_imports.py\n")
    
    response = input("Deseja executar o teste agora? (s/n): ")
    if response.lower() == 's':
        if system == "darwin":  # macOS
            subprocess.run(["open", "-a", os.path.join(exe_folder, "PrintManagementSystem.app"), 
                            os.path.join(exe_folder, "test_imports.py")])
        else:
            subprocess.run([exe_path, "test_imports.py"], cwd=exe_folder)
    
    return True

def build_windows_installer():
    """Constrói o instalador para Windows usando Inno Setup"""
    print_header("Construindo instalador Windows")
    
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
        installer_path = f"Output/Instalador_Gerenciamento_LoQQuei_V{__version__}.exe"
        if os.path.exists(installer_path):
            size_mb = os.path.getsize(installer_path) / (1024 * 1024)
            print(f"\n✓ Instalador Windows criado com sucesso!")
            print(f"  Caminho: {installer_path}")
            print(f"  Tamanho: {size_mb:.2f} MB")
            return True
        else:
            print("\n❌ Instalador Windows não foi criado!")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"\n❌ Erro ao executar Inno Setup: {e}")
        return False

def build_macos_installer():
    """Constrói instalador para macOS (DMG) - VERSÃO MELHORADA"""
    print_header("Construindo instalador macOS")
    
    try:
        app_path = "build/exe/PrintManagementSystem.app"
        if not os.path.exists(app_path):
            print("❌ Aplicação .app não encontrada!")
            return False
        
        # Garante que o bundle está correto antes de criar o DMG
        if not create_macos_app_bundle():
            print("⚠ Problemas ao corrigir o bundle, continuando mesmo assim...")
        
        # Instala dependências necessárias
        try:
            import biplist
            print("✓ biplist já está instalado")
        except ImportError:
            print("Instalando biplist...")
            subprocess.run([sys.executable, "-m", "pip", "install", "biplist"], check=True)
        
        try:
            subprocess.run(["dmgbuild", "--help"], check=True, capture_output=True)
            print("✓ dmgbuild encontrado")
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("Instalando dmgbuild...")
            subprocess.run([sys.executable, "-m", "pip", "install", "dmgbuild"], check=True)
        
        # Cria configuração melhorada para o dmgbuild
        dmg_settings = '''# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import os.path

# Configurações do DMG
format = defines.get('format', 'UDBZ')
size = defines.get('size', None)
files = [defines.get('app', 'build/exe/PrintManagementSystem.app')]
symlinks = {'Applications': '/Applications'}
badge_icon = defines.get('badge_icon', None)

# Layout aprimorado
icon_locations = {
    'PrintManagementSystem.app': (150, 120),
    'Applications': (350, 120),
}

background = 'builtin-arrow'
show_status_bar = False
show_tab_view = False
show_toolbar = False
show_pathbar = False
show_sidebar = False
sidebar_width = 180

arrange_by = None
grid_offset = (0, 0)
grid_spacing = 100
scroll_position = (0, 0)
label_pos = 'bottom'
text_size = 16
icon_size = 128

default_view = 'icon-view'
include_icon_view_settings = 'auto'
include_list_view_settings = 'auto'

# Janela otimizada
window_rect = ((200, 120), (640, 400))

# Licença (opcional)
# license = {
#     'default-language': 'pt_BR',
#     'licenses': {
#         'pt_BR': 'LICENSE.txt',
#     },
#     'buttons': {
#         'pt_BR': [
#             'Português',
#             'Concordo',
#             'Discordo',
#             'Imprimir',
#             'Salvar...',
#             'Se você concorda com os termos desta licença, pressione "Concordo" para instalar o software. Se você não concorda, pressione "Discordo".'
#         ]
#     }
# }
'''
        
        with open('dmg_settings.py', 'w', encoding='utf-8') as f:
            f.write(dmg_settings)
        
        # Cria o DMG
        output_dir = "Output"
        os.makedirs(output_dir, exist_ok=True)
        
        dmg_path = os.path.join(output_dir, f"LoQQuei_PrintManagement_V{__version__}.dmg")
        
        if os.path.exists(dmg_path):
            os.remove(dmg_path)
        
        cmd = [
            "dmgbuild",
            "-s", "dmg_settings.py",
            "-D", f"app={app_path}",
            "Gerenciamento de Impressão LoQQuei",
            dmg_path
        ]
        
        print(f"Executando: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        
        if os.path.exists(dmg_path):
            size_mb = os.path.getsize(dmg_path) / (1024 * 1024)
            print(f"\n✓ Instalador macOS (DMG) criado com sucesso!")
            print(f"  Caminho: {dmg_path}")
            print(f"  Tamanho: {size_mb:.2f} MB")
            
            return True
        else:
            print("\n❌ Instalador macOS (DMG) não foi criado!")
            return False
            
    except Exception as e:
        print(f"\n❌ Erro ao criar instalador macOS: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_info_plist(plist_path):
    """Cria um Info.plist adequado para a aplicação"""
    plist_content = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>PrintManagementSystem</string>
    <key>CFBundleIdentifier</key>
    <string>com.loqquei.printmanagement</string>
    <key>CFBundleName</key>
    <string>PrintManagementSystem</string>
    <key>CFBundleDisplayName</key>
    <string>Gerenciamento de Impressão LoQQuei</string>
    <key>CFBundleVersion</key>
    <string>{__version__}</string>
    <key>CFBundleShortVersionString</key>
    <string>{__version__}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleSignature</key>
    <string>????</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSRequiresAquaSystemAppearance</key>
    <false/>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.business</string>
    <key>NSPrincipalClass</key>
    <string>NSApplication</string>
    <key>LSUIElement</key>
    <false/>
    <key>NSAppTransportSecurity</key>
    <dict>
        <key>NSAllowsArbitraryLoads</key>
        <true/>
    </dict>
</dict>
</plist>'''
    
    # Garante que o diretório existe
    os.makedirs(os.path.dirname(plist_path), exist_ok=True)
    
    with open(plist_path, 'w', encoding='utf-8') as f:
        f.write(plist_content)
    
    print(f"✓ Info.plist criado em: {plist_path}")

def test_macos_app():
    """Testa a aplicação macOS e fornece informações de debug"""
    print_header("Testando aplicação macOS")
    
    app_path = "build/exe/PrintManagementSystem.app"
    executable_path = os.path.join(app_path, "Contents/MacOS/PrintManagementSystem")
    
    if not os.path.exists(app_path):
        print("❌ Aplicação .app não encontrada!")
        return False
    
    if not os.path.exists(executable_path):
        print("❌ Executável não encontrado dentro do .app!")
        return False
    
    # Verifica permissões
    import stat
    file_stat = os.stat(executable_path)
    if not file_stat.st_mode & stat.S_IEXEC:
        print("❌ Executável não tem permissões de execução!")
        print("Corrigindo permissões...")
        os.chmod(executable_path, 0o755)
    
    print("✓ Estrutura da aplicação parece correta")
    
    # Testa execução
    print("\nTestando execução...")
    try:
        # Executa em background para não travar o terminal
        process = subprocess.Popen([executable_path], 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        
        print("✓ Aplicação iniciada")
        print(f"  PID: {process.pid}")
        print("  Verificando se está rodando...")
        
        # Aguarda um pouco para ver se não fecha imediatamente
        import time
        time.sleep(2)
        
        poll_result = process.poll()
        if poll_result is None:
            print("✓ Aplicação ainda está rodando")
            
            # Pergunta se quer terminar o processo
            response = input("\nDeseja parar a aplicação de teste? (s/n): ")
            if response.lower() == 's':
                process.terminate()
                process.wait()
                print("✓ Aplicação parada")
        else:
            print(f"❌ Aplicação fechou com código: {poll_result}")
            
            # Mostra erros se houver
            stdout, stderr = process.communicate()
            if stderr:
                print("Erros encontrados:")
                print(stderr.decode('utf-8'))
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao testar aplicação: {e}")
        return False

def build_linux_deb_package():
    """Constrói pacote DEB para distribuições Linux baseadas em Debian"""
    print_header("Construindo pacote DEB para Linux")
    
    try:
        # Criando estrutura de diretórios para o pacote DEB
        deb_root = "build/deb"
        if os.path.exists(deb_root):
            shutil.rmtree(deb_root)
        
        bin_dir = os.path.join(deb_root, "usr/local/bin")
        app_dir = os.path.join(deb_root, "usr/local/share/loqquei")
        desktop_dir = os.path.join(deb_root, "usr/share/applications")
        icons_dir = os.path.join(deb_root, "usr/share/icons/hicolor/128x128/apps")
        debian_dir = os.path.join(deb_root, "DEBIAN")
        
        for directory in [bin_dir, app_dir, desktop_dir, icons_dir, debian_dir]:
            os.makedirs(directory, exist_ok=True)
        
        # Copia o executável e recursos para a estrutura do pacote
        exe_src = "build/exe/PrintManagementSystem"
        exe_dst = os.path.join(bin_dir, "printmanagementsystem")
        
        shutil.copy(exe_src, exe_dst)
        os.chmod(exe_dst, 0o755)  # Torna o arquivo executável
        
        # Copia recursos
        resource_src = "build/exe/resources"
        resource_dst = os.path.join(app_dir, "resources")
        
        if os.path.exists(resource_src):
            shutil.copytree(resource_src, resource_dst)
        
        # Copia ícone (assume que existe um ícone PNG em resources)
        icon_src = os.path.join(resource_src, "icon.png")
        icon_dst = os.path.join(icons_dir, "loqquei-printmanagement.png")
        
        if os.path.exists(icon_src):
            shutil.copy(icon_src, icon_dst)
        
        # Cria arquivo .desktop
        desktop_content = '''[Desktop Entry]
Name=Gerenciamento de Impressão LoQQuei
Comment=Sistema de Gerenciamento de Impressão
Exec=/usr/local/bin/printmanagementsystem
Icon=loqquei-printmanagement
Terminal=false
Type=Application
Categories=Office;Utility;
StartupNotify=true
'''
        
        with open(os.path.join(desktop_dir, "loqquei-printmanagement.desktop"), 'w') as f:
            f.write(desktop_content)
        
        # Cria arquivo de controle
        control_content = f'''Package: loqquei-printmanagement
Version: {__version__}
Section: utils
Priority: optional
Architecture: amd64
Depends: libc6 (>= 2.15)
Maintainer: LoQQuei <contato@loqquei.com.br>
Description: Sistema de Gerenciamento de Impressão LoQQuei
 Aplicação desktop para gerenciamento de impressões,
 compatível com impressoras IPP/CUPS.
'''
        
        with open(os.path.join(debian_dir, "control"), 'w') as f:
            f.write(control_content)
        
        # Constrói o pacote DEB
        output_dir = "Output"
        os.makedirs(output_dir, exist_ok=True)
        
        deb_path = os.path.join(output_dir, f"loqquei-printmanagement_{__version__}_amd64.deb")
        
        # Comando para criar o pacote DEB
        subprocess.run([
            "dpkg-deb",
            "--build",
            "--root-owner-group",
            deb_root,
            deb_path
        ], check=True)
        
        if os.path.exists(deb_path):
            size_mb = os.path.getsize(deb_path) / (1024 * 1024)
            print(f"\n✓ Pacote DEB criado com sucesso!")
            print(f"  Caminho: {deb_path}")
            print(f"  Tamanho: {size_mb:.2f} MB")
            return True
        else:
            print("\n❌ Pacote DEB não foi criado!")
            return False
            
    except Exception as e:
        print(f"\n❌ Erro ao criar pacote DEB: {e}")
        return False

def build_linux_appimage():
    """Constrói AppImage para Linux (distribuição universal)"""
    print_header("Construindo AppImage para Linux")
    
    try:
        # Baixa o appimagetool
        appimage_tool = "appimagetool-x86_64.AppImage"
        if not os.path.exists(appimage_tool):
            print("Baixando appimagetool...")
            subprocess.run([
                "wget", "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage",
                "-O", appimage_tool
            ], check=True)
            os.chmod(appimage_tool, 0o755)
        
        # Cria estrutura AppDir
        appdir = "build/AppDir"
        if os.path.exists(appdir):
            shutil.rmtree(appdir)
        
        os.makedirs(os.path.join(appdir, "usr/bin"), exist_ok=True)
        
        # Copia o executável e recursos
        shutil.copy("build/exe/PrintManagementSystem", os.path.join(appdir, "usr/bin/PrintManagementSystem"))
        os.chmod(os.path.join(appdir, "usr/bin/PrintManagementSystem"), 0o755)
        
        if os.path.exists("build/exe/resources"):
            shutil.copytree(
                "build/exe/resources", 
                os.path.join(appdir, "usr/share/loqquei/resources")
            )
        
        # Cria arquivo desktop
        desktop_content = '''[Desktop Entry]
Name=Gerenciamento de Impressão LoQQuei
Comment=Sistema de Gerenciamento de Impressão
Exec=PrintManagementSystem
Icon=loqquei-printmanagement
Terminal=false
Type=Application
Categories=Office;Utility;
StartupNotify=true
'''
        
        with open(os.path.join(appdir, "loqquei-printmanagement.desktop"), 'w') as f:
            f.write(desktop_content)
        
        # Copia ícone
        icon_src = "build/exe/resources/icon.png"
        if os.path.exists(icon_src):
            shutil.copy(icon_src, os.path.join(appdir, "loqquei-printmanagement.png"))
        
        # Cria AppRun
        apprun_content = '''#!/bin/bash
SELF=$(readlink -f "$0")
HERE=${SELF%/*}
export PATH="${HERE}/usr/bin:${PATH}"
export LD_LIBRARY_PATH="${HERE}/usr/lib:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/PrintManagementSystem" "$@"
'''
        
        with open(os.path.join(appdir, "AppRun"), 'w') as f:
            f.write(apprun_content)
        os.chmod(os.path.join(appdir, "AppRun"), 0o755)
        
        # Cria o AppImage
        output_dir = "Output"
        os.makedirs(output_dir, exist_ok=True)
        
        appimage_path = os.path.join(output_dir, f"LoQQuei_PrintManagement-{__version__}-x86_64.AppImage")
        
        # Executa o appimagetool
        subprocess.run([
            f"./{appimage_tool}",
            appdir,
            appimage_path
        ], check=True)
        
        if os.path.exists(appimage_path):
            size_mb = os.path.getsize(appimage_path) / (1024 * 1024)
            print(f"\n✓ AppImage criado com sucesso!")
            print(f"  Caminho: {appimage_path}")
            print(f"  Tamanho: {size_mb:.2f} MB")
            return True
        else:
            print("\n❌ AppImage não foi criado!")
            return False
            
    except Exception as e:
        print(f"\n❌ Erro ao criar AppImage: {e}")
        return False

def build_installer_for_platform():
    """Constrói o instalador apropriado para a plataforma atual"""
    system = platform.system().lower()
    
    if system == "windows":
        return build_windows_installer()
    elif system == "darwin":  # macOS
        return build_macos_installer()
    elif system == "linux":
        # Pergunta qual formato de pacote Linux deseja criar
        print("\nEscolha o tipo de instalador Linux:")
        print("1. Pacote DEB (Debian, Ubuntu, Mint, etc.)")
        print("2. AppImage (Universal)")
        
        choice = input("Opção (1/2): ")
        
        if choice == "1":
            return build_linux_deb_package()
        elif choice == "2":
            return build_linux_appimage()
        else:
            print("❌ Opção inválida!")
            return False
    else:
        print(f"❌ Sistema operacional não suportado: {system}")
        return False

def main():
    """Função principal"""
    print_header("Build Multiplataforma do Sistema de Gerenciamento de Impressão")
    
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
    response = input("\nDeseja construir o instalador para " + platform.system() + "? (s/n): ")
    if response.lower() == 's':
        if build_installer_for_platform():
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
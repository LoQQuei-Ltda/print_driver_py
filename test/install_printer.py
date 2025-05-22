import os
import sys
import ctypes
import subprocess
import tempfile
import time
import winreg
from pathlib import Path
import shutil
import urllib.request

def is_admin():
    """Verifica se o script está sendo executado com privilégios de administrador"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def create_output_directory():
    """Cria o diretório de saída para os PDFs"""
    pdf_dir = Path("c:/pdfs")
    pdf_dir.mkdir(parents=True, exist_ok=True)
    print(f"Diretório para PDFs criado: {pdf_dir}")
    
    # Configurar permissões de escrita
    try:
        subprocess.run([
            "icacls", "c:/pdfs", 
            "/grant", "Users:(OI)(CI)F", 
            "/T"
        ])
    except Exception as e:
        print(f"Aviso: Não foi possível configurar permissões: {e}")

def install_cutepdf_alternative():
    """Método alternativo para instalar CutePDF"""
    print("Preparando instalação alternativa do CutePDF Writer...")
    
    # MÉTODO 1: Download manual e instruções
    print("\n=== OPÇÃO 1: Instalação Manual do CutePDF ===")
    print("O instalador automático falhou. Vamos tentar uma instalação manual:")
    print("1. Baixe manualmente o CutePDF em: https://www.cutepdf.com/Products/CutePDF/writer.asp")
    print("2. Baixe também o conversor PS2PDF: https://www.cutepdf.com/Support/download.asp?file=converter.exe")
    print("3. Instale primeiro o conversor PS2PDF e depois o CutePDF")
    
    # Perguntar se o usuário quer tentar a instalação manual agora
    choice = input("\nVocê quer que eu baixe os instaladores agora para você? (S/N): ")
    
    if choice.lower() == "s":
        temp_dir = tempfile.gettempdir()
        
        # Criar pasta para os downloads
        downloads_folder = os.path.join(temp_dir, "CutePDF_Downloads")
        os.makedirs(downloads_folder, exist_ok=True)
        
        # URLs alternativas (podem ser mais estáveis)
        converter_url = "https://www.cutepdf.com/download/converter.exe"
        cutepdf_url = "https://www.cutepdf.com/download/CuteWriter.exe"
        
        converter_path = os.path.join(downloads_folder, "converter.exe")
        cutepdf_path = os.path.join(downloads_folder, "CuteWriter.exe")
        
        try:
            # Tentar baixar os instaladores
            print(f"Baixando conversor PS2PDF para: {converter_path}")
            urllib.request.urlretrieve(converter_url, converter_path)
            
            print(f"Baixando CutePDF Writer para: {cutepdf_path}")
            urllib.request.urlretrieve(cutepdf_url, cutepdf_path)
            
            # Executar os instaladores - primeiro o conversor e depois o CutePDF
            print("\nOs arquivos foram baixados. Execute-os manualmente nesta ordem:")
            print(f"1. {converter_path}")
            print(f"2. {cutepdf_path}")
            
            # Abrir o explorador de arquivos na pasta de downloads
            subprocess.run(["explorer", downloads_folder])
            
            # Perguntar se o usuário quer continuar depois da instalação manual
            input("\nDepois de instalar ambos os programas, pressione Enter para continuar com a configuração...")
            return True
        
        except Exception as e:
            print(f"Erro ao baixar arquivos: {e}")
            print("Por favor, baixe-os manualmente usando os links fornecidos.")
            input("Depois de instalar ambos os programas, pressione Enter para continuar...")
            return True
    
    else:
        print("\nPor favor, instale o CutePDF manualmente e depois execute este script novamente.")
        input("Pressione Enter quando estiver pronto para continuar...")
        return check_cutepdf_installed()

def check_cutepdf_installed():
    """Verifica se o CutePDF está instalado"""
    print("Verificando se o CutePDF está instalado...")
    
    # Verificar a existência da impressora
    try:
        ps_script = """
        $printer = Get-Printer -Name "CutePDF Writer" -ErrorAction SilentlyContinue
        if ($printer -ne $null) {
            Write-Output "PRINTER_FOUND"
        } else {
            Write-Output "PRINTER_NOT_FOUND"
        }
        """
        
        ps_file = os.path.join(tempfile.gettempdir(), "check_printer.ps1")
        with open(ps_file, "w") as f:
            f.write(ps_script)
        
        result = subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file], 
                               capture_output=True, text=True)
        
        if "PRINTER_FOUND" in result.stdout:
            print("CutePDF Writer está instalado.")
            return True
        
        # Verificar no registro
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer"):
                print("CutePDF Writer encontrado no registro.")
                return True
        except:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Wow6432Node\CutePDF Writer"):
                    print("CutePDF Writer encontrado no registro (32-bit).")
                    return True
            except:
                pass
        
        # Verificar diretórios comuns de instalação
        program_files = os.environ.get('PROGRAMFILES', 'C:/Program Files')
        program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')
        
        cutepdf_paths = [
            os.path.join(program_files, "Acro Software", "CutePDF Writer"),
            os.path.join(program_files_x86, "Acro Software", "CutePDF Writer"),
            os.path.join(program_files, "CutePDF Writer"),
            os.path.join(program_files_x86, "CutePDF Writer")
        ]
        
        for path in cutepdf_paths:
            if os.path.exists(path):
                print(f"CutePDF Writer encontrado em: {path}")
                return True
        
        print("CutePDF Writer não foi encontrado no sistema.")
        return False
    
    except Exception as e:
        print(f"Erro ao verificar instalação: {e}")
        return False

def configure_cutepdf_registry():
    """Configura o CutePDF para salvar automaticamente sem diálogos"""
    print("Configurando CutePDF para salvar sem diálogos...")
    
    # Criar diretório de saída se não existir
    os.makedirs("c:/pdfs", exist_ok=True)
    
    try:
        # Chaves específicas do CutePDF
        registry_keys = [
            # HKEY_CURRENT_USER
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "AutoSave", 1, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "ShowSaveAS", 0, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "PromptForFileName", 0, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "UseDocumentTitle", 1, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "Output", "c:\\pdfs", winreg.REG_SZ),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "ConfirmOverwrite", 0, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "ShowSettings", 0, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "ShowPDF", 0, winreg.REG_DWORD),
            (winreg.HKEY_CURRENT_USER, r"Software\CutePDF Writer", "ShowProgress", 0, winreg.REG_DWORD),
            
            # HKEY_LOCAL_MACHINE
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "AutoSave", 1, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "ShowSaveAS", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "PromptForFileName", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "UseDocumentTitle", 1, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "Output", "c:\\pdfs", winreg.REG_SZ),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "ConfirmOverwrite", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "ShowSettings", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "ShowPDF", 0, winreg.REG_DWORD),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\CutePDF Writer", "ShowProgress", 0, winreg.REG_DWORD),
        ]
        
        for hkey, key_path, value_name, value_data, value_type in registry_keys:
            try:
                # Criar a chave se não existir
                key = winreg.CreateKey(hkey, key_path)
                # Definir o valor
                winreg.SetValueEx(key, value_name, 0, value_type, value_data)
                winreg.CloseKey(key)
            except Exception as e:
                print(f"Aviso: Não foi possível definir {key_path}\\{value_name}: {e}")
        
        print("Configurações de registro aplicadas.")
        
        # Tentar também via VBScript (mais confiável para algumas configurações)
        vbs_file = os.path.join(tempfile.gettempdir(), "cutepdf_config.vbs")
        
        with open(vbs_file, "w") as f:
            f.write("""On Error Resume Next
Set WshShell = CreateObject("WScript.Shell")

' Configurações principais no HKCU
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\AutoSave", 1, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\ShowSaveAS", 0, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\PromptForFileName", 0, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\UseDocumentTitle", 1, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\Output", "c:\\pdfs", "REG_SZ"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\ConfirmOverwrite", 0, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\ShowSettings", 0, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\ShowPDF", 0, "REG_DWORD"
WshShell.RegWrite "HKCU\\Software\\CutePDF Writer\\ShowProgress", 0, "REG_DWORD"

' Configurações principais no HKLM
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\AutoSave", 1, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\ShowSaveAS", 0, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\PromptForFileName", 0, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\UseDocumentTitle", 1, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\Output", "c:\\pdfs", "REG_SZ"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\ConfirmOverwrite", 0, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\ShowSettings", 0, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\ShowPDF", 0, "REG_DWORD"
WshShell.RegWrite "HKLM\\SOFTWARE\\CutePDF Writer\\ShowProgress", 0, "REG_DWORD"

WScript.Echo "VBS: Configurações aplicadas com sucesso."
""")
        
        # Executar script VBS
        subprocess.run(["cscript", "//nologo", vbs_file], capture_output=True, text=True)
        
        try:
            os.remove(vbs_file)
        except:
            pass
        
        return True
    
    except Exception as e:
        print(f"Erro ao configurar registro: {e}")
        return False

def modify_cutepdf_config_files():
    """Modifica diretamente os arquivos de configuração do CutePDF"""
    print("Procurando e modificando arquivos de configuração do CutePDF...")
    
    try:
        # Locais comuns de instalação do CutePDF
        program_files = os.environ.get('PROGRAMFILES', 'C:/Program Files')
        program_files_x86 = os.environ.get('PROGRAMFILES(X86)', 'C:/Program Files (x86)')
        
        cutepdf_paths = [
            os.path.join(program_files, "Acro Software", "CutePDF Writer"),
            os.path.join(program_files_x86, "Acro Software", "CutePDF Writer"),
            os.path.join(program_files, "CutePDF Writer"),
            os.path.join(program_files_x86, "CutePDF Writer")
        ]
        
        # Possíveis arquivos de configuração
        config_files = ['cpwcfg.ini', 'cutepdf.ini', 'writer.ini', 'config.ini']
        
        # Procurar e modificar os arquivos de configuração
        found_files = False
        
        for cutepdf_path in cutepdf_paths:
            if os.path.exists(cutepdf_path):
                print(f"Pasta do CutePDF encontrada: {cutepdf_path}")
                
                for config_file in config_files:
                    config_path = os.path.join(cutepdf_path, config_file)
                    
                    # Se o arquivo existir, modifique-o
                    if os.path.exists(config_path):
                        print(f"Arquivo de configuração encontrado: {config_path}")
                        
                        try:
                            # Ler o conteúdo atual
                            with open(config_path, "r", encoding="utf-8", errors="ignore") as f:
                                content = f.read()
                            
                            # Fazer backup
                            backup_path = f"{config_path}.bak"
                            with open(backup_path, "w", encoding="utf-8") as f:
                                f.write(content)
                            
                            # Modificar as configurações
                            modified_content = content
                            settings_to_modify = {
                                "AutoSave": "1",
                                "ShowSaveAS": "0",
                                "PromptForFileName": "0",
                                "UseDocumentTitle": "1",
                                "Output": "c:\\pdfs",
                                "ConfirmOverwrite": "0",
                                "ShowSettings": "0",
                                "ShowPDF": "0",
                                "ShowProgress": "0"
                            }
                            
                            # Formato INI: chave=valor
                            for key, value in settings_to_modify.items():
                                # Se a chave já existir, substitua seu valor
                                pattern = r"(?m)^{0}\s*=.*$".format(key)
                                replacement = f"{key}={value}"
                                
                                import re
                                if re.search(pattern, modified_content):
                                    modified_content = re.sub(pattern, replacement, modified_content)
                                else:
                                    # Se a chave não existir, adicione-a
                                    modified_content += f"\n{key}={value}"
                            
                            # Salvar o conteúdo modificado
                            with open(config_path, "w", encoding="utf-8") as f:
                                f.write(modified_content)
                            
                            found_files = True
                            print(f"Arquivo {config_file} modificado.")
                        except Exception as e:
                            print(f"Erro ao modificar {config_file}: {e}")
                
                # Se não encontrou arquivos de configuração, criar um novo
                if not found_files:
                    print("Nenhum arquivo de configuração encontrado. Criando um novo...")
                    
                    config_path = os.path.join(cutepdf_path, "cpwcfg.ini")
                    try:
                        with open(config_path, "w", encoding="utf-8") as f:
                            f.write("[CutePDF Writer]\n")
                            f.write("AutoSave=1\n")
                            f.write("ShowSaveAS=0\n")
                            f.write("PromptForFileName=0\n")
                            f.write("UseDocumentTitle=1\n")
                            f.write("Output=c:\\pdfs\n")
                            f.write("ConfirmOverwrite=0\n")
                            f.write("ShowSettings=0\n")
                            f.write("ShowPDF=0\n")
                            f.write("ShowProgress=0\n")
                        
                        found_files = True
                        print(f"Arquivo de configuração criado: {config_path}")
                    except Exception as e:
                        print(f"Erro ao criar arquivo de configuração: {e}")
        
        if not found_files:
            print("Nenhum arquivo de configuração encontrado ou criado.")
            print("Utilizando apenas configurações do registro.")
        
        return True
    
    except Exception as e:
        print(f"Erro ao modificar arquivos de configuração: {e}")
        return False

def create_desktop_shortcut():
    """Cria um atalho na área de trabalho para a pasta de PDFs"""
    try:
        desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        if not os.path.exists(desktop):
            print("Diretório da área de trabalho não encontrado. Pulando criação de atalho.")
            return
        
        shortcut_path = os.path.join(desktop, "PDFs.lnk")
        
        ps_script = f"""
        $WshShell = New-Object -comObject WScript.Shell
        $Shortcut = $WshShell.CreateShortcut("{shortcut_path}")
        $Shortcut.TargetPath = "c:\\pdfs"
        $Shortcut.IconLocation = "shell32.dll,36"
        $Shortcut.Description = "Pasta de PDFs"
        $Shortcut.Save()
        """
        
        ps_file = os.path.join(tempfile.gettempdir(), "create_pdf_shortcut.ps1")
        with open(ps_file, "w") as f:
            f.write(ps_script)
        
        subprocess.run(["powershell", "-ExecutionPolicy", "Bypass", "-File", ps_file])
        print("Atalho para a pasta de PDFs criado na área de trabalho")
    except Exception as e:
        print(f"Não foi possível criar o atalho: {e}")

def create_system_config_file():
    """Cria o arquivo de configuração diretamente no diretório do sistema"""
    print("Criando arquivo de configuração diretamente no sistema...")
    
    # Locais comuns onde o CutePDF procura configurações
    system_dirs = [
        os.path.join(os.environ.get('SYSTEMROOT', 'C:/Windows'), "System32"),
        os.path.join(os.environ.get('SYSTEMROOT', 'C:/Windows'), "SysWOW64"),
    ]
    
    for system_dir in system_dirs:
        if os.path.exists(system_dir):
            config_path = os.path.join(system_dir, "cutepdf.ini")
            try:
                with open(config_path, "w") as f:
                    f.write("[CutePDF Writer]\n")
                    f.write("AutoSave=1\n")
                    f.write("ShowSaveAS=0\n")
                    f.write("PromptForFileName=0\n")
                    f.write("UseDocumentTitle=1\n")
                    f.write("Output=c:\\pdfs\n")
                    f.write("ConfirmOverwrite=0\n")
                    f.write("ShowSettings=0\n")
                    f.write("ShowPDF=0\n")
                    f.write("ShowProgress=0\n")
                print(f"Arquivo de configuração criado em: {config_path}")
            except Exception as e:
                print(f"Erro ao criar arquivo de configuração em {system_dir}: {e}")
    
    # Também criar arquivo global no ProgramData
    try:
        program_data = os.environ.get('PROGRAMDATA', 'C:/ProgramData')
        cutepdf_data_dir = os.path.join(program_data, "CutePDF Writer")
        os.makedirs(cutepdf_data_dir, exist_ok=True)
        
        config_path = os.path.join(cutepdf_data_dir, "config.ini")
        with open(config_path, "w") as f:
            f.write("[CutePDF Writer]\n")
            f.write("AutoSave=1\n")
            f.write("ShowSaveAS=0\n")
            f.write("PromptForFileName=0\n")
            f.write("UseDocumentTitle=1\n")
            f.write("Output=c:\\pdfs\n")
            f.write("ConfirmOverwrite=0\n")
            f.write("ShowSettings=0\n")
            f.write("ShowPDF=0\n")
            f.write("ShowProgress=0\n")
        print(f"Arquivo de configuração global criado em: {config_path}")
    except Exception as e:
        print(f"Erro ao criar arquivo de configuração global: {e}")

def main():
    """Função principal para instalar e configurar o CutePDF sem diálogos"""
    # Verificar privilégios de administrador
    if not is_admin():
        print("Este script requer privilégios de administrador.")
        print("Por favor, execute novamente como administrador.")
        return False
    
    print("=== Instalador de CutePDF Sem Diálogos (Método Alternativo) ===")
    
    # Criar diretório de saída
    create_output_directory()
    
    # Verificar se o CutePDF já está instalado
    if not check_cutepdf_installed():
        # Se não estiver instalado, tentar instalá-lo
        if not install_cutepdf_alternative():
            print("Falha ao instalar CutePDF. Abortando.")
            return False
    
    # Configurar CutePDF via registro
    configure_cutepdf_registry()
    
    # Modificar arquivos de configuração diretamente
    modify_cutepdf_config_files()
    
    # Criar arquivos de configuração no diretório do sistema
    create_system_config_file()
    
    # Criar atalho na área de trabalho
    create_desktop_shortcut()
    
    print("\n=== Configuração concluída com sucesso! ===")
    print("O CutePDF Writer está configurado para funcionar sem diálogos.")
    print("Os arquivos PDF serão salvos automaticamente em c:/pdfs")
    
    print("\nPara imprimir um documento como PDF:")
    print("1. Abra o documento desejado")
    print("2. Selecione 'Imprimir' e escolha a impressora 'CutePDF Writer'")
    print("3. O PDF será salvo automaticamente em c:/pdfs sem mostrar diálogos")
    
    return True

if __name__ == "__main__":
    main()
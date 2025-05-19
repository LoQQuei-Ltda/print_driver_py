import os
import sys
import subprocess
import time
import tempfile
import urllib.request
import ctypes
import winreg
from pathlib import Path
import shutil
import locale

# Constantes
PDF_DIR = "c:/pdfs"
PDF24_MSI_URL = "https://download.pdf24.org/pdf24-creator-11.11.1-x64.msi"
PRINTER_NAME = "Impressora LoQQuei"

# Detecta o idioma do Windows para usar o nome correto do grupo "Everyone"
try:
    lang = locale.getpreferredencoding()
    if lang.lower() == 'cp1252':  # Português
        EVERYONE_GROUP = "Todos"
    else:
        EVERYONE_GROUP = "Everyone"
except:
    EVERYONE_GROUP = "Todos"  # Assumir português como padrão

def is_admin():
    """Verifica se o script está sendo executado como administrador."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def install_required_packages():
    """Instala pacotes Python necessários."""
    required_packages = ['pywin32']
    
    for package in required_packages:
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package, '--quiet'])
            print(f"Pacote {package} instalado com sucesso.")
        except:
            print(f"Erro ao instalar o pacote {package}.")
            return False
    
    return True

def download_file(url, destination):
    """Baixa arquivo da URL especificada."""
    try:
        urllib.request.urlretrieve(url, destination)
        return True
    except Exception as e:
        print(f"Erro ao baixar: {e}")
        return False

def install_pdf24_printer_only():
    """Baixa e instala APENAS a impressora PDF24 (componente leve)."""
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "pdf24_setup.msi")
    
    # Baixa o instalador
    if not download_file(PDF24_MSI_URL, installer_path):
        return False
    
    # Parâmetros para instalação silenciosa MSI - APENAS o componente da impressora
    install_args = [
        'msiexec',
        '/i',
        installer_path,
        '/qn',                    # Modo completamente silencioso (sem interface)
        '/norestart',             # Não reiniciar após instalação
        'AUTOUPDATE=0',           # Desativar atualizações automáticas
        'DESKTOPICONS=0',         # Não criar ícones na área de trabalho
        'STARTMENU=0',            # Não criar atalhos no menu iniciar
        'AUTOSTART=0',            # Não iniciar automaticamente
        'ALLUSERS=1',             # Instalar para todos os usuários
        'COMPONENTS=printer'      # INSTALA APENAS A IMPRESSORA
    ]
    
    try:
        print("Iniciando instalação apenas da impressora virtual...")
        # Executa o instalador
        process = subprocess.Popen(install_args, 
                                 stdout=subprocess.PIPE, 
                                 stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        # Verifica se houve erro
        if process.returncode != 0:
            print(f"Erro na instalação: Código {process.returncode}")
            # Tentativa alternativa: instalar com parâmetros padrão e depois configurar
            print("Tentando método alternativo de instalação...")
            alt_args = [
                'msiexec',
                '/i',
                installer_path,
                '/qn',                # Modo completamente silencioso (sem interface)
                '/norestart',         # Não reiniciar após instalação
                'AUTOUPDATE=0',       # Desativar atualizações automáticas
                'DESKTOPICONS=0',     # Não criar ícones na área de trabalho
                'STARTMENU=0',        # Não criar atalhos no menu iniciar
                'AUTOSTART=0',        # Não iniciar automaticamente
                'ALLUSERS=1'          # Instalar para todos os usuários
            ]
            process = subprocess.Popen(alt_args, 
                                    stdout=subprocess.PIPE, 
                                    stderr=subprocess.PIPE)
            stdout, stderr = process.communicate()
        
        # Aguarda a instalação concluir
        print("Aguardando conclusão da instalação...")
        time.sleep(30)
        
        # Verifica se a impressora PDF24 foi instalada
        import win32print
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        pdf24_installed = any("PDF24" in printer for printer in printers)
        
        if pdf24_installed:
            print("Impressora PDF24 instalada com sucesso.")
            return True
        else:
            print("A impressora PDF24 não foi detectada após a instalação.")
            print("Impressoras disponíveis:", printers)
            return False
    
    except Exception as e:
        print(f"Erro durante a instalação: {e}")
        return False
    finally:
        # Limpa o arquivo temporário
        try:
            if os.path.exists(installer_path):
                os.remove(installer_path)
        except:
            pass

def setup_output_folder():
    """Cria e configura a pasta de saída com permissões adequadas."""
    try:
        # Cria o diretório de destino, se não existir
        if not os.path.exists(PDF_DIR):
            os.makedirs(PDF_DIR)
        
        # Define permissões para "Todos" usando icacls (Windows)
        # Usando o nome correto do grupo baseado no idioma
        subprocess.call(f'icacls "{PDF_DIR}" /grant "{EVERYONE_GROUP}":(OI)(CI)F /T', shell=True)
        subprocess.call(f'icacls "{PDF_DIR}" /grant SYSTEM:(OI)(CI)F /T', shell=True)
        
        return True
    except Exception as e:
        print(f"Erro ao configurar pasta de saída: {e}")
        return False

def disable_ui_executables_only():
    """Desativa apenas os executáveis relacionados à interface gráfica, preservando os essenciais."""
    try:
        # Identifica o diretório de instalação
        program_files = os.environ.get('PROGRAMFILES', 'C:\\Program Files')
        pdf24_dir = os.path.join(program_files, 'PDF24')
        
        # Mata apenas processos de interface
        subprocess.call('taskkill /F /IM pdf24creator.exe', shell=True)
        subprocess.call('taskkill /F /IM pdf24settings.exe', shell=True)
        
        # Lista de executáveis UI que devem ser desativados
        ui_executables = [
            'pdf24-Creator.exe',     # Interface principal
            'pdf24-DocTool.exe',      # Ferramenta de documento
            'pdf24-DesktopTool.exe',  # Ferramenta de desktop
            'pdf24-Settings.exe'      # Configurações
        ]
        
        if os.path.exists(pdf24_dir):
            print(f"Desativando interfaces gráficas em {pdf24_dir}...")
            for ui_exe in ui_executables:
                filepath = os.path.join(pdf24_dir, ui_exe)
                if os.path.exists(filepath):
                    try:
                        # Renomeia para .disabled
                        disabled_path = filepath + '.disabled'
                        if os.path.exists(disabled_path):
                            os.remove(disabled_path)
                        os.rename(filepath, disabled_path)
                        print(f"Desativado: {filepath}")
                    except Exception as e:
                        print(f"Não foi possível desativar {filepath}: {e}")
                        # Não tenta substituir por arquivo vazio para evitar problemas
        else:
            print(f"Diretório {pdf24_dir} não encontrado.")
        
        return True
    except Exception as e:
        print(f"Erro ao desativar executáveis de interface: {e}")
        return False

def configure_pdf24_silent_mode():
    """Configura apenas as configurações de modo silencioso essenciais."""
    try:
        # Configurações via registro do Windows
        try:
            # Configurações para HKLM (todos os usuários)
            reg_path_all = r"SOFTWARE\PDF24\pdf24Creator"
            try:
                key_all = winreg.CreateKey(winreg.HKEY_LOCAL_MACHINE, reg_path_all)
                
                # Define configurações para todos os usuários
                winreg.SetValueEx(key_all, "AutoSaveDirectory", 0, winreg.REG_SZ, PDF_DIR)
                winreg.SetValueEx(key_all, "AutoSaveEnabled", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key_all, "AutoSaveFormat", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key_all, "ShowProcessWindow", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key_all, "ShowFinishWindow", 0, winreg.REG_DWORD, 0)
                winreg.SetValueEx(key_all, "UseAutosave", 0, winreg.REG_DWORD, 1)
                winreg.SetValueEx(key_all, "SilentMode", 0, winreg.REG_DWORD, 1)
                
                winreg.CloseKey(key_all)
            except Exception as e:
                print(f"Aviso: Não foi possível configurar registro para todos os usuários: {e}")
                
            # Caminho do registro para PDF24 (usuário atual)
            reg_path = r"SOFTWARE\PDF24\pdf24Creator"
            
            # Abre a chave (ou cria se não existir)
            key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, reg_path)
            
            # Define configurações para salvar automaticamente e suprimir janelas
            winreg.SetValueEx(key, "AutoSaveDirectory", 0, winreg.REG_SZ, PDF_DIR)
            winreg.SetValueEx(key, "AutoSaveEnabled", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "AutoSaveFormat", 0, winreg.REG_DWORD, 0)  # 0 = PDF
            winreg.SetValueEx(key, "ShowProcessWindow", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "ShowFinishWindow", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "ToolbarIntegration", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "CheckForUpdates", 0, winreg.REG_DWORD, 0)
            winreg.SetValueEx(key, "UseAutosave", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(key, "ShowSaveDialog", 0, winreg.REG_DWORD, 0)
            
            # Fecha a chave
            winreg.CloseKey(key)
            
            # Configurações da impressora
            printer_path = r"SOFTWARE\PDF24\pdf24Creator\Printer"
            printer_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, printer_path)
            
            # Define configurações da impressora
            winreg.SetValueEx(printer_key, "DefaultOutputFormat", 0, winreg.REG_DWORD, 0)  # 0 = PDF
            winreg.SetValueEx(printer_key, "DefaultOutputDirectory", 0, winreg.REG_SZ, PDF_DIR)
            winreg.SetValueEx(printer_key, "AutoSave", 0, winreg.REG_DWORD, 1)
            winreg.SetValueEx(printer_key, "AutoSaveDirectory", 0, winreg.REG_SZ, PDF_DIR)
            winreg.SetValueEx(printer_key, "ShowSaveDialog", 0, winreg.REG_DWORD, 0)
            
            # Fecha a chave
            winreg.CloseKey(printer_key)
            
            return True
        except Exception as e:
            print(f"Erro ao configurar o modo silencioso: {e}")
            return False
        
    except Exception as e:
        print(f"Erro geral na configuração: {e}")
        return False

def rename_pdf24_printer():
    """Renomeia a impressora PDF24 para o nome desejado usando vários métodos."""
    try:
        # Primeiro verifica se a impressora PDF24 existe
        import win32print
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        
        pdf_printer = None
        for printer in printers:
            if "PDF24" in printer:
                pdf_printer = printer
                break
        
        if not pdf_printer:
            print("Impressora PDF24 não encontrada para renomear.")
            print("Impressoras disponíveis:", printers)
            return False
        
        print(f"Renomeando impressora '{pdf_printer}' para '{PRINTER_NAME}'...")
        
        # Método 1: Usando PowerShell (mais confiável para renomear impressoras)
        ps_command = f'powershell -Command "$printer = Get-Printer | Where-Object {{$_.Name -eq \'{pdf_printer}\'}}; if ($printer) {{ Rename-Printer -Name $printer.Name -NewName \'{PRINTER_NAME}\' }}"'
        subprocess.call(ps_command, shell=True)
        
        # Aguarda um pouco para garantir que a renomeação foi concluída
        time.sleep(5)
        
        # Verifica se a renomeação foi bem-sucedida
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        if PRINTER_NAME in printers:
            print(f"Impressora renomeada com sucesso para '{PRINTER_NAME}'.")
            return True
        
        # Método 2: Usando wmic (alternativa)
        wmic_command = f'wmic printer where "name=\'{pdf_printer}\'" call RenamePrinter name="{PRINTER_NAME}"'
        subprocess.call(wmic_command, shell=True)
        
        # Aguarda um pouco para garantir que a renomeação foi concluída
        time.sleep(5)
        
        # Verifica novamente
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        if PRINTER_NAME in printers:
            print(f"Impressora renomeada com sucesso para '{PRINTER_NAME}' (método 2).")
            return True
        
        # Método 3: Usando o PrintUIEntry (última tentativa)
        rename_cmd = f'rundll32 printui.dll,PrintUIEntry /Xs /n"{pdf_printer}" Name "{PRINTER_NAME}"'
        subprocess.call(rename_cmd, shell=True)
        
        # Aguarda um pouco e verifica uma última vez
        time.sleep(5)
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        if PRINTER_NAME in printers:
            print(f"Impressora renomeada com sucesso para '{PRINTER_NAME}' (método 3).")
            return True
        else:
            print(f"Não foi possível renomear a impressora. Nome atual: '{pdf_printer}'")
            return False
        
    except Exception as e:
        print(f"Erro ao renomear impressora: {e}")
        return False

def set_as_default_printer():
    """Define a impressora como padrão."""
    try:
        import win32print
        
        # Aguarda um pouco para garantir que a impressora foi instalada
        time.sleep(5)
        
        # Tentativa 1: Encontra a impressora pelo novo nome
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        
        for printer in printers:
            if PRINTER_NAME in printer:
                # Define como impressora padrão
                win32print.SetDefaultPrinter(printer)
                print(f"Impressora '{printer}' definida como padrão.")
                return True
        
        # Tentativa 2: Se não encontrou pelo nome personalizado, tenta pelo nome do PDF24
        for printer in printers:
            if "PDF24" in printer:
                # Define como impressora padrão
                win32print.SetDefaultPrinter(printer)
                print(f"Impressora PDF24 '{printer}' definida como padrão.")
                
                # Tenta renomear novamente
                rename_cmd = f'rundll32 printui.dll,PrintUIEntry /Xs /n"{printer}" Name "{PRINTER_NAME}"'
                subprocess.call(rename_cmd, shell=True)
                return True
        
        print("Nenhuma impressora PDF24 encontrada para definir como padrão.")
        print("Impressoras disponíveis:", printers)
        return False
    
    except Exception as e:
        print(f"Erro ao definir impressora padrão: {e}")
        return False

def configure_pdf24_service():
    """Configura o serviço PDF24 corretamente."""
    try:
        # Configura o serviço PDF24 para iniciar automaticamente
        subprocess.call('sc config "PDF24" start= auto', shell=True)
        
        # Garante que o serviço esteja em execução
        subprocess.call('sc start "PDF24"', shell=True)
        
        return True
    except Exception as e:
        print(f"Erro ao configurar serviço PDF24: {e}")
        return False

def disable_pdf24_autostart():
    """Desativa inicialização automática do PDF24."""
    try:
        # Remove entradas do registro que podem iniciar o PDF24 automaticamente
        autorun_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run"
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, autorun_path, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.DeleteValue(key, "PDF24")
            except:
                pass
            try:
                winreg.DeleteValue(key, "PDF24Creator")
            except:
                pass
            winreg.CloseKey(key)
        except:
            pass
            
        # Remove também da inicialização para todos os usuários
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, autorun_path, 0, winreg.KEY_ALL_ACCESS)
            try:
                winreg.DeleteValue(key, "PDF24")
            except:
                pass
            try:
                winreg.DeleteValue(key, "PDF24Creator") 
            except:
                pass
            winreg.CloseKey(key)
        except:
            pass
            
        return True
    except:
        return False

def configure_printer_settings():
    """Configurações adicionais da impressora."""
    try:
        # Configura spooler de impressão
        subprocess.call('sc config "Spooler" start= auto', shell=True)
        subprocess.call('sc start "Spooler"', shell=True)
        
        # Configura permissões para o serviço PDF24
        subprocess.call('sc sdset PDF24 D:(A;;CCLCSWRPWPDTLOCRRC;;;SY)(A;;CCDCLCSWRPWPDTLOCRSDRCWDWO;;;BA)(A;;CCLCSWLOCRRC;;;IU)(A;;CCLCSWLOCRRC;;;SU)(A;;CR;;;AU)', shell=True)
        
        return True
    except Exception as e:
        print(f"Erro ao configurar ajustes da impressora: {e}")
        return False

def restartprint_service():
    """Reinicia o serviço de impressão."""
    try:
        # Reinicia o serviço de impressão para aplicar as alterações
        print("Reiniciando serviços de impressão...")
        subprocess.call('net stop spooler', shell=True)
        time.sleep(3)
        subprocess.call('net start spooler', shell=True)
        time.sleep(3)
        return True
    except Exception as e:
        print(f"Erro ao reiniciar serviço de impressão: {e}")
        return False

def verify_installation():
    """Verifica se a instalação foi bem-sucedida."""
    try:
        import win32print
        
        # Lista todas as impressoras instaladas
        printers = [printer[2] for printer in win32print.EnumPrinters(2)]
        
        print("\nImpressoras instaladas:")
        for printer in printers:
            print(f"- {printer}")
        
        # Verifica se a nossa impressora está na lista
        if PRINTER_NAME in printers:
            print(f"\nInstalação verificada: A impressora '{PRINTER_NAME}' está instalada corretamente.")
            return True
        elif any("PDF24" in printer for printer in printers):
            pdf24_printer = next(printer for printer in printers if "PDF24" in printer)
            print(f"\nImpressora PDF24 '{pdf24_printer}' encontrada, mas não foi possível renomeá-la.")
            return True
        else:
            print("\nAVISO: Nenhuma impressora PDF24 ou com o nome personalizado foi encontrada!")
            return False
    
    except Exception as e:
        print(f"Erro na verificação da instalação: {e}")
        return False

def create_test_print():
    """Cria um arquivo de teste para verificar se a impressora funciona corretamente."""
    try:
        # Cria um arquivo de texto simples
        test_file = os.path.join(tempfile.gettempdir(), "pdf24_test.txt")
        with open(test_file, "w") as f:
            f.write("Este é um teste da impressora virtual PDF24.\n")
            f.write(f"Data e hora: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("Se este teste for bem sucedido, um arquivo PDF será criado na pasta de destino sem mostrar janelas.")
        
        # Imprime o arquivo usando a impressora configurada
        print_cmd = f'powershell -Command "Get-Content \'{test_file}\' | Out-Printer -Name \'{PRINTER_NAME}\'"'
        subprocess.call(print_cmd, shell=True)
        
        print(f"\nArquivo de teste enviado para impressão. Verifique a pasta {PDF_DIR} em alguns instantes.")
        return True
    except Exception as e:
        print(f"Erro ao criar teste de impressão: {e}")
        return False

def main():
    # Verifica se está sendo executado como administrador
    if not is_admin():
        # Tenta reexecutar como administrador
        print("Solicitando privilégios de administrador...")
        try:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
        except:
            print("Não foi possível obter privilégios de administrador.")
        return
    
    print(f"Iniciando configuração da impressora virtual '{PRINTER_NAME}'...")
    
    # Passo 1: Instalar pacotes necessários
    print("\nInstalando pacotes Python necessários...")
    if not install_required_packages():
        print("Falha ao instalar pacotes necessários. Continuando mesmo assim...")
    
    # Passo 2: Configurar pasta de saída com permissões adequadas
    print(f"\nConfigurando pasta de destino {PDF_DIR}...")
    setup_output_folder()
    
    # Passo 3: Instalar APENAS o componente da impressora PDF24 (muito mais leve)
    print("\nInstalando o componente da impressora PDF24 (instalação mínima)...")
    if not install_pdf24_printer_only():
        print("Falha na instalação do componente da impressora PDF24.")
        return
    
    # Espera um pouco para garantir que a instalação foi concluída
    print("\nAguardando conclusão da instalação...")
    time.sleep(20)
    
    # Passo 4: Desativar APENAS executáveis de interface gráfica
    print("\nDesativando interfaces gráficas (preservando funcionalidades essenciais)...")
    disable_ui_executables_only()
    
    # Passo 5: Configurar o PDF24 com modo silencioso básico
    print("\nConfigurando o PDF24 em modo silencioso (preservando funcionalidades essenciais)...")
    configure_pdf24_silent_mode()
    
    # Passo 6: Configurações da impressora
    print("\nAplicando configurações específicas da impressora...")
    configure_printer_settings()
    
    # Passo 7: Renomear impressora
    print("\nRenomeando a impressora para 'Impressora LoQQuei'...")
    rename_pdf24_printer()
    
    # Passo 8: Configurar serviço PDF24
    print("\nConfigurando serviço PDF24...")
    configure_pdf24_service()
    
    # Passo 9: Definir como impressora padrão
    print("\nDefinindo como impressora padrão...")
    set_as_default_printer()
    
    # Passo 10: Desativar inicialização automática de componentes desnecessários
    print("\nDesativando inicialização automática de componentes desnecessários...")
    disable_pdf24_autostart()
    
    # Passo 11: Reiniciar o serviço de impressão
    print("\nReiniciando serviços de impressão...")
    restartprint_service()
    
    # Verificação final
    print("\nVerificando instalação...")
    verify_installation()
    
    # Teste de impressão (opcional)
    print("\nCriando teste de impressão...")
    create_test_print()
    
    print(f"\nInstalação concluída! A impressora '{PRINTER_NAME}' está configurada para salvar PDFs em {PDF_DIR}.")
    print("A instalação foi feita usando apenas o componente da impressora, economizando espaço em disco.")
    print("Configurações de modo silencioso foram aplicadas para suprimir interfaces, mantendo funcionalidades essenciais.")
    print("\nDica: Verifique a pasta {PDF_DIR} após usar a impressora. Se não funcionar, pode ser necessário reiniciar o PC.")

if __name__ == "__main__":
    main()
#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import ctypes
import subprocess
import argparse
import winreg
import logging

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutoPrinterLoQQuei")

class AutoPrinterLoQQuei:
    PRINTER_NAME = "Impressora LoQQuei"
    PORT_NAME = "FILE:"
    BASE_PRINTER = "Microsoft Print to PDF"
    PDF_FOLDER = r"C:\Users\Public\Documents\LoQQueiPDFs"
    
    def __init__(self):
        os.makedirs(self.PDF_FOLDER, exist_ok=True)

    def is_admin(self):
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception as e:
            logger.error(f"Erro ao checar admin: {e}")
            return False

    def elevate(self, uninstall=False):
        script = os.path.abspath(sys.argv[0])
        params = []
        if uninstall:
            params.append("--uninstall")
        params.append("--elevated")
        logger.info("Reiniciando com privilégios administrativos...")
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{script}" {" ".join(params)}', None, 1)
        if ret <= 32:
            logger.error(f"Falha ao pedir admin. Código: {ret}")
            return False
        return True

    def printer_exists(self):
        try:
            ps = f'''
            if (Get-Printer -Name "{self.PRINTER_NAME}" -ErrorAction SilentlyContinue) {{ Write-Output "True" }} else {{ Write-Output "False" }}
            '''
            result = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True)
            return "True" in result.stdout
        except Exception as e:
            logger.error(f"Erro ao checar impressora: {e}")
            return False

    def install(self):
        if not self.is_admin():
            return self.elevate(uninstall=False)

        logger.info("Instalando impressora virtual...")

        # Remove impressora antiga se existir
        if self.printer_exists():
            logger.info(f"Impressora '{self.PRINTER_NAME}' já existe. Removendo antes de instalar.")
            self.uninstall()

        # Clonar Microsoft Print to PDF para Impressora LoQQuei
        ps_clone = f'''
        $src = Get-Printer -Name "{self.BASE_PRINTER}"
        Remove-Printer -Name "{self.PRINTER_NAME}" -ErrorAction SilentlyContinue
        Add-Printer -Name "{self.PRINTER_NAME}" -DriverName $src.DriverName -PortName "{self.PORT_NAME}"
        Set-Printer -Name "{self.PRINTER_NAME}" -Default $true
        if (Get-Printer -Name "{self.PRINTER_NAME}" -ErrorAction SilentlyContinue) {{ Write-Output "True" }} else {{ Write-Output "False" }}
        '''
        result = subprocess.run(["powershell", "-Command", ps_clone], capture_output=True, text=True)
        if "True" not in result.stdout:
            logger.error(f"Falha ao criar impressora: {result.stdout.strip()}")
            return False
        
        # Configura o registro para salvar PDF automaticamente na pasta fixa
        self.configure_registry_path()

        logger.info(f"Impressora '{self.PRINTER_NAME}' instalada e configurada para salvar PDFs em '{self.PDF_FOLDER}'")
        return True

    def uninstall(self):
        if not self.is_admin():
            return self.elevate(uninstall=True)

        logger.info("Removendo impressora virtual...")
        ps_remove = f'''
        Remove-Printer -Name "{self.PRINTER_NAME}" -ErrorAction SilentlyContinue
        if (-not (Get-Printer -Name "{self.PRINTER_NAME}" -ErrorAction SilentlyContinue)) {{ Write-Output "True" }} else {{ Write-Output "False" }}
        '''
        result = subprocess.run(["powershell", "-Command", ps_remove], capture_output=True, text=True)
        if "True" in result.stdout:
            logger.info(f"Impressora '{self.PRINTER_NAME}' removida com sucesso.")
            # Remove as chaves do registro também
            self.remove_registry_path()
            return True
        else:
            logger.error(f"Falha ao remover impressora: {result.stdout.strip()}")
            return False

    def configure_registry_path(self):
        try:
            # Caminhos no registro para ajustar a impressão automática sem popup
            base_key_path = fr"Software\Microsoft\Windows NT\CurrentVersion\Print\Printers\{self.PRINTER_NAME}"
            devmode_path = base_key_path + r"\DevMode"
            client_side_path = base_key_path + r"\Client Side Rendering Print Provider"

            # Abre ou cria as chaves necessárias
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, base_key_path, 0, winreg.KEY_SET_VALUE) as base_key:
                # Força o caminho do arquivo PDF (exemplo com nome fixo, pode alterar para timestamp)
                # A Microsoft Print to PDF espera uma string PrintFileName na chave DevMode
                with winreg.CreateKey(base_key, "DevMode") as devmode_key:
                    # Aqui definimos o arquivo padrão, pode ser só a pasta (não testado) ou um arquivo com nome padrão
                    winreg.SetValueEx(devmode_key, "PrintFileName", 0, winreg.REG_SZ, os.path.join(self.PDF_FOLDER, "documento.pdf"))
                
                with winreg.CreateKey(base_key, "Client Side Rendering Print Provider") as client_key:
                    # Define a flag para eliminar o popup (DWORD 1)
                    winreg.SetValueEx(client_key, "NoPrompt", 0, winreg.REG_DWORD, 1)

            logger.info("Configuração do registro para salvamento automático aplicada.")
        except FileNotFoundError:
            logger.error("Erro: Impressora não encontrada no registro. Tente executar após a instalação.")
        except PermissionError:
            logger.error("Erro: Permissão negada para editar o registro. Execute o script como administrador.")
        except Exception as e:
            logger.error(f"Erro inesperado no registro: {e}")

    def remove_registry_path(self):
        try:
            base_key_path = fr"Software\Microsoft\Windows NT\CurrentVersion\Print\Printers\{self.PRINTER_NAME}"
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base_key_path + r"\DevMode")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base_key_path + r"\Client Side Rendering Print Provider")
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, base_key_path)
            logger.info("Configurações do registro removidas.")
        except FileNotFoundError:
            pass
        except PermissionError:
            logger.error("Erro ao tentar remover chave do registro. Permissão negada.")
        except Exception as e:
            logger.error(f"Erro inesperado ao remover chave do registro: {e}")

def main():
    parser = argparse.ArgumentParser(description="Instalador da impressora virtual 'Impressora LoQQuei'")
    parser.add_argument("--uninstall", action="store_true", help="Desinstalar a impressora")
    parser.add_argument("--elevated", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    installer = AutoPrinterLoQQuei()

    if args.uninstall:
        logger.info("Executando desinstalação...")
        if installer.uninstall():
            print("Impressora virtual removida com sucesso!")
        else:
            print("Falha ao remover a impressora virtual.")
    else:
        logger.info("Executando instalação...")
        if installer.install():
            print(f"Impressora virtual instalada com sucesso!\nPDFs serão salvos em: {installer.PDF_FOLDER}")
        else:
            print("Falha ao instalar a impressora virtual.")

    if args.elevated:
        input("Pressione Enter para sair...")

if __name__ == "__main__":
    sys.exit(main())

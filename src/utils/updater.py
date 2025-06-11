#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sistema de atualização automática da aplicação - Sem requisito de privilégios administrativos
"""

import os
import sys
import platform
import logging
import subprocess
import tempfile
import shutil
import time
import json
import threading
import requests
from datetime import datetime
import ctypes

# Importa o sistema de notificações da classe PrinterList
from src.ui.printer_list import SystemNotification

logger = logging.getLogger("PrintManagementSystem.Utils.Updater")

class AppUpdater:
    """Gerenciador de atualizações automáticas da aplicação"""
    
    def __init__(self, config, api_client=None):
        """
        Inicializa o gerenciador de atualizações
        
        Args:
            config: Configuração da aplicação
            api_client: Cliente da API (opcional)
        """
        self.config = config
        self.api_client = api_client
        self.system = platform.system()
        self.app_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        self.current_version = self._get_current_version()
        self.update_url = "https://api.loqquei.com.br/api/v1/desktop/update"
        self.update_info = None
        self.is_checking = False
        self.is_updating = False
        
        # Inicializa o sistema de notificações
        self.notification_system = SystemNotification()
    
    def _get_current_version(self):
        """
        Obtém a versão atual da aplicação
        
        Returns:
            str: Versão atual
        """
        try:
            # Tenta ler a versão do arquivo __init__.py
            init_path = os.path.join(self.app_root, "src", "__init__.py")
            if os.path.exists(init_path):
                with open(init_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.startswith("__version__"):
                            return line.split("=")[1].strip().strip('"\'')
            
            # Se não encontrou no __init__.py, tenta no setup.py
            setup_path = os.path.join(self.app_root, "setup.py")
            if os.path.exists(setup_path):
                with open(setup_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        if "APP_VERSION" in line:
                            return line.split("=")[1].strip().strip('"\'')
            
            return "2.0.3"  # Versão padrão
        except Exception as e:
            logger.error(f"Erro ao obter versão atual: {str(e)}")
            return "2.0.3"
    
    def check_for_update(self, silent=True):
        """
        Verifica se existem atualizações disponíveis
        
        Args:
            silent (bool): Se True, não exibe notificações de "sem atualizações"
            
        Returns:
            bool: True se há atualizações disponíveis
        """
        if self.is_checking or self.is_updating:
            logger.debug("Já existe uma verificação ou atualização em andamento")
            return False
        
        self.is_checking = True
        
        try:
            # Verifica atualizações através da API
            update_info = self._check_api_update()
            
            # Se não conseguiu pela API, tenta diretamente
            if not update_info:
                update_info = self._check_direct_update()
            
            if not update_info:
                if not silent:
                    logger.info("Nenhuma atualização disponível")
                    self.notification_system.show_notification(
                        "Sistema Atualizado",
                        f"Você já está usando a versão mais recente ({self.current_version}).",
                        duration=5,
                        notification_type="success"
                    )
                self.is_checking = False
                return False
            
            # Verifica se a versão remota é mais recente
            remote_version = update_info.get('version')
            if not remote_version:
                logger.warning("API retornou informações sem versão")
                self.is_checking = False
                return False
                
            if not self._is_newer_version(remote_version):
                if not silent:
                    logger.info(f"Versão atual ({self.current_version}) é a mais recente")
                    self.notification_system.show_notification(
                        "Sistema Atualizado",
                        f"Você já está usando a versão mais recente ({self.current_version}).",
                        duration=5,
                        notification_type="success"
                    )
                self.is_checking = False
                return False
            
            # Guarda informações da atualização
            self.update_info = update_info
            logger.info(f"Nova versão disponível: {remote_version}")
            
            self.is_checking = False
            return True
            
        except Exception as e:
            logger.error(f"Erro ao verificar atualizações: {str(e)}")
            self.is_checking = False
            return False
    
    def _check_api_update(self):
        """
        Verifica atualizações usando o cliente da API
        
        Returns:
            dict: Informações da atualização ou None
        """
        if not self.api_client:
            return None
        
        try:
            # Cria parâmetros para a requisição
            params = {
                "version": self.current_version,
                "platform": self.system.lower(),
                "arch": platform.architecture()[0],
                "python_version": platform.python_version()
            }
            
            # Consulta a API para atualizações usando o endpoint /desktop/update
            if hasattr(self.api_client, '_make_request'):
                response = self.api_client._make_request("GET", "/desktop/update", params=params)
                
                # Verifica se há informações de versão no formato esperado
                if response and isinstance(response, dict):
                    # A API retorna: {'version': 'v2.0.3', 'updateUrl': 'https://...'}
                    version = response.get('version')
                    update_url = response.get('updateUrl')
                    
                    if version and update_url:
                        # Normaliza o formato para compatibilidade com o resto do código
                        update_info = {
                            'version': version,
                            'url': update_url  # Mapeia updateUrl para url
                        }
                        logger.info(f"Versão do servidor: {version}")
                        return update_info
                    else:
                        logger.warning("Resposta da API não contém version ou updateUrl")
                        return None
            
            return None
        except Exception as e:
            logger.error(f"Erro ao verificar atualizações pela API: {str(e)}")
            return None
    
    def _check_direct_update(self):
        """
        Verifica atualizações diretamente no servidor
        
        Returns:
            dict: Informações da atualização ou None
        """
        try:
            # Cria parâmetros para a requisição
            params = {
                "version": self.current_version,
                "platform": self.system.lower(),
                "arch": platform.architecture()[0],
                "python_version": platform.python_version()
            }
            
            # Faz a requisição para o servidor usando o endpoint /desktop/update
            response = requests.get(self.update_url, params=params, timeout=10)
            
            # Verifica se a requisição foi bem-sucedida
            if response.status_code == 200:
                response_data = response.json()
                
                # Verifica diferentes formatos de resposta possíveis
                if "data" in response_data and isinstance(response_data["data"], dict):
                    # Formato: {"data": {"version": "...", "updateUrl": "..."}}
                    data = response_data["data"]
                    version = data.get('version')
                    update_url = data.get('updateUrl') or data.get('url')
                    
                    if version and update_url:
                        update_info = {
                            'version': version,
                            'url': update_url
                        }
                        logger.info(f"Versão do servidor: {version}")
                        return update_info
                elif "version" in response_data:
                    # Formato direto: {"version": "...", "updateUrl": "..."}
                    version = response_data.get('version')
                    update_url = response_data.get('updateUrl') or response_data.get('url')
                    
                    if version and update_url:
                        update_info = {
                            'version': version,
                            'url': update_url
                        }
                        logger.info(f"Versão do servidor: {version}")
                        return update_info
                
                logger.warning("Resposta do servidor não contém informações de versão válidas")
                return None
            else:
                logger.warning(f"Servidor retornou código {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Erro ao verificar atualizações diretamente: {str(e)}")
            return None
    
    def _is_newer_version(self, remote_version):
        """
        Verifica se a versão remota é mais recente que a versão atual
        
        Args:
            remote_version (str): Versão remota
            
        Returns:
            bool: True se a versão remota for mais recente
        """
        if not remote_version:
            return False
        
        try:
            logger.info(f"Comparando versões: atual={self.current_version}, remota={remote_version}")
            
            # Limpa as versões (remove caracteres como 'v' no início)
            current_clean = self.current_version.lstrip('v')
            remote_clean = remote_version.lstrip('v')
            
            # Converte as versões para tuples de inteiros
            try:
                current_parts = current_clean.split('.')
                remote_parts = remote_clean.split('.')
                
                # Garante que ambas as versões tenham o mesmo número de partes
                max_parts = max(len(current_parts), len(remote_parts))
                current_parts.extend(['0'] * (max_parts - len(current_parts)))
                remote_parts.extend(['0'] * (max_parts - len(remote_parts)))
                
                # Converte para inteiros
                current = tuple(int(part) for part in current_parts)
                remote = tuple(int(part) for part in remote_parts)
                
                # Compara as versões
                result = remote > current
                
            except ValueError as ve:
                logger.warning(f"Erro ao converter versões para inteiros: {ve}")
                # Se não conseguir converter para inteiros, compara como strings
                # Isso é menos preciso, mas funciona para formatos não padrão
                current_parts = current_clean.split('.')
                remote_parts = remote_clean.split('.')
                
                # Compara cada parte das versões
                result = False
                max_parts = max(len(current_parts), len(remote_parts))
                
                for i in range(max_parts):
                    c_part = current_parts[i] if i < len(current_parts) else "0"
                    r_part = remote_parts[i] if i < len(remote_parts) else "0"
                    
                    # Tenta converter para inteiros para comparar
                    try:
                        c_val = int(c_part)
                        r_val = int(r_part)
                        if r_val > c_val:
                            result = True
                            break
                        elif r_val < c_val:
                            break
                    except ValueError:
                        # Se não conseguir converter, compara como strings
                        if r_part > c_part:
                            result = True
                            break
                        elif r_part < c_part:
                            break
            
            logger.info(f"Resultado da comparação: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Erro ao comparar versões: {str(e)}")
            # No caso de erro, retorna False por segurança
            return False
    
    def download_update(self):
        """
        Baixa a atualização
        
        Returns:
            str: Caminho para o arquivo de atualização ou None
        """
        if not self.update_info or not self.update_info.get('url'):
            logger.error("Informações de atualização indisponíveis ou incompletas")
            return None
        
        try:
            download_url = self.update_info['url']
            download_dir = os.path.join(self.config.temp_dir, "updates")
            os.makedirs(download_dir, exist_ok=True)
            
            # Nome do arquivo de atualização
            filename = os.path.basename(download_url)
            if not filename or '.' not in filename:
                # Se não conseguir extrair o nome do arquivo da URL, usa um nome padrão
                file_extension = ".exe" if self.system == "Windows" else ".zip"
                filename = f"update-{self.update_info.get('version', 'latest')}{file_extension}"
            
            # Caminho completo do arquivo
            file_path = os.path.join(download_dir, filename)
            
            # Notifica início do download
            self.notification_system.show_notification(
                "Baixando Atualização",
                f"Baixando versão {self.update_info.get('version', 'mais recente')}...",
                duration=5,
                notification_type="info"
            )
            
            # Baixa o arquivo
            logger.info(f"Baixando atualização de {download_url}")
            response = requests.get(download_url, stream=True, timeout=60)
            
            # Verifica se a requisição foi bem-sucedida
            if response.status_code == 200:
                # Obtém o tamanho total do arquivo se disponível
                total_size = int(response.headers.get('content-length', 0))
                downloaded_size = 0
                
                # Salva o arquivo
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            
                            # Log do progresso a cada 10% (se o tamanho total for conhecido)
                            if total_size > 0:
                                progress = (downloaded_size / total_size) * 100
                                if progress % 10 < 1:  # Log aproximadamente a cada 10%
                                    logger.debug(f"Download: {progress:.1f}% ({downloaded_size}/{total_size} bytes)")
                
                logger.info(f"Atualização baixada para {file_path} ({downloaded_size} bytes)")
                
                # Notifica conclusão do download
                self.notification_system.show_notification(
                    "Download Concluído",
                    "A atualização foi baixada e será instalada automaticamente.",
                    duration=5,
                    notification_type="success"
                )
                
                return file_path
            else:
                logger.error(f"Erro ao baixar atualização: código {response.status_code}")
                
                # Notifica erro no download
                self.notification_system.show_notification(
                    "Erro no Download",
                    f"Não foi possível baixar a atualização (Erro {response.status_code}).",
                    duration=10,
                    notification_type="error"
                )
                
                return None
                
        except Exception as e:
            logger.error(f"Erro ao baixar atualização: {str(e)}")
            
            # Notifica erro no download
            self.notification_system.show_notification(
                "Erro no Download",
                f"Ocorreu um erro ao baixar a atualização: {str(e)}",
                duration=10,
                notification_type="error"
            )
            
            return None
    
    def apply_update(self, update_file=None):
        """
        Aplica a atualização
        
        Args:
            update_file (str, optional): Caminho para o arquivo de atualização
            
        Returns:
            bool: True se a atualização foi aplicada com sucesso
        """
        if self.is_updating:
            logger.warning("Já existe uma atualização em andamento")
            return False
        
        self.is_updating = True
        
        try:
            # Se não foi especificado o arquivo, baixa a atualização
            if not update_file:
                update_file = self.download_update()
            
            if not update_file or not os.path.exists(update_file):
                logger.error("Arquivo de atualização não encontrado")
                self.is_updating = False
                return False
            
            # Notifica início da instalação
            self.notification_system.show_notification(
                "Instalando Atualização",
                f"Instalando versão {self.update_info.get('version', 'mais recente')}. O aplicativo será reiniciado automaticamente.",
                duration=10,
                notification_type="info"
            )
            
            # Verifica se o arquivo baixado é um executável do Windows
            if update_file.lower().endswith('.exe') and self.system == "Windows":
                return self._apply_exe_update(update_file)
            else:
                # Aplica a atualização (formato ZIP) sem privilégios elevados
                return self._apply_update_without_privileges(update_file)
            
        except Exception as e:
            logger.error(f"Erro ao aplicar atualização: {str(e)}")
            
            # Notifica erro na instalação
            self.notification_system.show_notification(
                "Erro na Instalação",
                f"Ocorreu um erro ao instalar a atualização: {str(e)}",
                duration=10,
                notification_type="error"
            )
            
            self.is_updating = False
            return False
    
    def _apply_exe_update(self, exe_file):
        """
        Aplica atualização usando um executável (.exe) - SEM requisito de admin
        
        Args:
            exe_file (str): Caminho para o arquivo executável de atualização
            
        Returns:
            bool: True se a atualização foi iniciada com sucesso
        """
        try:
            logger.info(f"Executando atualização via executável: {exe_file}")
            
            # Executa o instalador de forma silenciosa SEM solicitar elevação
            # Adiciona parâmetros para instalação silenciosa
            startup_info = None
            creation_flags = 0
            
            # No Windows, esconde a janela do console
            if self.system == "Windows":
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup_info.wShowWindow = 0  # SW_HIDE
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            # Executa o instalador com parâmetros para instalação silenciosa
            subprocess.Popen(
                [exe_file, '/VERYSILENT', '/NORESTART', '/NOICONS', '/SP-', '/CLOSEAPPLICATIONS', 
                 '/RESTARTAPPLICATIONS', '/NOCANCEL', '/SUPPRESSMSGBOXES'], 
                startupinfo=startup_info,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info("Instalador de atualização iniciado")
            
            # Notifica que a instalação está em andamento
            self.notification_system.show_notification(
                "Instalação em Andamento",
                "O instalador está sendo executado em segundo plano. O aplicativo será reiniciado automaticamente.",
                duration=10,
                notification_type="info"
            )
            
            self.is_updating = False
            return True
            
        except Exception as e:
            logger.error(f"Erro ao executar instalador: {str(e)}")
            
            # Notifica erro na instalação
            self.notification_system.show_notification(
                "Erro na Instalação",
                f"Não foi possível executar o instalador: {str(e)}",
                duration=10,
                notification_type="error"
            )
            
            self.is_updating = False
            return False
    
    def _apply_update_without_privileges(self, update_file):
        """
        Aplica a atualização sem privilégios elevados
        
        Args:
            update_file (str): Caminho para o arquivo de atualização
            
        Returns:
            bool: True se a atualização foi iniciada com sucesso
        """
        try:
            logger.info(f"Aplicando atualização sem privilégios elevados: {update_file}")
            
            # Cria um script para aplicar a atualização
            temp_dir = tempfile.mkdtemp()
            script_path = os.path.join(temp_dir, "apply_update.py")
            
            # Determina se a aplicação está instalada no diretório do usuário
            is_user_install = self._is_user_installation()
            
            # Se for instalação de usuário, cria um script simplificado
            # que não requer privilégios administrativos
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(f"""
import os
import sys
import zipfile
import shutil
import time
import subprocess
import tempfile
import logging
import traceback

# Configura logging para não interferir com o usuário
log_file = os.path.join(tempfile.gettempdir(), "loqquei_update.log")
logging.basicConfig(filename=log_file, level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

def apply_update():
    try:
        logging.info("Iniciando aplicação da atualização (sem privilégios)")
        
        # Caminho do arquivo de atualização
        update_file = {repr(update_file)}
        logging.info(f"Arquivo de atualização: {{update_file}}")
        
        # Diretório da aplicação
        app_dir = {repr(self.app_root)}
        logging.info(f"Diretório da aplicação: {{app_dir}}")
        
        # Cria diretório temporário para extração
        temp_dir = tempfile.mkdtemp()
        logging.info(f"Diretório temporário: {{temp_dir}}")
        
        # Verifica se o arquivo existe
        if not os.path.exists(update_file):
            logging.error(f"Arquivo de atualização não encontrado: {{update_file}}")
            return False
            
        # Extrai os arquivos
        logging.info("Extraindo arquivos...")
        with zipfile.ZipFile(update_file, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Copia os arquivos para o diretório da aplicação
        logging.info("Copiando arquivos para o diretório da aplicação")
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, temp_dir)
                dst_path = os.path.join(app_dir, rel_path)
                
                # Cria diretório de destino se não existir
                try:
                    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                except Exception as e:
                    logging.warning(f"Erro ao criar diretório {{os.path.dirname(dst_path)}}: {{e}}")
                    continue
                
                # Tenta até 3 vezes para lidar com arquivos em uso
                for attempt in range(3):
                    try:
                        # Remove arquivos existentes primeiro (mais confiável do que substituir)
                        if os.path.exists(dst_path):
                            try:
                                os.remove(dst_path)
                            except Exception as remove_error:
                                logging.warning(f"Não foi possível remover arquivo existente {{dst_path}}: {{remove_error}}")
                                
                                # Se não conseguir remover, tenta renomear
                                try:
                                    temp_name = dst_path + ".old"
                                    if os.path.exists(temp_name):
                                        os.remove(temp_name)
                                    os.rename(dst_path, temp_name)
                                except Exception as rename_error:
                                    logging.warning(f"Não foi possível renomear arquivo existente {{dst_path}}: {{rename_error}}")
                        
                        # Copia o arquivo
                        shutil.copy2(src_path, dst_path)
                        logging.info(f"Copiado: {{rel_path}}")
                        break
                    except Exception as e:
                        logging.warning(f"Tentativa {{attempt+1}} falhou para {{rel_path}}: {{str(e)}}")
                        if attempt < 2:  # Só espera se não for a última tentativa
                            time.sleep(1)
        
        # Reinicia a aplicação se estiver em execução
        logging.info("Tentando reiniciar a aplicação")
        try:
            # Cria um script de reinicialização adequado para o sistema
            if sys.platform.startswith('win'):
                # Cria um arquivo de script para iniciar a aplicação após a atualização
                startup_script = os.path.join(tempfile.gettempdir(), "loqquei_restart.bat")
                with open(startup_script, 'w') as f:
                    f.write(f'''@echo off
REM Espera 1 segundo
timeout /t 1 /nobreak >nul
REM Tenta encerrar o processo Python atual
taskkill /F /IM "python.exe" /FI "WINDOWTITLE eq PrintManagementSystem*" >nul 2>&1
taskkill /F /IM "PrintManagementSystem.exe" >nul 2>&1
REM Espera mais 1 segundo
timeout /t 1 /nobreak >nul
REM Inicia o aplicativo atualizado
start "" "{{os.path.join(app_dir, "PrintManagementSystem.exe")}}"
REM Remove este script
del "%~f0"
''')
                
                # Executa o script de reinicialização de forma invisível
                subprocess.Popen(["cmd", "/c", startup_script], 
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
            else:
                # Cria um script shell para reinicializar a aplicação
                startup_script = os.path.join(tempfile.gettempdir(), "loqquei_restart.sh")
                with open(startup_script, 'w') as f:
                    f.write(f'''#!/bin/bash
# Espera 1 segundo
sleep 1
# Tenta encerrar o processo Python atual
pkill -f "python.*PrintManagementSystem" || true
pkill -f "PrintManagementSystem" || true
# Espera mais 1 segundo
sleep 1
# Inicia o aplicativo atualizado
nohup "{{os.path.join(app_dir, "PrintManagementSystem")}}" > /dev/null 2>&1 &
# Remove este script
rm "$0"
''')
                os.chmod(startup_script, 0o755)
                
                # Executa o script de reinicialização
                subprocess.Popen(["/bin/bash", startup_script], 
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
                
            logging.info("Script de reinicialização criado e executado")
            
        except Exception as e:
            logging.error(f"Erro ao tentar reiniciar: {{str(e)}}")
            logging.error(traceback.format_exc())
            
    except Exception as e:
        logging.error(f"Erro ao aplicar atualização: {{str(e)}}")
        logging.error(traceback.format_exc())
        return False
    finally:
        # Limpa os arquivos temporários
        try:
            logging.info("Limpando arquivos temporários")
            shutil.rmtree(temp_dir)
        except Exception as e:
            logging.error(f"Erro ao limpar diretório temporário: {{str(e)}}")
        
        try:
            os.remove(update_file)
            logging.info("Arquivo de atualização removido")
        except Exception as e:
            logging.error(f"Erro ao remover arquivo de atualização: {{str(e)}}")
    
    logging.info("Atualização concluída com sucesso!")
    return True

# Aplica a atualização
apply_update()
""")
            
            # Executa o script em um processo separado sem privilégios
            # e sem mostrar a janela do console
            startup_info = None
            creation_flags = 0
            
            # No Windows, esconde a janela do console
            if self.system == "Windows":
                startup_info = subprocess.STARTUPINFO()
                startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startup_info.wShowWindow = 0  # SW_HIDE
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            # Executa o script
            subprocess.Popen(
                [sys.executable, script_path],
                startupinfo=startup_info,
                creationflags=creation_flags,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            logger.info("Script de atualização iniciado")
            self.is_updating = False
            return True
                
        except Exception as e:
            logger.error(f"Erro ao aplicar atualização: {str(e)}")
            
            # Notifica erro na instalação
            self.notification_system.show_notification(
                "Erro na Instalação",
                f"Ocorreu um erro ao instalar a atualização: {str(e)}",
                duration=10,
                notification_type="error"
            )
            
            self.is_updating = False
            return False
    
    def _is_user_installation(self):
        """
        Verifica se a aplicação está instalada no diretório do usuário
        
        Returns:
            bool: True se for instalação de usuário
        """
        if self.system == "Windows":
            # Verifica se o diretório da aplicação está no AppData do usuário
            app_data = os.environ.get('LOCALAPPDATA', '')
            return app_data and self.app_root.lower().startswith(app_data.lower())
        else:
            # Em sistemas Unix, verifica se está no diretório home do usuário
            home_dir = os.path.expanduser("~")
            return self.app_root.startswith(home_dir)
    
    def check_and_update(self, silent=True, auto_apply=True):
        """
        Verifica e aplica atualizações automaticamente
        
        Args:
            silent (bool): Se True, não exibe notificações de "sem atualizações"
            auto_apply (bool): Se True, aplica automaticamente a atualização
            
        Returns:
            bool: True se a atualização foi iniciada
        """
        # Executa em thread separada para não bloquear a interface
        def update_thread():
            try:
                # Verifica se há atualizações
                if self.check_for_update(silent):
                    remote_version = self.update_info.get('version', 'nova versão')
                    
                    # Notificação sobre atualização disponível
                    self.notification_system.show_notification(
                        "Atualização Disponível",
                        f"Nova versão ({remote_version}) será instalada automaticamente.",
                        duration=10,
                        notification_type="info"
                    )
                    
                    if auto_apply:
                        # Aplica a atualização automaticamente
                        return self.apply_update()
                    return True
                return False
            except Exception as e:
                logger.error(f"Erro na thread de atualização: {str(e)}")
                
                # Notifica erro
                self.notification_system.show_notification(
                    "Erro na Atualização",
                    f"Ocorreu um erro ao processar a atualização: {str(e)}",
                    duration=10,
                    notification_type="error"
                )
                
                return False
        
        # Inicia a thread
        t = threading.Thread(target=update_thread, daemon=True)
        t.start()
        return True

# Função para configurar verificação periódica de atualizações
def setup_auto_updater(config, api_client):
    """
    Configura o verificador automático de atualizações
    
    Args:
        config: Configuração da aplicação
        api_client: Cliente da API
        
    Returns:
        AppUpdater: Instância do gerenciador de atualizações
    """
    updater = AppUpdater(config, api_client)
    
    # Inicia a verificação de atualizações em uma thread separada
    # para não bloquear a inicialização da aplicação
    def delayed_check():
        import time
        # Aguarda a inicialização completa da aplicação
        time.sleep(30)
        # Verifica se há atualizações
        updater.check_and_update(silent=True, auto_apply=True)
    
    check_thread = threading.Thread(target=delayed_check, daemon=True)
    check_thread.start()
    
    # Configura verificação periódica de atualizações (a cada 4 horas)
    def periodic_check():
        import time
        from datetime import datetime, timedelta
        
        # Define os minutos alvo para verificação
        target_minutes = [0, 10, 20, 30, 40, 50]
        
        while True:
            try:
                # Obtém o tempo atual
                now = datetime.now()
                current_minute = now.minute
                
                # Encontra o próximo minuto alvo
                next_minute = None
                for minute in target_minutes:
                    if minute > current_minute:
                        next_minute = minute
                        break
                
                if next_minute is None:
                    next_minute = target_minutes[0]
                    next_time = now.replace(minute=next_minute, second=0, microsecond=0) + timedelta(hours=1)
                else:
                    next_time = now.replace(minute=next_minute, second=0, microsecond=0)
                
                sleep_seconds = (next_time - now).total_seconds()
                
                if sleep_seconds > 0:
                    logger.debug(f"Próxima verificação de atualização em {sleep_seconds:.1f} segundos ({next_time.strftime('%H:%M:%S')})")
                    time.sleep(sleep_seconds)
                
                # Verifica se há atualizações no horário programado
                logger.info(f"Executando verificação periódica de atualizações às {datetime.now().strftime('%H:%M:%S')}")
                updater.check_and_update(silent=True, auto_apply=True)
                
            except Exception as e:
                logger.error(f"Erro na verificação periódica de atualizações: {str(e)}")
                time.sleep(60)
    
    periodic_thread = threading.Thread(target=periodic_check, daemon=True)
    periodic_thread.daemon = True
    periodic_thread.start()
    
    return updater
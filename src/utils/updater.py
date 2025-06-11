#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Sistema de atualização automática da aplicação - Com notificações e permissões melhoradas
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
                # Aplica a atualização com privilégios elevados (formato ZIP)
                return self._apply_update_with_privileges(update_file)
            
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
        Aplica atualização usando um executável (.exe)
        
        Args:
            exe_file (str): Caminho para o arquivo executável de atualização
            
        Returns:
            bool: True se a atualização foi iniciada com sucesso
        """
        try:
            logger.info(f"Executando atualização via executável: {exe_file}")
            
            # Executa o instalador de forma silenciosa
            if self._is_admin():
                # Se já tem privilégios, executa diretamente
                subprocess.Popen([exe_file, '/S', '/VERYSILENT', '/NORESTART', '/SP-'], 
                                creationflags=subprocess.CREATE_NO_WINDOW,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
            else:
                # Executa com privilégios elevados
                ctypes.windll.shell32.ShellExecuteW(None, "runas", exe_file, '/S /VERYSILENT /NORESTART /SP-', None, 0)
            
            logger.info("Instalador de atualização iniciado")
            self.is_updating = False
            return True
            
        except Exception as e:
            logger.error(f"Erro ao executar instalador: {str(e)}")
            self.is_updating = False
            return False
    
    def _is_admin(self):
        """
        Verifica se o aplicativo está sendo executado como administrador/root
        
        Returns:
            bool: True se o aplicativo está sendo executado com privilégios elevados
        """
        try:
            if self.system == "Windows":
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except Exception:
            return False
    
    def _apply_update_with_privileges(self, update_file):
        """
        Aplica a atualização com privilégios elevados
        
        Args:
            update_file (str): Caminho para o arquivo de atualização
            
        Returns:
            bool: True se a atualização foi iniciada com sucesso
        """
        # Cria um script para aplicar a atualização
        temp_dir = tempfile.mkdtemp()
        script_path = os.path.join(temp_dir, "apply_update.py")
        
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
import stat

# Configura logging secreto para não interferir com o usuário
log_file = os.path.join(tempfile.gettempdir(), "loqquei_update.log")
logging.basicConfig(filename=log_file, level=logging.INFO, 
                   format='%(asctime)s - %(levelname)s - %(message)s')

def set_permissions_recursive(path):
    try:
        if os.name == 'nt':  # Windows
            try:
                import win32security
                import win32con
                import win32api
                import win32net
                
                # Tenta usar a API win32 se disponível
                try:
                    # Obtém o SID para o grupo 'Everyone'
                    everyone, domain, type = win32security.LookupAccountName("", "Everyone")
                    users, domain, type = win32security.LookupAccountName("", "Users")
                    
                    # Define permissões de acesso para diretórios e arquivos
                    for root, dirs, files in os.walk(path):
                        for dir_name in dirs:
                            dir_path = os.path.join(root, dir_name)
                            try:
                                # Obtém o DACL do diretório
                                sd = win32security.GetFileSecurity(dir_path, win32security.DACL_SECURITY_INFORMATION)
                                dacl = sd.GetSecurityDescriptorDacl()
                                
                                # Adiciona permissão de acesso total para 'Everyone'
                                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, 
                                                        win32con.GENERIC_ALL, 
                                                        everyone)
                                
                                # Adiciona permissão de acesso total para 'Users'
                                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, 
                                                        win32con.GENERIC_ALL, 
                                                        users)
                                
                                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                                win32security.SetFileSecurity(dir_path, 
                                                            win32security.DACL_SECURITY_INFORMATION, 
                                                            sd)
                                
                                logging.info(f"Permissões definidas para diretório: {{dir_path}}")
                            except Exception as e:
                                logging.warning(f"Erro ao definir permissões para diretório {{dir_path}}: {{e}}")
                        
                        for file_name in files:
                            file_path = os.path.join(root, file_name)
                            try:
                                # Obtém o DACL do arquivo
                                sd = win32security.GetFileSecurity(file_path, win32security.DACL_SECURITY_INFORMATION)
                                dacl = sd.GetSecurityDescriptorDacl()
                                
                                # Adiciona permissão de acesso total para 'Everyone'
                                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, 
                                                        win32con.GENERIC_ALL, 
                                                        everyone)
                                
                                # Adiciona permissão de acesso total para 'Users'
                                dacl.AddAccessAllowedAce(win32security.ACL_REVISION, 
                                                        win32con.GENERIC_ALL, 
                                                        users)
                                
                                sd.SetSecurityDescriptorDacl(1, dacl, 0)
                                win32security.SetFileSecurity(file_path, 
                                                            win32security.DACL_SECURITY_INFORMATION, 
                                                            sd)
                                
                                # Remove flags de somente leitura, se existirem
                                attrs = win32api.GetFileAttributes(file_path)
                                if attrs & win32con.FILE_ATTRIBUTE_READONLY:
                                    win32api.SetFileAttributes(file_path, attrs & ~win32con.FILE_ATTRIBUTE_READONLY)
                                
                                logging.info(f"Permissões definidas para arquivo: {{file_path}}")
                            except Exception as e:
                                logging.warning(f"Erro ao definir permissões para arquivo {{file_path}}: {{e}}")
                                
                    # Define proprietário para o grupo Administrators
                    try:
                        admins, domain, type = win32security.LookupAccountName("", "Administrators")
                        sd = win32security.GetFileSecurity(path, win32security.OWNER_SECURITY_INFORMATION)
                        sd.SetSecurityDescriptorOwner(admins, 0)
                        win32security.SetFileSecurity(path, win32security.OWNER_SECURITY_INFORMATION, sd)
                        logging.info(f"Proprietário definido como Administrators para: {{path}}")
                    except Exception as e:
                        logging.warning(f"Erro ao definir proprietário: {{e}}")
                        
                except Exception as e:
                    logging.warning(f"Erro ao usar win32security, tentando método alternativo: {{e}}")
                    
                    # Método alternativo: usando icacls (disponível no Windows)
                    try:
                        # Garante que 'Everyone' tenha acesso total recursivamente
                        subprocess.run(['icacls', path, '/grant', 'Everyone:(OI)(CI)F', '/T', '/Q'], 
                                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        # Garante que 'Users' tenha acesso total recursivamente
                        subprocess.run(['icacls', path, '/grant', 'Users:(OI)(CI)F', '/T', '/Q'], 
                                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        # Remove atributos somente leitura recursivamente
                        subprocess.run(['attrib', '-R', f"{{path}}\\*.*", '/S', '/D'], 
                                    check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        
                        logging.info(f"Permissões definidas via icacls para: {{path}}")
                    except Exception as e:
                        logging.warning(f"Erro ao usar icacls: {{e}}")
            
            except ImportError:
                logging.warning("win32security não disponível, usando icacls")
                
                # Usando icacls (disponível no Windows)
                try:
                    # Garante que 'Everyone' tenha acesso total recursivamente
                    subprocess.run(['icacls', path, '/grant', 'Everyone:(OI)(CI)F', '/T', '/Q'], 
                                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Garante que 'Users' tenha acesso total recursivamente
                    subprocess.run(['icacls', path, '/grant', 'Users:(OI)(CI)F', '/T', '/Q'], 
                                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    # Remove atributos somente leitura recursivamente
                    subprocess.run(['attrib', '-R', f"{{path}}\\*.*", '/S', '/D'], 
                                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    
                    logging.info(f"Permissões definidas via icacls para: {{path}}")
                except Exception as e:
                    logging.warning(f"Erro ao usar icacls: {{e}}")
                    
        else:  # Unix/Linux/Mac
            # Define permissões 755 para diretórios e 644/755 para arquivos
            for root, dirs, files in os.walk(path):
                for dir_name in dirs:
                    try:
                        dir_path = os.path.join(root, dir_name)
                        os.chmod(dir_path, 0o755)  # rwxr-xr-x
                        logging.info(f"Permissões definidas para diretório: {{dir_path}}")
                    except Exception as e:
                        logging.warning(f"Erro ao definir permissões para diretório {{dir_path}}: {{e}}")
                
                for file_name in files:
                    try:
                        file_path = os.path.join(root, file_name)
                        if os.access(file_path, os.X_OK):
                            os.chmod(file_path, 0o755)  # rwxr-xr-x para executáveis
                        else:
                            os.chmod(file_path, 0o644)  # rw-r--r-- para arquivos normais
                        logging.info(f"Permissões definidas para arquivo: {{file_path}}")
                    except Exception as e:
                        logging.warning(f"Erro ao definir permissões para arquivo {{file_path}}: {{e}}")
                        
            # Tenta definir o proprietário para o usuário/grupo padrão se estiver rodando como root
            if os.geteuid() == 0:
                try:
                    import pwd
                    import grp
                    
                    # Obtém UID/GID do usuário que provavelmente iniciou o app (não root)
                    username = os.environ.get('SUDO_USER') or os.environ.get('USER') or 'nobody'
                    uid = pwd.getpwnam(username).pw_uid
                    gid = pwd.getpwnam(username).pw_gid
                    
                    # Aplica recursivamente
                    for root, dirs, files in os.walk(path):
                        for dir_name in dirs:
                            try:
                                dir_path = os.path.join(root, dir_name)
                                os.chown(dir_path, uid, gid)
                            except:
                                pass
                                
                        for file_name in files:
                            try:
                                file_path = os.path.join(root, file_name)
                                os.chown(file_path, uid, gid)
                            except:
                                pass
                                
                    logging.info(f"Proprietário definido como {{username}} para: {{path}}")
                except Exception as e:
                    logging.warning(f"Erro ao definir proprietário: {{e}}")
    except Exception as e:
        logging.error(f"Erro ao definir permissões recursivas: {{e}}")

def apply_update():
    try:
        logging.info("Iniciando aplicação da atualização")
        
        # Caminho do arquivo de atualização
        update_file = {repr(update_file)}
        logging.info(f"Arquivo de atualização: {{update_file}}")
        
        # Diretório da aplicação
        app_dir = {repr(self.app_root)}
        logging.info(f"Diretório da aplicação: {{app_dir}}")
        
        # Cria diretório temporário para extração
        temp_dir = tempfile.mkdtemp()
        logging.info(f"Diretório temporário: {{temp_dir}}")
        
        # Extrai os arquivos
        logging.info("Extraindo arquivos...")
        with zipfile.ZipFile(update_file, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # Define permissões adequadas para os arquivos extraídos
        logging.info("Definindo permissões para os arquivos extraídos...")
        set_permissions_recursive(temp_dir)
        
        # Copia os arquivos para o diretório da aplicação
        logging.info("Copiando arquivos para o diretório da aplicação")
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                src_path = os.path.join(root, file)
                rel_path = os.path.relpath(src_path, temp_dir)
                dst_path = os.path.join(app_dir, rel_path)
                
                # Cria diretório de destino se não existir
                os.makedirs(os.path.dirname(dst_path), exist_ok=True)
                
                # Tenta até 3 vezes para lidar com arquivos em uso
                for attempt in range(3):
                    try:
                        shutil.copy2(src_path, dst_path)
                        logging.info(f"Copiado: {{rel_path}}")
                        break
                    except Exception as e:
                        logging.warning(f"Tentativa {{attempt+1}} falhou para {{rel_path}}: {{str(e)}}")
                        time.sleep(1)
        
        # Define permissões adequadas para os arquivos copiados
        logging.info("Definindo permissões para os arquivos instalados...")
        set_permissions_recursive(app_dir)
        
        # Reinicia a aplicação se estiver em execução
        logging.info("Tentando reiniciar a aplicação")
        try:
            # Tenta encontrar o processo da aplicação
            if sys.platform.startswith('win'):
                # Cria um arquivo de script para iniciar a aplicação após a atualização
                startup_script = os.path.join(tempfile.gettempdir(), "loqquei_restart.bat")
                with open(startup_script, 'w') as f:
                    f.write(f'''@echo off
taskkill /IM "python.exe" /F >nul 2>&1
timeout /t 1 >nul
start "" /B "{{sys.executable}}" "{{os.path.join(app_dir, "main.py")}}"
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
pkill -f "python.*main.py" || true
sleep 1
nohup "{{sys.executable}}" "{{os.path.join(app_dir, "main.py")}}" > /dev/null 2>&1 &
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
            
    except Exception as e:
        logging.error(f"Erro ao aplicar atualização: {{str(e)}}")
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
        
        if self._is_admin():
            # Se já tem privilégios, executa diretamente
            try:
                subprocess.Popen([sys.executable, script_path], 
                                 creationflags=subprocess.CREATE_NO_WINDOW if self.system == "Windows" else 0,
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                self.is_updating = False
                return True
            except Exception as e:
                logger.error(f"Erro ao executar script de atualização: {str(e)}")
                self.is_updating = False
                return False
        else:
            # Executa com privilégios elevados de forma invisível
            try:
                if self.system == "Windows":
                    # No Windows, usa ShellExecute com o verbo "runas" e SW_HIDE
                    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, 
                                                       f'"{script_path}"', None, 0)
                elif self.system == "Darwin":  # macOS
                    # Cria um script AppleScript temporário para execução invisível
                    temp_script = os.path.join(tempfile.gettempdir(), "invisible_sudo.scpt")
                    with open(temp_script, 'w') as f:
                        f.write(f'''
do shell script "\\"{{sys.executable}}\\" \\"{{script_path}}\\"" with administrator privileges without altering line endings
''')
                    
                    # Executa o AppleScript
                    subprocess.Popen(["osascript", temp_script],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                    
                    # Remove o script temporário após um atraso
                    threading.Timer(5, lambda: os.remove(temp_script) if os.path.exists(temp_script) else None).start()
                else:  # Linux ou outros
                    # Cria um script para executar com sudo sem prompt visível
                    temp_script = os.path.join(tempfile.gettempdir(), "invisible_sudo.sh")
                    with open(temp_script, 'w') as f:
                        f.write(f'''#!/bin/bash
export SUDO_ASKPASS=/bin/true
for cmd in pkexec gksudo kdesudo sudo; do
    if command -v $cmd >/dev/null 2>&1; then
        if [ "$cmd" = "sudo" ]; then
            $cmd -A "{sys.executable}" "{script_path}" >/dev/null 2>&1 &
        else
            $cmd "{sys.executable}" "{script_path}" >/dev/null 2>&1 &
        fi
        exit 0
    fi
done

# Fallback - tenta executar diretamente
"{sys.executable}" "{script_path}" >/dev/null 2>&1 &
''')
                    
                    # Torna o script executável
                    os.chmod(temp_script, 0o755)
                    
                    # Executa o script
                    subprocess.Popen(["/bin/bash", temp_script],
                                    stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
                    
                    # Remove o script temporário após um atraso
                    threading.Timer(5, lambda: os.remove(temp_script) if os.path.exists(temp_script) else None).start()
                
                self.is_updating = False
                return True
            except Exception as e:
                logger.error(f"Erro ao solicitar privilégios para atualização: {str(e)}")
                self.is_updating = False
                return False
    
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
@echo off
REM Script para executar o Sistema de Gerenciamento de Impressao

REM Obtem o diretorio do script
set "APP_DIR=%~dp0.."

REM Muda para o diretorio da aplicacao
cd /d "%APP_DIR%"

REM Verifica se Python esta disponivel
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado! > "%APP_DIR%\error.log"
    echo Por favor, verifique se o Python foi instalado corretamente. >> "%APP_DIR%\error.log"
    
    REM Tenta mostrar mensagem de erro sem travar
    msg * "ERRO: Python nao encontrado! Verifique a instalacao." 2>nul
    exit /b 1
)

REM Verifica se as dependencias estao instaladas
python -c "import wx" 2>nul
if errorlevel 1 (
    echo Dependencias nao encontradas. Executando instalacao... > "%APP_DIR%\install.log"
    call "%APP_DIR%\scripts\install_dependencies_silent.bat"
    if errorlevel 1 (
        echo Erro na instalacao das dependencias. >> "%APP_DIR%\install.log"
        exit /b 1
    )
)

REM Executa a aplicacao
echo Iniciando Sistema de Gerenciamento de Impressao... > "%APP_DIR%\startup.log"
start "" python "%APP_DIR%\main.py"

exit /b 0
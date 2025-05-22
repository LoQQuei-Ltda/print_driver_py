@echo off
echo Instalando dependencias do Sistema de Gerenciamento de Impressao...
echo.

REM Verifica se Python esta instalado
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado no sistema!
    echo Por favor, instale o Python 3.8 ou superior.
    exit /b 1
)

echo Python encontrado. Atualizando pip...
python -m pip install --upgrade pip

echo.
echo Instalando dependencias basicas...
python -m pip install --upgrade setuptools wheel

echo.
echo Instalando dependencias da aplicacao...

REM Instala dependencias uma por uma para melhor controle de erros
echo Instalando wxPython...
python -m pip install wxPython>=4.2.0

echo Instalando requests...
python -m pip install requests>=2.31.0

echo Instalando pypdf...
python -m pip install pypdf>=5.5.0

echo Instalando appdirs...
python -m pip install appdirs>=1.4.4

echo Instalando PyYAML...
python -m pip install pyyaml>=6.0.1

echo Instalando Pillow...
python -m pip install pillow>=10.0.1

echo Instalando watchdog...
python -m pip install watchdog>=2.3.0

echo Instalando pyipp...
python -m pip install pyipp>=0.11.0

REM Dependencias especificas do Windows
echo Instalando dependencias do Windows...
python -m pip install pywin32>=306
python -m pip install pywin32-ctypes>=0.2.0

echo.
echo Instalacao de dependencias concluida!
echo.

REM Verifica instalacoes
echo Verificando instalacoes...
python -c "import wx; print('wxPython: OK')" 2>nul || echo "wxPython: ERRO"
python -c "import requests; print('requests: OK')" 2>nul || echo "requests: ERRO"
python -c "import pypdf; print('pypdf: OK')" 2>nul || echo "pypdf: ERRO"
python -c "import appdirs; print('appdirs: OK')" 2>nul || echo "appdirs: ERRO"
python -c "import yaml; print('PyYAML: OK')" 2>nul || echo "PyYAML: ERRO"
python -c "import PIL; print('Pillow: OK')" 2>nul || echo "Pillow: ERRO"
python -c "import watchdog; print('watchdog: OK')" 2>nul || echo "watchdog: ERRO"
python -c "import pyipp; print('pyipp: OK')" 2>nul || echo "pyipp: ERRO"

echo.
echo Instalacao finalizada!
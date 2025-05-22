@echo off
echo ===================================
echo Construindo o Sistema de Gerenciamento de Impressão
echo ===================================
echo.

REM Verificar se o Inno Setup está instalado
if not exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
  if not exist "%PROGRAMFILES%\Inno Setup 6\ISCC.exe" (
    echo Erro: Inno Setup 6 não foi encontrado
    echo Por favor, instale o Inno Setup 6 antes de continuar
    echo Download: https://jrsoftware.org/isdl.php
    pause
    exit /b 1
  )
)

echo Limpando diretórios de build anteriores...
if exist "build" (
  echo - Removendo build...
  rmdir /s /q build
)

if exist "Output" (
  echo - Removendo pasta Output...
  rmdir /s /q Output
)

REM Pausa para garantir que todos os processos foram encerrados
timeout /t 2 /nobreak >nul

echo.
echo Construindo aplicação...
call python setup_cx_freeze.py build
if %ERRORLEVEL% NEQ 0 (
  echo Erro: Não foi possível construir a aplicação
  pause
  exit /b 1
)

echo.
echo Compilando o instalador com Inno Setup...
if exist "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" (
  "%PROGRAMFILES(X86)%\Inno Setup 6\ISCC.exe" installer.iss
) else (
  "%PROGRAMFILES%\Inno Setup 6\ISCC.exe" installer.iss
)

if %ERRORLEVEL% NEQ 0 (
  echo Erro: Não foi possível compilar o instalador
  pause
  exit /b 1
)

echo.
echo Construção concluída com sucesso!
echo O instalador está disponível na pasta "Output"
echo.
pause
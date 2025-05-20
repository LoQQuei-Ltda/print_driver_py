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

@REM echo Limpando diretórios de build anteriores...
@REM if exist "dist" (
@REM   echo - Removendo pasta dist...
@REM   rmdir /s /q dist
@REM )

@REM if exist "build" (
@REM   echo - Removendo build...
@REM   rmdir /s /q build
@REM )

@REM if exist "Output" (
@REM   echo - Removendo pasta Output...
@REM   rmdir /s /q Output
@REM )

@REM REM Pausa para garantir que todos os processos foram encerrados
@REM timeout /t 2 /nobreak >nul

@REM if exist "dist" (
@REM   echo - Removendo pasta dist...
@REM   rmdir /s /q dist 2>nul
@REM   if exist "dist" (
@REM     rd /s /q dist 2>nul
@REM   )
@REM )

@REM echo.
@REM echo Construindo aplicação...
@REM call python setup.py bdist_pyinstaller
@REM if %ERRORLEVEL% NEQ 0 (
@REM   echo Erro: Não foi possível construir a aplicação
@REM   pause
@REM   exit /b 1
@REM )

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
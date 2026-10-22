@echo off
setlocal
cd /d "%~dp0\.."
title PadBridge - gerar o programa
echo.
echo === PadBridge: gerando o PadBridge.exe ===
echo (feche o PadBridge antes, se estiver aberto)
echo.
if not exist "padbridge\app.py" ( echo ERRO: rode este script dentro do repositorio PadBridge. & goto :erro )
if not exist "padbridge\web\index.html" (
  echo Gerando a tela e o mapeamento...
  py -3 tools\gerar.py
  if errorlevel 1 goto :erro
)

set VENV=.venv
if not exist "%VENV%\Scripts\python.exe" (
  echo Criando o ambiente virtual, so na primeira vez...
  py -3.12 -m venv %VENV%
)
if not exist "%VENV%\Scripts\python.exe" ( echo ERRO: nao consegui criar o ambiente. Python 3.12 instalado? & goto :erro )

echo Instalando as dependencias...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 ( echo ERRO ao instalar as dependencias. & goto :erro )

echo Gerando o .exe...
"%VENV%\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --noconsole --name PadBridge --add-data "padbridge\web\index.html;web" --hidden-import mido.backends.rtmidi --hidden-import pystray._win32 --collect-submodules mido padbridge\__main__.py
if errorlevel 1 ( echo ERRO ao gerar o .exe. & goto :erro )

echo.
echo PRONTO: dist\PadBridge.exe
echo Abra com duplo clique: o icone aparece ao lado do relogio do Windows.
pause
exit /b 0

:erro
echo.
echo Nao foi possivel concluir. Copie a mensagem acima e abra uma issue.
pause
exit /b 1

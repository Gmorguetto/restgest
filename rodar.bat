@echo off
rem ============================================================
rem  RestGest - prepara e inicia o sistema no Windows.
rem  Dois cliques neste arquivo fazem tudo:
rem   1. encontram o Python
rem   2. criam o ambiente virtual .venv e instalam as dependencias
rem   3. criam o arquivo .env com chave e senha aleatorias
rem   4. criam o banco com os dados de demonstracao
rem   5. iniciam o servidor em http://127.0.0.1:5000
rem  Os passos 2 a 4 so demoram na primeira vez.
rem ============================================================
setlocal
cd /d "%~dp0"
title RestGest

echo.
echo === RestGest ===
echo.

rem --- 1. Python ---
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if defined PY goto achou_python
python --version >nul 2>nul && set "PY=python"
if defined PY goto achou_python
echo Python nao encontrado.
echo Instale o Python 3.10 ou mais recente em https://www.python.org/downloads/
echo e marque a opcao "Add python.exe to PATH" durante a instalacao.
goto erro

:achou_python
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if not errorlevel 1 goto ambiente
echo Este sistema precisa do Python 3.10 ou mais recente. Versao encontrada:
%PY% --version
goto erro

rem --- 2. Ambiente virtual e dependencias ---
:ambiente
set "VPY=.venv\Scripts\python.exe"
if exist "%VPY%" goto instalar
echo Criando o ambiente virtual .venv (so na primeira vez)...
%PY% -m venv .venv
if errorlevel 1 goto erro

:instalar
echo Conferindo as dependencias (na primeira vez demora um pouco)...
"%VPY%" -m pip install --disable-pip-version-check -q -r requirements.txt
if errorlevel 1 goto erro

rem --- 3. Arquivo .env com segredos gerados na hora ---
if exist ".env" goto banco
echo Criando o arquivo .env com uma chave e uma senha de demonstracao aleatorias...
"%VPY%" -c "import secrets; open('.env', 'w', encoding='utf-8').write(f'SECRET_KEY={secrets.token_hex(32)}\nSENHA_DEMO=demo-{secrets.token_hex(4)}\n')"
if errorlevel 1 goto erro

rem --- 4. Banco de dados com os dados de demonstracao ---
:banco
if exist "instance\restaurante.db" goto iniciar
echo Criando o banco com os dados de demonstracao...
"%VPY%" -m flask seed-demo
if errorlevel 1 goto erro

rem --- 5. Servidor ---
:iniciar
echo.
for /f "usebackq tokens=1,* delims==" %%a in (".env") do if "%%a"=="SENHA_DEMO" echo Senha dos usuarios de demonstracao: %%b
echo Os e-mails dos usuarios aparecem na tela de login.
echo.
echo Sistema em http://127.0.0.1:5000 - para parar, feche esta janela ou aperte Ctrl+C.
echo.
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://127.0.0.1:5000'"
"%VPY%" -m flask run
goto fim

:erro
echo.
echo Algo deu errado. Leia a mensagem acima.

:fim
echo.
pause
endlocal

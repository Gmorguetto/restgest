@echo off
rem ============================================================
rem  RestGest - recria os dados de demonstracao com a data de hoje.
rem  Use no dia da apresentacao: o painel mostra as vendas "de hoje",
rem  entao dados criados em outro dia aparecem zerados.
rem  ATENCAO: apaga tudo o que foi cadastrado no banco local.
rem ============================================================
setlocal
cd /d "%~dp0"
title RestGest - recriar demonstracao

set "VPY=.venv\Scripts\python.exe"
if exist "%VPY%" goto confirmar
echo Rode primeiro o rodar.bat: ele prepara o ambiente e cria o arquivo .env.
goto fim

:confirmar
echo Isto apaga tudo o que foi cadastrado no banco local e recria os dois
echo restaurantes de demonstracao, com vendas e mesas de hoje.
echo.
choice /c SN /m "Continuar? (S = sim, N = nao)"
if errorlevel 2 goto fim
"%VPY%" -m flask seed-demo
if errorlevel 1 goto erro
echo.
echo Pronto. Se o sistema ja estiver aberto no navegador, e so atualizar a pagina.
goto fim

:erro
echo.
echo Algo deu errado. Leia a mensagem acima.

:fim
echo.
pause
endlocal

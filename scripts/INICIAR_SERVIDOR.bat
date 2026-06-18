@echo off
cd /d "%~dp0.."
echo.
echo  Iniciando servidor de Disponibilidade de Condutores...
echo  Nao feche esta janela enquanto quiser usar o sistema.
echo.
python servidor.py
if errorlevel 1 (
    echo.
    echo  Erro ao iniciar o servidor.
    pause
)

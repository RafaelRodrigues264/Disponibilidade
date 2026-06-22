@echo off
cd /d "%~dp0.."
echo.
echo  Enviando dados para o servidor...
echo.
python gerar_dados.py
if errorlevel 1 (
    echo.
    echo  Erro ao executar. Verifique as mensagens acima.
    pause
)

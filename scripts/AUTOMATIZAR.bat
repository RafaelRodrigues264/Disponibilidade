@echo off
cd /d "%~dp0.."
echo.
echo  Automacao ATSLog - Fichas Ponto + Dashboard
echo  ============================================
echo.

python automacao_atslog.py

if errorlevel 1 (
    echo.
    echo  Erro durante a automacao. Veja as mensagens acima.
    pause
)

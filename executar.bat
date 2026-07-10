@echo off
chcp 65001 >nul
cd /d "%~dp0"
call venv\Scripts\activate.bat
echo.
echo  ================================================
echo   Iniciando DashID...
echo   Dashboard de Performance de Lojas - Cp Fani
echo  ================================================
echo.
echo  Abrindo o dashboard no navegador...
echo  Se nao abrir automaticamente, acesse: http://localhost:8501
echo.
streamlit run app.py --server.headless true
echo.
echo  Dashboard encerrado.
pause

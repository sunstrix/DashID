@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: ============================================================================
:: DashID - Script de Execução Rápida
:: ============================================================================
:: Este script ativa o ambiente virtual e inicia o dashboard Streamlit.
:: Use este arquivo após executar instalar.bat pela primeira vez.
::
:: Autor: Alex Paulo
:: Versão: 0.2.0
:: ============================================================================

echo.
echo  ================================================
echo   DashID - Dashboard de Performance
echo   NSF Cosmeticos e Presentes (Cp Fani)
echo  ================================================
echo.

:: Verifica se o ambiente virtual existe
if not exist "venv\Scripts\activate.bat" (
    echo  [ERRO] Ambiente virtual nao encontrado.
    echo  Execute primeiro o arquivo 'instalar.bat' para configurar o projeto.
    echo.
    pause
    exit /b 1
)

:: Ativa o ambiente virtual
echo  Ativando ambiente virtual...
call venv\Scripts\activate.bat
echo  [OK] Ambiente virtual ativado.
echo.

:: Verifica se o app.py existe
if not exist "app.py" (
    echo  [ERRO] Arquivo app.py nao encontrado.
    echo  Certifique-se de executar este script na raiz do projeto DashID.
    echo.
    pause
    exit /b 1
)

:: Inicia o Streamlit
echo  ================================================
echo   Iniciando DashID...
echo   Dashboard de Performance de Lojas - Cp Fani
echo   Meta do ID: 115%%
echo  ================================================
echo.
echo  O dashboard sera aberto automaticamente no seu navegador.
echo  Se nao abrir, acesse: http://localhost:8501
echo.
echo  Para encerrar o dashboard, pressione Ctrl+C nesta janela.
echo.
echo  ================================================
echo.

:: Executa o Streamlit
streamlit run app.py --server.headless true

:: Se o Streamlit encerrar, pausa para o usuário ver erros
echo.
echo  ================================================
echo   Dashboard encerrado.
echo  ================================================
echo.
pause
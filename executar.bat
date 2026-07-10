@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: DashID - Script de Execucao Rapida
:: ============================================================================
:: Este script:
:: 1. Ativa o ambiente virtual
:: 2. Inicia o dashboard Streamlit
:: 3. Gera log de execucao (executar_log.txt)
:: 4. NUNCA fecha sozinho - sempre pausa no final
::
:: Autor: Alex Paulo
:: Versao: 0.2.2
:: ============================================================================

:: Muda para o diretorio do script
cd /d "%~dp0"

:: Define o arquivo de log
set LOGFILE=%~dp0executar_log.txt

:: Limpa log anterior e cria novo com timestamp
echo ==================================================================== > "%LOGFILE%"
echo  DASHID - LOG DE EXECUCAO                                             >> "%LOGFILE%"
echo  Data/Hora: %DATE% %TIME%                                            >> "%LOGFILE%"
echo  Diretorio: %CD%                                                     >> "%LOGFILE%"
echo ==================================================================== >> "%LOGFILE%"
echo. >> "%LOGFILE%"

:: Funcao auxiliar para logar mensagens
goto :main

:log
echo %~1
echo [%DATE% %TIME%] %~1 >> "%LOGFILE%"
goto :eof

:main
echo.
echo  ================================================
echo   Iniciando DashID...
echo   Dashboard de Performance de Lojas - Cp Fani
echo   Meta do ID: 115%%
echo  ================================================
echo.

:: Verifica se o ambiente virtual existe
if not exist "venv\Scripts\activate.bat" (
    call :log "[ERRO] Ambiente virtual nao encontrado."
    call :log "Execute primeiro o arquivo 'instalar.bat' para configurar o projeto."
    goto :error
)

:: Ativa o ambiente virtual
call :log "Ativando ambiente virtual..."
call venv\Scripts\activate.bat >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 (
    call :log "[ERRO] Falha ao ativar o ambiente virtual."
    goto :error
)
call :log "[OK] Ambiente virtual ativado."

:: Verifica se o app.py existe
if not exist "app.py" (
    call :log "[ERRO] Arquivo app.py nao encontrado."
    call :log "Certifique-se de executar este script na raiz do projeto DashID."
    goto :error
)

call :log ""
call :log "================================================"
call :log " Dashboard abrindo no navegador..."
call :log " Se nao abrir, acesse: http://localhost:8501"
call :log " Para encerrar, pressione Ctrl+C nesta janela."
call :log "================================================"
call :log ""

:: Executa o Streamlit
call :log "Iniciando Streamlit..."
streamlit run app.py --server.headless true >> "%LOGFILE%" 2>&1

:: Se o Streamlit encerrar
call :log ""
call :log "================================================"
call :log " Dashboard encerrado."
call :log "================================================"
goto :show_log

:error
call :log ""
call :log "================================================"
call :log " ERRO AO INICIAR O DASHBOARD"
call :log "================================================"
call :log ""
call :log "Verifique o arquivo de log para mais detalhes:"
call :log "   %LOGFILE%"
call :log ""
call :log "Possiveis causas:"
call :log "  - Ambiente virtual nao criado (execute instalar.bat)"
call :log "  - Arquivo app.py nao encontrado"
call :log "  - Porta 8501 ja esta em uso"
call :log ""
call :log "================================================"
goto :show_log

:show_log
echo.
echo.
echo ============================================================
echo  LOG DA EXECUCAO (ultimas 30 linhas):
echo ============================================================
echo.
:: Mostra as ultimas 30 linhas do log
powershell -command "Get-Content '%LOGFILE%' -Tail 30"
echo.
echo ============================================================
echo  Log completo salvo em: %LOGFILE%
echo ============================================================
echo.
echo Pressione qualquer tecla para SAIR...
pause >nul
endlocal
exit /b
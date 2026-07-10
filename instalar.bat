@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: DashID - Script de Instalacao Automatizada (Windows)
:: Versao com LOG para diagnostico de erros
:: ============================================================================
:: Este script:
:: 1. Gera um arquivo de log (instalar_log.txt) com TODAS as saidas
:: 2. NUNCA fecha sozinho - sempre pausa no final (sucesso OU erro)
:: 3. Mostra o log ao final para o usuario ver o que aconteceu
::
:: Autor: Alex Paulo
:: Versao: 0.2.2
:: ============================================================================

:: Muda para o diretorio do script
cd /d "%~dp0"

:: Define o arquivo de log
set LOGFILE=%~dp0instalar_log.txt

:: Limpa log anterior e cria novo com timestamp
echo ==================================================================== > "%LOGFILE%"
echo  DASHID - LOG DE INSTALACAO                                           >> "%LOGFILE%"
echo  Data/Hora: %DATE% %TIME%                                            >> "%LOGFILE%"
echo  Diretorio: %CD%                                                     >> "%LOGFILE%"
echo ==================================================================== >> "%LOGFILE%"
echo. >> "%LOGFILE%"

:: Funcao auxiliar para logar mensagens (echo na tela + no log)
:: Uso: call :log "mensagem"
goto :main

:log
echo %~1
echo [%DATE% %TIME%] %~1 >> "%LOGFILE%"
goto :eof

:log_only
echo [%DATE% %TIME%] %~1 >> "%LOGFILE%"
goto :eof

:main
:: Redireciona TUDO (stdout + stderr) para o log, mas mantendo echo na tela
:: Vamos fazer manualmente para ter controle

call :log ""
call :log "================================================"
call :log " DashID - Instalador Automatizado"
call :log " NSF Cosmeticos e Presentes (Cp Fani)"
call :log " Meta do ID: 115%%"
call :log "================================================"
call :log ""

:: --------------------------------------------------------------------
:: 1. Verificar Python
:: --------------------------------------------------------------------
call :log "[1/5] Verificando instalacao do Python..."
python --version > "%TEMP%\pyver.tmp" 2>&1
if %errorlevel% neq 0 (
    call :log ""
    call :log "[ERRO] Python nao foi encontrado no PATH do sistema."
    call :log "Por favor, instale o Python 3.11 ou superior de https://www.python.org/"
    call :log "Certifique-se de marcar a opcao 'Add Python to PATH'."
    goto :error
)
set /p PYVER=<"%TEMP%\pyver.tmp"
del "%TEMP%\pyver.tmp" 2>nul
call :log "[OK] %PYVER% encontrado."
call :log ""

:: --------------------------------------------------------------------
:: 2. Criar Ambiente Virtual
:: --------------------------------------------------------------------
call :log "[2/5] Configurando ambiente virtual..."
if not exist "venv" (
    call :log "Criando ambiente virtual em 'venv'..."
    python -m venv venv >> "%LOGFILE%" 2>&1
    if !errorlevel! neq 0 (
        call :log "[ERRO] Falha ao criar o ambiente virtual."
        goto :error
    )
    call :log "[OK] Ambiente virtual criado com sucesso."
) else (
    call :log "[OK] Ambiente virtual 'venv' ja existe."
)
call :log ""

:: --------------------------------------------------------------------
:: 3. Ativar venv e atualizar ferramentas
:: --------------------------------------------------------------------
call :log "[3/5] Ativando ambiente virtual e atualizando ferramentas..."

if not exist "venv\Scripts\activate.bat" (
    call :log "[ERRO] Arquivo venv\Scripts\activate.bat nao encontrado."
    goto :error
)

call venv\Scripts\activate.bat >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 (
    call :log "[ERRO] Falha ao ativar o ambiente virtual."
    goto :error
)
call :log "[OK] Ambiente virtual ativado."

call :log "Atualizando pip, setuptools e wheel..."
python -m pip install --upgrade pip setuptools wheel >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 (
    call :log "[AVISO] Falha ao atualizar pip/setuptools/wheel. Continuando..."
) else (
    call :log "[OK] pip, setuptools e wheel atualizados."
)
call :log ""

:: --------------------------------------------------------------------
:: 4. Instalar Dependencias
:: --------------------------------------------------------------------
call :log "[4/5] Instalando dependencias do projeto..."
if not exist "requirements.txt" (
    call :log "[ERRO] Arquivo requirements.txt nao encontrado."
    call :log "Certifique-se de executar este script na raiz do projeto DashID."
    goto :error
)

call :log "Instalando (isso pode levar alguns minutos)..."
call :log ""

:: Tenta instalar tudo
pip install -r requirements.txt >> "%LOGFILE%" 2>&1
if !errorlevel! neq 0 (
    call :log ""
    call :log "[AVISO] Instalacao padrao falhou."
    call :log "Tentando instalar Pillow com binarios pre-compilados..."
    call :log ""
    
    pip install "pillow>=11.0.0" --only-binary :all: >> "%LOGFILE%" 2>&1
    if !errorlevel! neq 0 (
        call :log "[ERRO] Falha ao instalar Pillow."
        goto :error
    )
    
    call :log "[OK] Pillow instalado via binarios pre-compilados."
    call :log "Instalando demais dependencias..."
    
    pip install -r requirements.txt >> "%LOGFILE%" 2>&1
    if !errorlevel! neq 0 (
        call :log "[ERRO] Falha ao instalar outras dependencias."
        goto :error
    )
)

call :log "[OK] Todas as dependencias instaladas com sucesso."
call :log ""

:: --------------------------------------------------------------------
:: 5. Criar executar.bat
:: --------------------------------------------------------------------
call :log "[5/5] Criando script de execucao rapida (executar.bat)..."

(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%%~dp0"
echo call venv\Scripts\activate.bat
echo echo.
echo echo  ================================================
echo echo   Iniciando DashID...
echo echo   Dashboard de Performance de Lojas - Cp Fani
echo echo   Meta do ID: 115%%%%
echo echo  ================================================
echo echo.
echo echo  O dashboard sera aberto automaticamente no seu navegador.
echo echo  Se nao abrir, acesse: http://localhost:8501
echo echo.
echo echo  Para encerrar o dashboard, pressione Ctrl+C nesta janela.
echo echo.
echo streamlit run app.py --server.headless true
echo echo.
echo echo  Dashboard encerrado.
echo pause
) > executar.bat

if !errorlevel! neq 0 (
    call :log "[ERRO] Falha ao criar executar.bat."
    goto :error
)
call :log "[OK] Arquivo 'executar.bat' criado."
call :log ""

:: --------------------------------------------------------------------
:: SUCESSO
:: --------------------------------------------------------------------
goto :success

:success
call :log ""
call :log "================================================"
call :log "  INSTALACAO CONCLUIDA COM SUCESSO!"
call :log "================================================"
call :log ""
call :log "Para iniciar o dashboard, basta executar:"
call :log ""
call :log "   executar.bat"
call :log ""
call :log "Ou abra o terminal na pasta do projeto e digite:"
call :log "   streamlit run app.py"
call :log ""
call :log "================================================"
goto :show_log

:error
call :log ""
call :log "================================================"
call :log "  ERRO DURANTE A INSTALACAO"
call :log "================================================"
call :log ""
call :log "Verifique o arquivo de log para mais detalhes:"
call :log "   %LOGFILE%"
call :log ""
call :log "Possiveis causas:"
call :log "  - Python nao instalado ou nao esta no PATH"
call :log "  - Sem conexao com a internet"
call :log "  - Permissoes insuficientes (tente executar como Admin)"
call :log "  - Antivirus bloqueando a instalacao"
call :log ""
call :log "================================================"
goto :show_log

:show_log
echo.
echo.
echo ============================================================
echo  LOG DA INSTALACAO (ultimas 30 linhas):
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
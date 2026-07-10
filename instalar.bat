@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: Muda para o diretório onde este script está localizado
cd /d "%~dp0"

:: ============================================================================
:: DashID - Script de Instalação Automatizada (Windows)
:: ============================================================================
:: Este script configura o ambiente virtual, instala as dependências e
:: cria um atalho (executar.bat) para iniciar o dashboard facilmente.
::
:: CORREÇÕES:
:: - Suporte a Python 3.14+ (Pillow >= 11.0.0)
:: - Fallback com --only-binary :all: se Pillow falhar
:: - Cria executar.bat em vez de run.bat
::
:: Autor: Alex Paulo
:: Versão: 0.2.0
:: ============================================================================

echo.
echo  ================================================
echo   DashID - Instalador Automatizado
echo   NSF Cosmeticos e Presentes (Cp Fani)
echo  ================================================
echo.

:: ----------------------------------------------------------------------------
:: 1. Verificar se o Python está instalado
:: ----------------------------------------------------------------------------
echo [1/5] Verificando instalacao do Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo  [ERRO] Python nao foi encontrado no PATH do sistema.
    echo  Por favor, instale o Python 3.11 ou superior de https://www.python.org/
    echo  Certifique-se de marcar a opcao "Add Python to PATH" durante a instalacao.
    echo.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK] Python %PYVER% encontrado.
echo.

:: ----------------------------------------------------------------------------
:: 2. Criar Ambiente Virtual (venv)
:: ----------------------------------------------------------------------------
echo [2/5] Configurando ambiente virtual...
if not exist "venv" (
    echo  Criando ambiente virtual em 'venv'...
    python -m venv venv
    if %errorlevel% neq 0 (
        echo  [ERRO] Falha ao criar o ambiente virtual.
        pause
        exit /b 1
    )
    echo  [OK] Ambiente virtual criado com sucesso.
) else (
    echo  [OK] Ambiente virtual 'venv' ja existe.
)
echo.

:: ----------------------------------------------------------------------------
:: 3. Ativar Ambiente Virtual e Atualizar pip
:: ----------------------------------------------------------------------------
echo [3/5] Ativando ambiente virtual e atualizando pip...
call venv\Scripts\activate.bat

python -m pip install --upgrade pip --quiet
if %errorlevel% neq 0 (
    echo  [AVISO] Falha ao atualizar o pip. Continuando...
) else (
    echo  [OK] pip atualizado.
)
echo.

:: ----------------------------------------------------------------------------
:: 4. Instalar Dependências
:: ----------------------------------------------------------------------------
echo [4/5] Instalando dependencias do projeto...
if not exist "requirements.txt" (
    echo  [ERRO] Arquivo requirements.txt nao encontrado.
    echo  Certifique-se de executar este script na raiz do projeto DashID.
    pause
    exit /b 1
)

echo  Isso pode levar alguns minutos. Por favor, aguarde...
echo.

:: Tenta instalar normalmente primeiro
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo.
    echo  [AVISO] Instalacao padrao falhou. Tentando com --only-binary :all:...
    echo  Isso resolve problemas com Pillow em Python 3.14+.
    echo.
    
    :: Tenta instalar Pillow primeiro com --only-binary
    pip install "pillow>=11.0.0" --only-binary :all: --quiet
    if %errorlevel% neq 0 (
        echo  [ERRO] Falha ao instalar Pillow. Verifique sua conexao com a internet.
        pause
        exit /b 1
    )
    
    echo  [OK] Pillow instalado com sucesso.
    echo  Instalando demais dependencias...
    
    :: Instala o resto das dependências
    pip install -r requirements.txt --quiet
    if %errorlevel% neq 0 (
        echo.
        echo  [ERRO] Falha ao instalar algumas dependencias.
        echo  Verifique sua conexao com a internet e tente novamente.
        pause
        exit /b 1
    )
)

echo  [OK] Dependencias instaladas com sucesso.
echo.

:: ----------------------------------------------------------------------------
:: 5. Criar Script de Execução (executar.bat)
:: ----------------------------------------------------------------------------
echo [5/5] Criando script de execucao rapida (executar.bat)...

(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%%~dp0"
echo call venv\Scripts\activate.bat
echo echo.
echo echo  ================================================
echo echo   Iniciando DashID...
echo echo   Dashboard de Performance de Lojas - Cp Fani
echo echo  ================================================
echo echo.
echo echo  Abrindo o dashboard no navegador...
echo echo  Se nao abrir automaticamente, acesse: http://localhost:8501
echo echo.
echo streamlit run app.py --server.headless true
echo echo.
echo echo  Dashboard encerrado.
echo pause
) > executar.bat

echo  [OK] Arquivo 'executar.bat' criado.
echo.

:: ----------------------------------------------------------------------------
:: Finalização
:: ----------------------------------------------------------------------------
echo  ================================================
echo   INSTALACAO CONCLUIDA COM SUCESSO!
echo  ================================================
echo.
echo  Para iniciar o dashboard, basta executar:
echo.
echo     executar.bat
echo.
echo  Ou abra o terminal na pasta do projeto e digite:
echo     streamlit run app.py
echo.
echo  O dashboard sera aberto automaticamente no seu navegador.
echo.
echo  ================================================
echo.

pause
endlocal
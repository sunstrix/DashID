"""
DashID - Conector Opcional para Microsoft SharePoint (Graph API)
=================================================================

Módulo desacoplado que permite leitura direta da planilha de projeção
armazenada no SharePoint corporativo (Microsoft 365), usando Microsoft Graph API.

IMPORTANTE: Este módulo é OPCIONAL. O dashboard funciona perfeitamente
sem ele, usando apenas o upload manual via Streamlit (data_loader.py).

Para habilitar:
1. Crie um arquivo .env na raiz do projeto (veja .env.example)
2. Configure as credenciais do Azure AD (client_id, tenant_id, client_secret)
3. Configure o site_id e drive_id do SharePoint
4. Configure o path do arquivo no drive

Se as credenciais não estiverem configuradas, as funções deste módulo
retornarão None ou False, permitindo que o fluxo principal continue
normalmente via upload manual.

Requisitos (quando habilitado):
- requests
- python-dotenv
- msal (Microsoft Authentication Library)

Autor: Alex Paulo
Versão: 0.2.0
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import requests

from config import LOG_CONFIG, META_ID

# Configuração de logging
logging.basicConfig(
    level=LOG_CONFIG["LEVEL"],
    format=LOG_CONFIG["FORMAT"],
    datefmt=LOG_CONFIG["DATE_FORMAT"],
)
logger = logging.getLogger(__name__)

# Tenta carregar variáveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
    logger.info("python-dotenv carregado com sucesso")
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv não instalado. Usando apenas variáveis de ambiente do sistema.")


# ============================================================================
# CONFIGURAÇÃO DO SHAREPOINT (via variáveis de ambiente)
# ============================================================================


class SharePointConfig:
    """Configurações do SharePoint carregadas de variáveis de ambiente."""

    # Azure AD / Microsoft Identity Platform
    TENANT_ID: Optional[str] = os.getenv("SHAREPOINT_TENANT_ID")
    CLIENT_ID: Optional[str] = os.getenv("SHAREPOINT_CLIENT_ID")
    CLIENT_SECRET: Optional[str] = os.getenv("SHAREPOINT_CLIENT_SECRET")

    # SharePoint / Graph API
    SITE_ID: Optional[str] = os.getenv("SHAREPOINT_SITE_ID")
    DRIVE_ID: Optional[str] = os.getenv("SHAREPOINT_DRIVE_ID")
    FILE_PATH: Optional[str] = os.getenv("SHAREPOINT_FILE_PATH", "Relatorio_de_projecao.xlsx")

    # Escopos necessários para Graph API
    SCOPES = ["https://graph.microsoft.com/.default"]

    # Endpoints
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    LOGIN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token" if TENANT_ID else None

    @classmethod
    def is_configured(cls) -> bool:
        """Verifica se todas as credenciais necessárias estão configuradas.

        Returns:
            True se todas as credenciais estão presentes, False caso contrário.
        """
        required_vars = [
            cls.TENANT_ID,
            cls.CLIENT_ID,
            cls.CLIENT_SECRET,
            cls.SITE_ID,
            cls.DRIVE_ID,
        ]

        is_configured = all(var is not None and var.strip() != "" for var in required_vars)

        if not is_configured:
            logger.info("Credenciais do SharePoint não configuradas. Usando upload manual.")

        return is_configured


# ============================================================================
# AUTENTICAÇÃO (Microsoft Authentication Library - MSAL)
# ============================================================================


def get_access_token() -> Optional[str]:
    """Obtém token de acesso para Microsoft Graph API usando Client Credentials.

    Usa o fluxo "Client Credentials" (aplicação daemon, sem interação do usuário).

    Returns:
        Token de acesso (string) ou None se falhar.
    """
    if not SharePointConfig.is_configured():
        logger.warning("SharePoint não configurado. Não é possível obter token.")
        return None

    try:
        # Tenta usar MSAL (recomendado)
        try:
            import msal

            app = msal.ConfidentialClientApplication(
                client_id=SharePointConfig.CLIENT_ID,
                client_credential=SharePointConfig.CLIENT_SECRET,
                authority=f"https://login.microsoftonline.com/{SharePointConfig.TENANT_ID}",
            )

            result = app.acquire_token_for_client(scopes=SharePointConfig.SCOPES)

            if "access_token" in result:
                logger.info("Token de acesso obtido com sucesso via MSAL")
                return result["access_token"]
            else:
                error_msg = result.get("error_description", result.get("error", "Erro desconhecido"))
                logger.error(f"Erro ao obter token via MSAL: {error_msg}")
                return None

        except ImportError:
            logger.warning("MSAL não instalado. Tentando autenticação via requests direto.")

            # Fallback: requisição direta ao endpoint de token
            token_data = {
                "grant_type": "client_credentials",
                "client_id": SharePointConfig.CLIENT_ID,
                "client_secret": SharePointConfig.CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            }

            response = requests.post(SharePointConfig.LOGIN_URL, data=token_data, timeout=30)

            if response.status_code == 200:
                token_json = response.json()
                logger.info("Token de acesso obtido com sucesso via requests")
                return token_json.get("access_token")
            else:
                logger.error(f"Erro ao obter token via requests: {response.status_code} - {response.text}")
                return None

    except Exception as e:
        logger.error(f"Exceção ao obter token de acesso: {e}")
        return None


# ============================================================================
# DOWNLOAD DO ARQUIVO DO SHAREPOINT
# ============================================================================


def download_file_from_sharepoint() -> Tuple[Optional[bytes], Optional[str]]:
    """Baixa o arquivo de projeção do SharePoint via Microsoft Graph API.

    Endpoint usado:
        GET /drives/{drive-id}/root:/{item-path}:/content

    Returns:
        Tupla (file_content, error_message):
            - file_content: Conteúdo binário do arquivo (bytes) ou None
            - error_message: Mensagem de erro (string) ou None se sucesso
    """
    if not SharePointConfig.is_configured():
        return None, "SharePoint não configurado. Configure as variáveis de ambiente."

    # Obtém token de acesso
    access_token = get_access_token()
    if not access_token:
        return None, "Não foi possível obter token de acesso para o SharePoint."

    # Monta a URL do endpoint
    drive_id = SharePointConfig.DRIVE_ID
    file_path = SharePointConfig.FILE_PATH
    url = f"{SharePointConfig.GRAPH_API_BASE}/drives/{drive_id}/root:/{file_path}:/content"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    try:
        logger.info(f"Baixando arquivo do SharePoint: {file_path}")
        response = requests.get(url, headers=headers, timeout=60)

        if response.status_code == 200:
            file_content = response.content
            logger.info(f"Arquivo baixado com sucesso: {len(file_content)} bytes")
            return file_content, None
        else:
            error_msg = f"Erro ao baixar arquivo: HTTP {response.status_code} - {response.text}"
            logger.error(error_msg)
            return None, error_msg

    except requests.exceptions.Timeout:
        error_msg = "Timeout ao tentar baixar arquivo do SharePoint (60s)."
        logger.error(error_msg)
        return None, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f"Erro de conexão ao baixar arquivo: {e}"
        logger.error(error_msg)
        return None, error_msg

    except Exception as e:
        error_msg = f"Erro inesperado ao baixar arquivo: {e}"
        logger.error(error_msg)
        return None, error_msg


# ============================================================================
# FUNÇÃO PRINCIPAL (INTEGRAÇÃO COM DATA_LOADER)
# ============================================================================


def load_data_from_sharepoint() -> Tuple[Optional[bytes], Optional[dict]]:
    """Função principal para carregar dados diretamente do SharePoint.

    Esta função é chamada pelo app.py quando o usuário seleciona a opção
    de carregar dados do SharePoint (em vez de upload manual).

    Returns:
        Tupla (file_content, metadata):
            - file_content: Conteúdo binário do arquivo (bytes) ou None
            - metadata: Dicionário com metadados ou None
    """
    logger.info("Tentando carregar dados diretamente do SharePoint...")

    file_content, error_msg = download_file_from_sharepoint()

    if file_content is None:
        logger.error(f"Falha ao carregar do SharePoint: {error_msg}")
        return None, None

    # Metadados do arquivo baixado
    metadata = {
        "source": "sharepoint",
        "filename": SharePointConfig.FILE_PATH,
        "file_size_bytes": len(file_content),
        "file_size_mb": len(file_content) / (1024 * 1024),
        "site_id": SharePointConfig.SITE_ID,
        "drive_id": SharePointConfig.DRIVE_ID,
    }

    logger.info(f"Dados carregados do SharePoint com sucesso: {metadata}")
    return file_content, metadata


# ============================================================================
# VERIFICAÇÃO DE STATUS (para UI)
# ============================================================================


def check_sharepoint_status() -> dict:
    """Verifica o status de configuração do SharePoint.

    Útil para exibir no dashboard se o SharePoint está configurado ou não.

    Returns:
        Dicionário com:
            - "configured": bool (se está configurado)
            - "dotenv_available": bool (se python-dotenv está instalado)
            - "missing_vars": list (variáveis faltantes, se houver)
    """
    missing_vars = []

    if not SharePointConfig.TENANT_ID:
        missing_vars.append("SHAREPOINT_TENANT_ID")
    if not SharePointConfig.CLIENT_ID:
        missing_vars.append("SHAREPOINT_CLIENT_ID")
    if not SharePointConfig.CLIENT_SECRET:
        missing_vars.append("SHAREPOINT_CLIENT_SECRET")
    if not SharePointConfig.SITE_ID:
        missing_vars.append("SHAREPOINT_SITE_ID")
    if not SharePointConfig.DRIVE_ID:
        missing_vars.append("SHAREPOINT_DRIVE_ID")

    status = {
        "configured": len(missing_vars) == 0,
        "dotenv_available": DOTENV_AVAILABLE,
        "missing_vars": missing_vars,
    }

    if status["configured"]:
        logger.info("SharePoint está configurado e pronto para uso")
    else:
        logger.info(f"SharePoint não configurado. Variáveis faltantes: {missing_vars}")

    return status


# ============================================================================
# TESTES (opcional, para desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    # Teste básico (apenas para desenvolvimento)
    print("Módulo sharepoint_connector.py carregado com sucesso.")
    print(f"Meta do ID: {META_ID} ({META_ID*100:.0f}%)")
    print(f"SharePoint configurado: {SharePointConfig.is_configured()}")
    print(f"python-dotenv disponível: {DOTENV_AVAILABLE}")

    status = check_sharepoint_status()
    print(f"Status: {status}")

    if status["configured"]:
        print("\nTentando baixar arquivo do SharePoint...")
        file_content, metadata = load_data_from_sharepoint()
        if file_content:
            print(f"Arquivo baixado: {len(file_content)} bytes")
        else:
            print("Falha ao baixar arquivo")
    else:
        print("\nSharePoint não configurado. Use upload manual via Streamlit.")
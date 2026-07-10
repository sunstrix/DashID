"""
DashID - Conector SharePoint (FONTE PRINCIPAL + FALLBACK GRAPH API)
====================================================================

Este modulo implementa DOIS metodos de acesso ao SharePoint:

1. METODO PRINCIPAL (download_from_sharepoint_link):
   - Baixa diretamente do link de compartilhamento do SharePoint
   - Nao requer credenciais (autenticacao via cookies/sessao publica)
   - Segue redirects automaticamente para encontrar a URL de download real
   - Salva o arquivo localmente em cache (data/relatorio_sharepoint.xlsx)
   - Usado como fonte principal do dashboard

2. METODO FALLBACK (download_file_from_sharepoint via Graph API):
   - Usa Microsoft Graph API com Client Credentials
   - Requer credenciais configuradas no .env (TENANT_ID, CLIENT_ID, etc.)
   - Usado apenas se o metodo principal falhar e o usuario quiser
     habilitar autenticacao avancada

CORRECAO APLICADA (v0.2.5):
- Filtra GUIDs capturados por regex (causa do erro "No scheme supplied")
- Valida URL extraida antes de tentar download
- Adiciona fallback com ?download=1
- Rejeita strings que nao comecam com http:// ou https://

Autor: Alex Paulo
Versao: 0.2.5
"""

import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, parse_qs

import requests

from config import LOG_CONFIG, META_ID, SHAREPOINT_CONFIG

# Configuracao de logging
logging.basicConfig(
    level=LOG_CONFIG["LEVEL"],
    format=LOG_CONFIG["FORMAT"],
    datefmt=LOG_CONFIG["DATE_FORMAT"],
)
logger = logging.getLogger(__name__)

# Tenta carregar variaveis de ambiente do arquivo .env
try:
    from dotenv import load_dotenv
    load_dotenv()
    DOTENV_AVAILABLE = True
    logger.info("python-dotenv carregado com sucesso")
except ImportError:
    DOTENV_AVAILABLE = False
    logger.warning("python-dotenv nao instalado. Usando apenas variaveis de ambiente do sistema.")


# ============================================================================
# CONFIGURACOES DO SHAREPOINT
# ============================================================================


class SharePointConfig:
    """Configuracoes do SharePoint carregadas de variaveis de ambiente.

    Usadas APENAS para o fallback via Microsoft Graph API.
    O download direto do link de compartilhamento NAO usa estas credenciais.
    """

    # Azure AD / Microsoft Identity Platform
    TENANT_ID: Optional[str] = os.getenv("SHAREPOINT_TENANT_ID")
    CLIENT_ID: Optional[str] = os.getenv("SHAREPOINT_CLIENT_ID")
    CLIENT_SECRET: Optional[str] = os.getenv("SHAREPOINT_CLIENT_SECRET")

    # SharePoint / Graph API
    SITE_ID: Optional[str] = os.getenv("SHAREPOINT_SITE_ID")
    DRIVE_ID: Optional[str] = os.getenv("SHAREPOINT_DRIVE_ID")
    FILE_PATH: Optional[str] = os.getenv(
        "SHAREPOINT_FILE_PATH",
        "Relatorio_de_projecao.xlsx"
    )

    # Escopos necessarios para Graph API
    SCOPES = ["https://graph.microsoft.com/.default"]

    # Endpoints
    GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
    LOGIN_URL = (
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
        if TENANT_ID else None
    )

    @classmethod
    def is_configured(cls) -> bool:
        """Verifica se todas as credenciais necessarias estao configuradas."""
        required_vars = [
            cls.TENANT_ID,
            cls.CLIENT_ID,
            cls.CLIENT_SECRET,
            cls.SITE_ID,
            cls.DRIVE_ID,
        ]
        is_configured = all(
            var is not None and var.strip() != "" for var in required_vars
        )
        if not is_configured:
            logger.info(
                "Credenciais do Graph API nao configuradas. "
                "Apenas download direto do link estara disponivel."
            )
        return is_configured


# ============================================================================
# FUNCOES AUXILIARES DE VALIDACAO DE URL
# ============================================================================


def _is_valid_url(url: str) -> bool:
    """Verifica se uma string e uma URL valida (com scheme http/https).

    Args:
        url: String a ser verificada.

    Returns:
        True se e uma URL valida, False caso contrario.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.strip()

    # Rejeita strings vazias ou muito curtas
    if len(url) < 10:
        return False

    # Rejeita GUIDs explicitamente (padrao {xxxxxxxx-xxxx-...})
    if url.startswith("{") and url.endswith("}"):
        logger.warning(f"String rejeitada (GUID detectado): {url}")
        return False

    # Rejeita strings que comecam com { mas nao terminam com }
    # (GUIDs parciais capturados por regex)
    if url.startswith("{"):
        logger.warning(f"String rejeitada (inicia com {{): {url}")
        return False

    # Deve ter scheme http:// ou https://
    if not (url.startswith("http://") or url.startswith("https://")):
        logger.warning(f"String rejeitada (sem scheme http/https): {url[:80]}")
        return False

    # Tenta fazer parse da URL
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False


def _is_guid(string: str) -> bool:
    """Verifica se uma string e um GUID do SharePoint.

    Args:
        string: String a ser verificada.

    Returns:
        True se parece ser um GUID, False caso contrario.
    """
    if not string or not isinstance(string, str):
        return False

    string = string.strip()

    # Padrao classico de GUID: {xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx}
    guid_pattern = r'^\{?[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\}?$'
    if re.match(guid_pattern, string):
        return True

    # GUID sem hifens
    guid_no_dash = r'^\{?[0-9a-fA-F]{32}\}?$'
    if re.match(guid_no_dash, string):
        return True

    return False


# ============================================================================
# METODO PRINCIPAL: DOWNLOAD DIRETO DO LINK DE COMPARTILHAMENTO
# ============================================================================


def _ensure_cache_dir() -> Path:
    """Garante que o diretorio de cache existe.

    Returns:
        Path do diretorio de cache.
    """
    cache_dir = Path(SHAREPOINT_CONFIG["CACHE_DIR"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_cache_file_path() -> Path:
    """Retorna o caminho completo do arquivo em cache.

    Returns:
        Path do arquivo cacheado.
    """
    cache_dir = _ensure_cache_dir()
    return cache_dir / SHAREPOINT_CONFIG["CACHE_FILENAME"]


def _is_cache_valid() -> bool:
    """Verifica se o cache e valido (arquivo existe e esta dentro do TTL).

    Returns:
        True se o cache e valido, False caso contrario.
    """
    cache_file = _get_cache_file_path()

    if not cache_file.exists():
        logger.info("Arquivo de cache nao encontrado.")
        return False

    file_age = time.time() - cache_file.stat().st_mtime
    ttl = SHAREPOINT_CONFIG["CACHE_TTL"]

    if file_age > ttl:
        logger.info(
            f"Cache expirado. Idade: {file_age:.0f}s, TTL: {ttl}s."
        )
        return False

    logger.info(
        f"Cache valido. Idade: {file_age:.0f}s, TTL: {ttl}s."
    )
    return True


def _extract_download_url(share_url: str, timeout: int) -> Optional[str]:
    """Extrai a URL de download real a partir do link de compartilhamento.

    O SharePoint redireciona o link de compartilhamento para uma pagina
    que contem a URL de download real. Este metodo segue os redirects e
    tenta extrair essa URL, VALIDANDO que nao e um GUID.

    Args:
        share_url: Link de compartilhamento do SharePoint.
        timeout: Timeout em segundos.

    Returns:
        URL de download valida ou None se nao conseguir extrair.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/webp,*/*;q=0.8"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        # Faz GET seguindo redirects para encontrar a URL final
        logger.info(f"Acessando link de compartilhamento: {share_url[:80]}...")
        response = requests.get(
            share_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:
            logger.error(
                f"Erro ao acessar link: HTTP {response.status_code}"
            )
            return None

        final_url = response.url
        logger.info(f"URL final apos redirects: {final_url[:80]}...")

        # Lista de URLs candidatas a download (serao validadas)
        candidate_urls = []

        # Tenta extrair parametros da URL que contenham a URL de download
        parsed = urlparse(final_url)
        query_params = parse_qs(parsed.query)

        # Parametros comuns que contem URL de download
        for param in ["sourcedoc", "file", "download", "url", "fileUrl", "OriginalSource"]:
            if param in query_params:
                url_candidata = query_params[param][0]
                candidate_urls.append(("param_" + param, url_candidata))

        # Se a URL final ja for valida e terminar com .xlsx, pode ser o download direto
        if _is_valid_url(final_url) and ".xlsx" in final_url.lower():
            candidate_urls.append(("final_url_xlsx", final_url))

        # Extrai URLs do HTML usando regex
        html_content = response.text

        # Padroes de regex para encontrar URLs no HTML (usando raw strings para evitar warnings)
        patterns = [
            (r'downloadUrl"\s*:\s*"([^"]+)"', "downloadUrl_json"),
            (r'fileUrl"\s*:\s*"([^"]+)"', "fileUrl_json"),
            (r'"@content\.downloadUrl"\s*:\s*"([^"]+)"', "graph_download"),
            (r'href="([^"]*download=1[^"]*)"', "download_param"),
            (r'href="([^"]*download\.aspx[^"]*)"', "download_aspx"),
            (r'href="(https?://[^"]*\.xlsx[^"]*)"', "xlsx_url"),
            (r'"(https?://[^"]*sharepoint\.com[^"]*\.xlsx[^"]*)"', "sharepoint_xlsx"),
            (r'"(https?://[^"]*/_layouts/15/download\.aspx[^"]*)"', "layouts_download"),
        ]

        for pattern, pattern_name in patterns:
            try:
                matches = re.findall(pattern, html_content)
                for match in matches:
                    # Decodifica URL se necessario
                    url_decoded = match.replace("\\u0026", "&").replace("\\/", "/")
                    candidate_urls.append((pattern_name, url_decoded))
            except re.error as e:
                logger.warning(f"Erro no regex '{pattern_name}': {e}")

        # Valida todas as URLs candidatas e retorna a primeira valida
        logger.info(f"Encontradas {len(candidate_urls)} URLs candidatas")

        for source, url in candidate_urls:
            logger.debug(f"Validando URL de fonte '{source}': {url[:80]}...")

            # Rejeita GUIDs
            if _is_guid(url):
                logger.warning(f"URL rejeitada (GUID): {url}")
                continue

            # Valida como URL
            if _is_valid_url(url):
                logger.info(f"URL valida encontrada (fonte: {source}): {url[:80]}...")
                return url
            else:
                logger.debug(f"URL invalida rejeitada: {url[:50]}...")

        # FALLBACK 1: Tenta adicionar ?download=1 na URL final
        logger.info("Nenhuma URL valida encontrada no HTML. Tentando fallback com ?download=1")
        download_url = final_url
        if "?" in download_url:
            download_url = download_url + "&download=1"
        else:
            download_url = download_url + "?download=1"

        if _is_valid_url(download_url):
            logger.info(f"Usando URL com ?download=1: {download_url[:80]}...")
            return download_url

        # FALLBACK 2: Tenta a URL original de compartilhamento com ?download=1
        logger.info("Tentando URL original com ?download=1")
        original_with_download = share_url
        if "?" in original_with_download:
            original_with_download = original_with_download + "&download=1"
        else:
            original_with_download = original_with_download + "?download=1"

        if _is_valid_url(original_with_download):
            logger.info(f"Usando URL original com ?download=1: {original_with_download[:80]}...")
            return original_with_download

        logger.error("Nao foi possivel extrair nenhuma URL valida de download")
        return None

    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao acessar link de compartilhamento ({timeout}s)")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de conexao ao acessar link: {e}")
        return None
    except Exception as e:
        logger.error(f"Erro inesperado ao extrair URL de download: {e}")
        return None


def download_from_sharepoint_link(share_url: str) -> Tuple[Optional[bytes], Optional[str]]:
    """Baixa o arquivo diretamente do link de compartilhamento do SharePoint.

    Este e o METODO PRINCIPAL de obtencao de dados. Nao requer credenciais.

    Fluxo:
    1. Verifica se existe cache valido (TTL de 1 hora)
    2. Se cache valido, retorna o conteudo do cache
    3. Se cache invalido, baixa do SharePoint
    4. Salva em cache local
    5. Retorna o conteudo

    Args:
        share_url: Link de compartilhamento do SharePoint.

    Returns:
        Tupla (file_content, error_message):
            - file_content: Conteudo binario do arquivo (bytes) ou None
            - error_message: Mensagem de erro (string) ou None se sucesso
    """
    # Valida a URL de entrada primeiro
    if not _is_valid_url(share_url):
        error_msg = (
            f"URL de compartilhamento invalida: {share_url[:50]}... "
            "Verifique o campo SHARE_URL em config.py. "
            "A URL deve comecar com 'https://' e nao pode ser um GUID."
        )
        logger.error(error_msg)
        return None, error_msg

    # Verifica cache primeiro
    if _is_cache_valid():
        try:
            cache_file = _get_cache_file_path()
            with open(cache_file, "rb") as f:
                file_content = f.read()
            logger.info(
                f"Arquivo carregado do cache: {len(file_content)} bytes"
            )
            return file_content, None
        except Exception as e:
            logger.warning(f"Erro ao ler cache: {e}. Tentando download.")

    # Extrai URL de download real
    timeout = SHAREPOINT_CONFIG["TIMEOUT"]
    download_url = _extract_download_url(share_url, timeout)

    if not download_url:
        error_msg = (
            "Nao foi possivel extrair URL de download do link de compartilhamento. "
            "Verifique se o link e valido e se voce tem acesso ao arquivo."
        )
        return None, error_msg

    # VALIDACAO CRITICA: Rejeita GUIDs antes de tentar baixar
    if _is_guid(download_url) or not _is_valid_url(download_url):
        error_msg = (
            f"URL de download invalida extraida: {download_url[:50]}... "
            "O SharePoint pode estar exigindo autenticacao."
        )
        logger.error(error_msg)
        return None, error_msg

    # Baixa o arquivo
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    try:
        logger.info(f"Baixando arquivo de: {download_url[:80]}...")
        response = requests.get(
            download_url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code != 200:
            error_msg = (
                f"Erro ao baixar arquivo: HTTP {response.status_code}. "
                f"Resposta: {response.text[:200]}"
            )
            logger.error(error_msg)
            return None, error_msg

        file_content = response.content

        # Verifica se o conteudo parece ser um arquivo Excel valido
        if len(file_content) < 100:
            error_msg = (
                f"Arquivo baixado muito pequeno ({len(file_content)} bytes). "
                "Provavelmente o link retornou uma pagina HTML em vez do arquivo."
            )
            logger.error(error_msg)
            return None, error_msg

        # Verifica assinatura de arquivo ZIP (xlsx e um zip)
        if not file_content.startswith(b"PK"):
            # Pode ser que o SharePoint tenha retornado HTML
            if b"<html" in file_content.lower()[:1000]:
                error_msg = (
                    "O link retornou uma pagina HTML em vez do arquivo Excel. "
                    "Isso geralmente acontece quando o link requer autenticacao "
                    "ou esta expirado."
                )
                logger.error(error_msg)
                return None, error_msg

        # Salva em cache
        try:
            cache_file = _get_cache_file_path()
            with open(cache_file, "wb") as f:
                f.write(file_content)
            logger.info(
                f"Arquivo salvo em cache: {cache_file} "
                f"({len(file_content)} bytes)"
            )
        except Exception as e:
            logger.warning(f"Erro ao salvar cache: {e}")

        logger.info(f"Arquivo baixado com sucesso: {len(file_content)} bytes")
        return file_content, None

    except requests.exceptions.Timeout:
        error_msg = f"Timeout ao baixar arquivo ({timeout}s)."
        logger.error(error_msg)
        return None, error_msg
    except requests.exceptions.RequestException as e:
        error_msg = f"Erro de conexao ao baixar arquivo: {e}"
        logger.error(error_msg)
        return None, error_msg
    except Exception as e:
        error_msg = f"Erro inesperado ao baixar arquivo: {e}"
        logger.error(error_msg)
        return None, error_msg


def load_data_from_sharepoint_link(share_url: str) -> Tuple[Optional[bytes], dict]:
    """Funcao principal para carregar dados do link de compartilhamento.

    Chamada pelo app.py na inicializacao para baixar automaticamente
    a planilha do SharePoint.

    Args:
        share_url: Link de compartilhamento do SharePoint.

    Returns:
        Tupla (file_content, metadata):
            - file_content: Conteudo binario do arquivo (bytes) ou None
            - metadata: Dicionario com metadados (inclui 'error' se falhou)
    """
    from datetime import datetime

    logger.info("Iniciando download do SharePoint via link de compartilhamento...")
    logger.info(f"URL: {share_url[:80]}...")

    file_content, error_msg = download_from_sharepoint_link(share_url)

    cache_file = _get_cache_file_path()
    last_update = None
    if cache_file.exists():
        last_update = datetime.fromtimestamp(
            cache_file.stat().st_mtime
        ).strftime("%d/%m/%Y %H:%M:%S")

    if file_content is None:
        logger.error(f"Falha ao carregar do SharePoint: {error_msg}")
        metadata = {
            "source": "sharepoint",
            "success": False,
            "error": error_msg,
            "last_update": last_update,
        }
        return None, metadata

    metadata = {
        "source": "sharepoint",
        "success": True,
        "filename": SHAREPOINT_CONFIG["CACHE_FILENAME"],
        "file_size_bytes": len(file_content),
        "file_size_mb": len(file_content) / (1024 * 1024),
        "share_url": share_url,
        "cache_file": str(cache_file),
        "last_update": last_update,
    }

    logger.info(f"Dados carregados do SharePoint com sucesso: {metadata}")
    return file_content, metadata


def invalidate_cache() -> bool:
    """Invalida o cache removendo o arquivo local.

    Returns:
        True se o cache foi removido, False caso contrario.
    """
    cache_file = _get_cache_file_path()
    try:
        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"Cache invalidado: {cache_file}")
            return True
        logger.info("Nenhum cache para invalidar.")
        return True
    except Exception as e:
        logger.error(f"Erro ao invalidar cache: {e}")
        return False


# ============================================================================
# METODO FALLBACK: MICROSOFT GRAPH API (requer credenciais)
# ============================================================================


def get_access_token() -> Optional[str]:
    """Obtem token de acesso para Microsoft Graph API usando Client Credentials.

    Usa o fluxo "Client Credentials" (aplicacao daemon, sem interacao do usuario).
    Este metodo e usado APENAS como fallback avancado.

    Returns:
        Token de acesso (string) ou None se falhar.
    """
    if not SharePointConfig.is_configured():
        logger.warning(
            "Graph API nao configurado. Credenciais ausentes no .env."
        )
        return None

    try:
        # Tenta usar MSAL (recomendado)
        try:
            import msal

            app = msal.ConfidentialClientApplication(
                client_id=SharePointConfig.CLIENT_ID,
                client_credential=SharePointConfig.CLIENT_SECRET,
                authority=(
                    f"https://login.microsoftonline.com/"
                    f"{SharePointConfig.TENANT_ID}"
                ),
            )

            result = app.acquire_token_for_client(scopes=SharePointConfig.SCOPES)

            if "access_token" in result:
                logger.info("Token de acesso obtido com sucesso via MSAL")
                return result["access_token"]
            else:
                error_msg = result.get(
                    "error_description",
                    result.get("error", "Erro desconhecido")
                )
                logger.error(f"Erro ao obter token via MSAL: {error_msg}")
                return None

        except ImportError:
            logger.warning(
                "MSAL nao instalado. Tentando autenticacao via requests direto."
            )

            # Fallback: requisicao direta ao endpoint de token
            if not SharePointConfig.LOGIN_URL:
                logger.error("LOGIN_URL nao configurada (TENANT_ID ausente)")
                return None

            token_data = {
                "grant_type": "client_credentials",
                "client_id": SharePointConfig.CLIENT_ID,
                "client_secret": SharePointConfig.CLIENT_SECRET,
                "scope": "https://graph.microsoft.com/.default",
            }

            response = requests.post(
                SharePointConfig.LOGIN_URL,
                data=token_data,
                timeout=30,
            )

            if response.status_code == 200:
                token_json = response.json()
                logger.info("Token de acesso obtido com sucesso via requests")
                return token_json.get("access_token")
            else:
                logger.error(
                    f"Erro ao obter token via requests: "
                    f"{response.status_code} - {response.text}"
                )
                return None

    except Exception as e:
        logger.error(f"Excecao ao obter token de acesso: {e}")
        return None


def download_file_from_sharepoint() -> Tuple[Optional[bytes], Optional[str]]:
    """Baixa o arquivo via Microsoft Graph API (METODO FALLBACK).

    Endpoint usado:
        GET /drives/{drive-id}/root:/{item-path}:/content

    Returns:
        Tupla (file_content, error_message):
            - file_content: Conteudo binario do arquivo (bytes) ou None
            - error_message: Mensagem de erro (string) ou None se sucesso
    """
    if not SharePointConfig.is_configured():
        return (
            None,
            "Graph API nao configurado. Configure as variaveis de ambiente "
            "no .env para usar este metodo."
        )

    # Obtem token de acesso
    access_token = get_access_token()
    if not access_token:
        return None, "Nao foi possivel obter token de acesso para o Graph API."

    # Monta a URL do endpoint
    drive_id = SharePointConfig.DRIVE_ID
    file_path = SharePointConfig.FILE_PATH
    url = (
        f"{SharePointConfig.GRAPH_API_BASE}/drives/"
        f"{drive_id}/root:/{file_path}:/content"
    )

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }

    try:
        logger.info(f"Baixando arquivo via Graph API: {file_path}")
        response = requests.get(url, headers=headers, timeout=60)

        if response.status_code == 200:
            file_content = response.content
            logger.info(f"Arquivo baixado com sucesso: {len(file_content)} bytes")
            return file_content, None
        else:
            error_msg = (
                f"Erro ao baixar arquivo: HTTP {response.status_code} - "
                f"{response.text[:200]}"
            )
            logger.error(error_msg)
            return None, error_msg

    except requests.exceptions.Timeout:
        error_msg = "Timeout ao baixar arquivo do Graph API (60s)."
        logger.error(error_msg)
        return None, error_msg

    except requests.exceptions.RequestException as e:
        error_msg = f"Erro de conexao ao baixar arquivo: {e}"
        logger.error(error_msg)
        return None, error_msg

    except Exception as e:
        error_msg = f"Erro inesperado ao baixar arquivo: {e}"
        logger.error(error_msg)
        return None, error_msg


def load_data_from_sharepoint() -> Tuple[Optional[bytes], Optional[dict]]:
    """Funcao de fallback para carregar dados via Microsoft Graph API.

    Retorna:
        Tupla (file_content, metadata):
            - file_content: Conteudo binario do arquivo (bytes) ou None
            - metadata: Dicionario com metadados ou None
    """
    logger.info("Tentando carregar dados via Microsoft Graph API (fallback)...")

    file_content, error_msg = download_file_from_sharepoint()

    if file_content is None:
        logger.error(f"Falha ao carregar via Graph API: {error_msg}")
        return None, None

    metadata = {
        "source": "sharepoint_graph_api",
        "filename": SharePointConfig.FILE_PATH,
        "file_size_bytes": len(file_content),
        "file_size_mb": len(file_content) / (1024 * 1024),
        "site_id": SharePointConfig.SITE_ID,
        "drive_id": SharePointConfig.DRIVE_ID,
    }

    logger.info(f"Dados carregados via Graph API com sucesso: {metadata}")
    return file_content, metadata


# ============================================================================
# VERIFICACAO DE STATUS (para UI)
# ============================================================================


def check_sharepoint_status() -> dict:
    """Verifica o status de configuracao do SharePoint.

    Util para exibir no dashboard se os metodos de acesso estao disponiveis.

    Returns:
        Dicionario com:
            - "direct_link_configured": bool (link de compartilhamento)
            - "graph_api_configured": bool (credenciais do Graph API)
            - "cache_exists": bool (arquivo em cache local)
            - "cache_valid": bool (cache dentro do TTL)
            - "dotenv_available": bool
            - "missing_vars": list (variaveis faltantes do Graph API)
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

    cache_file = _get_cache_file_path()

    status = {
        "configured": len(missing_vars) == 0,  # Mantido para compatibilidade
        "direct_link_configured": bool(SHAREPOINT_CONFIG.get("SHARE_URL")),
        "graph_api_configured": len(missing_vars) == 0,
        "cache_exists": cache_file.exists(),
        "cache_valid": _is_cache_valid(),
        "dotenv_available": DOTENV_AVAILABLE,
        "missing_vars": missing_vars,
        "share_url": SHAREPOINT_CONFIG.get("SHARE_URL"),
    }

    logger.info(
        f"Status SharePoint: link={status['direct_link_configured']}, "
        f"graph_api={status['graph_api_configured']}, "
        f"cache={status['cache_valid']}"
    )

    return status


# ============================================================================
# TESTES (opcional, para desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    print("Modulo sharepoint_connector.py carregado com sucesso.")
    print(f"Meta do ID: {META_ID} ({META_ID*100:.0f}%)")
    print(f"URL de compartilhamento: {SHAREPOINT_CONFIG.get('SHARE_URL')}")
    print(f"Graph API configurado: {SharePointConfig.is_configured()}")
    print(f"python-dotenv disponivel: {DOTENV_AVAILABLE}")

    status = check_sharepoint_status()
    print(f"\nStatus: {status}")

    print("\n" + "=" * 70)
    print("Testando download direto do link de compartilhamento...")
    print("=" * 70)

    share_url = SHAREPOINT_CONFIG.get("SHARE_URL")
    if share_url:
        file_content, metadata = load_data_from_sharepoint_link(share_url)
        if file_content:
            print(f"SUCESSO! Arquivo baixado: {len(file_content)} bytes")
            print(f"Metadata: {metadata}")
        else:
            print(f"FALHA: {metadata}")
    else:
        print("URL de compartilhamento nao configurada em config.py")
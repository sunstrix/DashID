"""
DashID - Modulo de Carregamento e Validacao de Dados
=====================================================

Responsavel por:
- Ler arquivo local sincronizado pelo OneDrive/SharePoint (FONTE PRINCIPAL)
- Receber upload da planilha Excel (.xlsx) via Streamlit (FALLBACK)
- Validar o arquivo (extensao, tamanho, estrutura)
- Fazer parsing da planilha bruta com estrutura real:
  * Coluna A: Codigo da Loja (float/int, NaN para totalizacoes)
  * Coluna B: Nome da Loja (str)
  * Coluna C: Cidade (str)
  * Colunas D+: Datas como datetime objects (dinamico)
  * Valores: strings com "%" (ex: "116.22%") -> converter para float (1.1622)
- Separar lojas individuais de linhas de totalizacao por canal
- Adaptar-se dinamicamente ao numero de colunas de datas

ESTRUTURA REAL DA PLANILHA (verificada):
- Linha 1 (cabecalho): Codigo da Loja | (vazio) | Cidade | datas...
- Linhas 2-10: Lojas SBC (9 lojas)
- Linha 11: SOMA LOJA SBC (totalizacao)
- Linhas 12-17: Lojas SP (6 lojas)
- Linha 18: Total LOJA SP (totalizacao)
- Linha 19: Linha em branco
- Linha 20: TOTAL CANAL LOJA CP FANI (totalizacao geral)

ESTRATEGIA DE LEITURA (v0.3.0):
1. Tentar ler arquivo local (caminho configurado em LOCAL_CONFIG)
2. Se falhar, tentar SharePoint via HTTP (fallback)
3. Se ambos falharem, permitir upload manual

Autor: Alex Paulo
Versao: 0.3.0
"""

import io
import logging
from typing import Optional, Tuple, List, Dict
from pathlib import Path

import pandas as pd
import numpy as np
import streamlit as st

from config import (
    BUSINESS_CONFIG,
    CHANNEL_PREFIXES,
    FILE_CONFIG,
    LOCAL_CONFIG,
    LOG_CONFIG,
    META_ID,
    validate_local_file,
)

# Configuracao de logging
logging.basicConfig(
    level=LOG_CONFIG["LEVEL"],
    format=LOG_CONFIG["FORMAT"],
    datefmt=LOG_CONFIG["DATE_FORMAT"],
)
logger = logging.getLogger(__name__)


# ============================================================================
# VALIDACAO DE ARQUIVO
# ============================================================================


def validate_file(uploaded_file) -> Tuple[bool, str]:
    """Valida o arquivo enviado pelo usuario.

    Args:
        uploaded_file: Arquivo enviado via st.file_uploader.

    Returns:
        Tupla (is_valid, error_message):
            - is_valid: True se o arquivo e valido, False caso contrario.
            - error_message: Mensagem de erro (vazia se valido).
    """
    if uploaded_file is None:
        return False, "Nenhum arquivo foi enviado."

    # Verifica extensao
    file_extension = "." + uploaded_file.name.split(".")[-1].lower()
    if file_extension not in FILE_CONFIG["ALLOWED_EXTENSIONS"]:
        return False, (
            f"Extensao de arquivo nao suportada: {file_extension}. "
            f"Use apenas: {', '.join(FILE_CONFIG['ALLOWED_EXTENSIONS'])}"
        )

    # Verifica tamanho
    file_size = uploaded_file.size
    if file_size > FILE_CONFIG["MAX_FILE_SIZE_BYTES"]:
        size_mb = file_size / (1024 * 1024)
        return False, (
            f"Arquivo muito grande: {size_mb:.2f} MB. "
            f"Tamanho maximo permitido: {FILE_CONFIG['MAX_FILE_SIZE_MB']} MB."
        )

    return True, ""


# ============================================================================
# CONVERSAO DE VALORES (STRING COM "%" -> FLOAT)
# ============================================================================


def convert_percentage_string(value) -> Optional[float]:
    """Converte string com "%" para float (indice).

    Exemplos:
        "116.22%" -> 1.1622
        "125%" -> 1.25
        "" ou NaN -> None

    Args:
        value: Valor a converter (string, float, ou NaN).

    Returns:
        Float representando o indice (ex: 1.1622) ou None se invalido.
    """
    if pd.isna(value):
        return None

    # Se ja e numerico (float/int), retorna como esta
    if isinstance(value, (int, float)):
        return float(value)

    # Se e string
    if isinstance(value, str):
        value = value.strip()
        if value == "" or value == "-":
            return None

        # Remove "%" e converte
        if "%" in value:
            value = value.replace("%", "").strip()

        try:
            # Converte para float e divide por 100
            return float(value) / 100.0
        except (ValueError, TypeError):
            return None

    return None


# ============================================================================
# DETECCAO DE COLUNAS DE DATA
# ============================================================================


def detect_date_columns(df: pd.DataFrame) -> List[pd.Timestamp]:
    """Detecta colunas que contem datas (datetime objects ou strings parseaveis).

    Args:
        df: DataFrame com cabecalho na linha 0.

    Returns:
        Lista de timestamps das colunas de data detectadas.
    """
    date_columns = []

    for col in df.columns:
        # Se ja e datetime
        if isinstance(col, pd.Timestamp):
            date_columns.append(col)
        elif isinstance(col, (pd.Timestamp, np.datetime64)):
            date_columns.append(pd.Timestamp(col))
        else:
            # Tenta converter para datetime
            try:
                parsed_date = pd.to_datetime(col, errors="coerce")
                if pd.notna(parsed_date):
                    date_columns.append(parsed_date)
            except:
                pass

    return date_columns


# ============================================================================
# PARSING DA PLANILHA
# ============================================================================


def parse_worksheet(file_content: bytes) -> pd.DataFrame:
    """Faz parsing da planilha Excel bruta.

    Le a planilha com header=0 (primeira linha e cabecalho).

    Args:
        file_content: Conteudo binario do arquivo Excel.

    Returns:
        DataFrame bruto com todos os dados da planilha.

    Raises:
        ValueError: Se a planilha nao puder ser lida ou estiver vazia.
    """
    try:
        # Le a planilha com header=0 (primeira linha e cabecalho)
        df_raw = pd.read_excel(
            io.BytesIO(file_content),
            sheet_name=FILE_CONFIG["SHEET_NAME"],
            header=0,
            engine="openpyxl",
        )

        if df_raw.empty:
            raise ValueError("A planilha esta vazia.")

        logger.info(f"Planilha lida com sucesso: {df_raw.shape[0]} linhas, {df_raw.shape[1]} colunas")
        return df_raw

    except Exception as e:
        logger.error(f"Erro ao ler a planilha: {e}")
        raise ValueError(f"Nao foi possivel ler a planilha: {e}")


def identify_stores_and_channels(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], List[str]]:
    """Identifica e separa lojas individuais de linhas de totalizacao.

    Analisa a coluna "Codigo da Loja" para identificar:
    - Lojas individuais: codigo != NaN
    - Linhas de totalizacao: codigo = NaN e nome contem "SOMA", "Total", "TOTAL"
    - Linhas em branco: todas as colunas principais sao NaN

    Args:
        df_raw: DataFrame bruto da planilha.

    Returns:
        Tupla (df_stores, df_channels, store_names, channel_names):
            - df_stores: DataFrame apenas com lojas individuais
            - df_channels: DataFrame com linhas de totalizacao por canal
            - store_names: Lista de nomes das lojas individuais
            - channel_names: Lista de nomes dos canais
    """
    # Renomeia colunas para facilitar o trabalho
    # Coluna B (indice 1) pode estar vazia no header, entao renomeamos
    col_names = df_raw.columns.tolist()
    if len(col_names) >= 2:
        # Renomeia coluna B para "Loja" se estiver vazia ou for "Unnamed: 1"
        if col_names[1] == "" or str(col_names[1]).startswith("Unnamed"):
            df_raw = df_raw.rename(columns={col_names[1]: "Loja"})

    # Identifica coluna de codigo da loja
    codigo_col = "Codigo da Loja" if "Codigo da Loja" in df_raw.columns else df_raw.columns[0]
    loja_col = "Loja" if "Loja" in df_raw.columns else df_raw.columns[1]
    cidade_col = "Cidade" if "Cidade" in df_raw.columns else df_raw.columns[2]

    # Identifica linhas de totalizacao por canal
    is_channel = pd.Series([False] * len(df_raw))
    channel_keywords = ["SOMA", "Total", "TOTAL"]

    for keyword in channel_keywords:
        mask = df_raw[loja_col].astype(str).str.contains(keyword, case=False, na=False)
        is_channel = is_channel | mask

    # Identifica linhas em branco (todas as colunas principais sao NaN)
    is_blank = (
        df_raw[codigo_col].isna() &
        df_raw[loja_col].isna() &
        df_raw[cidade_col].isna()
    )

    # Lojas individuais: nao e canal, nao e em branco, codigo != NaN
    is_store = ~is_channel & ~is_blank & df_raw[codigo_col].notna()

    # Extrai DataFrames
    df_stores = df_raw[is_store].copy()
    df_channels = df_raw[is_channel].copy()

    # Extrai nomes das lojas (remove espacos em branco)
    store_names = df_stores[loja_col].astype(str).str.strip().tolist()
    channel_names = df_channels[loja_col].astype(str).str.strip().tolist()

    logger.info(f"Identificadas {len(store_names)} lojas individuais e {len(channel_names)} canais")

    return df_stores, df_channels, store_names, channel_names


def clean_and_structure_data(
    df_stores: pd.DataFrame,
    df_channels: pd.DataFrame,
    store_names: List[str],
    channel_names: List[str]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Index]:
    """Limpa e estrutura os dados em formato analisavel.

    Transforma os DataFrames brutos em:
    - DataFrame com lojas (indice = nome da loja, colunas = datas)
    - DataFrame com canais (indice = nome do canal, colunas = datas)
    - Indice de datas (colunas)

    Args:
        df_stores: DataFrame com lojas individuais.
        df_channels: DataFrame com totalizacoes por canal.
        store_names: Lista de nomes das lojas.
        channel_names: Lista de nomes dos canais.

    Returns:
        Tupla (df_stores_structured, df_channels_structured, dates):
            - df_stores_structured: DataFrame estruturado das lojas
            - df_channels_structured: DataFrame estruturado dos canais
            - dates: Indice de datas (colunas)
    """
    # Identifica colunas de data
    codigo_col = "Codigo da Loja" if "Codigo da Loja" in df_stores.columns else df_stores.columns[0]
    loja_col = "Loja" if "Loja" in df_stores.columns else df_stores.columns[1]
    cidade_col = "Cidade" if "Cidade" in df_stores.columns else df_stores.columns[2]

    # Colunas de data sao todas exceto as 3 primeiras (codigo, loja, cidade)
    date_columns_raw = df_stores.columns[3:]

    # Converte colunas de data para Timestamp
    dates = []
    for col in date_columns_raw:
        try:
            if isinstance(col, pd.Timestamp):
                dates.append(col)
            else:
                parsed = pd.to_datetime(col, errors="coerce")
                if pd.notna(parsed):
                    dates.append(parsed)
                else:
                    dates.append(pd.NaT)
        except:
            dates.append(pd.NaT)

    # Cria indice de datas (remove NaT)
    dates_index = pd.Index([d for d in dates if pd.notna(d)])

    # Para df_stores: extrai valores e converte de string com "%" para float
    if len(df_stores) > 0:
        df_stores_values = df_stores.iloc[:, 3:].copy()

        # Aplica conversao de valores usando map() (Pandas 2.1+)
        df_stores_values = df_stores_values.map(convert_percentage_string)

        # Define indice como nomes das lojas
        df_stores_structured = df_stores_values.copy()
        df_stores_structured.index = store_names

        # Define colunas como datas
        if len(dates_index) == df_stores_values.shape[1]:
            df_stores_structured.columns = dates_index
    else:
        df_stores_structured = pd.DataFrame()

    # Para df_channels: mesma logica
    if len(df_channels) > 0:
        df_channels_values = df_channels.iloc[:, 3:].copy()
        df_channels_values = df_channels_values.map(convert_percentage_string)

        df_channels_structured = df_channels_values.copy()
        df_channels_structured.index = channel_names

        if len(dates_index) == df_channels_values.shape[1]:
            df_channels_structured.columns = dates_index
    else:
        df_channels_structured = pd.DataFrame()

    logger.info(f"Dados estruturados: {len(df_stores_structured)} lojas, {len(df_channels_structured)} canais, {len(dates_index)} datas")

    return df_stores_structured, df_channels_structured, dates_index


# ============================================================================
# FUNCAO PRINCIPAL DE CARREGAMENTO - UPLOAD MANUAL
# ============================================================================


@st.cache_data(ttl=0, show_spinner=False)
def load_data_from_upload(uploaded_file) -> dict:
    """Carrega e processa dados da planilha enviada pelo usuario.

    Funcao principal que orquestra todo o processo:
    1. Valida o arquivo
    2. Le a planilha bruta
    3. Identifica lojas e canais
    4. Estrutura os dados
    5. Retorna dicionario com DataFrames prontos para analise

    Args:
        uploaded_file: Arquivo enviado via st.file_uploader.

    Returns:
        Dicionario com:
            - "stores": DataFrame das lojas (indice = loja, colunas = datas)
            - "channels": DataFrame dos canais (indice = canal, colunas = datas)
            - "dates": Indice de datas
            - "store_names": Lista de nomes das lojas
            - "channel_names": Lista de nomes dos canais
            - "metadata": Dicionario com metadados do arquivo

    Raises:
        ValueError: Se o arquivo for invalido ou nao puder ser processado.
    """
    # Valida o arquivo
    is_valid, error_msg = validate_file(uploaded_file)
    if not is_valid:
        raise ValueError(error_msg)

    # Le o conteudo do arquivo
    file_content = uploaded_file.getvalue()

    # Faz parsing da planilha
    df_raw = parse_worksheet(file_content)

    # Identifica lojas e canais
    df_stores, df_channels, store_names, channel_names = identify_stores_and_channels(df_raw)

    # Estrutura os dados
    df_stores_structured, df_channels_structured, dates = clean_and_structure_data(
        df_stores, df_channels, store_names, channel_names
    )

    # Metadados do arquivo
    metadata = {
        "filename": uploaded_file.name,
        "file_size_bytes": uploaded_file.size,
        "file_size_mb": uploaded_file.size / (1024 * 1024),
        "num_stores": len(store_names),
        "num_channels": len(channel_names),
        "num_days": len(dates),
        "date_range": (dates.min(), dates.max()) if len(dates) > 0 else (None, None),
        "source": "upload",
    }

    logger.info(f"Dados carregados com sucesso: {metadata}")

    return {
        "stores": df_stores_structured,
        "channels": df_channels_structured,
        "dates": dates,
        "store_names": store_names,
        "channel_names": channel_names,
        "metadata": metadata,
    }


# ============================================================================
# NOVA FUNCAO: LEITURA DE ARQUIVO LOCAL (FONTE PRINCIPAL)
# ============================================================================


@st.cache_data(ttl=0, show_spinner=False)
def load_data_from_local() -> dict:
    """Carrega dados do arquivo local sincronizado pelo OneDrive/SharePoint.

    Esta e a FONTE PRINCIPAL de dados. Le diretamente do sistema de arquivos
    um arquivo que e mantido atualizado automaticamente pelo OneDrive.

    Returns:
        Dicionario com os dados estruturados (mesmo formato de load_data_from_upload)

    Raises:
        ValueError: Se o arquivo local nao existir ou nao puder ser lido.
    """
    # Valida se arquivo local existe
    is_valid, error_msg, file_path = validate_local_file()
    
    if not is_valid:
        raise ValueError(error_msg)

    logger.info(f"Lendo arquivo local: {file_path}")

    try:
        # Le o conteudo do arquivo
        with open(file_path, "rb") as f:
            file_content = f.read()

        file_size = len(file_content)
        logger.info(f"Arquivo local lido: {file_size} bytes")

        # Faz parsing da planilha
        df_raw = parse_worksheet(file_content)

        # Identifica lojas e canais
        df_stores, df_channels, store_names, channel_names = identify_stores_and_channels(df_raw)

        # Estrutura os dados
        df_stores_structured, df_channels_structured, dates = clean_and_structure_data(
            df_stores, df_channels, store_names, channel_names
        )

        # Metadados do arquivo
        metadata = {
            "filename": file_path.name,
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "file_size_mb": file_size / (1024 * 1024),
            "num_stores": len(store_names),
            "num_channels": len(channel_names),
            "num_days": len(dates),
            "date_range": (dates.min(), dates.max()) if len(dates) > 0 else (None, None),
            "source": "local",
            "last_modified": pd.Timestamp.fromtimestamp(file_path.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
        }

        logger.info(f"Dados locais carregados com sucesso: {metadata}")

        return {
            "stores": df_stores_structured,
            "channels": df_channels_structured,
            "dates": dates,
            "store_names": store_names,
            "channel_names": channel_names,
            "metadata": metadata,
        }

    except Exception as e:
        logger.error(f"Erro ao ler arquivo local: {e}")
        raise ValueError(f"Erro ao processar arquivo local: {e}")


# ============================================================================
# FUNCAO AUXILIAR: VERIFICA DISPONIBILIDADE DE FONTES
# ============================================================================


def check_data_sources() -> dict:
    """Verifica quais fontes de dados estao disponiveis.

    Returns:
        Dicionario com:
            - "local_available": bool
            - "local_path": str
            - "local_error": str or None
            - "recommended_source": str ("local", "sharepoint", ou "upload")
    """
    result = {
        "local_available": False,
        "local_path": str(LOCAL_CONFIG.get("FILE_PATH", "")),
        "local_error": None,
        "recommended_source": "upload",
    }

    # Verifica arquivo local
    if LOCAL_CONFIG.get("ENABLED", True):
        is_valid, error_msg, _ = validate_local_file()
        result["local_available"] = is_valid
        if not is_valid:
            result["local_error"] = error_msg
        else:
            result["recommended_source"] = "local"

    logger.info(f"Fontes de dados disponiveis: {result}")
    return result


# ============================================================================
# FUNCOES AUXILIARES
# ============================================================================


def get_last_available_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Retorna a ultima data com dados disponiveis (nao-NaN) no DataFrame.

    Args:
        df: DataFrame com datas nas colunas.

    Returns:
        Ultima data com pelo menos um valor nao-NaN, ou None se nao houver dados.
    """
    if df.empty or len(df.columns) == 0:
        return None

    # Para cada coluna (data), verifica se ha pelo menos um valor nao-NaN
    has_data = df.notna().any()
    dates_with_data = has_data[has_data].index

    if len(dates_with_data) == 0:
        return None

    return dates_with_data.max()


def get_store_data_for_date_range(
    df: pd.DataFrame,
    start_date: Optional[pd.Timestamp] = None,
    end_date: Optional[pd.Timestamp] = None
) -> pd.DataFrame:
    """Filtra o DataFrame para um intervalo de datas especifico.

    Args:
        df: DataFrame com datas nas colunas.
        start_date: Data inicial (inclusive). Se None, usa a primeira data.
        end_date: Data final (inclusive). Se None, usa a ultima data.

    Returns:
        DataFrame filtrado.
    """
    if df.empty or len(df.columns) == 0:
        return df

    if start_date is None:
        start_date = df.columns.min()
    if end_date is None:
        end_date = df.columns.max()

    # Filtra colunas (datas) no intervalo
    mask = (df.columns >= start_date) & (df.columns <= end_date)
    return df.loc[:, mask]


def calculate_daily_variation(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula a variacao percentual diaria entre um dia e o anterior.

    Para cada loja e cada data, calcula:
        variacao = (valor_dia_atual / valor_dia_anterior) - 1

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame com variacoes percentuais (mesmo formato do input).
    """
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    # Calcula variacao: (dia_atual / dia_anterior) - 1
    df_variation = df.pct_change(axis=1)

    # Primeira coluna nao tem dia anterior, entao sera NaN
    return df_variation


# ============================================================================
# TESTES (opcional, para desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    # Teste basico (apenas para desenvolvimento)
    print("Modulo data_loader.py carregado com sucesso.")
    print(f"Configuracoes de arquivo: {FILE_CONFIG}")
    print(f"Meta do ID: {META_ID}")
    
    # Testa verificacao de fontes
    sources = check_data_sources()
    print(f"\nFontes disponiveis: {sources}")
    
    if sources["local_available"]:
        print("\nTentando carregar arquivo local...")
        try:
            data = load_data_from_local()
            print(f"SUCESSO! {data['metadata']['num_stores']} lojas carregadas")
            print(f"Periodo: {data['metadata']['date_range']}")
        except Exception as e:
            print(f"ERRO: {e}")
    else:
        print(f"\nArquivo local nao disponivel: {sources['local_error']}")
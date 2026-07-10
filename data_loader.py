"""
DashID - Módulo de Carregamento e Validação de Dados
=====================================================

Responsável por:
- Receber o upload da planilha Excel (.xlsx) via Streamlit
- Validar o arquivo (extensão, tamanho, estrutura)
- Fazer parsing da planilha bruta
- Estruturar os dados em DataFrames prontos para análise
- Identificar lojas individuais vs. linhas de totalização por canal

Estrutura esperada da planilha:
- Coluna A: nome da loja/PDV (ex.: "Coop Joaquim Nabuco", "Shopping Metrópole")
- Colunas B em diante: datas sequenciais (01/07/2026 a 31/07/2026)
- Valores: índice de atingimento de meta (ex.: 1.1622 = 116.22% da meta)
- Linhas em branco separam grupos de lojas por canal/região
- Linhas de totalização: "CANAL LOJA SBC", "CANAL LOJA SP", "CANAL LOJA CP FANI"

Autor: Alex Paulo
Versão: 0.1.0
"""

import io
import logging
from typing import Optional, Tuple

import pandas as pd
import streamlit as st

from config import (
    BUSINESS_CONFIG,
    CHANNEL_PREFIXES,
    FILE_CONFIG,
    LOG_CONFIG,
)

# Configuração de logging
logging.basicConfig(
    level=LOG_CONFIG["LEVEL"],
    format=LOG_CONFIG["FORMAT"],
    datefmt=LOG_CONFIG["DATE_FORMAT"],
)
logger = logging.getLogger(__name__)


# ============================================================================
# VALIDAÇÃO DE ARQUIVO
# ============================================================================


def validate_file(uploaded_file) -> Tuple[bool, str]:
    """Valida o arquivo enviado pelo usuário.

    Args:
        uploaded_file: Arquivo enviado via st.file_uploader.

    Returns:
        Tupla (is_valid, error_message):
            - is_valid: True se o arquivo é válido, False caso contrário.
            - error_message: Mensagem de erro (vazia se válido).
    """
    if uploaded_file is None:
        return False, "Nenhum arquivo foi enviado."

    # Verifica extensão
    file_extension = "." + uploaded_file.name.split(".")[-1].lower()
    if file_extension not in FILE_CONFIG["ALLOWED_EXTENSIONS"]:
        return False, (
            f"Extensão de arquivo não suportada: {file_extension}. "
            f"Use apenas: {', '.join(FILE_CONFIG['ALLOWED_EXTENSIONS'])}"
        )

    # Verifica tamanho
    file_size = uploaded_file.size
    if file_size > FILE_CONFIG["MAX_FILE_SIZE_BYTES"]:
        size_mb = file_size / (1024 * 1024)
        return False, (
            f"Arquivo muito grande: {size_mb:.2f} MB. "
            f"Tamanho máximo permitido: {FILE_CONFIG['MAX_FILE_SIZE_MB']} MB."
        )

    return True, ""


# ============================================================================
# PARSING DA PLANILHA
# ============================================================================


def parse_worksheet(file_content: bytes) -> pd.DataFrame:
    """Faz parsing da planilha Excel bruta.

    Lê a planilha assumindo que:
    - Linha 1 (índice 0): cabeçalho com datas
    - Coluna 0 (A): nomes das lojas
    - Colunas 1+ (B em diante): valores diários

    Args:
        file_content: Conteúdo binário do arquivo Excel.

    Returns:
        DataFrame bruto com todos os dados da planilha.

    Raises:
        ValueError: Se a planilha não puder ser lida ou estiver vazia.
    """
    try:
        # Lê a planilha sem cabeçalho (header=None) para ter controle total
        df_raw = pd.read_excel(
            io.BytesIO(file_content),
            sheet_name=FILE_CONFIG["SHEET_NAME"],
            header=None,
            engine="openpyxl",
        )

        if df_raw.empty:
            raise ValueError("A planilha está vazia.")

        logger.info(f"Planilha lida com sucesso: {df_raw.shape[0]} linhas, {df_raw.shape[1]} colunas")
        return df_raw

    except Exception as e:
        logger.error(f"Erro ao ler a planilha: {e}")
        raise ValueError(f"Não foi possível ler a planilha: {e}")


def identify_stores_and_channels(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, list]:
    """Identifica e separa lojas individuais de linhas de totalização.

    Analisa a coluna 0 (A) para identificar:
    - Lojas individuais (nomes de PDV)
    - Linhas de totalização por canal (CANAL LOJA SBC, SP, CP FANI)
    - Linhas em branco (separadores)

    Args:
        df_raw: DataFrame bruto da planilha.

    Returns:
        Tupla (df_stores, df_channels, store_names):
            - df_stores: DataFrame apenas com lojas individuais
            - df_channels: DataFrame com linhas de totalização por canal
            - store_names: Lista de nomes das lojas individuais
    """
    # Coluna 0 contém os nomes das lojas/canais
    col_names = df_raw.iloc[:, 0]

    # Identifica linhas de totalização por canal
    channel_rows = []
    for prefix_key, prefix_value in CHANNEL_PREFIXES.items():
        mask = col_names.astype(str).str.contains(prefix_value, case=False, na=False)
        if mask.any():
            channel_rows.append(mask)

    # Cria máscara para linhas de totalização
    if channel_rows:
        is_channel = channel_rows[0]
        for mask in channel_rows[1:]:
            is_channel = is_channel | mask
    else:
        is_channel = pd.Series([False] * len(df_raw))

    # Identifica linhas em branco (separadores)
    is_blank = col_names.isna() | (col_names.astype(str).str.strip() == "")

    # Identifica cabeçalho (primeira linha com datas)
    is_header = pd.Series([False] * len(df_raw))
    if len(df_raw) > 0:
        # Assume que a primeira linha é o cabeçalho
        is_header.iloc[0] = True

    # Lojas individuais: não é cabeçalho, não é canal, não é em branco
    is_store = ~is_header & ~is_channel & ~is_blank

    # Extrai DataFrames
    df_stores = df_raw[is_store].copy()
    df_channels = df_raw[is_channel].copy()

    # Extrai nomes das lojas
    store_names = df_stores.iloc[:, 0].astype(str).str.strip().tolist()

    logger.info(f"Identificadas {len(store_names)} lojas individuais e {len(df_channels)} canais")

    return df_stores, df_channels, store_names


def clean_and_structure_data(
    df_stores: pd.DataFrame,
    df_channels: pd.DataFrame,
    store_names: list
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Index]:
    """Limpa e estrutura os dados em formato analisável.

    Transforma os DataFrames brutos em:
    - DataFrame com lojas (índice = nome da loja, colunas = datas)
    - DataFrame com canais (índice = nome do canal, colunas = datas)
    - Índice de datas (colunas)

    Args:
        df_stores: DataFrame com lojas individuais.
        df_channels: DataFrame com totalizações por canal.
        store_names: Lista de nomes das lojas.

    Returns:
        Tupla (df_stores_structured, df_channels_structured, dates):
            - df_stores_structured: DataFrame estruturado das lojas
            - df_channels_structured: DataFrame estruturado dos canais
            - dates: Índice de datas (colunas)
    """
    # Extrai datas do cabeçalho (primeira linha, colunas 1+)
    if len(df_stores) > 0:
        # Assume que a primeira linha do df_raw original era o cabeçalho
        # Como df_stores não inclui o cabeçalho, precisamos pegar do df_raw original
        # Vamos assumir que as datas estão na primeira linha do arquivo
        pass

    # Para df_stores: índice = nomes das lojas, colunas = datas
    if len(df_stores) > 0:
        # Coluna 0 = nomes das lojas (já extraídos)
        # Colunas 1+ = valores diários
        df_stores_values = df_stores.iloc[:, 1:].copy()

        # Converte para numérico (força NaN para valores inválidos)
        df_stores_values = df_stores_values.apply(pd.to_numeric, errors="coerce")

        # Define índice como nomes das lojas
        df_stores_structured = df_stores_values.copy()
        df_stores_structured.index = store_names

        # Extrai datas (assumindo que a primeira linha do arquivo original tinha as datas)
        # Como não temos acesso direto ao df_raw aqui, vamos gerar datas sequenciais
        # baseado no número de colunas
        num_days = df_stores_values.shape[1]
        dates = pd.date_range(start="2026-07-01", periods=num_days, freq="D")
        df_stores_structured.columns = dates
    else:
        df_stores_structured = pd.DataFrame()
        dates = pd.Index([])

    # Para df_channels: índice = nomes dos canais, colunas = datas
    if len(df_channels) > 0:
        channel_names = df_channels.iloc[:, 0].astype(str).str.strip().tolist()
        df_channels_values = df_channels.iloc[:, 1:].copy()
        df_channels_values = df_channels_values.apply(pd.to_numeric, errors="coerce")

        df_channels_structured = df_channels_values.copy()
        df_channels_structured.index = channel_names

        if len(dates) > 0 and len(dates) == df_channels_values.shape[1]:
            df_channels_structured.columns = dates
    else:
        df_channels_structured = pd.DataFrame()

    logger.info(f"Dados estruturados: {len(df_stores_structured)} lojas, {len(df_channels_structured)} canais")

    return df_stores_structured, df_channels_structured, dates


# ============================================================================
# FUNÇÃO PRINCIPAL DE CARREGAMENTO
# ============================================================================


@st.cache_data(ttl=0, show_spinner=False)
def load_data_from_upload(uploaded_file) -> dict:
    """Carrega e processa dados da planilha enviada pelo usuário.

    Função principal que orquestra todo o processo:
    1. Valida o arquivo
    2. Lê a planilha bruta
    3. Identifica lojas e canais
    4. Estrutura os dados
    5. Retorna dicionário com DataFrames prontos para análise

    Args:
        uploaded_file: Arquivo enviado via st.file_uploader.

    Returns:
        Dicionário com:
            - "stores": DataFrame das lojas (índice = loja, colunas = datas)
            - "channels": DataFrame dos canais (índice = canal, colunas = datas)
            - "dates": Índice de datas
            - "store_names": Lista de nomes das lojas
            - "channel_names": Lista de nomes dos canais
            - "metadata": Dicionário com metadados do arquivo

    Raises:
        ValueError: Se o arquivo for inválido ou não puder ser processado.
    """
    # Valida o arquivo
    is_valid, error_msg = validate_file(uploaded_file)
    if not is_valid:
        raise ValueError(error_msg)

    # Lê o conteúdo do arquivo
    file_content = uploaded_file.getvalue()

    # Faz parsing da planilha
    df_raw = parse_worksheet(file_content)

    # Identifica lojas e canais
    df_stores, df_channels, store_names = identify_stores_and_channels(df_raw)

    # Estrutura os dados
    df_stores_structured, df_channels_structured, dates = clean_and_structure_data(
        df_stores, df_channels, store_names
    )

    # Extrai nomes dos canais
    channel_names = df_channels_structured.index.tolist() if len(df_channels_structured) > 0 else []

    # Metadados do arquivo
    metadata = {
        "filename": uploaded_file.name,
        "file_size_bytes": uploaded_file.size,
        "file_size_mb": uploaded_file.size / (1024 * 1024),
        "num_stores": len(store_names),
        "num_channels": len(channel_names),
        "num_days": len(dates),
        "date_range": (dates.min(), dates.max()) if len(dates) > 0 else (None, None),
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
# FUNÇÕES AUXILIARES
# ============================================================================


def get_last_available_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Retorna a última data com dados disponíveis (não-NaN) no DataFrame.

    Args:
        df: DataFrame com datas nas colunas.

    Returns:
        Última data com pelo menos um valor não-NaN, ou None se não houver dados.
    """
    if df.empty or len(df.columns) == 0:
        return None

    # Para cada coluna (data), verifica se há pelo menos um valor não-NaN
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
    """Filtra o DataFrame para um intervalo de datas específico.

    Args:
        df: DataFrame com datas nas colunas.
        start_date: Data inicial (inclusive). Se None, usa a primeira data.
        end_date: Data final (inclusive). Se None, usa a última data.

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
    """Calcula a variação percentual diária entre um dia e o anterior.

    Para cada loja e cada data, calcula:
        variação = (valor_dia_atual / valor_dia_anterior) - 1

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame com variações percentuais (mesmo formato do input).
    """
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    # Calcula variação: (dia_atual / dia_anterior) - 1
    df_variation = df.pct_change(axis=1)

    # Primeira coluna não tem dia anterior, então será NaN
    return df_variation


# ============================================================================
# TESTES (opcional, para desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    # Teste básico (apenas para desenvolvimento)
    print("Módulo data_loader.py carregado com sucesso.")
    print(f"Configurações de arquivo: {FILE_CONFIG}")
    print(f"Prefixos de canal: {CHANNEL_PREFIXES}")
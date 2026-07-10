"""
DashID - Módulo de Carregamento e Validação de Dados
=====================================================

Responsável por:
- Receber o upload da planilha Excel (.xlsx) via Streamlit
- Validar o arquivo (extensão, tamanho, estrutura)
- Fazer parsing da planilha bruta com estrutura real:
  * Coluna A: Código da Loja (float/int, NaN para totalizações)
  * Coluna B: Nome da Loja (str)
  * Coluna C: Cidade (str)
  * Colunas D+: Datas como datetime objects (dinâmico)
  * Valores: strings com "%" (ex: "116.22%") -> converter para float (1.1622)
- Separar lojas individuais de linhas de totalização por canal
- Adaptar-se dinamicamente ao número de colunas de datas

Estrutura real da planilha (verificada):
- Linha 1 (cabeçalho): Código da Loja | (vazio) | Cidade | datas...
- Linhas 2-10: Lojas SBC (9 lojas)
- Linha 11: SOMA LOJA SBC (totalização)
- Linhas 12-17: Lojas SP (6 lojas)
- Linha 18: Total LOJA SP (totalização)
- Linha 19: Linha em branco
- Linha 20: TOTAL CANAL LOJA CP FANI (totalização geral)

Autor: Alex Paulo
Versão: 0.2.0
"""

import io
import logging
from typing import Optional, Tuple, List, Dict

import pandas as pd
import numpy as np
import streamlit as st

from config import (
    BUSINESS_CONFIG,
    CHANNEL_PREFIXES,
    FILE_CONFIG,
    LOG_CONFIG,
    META_ID,
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
# CONVERSÃO DE VALORES (STRING COM "%" -> FLOAT)
# ============================================================================


def convert_percentage_string(value) -> Optional[float]:
    """Converte string com "%" para float (índice).

    Exemplos:
        "116.22%" -> 1.1622
        "125%" -> 1.25
        "" ou NaN -> None

    Args:
        value: Valor a converter (string, float, ou NaN).

    Returns:
        Float representando o índice (ex: 1.1622) ou None se inválido.
    """
    if pd.isna(value):
        return None

    # Se já é numérico (float/int), retorna como está
    if isinstance(value, (int, float)):
        return float(value)

    # Se é string
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
# DETECÇÃO DE COLUNAS DE DATA
# ============================================================================


def detect_date_columns(df: pd.DataFrame) -> List[pd.Timestamp]:
    """Detecta colunas que contêm datas (datetime objects ou strings parseáveis).

    Args:
        df: DataFrame com cabeçalho na linha 0.

    Returns:
        Lista de timestamps das colunas de data detectadas.
    """
    date_columns = []

    for col in df.columns:
        # Se já é datetime
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

    Lê a planilha com header=0 (primeira linha é cabeçalho).

    Args:
        file_content: Conteúdo binário do arquivo Excel.

    Returns:
        DataFrame bruto com todos os dados da planilha.

    Raises:
        ValueError: Se a planilha não puder ser lida ou estiver vazia.
    """
    try:
        # Lê a planilha com header=0 (primeira linha é cabeçalho)
        df_raw = pd.read_excel(
            io.BytesIO(file_content),
            sheet_name=FILE_CONFIG["SHEET_NAME"],
            header=0,
            engine="openpyxl",
        )

        if df_raw.empty:
            raise ValueError("A planilha está vazia.")

        logger.info(f"Planilha lida com sucesso: {df_raw.shape[0]} linhas, {df_raw.shape[1]} colunas")
        return df_raw

    except Exception as e:
        logger.error(f"Erro ao ler a planilha: {e}")
        raise ValueError(f"Não foi possível ler a planilha: {e}")


def identify_stores_and_channels(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], List[str]]:
    """Identifica e separa lojas individuais de linhas de totalização.

    Analisa a coluna "Código da Loja" para identificar:
    - Lojas individuais: código != NaN
    - Linhas de totalização: código = NaN e nome contém "SOMA", "Total", "TOTAL"
    - Linhas em branco: todas as colunas principais são NaN

    Args:
        df_raw: DataFrame bruto da planilha.

    Returns:
        Tupla (df_stores, df_channels, store_names, channel_names):
            - df_stores: DataFrame apenas com lojas individuais
            - df_channels: DataFrame com linhas de totalização por canal
            - store_names: Lista de nomes das lojas individuais
            - channel_names: Lista de nomes dos canais
    """
    # Renomeia colunas para facilitar o trabalho
    # Coluna B (índice 1) pode estar vazia no header, então renomeamos
    col_names = df_raw.columns.tolist()
    if len(col_names) >= 2:
        # Renomeia coluna B para "Loja" se estiver vazia ou for "Unnamed: 1"
        if col_names[1] == "" or str(col_names[1]).startswith("Unnamed"):
            df_raw = df_raw.rename(columns={col_names[1]: "Loja"})

    # Identifica coluna de código da loja
    codigo_col = "Código da Loja" if "Código da Loja" in df_raw.columns else df_raw.columns[0]
    loja_col = "Loja" if "Loja" in df_raw.columns else df_raw.columns[1]
    cidade_col = "Cidade" if "Cidade" in df_raw.columns else df_raw.columns[2]

    # Identifica linhas de totalização por canal
    is_channel = pd.Series([False] * len(df_raw))
    channel_keywords = ["SOMA", "Total", "TOTAL"]

    for keyword in channel_keywords:
        mask = df_raw[loja_col].astype(str).str.contains(keyword, case=False, na=False)
        is_channel = is_channel | mask

    # Identifica linhas em branco (todas as colunas principais são NaN)
    is_blank = (
        df_raw[codigo_col].isna() &
        df_raw[loja_col].isna() &
        df_raw[cidade_col].isna()
    )

    # Lojas individuais: não é canal, não é em branco, código != NaN
    is_store = ~is_channel & ~is_blank & df_raw[codigo_col].notna()

    # Extrai DataFrames
    df_stores = df_raw[is_store].copy()
    df_channels = df_raw[is_channel].copy()

    # Extrai nomes das lojas (remove espaços em branco)
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
    """Limpa e estrutura os dados em formato analisável.

    Transforma os DataFrames brutos em:
    - DataFrame com lojas (índice = nome da loja, colunas = datas)
    - DataFrame com canais (índice = nome do canal, colunas = datas)
    - Índice de datas (colunas)

    Args:
        df_stores: DataFrame com lojas individuais.
        df_channels: DataFrame com totalizações por canal.
        store_names: Lista de nomes das lojas.
        channel_names: Lista de nomes dos canais.

    Returns:
        Tupla (df_stores_structured, df_channels_structured, dates):
            - df_stores_structured: DataFrame estruturado das lojas
            - df_channels_structured: DataFrame estruturado dos canais
            - dates: Índice de datas (colunas)
    """
    # Identifica colunas de data
    codigo_col = "Código da Loja" if "Código da Loja" in df_stores.columns else df_stores.columns[0]
    loja_col = "Loja" if "Loja" in df_stores.columns else df_stores.columns[1]
    cidade_col = "Cidade" if "Cidade" in df_stores.columns else df_stores.columns[2]

    # Colunas de data são todas exceto as 3 primeiras (código, loja, cidade)
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

    # Cria índice de datas (remove NaT)
    dates_index = pd.Index([d for d in dates if pd.notna(d)])

    # Para df_stores: extrai valores e converte de string com "%" para float
    if len(df_stores) > 0:
        df_stores_values = df_stores.iloc[:, 3:].copy()

        # Aplica conversão de valores
        df_stores_values = df_stores_values.applymap(convert_percentage_string)

        # Define índice como nomes das lojas
        df_stores_structured = df_stores_values.copy()
        df_stores_structured.index = store_names

        # Define colunas como datas
        if len(dates_index) == df_stores_values.shape[1]:
            df_stores_structured.columns = dates_index
    else:
        df_stores_structured = pd.DataFrame()

    # Para df_channels: mesma lógica
    if len(df_channels) > 0:
        df_channels_values = df_channels.iloc[:, 3:].copy()
        df_channels_values = df_channels_values.applymap(convert_percentage_string)

        df_channels_structured = df_channels_values.copy()
        df_channels_structured.index = channel_names

        if len(dates_index) == df_channels_values.shape[1]:
            df_channels_structured.columns = dates_index
    else:
        df_channels_structured = pd.DataFrame()

    logger.info(f"Dados estruturados: {len(df_stores_structured)} lojas, {len(df_channels_structured)} canais, {len(dates_index)} datas")

    return df_stores_structured, df_channels_structured, dates_index


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
    print(f"Meta do ID: {META_ID}")
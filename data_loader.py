"""
DashID - Modulo de Carregamento e Validacao de Dados
=====================================================

Responsavel por:
- Ler arquivo local sincronizado pelo OneDrive/SharePoint (FONTE PRINCIPAL)
- Receber upload da planilha Excel (.xlsx) via Streamlit (FALLBACK)
- Validar o arquivo (extensao, tamanho, estrutura)
- Fazer parsing da planilha bruta com estrutura real:
  * Coluna A: Codigo da Loja (float/int)
  * Coluna B: Nome da Loja (str)
  * Coluna C: Cidade (str) - USADO PARA AGRUPAMENTO POR CANAL
  * Colunas D+: Datas como datetime objects (dinamico)
  * Valores: strings com "%" (ex: "116.22%") -> converter para float (1.1622)
- Agrupar lojas por cidade (coluna C) para comparativo por canal
- Adaptar-se dinamicamente ao numero de colunas de datas

ESTRUTURA REAL DA PLANILHA (verificada):
- Linha 1 (cabecalho): Codigo da Loja | (vazio) | Cidade | datas...
- Linhas 2-10: Lojas SBC (9 lojas)
- Linhas 11-16: Lojas SP (6 lojas)
- SEM LINHAS DE TOTALIZACAO (removidas pelo usuario)
- Agrupamento por cidade feito automaticamente via coluna C

CORRECOES v0.4.4:
- parse_date_string() melhorada: tenta multiplos formatos de data
- Logging detalhado de cada coluna convertida/falhada
- Tratamento robusto de inconsistencias (filtra colunas invalidas)
- Garante que apenas colunas 100% validas sejam usadas

CORRECOES v0.4.3:
- Adicionada funcao parse_date_string() para converter "1-Jul" em Timestamp
- Conversao explicita de colunas de datas para Timestamp (evita str vs datetime)
- Conversao explicita para float64 (evita dtype object)

CORRECOES v0.4.2:
- Substituido applymap() por map() (compativel Pandas 2.1+)

CORRECOES v0.4.1:
- Converte valores para float ANTES de calcular media por cidade

CORRECOES v0.4.0:
- Removeu-se a busca por linhas de totalizacao (SOMA, Total, TOTAL)
- Agrupamento por cidade feito automaticamente via coluna C "Cidade"

Autor: Alex Paulo
Versao: 0.4.4
"""

import io
import logging
from typing import Optional, Tuple, List, Dict
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import streamlit as st

from config import (
    BUSINESS_CONFIG,
    FILE_CONFIG,
    LOG_CONFIG,
    META_ID,
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
# CONVERSAO DE DATAS (STRING "1-Jul" -> TIMESTAMP) - v0.4.4
# ============================================================================


def parse_date_string(date_str) -> Optional[pd.Timestamp]:
    """Converte string de data (ex: '1-Jul', '2-Jul') para Timestamp.
    
    CORRECAO v0.4.4: Tenta multiplos formatos para garantir conversao.
    
    Args:
        date_str: String de data (ex: "1-Jul", "2-Jul", "10-Jul")
    
    Returns:
        pd.Timestamp ou None se nao conseguir converter
    """
    if pd.isna(date_str):
        return None
    
    try:
        # Se ja e Timestamp, retorna como esta
        if isinstance(date_str, pd.Timestamp):
            return date_str
        
        # Se e datetime, converte para Timestamp
        if isinstance(date_str, datetime):
            return pd.Timestamp(date_str)
        
        # Converte string
        date_str = str(date_str).strip()
        if not date_str:
            return None
        
        # Lista de formatos para tentar (do mais especifico ao mais generico)
        formatos = [
            "%d-%b-%Y",  # "1-Jul-2026" (ingles)
            "%d/%b/%Y",  # "1/Jul/2026" (ingles)
            "%d-%b-%y",  # "1-Jul-26" (ano com 2 digitos)
            "%d/%b/%y",  # "1/Jul/26" (ano com 2 digitos)
        ]
        
        # Tenta cada formato com ano 2026
        for formato in formatos:
            try:
                # Adiciona ano se necessario
                if "%Y" in formato or "%y" in formato:
                    data_com_ano = date_str
                else:
                    data_com_ano = f"{date_str}-2026"
                
                parsed = pd.to_datetime(data_com_ano, format=formato, errors="coerce")
                
                if pd.notna(parsed):
                    logger.debug(f"Data '{date_str}' convertida com formato '{formato}': {parsed}")
                    return parsed
            except:
                continue
        
        # Se nenhum formato funcionou, tenta parser generico do pandas
        try:
            # Tenta parsear sem formato especifico (pandas tenta adivinhar)
            parsed = pd.to_datetime(date_str + "-2026", errors="coerce")
            if pd.notna(parsed):
                logger.debug(f"Data '{date_str}' convertida com parser generico: {parsed}")
                return parsed
        except:
            pass
        
        # Se nada funcionou, retorna None
        logger.warning(f"Nao foi possivel converter data: '{date_str}'")
        return None
        
    except Exception as e:
        logger.error(f"Erro inesperado ao converter data '{date_str}': {e}")
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


def identify_stores_and_channels(df_raw: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, List[str], Dict[str, List[str]]]:
    """Identifica lojas individuais e agrupa por cidade (coluna C).

    ATUALIZACAO v0.4.0:
    - Removeu-se a busca por linhas de totalizacao (SOMA, Total, TOTAL)
    - Agrupamento por cidade feito automaticamente via coluna C "Cidade"
    - Retorna dicionario de cidades -> lista de lojas

    CORRECAO v0.4.1:
    - Converte valores para float ANTES de calcular media por cidade
    - Evita erro "Cannot perform reduction 'mean' with string dtype"

    Args:
        df_raw: DataFrame bruto da planilha.

    Returns:
        Tupla (df_stores, df_channels, store_names, city_stores_dict):
            - df_stores: DataFrame apenas com lojas individuais
            - df_channels: DataFrame agrupado por cidade
            - store_names: Lista de nomes das lojas (formato "Codigo - Nome")
            - city_stores_dict: Dicionario {cidade: [lista de lojas]}
    """
    # Renomeia colunas para facilitar o trabalho
    # Coluna B (indice 1) pode estar vazia no header, entao renomeamos
    col_names = df_raw.columns.tolist()
    if len(col_names) >= 2:
        # Renomeia coluna B para "Loja" se estiver vazia ou for "Unnamed: 1"
        if col_names[1] == "" or str(col_names[1]).startswith("Unnamed"):
            df_raw = df_raw.rename(columns={col_names[1]: "Loja"})

    # Identifica colunas
    codigo_col = "Codigo da Loja" if "Codigo da Loja" in df_raw.columns else df_raw.columns[0]
    loja_col = "Loja" if "Loja" in df_raw.columns else df_raw.columns[1]
    cidade_col = "Cidade" if "Cidade" in df_raw.columns else df_raw.columns[2]

    # Filtra apenas linhas com codigo da loja (remove linhas vazias e de totalizacao)
    # v0.4.0: Considera apenas linhas onde Codigo da Loja nao e NaN
    is_store = df_raw[codigo_col].notna()
    df_stores = df_raw[is_store].copy()

    # Converte codigo para inteiro (remove .0)
    df_stores[codigo_col] = df_stores[codigo_col].astype(int)

    # Cria nome completo da loja: "Codigo - Nome"
    df_stores["Nome_Completo"] = df_stores.apply(
        lambda row: f"{int(row[codigo_col])} - {row[loja_col].strip()}" if pd.notna(row[loja_col]) else f"{int(row[codigo_col])}",
        axis=1
    )

    # Extrai nomes das lojas (formato "Codigo - Nome")
    store_names = df_stores["Nome_Completo"].tolist()

    # Agrupa por cidade (coluna C)
    city_stores_dict = {}
    if cidade_col in df_stores.columns:
        # Agrupa lojas por cidade
        for cidade in df_stores[cidade_col].unique():
            if pd.notna(cidade):
                lojas_da_cidade = df_stores[df_stores[cidade_col] == cidade]["Nome_Completo"].tolist()
                city_stores_dict[cidade] = lojas_da_cidade

    # Cria DataFrame de canais agrupado por cidade
    if not df_stores.empty and cidade_col in df_stores.columns:
        # Agrupa dados por cidade
        df_channels_list = []
        for cidade, lojas in city_stores_dict.items():
            # Filtra lojas desta cidade
            df_city = df_stores[df_stores["Nome_Completo"].isin(lojas)]
            
            # Calcula media por cidade para cada data
            city_data = {
                "canal": cidade,
                "num_lojas": len(lojas),
                "lojas": ", ".join(lojas),
            }
            
            # Colunas de data (todas exceto as 3 primeiras)
            date_cols = df_stores.columns[3:]
            for col in date_cols:
                if col in df_city.columns:
                    # CORRECAO v0.4.1: Converter para float ANTES de calcular media
                    valores_convertidos = df_city[col].apply(convert_percentage_string)
                    # Filtra valores None/NaN
                    valores_validos = valores_convertidos.dropna()
                    if len(valores_validos) > 0:
                        city_data[col] = valores_validos.mean()
                    else:
                        city_data[col] = np.nan
            
            df_channels_list.append(city_data)
        
        df_channels = pd.DataFrame(df_channels_list)
        df_channels = df_channels.set_index("canal")
    else:
        df_channels = pd.DataFrame()

    logger.info(f"Identificadas {len(store_names)} lojas individuais em {len(city_stores_dict)} cidades")
    logger.info(f"Cidades encontradas: {list(city_stores_dict.keys())}")

    return df_stores, df_channels, store_names, city_stores_dict


def clean_and_structure_data(
    df_stores: pd.DataFrame,
    df_channels: pd.DataFrame,
    store_names: List[str],
    city_stores_dict: Dict[str, List[str]]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.Index]:
    """Limpa e estrutura os dados em formato analisavel.

    Transforma os DataFrames brutos em:
    - DataFrame com lojas (indice = "Codigo - Nome", colunas = datas)
    - DataFrame com cidades (indice = cidade, colunas = datas)
    - Indice de datas (colunas)

    CORRECAO v0.4.4:
    - Logging detalhado de cada coluna (sucesso/falha)
    - Filtra APENAS colunas que foram convertidas com sucesso
    - Garante consistencia total entre colunas e valores
    - Log de todas as colunas processadas

    Args:
        df_stores: DataFrame com lojas individuais.
        df_channels: DataFrame com agrupamento por cidade.
        store_names: Lista de nomes das lojas (formato "Codigo - Nome").
        city_stores_dict: Dicionario {cidade: [lista de lojas]}.

    Returns:
        Tupla (df_stores_structured, df_channels_structured, dates):
            - df_stores_structured: DataFrame estruturado das lojas
            - df_channels_structured: DataFrame estruturado das cidades
            - dates: Indice de datas (colunas)
    """
    # Identifica colunas de data
    codigo_col = "Codigo da Loja" if "Codigo da Loja" in df_stores.columns else df_stores.columns[0]
    cidade_col = "Cidade" if "Cidade" in df_stores.columns else df_stores.columns[2]

    # Colunas de data sao todas exceto as 3 primeiras (codigo, loja, cidade)
    date_columns_raw = df_stores.columns[3:]
    
    logger.info(f"Colunas de data brutas encontradas: {len(date_columns_raw)}")
    logger.info(f"Nomes das colunas: {list(date_columns_raw)}")

    # CORRECAO v0.4.4: Converte colunas de data e identifica quais sao validas
    valid_date_columns = []  # Nomes originais das colunas validas
    valid_dates = []  # Timestamps convertidos
    
    for col in date_columns_raw:
        # Usa parse_date_string() para converter "1-Jul" em Timestamp
        parsed_date = parse_date_string(col)
        
        if parsed_date is not None:
            valid_date_columns.append(col)
            valid_dates.append(parsed_date)
            logger.info(f"✓ Coluna '{col}' convertida com sucesso para {parsed_date}")
        else:
            logger.error(f"✗ Coluna '{col}' FALHOU na conversao - sera ignorada")

    logger.info(f"Resultado da conversao: {len(valid_date_columns)} de {len(date_columns_raw)} colunas validas")
    
    if len(valid_date_columns) == 0:
        logger.error("NENHUMA coluna de data foi convertida! Verifique o formato das datas.")
        return pd.DataFrame(), pd.DataFrame(), pd.Index([])

    # Cria indice de datas (apenas datas validas)
    dates_index = pd.Index(valid_dates)
    
    logger.info(f"Periodo: {dates_index.min()} a {dates_index.max()}")

    # Para df_stores: extrai APENAS colunas validas e converte para float
    if len(df_stores) > 0 and len(valid_date_columns) > 0:
        # CORRECAO v0.4.4: Filtra APENAS colunas que foram convertidas com sucesso
        df_stores_values = df_stores[valid_date_columns].copy()
        
        logger.info(f"DataFrame de lojas antes da conversao: shape={df_stores_values.shape}, colunas={list(df_stores_values.columns)}")

        # CORRECAO v0.4.2: Usar map() em vez de applymap() (Pandas 2.1+)
        df_stores_values = df_stores_values.map(convert_percentage_string)

        # CORRECAO v0.4.3: Converter explicitamente para float64
        df_stores_values = df_stores_values.astype('float64')

        # Define indice como nomes completos das lojas ("Codigo - Nome")
        df_stores_structured = df_stores_values.copy()
        df_stores_structured.index = store_names

        # Define colunas como datas convertidas (garantido que tem o mesmo tamanho)
        df_stores_structured.columns = dates_index
        
        logger.info(f"DataFrame de lojas DEPOIS da conversao: shape={df_stores_structured.shape}, dtype={df_stores_structured.dtypes.iloc[0]}")
    else:
        df_stores_structured = pd.DataFrame()

    # Para df_channels (cidades): mesma logica
    if not df_channels.empty and len(valid_date_columns) > 0:
        # Filtra APENAS colunas validas
        df_channels_values = df_channels[valid_date_columns].copy()
        
        # CORRECAO v0.4.3: Converter explicitamente para float64
        df_channels_values = df_channels_values.astype('float64')
        
        df_channels_structured = df_channels_values.copy()
        df_channels_structured.columns = dates_index
        
        logger.info(f"DataFrame de cidades DEPOIS da conversao: shape={df_channels_structured.shape}")
    else:
        df_channels_structured = pd.DataFrame()

    logger.info(f"Dados estruturados: {len(df_stores_structured)} lojas, {len(df_channels_structured)} cidades, {len(dates_index)} datas")
    
    # Log do tipo das colunas para debug
    if not df_stores_structured.empty:
        logger.info(f"Tipo das colunas: {df_stores_structured.dtypes.iloc[0]}")

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
    3. Identifica lojas e agrupa por cidade (coluna C)
    4. Estrutura os dados
    5. Retorna dicionario com DataFrames prontos para analise

    Args:
        uploaded_file: Arquivo enviado via st.file_uploader.

    Returns:
        Dicionario com:
            - "stores": DataFrame das lojas (indice = "Codigo - Nome", colunas = datas)
            - "channels": DataFrame das cidades (indice = cidade, colunas = datas)
            - "dates": Indice de datas
            - "store_names": Lista de nomes das lojas (formato "Codigo - Nome")
            - "city_stores_dict": Dicionario {cidade: [lista de lojas]}
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

    # Identifica lojas e agrupa por cidade
    df_stores, df_channels, store_names, city_stores_dict = identify_stores_and_channels(df_raw)

    # Estrutura os dados
    df_stores_structured, df_channels_structured, dates = clean_and_structure_data(
        df_stores, df_channels, store_names, city_stores_dict
    )

    # Metadados do arquivo
    metadata = {
        "filename": uploaded_file.name,
        "file_size_bytes": uploaded_file.size,
        "file_size_mb": uploaded_file.size / (1024 * 1024),
        "num_stores": len(store_names),
        "num_channels": len(city_stores_dict),
        "num_days": len(dates),
        "date_range": (dates.min(), dates.max()) if len(dates) > 0 else (None, None),
        "source": "upload",
        "cities": list(city_stores_dict.keys()),
    }

    logger.info(f"Dados carregados com sucesso: {metadata}")

    return {
        "stores": df_stores_structured,
        "channels": df_channels_structured,
        "dates": dates,
        "store_names": store_names,
        "channel_names": list(city_stores_dict.keys()),
        "city_stores_dict": city_stores_dict,
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
    from config import LOCAL_CONFIG, validate_local_file

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

        # Identifica lojas e agrupa por cidade
        df_stores, df_channels, store_names, city_stores_dict = identify_stores_and_channels(df_raw)

        # Estrutura os dados
        df_stores_structured, df_channels_structured, dates = clean_and_structure_data(
            df_stores, df_channels, store_names, city_stores_dict
        )

        # Metadados do arquivo
        metadata = {
            "filename": file_path.name,
            "file_path": str(file_path),
            "file_size_bytes": file_size,
            "file_size_mb": file_size / (1024 * 1024),
            "num_stores": len(store_names),
            "num_channels": len(city_stores_dict),
            "num_days": len(dates),
            "date_range": (dates.min(), dates.max()) if len(dates) > 0 else (None, None),
            "source": "local",
            "last_modified": pd.Timestamp.fromtimestamp(file_path.stat().st_mtime).strftime("%d/%m/%Y %H:%M:%S"),
            "cities": list(city_stores_dict.keys()),
        }

        logger.info(f"Dados locais carregados com sucesso: {metadata}")

        return {
            "stores": df_stores_structured,
            "channels": df_channels_structured,
            "dates": dates,
            "store_names": store_names,
            "channel_names": list(city_stores_dict.keys()),
            "city_stores_dict": city_stores_dict,
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
    from config import LOCAL_CONFIG, validate_local_file

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
            print(f"Cidades: {data['metadata']['cities']}")
            print(f"Periodo: {data['metadata']['date_range']}")
        except Exception as e:
            print(f"ERRO: {e}")
    else:
        print(f"\nArquivo local nao disponivel: {sources['local_error']}")
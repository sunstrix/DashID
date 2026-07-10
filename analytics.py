"""
DashID - Modulo de Análise e Cálculo de Indicadores
====================================================

Responsável por todos os cálculos de negócio, indicadores e análises:
- KPIs de topo (cards): índice médio MTD, melhor/pior loja, acima/abaixo da meta (1.15)
- Análise horizontal: variação diária, tabela formatada, gráfico de linhas
- Análise por dia da semana: agrupamento, boxplot, heatmap, melhor/pior dia
- Ranking de lojas com variação semanal
- Médias móveis (3 e 7 dias)
- Volatilidade/consistência (desvio padrão)
- Tendência (regressão linear simples)
- Alertas de queda consecutiva
- Comparativo por canal/região
- Distribuição (histograma)
- Funções auxiliares para exportação

META DO ID: 115% (1.15) - Consulta de CPF do cliente no sistema.

CORRECOES APLICADAS (v0.3.3):
- calculate_kpi_cards(): Filtragem segura de NaN usando pd.notna()
- calculate_distribution(): Filtragem segura de valores nao numericos
- calculate_moving_averages(): Removido parametro axis (incompativel Pandas 2.1+)

Autor: Alex Paulo
Versao: 0.3.3
"""

import io
import logging
from typing import Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from config import (
    BUSINESS_CONFIG,
    CHANNEL_LABELS,
    CHANNEL_PREFIXES,
    Colors,
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
# KPIs DE TOPO (CARDS)
# ============================================================================


def calculate_kpi_cards(df_stores: pd.DataFrame) -> Dict:
    """Calcula os KPIs principais para exibição em cards no topo do dashboard.

    KPIs calculados:
    - Índice médio geral do mês (MTD - Month to Date)
    - Loja com melhor índice acumulado
    - Loja com pior índice acumulado
    - Número de lojas acima da meta (>= 1.15) no último dia disponível
    - Número de lojas abaixo da meta (< 1.15) no último dia disponível

    Args:
        df_stores: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        Dicionário com os KPIs calculados.
    """
    if df_stores.empty:
        return {
            "media_geral": 0.0,
            "melhor_loja": {"nome": "-", "valor": 0.0},
            "pior_loja": {"nome": "-", "valor": 0.0},
            "acima_meta": 0,
            "abaixo_meta": 0,
            "total_lojas": 0,
            "ultimo_dia": None,
        }

    # Última data com dados disponíveis
    last_date = get_last_available_date(df_stores)
    if last_date is None:
        return {
            "media_geral": 0.0,
            "melhor_loja": {"nome": "-", "valor": 0.0},
            "pior_loja": {"nome": "-", "valor": 0.0},
            "acima_meta": 0,
            "abaixo_meta": 0,
            "total_lojas": len(df_stores),
            "ultimo_dia": None,
        }

    # Índice médio geral do mês (MTD) - média de todos os valores não-NaN
    # CORREÇÃO: Usar pd.isna() em vez de np.isnan() para compatibilidade
    media_geral = df_stores.values.flatten()
    # Converter para float e filtrar NaN de forma segura
    media_geral_float = []
    for val in media_geral:
        try:
            if pd.notna(val):
                media_geral_float.append(float(val))
        except (ValueError, TypeError):
            pass
    
    media_geral = float(np.mean(media_geral_float)) if len(media_geral_float) > 0 else 0.0

    # Índice acumulado por loja (média do mês até a última data)
    df_until_last = df_stores.loc[:, df_stores.columns <= last_date]
    media_por_loja = df_until_last.mean(axis=1)

    # Melhor e pior loja
    melhor_loja_idx = media_por_loja.idxmax()
    pior_loja_idx = media_por_loja.idxmin()
    melhor_loja_valor = float(media_por_loja[melhor_loja_idx])
    pior_loja_valor = float(media_por_loja[pior_loja_idx])

    # Lojas acima/abaixo da meta no último dia disponível (META = 1.15)
    valores_ultimo_dia = df_stores[last_date].dropna()
    acima_meta = int((valores_ultimo_dia >= META_ID).sum())
    abaixo_meta = int((valores_ultimo_dia < META_ID).sum())

    return {
        "media_geral": media_geral,
        "melhor_loja": {"nome": str(melhor_loja_idx), "valor": melhor_loja_valor},
        "pior_loja": {"nome": str(pior_loja_idx), "valor": pior_loja_valor},
        "acima_meta": acima_meta,
        "abaixo_meta": abaixo_meta,
        "total_lojas": len(valores_ultimo_dia),
        "ultimo_dia": last_date,
    }


def get_last_available_date(df: pd.DataFrame) -> Optional[pd.Timestamp]:
    """Retorna a última data com pelo menos um valor não-NaN."""
    if df.empty or len(df.columns) == 0:
        return None

    has_data = df.notna().any()
    dates_with_data = has_data[has_data].index

    if len(dates_with_data) == 0:
        return None

    return dates_with_data.max()


# ============================================================================
# ANÁLISE HORIZONTAL (DIA A DIA)
# ============================================================================


def calculate_daily_variation(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula a variação percentual diária entre um dia e o anterior.

    Fórmula: variação = (valor_dia_atual / valor_dia_anterior) - 1

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame com variações percentuais (mesmo formato do input).
    """
    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    # pct_change(axis=1) calcula variação ao longo das colunas (datas)
    df_variation = df.pct_change(axis=1)
    return df_variation


def get_top_movers(df: pd.DataFrame, top_n: int = 5) -> Dict:
    """Identifica as maiores altas e maiores quedas no último dia disponível.

    Args:
        df: DataFrame com variações percentuais (output de calculate_daily_variation).
        top_n: Número de lojas a retornar em cada categoria.

    Returns:
        Dicionário com:
            - "maiores_altas": lista de tuplas (loja, variação)
            - "maiores_quedas": lista de tuplas (loja, variação)
            - "data": data de referência
    """
    if df.empty:
        return {"maiores_altas": [], "maiores_quedas": [], "data": None}

    last_date = get_last_available_date(df)
    if last_date is None:
        return {"maiores_altas": [], "maiores_quedas": [], "data": None}

    valores_ultimo_dia = df[last_date].dropna()

    # Maiores altas (top N maiores valores)
    maiores_altas = valores_ultimo_dia.nlargest(top_n)
    maiores_altas_list = [(str(loja), float(var)) for loja, var in maiores_altas.items()]

    # Maiores quedas (top N menores valores)
    maiores_quedas = valores_ultimo_dia.nsmallest(top_n)
    maiores_quedas_list = [(str(loja), float(var)) for loja, var in maiores_quedas.items()]

    return {
        "maiores_altas": maiores_altas_list,
        "maiores_quedas": maiores_quedas_list,
        "data": last_date,
    }


def prepare_variation_table(
    df_variation: pd.DataFrame,
    selected_stores: Optional[List[str]] = None
) -> pd.DataFrame:
    """Prepara a tabela de variação diária com formatação para exibição.

    Args:
        df_variation: DataFrame com variações percentuais.
        selected_stores: Lista de lojas a incluir (None = todas).

    Returns:
        DataFrame formatado para exibição (percentual com 2 casas decimais).
    """
    if df_variation.empty:
        return pd.DataFrame()

    df_filtered = df_variation.copy()
    if selected_stores:
        df_filtered = df_filtered.loc[df_filtered.index.isin(selected_stores)]

    # Formata como percentual
    df_formatted = df_filtered.copy()
    for col in df_formatted.columns:
        df_formatted[col] = df_formatted[col].apply(
            lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-"
        )

    return df_formatted


# ============================================================================
# ANÁLISE POR DIA DA SEMANA
# ============================================================================


def analyze_by_weekday(df: pd.DataFrame) -> pd.DataFrame:
    """Agrupar os valores por dia da semana (segunda a domingo).

    Calcula média, mediana e desvio padrão do índice por loja e consolidado.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame com:
            - Índice: dias da semana (0=segunda, 6=domingo)
            - Colunas: média, mediana, desvio padrão (consolidado)
            - E por loja (se aplicável)
    """
    if df.empty:
        return pd.DataFrame()

    # Mapeia cada data para o dia da semana (0=segunda, 6=domingo)
    weekdays = df.columns.dayofweek

    # Cria DataFrame com dia da semana como índice auxiliar
    df_with_weekday = df.T.copy()
    df_with_weekday["weekday"] = weekdays

    # Agrupa por dia da semana
    grouped = df_with_weekday.groupby("weekday")

    # Calcula estatísticas consolidadas
    stats = pd.DataFrame({
        "media": grouped.mean().mean(axis=1),
        "mediana": grouped.median().median(axis=1),
        "desvio_padrao": grouped.std().mean(axis=1),
    })

    # Mapeia nomes dos dias
    weekday_names = {
        0: "Segunda",
        1: "Terça",
        2: "Quarta",
        3: "Quinta",
        4: "Sexta",
        5: "Sábado",
        6: "Domingo",
    }
    stats.index = stats.index.map(weekday_names)

    return stats


def analyze_weekday_by_store(df: pd.DataFrame) -> pd.DataFrame:
    """Analisa o desempenho por dia da semana para cada loja individualmente.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame com:
            - Índice: nomes das lojas
            - Colunas: dias da semana (Segunda a Domingo) com valores médios
    """
    if df.empty:
        return pd.DataFrame()

    weekdays = df.columns.dayofweek
    df_with_weekday = df.T.copy()
    df_with_weekday["weekday"] = weekdays

    # Agrupa por dia da semana e calcula média para cada loja
    grouped = df_with_weekday.groupby("weekday").mean()

    # Transpõe para ter lojas nas linhas e dias nas colunas
    result = grouped.T

    # Mapeia nomes dos dias
    weekday_names = {
        0: "Segunda",
        1: "Terça",
        2: "Quarta",
        3: "Quinta",
        4: "Sexta",
        5: "Sábado",
        6: "Domingo",
    }
    result.columns = [weekday_names[i] for i in result.columns]

    return result


def get_best_worst_weekday(df_weekday_store: pd.DataFrame) -> pd.DataFrame:
    """Identifica o melhor e pior dia da semana para cada loja.

    Args:
        df_weekday_store: DataFrame da função analyze_weekday_by_store.

    Returns:
        DataFrame com colunas: loja, melhor_dia, pior_dia.
    """
    if df_weekday_store.empty:
        return pd.DataFrame()

    results = []
    for loja in df_weekday_store.index:
        valores = df_weekday_store.loc[loja].dropna()
        if len(valores) == 0:
            continue

        melhor_dia = valores.idxmax()
        pior_dia = valores.idxmin()

        results.append({
            "loja": loja,
            "melhor_dia": melhor_dia,
            "pior_dia": pior_dia,
            "melhor_valor": float(valores[melhor_dia]),
            "pior_valor": float(valores[pior_dia]),
        })

    return pd.DataFrame(results)


# ============================================================================
# RANKING DE LOJAS
# ============================================================================


def calculate_store_ranking(
    df_stores: pd.DataFrame,
    period: str = "month"
) -> pd.DataFrame:
    """Calcula o ranking de lojas pelo índice médio acumulado.

    Args:
        df_stores: DataFrame com lojas nas linhas e datas nas colunas.
        period: "month" (mês atual) ou "last_week" (últimos 7 dias).

    Returns:
        DataFrame ordenado com:
            - loja, indice_medio, variacao_semanal, posicao
    """
    if df_stores.empty:
        return pd.DataFrame()

    if period == "last_week":
        # Últimos 7 dias com dados
        last_date = get_last_available_date(df_stores)
        if last_date is None:
            return pd.DataFrame()
        start_date = last_date - pd.Timedelta(days=6)
        df_period = df_stores.loc[:, (df_stores.columns >= start_date) & (df_stores.columns <= last_date)]
    else:
        df_period = df_stores

    # Índice médio por loja
    media_por_loja = df_period.mean(axis=1)

    # Variação frente à semana anterior (se houver dados suficientes)
    variacao_semanal = pd.Series(np.nan, index=df_stores.index)
    if len(df_stores.columns) >= 14:
        last_date = get_last_available_date(df_stores)
        if last_date is not None:
            # Semana atual (últimos 7 dias)
            start_current = last_date - pd.Timedelta(days=6)
            df_current = df_stores.loc[:, (df_stores.columns >= start_current) & (df_stores.columns <= last_date)]
            media_current = df_current.mean(axis=1)

            # Semana anterior (7 dias antes disso)
            end_previous = start_current - pd.Timedelta(days=1)
            start_previous = end_previous - pd.Timedelta(days=6)
            df_previous = df_stores.loc[:, (df_stores.columns >= start_previous) & (df_stores.columns <= end_previous)]
            if not df_previous.empty:
                media_previous = df_previous.mean(axis=1)
                # Variação percentual
                variacao_semanal = ((media_current / media_previous) - 1) * 100

    # Monta DataFrame do ranking
    ranking = pd.DataFrame({
        "loja": media_por_loja.index,
        "indice_medio": media_por_loja.values,
        "variacao_semanal": variacao_semanal.values,
    })

    # Ordena por índice médio (decrescente)
    ranking = ranking.sort_values("indice_medio", ascending=False).reset_index(drop=True)
    ranking["posicao"] = ranking.index + 1

    return ranking


# ============================================================================
# MÉDIAS MÓVEIS
# ============================================================================


def calculate_moving_averages(
    df: pd.DataFrame,
    windows: List[int] = None
) -> Dict[int, pd.DataFrame]:
    """Calcula médias móveis para suavizar ruído diário.

    CORRECAO (v0.3.3): Pandas 2.1+ nao aceita axis como argumento nomeado.
    Usamos .T.rolling().T para aplicar rolling nas colunas.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.
        windows: Lista de tamanhos de janela (padrão: [3, 7]).

    Returns:
        Dicionário {window: DataFrame com médias móveis}.
    """
    if windows is None:
        windows = [
            BUSINESS_CONFIG["MOVING_AVERAGE_SHORT"],
            BUSINESS_CONFIG["MOVING_AVERAGE_LONG"],
        ]

    if df.empty:
        return {w: pd.DataFrame() for w in windows}

    result = {}
    for window in windows:
        # CORRECAO: Pandas 2.1+ - usar transposicao em vez de axis
        df_ma = df.T.rolling(window=window, min_periods=1).mean().T
        result[window] = df_ma

    return result


# ============================================================================
# VOLATILIDADE / CONSISTÊNCIA
# ============================================================================


def calculate_volatility(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula a volatilidade (desvio padrão) do índice por loja.

    Lojas com menor desvio padrão são mais consistentes.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame ordenado com:
            - loja, desvio_padrao, classificacao (consistente/moderado/instavel)
    """
    if df.empty:
        return pd.DataFrame()

    std_por_loja = df.std(axis=1)

    # Classificação baseada em limiares
    classificacao = pd.cut(
        std_por_loja,
        bins=[-np.inf, 0.05, 0.10, np.inf],
        labels=["Consistente", "Moderado", "Instável"]
    )

    result = pd.DataFrame({
        "loja": std_por_loja.index,
        "desvio_padrao": std_por_loja.values,
        "classificacao": classificacao.values,
    })

    # Ordena por desvio padrão (crescente = mais consistente primeiro)
    result = result.sort_values("desvio_padrao", ascending=True).reset_index(drop=True)

    return result


# ============================================================================
# TENDÊNCIA (REGRESSÃO LINEAR)
# ============================================================================


def calculate_trend(df: pd.DataFrame) -> pd.DataFrame:
    """Calcula a tendência de cada loja via regressão linear simples.

    Usa numpy.polyfit para ajustar uma reta aos dados diários.
    Classifica a tendência como: alta, estável ou queda.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.

    Returns:
        DataFrame com:
            - loja, inclinacao, classificacao_tendencia
    """
    if df.empty:
        return pd.DataFrame()

    min_points = BUSINESS_CONFIG["TREND_REGRESSION_MIN_POINTS"]
    results = []

    for loja in df.index:
        valores = df.loc[loja].dropna()
        if len(valores) < min_points:
            results.append({
                "loja": loja,
                "inclinacao": np.nan,
                "classificacao_tendencia": "Dados insuficientes",
            })
            continue

        # X = índices numéricos dos dias (0, 1, 2, ...)
        x = np.arange(len(valores))
        y = valores.values

        # Regressão linear (grau 1)
        try:
            slope, intercept = np.polyfit(x, y, 1)

            # Classificação baseada na inclinação
            if slope > 0.005:
                classificacao = "Alta"
            elif slope < -0.005:
                classificacao = "Queda"
            else:
                classificacao = "Estável"

            results.append({
                "loja": loja,
                "inclinacao": float(slope),
                "classificacao_tendencia": classificacao,
            })
        except Exception as e:
            logger.warning(f"Erro ao calcular tendência para {loja}: {e}")
            results.append({
                "loja": loja,
                "inclinacao": np.nan,
                "classificacao_tendencia": "Erro",
            })

    return pd.DataFrame(results)


def generate_sparkline_data(df: pd.DataFrame, loja: str) -> List[float]:
    """Gera dados para sparkline (mini-gráfico) de uma loja específica.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.
        loja: Nome da loja.

    Returns:
        Lista de valores normalizados (0 a 1) para o sparkline.
    """
    if loja not in df.index:
        return []

    valores = df.loc[loja].dropna()
    if len(valores) == 0:
        return []

    # Normaliza para 0-1
    min_val = valores.min()
    max_val = valores.max()

    if max_val == min_val:
        return [0.5] * len(valores)

    normalized = (valores - min_val) / (max_val - min_val)
    return normalized.tolist()


# ============================================================================
# ALERTAS DE QUEDA CONSECUTIVA
# ============================================================================


def detect_consecutive_drops(
    df_variation: pd.DataFrame,
    threshold: int = None
) -> pd.DataFrame:
    """Detecta lojas com quedas consecutivas no índice.

    Args:
        df_variation: DataFrame com variações percentuais.
        threshold: Número mínimo de quedas consecutivas para alertar (padrão: 3).

    Returns:
        DataFrame com:
            - loja, dias_consecutivos_queda, ultima_data
    """
    if threshold is None:
        threshold = BUSINESS_CONFIG["CONSECUTIVE_DROP_THRESHOLD"]

    if df_variation.empty:
        return pd.DataFrame()

    results = []

    for loja in df_variation.index:
        valores = df_variation.loc[loja].dropna()
        if len(valores) == 0:
            continue

        # Conta quedas consecutivas (valores negativos)
        consecutivas = 0
        max_consecutivas = 0

        for var in valores.values:
            if var < 0:
                consecutivas += 1
                max_consecutivas = max(max_consecutivas, consecutivas)
            else:
                consecutivas = 0

        if max_consecutivas >= threshold:
            results.append({
                "loja": loja,
                "dias_consecutivos_queda": max_consecutivas,
                "ultima_data": valores.index[-1],
            })

    result_df = pd.DataFrame(results)
    if not result_df.empty:
        result_df = result_df.sort_values("dias_consecutivos_queda", ascending=False)

    return result_df


# ============================================================================
# COMPARATIVO POR CANAL / REGIÃO
# ============================================================================


def aggregate_by_channel(
    df_channels: pd.DataFrame,
    df_stores: pd.DataFrame
) -> pd.DataFrame:
    """Agrega dados por canal/região.

    Usa as linhas de totalização já existentes na planilha (SOMA LOJA SBC, etc.)
    e também calcula agregações manuais se necessário.

    Args:
        df_channels: DataFrame com totalizações por canal (do data_loader).
        df_stores: DataFrame com lojas individuais.

    Returns:
        DataFrame com:
            - canal, indice_medio, num_lojas, variacao_ultimo_dia
    """
    if df_channels.empty and df_stores.empty:
        return pd.DataFrame()

    results = []

    # Usa df_channels se disponível (totalizações da planilha)
    if not df_channels.empty:
        for canal in df_channels.index:
            valores = df_channels.loc[canal].dropna()
            if len(valores) == 0:
                continue

            indice_medio = float(valores.mean())
            ultimo_valor = float(valores.iloc[-1]) if len(valores) > 0 else np.nan
            penultimo_valor = float(valores.iloc[-2]) if len(valores) > 1 else np.nan

            if pd.notna(ultimo_valor) and pd.notna(penultimo_valor) and penultimo_valor != 0:
                variacao = ((ultimo_valor / penultimo_valor) - 1) * 100
            else:
                variacao = np.nan

            # Mapeia nome amigável do canal
            canal_nome = canal
            for key, prefix in CHANNEL_PREFIXES.items():
                if prefix in canal:
                    canal_nome = CHANNEL_LABELS.get(key, canal)
                    break

            results.append({
                "canal": canal_nome,
                "indice_medio": indice_medio,
                "num_lojas": np.nan,  # Não temos essa info nas totalizações
                "variacao_ultimo_dia": variacao,
            })

    return pd.DataFrame(results)


# ============================================================================
# DISTRIBUIÇÃO (HISTOGRAMA)
# ============================================================================


def calculate_distribution(
    df: pd.DataFrame,
    bins: int = 20
) -> pd.DataFrame:
    """Calcula a distribuição dos índices diários para histograma.

    Args:
        df: DataFrame com lojas nas linhas e datas nas colunas.
        bins: Número de faixas do histograma.

    Returns:
        DataFrame com:
            - faixa, frequencia, frequencia_acumulada
    """
    if df.empty:
        return pd.DataFrame()

    # Achata todos os valores não-NaN
    valores = df.values.flatten()
    # Filtra valores não numéricos e NaN de forma segura
    valores_filtrados = []
    for val in valores:
        try:
            if pd.notna(val):
                valores_filtrados.append(float(val))
        except (ValueError, TypeError):
            pass
    
    if len(valores_filtrados) == 0:
        return pd.DataFrame()

    # Calcula histograma
    hist, bin_edges = np.histogram(valores_filtrados, bins=bins)

    # Monta DataFrame
    faixas = [f"{bin_edges[i]:.2f} - {bin_edges[i+1]:.2f}" for i in range(len(hist))]
    frequencia_acumulada = np.cumsum(hist)

    result = pd.DataFrame({
        "faixa": faixas,
        "frequencia": hist,
        "frequencia_acumulada": frequencia_acumulada,
        "percentual": (hist / len(valores_filtrados)) * 100,
    })

    return result


# ============================================================================
# EXPORTAÇÃO
# ============================================================================


def export_to_csv(df: pd.DataFrame, filename: str = "dashid_export.csv") -> bytes:
    """Exporta DataFrame para CSV.

    Args:
        df: DataFrame a exportar.
        filename: Nome do arquivo (apenas para referência).

    Returns:
        Conteúdo do CSV em bytes.
    """
    csv_buffer = io.BytesIO()
    df.to_csv(csv_buffer, index=True, encoding="utf-8-sig")
    csv_buffer.seek(0)
    return csv_buffer.getvalue()


def export_to_excel(df: pd.DataFrame, filename: str = "dashid_export.xlsx") -> bytes:
    """Exporta DataFrame para Excel.

    Args:
        df: DataFrame a exportar.
        filename: Nome do arquivo (apenas para referência).

    Returns:
        Conteúdo do Excel em bytes.
    """
    excel_buffer = io.BytesIO()
    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="DashID", index=True)
    excel_buffer.seek(0)
    return excel_buffer.getvalue()


# ============================================================================
# TESTES (opcional, para desenvolvimento)
# ============================================================================

if __name__ == "__main__":
    print("Módulo analytics.py carregado com sucesso.")
    print(f"Meta do ID: {META_ID} ({META_ID*100:.0f}%)")
    print(f"Configurações de negócio: {BUSINESS_CONFIG}")
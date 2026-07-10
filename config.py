"""
DashID - Módulo de Configurações Globais
=========================================

Define constantes, paleta de cores, configurações de tema e parâmetros
de negócio utilizados em todo o dashboard.

Autor: Alex Paulo
Versão: 0.1.0
"""

# ============================================================================
# INFORMAÇÕES DO PROJETO
# ============================================================================
PROJECT_NAME = "DashID"
PROJECT_VERSION = "0.1.0"
PROJECT_DESCRIPTION = (
    "Dashboard de análise de performance diária de lojas da "
    "NSF Cosméticos e Presentes (Cp Fani)"
)
PROJECT_AUTHOR = "Sunstrix"
PROJECT_REPO = "https://github.com/sunstrix/DashID"

# ============================================================================
# PALETA DE CORES - TEMA ESCURO PREMIUM
# ============================================================================
# Identidade visual inspirada na NSF Cosméticos / Cp Fani, com acabamento
# premium em tema escuro. A paleta combina dourado (sofisticação), magenta
# (identidade da marca) e tons neutros frios para o fundo.


class Colors:
    """Paleta de cores do DashID."""

    # --- Fundos (backgrounds) ------------------------------------------------
    BACKGROUND = "#0A0E1A"          # Fundo principal (azul-noite profundo)
    SIDEBAR_BG = "#0F1420"          # Fundo da barra lateral
    CARD_BG = "#151B2E"             # Fundo de cards e containers
    CARD_BORDER = "#1F2940"         # Borda sutil dos cards
    INPUT_BG = "#1A2038"            # Fundo de inputs e seletores
    HOVER_BG = "#1E2746"            # Fundo em estado hover

    # --- Cores primárias da marca -------------------------------------------
    PRIMARY = "#D4AF37"             # Dourado principal (identidade premium)
    PRIMARY_LIGHT = "#F4D03F"       # Dourado claro (destaques)
    PRIMARY_DARK = "#A8862A"        # Dourado escuro (contraste)
    SECONDARY = "#E91E63"           # Magenta/rosa (identidade Cp Fani)
    SECONDARY_LIGHT = "#F06292"     # Rosa claro
    ACCENT = "#FFD700"              # Ouro (acentos de destaque)

    # --- Texto --------------------------------------------------------------
    TEXT_PRIMARY = "#FFFFFF"        # Texto principal (branco puro)
    TEXT_SECONDARY = "#B0B8C8"      # Texto secundário (cinza-azulado)
    TEXT_MUTED = "#6B7280"          # Texto silenciado
    TEXT_ON_PRIMARY = "#0A0E1A"     # Texto sobre fundo dourado

    # --- Cores semânticas (status) ------------------------------------------
    SUCCESS = "#10B981"             # Verde (positivo/acima da meta)
    SUCCESS_LIGHT = "#34D399"       # Verde claro
    DANGER = "#EF4444"              # Vermelho (negativo/abaixo da meta)
    DANGER_LIGHT = "#F87171"        # Vermelho claro
    WARNING = "#F59E0B"             # Amarelo (alerta/atenção)
    WARNING_LIGHT = "#FBBF24"       # Amarelo claro
    INFO = "#3B82F6"                # Azul (informação)
    INFO_LIGHT = "#60A5FA"          # Azul claro
    NEUTRAL = "#6B7280"             # Cinza (estável/sem variação)

    # --- Paleta para gráficos Plotly (10 cores distintas) -------------------
    PLOTLY_PALETTE = [
        "#D4AF37",  # Dourado
        "#E91E63",  # Magenta
        "#3B82F6",  # Azul
        "#10B981",  # Verde
        "#F59E0B",  # Âmbar
        "#8B5CF6",  # Roxo
        "#EC4899",  # Rosa
        "#14B8A6",  # Teal
        "#F97316",  # Laranja
        "#06B6D4",  # Ciano
    ]

    # --- Gradientes (para uso em CSS/HTML customizado) ----------------------
    GRADIENT_PRIMARY = "linear-gradient(135deg, #D4AF37 0%, #F4D03F 100%)"
    GRADIENT_SECONDARY = "linear-gradient(135deg, #E91E63 0%, #F06292 100%)"
    GRADIENT_CARD = "linear-gradient(135deg, #151B2E 0%, #1A2038 100%)"


# ============================================================================
# CONFIGURAÇÕES DE NEGÓCIO
# ============================================================================

BUSINESS_CONFIG = {
    # Índice de atingimento de meta (1.0 = 100% da meta)
    "META_THRESHOLD": 1.0,

    # Limiares de performance (usados em formatação condicional)
    "PERFORMANCE_HIGH": 1.15,      # Acima de 115% = excelente
    "PERFORMANCE_MEDIUM": 1.05,    # Acima de 105% = bom
    "PERFORMANCE_LOW": 0.95,       # Abaixo de 95% = atenção
    "PERFORMANCE_CRITICAL": 0.85,  # Abaixo de 85% = crítico

    # Análise de tendência
    "CONSECUTIVE_DROP_THRESHOLD": 3,  # Dias consecutivos de queda para alerta

    # Médias móveis
    "MOVING_AVERAGE_SHORT": 3,     # MMA de 3 dias
    "MOVING_AVERAGE_LONG": 7,      # MMA de 7 dias

    # Regressão linear (análise de tendência)
    "TREND_REGRESSION_MIN_POINTS": 3,  # Mínimo de pontos para calcular tendência
}

# ============================================================================
# CONFIGURAÇÕES DE CANAIS / REGIÕES
# ============================================================================
# Prefixos das linhas de totalização presentes na planilha.
# Usado para identificar e agrupar lojas por canal.

CHANNEL_PREFIXES = {
    "SBC": "CANAL LOJA SBC",
    "SP": "CANAL LOJA SP",
    "CP_FANI": "CANAL LOJA CP FANI",
}

# Mapeamento amigável para exibição
CHANNEL_LABELS = {
    "SBC": "São Bernardo do Campo",
    "SP": "São Paulo",
    "CP_FANI": "Cp Fani (Consolidado)",
}

# ============================================================================
# CONFIGURAÇÕES DE CACHE
# ============================================================================

CACHE_CONFIG = {
    # TTL (Time To Live) em segundos - 0 = cache permanente até mudar input
    "DATA_TTL": 0,
    "ANALYTICS_TTL": 0,

    # Mostrar indicador de cache no Streamlit
    "SHOW_INDICATOR": False,
}

# ============================================================================
# CONFIGURAÇÕES DE LAYOUT
# ============================================================================

LAYOUT_CONFIG = {
    # Streamlit
    "PAGE_TITLE": "DashID | NSF Cosméticos - Cp Fani",
    "PAGE_ICON": "📊",
    "LAYOUT": "wide",                  # "wide" ou "centered"
    "INITIAL_SIDEBAR_STATE": "expanded",  # "expanded", "collapsed", "auto"

    # Tipografia
    "FONT_FAMILY": "'Segoe UI', 'Inter', sans-serif",

    # Dimensões
    "CHART_HEIGHT": 450,               # Altura padrão dos gráficos (px)
    "CHART_HEIGHT_SMALL": 300,         # Altura de gráficos pequenos
    "KPI_CARD_HEIGHT": 140,            # Altura dos cards de KPI

    # Heatmap
    "HEATMAP_COLORSCALE": [
        [0.0, "#EF4444"],    # Vermelho (pior)
        [0.5, "#151B2E"],    # Fundo neutro
        [1.0, "#10B981"],    # Verde (melhor)
    ],
}

# ============================================================================
# CONFIGURAÇÕES DE PLOTLY (template unificado)
# ============================================================================

PLOTLY_LAYOUT_TEMPLATE = {
    "layout": {
        "paper_bgcolor": Colors.CARD_BG,
        "plot_bgcolor": Colors.CARD_BG,
        "font": {
            "color": Colors.TEXT_PRIMARY,
            "family": "'Segoe UI', 'Inter', sans-serif",
            "size": 12,
        },
        "title": {
            "font": {"size": 16, "color": Colors.PRIMARY},
            "x": 0.5,
            "xanchor": "center",
        },
        "legend": {
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": Colors.TEXT_SECONDARY, "size": 11},
        },
        "xaxis": {
            "gridcolor": Colors.CARD_BORDER,
            "linecolor": Colors.CARD_BORDER,
            "zerolinecolor": Colors.CARD_BORDER,
        },
        "yaxis": {
            "gridcolor": Colors.CARD_BORDER,
            "linecolor": Colors.CARD_BORDER,
            "zerolinecolor": Colors.CARD_BORDER,
        },
        "margin": {"l": 50, "r": 30, "t": 60, "b": 50},
        "colorway": Colors.PLOTLY_PALETTE,
    }
}

# ============================================================================
# CONFIGURAÇÕES DE ARQUIVO
# ============================================================================

FILE_CONFIG = {
    # Nome padrão da aba da planilha
    "SHEET_NAME": "Planilha1",

    # Extensões aceitas no upload
    "ALLOWED_EXTENSIONS": [".xlsx", ".xlsm"],

    # Tamanho máximo do arquivo (em bytes) - 20 MB
    "MAX_FILE_SIZE_MB": 20,
    "MAX_FILE_SIZE_BYTES": 20 * 1024 * 1024,

    # Diretório de dados (quando usando conector SharePoint)
    "DATA_DIR": "data",
    "DEFAULT_FILENAME": "projecao_diaria.xlsx",
}

# ============================================================================
# CONFIGURAÇÕES DE LOG
# ============================================================================

LOG_CONFIG = {
    "LEVEL": "INFO",
    "FORMAT": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    "DATE_FORMAT": "%Y-%m-%d %H:%M:%S",
}

# ============================================================================
# CSS CUSTOMIZADO DO STREAMLIT
# ============================================================================
# CSS injetado via st.markdown para aplicar o tema escuro premium.

CUSTOM_CSS = f"""
<style>
    /* === Fundo principal === */
    .stApp {{
        background-color: {Colors.BACKGROUND};
        color: {Colors.TEXT_PRIMARY};
        font-family: {LAYOUT_CONFIG['FONT_FAMILY']};
    }}

    /* === Barra lateral === */
    section[data-testid="stSidebar"] {{
        background-color: {Colors.SIDEBAR_BG};
        border-right: 1px solid {Colors.CARD_BORDER};
    }}

    /* === Headers === */
    h1, h2, h3, h4 {{
        color: {Colors.PRIMARY};
        font-weight: 600;
    }}

    h1 {{
        background: {Colors.GRADIENT_PRIMARY};
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}

    /* === Cards (st.metric e containers) === */
    div[data-testid="stMetric"] {{
        background-color: {Colors.CARD_BG};
        border: 1px solid {Colors.CARD_BORDER};
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}

    div[data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(212, 175, 55, 0.15);
    }}

    div[data-testid="stMetric"] label {{
        color: {Colors.TEXT_SECONDARY} !important;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
        color: {Colors.TEXT_PRIMARY} !important;
        font-size: 1.8rem;
        font-weight: 700;
    }}

    /* === DataFrames === */
    div[data-testid="stDataFrame"] {{
        border: 1px solid {Colors.CARD_BORDER};
        border-radius: 8px;
        overflow: hidden;
    }}

    /* === Botões === */
    .stButton > button {{
        background-color: {Colors.CARD_BG};
        color: {Colors.TEXT_PRIMARY};
        border: 1px solid {Colors.PRIMARY};
        border-radius: 8px;
        padding: 0.4rem 1.2rem;
        font-weight: 500;
        transition: all 0.2s ease;
    }}

    .stButton > button:hover {{
        background-color: {Colors.PRIMARY};
        color: {Colors.TEXT_ON_PRIMARY};
        border-color: {Colors.PRIMARY_LIGHT};
    }}

    /* === Primary button === */
    .stButton > button[kind="primary"] {{
        background: {Colors.GRADIENT_PRIMARY};
        color: {Colors.TEXT_ON_PRIMARY};
        border: none;
        font-weight: 600;
    }}

    /* === File uploader === */
    div[data-testid="stFileUploader"] {{
        background-color: {Colors.CARD_BG};
        border: 2px dashed {Colors.PRIMARY};
        border-radius: 12px;
        padding: 20px;
    }}

    /* === Selectbox / Multiselect === */
    div[data-testid="stSelectbox"],
    div[data-testid="stMultiSelect"] {{
        background-color: {Colors.INPUT_BG};
        border: 1px solid {Colors.CARD_BORDER};
        border-radius: 8px;
    }}

    /* === Expander === */
    section[data-testid="stSidebar"] .streamlit-expanderHeader,
    .streamlit-expanderHeader {{
        background-color: {Colors.CARD_BG};
        border: 1px solid {Colors.CARD_BORDER};
        border-radius: 8px;
        color: {Colors.TEXT_PRIMARY};
    }}

    /* === Divider === */
    hr {{
        border-color: {Colors.CARD_BORDER};
    }}

    /* === Tabs === */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
    }}

    .stTabs [data-baseweb="tab"] {{
        background-color: {Colors.CARD_BG};
        border: 1px solid {Colors.CARD_BORDER};
        border-radius: 8px 8px 0 0;
        color: {Colors.TEXT_SECONDARY};
        padding: 10px 20px;
    }}

    .stTabs [aria-selected="true"] {{
        background: {Colors.GRADIENT_PRIMARY};
        color: {Colors.TEXT_ON_PRIMARY};
        border-color: {Colors.PRIMARY};
    }}

    /* === Alert boxes === */
    .stAlert {{
        border-radius: 8px;
    }}

    /* === Scrollbar customizada === */
    ::-webkit-scrollbar {{
        width: 10px;
        height: 10px;
    }}

    ::-webkit-scrollbar-track {{
        background: {Colors.BACKGROUND};
    }}

    ::-webkit-scrollbar-thumb {{
        background: {Colors.CARD_BORDER};
        border-radius: 5px;
    }}

    ::-webkit-scrollbar-thumb:hover {{
        background: {Colors.PRIMARY_DARK};
    }}
</style>
"""

# ============================================================================
# UTILITÁRIOS
# ============================================================================


def get_color_for_value(value: float, threshold: float = 1.0) -> str:
    """Retorna a cor apropriada para um valor de índice de atingimento.

    Args:
        value: Valor do índice (ex.: 1.15, 0.92).
        threshold: Limiar da meta (padrão: 1.0).

    Returns:
        Código hexadecimal da cor correspondente.
    """
    if value >= BUSINESS_CONFIG["PERFORMANCE_HIGH"]:
        return Colors.SUCCESS
    elif value >= threshold:
        return Colors.SUCCESS_LIGHT
    elif value >= BUSINESS_CONFIG["PERFORMANCE_LOW"]:
        return Colors.WARNING
    elif value >= BUSINESS_CONFIG["PERFORMANCE_CRITICAL"]:
        return Colors.DANGER_LIGHT
    else:
        return Colors.DANGER


def get_variation_color(variation: float) -> str:
    """Retorna a cor para uma variação percentual.

    Args:
        variation: Valor da variação (ex.: 0.05 para +5%, -0.03 para -3%).

    Returns:
        Código hexadecimal da cor.
    """
    if variation > 0.001:
        return Colors.SUCCESS
    elif variation < -0.001:
        return Colors.DANGER
    else:
        return Colors.NEUTRAL
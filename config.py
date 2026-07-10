"""
DashID - Modulo de Configuracoes Globais
=========================================

Define constantes, paleta de cores, configuracoes de tema e parametros
de negocio utilizados em todo o dashboard.

META DO ID: 115% (1.15) - Consulta de CPF do cliente no sistema.

Autor: Alex Paulo
Versao: 0.2.4
"""

# ============================================================================
# INFORMACOES DO PROJETO
# ============================================================================
PROJECT_NAME = "DashID"
PROJECT_VERSION = "0.2.4"
PROJECT_DESCRIPTION = (
    "Dashboard de analise de performance diaria de lojas da "
    "NSF Cosmeticos e Presentes (Cp Fani)"
)
PROJECT_AUTHOR = "Sunstrix"
PROJECT_REPO = "https://github.com/sunstrix/DashID"

# ============================================================================
# PALETA DE CORES - TEMA ESCURO PREMIUM
# ============================================================================
# Identidade visual inspirada na NSF Cosmeticos / Cp Fani, com acabamento
# premium em tema escuro. A paleta combina dourado (sofisticacao), magenta
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

    # --- Cores primarias da marca -------------------------------------------
    PRIMARY = "#D4AF37"             # Dourado principal (identidade premium)
    PRIMARY_LIGHT = "#F4D03F"       # Dourado claro (destaques)
    PRIMARY_DARK = "#A8862A"        # Dourado escuro (contraste)
    SECONDARY = "#E91E63"           # Magenta/rosa (identidade Cp Fani)
    SECONDARY_LIGHT = "#F06292"     # Rosa claro
    ACCENT = "#FFD700"              # Ouro (acentos de destaque)

    # --- Texto --------------------------------------------------------------
    TEXT_PRIMARY = "#FFFFFF"        # Texto principal (branco puro)
    TEXT_SECONDARY = "#B0B8C8"      # Texto secundario (cinza-azulado)
    TEXT_MUTED = "#6B7280"          # Texto silenciado
    TEXT_ON_PRIMARY = "#0A0E1A"     # Texto sobre fundo dourado

    # --- Cores semanticas (status) ------------------------------------------
    SUCCESS = "#10B981"             # Verde (positivo/acima da meta)
    SUCCESS_LIGHT = "#34D399"       # Verde claro
    DANGER = "#EF4444"              # Vermelho (negativo/abaixo da meta)
    DANGER_LIGHT = "#F87171"        # Vermelho claro
    WARNING = "#F59E0B"             # Amarelo (alerta/atencao)
    WARNING_LIGHT = "#FBBF24"       # Amarelo claro
    INFO = "#3B82F6"                # Azul (informacao)
    INFO_LIGHT = "#60A5FA"          # Azul claro
    NEUTRAL = "#6B7280"             # Cinza (estavel/sem variacao)

    # --- Paleta para graficos Plotly (10 cores distintas) -------------------
    PLOTLY_PALETTE = [
        "#D4AF37",  # Dourado
        "#E91E63",  # Magenta
        "#3B82F6",  # Azul
        "#10B981",  # Verde
        "#F59E0B",  # Ambar
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
# CONFIGURACOES DE NEGOCIO
# ============================================================================

# META DO ID (Indice de Identificacao) = 115% (1.15)
# Consulta de CPF do cliente no sistema.
# REGRA DE OURO: Toda analise deve usar 1.15 como referencia.
META_ID = 1.15

BUSINESS_CONFIG = {
    # Indice de atingimento de meta (1.15 = 115% da meta)
    "META_THRESHOLD": META_ID,

    # Limiares de performance (usados em formatacao condicional)
    # Ajustados em relacao a meta de 1.15
    "PERFORMANCE_HIGH": 1.30,      # Acima de 130% = excelente
    "PERFORMANCE_MEDIUM": 1.20,    # Acima de 120% = bom
    "PERFORMANCE_LOW": 1.10,       # Abaixo de 110% = atencao
    "PERFORMANCE_CRITICAL": 1.00,  # Abaixo de 100% = critico

    # Analise de tendencia
    "CONSECUTIVE_DROP_THRESHOLD": 3,  # Dias consecutivos de queda para alerta

    # Medias moveis
    "MOVING_AVERAGE_SHORT": 3,     # MMA de 3 dias
    "MOVING_AVERAGE_LONG": 7,      # MMA de 7 dias

    # Regressao linear (analise de tendencia)
    "TREND_REGRESSION_MIN_POINTS": 3,  # Minimo de pontos para calcular tendencia
}

# ============================================================================
# CONFIGURACOES DE CANAIS / REGIOES
# ============================================================================
# Prefixos das linhas de totalizacao presentes na planilha.
# Usado para identificar e agrupar lojas por canal.

CHANNEL_PREFIXES = {
    "SBC": "SOMA LOJA SBC",
    "SP": "Total LOJA SP",
    "CP_FANI": "TOTAL CANAL LOJA CP FANI",
}

# Mapeamento amigavel para exibicao
CHANNEL_LABELS = {
    "SBC": "Sao Bernardo do Campo",
    "SP": "Sao Paulo",
    "CP_FANI": "Cp Fani (Consolidado)",
}

# ============================================================================
# CONFIGURACOES DE SHAREPOINT
# ============================================================================
#
# IMPORTANTE - COMO OBTER A URL CORRETA DO SHAREPOINT:
#
# 1. Abra o arquivo "Relatorio de projecao mes julho 26.xlsx" no SharePoint
#    (https://didiernsf.sharepoint.com)
#
# 2. Clique no botao "Compartilhar" (ou "Share") no canto superior direito
#
# 3. Na janela de compartilhamento, clique em "Qualquer pessoa com o link
#    pode editar" (ou similar) para ajustar as permissoes
#
# 4. Selecione "Qualquer pessoa" e marque "Permitir download" (IMPORTANTE!)
#
# 5. Clique em "Aplicar" e depois em "Copiar link"
#
# 6. Cole o link abaixo no campo SHARE_URL
#
# FORMATO CORRETO da URL (exemplo):
#   https://didiernsf.sharepoint.com/:x:/s/NSFcosmticosepresentesLTDA/
#   EajHkR8mT8tNnQm5yZxYwB0Bxyz123?e=AbCdEf
#
# FORMATO INCORRETO (NAO USAR):
#   {713fd0fc-9f7f-475a-b2af-911be0c9a52a}  <- Isso e um GUID, nao URL!
#
# ============================================================================

SHAREPOINT_CONFIG = {
    # Link de compartilhamento direto do SharePoint
    #
    # COLE AQUI a URL completa copiada do botao "Compartilhar" do SharePoint
    # A URL deve começar com "https://" e conter "/:x:/" (indica arquivo Excel)
    #
    # Exemplo de URL valida:
    # "https://didiernsf.sharepoint.com/:x:/s/NSFcosmticosepresentesLTDA/EajHkR8mT8tNnQm5yZxYwB0Bxyz123?e=AbCdEf"
    #
    # URL invalida (GUID - NAO funciona):
    # "{713fd0fc-9f7f-475a-b2af-911be0c9a52a}"
    #
    # SUBSTITUA A URL ABAIXO pela URL real do seu arquivo:
    "SHARE_URL": (
        "https://didiernsf.sharepoint.com/:x:/s/"
        "NSFcosmticosepresentesLTDA/"
        "IQAP_RPH98laR7KvkRvgyaUqAYM5B2REUbXMGolJdXTTFHQ"
        "?e=gaqRoIPe3kg"
    ),

    # Diretorio local para cache do arquivo
    "CACHE_DIR": "data",
    "CACHE_FILENAME": "relatorio_sharepoint.xlsx",

    # TTL do cache em segundos (1 hora = 3600 segundos)
    "CACHE_TTL": 3600,

    # Timeout para requisicoes (segundos)
    "TIMEOUT": 30,

    # Validacao da URL (nao alterar)
    "URL_MUST_START_WITH": "https://",
}

# ============================================================================
# VALIDACAO DA URL DO SHAREPOINT
# ============================================================================


def validate_sharepoint_url():
    """Valida se a URL do SharePoint esta no formato correto.

    Returns:
        Tupla (is_valid, error_message)
    """
    url = SHAREPOINT_CONFIG.get("SHARE_URL", "")

    if not url:
        return False, "SHARE_URL esta vazio em config.py"

    if not url.startswith(SHAREPOINT_CONFIG["URL_MUST_START_WITH"]):
        return False, (
            f"SHARE_URL invalido. Deve comecar com 'https://'. "
            f"Valor atual: {url[:50]}..."
        )

    # Verifica se nao e um GUID (erro comum)
    if url.startswith("{") and url.endswith("}"):
        return False, (
            "SHARE_URL contem um GUID em vez de uma URL completa. "
            "Use o botao 'Compartilhar' do SharePoint para obter a URL correta."
        )

    # Verifica se parece ser uma URL do SharePoint
    if "sharepoint.com" not in url.lower():
        return False, (
            "SHARE_URL nao parece ser uma URL do SharePoint. "
            f"Valor atual: {url[:50]}..."
        )

    return True, "URL valida"


# Executa validacao ao importar o modulo
_url_valid, _url_error = validate_sharepoint_url()
if not _url_valid:
    import warnings
    warnings.warn(
        f"[DashID] Configuracao invalida do SharePoint: {_url_error}",
        UserWarning,
        stacklevel=2
    )

# ============================================================================
# CONFIGURACOES DE CACHE
# ============================================================================

CACHE_CONFIG = {
    # TTL (Time To Live) em segundos - 0 = cache permanente ate mudar input
    "DATA_TTL": 0,
    "ANALYTICS_TTL": 0,

    # Mostrar indicador de cache no Streamlit
    "SHOW_INDICATOR": False,
}

# ============================================================================
# CONFIGURACOES DE LAYOUT
# ============================================================================

LAYOUT_CONFIG = {
    # Streamlit
    "PAGE_TITLE": "DashID | NSF Cosmeticos - Cp Fani",
    "PAGE_ICON": "📊",
    "LAYOUT": "wide",                  # "wide" ou "centered"
    "INITIAL_SIDEBAR_STATE": "expanded",  # "expanded", "collapsed", "auto"

    # Tipografia
    "FONT_FAMILY": "'Segoe UI', 'Inter', sans-serif",

    # Dimensoes
    "CHART_HEIGHT": 450,               # Altura padrao dos graficos (px)
    "CHART_HEIGHT_SMALL": 300,         # Altura de graficos pequenos
    "KPI_CARD_HEIGHT": 140,            # Altura dos cards de KPI

    # Heatmap
    "HEATMAP_COLORSCALE": [
        [0.0, "#EF4444"],    # Vermelho (pior)
        [0.5, "#151B2E"],    # Fundo neutro
        [1.0, "#10B981"],    # Verde (melhor)
    ],
}

# ============================================================================
# CONFIGURACOES DE PLOTLY (template unificado)
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
# CONFIGURACOES DE ARQUIVO
# ============================================================================

FILE_CONFIG = {
    # Nome padrao da aba da planilha
    "SHEET_NAME": "Planilha1",

    # Extensoes aceitas no upload
    "ALLOWED_EXTENSIONS": [".xlsx", ".xlsm"],

    # Tamanho maximo do arquivo (em bytes) - 20 MB
    "MAX_FILE_SIZE_MB": 20,
    "MAX_FILE_SIZE_BYTES": 20 * 1024 * 1024,

    # Diretorio de dados (quando usando conector SharePoint)
    "DATA_DIR": "data",
    "DEFAULT_FILENAME": "projecao_diaria.xlsx",
}

# ============================================================================
# CONFIGURACOES DE LOG
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

    /* === Botoes === */
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
# UTILITARIOS
# ============================================================================


def get_color_for_value(value: float, threshold: float = None) -> str:
    """Retorna a cor apropriada para um valor de indice de atingimento.

    Args:
        value: Valor do indice (ex.: 1.25, 1.10).
        threshold: Limiar da meta (padrao: META_ID = 1.15).

    Returns:
        Codigo hexadecimal da cor correspondente.
    """
    if threshold is None:
        threshold = META_ID

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
    """Retorna a cor para uma variacao percentual.

    Args:
        variation: Valor da variacao (ex.: 0.05 para +5%, -0.03 para -3%).

    Returns:
        Codigo hexadecimal da cor.
    """
    if variation > 0.001:
        return Colors.SUCCESS
    elif variation < -0.001:
        return Colors.DANGER
    else:
        return Colors.NEUTRAL


def format_percentage(value: float, decimals: int = 2) -> str:
    """Formata valor como percentual.

    Args:
        value: Valor a formatar (ex.: 1.1522).
        decimals: Casas decimais (padrao: 2).

    Returns:
        String formatada (ex.: "115.22%").
    """
    import pandas as pd
    if pd.isna(value):
        return "-"
    return f"{value*100:.{decimals}f}%"


def format_meta_info() -> str:
    """Retorna string informativa sobre a meta do ID.

    Returns:
        String formatada com informacao da meta.
    """
    return f"Meta do ID: {META_ID*100:.0f}% ({META_ID})"
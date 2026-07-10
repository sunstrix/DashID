"""
DashID - Aplicacao Principal Streamlit (v0.3.0)
================================================

ESTRATEGIA DE FONTE DE DADOS (ORDEM DE PRIORIDADE):
1. ARQUIVO LOCAL (prioritaria) - lido do OneDrive/SharePoint sincronizado
   Caminho: %USERPROFILE%\NSF cosméticos e presentes LTDA\
            NSF Cosméticos e Presentes LTDA - Documentos\
            Departamento Pessoal\EMILY - Multi Lojas\
            relatório ID Relatório de projeção.xlsx

2. SHAREPOINT VIA HTTP (fallback) - download direto do link
   Usado apenas se arquivo local nao existir

3. UPLOAD MANUAL (emergencia) - usuario envia arquivo
   Ultima opcao se ambas acima falharem

META DO ID: 115% (1.15) - Consulta de CPF do cliente no sistema.

Autor: Alex Paulo
Versao: 0.3.0
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
import os
import logging
import traceback
from datetime import datetime

from config import (
    BUSINESS_CONFIG,
    Colors,
    CUSTOM_CSS,
    DATA_SOURCE_INFO,
    LAYOUT_CONFIG,
    LOCAL_CONFIG,
    META_ID,
    PLOTLY_LAYOUT_TEMPLATE,
    PROJECT_DESCRIPTION,
    PROJECT_NAME,
    PROJECT_VERSION,
    SHAREPOINT_CONFIG,
)
from data_loader import (
    load_data_from_local,
    load_data_from_upload,
    check_data_sources,
)
from analytics import (
    aggregate_by_channel,
    analyze_by_weekday,
    analyze_weekday_by_store,
    calculate_distribution,
    calculate_kpi_cards,
    calculate_moving_averages,
    calculate_store_ranking,
    calculate_trend,
    calculate_daily_variation,
    calculate_volatility,
    detect_consecutive_drops,
    export_to_csv,
    export_to_excel,
    get_best_worst_weekday,
    get_top_movers,
    prepare_variation_table,
)

# ============================================================================
# CONFIGURACAO DE LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
)
logger = logging.getLogger("dashid.app")

# ============================================================================
# CONFIGURACAO DA PAGINA
# ============================================================================

try:
    st.set_page_config(
        page_title=LAYOUT_CONFIG["PAGE_TITLE"],
        page_icon=LAYOUT_CONFIG["PAGE_ICON"],
        layout=LAYOUT_CONFIG["LAYOUT"],
        initial_sidebar_state=LAYOUT_CONFIG["INITIAL_SIDEBAR_STATE"],
    )
except Exception as e:
    logger.error(f"Erro ao configurar pagina: {e}")

# Injeta CSS customizado
try:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)
except Exception as e:
    logger.error(f"Erro ao injetar CSS: {e}")

# ============================================================================
# FUNCAO DE CARREGAMENTO COM ESTRATEGIA DE FALLBACK
# ============================================================================


def load_data_with_fallback():
    """Carrega dados seguindo a estrategia de prioridade.

    Ordem:
    1. Tenta arquivo local (rapido e confiavel)
    2. Se falhar, tenta SharePoint via HTTP (fallback)
    3. Retorna dados + info da fonte usada

    Returns:
        Tupla (data_dict, source_used, error_message)
    """
    # VERIFICA FONTES DISPONIVEIS
    sources = check_data_sources()
    logger.info(f"Fontes disponiveis: {sources}")

    # TENTATIVA 1: ARQUIVO LOCAL (PRIORITARIO)
    if sources.get("local_available"):
        try:
            logger.info(f"Tentando ler arquivo local: {sources['local_path']}")
            data = load_data_from_local()
            logger.info("Arquivo local carregado com sucesso!")
            return data, "local", None
        except Exception as e:
            error_msg = f"Erro ao ler arquivo local: {e}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            # Continua para proxima tentativa
    else:
        logger.warning(f"Arquivo local nao disponivel: {sources.get('local_error')}")

    # TENTATIVA 2: SHAREPOINT VIA HTTP (FALLBACK)
    try:
        from sharepoint_connector import load_data_from_sharepoint_link

        share_url = SHAREPOINT_CONFIG.get("SHARE_URL")
        if share_url:
            logger.info("Tentando download do SharePoint via HTTP...")
            file_content, metadata = load_data_from_sharepoint_link(share_url)

            if file_content is not None:
                # Cria objeto fake para o data_loader
                class FakeUploadedFile:
                    def __init__(self, content, name, size):
                        self._content = content
                        self.name = name
                        self.size = size

                    def getvalue(self):
                        return self._content

                fake_file = FakeUploadedFile(
                    content=file_content,
                    name=metadata.get("filename", "sharepoint.xlsx") if metadata else "sharepoint.xlsx",
                    size=metadata.get("file_size_bytes", len(file_content)) if metadata else len(file_content),
                )

                data = load_data_from_upload(fake_file)
                data["metadata"]["source"] = "sharepoint"
                if metadata:
                    data["metadata"]["last_update"] = metadata.get("last_update")

                logger.info("SharePoint carregado com sucesso (fallback)!")
                return data, "sharepoint", None
            else:
                sp_error = metadata.get("error", "Erro desconhecido") if metadata else "Erro desconhecido"
                logger.error(f"SharePoint falhou: {sp_error}")
        else:
            logger.warning("URL do SharePoint nao configurada")
    except Exception as e:
        logger.error(f"Erro no fallback do SharePoint: {e}")
        logger.error(traceback.format_exc())

    # TODAS AS TENTATIVAS FALHARAM
    return None, None, "Nenhuma fonte de dados disponivel"


# ============================================================================
# SIDEBAR
# ============================================================================


def render_sidebar():
    """Renderiza a barra lateral com estrategia de fallback inteligente."""
    try:
        with st.sidebar:
            # Logo/Titulo
            st.markdown(
                f"""
                <div style="text-align: center; padding: 20px 0;">
                    <h1 style="margin: 0; font-size: 2.5rem;">📊 {PROJECT_NAME}</h1>
                    <p style="color: {Colors.TEXT_SECONDARY}; margin-top: 8px;">
                        {PROJECT_DESCRIPTION}
                    </p>
                    <p style="color: {Colors.PRIMARY}; font-size: 0.85rem; margin-top: 4px;
                       font-weight: 600;">
                        🎯 Meta do ID: {META_ID*100:.0f}%
                    </p>
                    <p style="color: {Colors.TEXT_MUTED}; font-size: 0.75rem; margin-top: 2px;">
                        Versao {PROJECT_VERSION}
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            st.markdown("---")

            # STATUS DA FONTE DE DADOS
            st.markdown("### 📂 Fonte de Dados")

            # Carrega dados automaticamente se ainda nao carregou
            if "data" not in st.session_state:
                if "load_attempted" not in st.session_state:
                    st.session_state["load_attempted"] = True

                    with st.spinner("🔄 Carregando dados..."):
                        data, source_used, error = load_data_with_fallback()

                        if data is not None:
                            st.session_state["data"] = data
                            st.session_state["source_used"] = source_used
                            st.success(f"✅ Dados carregados de: **{source_used.upper()}**")
                            st.rerun()
                        else:
                            st.session_state["load_error"] = error
                            st.error("❌ Nao foi possivel carregar dados automaticamente")
                            st.info("Use o upload manual abaixo.")

            # Informacoes da fonte usada
            if "data" in st.session_state:
                source = st.session_state.get("source_used", "desconhecido")
                source_icons = {
                    "local": "💻",
                    "sharepoint": "☁️",
                    "upload": "📁",
                }
                source_names = {
                    "local": "Arquivo Local (OneDrive)",
                    "sharepoint": "SharePoint (HTTP)",
                    "upload": "Upload Manual",
                }
                icon = source_icons.get(source, "❓")
                name = source_names.get(source, source)

                st.success(f"{icon} Fonte: **{name}**")

                metadata = st.session_state["data"]["metadata"]

                # Mostra caminho se for local
                if source == "local":
                    st.caption(f"📍 {metadata.get('file_path', '-')}")
                    if metadata.get('last_modified'):
                        st.caption(f"🕐 Modificado: {metadata['last_modified']}")

            # Botao para forcar recarga
            if st.button("🔄 Recarregar dados"):
                keys_to_remove = ["data", "source_used", "load_attempted", "load_error"]
                for key in keys_to_remove:
                    if key in st.session_state:
                        del st.session_state[key]
                # Limpa caches
                try:
                    load_data_from_local.clear()
                    load_data_from_upload.clear()
                except:
                    pass
                st.rerun()

            # UPLOAD MANUAL (sempre disponivel como opcao)
            with st.expander("📁 Upload Manual (substituir fonte)"):
                st.caption(
                    "Envie uma planilha Excel (.xlsx) para substituir a fonte atual."
                )
                uploaded_file = st.file_uploader(
                    "Arquivo local (.xlsx)",
                    type=["xlsx", "xlsm"],
                    label_visibility="collapsed",
                )

                if uploaded_file is not None:
                    try:
                        with st.spinner("Processando arquivo..."):
                            data = load_data_from_upload(uploaded_file)
                            data["metadata"]["source"] = "upload"
                            st.session_state["data"] = data
                            st.session_state["source_used"] = "upload"
                            st.success("✅ Arquivo carregado!")
                            st.rerun()
                    except Exception as e:
                        st.error(f"❌ Erro: {e}")
                        logger.error(traceback.format_exc())

            st.markdown("---")

            # NAVEGACAO
            st.markdown("### 🧭 Navegacao")
            navigation = st.radio(
                "Selecione a analise:",
                [
                    "📊 Visao Geral",
                    "📈 Analise Horizontal",
                    "📅 Dia da Semana",
                    "🏆 Ranking de Lojas",
                    "📉 Medias Moveis e Tendencia",
                    "⚠️ Alertas e Consistencia",
                    "🏢 Comparativo por Canal",
                    "📊 Distribuicao",
                ],
                index=0,
            )

            st.markdown("---")

            # INFORMACOES DO ARQUIVO
            if "data" in st.session_state:
                try:
                    metadata = st.session_state["data"]["metadata"]
                    st.markdown("### ℹ️ Dados Carregados")

                    date_start = "-"
                    date_end = "-"
                    dr = metadata.get("date_range", (None, None))
                    if dr and dr[0] is not None:
                        try:
                            date_start = dr[0].strftime("%d/%m/%Y")
                        except:
                            date_start = str(dr[0])
                    if dr and dr[1] is not None:
                        try:
                            date_end = dr[1].strftime("%d/%m/%Y")
                        except:
                            date_end = str(dr[1])

                    st.markdown(
                        f"""
                        - **Arquivo:** {metadata.get('filename', '-')}
                        - **Tamanho:** {metadata.get('file_size_mb', 0):.2f} MB
                        - **Lojas:** {metadata.get('num_stores', 0)}
                        - **Canais:** {metadata.get('num_channels', 0)}
                        - **Dias com dados:** {metadata.get('num_days', 0)}
                        - **Periodo:** {date_start} a {date_end}
                        - **🎯 Meta:** {META_ID*100:.0f}%
                        """
                    )
                except Exception as e:
                    st.error(f"Erro ao mostrar metadados: {e}")

            # FILTROS DE LOJA
            if "data" in st.session_state:
                try:
                    st.markdown("---")
                    st.markdown("### 🔍 Filtros")
                    store_names = st.session_state["data"]["store_names"]
                    selected_stores = st.multiselect(
                        "Selecione as lojas:",
                        options=store_names,
                        default=store_names[:5] if len(store_names) > 5 else store_names,
                        help="Deixe vazio para ver todas as lojas.",
                    )
                    st.session_state["selected_stores"] = selected_stores if selected_stores else store_names
                except Exception as e:
                    st.error(f"Erro nos filtros: {e}")

            return navigation
    except Exception as e:
        logger.error(f"Erro critico na sidebar: {e}")
        logger.error(traceback.format_exc())
        st.error(f"Erro critico na sidebar: {e}")
        return "📊 Visao Geral"


# ============================================================================
# FUNCOES AUXILIARES DE VISUALIZACAO
# ============================================================================


def format_percentage(value: float, decimals: int = 2) -> str:
    """Formata valor como percentual."""
    if pd.isna(value):
        return "-"
    return f"{value*100:.{decimals}f}%"


def format_variation(value: float, decimals: int = 2) -> str:
    """Formata variacao com sinal e cor."""
    if pd.isna(value):
        return "-"
    signal = "+" if value > 0 else ""
    return f"{signal}{value*100:.{decimals}f}%"


def meta_label() -> str:
    """Retorna label da meta formatada."""
    return f"Meta ({META_ID*100:.0f}%)"


# ============================================================================
# SECOES DO DASHBOARD (com protecao contra erros)
# ============================================================================


def render_visao_geral(df_stores: pd.DataFrame):
    """Renderiza a secao de Visao Geral com KPIs de topo."""
    try:
        st.header("📊 Visao Geral")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% (consulta de CPF do cliente)")

        kpis = calculate_kpi_cards(df_stores)

        col1, col2, col3, col4, col5 = st.columns(5)

        with col1:
            media_geral_pct = format_percentage(kpis["media_geral"])
            delta_text = "✅ Acima da meta" if kpis["media_geral"] >= META_ID else "⚠️ Abaixo da meta"
            st.metric(
                label="Indice Medio MTD",
                value=media_geral_pct,
                delta=delta_text,
                delta_color="normal" if kpis["media_geral"] >= META_ID else "inverse",
            )

        with col2:
            st.metric(
                label="Melhor Loja",
                value=kpis["melhor_loja"]["nome"][:20],
                delta=format_percentage(kpis["melhor_loja"]["valor"]),
            )

        with col3:
            pior_acima_meta = kpis["pior_loja"]["valor"] >= META_ID
            st.metric(
                label="Pior Loja",
                value=kpis["pior_loja"]["nome"][:20],
                delta=format_percentage(kpis["pior_loja"]["valor"]),
                delta_color="normal" if pior_acima_meta else "inverse",
            )

        with col4:
            pct_acima = (kpis["acima_meta"] / kpis["total_lojas"] * 100) if kpis["total_lojas"] > 0 else 0
            st.metric(
                label=f"Acima da Meta (≥{META_ID*100:.0f}%)",
                value=f"{kpis['acima_meta']} lojas",
                delta=f"{pct_acima:.1f}%",
            )

        with col5:
            pct_abaixo = (kpis["abaixo_meta"] / kpis["total_lojas"] * 100) if kpis["total_lojas"] > 0 else 0
            st.metric(
                label=f"Abaixo da Meta (<{META_ID*100:.0f}%)",
                value=f"{kpis['abaixo_meta']} lojas",
                delta=f"{pct_abaixo:.1f}%",
                delta_color="inverse",
            )

        st.markdown("---")

        # Grafico de evolucao geral
        st.subheader("📈 Evolucao Diaria Geral")
        media_diaria = df_stores.mean(axis=0)

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=media_diaria.index,
                y=media_diaria.values,
                mode="lines+markers",
                name="Media Geral",
                line=dict(color=Colors.PRIMARY, width=3),
                marker=dict(size=8),
            )
        )

        fig.add_hline(
            y=META_ID,
            line_dash="dash",
            line_color=Colors.WARNING,
            annotation_text=meta_label(),
            annotation_position="top right",
            annotation_font_color=Colors.WARNING,
        )

        fig.update_layout(
            title=f"Indice Medio de Atingimento - Evolucao Diaria (Meta: {META_ID*100:.0f}%)",
            xaxis_title="Data",
            yaxis_title="Indice de Atingimento",
            height=LAYOUT_CONFIG["CHART_HEIGHT"],
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

        # Tabela resumo por loja
        st.subheader("📋 Performance por Loja (Ultimo Dia)")
        has_data = df_stores.notna().any()
        dates_with_data = has_data[has_data].index
        if len(dates_with_data) > 0:
            last_date = dates_with_data.max()
            col_name = f"Indice ({last_date.strftime('%d/%m') if hasattr(last_date, 'strftime') else last_date})"
            ultimo_dia_df = pd.DataFrame({
                "Loja": df_stores.index,
                col_name: df_stores[last_date].values,
                "Status": df_stores[last_date].apply(
                    lambda x: "✅ Acima" if pd.notna(x) and x >= META_ID else ("⚠️ Abaixo" if pd.notna(x) else "❌ Sem dado")
                ),
            })

            st.dataframe(
                ultimo_dia_df.style.format({
                    col_name: lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-",
                }),
                use_container_width=True,
                height=500,
            )
    except Exception as e:
        st.error(f"Erro na Visao Geral: {e}")
        logger.error(traceback.format_exc())


def render_analise_horizontal(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a secao de Analise Horizontal."""
    try:
        st.header("📈 Analise Horizontal (Dia a Dia)")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Variacao = (dia atual / dia anterior) - 1")

        df_variation = calculate_daily_variation(df_stores)
        top_movers = get_top_movers(df_variation, top_n=5)

        if top_movers["data"]:
            data_str = top_movers["data"].strftime("%d/%m/%Y") if hasattr(top_movers["data"], "strftime") else str(top_movers["data"])
            st.subheader(f"🏆 Maiores Altas e Quedas - {data_str}")

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**🟢 Maiores Altas**")
                if top_movers["maiores_altas"]:
                    for loja, var in top_movers["maiores_altas"]:
                        st.markdown(f"- **{loja}**: {format_variation(var)}")

            with col2:
                st.markdown("**🔴 Maiores Quedas**")
                if top_movers["maiores_quedas"]:
                    for loja, var in top_movers["maiores_quedas"]:
                        st.markdown(f"- **{loja}**: {format_variation(var)}")

        st.markdown("---")

        stores_to_plot = [s for s in selected_stores if s in df_stores.index]
        if not stores_to_plot:
            stores_to_plot = df_stores.index.tolist()

        df_filtered = df_stores.loc[stores_to_plot]

        fig = go.Figure()
        for i, loja in enumerate(stores_to_plot):
            color = Colors.PLOTLY_PALETTE[i % len(Colors.PLOTLY_PALETTE)]
            fig.add_trace(
                go.Scatter(
                    x=df_filtered.columns,
                    y=df_filtered.loc[loja].values,
                    mode="lines+markers",
                    name=loja,
                    line=dict(color=color, width=2),
                    marker=dict(size=6),
                )
            )

        fig.add_hline(
            y=META_ID,
            line_dash="dash",
            line_color=Colors.WARNING,
            annotation_text=meta_label(),
            annotation_font_color=Colors.WARNING,
        )

        fig.update_layout(
            title=f"Evolucao Diaria do Indice por Loja (Meta: {META_ID*100:.0f}%)",
            xaxis_title="Data",
            yaxis_title="Indice de Atingimento",
            height=LAYOUT_CONFIG["CHART_HEIGHT"],
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Erro na Analise Horizontal: {e}")
        logger.error(traceback.format_exc())


def render_dia_da_semana(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a secao de Analise por Dia da Semana."""
    try:
        st.header("📅 Analise por Dia da Semana")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Agrupamento por dia da semana")

        df_weekday = analyze_by_weekday(df_stores)

        if not df_weekday.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=df_weekday.index,
                    y=df_weekday["media"],
                    name="Media",
                    marker_color=Colors.PRIMARY,
                    text=df_weekday["media"].apply(lambda x: f"{x*100:.1f}%"),
                    textposition="auto",
                )
            )

            fig.add_hline(
                y=META_ID,
                line_dash="dash",
                line_color=Colors.WARNING,
                annotation_text=meta_label(),
                annotation_font_color=Colors.WARNING,
            )

            fig.update_layout(
                title=f"Indice Medio por Dia da Semana (Meta: {META_ID*100:.0f}%)",
                xaxis_title="Dia da Semana",
                yaxis_title="Indice de Atingimento",
                height=LAYOUT_CONFIG["CHART_HEIGHT_SMALL"],
                **PLOTLY_LAYOUT_TEMPLATE["layout"],
            )

            st.plotly_chart(fig, use_container_width=True)

            st.dataframe(
                df_weekday.style.format({
                    "media": lambda x: f"{x*100:.2f}%",
                    "mediana": lambda x: f"{x*100:.2f}%",
                    "desvio_padrao": lambda x: f"{x*100:.2f}%",
                }),
                use_container_width=True,
            )
    except Exception as e:
        st.error(f"Erro na Analise por Dia da Semana: {e}")
        logger.error(traceback.format_exc())


def render_ranking(df_stores: pd.DataFrame):
    """Renderiza a secao de Ranking de Lojas."""
    try:
        st.header("🏆 Ranking de Lojas")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Ordenado pelo indice medio acumulado")

        df_ranking = calculate_store_ranking(df_stores, period="month")

        if not df_ranking.empty:
            df_ranking_display = df_ranking.copy()
            df_ranking_display["status_meta"] = df_ranking_display["indice_medio"].apply(
                lambda x: "✅ Acima" if x >= META_ID else "⚠️ Abaixo"
            )

            st.dataframe(
                df_ranking_display.style.format({
                    "indice_medio": lambda x: f"{x*100:.2f}%",
                    "variacao_semanal": lambda x: f"{x:+.2f}%" if pd.notna(x) else "-",
                }),
                use_container_width=True,
                height=500,
            )

            colors = [
                Colors.SUCCESS if val >= META_ID else Colors.DANGER
                for val in df_ranking["indice_medio"]
            ]

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=df_ranking["indice_medio"],
                    y=df_ranking["loja"],
                    orientation="h",
                    marker_color=colors,
                    text=df_ranking["indice_medio"].apply(lambda x: f"{x*100:.2f}%"),
                    textposition="auto",
                )
            )

            fig.add_vline(
                x=META_ID,
                line_dash="dash",
                line_color=Colors.WARNING,
                annotation_text=meta_label(),
                annotation_font_color=Colors.WARNING,
            )

            fig.update_layout(
                title=f"Ranking de Lojas por Indice Medio (Meta: {META_ID*100:.0f}%)",
                xaxis_title="Indice de Atingimento",
                yaxis=dict(autorange="reversed"),
                height=max(400, len(df_ranking) * 30),
                **PLOTLY_LAYOUT_TEMPLATE["layout"],
            )

            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Erro no Ranking: {e}")
        logger.error(traceback.format_exc())


def render_medias_moveis_tendencia(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a secao de Medias Moveis e Tendencia."""
    try:
        st.header("📉 Medias Moveis e Tendencia")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Suavizacao e regressao linear")

        stores_for_ma = [s for s in selected_stores if s in df_stores.index]
        if not stores_for_ma:
            stores_for_ma = df_stores.index.tolist()[:1]

        mas = calculate_moving_averages(df_stores.loc[stores_for_ma])

        if mas:
            loja_selecionada = st.selectbox(
                "Selecione uma loja para visualizar:",
                options=stores_for_ma,
                index=0,
            )

            fig = go.Figure()

            fig.add_trace(
                go.Scatter(
                    x=df_stores.columns,
                    y=df_stores.loc[loja_selecionada].values,
                    mode="lines",
                    name="Original",
                    line=dict(color=Colors.TEXT_MUTED, width=1, dash="dot"),
                )
            )

            if 3 in mas and loja_selecionada in mas[3].index:
                fig.add_trace(
                    go.Scatter(
                        x=mas[3].columns,
                        y=mas[3].loc[loja_selecionada].values,
                        mode="lines",
                        name="MMA 3 dias",
                        line=dict(color=Colors.INFO, width=2),
                    )
                )

            if 7 in mas and loja_selecionada in mas[7].index:
                fig.add_trace(
                    go.Scatter(
                        x=mas[7].columns,
                        y=mas[7].loc[loja_selecionada].values,
                        mode="lines",
                        name="MMA 7 dias",
                        line=dict(color=Colors.SECONDARY, width=2),
                    )
                )

            fig.add_hline(
                y=META_ID,
                line_dash="dash",
                line_color=Colors.WARNING,
                annotation_text=meta_label(),
                annotation_font_color=Colors.WARNING,
            )

            fig.update_layout(
                title=f"Medias Moveis - {loja_selecionada} (Meta: {META_ID*100:.0f}%)",
                xaxis_title="Data",
                yaxis_title="Indice de Atingimento",
                height=LAYOUT_CONFIG["CHART_HEIGHT"],
                **PLOTLY_LAYOUT_TEMPLATE["layout"],
            )

            st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")

        df_trend = calculate_trend(df_stores)

        if not df_trend.empty:
            st.subheader("📈 Analise de Tendencia (Regressao Linear)")

            media_atual = df_stores.mean(axis=1)
            df_trend["status_meta"] = media_atual.apply(
                lambda x: "✅ Acima" if x >= META_ID else "⚠️ Abaixo"
            )

            st.dataframe(
                df_trend.style.format({
                    "inclinacao": lambda x: f"{x:.4f}" if pd.notna(x) else "-",
                }),
                use_container_width=True,
                height=400,
            )

            trend_counts = df_trend["classificacao_tendencia"].value_counts()

            color_map = {
                "Alta": Colors.SUCCESS,
                "Estavel": Colors.NEUTRAL,
                "Queda": Colors.DANGER,
                "Dados insuficientes": Colors.TEXT_MUTED,
                "Erro": Colors.WARNING,
            }
            pie_colors = [color_map.get(label, Colors.NEUTRAL) for label in trend_counts.index]

            fig = go.Figure()
            fig.add_trace(
                go.Pie(
                    labels=trend_counts.index,
                    values=trend_counts.values,
                    marker=dict(colors=pie_colors),
                    textinfo="label+percent",
                )
            )

            fig.update_layout(
                title="Distribuicao de Tendencias por Loja",
                height=400,
                **PLOTLY_LAYOUT_TEMPLATE["layout"],
            )

            st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"Erro em Medias Moveis: {e}")
        logger.error(traceback.format_exc())


def render_alertas_consistencia(df_stores: pd.DataFrame):
    """Renderiza a secao de Alertas e Consistencia."""
    try:
        st.header("⚠️ Alertas e Consistencia")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Monitoramento de quedas e volatilidade")

        df_variation = calculate_daily_variation(df_stores)
        df_alerts = detect_consecutive_drops(df_variation, threshold=3)

        if not df_alerts.empty:
            st.warning(f"⚠️ {len(df_alerts)} loja(s) com 3 ou mais dias consecutivos de queda:")
            st.dataframe(
                df_alerts.style.format({
                    "ultima_data": lambda x: x.strftime("%d/%m/%Y") if hasattr(x, "strftime") and pd.notna(x) else str(x),
                }),
                use_container_width=True,
            )
        else:
            st.success("✅ Nenhuma loja com quedas consecutivas criticas (3+ dias)")

        st.markdown("---")

        has_data = df_stores.notna().any()
        dates_with_data = has_data[has_data].index
        if len(dates_with_data) > 0:
            last_date = dates_with_data.max()
            ultimo_dia = df_stores[last_date].dropna()
            abaixo_meta = ultimo_dia[ultimo_dia < META_ID]

            st.subheader(f"🚨 Lojas Abaixo da Meta (<{META_ID*100:.0f}%) no Ultimo Dia")

            if len(abaixo_meta) > 0:
                df_abaixo = pd.DataFrame({
                    "Loja": abaixo_meta.index,
                    "Indice": abaixo_meta.values,
                    "Distancia da Meta": abaixo_meta.apply(lambda x: META_ID - x),
                })
                df_abaixo = df_abaixo.sort_values("Indice", ascending=True)

                st.error(f"🔴 {len(abaixo_meta)} loja(s) abaixo da meta no ultimo dia:")
                st.dataframe(
                    df_abaixo.style.format({
                        "Indice": lambda x: f"{x*100:.2f}%",
                        "Distancia da Meta": lambda x: f"-{x*100:.2f}%",
                    }),
                    use_container_width=True,
                )
            else:
                st.success(f"✅ Todas as lojas estao acima da meta de {META_ID*100:.0f}% no ultimo dia!")

        st.markdown("---")

        df_volatility = calculate_volatility(df_stores)

        if not df_volatility.empty:
            st.subheader("📊 Volatilidade e Consistencia")
            st.dataframe(
                df_volatility.style.format({
                    "desvio_padrao": lambda x: f"{x*100:.2f}%",
                }),
                use_container_width=True,
                height=400,
            )
    except Exception as e:
        st.error(f"Erro em Alertas: {e}")
        logger.error(traceback.format_exc())


def render_comparativo_canal(df_stores: pd.DataFrame, df_channels: pd.DataFrame):
    """Renderiza a secao de Comparativo por Canal."""
    try:
        st.header("🏢 Comparativo por Canal/Regiao")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Agregacao por canal")

        df_channel_agg = aggregate_by_channel(df_channels, df_stores)

        if not df_channel_agg.empty:
            st.dataframe(
                df_channel_agg.style.format({
                    "indice_medio": lambda x: f"{x*100:.2f}%",
                    "variacao_ultimo_dia": lambda x: f"{x:+.2f}%" if pd.notna(x) else "-",
                }),
                use_container_width=True,
            )

            colors_channel = [
                Colors.SUCCESS if val >= META_ID else Colors.DANGER
                for val in df_channel_agg["indice_medio"]
            ]

            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=df_channel_agg["canal"],
                    y=df_channel_agg["indice_medio"],
                    marker_color=colors_channel,
                    text=df_channel_agg["indice_medio"].apply(lambda x: f"{x*100:.2f}%"),
                    textposition="auto",
                )
            )

            fig.add_hline(
                y=META_ID,
                line_dash="dash",
                line_color=Colors.WARNING,
                annotation_text=meta_label(),
                annotation_font_color=Colors.WARNING,
            )

            fig.update_layout(
                title=f"Indice Medio por Canal/Regiao (Meta: {META_ID*100:.0f}%)",
                xaxis_title="Canal",
                yaxis_title="Indice de Atingimento",
                height=LAYOUT_CONFIG["CHART_HEIGHT_SMALL"],
                **PLOTLY_LAYOUT_TEMPLATE["layout"],
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum dado de canal disponivel.")
    except Exception as e:
        st.error(f"Erro em Comparativo por Canal: {e}")
        logger.error(traceback.format_exc())


def render_distribuicao(df_stores: pd.DataFrame):
    """Renderiza a secao de Distribuicao."""
    try:
        st.header("📊 Distribuicao dos Indices")
        st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Concentracao de performance")

        df_dist = calculate_distribution(df_stores, bins=20)

        if not df_dist.empty:
            fig = go.Figure()
            fig.add_trace(
                go.Bar(
                    x=df_dist["faixa"],
                    y=df_dist["frequencia"],
                    marker_color=Colors.PRIMARY,
                    text=df_dist["frequencia"],
                    textposition="auto",
                )
            )

            fig.update_layout(
                title=f"Distribuicao dos Indices Diarios (Meta: {META_ID*100:.0f}%)",
                xaxis_title="Faixa de Indice",
                yaxis_title="Frequencia",
                height=LAYOUT_CONFIG["CHART_HEIGHT"],
                **PLOTLY_LAYOUT_TEMPLATE["layout"],
            )

            st.plotly_chart(fig, use_container_width=True)

            valores = df_stores.values.flatten()
            valores = valores[~np.isnan(valores)]

            if len(valores) > 0:
                acima_meta_count = int((valores >= META_ID).sum())
                abaixo_meta_count = int((valores < META_ID).sum())
                total = len(valores)

                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Total de Registros", f"{total}")
                with col2:
                    st.metric("Media Geral", f"{np.mean(valores)*100:.2f}%")
                with col3:
                    st.metric(f"Acima da Meta (≥{META_ID*100:.0f}%)", f"{acima_meta_count} ({acima_meta_count/total*100:.1f}%)")
                with col4:
                    st.metric(f"Abaixo da Meta (<{META_ID*100:.0f}%)", f"{abaixo_meta_count} ({abaixo_meta_count/total*100:.1f}%)")

            st.dataframe(
                df_dist.style.format({
                    "percentual": lambda x: f"{x:.2f}%",
                }),
                use_container_width=True,
            )
    except Exception as e:
        st.error(f"Erro em Distribuicao: {e}")
        logger.error(traceback.format_exc())


# ============================================================================
# MAIN (com protecao total)
# ============================================================================


def main():
    """Funcao principal da aplicacao com protecao total contra erros."""
    try:
        logger.info("Iniciando DashID...")
        navigation = render_sidebar()

        if "data" not in st.session_state:
            st.title(f"📊 {PROJECT_NAME}")

            error_msg = st.session_state.get("load_error", None)

            if error_msg:
                st.markdown(
                    f"""
                    <div style="text-align: center; padding: 40px 20px;">
                        <h2 style="color: {Colors.DANGER};">⚠️ Nao foi possivel carregar os dados</h2>
                        <p style="color: {Colors.TEXT_SECONDARY}; font-size: 1.1rem; margin-top: 20px;">
                            O dashboard nao conseguiu acessar nenhuma fonte de dados automaticamente.
                        </p>
                        <div style="background: {Colors.CARD_BG}; padding: 15px; border-radius: 8px; 
                                    margin: 20px auto; max-width: 700px; text-align: left;">
                            <p style="color: {Colors.DANGER};"><strong>Erro:</strong></p>
                            <code style="color: {Colors.TEXT_PRIMARY};">{error_msg}</code>
                        </div>
                        <div style="background: {Colors.CARD_BG}; padding: 15px; border-radius: 8px; 
                                    margin: 20px auto; max-width: 700px; text-align: left;">
                            <p style="color: {Colors.PRIMARY};"><strong>📍 Caminho esperado do arquivo local:</strong></p>
                            <code style="color: {Colors.TEXT_PRIMARY}; font-size: 0.85rem;">{LOCAL_CONFIG.get('FILE_PATH', 'N/A')}</code>
                        </div>
                        <p style="color: {Colors.PRIMARY}; font-size: 1rem; margin-top: 20px; font-weight: 600;">
                            👈 Use o "Upload Manual" na barra lateral
                            para carregar um arquivo local.
                        </p>
                        <p style="color: {Colors.TEXT_MUTED}; font-size: 0.9rem; margin-top: 20px;">
                            🎯 Meta do ID: {META_ID*100:.0f}% (consulta de CPF do cliente)
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.info("👈 Carregando dados... Aguarde.")
            return

        data = st.session_state["data"]
        df_stores = data["stores"]
        df_channels = data["channels"]
        selected_stores = st.session_state.get("selected_stores", data["store_names"])

        if df_stores.empty:
            st.warning("⚠️ Nenhum dado de loja encontrado na planilha.")
            return

        # Renderiza secao selecionada
        if navigation == "📊 Visao Geral":
            render_visao_geral(df_stores)
        elif navigation == "📈 Analise Horizontal":
            render_analise_horizontal(df_stores, selected_stores)
        elif navigation == "📅 Dia da Semana":
            render_dia_da_semana(df_stores, selected_stores)
        elif navigation == "🏆 Ranking de Lojas":
            render_ranking(df_stores)
        elif navigation == "📉 Medias Moveis e Tendencia":
            render_medias_moveis_tendencia(df_stores, selected_stores)
        elif navigation == "⚠️ Alertas e Consistencia":
            render_alertas_consistencia(df_stores)
        elif navigation == "🏢 Comparativo por Canal":
            render_comparativo_canal(df_stores, df_channels)
        elif navigation == "📊 Distribuicao":
            render_distribuicao(df_stores)

        logger.info("Renderizacao concluida com sucesso")

    except Exception as e:
        logger.critical(f"ERRO CRITICO NO MAIN: {e}")
        logger.critical(traceback.format_exc())
        st.error(f"❌ Erro critico no dashboard: {e}")
        st.code(traceback.format_exc(), language="text")


if __name__ == "__main__":
    main()
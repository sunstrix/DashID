"""
DashID - Aplicação Principal Streamlit
=======================================

Dashboard de análise de performance diária de lojas da NSF Cosméticos e Presentes (Cp Fani).

Estrutura:
- Sidebar: upload de arquivo, navegação, filtros
- Visão Geral: KPIs de topo (cards)
- Análise Horizontal: variação diária, gráfico de linhas, top movers
- Análise por Dia da Semana: agrupamento, heatmap, melhor/pior dia
- Ranking de Lojas: tabela ordenável com variação semanal
- Médias Móveis e Tendência: suavização e regressão linear
- Alertas e Consistência: quedas consecutivas, volatilidade
- Comparativo por Canal: agregação por região
- Distribuição: histograma dos índices

Autor: Alex Paulo
Versão: 0.1.0
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

from config import (
    BUSINESS_CONFIG,
    Colors,
    CUSTOM_CSS,
    LAYOUT_CONFIG,
    PLOTLY_LAYOUT_TEMPLATE,
    PROJECT_DESCRIPTION,
    PROJECT_NAME,
    PROJECT_VERSION,
)
from data_loader import load_data_from_upload
from sharepoint_connector import check_sharepoint_status, load_data_from_sharepoint
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
# CONFIGURAÇÃO DA PÁGINA
# ============================================================================

st.set_page_config(
    page_title=LAYOUT_CONFIG["PAGE_TITLE"],
    page_icon=LAYOUT_CONFIG["PAGE_ICON"],
    layout=LAYOUT_CONFIG["LAYOUT"],
    initial_sidebar_state=LAYOUT_CONFIG["INITIAL_SIDEBAR_STATE"],
)

# Injeta CSS customizado
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================================
# SIDEBAR
# ============================================================================


def render_sidebar():
    """Renderiza a barra lateral com upload, navegação e filtros."""
    with st.sidebar:
        # Logo/Título
        st.markdown(
            f"""
            <div style="text-align: center; padding: 20px 0;">
                <h1 style="margin: 0; font-size: 2.5rem;">📊 {PROJECT_NAME}</h1>
                <p style="color: {Colors.TEXT_SECONDARY}; margin-top: 8px;">
                    {PROJECT_DESCRIPTION}
                </p>
                <p style="color: {Colors.TEXT_MUTED}; font-size: 0.8rem; margin-top: 4px;">
                    Versão {PROJECT_VERSION}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("---")

        # Upload de arquivo
        st.markdown("### 📁 Fonte de Dados")

        # Verifica status do SharePoint
        sp_status = check_sharepoint_status()

        # Tabs para escolher fonte de dados
        source_tab1, source_tab2 = st.tabs(["Upload Manual", "SharePoint"])

        with source_tab1:
            uploaded_file = st.file_uploader(
                "Envie a planilha de projeção (.xlsx)",
                type=["xlsx", "xlsm"],
                help="Arquivo Excel com índice de atingimento de meta por loja e por dia.",
            )

        with source_tab2:
            if sp_status["configured"]:
                st.success("✅ SharePoint configurado")
                load_from_sp = st.button("🔄 Carregar do SharePoint")
                if load_from_sp:
                    with st.spinner("Baixando arquivo do SharePoint..."):
                        file_content, metadata = load_data_from_sharepoint()
                        if file_content:
                            st.session_state["sharepoint_data"] = file_content
                            st.success("Arquivo carregado com sucesso!")
                        else:
                            st.error("Falha ao carregar do SharePoint")
            else:
                st.warning("⚠️ SharePoint não configurado")
                st.info(
                    "Configure as variáveis de ambiente no arquivo .env "
                    "(veja .env.example)"
                )
                if sp_status["missing_vars"]:
                    st.code("\n".join(sp_status["missing_vars"]), language="bash")

        st.markdown("---")

        # Navegação
        st.markdown("### 🧭 Navegação")
        navigation = st.radio(
            "Selecione a análise:",
            [
                "📊 Visão Geral",
                "📈 Análise Horizontal",
                "📅 Dia da Semana",
                "🏆 Ranking de Lojas",
                "📉 Médias Móveis e Tendência",
                "⚠️ Alertas e Consistência",
                "🏢 Comparativo por Canal",
                "📊 Distribuição",
            ],
            index=0,
        )

        st.markdown("---")

        # Informações do arquivo
        if "data" in st.session_state:
            metadata = st.session_state["data"]["metadata"]
            st.markdown("### ℹ️ Dados Carregados")
            st.markdown(
                f"""
                - **Arquivo:** {metadata['filename']}
                - **Tamanho:** {metadata['file_size_mb']:.2f} MB
                - **Lojas:** {metadata['num_stores']}
                - **Canais:** {metadata['num_channels']}
                - **Dias:** {metadata['num_days']}
                - **Período:** {metadata['date_range'][0].strftime('%d/%m/%Y') if metadata['date_range'][0] else '-'} 
                  a {metadata['date_range'][1].strftime('%d/%m/%Y') if metadata['date_range'][1] else '-'}
                """
            )

        # Filtros de loja (aparece apenas se dados carregados)
        if "data" in st.session_state:
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

        return navigation, uploaded_file


# ============================================================================
# FUNÇÕES AUXILIARES DE VISUALIZAÇÃO
# ============================================================================


def create_plotly_figure(fig_type="line", **kwargs):
    """Cria figura Plotly com template unificado."""
    fig = go.Figure()
    fig.update_layout(**PLOTLY_LAYOUT_TEMPLATE["layout"])
    return fig


def format_percentage(value: float, decimals: int = 2) -> str:
    """Formata valor como percentual."""
    if pd.isna(value):
        return "-"
    return f"{value*100:.{decimals}f}%"


def format_variation(value: float, decimals: int = 2) -> str:
    """Formata variação com sinal e cor."""
    if pd.isna(value):
        return "-"
    signal = "+" if value > 0 else ""
    return f"{signal}{value*100:.{decimals}f}%"


# ============================================================================
# SEÇÕES DO DASHBOARD
# ============================================================================


def render_visao_geral(df_stores: pd.DataFrame):
    """Renderiza a seção de Visão Geral com KPIs de topo."""
    st.header("📊 Visão Geral")

    # Calcula KPIs
    kpis = calculate_kpi_cards(df_stores)

    # Cards de KPI
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Índice Médio MTD",
            value=format_percentage(kpis["media_geral"]),
            delta="Acima da meta" if kpis["media_geral"] >= 1.0 else "Abaixo da meta",
            delta_color="normal" if kpis["media_geral"] >= 1.0 else "inverse",
        )

    with col2:
        st.metric(
            label="Melhor Loja",
            value=kpis["melhor_loja"]["nome"],
            delta=format_percentage(kpis["melhor_loja"]["valor"]),
        )

    with col3:
        st.metric(
            label="Pior Loja",
            value=kpis["pior_loja"]["nome"],
            delta=format_percentage(kpis["pior_loja"]["valor"]),
            delta_color="inverse",
        )

    with col4:
        st.metric(
            label="Acima da Meta",
            value=f"{kpis['acima_meta']} lojas",
            delta=f"{(kpis['acima_meta']/kpis['total_lojas']*100):.1f}%" if kpis['total_lojas'] > 0 else "0%",
        )

    with col5:
        st.metric(
            label="Abaixo da Meta",
            value=f"{kpis['abaixo_meta']} lojas",
            delta=f"{(kpis['abaixo_meta']/kpis['total_lojas']*100):.1f}%" if kpis['total_lojas'] > 0 else "0%",
            delta_color="inverse",
        )

    st.markdown("---")

    # Gráfico de evolução geral (média diária de todas as lojas)
    st.subheader("📈 Evolução Diária Geral")
    media_diaria = df_stores.mean(axis=0)

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=media_diaria.index,
            y=media_diaria.values,
            mode="lines+markers",
            name="Média Geral",
            line=dict(color=Colors.PRIMARY, width=3),
            marker=dict(size=8),
        )
    )

    # Linha de meta (1.0)
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color=Colors.WARNING,
        annotation_text="Meta (100%)",
        annotation_position="top right",
    )

    fig.update_layout(
        title="Índice Médio de Atingimento de Meta - Evolução Diária",
        xaxis_title="Data",
        yaxis_title="Índice de Atingimento",
        height=LAYOUT_CONFIG["CHART_HEIGHT"],
        **PLOTLY_LAYOUT_TEMPLATE["layout"],
    )

    st.plotly_chart(fig, use_container_width=True)


def render_analise_horizontal(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a seção de Análise Horizontal."""
    st.header("📈 Análise Horizontal (Dia a Dia)")

    # Calcula variação diária
    df_variation = calculate_daily_variation(df_stores)

    # Top movers
    top_movers = get_top_movers(df_variation, top_n=5)

    if top_movers["data"]:
        st.subheader(f"🏆 Maiores Altas e Quedas - {top_movers['data'].strftime('%d/%m/%Y')}")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**🟢 Maiores Altas**")
            for loja, var in top_movers["maiores_altas"]:
                st.markdown(f"- **{loja}**: {format_variation(var)}")

        with col2:
            st.markdown("**🔴 Maiores Quedas**")
            for loja, var in top_movers["maiores_quedas"]:
                st.markdown(f"- **{loja}**: {format_variation(var)}")

    st.markdown("---")

    # Gráfico de linhas comparando lojas selecionadas
    st.subheader("📊 Evolução Comparativa por Loja")

    df_filtered = df_stores.loc[selected_stores]

    fig = go.Figure()
    for i, loja in enumerate(selected_stores):
        fig.add_trace(
            go.Scatter(
                x=df_filtered.columns,
                y=df_filtered.loc[loja].values,
                mode="lines+markers",
                name=loja,
                line=dict(color=Colors.PLOTLY_PALETTE[i % len(Colors.PLOTLY_PALETTE)], width=2),
                marker=dict(size=6),
            )
        )

    # Linha de meta
    fig.add_hline(
        y=1.0,
        line_dash="dash",
        line_color=Colors.WARNING,
        annotation_text="Meta (100%)",
    )

    fig.update_layout(
        title="Evolução Diária do Índice por Loja",
        xaxis_title="Data",
        yaxis_title="Índice de Atingimento",
        height=LAYOUT_CONFIG["CHART_HEIGHT"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT_TEMPLATE["layout"],
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Tabela de variação diária
    st.subheader("📋 Tabela de Variação Diária")

    df_variation_filtered = df_variation.loc[selected_stores]
    df_table = prepare_variation_table(df_variation_filtered)

    # Exibe tabela
    st.dataframe(
        df_table,
        use_container_width=True,
        height=400,
    )

    # Botão de exportação
    col1, col2 = st.columns(2)
    with col1:
        csv_data = export_to_csv(df_variation_filtered)
        st.download_button(
            label="📥 Exportar CSV",
            data=csv_data,
            file_name="dashid_variacao_diaria.csv",
            mime="text/csv",
        )

    with col2:
        excel_data = export_to_excel(df_variation_filtered)
        st.download_button(
            label="📥 Exportar Excel",
            data=excel_data,
            file_name="dashid_variacao_diaria.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_dia_da_semana(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a seção de Análise por Dia da Semana."""
    st.header("📅 Análise por Dia da Semana")

    # Análise consolidada
    st.subheader("📊 Desempenho Médio por Dia da Semana (Consolidado)")
    df_weekday = analyze_by_weekday(df_stores)

    if not df_weekday.empty:
        # Gráfico de barras
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_weekday.index,
                y=df_weekday["media"],
                name="Média",
                marker_color=Colors.PRIMARY,
            )
        )

        fig.add_hline(
            y=1.0,
            line_dash="dash",
            line_color=Colors.WARNING,
            annotation_text="Meta (100%)",
        )

        fig.update_layout(
            title="Índice Médio por Dia da Semana",
            xaxis_title="Dia da Semana",
            yaxis_title="Índice de Atingimento",
            height=LAYOUT_CONFIG["CHART_HEIGHT_SMALL"],
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

        # Tabela de estatísticas
        st.dataframe(
            df_weekday.style.format({
                "media": lambda x: f"{x*100:.2f}%",
                "mediana": lambda x: f"{x*100:.2f}%",
                "desvio_padrao": lambda x: f"{x*100:.2f}%",
            }),
            use_container_width=True,
        )

    st.markdown("---")

    # Heatmap por loja e dia da semana
    st.subheader("🔥 Heatmap: Desempenho por Loja e Dia da Semana")
    df_weekday_store = analyze_weekday_by_store(df_stores.loc[selected_stores])

    if not df_weekday_store.empty:
        fig = px.imshow(
            df_weekday_store.values,
            x=df_weekday_store.columns,
            y=df_weekday_store.index,
            color_continuous_scale=[
                (0.0, Colors.DANGER),
                (0.5, Colors.CARD_BG),
                (1.0, Colors.SUCCESS),
            ],
            labels={"color": "Índice"},
            aspect="auto",
        )

        fig.update_layout(
            title="Heatmap de Desempenho por Loja e Dia da Semana",
            height=max(400, len(selected_stores) * 30),
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

    # Melhor e pior dia por loja
    st.subheader("🏆 Melhor e Pior Dia da Semana por Loja")
    df_best_worst = get_best_worst_weekday(df_weekday_store)

    if not df_best_worst.empty:
        st.dataframe(
            df_best_worst.style.format({
                "melhor_valor": lambda x: f"{x*100:.2f}%",
                "pior_valor": lambda x: f"{x*100:.2f}%",
            }),
            use_container_width=True,
            height=400,
        )


def render_ranking(df_stores: pd.DataFrame):
    """Renderiza a seção de Ranking de Lojas."""
    st.header("🏆 Ranking de Lojas")

    # Ranking do mês
    st.subheader("📊 Ranking por Índice Médio Acumulado (Mês)")
    df_ranking = calculate_store_ranking(df_stores, period="month")

    if not df_ranking.empty:
        # Tabela formatada
        st.dataframe(
            df_ranking.style.format({
                "indice_medio": lambda x: f"{x*100:.2f}%",
                "variacao_semanal": lambda x: f"{x:+.2f}%" if pd.notna(x) else "-",
            }).background_gradient(
                subset=["indice_medio"],
                cmap="RdYlGn",
                vmin=0.8,
                vmax=1.2,
            ),
            use_container_width=True,
            height=500,
        )

        # Gráfico de barras do ranking
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_ranking["indice_medio"],
                y=df_ranking["loja"],
                orientation="h",
                marker_color=Colors.PRIMARY,
                text=df_ranking["indice_medio"].apply(lambda x: f"{x*100:.2f}%"),
                textposition="auto",
            )
        )

        fig.add_vline(
            x=1.0,
            line_dash="dash",
            line_color=Colors.WARNING,
            annotation_text="Meta",
        )

        fig.update_layout(
            title="Ranking de Lojas por Índice Médio",
            xaxis_title="Índice de Atingimento",
            yaxis=dict(autorange="reversed"),
            height=max(400, len(df_ranking) * 30),
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

    # Exportação
    csv_data = export_to_csv(df_ranking)
    st.download_button(
        label="📥 Exportar Ranking (CSV)",
        data=csv_data,
        file_name="dashid_ranking_lojas.csv",
        mime="text/csv",
    )


def render_medias_moveis_tendencia(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a seção de Médias Móveis e Tendência."""
    st.header("📉 Médias Móveis e Tendência")

    # Médias móveis
    st.subheader("📊 Médias Móveis (3 e 7 dias)")
    mas = calculate_moving_averages(df_stores.loc[selected_stores])

    if mas:
        # Gráfico comparativo para loja selecionada
        loja_selecionada = st.selectbox(
            "Selecione uma loja para visualizar:",
            options=selected_stores,
            index=0,
        )

        fig = go.Figure()

        # Dados originais
        fig.add_trace(
            go.Scatter(
                x=df_stores.columns,
                y=df_stores.loc[loja_selecionada].values,
                mode="lines",
                name="Original",
                line=dict(color=Colors.TEXT_MUTED, width=1, dash="dot"),
            )
        )

        # MMA 3 dias
        if 3 in mas:
            fig.add_trace(
                go.Scatter(
                    x=mas[3].columns,
                    y=mas[3].loc[loja_selecionada].values,
                    mode="lines",
                    name="MMA 3 dias",
                    line=dict(color=Colors.INFO, width=2),
                )
            )

        # MMA 7 dias
        if 7 in mas:
            fig.add_trace(
                go.Scatter(
                    x=mas[7].columns,
                    y=mas[7].loc[loja_selecionada].values,
                    mode="lines",
                    name="MMA 7 dias",
                    line=dict(color=Colors.SECONDARY, width=2),
                )
            )

        fig.add_hline(y=1.0, line_dash="dash", line_color=Colors.WARNING)

        fig.update_layout(
            title=f"Médias Móveis - {loja_selecionada}",
            xaxis_title="Data",
            yaxis_title="Índice de Atingimento",
            height=LAYOUT_CONFIG["CHART_HEIGHT"],
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Tendência (regressão linear)
    st.subheader("📈 Análise de Tendência (Regressão Linear)")
    df_trend = calculate_trend(df_stores)

    if not df_trend.empty:
        # Tabela de tendências
        st.dataframe(
            df_trend.style.format({
                "inclinacao": lambda x: f"{x:.4f}" if pd.notna(x) else "-",
            }),
            use_container_width=True,
            height=400,
        )

        # Gráfico de distribuição de tendências
        trend_counts = df_trend["classificacao_tendencia"].value_counts()

        fig = go.Figure()
        fig.add_trace(
            go.Pie(
                labels=trend_counts.index,
                values=trend_counts.values,
                marker=dict(colors=[Colors.SUCCESS, Colors.NEUTRAL, Colors.DANGER]),
                textinfo="label+percent",
            )
        )

        fig.update_layout(
            title="Distribuição de Tendências por Loja",
            height=400,
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)


def render_alertas_consistencia(df_stores: pd.DataFrame):
    """Renderiza a seção de Alertas e Consistência."""
    st.header("⚠️ Alertas e Consistência")

    # Alertas de queda consecutiva
    st.subheader("🔴 Alertas de Queda Consecutiva")
    df_variation = calculate_daily_variation(df_stores)
    df_alerts = detect_consecutive_drops(df_variation, threshold=3)

    if not df_alerts.empty:
        st.warning(f"⚠️ {len(df_alerts)} loja(s) com 3 ou mais dias consecutivos de queda:")
        st.dataframe(
            df_alerts.style.format({
                "ultima_data": lambda x: x.strftime("%d/%m/%Y") if pd.notna(x) else "-",
            }),
            use_container_width=True,
        )
    else:
        st.success("✅ Nenhuma loja com quedas consecutivas críticas")

    st.markdown("---")

    # Volatilidade / Consistência
    st.subheader("📊 Volatilidade e Consistência")
    df_volatility = calculate_volatility(df_stores)

    if not df_volatility.empty:
        st.dataframe(
            df_volatility.style.format({
                "desvio_padrao": lambda x: f"{x*100:.2f}%",
            }),
            use_container_width=True,
            height=400,
        )

        # Gráfico de barras da volatilidade
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_volatility["desvio_padrao"],
                y=df_volatility["loja"],
                orientation="h",
                marker_color=Colors.SECONDARY,
                text=df_volatility["classificacao"],
                textposition="auto",
            )
        )

        fig.update_layout(
            title="Volatilidade por Loja (Desvio Padrão)",
            xaxis_title="Desvio Padrão",
            yaxis=dict(autorange="reversed"),
            height=max(400, len(df_volatility) * 25),
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)


def render_comparativo_canal(df_stores: pd.DataFrame, df_channels: pd.DataFrame):
    """Renderiza a seção de Comparativo por Canal."""
    st.header("🏢 Comparativo por Canal/Região")

    df_channel_agg = aggregate_by_channel(df_channels, df_stores)

    if not df_channel_agg.empty:
        # Tabela de canais
        st.dataframe(
            df_channel_agg.style.format({
                "indice_medio": lambda x: f"{x*100:.2f}%",
                "variacao_ultimo_dia": lambda x: f"{x:+.2f}%" if pd.notna(x) else "-",
            }),
            use_container_width=True,
        )

        # Gráfico de barras comparativo
        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_channel_agg["canal"],
                y=df_channel_agg["indice_medio"],
                marker_color=Colors.PRIMARY,
                text=df_channel_agg["indice_medio"].apply(lambda x: f"{x*100:.2f}%"),
                textposition="auto",
            )
        )

        fig.add_hline(y=1.0, line_dash="dash", line_color=Colors.WARNING)

        fig.update_layout(
            title="Índice Médio por Canal/Região",
            xaxis_title="Canal",
            yaxis_title="Índice de Atingimento",
            height=LAYOUT_CONFIG["CHART_HEIGHT_SMALL"],
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Nenhum dado de canal disponível.")


def render_distribuicao(df_stores: pd.DataFrame):
    """Renderiza a seção de Distribuição."""
    st.header("📊 Distribuição dos Índices")

    df_dist = calculate_distribution(df_stores, bins=20)

    if not df_dist.empty:
        # Histograma
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
            title="Distribuição dos Índices Diários",
            xaxis_title="Faixa de Índice",
            yaxis_title="Frequência",
            height=LAYOUT_CONFIG["CHART_HEIGHT"],
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

        # Tabela de distribuição
        st.dataframe(
            df_dist.style.format({
                "percentual": lambda x: f"{x:.2f}%",
            }),
            use_container_width=True,
        )


# ============================================================================
# MAIN
# ============================================================================


def main():
    """Função principal da aplicação."""
    # Renderiza sidebar e obtém navegação
    navigation, uploaded_file = render_sidebar()

    # Processa upload de arquivo
    if uploaded_file is not None:
        try:
            with st.spinner("Carregando dados..."):
                data = load_data_from_upload(uploaded_file)
                st.session_state["data"] = data
        except Exception as e:
            st.error(f"❌ Erro ao carregar arquivo: {e}")
            return

    # Verifica se há dados carregados
    if "data" not in st.session_state:
        st.title(f"📊 {PROJECT_NAME}")
        st.info(
            "👈 Envie uma planilha Excel (.xlsx) na barra lateral para começar a análise, "
            "ou configure o SharePoint para carregamento automático."
        )
        return

    # Extrai dados do session_state
    data = st.session_state["data"]
    df_stores = data["stores"]
    df_channels = data["channels"]
    selected_stores = st.session_state.get("selected_stores", data["store_names"])

    # Renderiza seção selecionada
    if navigation == "📊 Visão Geral":
        render_visao_geral(df_stores)
    elif navigation == "📈 Análise Horizontal":
        render_analise_horizontal(df_stores, selected_stores)
    elif navigation == "📅 Dia da Semana":
        render_dia_da_semana(df_stores, selected_stores)
    elif navigation == "🏆 Ranking de Lojas":
        render_ranking(df_stores)
    elif navigation == "📉 Médias Móveis e Tendência":
        render_medias_moveis_tendencia(df_stores, selected_stores)
    elif navigation == "⚠️ Alertas e Consistência":
        render_alertas_consistencia(df_stores)
    elif navigation == "🏢 Comparativo por Canal":
        render_comparativo_canal(df_stores, df_channels)
    elif navigation == "📊 Distribuição":
        render_distribuicao(df_stores)


if __name__ == "__main__":
    main()
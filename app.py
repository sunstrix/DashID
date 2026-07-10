"""
DashID - Aplicação Principal Streamlit
=======================================

Dashboard de análise de performance diária de lojas da NSF Cosméticos
e Presentes (Cp Fani).

META DO ID: 115% (1.15) - Consulta de CPF do cliente no sistema.

Estrutura:
- Sidebar: upload de arquivo, navegação, filtros
- Visão Geral: KPIs de topo (cards) com meta 115%
- Análise Horizontal: variação diária, gráfico de linhas, top movers
- Análise por Dia da Semana: agrupamento, heatmap, melhor/pior dia
- Ranking de Lojas: tabela ordenável com variação semanal
- Médias Móveis e Tendência: suavização e regressão linear
- Alertas e Consistência: quedas consecutivas, volatilidade
- Comparativo por Canal: agregação por região
- Distribuição: histograma dos índices

Autor: Alex Paulo
Versão: 0.2.0
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
    META_ID,
    PLOTLY_LAYOUT_TEMPLATE,
    PROJECT_DESCRIPTION,
    PROJECT_NAME,
    PROJECT_VERSION,
    format_meta_info,
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
                <p style="color: {Colors.PRIMARY}; font-size: 0.85rem; margin-top: 4px;
                   font-weight: 600;">
                    🎯 Meta do ID: {META_ID*100:.0f}%
                </p>
                <p style="color: {Colors.TEXT_MUTED}; font-size: 0.75rem; margin-top: 2px;">
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
                help=(
                    "Arquivo Excel com índice de atingimento de meta por loja "
                    "e por dia. Meta do ID: 115%."
                ),
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

            date_start = "-"
            date_end = "-"
            if metadata["date_range"][0] is not None:
                try:
                    date_start = metadata["date_range"][0].strftime("%d/%m/%Y")
                except:
                    date_start = str(metadata["date_range"][0])
            if metadata["date_range"][1] is not None:
                try:
                    date_end = metadata["date_range"][1].strftime("%d/%m/%Y")
                except:
                    date_end = str(metadata["date_range"][1])

            st.markdown(
                f"""
                - **Arquivo:** {metadata['filename']}
                - **Tamanho:** {metadata['file_size_mb']:.2f} MB
                - **Lojas:** {metadata['num_stores']}
                - **Canais:** {metadata['num_channels']}
                - **Dias com dados:** {metadata['num_days']}
                - **Período:** {date_start} a {date_end}
                - **🎯 Meta:** {META_ID*100:.0f}%
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


def meta_label() -> str:
    """Retorna label da meta formatada."""
    return f"Meta ({META_ID*100:.0f}%)"


# ============================================================================
# SEÇÕES DO DASHBOARD
# ============================================================================


def render_visao_geral(df_stores: pd.DataFrame):
    """Renderiza a seção de Visão Geral com KPIs de topo."""
    st.header("📊 Visão Geral")
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% (consulta de CPF do cliente)")

    # Calcula KPIs
    kpis = calculate_kpi_cards(df_stores)

    # Cards de KPI
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        media_geral_pct = format_percentage(kpis["media_geral"])
        delta_text = "✅ Acima da meta" if kpis["media_geral"] >= META_ID else "⚠️ Abaixo da meta"
        st.metric(
            label="Índice Médio MTD",
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

    # Linha de meta (1.15)
    fig.add_hline(
        y=META_ID,
        line_dash="dash",
        line_color=Colors.WARNING,
        annotation_text=meta_label(),
        annotation_position="top right",
        annotation_font_color=Colors.WARNING,
    )

    fig.update_layout(
        title=f"Índice Médio de Atingimento - Evolução Diária (Meta: {META_ID*100:.0f}%)",
        xaxis_title="Data",
        yaxis_title="Índice de Atingimento",
        height=LAYOUT_CONFIG["CHART_HEIGHT"],
        **PLOTLY_LAYOUT_TEMPLATE["layout"],
    )

    st.plotly_chart(fig, use_container_width=True)

    # Tabela resumo por loja (último dia disponível)
    st.subheader("📋 Performance por Loja (Último Dia)")
    last_date = None
    has_data = df_stores.notna().any()
    dates_with_data = has_data[has_data].index
    if len(dates_with_data) > 0:
        last_date = dates_with_data.max()

    if last_date is not None:
        ultimo_dia_df = pd.DataFrame({
            "Loja": df_stores.index,
            f"Índice ({last_date.strftime('%d/%m') if hasattr(last_date, 'strftime') else last_date})": df_stores[last_date].values,
            "Status": df_stores[last_date].apply(
                lambda x: "✅ Acima" if pd.notna(x) and x >= META_ID else ("⚠️ Abaixo" if pd.notna(x) else "❌ Sem dado")
            ),
        })

        st.dataframe(
            ultimo_dia_df.style.format({
                f"Índice ({last_date.strftime('%d/%m') if hasattr(last_date, 'strftime') else last_date})": lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-",
            }),
            use_container_width=True,
            height=500,
        )


def render_analise_horizontal(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a seção de Análise Horizontal."""
    st.header("📈 Análise Horizontal (Dia a Dia)")
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Variação = (dia atual / dia anterior) - 1")

    # Calcula variação diária
    df_variation = calculate_daily_variation(df_stores)

    # Top movers
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
            else:
                st.info("Nenhuma variação positiva no último dia.")

        with col2:
            st.markdown("**🔴 Maiores Quedas**")
            if top_movers["maiores_quedas"]:
                for loja, var in top_movers["maiores_quedas"]:
                    st.markdown(f"- **{loja}**: {format_variation(var)}")
            else:
                st.info("Nenhuma variação negativa no último dia.")

    st.markdown("---")

    # Gráfico de linhas comparando lojas selecionadas
    st.subheader("📊 Evolução Comparativa por Loja")

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

    # Linha de meta (1.15)
    fig.add_hline(
        y=META_ID,
        line_dash="dash",
        line_color=Colors.WARNING,
        annotation_text=meta_label(),
        annotation_font_color=Colors.WARNING,
    )

    fig.update_layout(
        title=f"Evolução Diária do Índice por Loja (Meta: {META_ID*100:.0f}%)",
        xaxis_title="Data",
        yaxis_title="Índice de Atingimento",
        height=LAYOUT_CONFIG["CHART_HEIGHT"],
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **PLOTLY_LAYOUT_TEMPLATE["layout"],
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # Tabela de valores absolutos
    st.subheader("📋 Tabela de Valores por Loja e Dia")

    df_table_abs = df_filtered.copy()
    for col in df_table_abs.columns:
        df_table_abs[col] = df_table_abs[col].apply(
            lambda x: f"{x*100:.2f}%" if pd.notna(x) else "-"
        )

    st.dataframe(
        df_table_abs,
        use_container_width=True,
        height=400,
    )

    # Exportação tabela de valores
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv_data = export_to_csv(df_filtered)
        st.download_button(
            label="📥 Exportar Valores (CSV)",
            data=csv_data,
            file_name="dashid_valores_diarios.csv",
            mime="text/csv",
        )

    with col_exp2:
        excel_data = export_to_excel(df_filtered)
        st.download_button(
            label="📥 Exportar Valores (Excel)",
            data=excel_data,
            file_name="dashid_valores_diarios.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.markdown("---")

    # Tabela de variação diária
    st.subheader("📋 Tabela de Variação Diária")

    df_variation_filtered = df_variation.loc[
        [s for s in stores_to_plot if s in df_variation.index]
    ]
    df_table_var = prepare_variation_table(df_variation_filtered)

    st.dataframe(
        df_table_var,
        use_container_width=True,
        height=400,
    )

    # Botão de exportação variação
    col_exp3, col_exp4 = st.columns(2)
    with col_exp3:
        csv_data_var = export_to_csv(df_variation_filtered)
        st.download_button(
            label="📥 Exportar Variação (CSV)",
            data=csv_data_var,
            file_name="dashid_variacao_diaria.csv",
            mime="text/csv",
        )

    with col_exp4:
        excel_data_var = export_to_excel(df_variation_filtered)
        st.download_button(
            label="📥 Exportar Variação (Excel)",
            data=excel_data_var,
            file_name="dashid_variacao_diaria.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_dia_da_semana(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a seção de Análise por Dia da Semana."""
    st.header("📅 Análise por Dia da Semana")
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Agrupamento por dia da semana")

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
            title=f"Índice Médio por Dia da Semana (Meta: {META_ID*100:.0f}%)",
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

        # Melhor e pior dia consolidado
        if not df_weekday["media"].isna().all():
            melhor_dia = df_weekday["media"].idxmax()
            pior_dia = df_weekday["media"].idxmin()
            col_info1, col_info2 = st.columns(2)
            with col_info1:
                st.success(f"🏆 Melhor dia: **{melhor_dia}** ({df_weekday.loc[melhor_dia, 'media']*100:.2f}%)")
            with col_info2:
                st.error(f"⚠️ Pior dia: **{pior_dia}** ({df_weekday.loc[pior_dia, 'media']*100:.2f}%)")

    st.markdown("---")

    # Heatmap por loja e dia da semana
    st.subheader("🔥 Heatmap: Desempenho por Loja e Dia da Semana")
    stores_for_heatmap = [s for s in selected_stores if s in df_stores.index]
    if not stores_for_heatmap:
        stores_for_heatmap = df_stores.index.tolist()

    df_weekday_store = analyze_weekday_by_store(df_stores.loc[stores_for_heatmap])

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
            height=max(400, len(stores_for_heatmap) * 30),
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
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Ordenado pelo índice médio acumulado")

    # Ranking do mês
    st.subheader("📊 Ranking por Índice Médio Acumulado (Mês)")
    df_ranking = calculate_store_ranking(df_stores, period="month")

    if not df_ranking.empty:
        # Adiciona coluna de status em relação à meta
        df_ranking_display = df_ranking.copy()
        df_ranking_display["status_meta"] = df_ranking_display["indice_medio"].apply(
            lambda x: "✅ Acima" if x >= META_ID else "⚠️ Abaixo"
        )

        # Tabela formatada
        st.dataframe(
            df_ranking_display.style.format({
                "indice_medio": lambda x: f"{x*100:.2f}%",
                "variacao_semanal": lambda x: f"{x:+.2f}%" if pd.notna(x) else "-",
            }),
            use_container_width=True,
            height=500,
        )

        # Gráfico de barras do ranking
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
            title=f"Ranking de Lojas por Índice Médio (Meta: {META_ID*100:.0f}%)",
            xaxis_title="Índice de Atingimento",
            yaxis=dict(autorange="reversed"),
            height=max(400, len(df_ranking) * 30),
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

    # Exportação
    col_exp1, col_exp2 = st.columns(2)
    with col_exp1:
        csv_data = export_to_csv(df_ranking)
        st.download_button(
            label="📥 Exportar Ranking (CSV)",
            data=csv_data,
            file_name="dashid_ranking_lojas.csv",
            mime="text/csv",
        )

    with col_exp2:
        excel_data = export_to_excel(df_ranking)
        st.download_button(
            label="📥 Exportar Ranking (Excel)",
            data=excel_data,
            file_name="dashid_ranking_lojas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )


def render_medias_moveis_tendencia(df_stores: pd.DataFrame, selected_stores: list):
    """Renderiza a seção de Médias Móveis e Tendência."""
    st.header("📉 Médias Móveis e Tendência")
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Suavização e regressão linear")

    # Médias móveis
    st.subheader("📊 Médias Móveis (3 e 7 dias)")
    stores_for_ma = [s for s in selected_stores if s in df_stores.index]
    if not stores_for_ma:
        stores_for_ma = df_stores.index.tolist()[:1]

    mas = calculate_moving_averages(df_stores.loc[stores_for_ma])

    if mas:
        # Gráfico comparativo para loja selecionada
        loja_selecionada = st.selectbox(
            "Selecione uma loja para visualizar:",
            options=stores_for_ma,
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

        # MMA 7 dias
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
            title=f"Médias Móveis - {loja_selecionada} (Meta: {META_ID*100:.0f}%)",
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
        # Adiciona coluna de status em relação à meta
        media_atual = df_stores.mean(axis=1)
        df_trend["status_meta"] = media_atual.apply(
            lambda x: "✅ Acima" if x >= META_ID else "⚠️ Abaixo"
        )

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

        color_map = {
            "Alta": Colors.SUCCESS,
            "Estável": Colors.NEUTRAL,
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
            title="Distribuição de Tendências por Loja",
            height=400,
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)


def render_alertas_consistencia(df_stores: pd.DataFrame):
    """Renderiza a seção de Alertas e Consistência."""
    st.header("⚠️ Alertas e Consistência")
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Monitoramento de quedas e volatilidade")

    # Alertas de queda consecutiva
    st.subheader("🔴 Alertas de Queda Consecutiva")
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
        st.success("✅ Nenhuma loja com quedas consecutivas críticas (3+ dias)")

    st.markdown("---")

    # Lojas abaixo da meta no último dia
    st.subheader(f"🚨 Lojas Abaixo da Meta (<{META_ID*100:.0f}%) no Último Dia")
    has_data = df_stores.notna().any()
    dates_with_data = has_data[has_data].index
    if len(dates_with_data) > 0:
        last_date = dates_with_data.max()
        ultimo_dia = df_stores[last_date].dropna()
        abaixo_meta = ultimo_dia[ultimo_dia < META_ID]

        if len(abaixo_meta) > 0:
            df_abaixo = pd.DataFrame({
                "Loja": abaixo_meta.index,
                "Índice": abaixo_meta.values,
                "Distância da Meta": abaixo_meta.apply(lambda x: META_ID - x),
            })
            df_abaixo = df_abaixo.sort_values("Índice", ascending=True)

            st.error(f"🔴 {len(abaixo_meta)} loja(s) abaixo da meta no último dia:")
            st.dataframe(
                df_abaixo.style.format({
                    "Índice": lambda x: f"{x*100:.2f}%",
                    "Distância da Meta": lambda x: f"-{x*100:.2f}%",
                }),
                use_container_width=True,
            )
        else:
            st.success(f"✅ Todas as lojas estão acima da meta de {META_ID*100:.0f}% no último dia!")
    else:
        st.info("Sem dados disponíveis para análise.")

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
        color_map_vol = {
            "Consistente": Colors.SUCCESS,
            "Moderado": Colors.WARNING,
            "Instável": Colors.DANGER,
        }
        bar_colors = [color_map_vol.get(c, Colors.NEUTRAL) for c in df_volatility["classificacao"]]

        fig = go.Figure()
        fig.add_trace(
            go.Bar(
                x=df_volatility["desvio_padrao"],
                y=df_volatility["loja"],
                orientation="h",
                marker_color=bar_colors,
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
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Agregação por canal")

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
            title=f"Índice Médio por Canal/Região (Meta: {META_ID*100:.0f}%)",
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
    st.caption(f"🎯 Meta do ID: {META_ID*100:.0f}% | Concentração de performance")

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

        # Linha vertical na meta (1.15)
        # Encontramos a faixa mais próxima da meta para anotar
        fig.update_layout(
            title=f"Distribuição dos Índices Diários (Meta: {META_ID*100:.0f}%)",
            xaxis_title="Faixa de Índice",
            yaxis_title="Frequência",
            height=LAYOUT_CONFIG["CHART_HEIGHT"],
            **PLOTLY_LAYOUT_TEMPLATE["layout"],
        )

        st.plotly_chart(fig, use_container_width=True)

        # Estatísticas resumidas
        valores = df_stores.values.flatten()
        valores = valores[~np.isnan(valores)]

        if len(valores) > 0:
            acima_meta_count = (valores >= META_ID).sum()
            abaixo_meta_count = (valores < META_ID).sum()
            total = len(valores)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total de Registros", f"{total}")
            with col2:
                st.metric("Média Geral", f"{np.mean(valores)*100:.2f}%")
            with col3:
                st.metric(f"Acima da Meta (≥{META_ID*100:.0f}%)", f"{acima_meta_count} ({acima_meta_count/total*100:.1f}%)")
            with col4:
                st.metric(f"Abaixo da Meta (<{META_ID*100:.0f}%)", f"{abaixo_meta_count} ({abaixo_meta_count/total*100:.1f}%)")

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
        st.markdown(
            f"""
            <div style="text-align: center; padding: 40px 20px;">
                <h2 style="color: {Colors.PRIMARY};">Bem-vindo ao DashID</h2>
                <p style="color: {Colors.TEXT_SECONDARY}; font-size: 1.1rem;">
                    Dashboard de análise de performance diária do <strong>Índice de Identificação (ID)</strong>
                </p>
                <p style="color: {Colors.PRIMARY}; font-size: 1.3rem; font-weight: 600;">
                    🎯 Meta do ID: {META_ID*100:.0f}% (consulta de CPF do cliente)
                </p>
                <p style="color: {Colors.TEXT_MUTED}; margin-top: 20px;">
                    👈 Envie uma planilha Excel (.xlsx) na barra lateral para começar a análise.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    # Extrai dados do session_state
    data = st.session_state["data"]
    df_stores = data["stores"]
    df_channels = data["channels"]
    selected_stores = st.session_state.get("selected_stores", data["store_names"])

    # Verifica se há dados válidos
    if df_stores.empty:
        st.warning("⚠️ Nenhum dado de loja encontrado na planilha. Verifique a estrutura do arquivo.")
        return

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
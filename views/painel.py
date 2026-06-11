"""Painel Epidemiológico — dashboard executivo SINAN."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.ui import fmt_br, page_header, register_plotly_theme, render_table
from database.connection import execute_query
from utils.geo import SIGLA_UF, UF_SIGLA

TPL = register_plotly_theme()

# Aliases locais (fonte única em utils/geo.py)
UF_MAP = UF_SIGLA
UF_REVERSE = SIGLA_UF


@st.cache_data(ttl=300, show_spinner=False)
def cached_query(sql: str):
    """Cache de 5 min nas consultas do painel — evita refazer ~12 queries
    idênticas a cada interação de filtro/rerun."""
    return execute_query(sql)

MESES = {
    "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
    "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
    "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
}

page_header(
    "Painel Epidemiológico",
    "Indicadores e séries temporais — Dengue · Botulismo · Doença de Chagas",
)

# ── Filters ───────────────────────────────────────────────────────────────────
with st.expander("Filtros", expanded=True):
    col1, col2, col3 = st.columns(3)
    with col1:
        # Load available years dynamically
        @st.cache_data(ttl=300)
        def get_anos():
            df, _ = cached_query(
                "SELECT DISTINCT ano FROM sus_sinan_dengue_anual ORDER BY ano DESC LIMIT 30"
            )
            return sorted(df["ano"].tolist(), reverse=True) if df is not None else []

        anos = get_anos()
        selected_anos = st.multiselect(
            "Anos", anos, default=anos[:3] if anos else [],
            placeholder="Todos os anos"
        )

    with col2:
        uf_options = ["Todos"] + sorted(UF_MAP.values())
        selected_uf = st.selectbox("UF", uf_options)

    with col3:
        selected_mes = st.selectbox(
            "Mês (para dados mensais)",
            ["Todos"] + [f"{k} - {v}" for k, v in MESES.items()]
        )

# Build WHERE clauses
def build_where(table_type: str = "anual") -> str:
    clauses = []
    if selected_anos:
        anos_str = ", ".join(f"'{a}'" for a in selected_anos)
        clauses.append(f"ano IN ({anos_str})")
    if selected_uf != "Todos":
        cod = UF_REVERSE.get(selected_uf, "")
        if cod:
            clauses.append(f"LEFT(codigo_municipio, 2) = '{cod}'")
    if table_type == "mensal" and selected_mes != "Todos":
        mes_cod = selected_mes.split(" - ")[0]
        clauses.append(f"mes = '{mes_cod}'")
    return "WHERE " + " AND ".join(clauses) if clauses else ""


# ── KPI helpers ───────────────────────────────────────────────────────────────
def get_total(table: str, col: str, where: str) -> int:
    sql = f"SELECT COALESCE(SUM({col}), 0) AS total FROM {table} {where}"
    df, err = cached_query(sql)
    if df is not None and not df.empty:
        return int(df["total"].iloc[0])
    return 0


# ── KPIs ──────────────────────────────────────────────────────────────────────
st.markdown("##### Resumo geral")
where_anual = build_where("anual")
where_mensal = build_where("mensal")

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
with st.spinner("Carregando indicadores..."):
    total_dengue  = get_total("sus_sinan_dengue_anual",     "casos_ano", where_anual)
    total_bot     = get_total("sus_sinan_botulismo_mensal", "casos_mes", where_mensal)
    total_chagas  = get_total("sus_sinan_chagas_mensal",    "casos_mes", where_mensal)
    obitos_dengue = get_total("sus_sinan_dengue_anual", "evolucao_obito_pelo_agravo_notificado", where_anual)

letalidade = (obitos_dengue / total_dengue * 100) if total_dengue else 0
kpi1.metric("Casos de dengue",    fmt_br(total_dengue))
kpi2.metric("Casos de botulismo", fmt_br(total_bot))
kpi3.metric("Casos de Chagas",    fmt_br(total_chagas))
kpi4.metric("Óbitos por dengue",  fmt_br(obitos_dengue),
            f"{letalidade:.2f}% letalidade".replace(".", ","),
            delta_color="inverse")

st.divider()

# ── Dengue tabs ───────────────────────────────────────────────────────────────
st.markdown("##### Dengue")
tab_d1, tab_d2, tab_d3, tab_d4 = st.tabs(
    ["Por ano", "Série mensal", "Por UF", "Perfil demográfico"]
)

with tab_d1:
    sql = f"""
        SELECT ano, SUM(casos_ano) AS total
        FROM sus_sinan_dengue_anual
        {build_where('anual')}
        GROUP BY ano ORDER BY ano
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        fig = px.bar(df, x="ano", y="total", title="Casos de Dengue por Ano",
                     labels={"ano": "Ano", "total": "Casos"},
                     template=TPL, color="total",
                     color_continuous_scale="Reds")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
        render_table(df)
    else:
        st.info("Sem dados para os filtros selecionados.")

with tab_d2:
    sql = f"""
        WITH serie AS (
            SELECT ano, mes, SUM(casos_mes) AS total
            FROM sus_sinan_dengue_antigo_mensal
            {build_where('mensal')}
            GROUP BY ano, mes
            UNION ALL
            SELECT ano, mes, SUM(casos_mes) AS total
            FROM sus_sinan_dengue_mensal
            {build_where('mensal')}
            GROUP BY ano, mes
        )
        SELECT ano, mes, SUM(total) AS total
        FROM serie
        GROUP BY ano, mes
        ORDER BY ano, mes
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        df["periodo"] = df["ano"] + "-" + df["mes"]
        fig = px.line(df, x="periodo", y="total", title="Série Temporal Mensal — Dengue",
                      labels={"periodo": "Período", "total": "Casos"},
                      template=TPL, markers=True)
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados mensais para os filtros selecionados.")

with tab_d3:
    sql = f"""
        SELECT LEFT(codigo_municipio, 2) AS cod_uf, SUM(casos_ano) AS total
        FROM sus_sinan_dengue_anual
        {build_where('anual')}
        GROUP BY cod_uf
        ORDER BY total DESC
        LIMIT 27
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        df["uf"] = df["cod_uf"].map(UF_MAP).fillna(df["cod_uf"])
        fig = px.bar(df.sort_values("total", ascending=True),
                     x="total", y="uf", orientation="h",
                     title="Casos de Dengue por UF",
                     labels={"total": "Casos", "uf": "UF"},
                     template=TPL, color="total",
                     color_continuous_scale="Reds")
        fig.update_layout(showlegend=False, height=600)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para os filtros selecionados.")

with tab_d4:
    col_a, col_b = st.columns(2)
    with col_a:
        sql_sexo = f"""
            SELECT
                SUM(sexo_masculino) AS masculino,
                SUM(sexo_feminino)  AS feminino
            FROM sus_sinan_dengue_anual {build_where('anual')}
        """
        df_s, _ = cached_query(sql_sexo)
        if df_s is not None and not df_s.empty:
            row = df_s.iloc[0]
            df_pie = pd.DataFrame({
                "Sexo": ["Masculino", "Feminino"],
                "Casos": [row["masculino"] or 0, row["feminino"] or 0]
            })
            fig = px.pie(df_pie, names="Sexo", values="Casos",
                         title="Distribuição por Sexo", template=TPL)
            st.plotly_chart(fig, use_container_width=True)

    with col_b:
        sql_raca = f"""
            SELECT
                SUM(raca_branca)   AS Branca,
                SUM(raca_preta)    AS Preta,
                SUM(raca_parda)    AS Parda,
                SUM(raca_amarela)  AS Amarela,
                SUM(raca_indigena) AS Indigena
            FROM sus_sinan_dengue_anual {build_where('anual')}
        """
        df_r, _ = cached_query(sql_raca)
        if df_r is not None and not df_r.empty:
            row = df_r.iloc[0]
            df_raca = pd.DataFrame({
                "Raça": list(row.index),
                "Casos": [row[c] or 0 for c in row.index]
            })
            fig = px.bar(df_raca, x="Raça", y="Casos",
                         title="Distribuição por Raça/Cor", template=TPL,
                         color="Casos", color_continuous_scale="Blues")
            st.plotly_chart(fig, use_container_width=True)

    # Faixa etária
    sql_fe = f"""
        SELECT
            SUM(faixa_etaria_1_ano) AS "< 1 ano",
            SUM(faixa_etaria_1_4)   AS "1-4",
            SUM(faixa_etaria_5_9)   AS "5-9",
            SUM(faixa_etaria_10_14) AS "10-14",
            SUM(faixa_etaria_15_19) AS "15-19",
            SUM(faixa_etaria_20_39) AS "20-39",
            SUM(faixa_etaria_40_59) AS "40-59",
            SUM(faixa_etaria_60_64) AS "60-64",
            SUM(faixa_etaria_65_69) AS "65-69",
            SUM(faixa_etaria_70_79) AS "70-79"
        FROM sus_sinan_dengue_anual {build_where('anual')}
    """
    df_fe, _ = cached_query(sql_fe)
    if df_fe is not None and not df_fe.empty:
        row = df_fe.iloc[0]
        df_faixa = pd.DataFrame({
            "Faixa Etária": list(row.index),
            "Casos": [row[c] or 0 for c in row.index]
        })
        fig = px.bar(df_faixa, x="Faixa Etária", y="Casos",
                     title="Casos por Faixa Etária", template=TPL,
                     color="Casos", color_continuous_scale="Oranges")
        st.plotly_chart(fig, use_container_width=True)

st.divider()

# ── Botulismo ─────────────────────────────────────────────────────────────────
st.subheader("🧫 Botulismo")
tab_b1, tab_b2 = st.tabs(["📆 Série Mensal", "🗺️ Por UF"])

with tab_b1:
    sql = f"""
        SELECT ano, mes, SUM(casos_mes) AS total
        FROM sus_sinan_botulismo_mensal
        {build_where('mensal')}
        GROUP BY ano, mes ORDER BY ano, mes
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        df["periodo"] = df["ano"] + "-" + df["mes"]
        fig = px.line(df, x="periodo", y="total",
                      title="Série Temporal Mensal — Botulismo",
                      template=TPL, markers=True,
                      labels={"periodo": "Período", "total": "Casos"})
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para os filtros selecionados.")

with tab_b2:
    sql = f"""
        SELECT LEFT(codigo_municipio, 2) AS cod_uf, SUM(casos_mes) AS total
        FROM sus_sinan_botulismo_mensal
        {build_where('mensal')}
        GROUP BY cod_uf ORDER BY total DESC LIMIT 27
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        df["uf"] = df["cod_uf"].map(UF_MAP).fillna(df["cod_uf"])
        fig = px.bar(df, x="uf", y="total", title="Botulismo por UF",
                     template=TPL, color="total",
                     color_continuous_scale="Purples",
                     labels={"uf": "UF", "total": "Casos"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para os filtros selecionados.")

st.divider()

# ── Chagas ────────────────────────────────────────────────────────────────────
st.subheader("🔬 Doença de Chagas")
tab_c1, tab_c2 = st.tabs(["📆 Série Mensal", "🗺️ Por UF"])

with tab_c1:
    sql = f"""
        SELECT ano, mes, SUM(casos_mes) AS total
        FROM sus_sinan_chagas_mensal
        {build_where('mensal')}
        GROUP BY ano, mes ORDER BY ano, mes
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        df["periodo"] = df["ano"] + "-" + df["mes"]
        fig = px.line(df, x="periodo", y="total",
                      title="Série Temporal Mensal — Doença de Chagas",
                      template=TPL, markers=True,
                      labels={"periodo": "Período", "total": "Casos"})
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para os filtros selecionados.")

with tab_c2:
    sql = f"""
        SELECT LEFT(codigo_municipio, 2) AS cod_uf, SUM(casos_mes) AS total
        FROM sus_sinan_chagas_mensal
        {build_where('mensal')}
        GROUP BY cod_uf ORDER BY total DESC LIMIT 27
    """
    df, _ = cached_query(sql)
    if df is not None and not df.empty:
        df["uf"] = df["cod_uf"].map(UF_MAP).fillna(df["cod_uf"])
        fig = px.bar(df, x="uf", y="total", title="Chagas por UF",
                     template=TPL, color="total",
                     color_continuous_scale="Greens",
                     labels={"uf": "UF", "total": "Casos"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados para os filtros selecionados.")

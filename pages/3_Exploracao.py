"""🔍 Exploração dos Dados — navegação direta nas tabelas SINAN."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components.sidebar import render_sidebar
from components.theme import apply_theme
from components.ui import page_header
from config.settings import get_settings
from database.connection import execute_query

st.set_page_config(page_title="Exploração | SINAN Analytics", page_icon="◆", layout="wide")
apply_theme()
render_sidebar()

settings = get_settings()

page_header(
    "Exploração dos Dados",
    "Navegue pelas tabelas, visualize registros e gere estatísticas descritivas",
)

# ── Table selector ────────────────────────────────────────────────────────────
selected_table = st.selectbox("Selecione a tabela", settings.sinan_tables)

col_lim, col_order, col_dir = st.columns([2, 3, 2])
with col_lim:
    limit = st.selectbox("Linhas", [50, 100, 500, 1000], index=0)
with col_order:
    order_col = st.text_input("Ordenar por coluna", placeholder="ex: nu_ano")
with col_dir:
    order_dir = st.selectbox("Direção", ["DESC", "ASC"])

# ── Load data ─────────────────────────────────────────────────────────────────
schema = settings.db_schema  # SUS_SINAN
order_clause = f"ORDER BY {order_col} {order_dir}" if order_col else ""
sql = f'SELECT * FROM "{schema}".{selected_table} {order_clause} LIMIT {limit}'

if st.button("Carregar dados", use_container_width=False, type="primary"):
    with st.spinner("Executando consulta..."):
        df, error = execute_query(sql)
    if error:
        st.error(f"Erro: {error}")
    else:
        st.session_state[f"explore_{selected_table}"] = df
        st.success(f"✅ {len(df)} linhas carregadas")

df: pd.DataFrame | None = st.session_state.get(f"explore_{selected_table}")

if df is not None and not df.empty:
    tab1, tab2, tab3 = st.tabs(["Dados", "Estatísticas", "Perfil"])

    with tab1:
        st.dataframe(df, use_container_width=True, hide_index=True)
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Exportar CSV", csv, f"{selected_table}.csv", "text/csv")

    with tab2:
        num_cols = df.select_dtypes(include="number")
        if not num_cols.empty:
            st.markdown("##### Estatísticas numéricas")
            st.dataframe(num_cols.describe().round(2), use_container_width=True)
        else:
            st.info("Nenhuma coluna numérica encontrada.")

    with tab3:
        st.markdown("##### Perfil das colunas")
        profile_rows = []
        for col in df.columns:
            profile_rows.append({
                "Coluna": col,
                "Tipo": str(df[col].dtype),
                "Não-nulos": int(df[col].notna().sum()),
                "Nulos": int(df[col].isna().sum()),
                "% Nulos": f"{df[col].isna().mean() * 100:.1f}%",
                "Únicos": int(df[col].nunique()),
                "Top valor": str(df[col].mode().iloc[0]) if not df[col].mode().empty else "—",
            })
        st.dataframe(pd.DataFrame(profile_rows), use_container_width=True, hide_index=True)
else:
    st.info("Clique em **Carregar dados** para visualizar os registros.")

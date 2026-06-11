"""Dicionário da Base — metadados das tabelas SINAN."""
from __future__ import annotations

import json
import os

import pandas as pd
import streamlit as st

from components.ui import fmt_br, page_header, render_table
from database.schema_loader import load_schema

page_header(
    "Dicionário de Dados",
    "Metadados completos das tabelas SINAN — tipos, descrições e exemplos",
)

# ── Load data ─────────────────────────────────────────────────────────────────
@st.cache_data(show_spinner="Carregando dicionário...")
def get_combined_dict() -> pd.DataFrame:
    """
    Constrói o dicionário combinando:
      1. Dicionário JSON curado (sempre carrega — base principal)
      2. Metadados do banco (enriquece tipo e nullable quando disponível)
    """
    _EMPTY_COLS = ["Tabela", "Coluna", "Tipo (DB)", "Nullable", "Descrição", "Exemplo"]

    # ── 1. Carrega JSON curado ────────────────────────────────────────────────
    dict_path = os.path.join(os.path.dirname(__file__), "..", "data", "dicionario_sinan.json")
    rows: list[dict] = []
    try:
        with open(dict_path, encoding="utf-8") as f:
            curated = json.load(f)

        # Suporta tanto "tabelas" (PT) quanto "tables" (EN)
        tabelas = curated.get("tabelas") or curated.get("tables") or {}
        for tname, tinfo in tabelas.items():
            # Suporta "colunas" (PT) ou "columns" (EN)
            colunas = tinfo.get("colunas") or tinfo.get("columns") or []
            for col in colunas:
                rows.append({
                    "Tabela": tname,
                    "Coluna":   col.get("nome")     or col.get("name", ""),
                    "Tipo (DB)":col.get("tipo")     or col.get("type", ""),
                    "Nullable": str(col.get("nulo") or col.get("nullable", "")),
                    "Descrição":col.get("descricao")or col.get("description", ""),
                    "Exemplo":  str(col.get("exemplo") or col.get("example", "")),
                })
    except Exception:
        pass

    # ── 2. Enriquece com schema real do banco (opcional) ──────────────────────
    try:
        schema = load_schema()
        db_lookup: dict[tuple, dict] = {}
        for table, cols in schema.items():
            for c in cols:
                db_lookup[(table, c["column"])] = c

        if rows:
            # Atualiza tipo/nullable com o valor real do banco
            for row in rows:
                key = (row["Tabela"], row["Coluna"])
                if key in db_lookup:
                    row["Tipo (DB)"] = db_lookup[key].get("type", row["Tipo (DB)"])
                    row["Nullable"]  = str(db_lookup[key].get("nullable", row["Nullable"]))
        else:
            # Banco disponível mas JSON não — usa schema bruto
            for table, cols in schema.items():
                for c in cols:
                    rows.append({
                        "Tabela": table,
                        "Coluna": c["column"],
                        "Tipo (DB)": c["type"],
                        "Nullable": c["nullable"],
                        "Descrição": "",
                        "Exemplo": "",
                    })
    except Exception:
        pass

    if not rows:
        return pd.DataFrame(columns=_EMPTY_COLS)

    return pd.DataFrame(rows)


df_dict = get_combined_dict()

if df_dict.empty:
    st.warning(
        "⚠️ Nenhum metadado carregado. "
        "Verifique se `data/dicionario_sinan.json` existe ou se o banco está acessível."
    )
    st.stop()

# ── Top metrics ───────────────────────────────────────────────────────────────
m1, m2, m3 = st.columns(3)
m1.metric("Tabelas", fmt_br(df_dict["Tabela"].nunique()))
m2.metric("Colunas", fmt_br(len(df_dict)))
m3.metric("Com descrição", fmt_br(int((df_dict["Descrição"] != "").sum())))

st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
col_s, col_t = st.columns([3, 2])
with col_s:
    search = st.text_input("Buscar coluna ou descrição", placeholder="ex: municipio, casos, óbito...")
with col_t:
    tables = ["Todas"] + sorted(df_dict["Tabela"].unique().tolist())
    selected_table = st.selectbox("Filtrar por tabela", tables)

filtered = df_dict.copy()
if selected_table != "Todas":
    filtered = filtered[filtered["Tabela"] == selected_table]
if search:
    mask = (
        filtered["Coluna"].str.contains(search, case=False, na=False) |
        filtered["Descrição"].str.contains(search, case=False, na=False)
    )
    filtered = filtered[mask]

st.caption(f"Exibindo **{len(filtered)}** colunas")

# ── Table display (HTML temático — segue dark/light) ─────────────────────────
_SHOW = ["Coluna", "Tipo (DB)", "Nullable", "Descrição", "Exemplo"]
if selected_table == "Todas":
    for table_name in sorted(df_dict["Tabela"].unique()):
        tdata = filtered[filtered["Tabela"] == table_name]
        if tdata.empty:
            continue
        with st.expander(f"{table_name}  ·  {len(tdata)} colunas", expanded=False):
            render_table(tdata[_SHOW].reset_index(drop=True))
else:
    render_table(filtered[_SHOW].reset_index(drop=True))

# ── Export ────────────────────────────────────────────────────────────────────
st.divider()
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button(
    "Exportar CSV",
    csv,
    "dicionario_sinan.csv",
    "text/csv",
    use_container_width=False,
)

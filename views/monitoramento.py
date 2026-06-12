"""Monitoramento — dashboard operacional."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from components.ui import fmt_br, page_header, register_plotly_theme, render_table
from services.monitoring_service import MonitoringService
from utils.auth import admin_unlocked

TPL = register_plotly_theme()

monitoring = MonitoringService()

page_header(
    "Monitoramento",
    "Auditoria operacional — consultas, tokens, custo estimado e latência",
)
st.caption(
    "Os logs ficam em SQLite local — em hospedagem efêmera (Streamlit Cloud), "
    "são zerados a cada redeploy."
)

# ── Refresh / Clear ───────────────────────────────────────────────────────────
col_r, col_c, _ = st.columns([2, 2, 8])
with col_r:
    if st.button("Atualizar", use_container_width=True):
        st.rerun()
with col_c:
    # Ação destrutiva — visível apenas para o admin (ou em dev local sem senha)
    if admin_unlocked():
        if st.button("Limpar logs", use_container_width=True):
            monitoring.clear_logs()
            st.success("Logs limpos.")
            st.rerun()

st.divider()

# ── Metrics ───────────────────────────────────────────────────────────────────
stats = monitoring.get_stats()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Consultas",        fmt_br(stats["total_queries"]))
c2.metric("Latência média",   f"{stats['avg_latency_ms']:.0f} ms")
c3.metric("Tokens entrada",   fmt_br(stats["total_input_tokens"]))
c4.metric("Tokens saída",     fmt_br(stats["total_output_tokens"]))
c5.metric("Custo estimado",   f"US$ {stats['estimated_cost_usd']:.4f}")

st.divider()

# ── History ───────────────────────────────────────────────────────────────────
df = monitoring.get_history(limit=200)

if df.empty:
    st.info("Nenhuma consulta registrada ainda. Faça perguntas na página Chat Analítico.")
else:
    # Chart — queries over time
    # format="mixed" tolera timestamps com e sem fuso (logs antigos + novos)
    if "timestamp" in df.columns:
        df["timestamp"] = pd.to_datetime(
            df["timestamp"], format="mixed", utc=True, errors="coerce"
        )
        df_valid = df.dropna(subset=["timestamp"])
        df_time = (
            df_valid.set_index("timestamp")
            .resample("1h")
            .size()
            .reset_index(name="count")
        )
        if not df_time.empty:
            fig = px.bar(
                df_time, x="timestamp", y="count",
                title="Consultas por hora",
                labels={"timestamp": "Hora", "count": "Nº consultas"},
                template=TPL,
            )
            st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Histórico de consultas")
    display_cols = ["timestamp", "question", "tables_used", "input_tokens", "output_tokens", "latency_ms", "error"]
    show_cols = [c for c in display_cols if c in df.columns]
    tbl = df[show_cols].rename(columns={
        "timestamp": "Data/Hora",
        "question": "Pergunta",
        "tables_used": "Tabelas",
        "input_tokens": "Tokens Entrada",
        "output_tokens": "Tokens Saída",
        "latency_ms": "Latência (ms)",
        "error": "Erro",
    })
    render_table(tbl)

    # SQL details expander
    with st.expander("Ver SQLs executados"):
        if "sql" in df.columns:
            for _, row in df.head(20).iterrows():
                if row.get("sql"):
                    st.markdown(f"**{row.get('question', '')[:80]}**")
                    st.code(row["sql"], language="sql")
                    st.divider()

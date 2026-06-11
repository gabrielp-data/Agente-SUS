"""💬 Chat com IA — página principal do agente SINAN."""
from __future__ import annotations

import time

import pandas as pd
import streamlit as st

from agents.sinan_agent import SinanAgent
from components.sidebar import render_sidebar
from components.theme import apply_theme
from components.ui import page_header
from database.schema_loader import load_schema
from services.bedrock_service import CredentialsExpiredError
from services.monitoring_service import MonitoringService, QueryLog

st.set_page_config(
    page_title="Chat Analítico | SINAN Analytics",
    page_icon="◆",
    layout="wide",
)
apply_theme()
render_sidebar()

ASSISTANT_AVATAR = ":material/analytics:"

monitoring = MonitoringService()

# ── Session state init ────────────────────────────────────────────────────────
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "db_schema" not in st.session_state:
    with st.spinner("Carregando schema do banco..."):
        try:
            st.session_state.db_schema = load_schema()
        except Exception as exc:
            st.error(f"❌ Não foi possível conectar ao banco de dados: {exc}")
            st.info("Configure a conexão na página ⚙️ Configurações.")
            st.stop()

if "agent" not in st.session_state:
    st.session_state.agent = SinanAgent()

# ── Header ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([8, 2])
with col1:
    page_header(
        "Chat Analítico",
        "Perguntas em linguagem natural convertidas em SQL auditável",
    )
with col2:
    st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
    if st.button("Limpar conversa", use_container_width=True):
        st.session_state.chat_history = []
        st.rerun()

st.divider()

# ── Chat history display ──────────────────────────────────────────────────────
for entry in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(entry["question"])

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        st.markdown(entry["answer"])

        # SQL transparency block
        if entry.get("sql"):
            with st.expander("Ver SQL gerado", expanded=False):
                st.code(entry["sql"], language="sql")
                if entry.get("sql_explanation"):
                    st.caption(f"_{entry['sql_explanation']}_")

        # Audit details
        if entry.get("tables_used") or entry.get("filters_applied"):
            with st.expander("Detalhes da consulta", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    if entry.get("tables_used"):
                        st.markdown("**Tabelas:**")
                        for t in entry["tables_used"]:
                            st.markdown(f"- `{t}`")
                    if entry.get("columns_used"):
                        st.markdown("**Colunas:**")
                        for c in entry["columns_used"]:
                            st.markdown(f"- `{c}`")
                with c2:
                    if entry.get("filters_applied"):
                        st.markdown("**Filtros:**")
                        for f in entry["filters_applied"]:
                            st.markdown(f"- {f}")

        # Chart
        if entry.get("chart") is not None:
            st.plotly_chart(entry["chart"], use_container_width=True)

        # Results table
        if entry.get("results") is not None and not entry["results"].empty:
            with st.expander(f"Dados ({len(entry['results'])} linhas)", expanded=False):
                st.dataframe(entry["results"], use_container_width=True)

# ── Input handling ────────────────────────────────────────────────────────────
# Check if a suggestion was clicked from sidebar
default_question = st.session_state.pop("suggested_question", "")

question = st.chat_input(
    "Faça uma pergunta sobre os dados do SINAN... (ex: Quantos casos de dengue em Brasília em 2023?)"
) or default_question

if question:
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant", avatar=ASSISTANT_AVATAR):
        start_time = time.monotonic()
        result = None
        error_msg = ""

        # Progressive status display (começa fechado — mais limpo)
        with st.status("Processando consulta...", expanded=False) as status:
            try:
                result = st.session_state.agent.run(
                    question=question,
                    chat_history=st.session_state.chat_history,
                    db_schema=st.session_state.db_schema,
                )
                for step in result.get("steps", []):
                    st.write(step)
                status.update(label="Concluído", state="complete", expanded=False)

            except CredentialsExpiredError as exc:
                st.error(str(exc))
                status.update(label="Credenciais inválidas", state="error")
                error_msg = str(exc)

            except Exception as exc:
                st.error(f"Erro inesperado: {exc}")
                status.update(label="Falha na consulta", state="error")
                error_msg = str(exc)

        if result:
            # Salva no histórico — quem renderiza a resposta é o loop do histórico
            # (acima), evitando a duplicação. Por isso não desenhamos aqui.
            latency_ms = int((time.monotonic() - start_time) * 1000)
            entry = {
                "question": question,
                "answer": result.get("answer", "Sem resposta."),
                "sql": result.get("sql", ""),
                "sql_explanation": result.get("sql_explanation", ""),
                "tables_used": result.get("tables_used", []),
                "columns_used": result.get("columns_used", []),
                "filters_applied": result.get("filters_applied", []),
                "results": result.get("results"),
                "chart": result.get("chart"),
            }
            st.session_state.chat_history.append(entry)

            # Log to monitoring
            monitoring.log_query(QueryLog(
                question=question,
                sql=entry["sql"],
                answer=entry["answer"][:500],
                tables_used=", ".join(entry["tables_used"]),
                input_tokens=result.get("total_input_tokens", 0),
                output_tokens=result.get("total_output_tokens", 0),
                latency_ms=latency_ms,
            ))

        elif error_msg:
            st.session_state.chat_history.append({
                "question": question,
                "answer": f"❌ {error_msg}",
                "sql": "", "sql_explanation": "",
                "tables_used": [], "columns_used": [],
                "filters_applied": [], "results": None, "chart": None,
            })
            monitoring.log_query(QueryLog(
                question=question, error=error_msg,
                latency_ms=int((time.monotonic() - start_time) * 1000),
            ))

    # Recarrega para o histórico renderizar a resposta uma única vez (sem flicker)
    if result or error_msg:
        st.rerun()
